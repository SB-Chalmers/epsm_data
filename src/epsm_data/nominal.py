"""Deterministic physical construction handovers for Honeybee and EPSM Core.

These pure functions export the supplied construction definitions. They neither
load a catalogue nor assess targets, source review, or simulation readiness.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from copy import deepcopy

from .domain import BuildingArchetype, BuildingElement, CarbonReference
from .serialization import _encode
from .thermal.boundary_conditions import get_boundary_resistances


def _identity(kind, value):
    digest = hashlib.sha256(
        json.dumps(value, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    return f"EPSM_{kind}_{digest[:24]}"


def _metrics(layers):
    return {
        "thickness_m": sum(layer["thickness"] for layer in layers),
        "resistance_m2k_w": sum(layer["thickness"] / layer["conductivity"] for layer in layers),
        "mass_kg_m2": sum(layer["thickness"] * layer["density"] for layer in layers),
        "heat_capacity_j_m2k": sum(
            layer["thickness"] * layer["density"] * layer["specific_heat"] for layer in layers
        ),
    }


def _portable_metadata(metadata):
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise TypeError("Construction metadata must be a portable mapping")
    try:
        return json.loads(json.dumps(_encode(metadata), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError("Construction metadata must contain finite portable values") from exc


def _source_id(value):
    return None if value is None or value == "" else str(value)


def _carbon_reference_matches(reference, carbon_reference):
    expected_id = carbon_reference.identifier if carbon_reference is not None else None
    if ("carbon_reference_id" in reference
            and reference["carbon_reference_id"] != expected_id):
        return False
    if "carbon_reference" in reference:
        supplied = reference["carbon_reference"]
        if supplied is None:
            return carbon_reference is None
        if carbon_reference is None:
            return False
        try:
            return CarbonReference.from_dict(supplied) == carbon_reference
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid supplied external carbon reference") from exc
    return True


def _attach_carbon_reference(reference, carbon_reference):
    if not _carbon_reference_matches(reference, carbon_reference):
        raise ValueError("Supplied external carbon reference disagrees with attached source")
    if carbon_reference is not None:
        reference["carbon_reference_id"] = carbon_reference.identifier
        reference["carbon_reference"] = carbon_reference.to_dict()
    return reference


def _reference_matches(reference, properties, boverket_id, carbon_reference=None):
    if _source_id(reference.get("boverket_id")) != _source_id(boverket_id):
        return False
    if not _carbon_reference_matches(reference, carbon_reference):
        return False
    supplied = reference.get("properties", {})
    if not isinstance(supplied, Mapping):
        raise ValueError("Source reference properties must be a mapping")
    return all(
        key not in supplied
        or (not isinstance(supplied[key], bool) and supplied[key] == value)
        for key, value in properties.items()
    )


def _opaque_properties(material):
    return {
        field: material.roughness.value if field == "roughness" else getattr(material, field)
        for field in (
            "roughness", "conductivity", "density", "specific_heat",
            "thermal_absorptance", "solar_absorptance", "visible_absorptance",
        )
    }


def _material_references(archetype, metadata):
    supplied = metadata.get("material_references", {})
    if not isinstance(supplied, dict) or any(not isinstance(ref, dict) for ref in supplied.values()):
        raise ValueError("material_references must map identifiers to reference records")
    references = deepcopy(supplied)
    by_json_id = {ref["json_id"]: ref for ref in references.values() if ref.get("json_id")}
    for _, element in sorted(archetype.construction_set.elements.items(), key=lambda item: item[0].value):
        if element.application == BuildingElement.WINDOW:
            continue
        for component in element.components:
            for slot in component.layers:
                for constituent in slot.layer.materials:
                    material = constituent.material
                    if material.json_id in by_json_id:
                        if not _reference_matches(
                            by_json_id[material.json_id], _opaque_properties(material),
                            material.boverket_id, material.carbon_reference,
                        ):
                            raise ValueError(
                                f"Material {material.json_id}: source reference disagrees with "
                                "physical properties or Boverket ID or external carbon reference"
                            )
                        _attach_carbon_reference(
                            by_json_id[material.json_id], material.carbon_reference
                        )
                        continue
                    ref = {
                        "json_id": material.json_id,
                        "honeybee_id": None,
                        "boverket_id": material.boverket_id,
                    }
                    _attach_carbon_reference(ref, material.carbon_reference)
                    key = material.json_id or material.name
                    if key in references and references[key] != ref:
                        raise ValueError(f"Conflicting material reference: {key}")
                    references[key] = ref
                    by_json_id[material.json_id] = ref
    return dict(sorted(references.items())), by_json_id


def _window_reference(element, references):
    candidates = [
        ref for key, ref in references.items()
        if ref.get("kind") in {"simple_window", "window"}
        or key.startswith(("window_", "window:"))
    ]
    if candidates:
        properties = {"u_value": element.u_value, "shgc": element.shgc, "vt": element.vt}
        matching = [
            ref for ref in candidates
            if _reference_matches(ref, properties, element.boverket_id, element.carbon_reference)
        ]
        if len(matching) != 1:
            raise ValueError(
                "Window requires exactly one source reference matching its physical "
                "properties, Boverket ID and external carbon reference"
            )
        reference = matching[0]
        _attach_carbon_reference(reference, element.carbon_reference)
        return deepcopy(reference)
    reference = _attach_carbon_reference({
        "kind": "simple_window", "boverket_id": element.boverket_id, "honeybee_id": None,
    }, element.carbon_reference)
    if element.carbon_reference is not None:
        references[f"window:{element.name}"] = deepcopy(reference)
    return reference


def export_nominal_constructions(archetype, *, metadata=None):
    """Export the actual supplied roles as native Honeybee and Core dictionaries.

    ``metadata`` is optional descriptive context. Supported fields include
    ``material_references``, ``boundary_details``, ``roof_topology``, ``category``,
    ``era`` and ``state``. No calibration, evidence or revision records are needed.

    Layers remain outside to inside. Parallel materials use area-weighted
    conductivity and density, and mass-weighted specific heat, preserving layer
    resistance, mass and thermal storage. Surface films are reported separately
    from material layers. Completeness of the Swedish catalogue is checked by
    Catalogue; partial custom constructions can also be exported here.
    """
    if not isinstance(archetype, BuildingArchetype):
        raise TypeError("Construction export requires an Archetype")
    if archetype.construction_set is None or not archetype.construction_set.elements:
        raise ValueError("Construction export requires supplied physical construction definitions")
    context_metadata = _portable_metadata(metadata)
    boundaries = context_metadata.get("boundary_details", {})
    if not isinstance(boundaries, dict) or any(not isinstance(v, dict) for v in boundaries.values()):
        raise ValueError("boundary_details must map roles to physical boundary records")
    references, by_json_id = _material_references(archetype, context_metadata)
    hb, core, roles, reciprocal = {}, {}, {}, {}
    elements = sorted(archetype.construction_set.elements.items(), key=lambda item: item[0].value)
    for role, element in elements:
        name = role.value
        context = {
            "role": name,
            "representation": "nominal_reference_projection",
            "boundary_details": deepcopy(boundaries.get(name, {})),
        }
        if role == BuildingElement.WINDOW:
            ref = _window_reference(element, references)
            material = {
                "type": "EnergyWindowMaterialSimpleGlazSys",
                "identifier": _identity("window_material", {
                    "reference": ref, "u": element.u_value, "shgc": element.shgc, "vt": element.vt,
                }),
                "u_factor": element.u_value,
                "shgc": element.shgc,
                "vt": element.vt,
                "user_data": {
                    "source_reference": ref,
                    "representation": "simple_whole_window",
                },
            }
            hb[name] = {
                "type": "WindowConstruction",
                "identifier": _identity("window", material),
                "materials": [material],
                "user_data": context,
            }
            core[name] = {
                "u_value_w_m2k": element.u_value,
                "solar_heat_gain_coefficient": element.shgc,
                "visible_transmittance": element.vt,
            }
            roles[name] = {
                "nominal_u_w_m2k": element.u_value,
                "window_reference": deepcopy(ref),
                "mass_kg_m2": None,
                "heat_capacity_j_m2k": None,
            }
            continue
        materials, source = [], {key: 0.0 for key in _metrics([])}
        for component in element.components:
            for slot in component.layers:
                layer = slot.layer
                constituents = layer.materials
                density = sum(c.area_fraction * c.material.density for c in constituents)
                capacity = sum(
                    c.area_fraction * c.material.density * c.material.specific_heat
                    for c in constituents
                )
                fields = {
                    "type": "EnergyMaterial",
                    "thickness": layer.thickness,
                    "conductivity": sum(
                        c.area_fraction * c.material.conductivity for c in constituents
                    ),
                    "density": density,
                    "specific_heat": capacity / density,
                    "roughness": constituents[0].material.roughness.value,
                    **{
                        field: sum(
                            c.area_fraction * getattr(c.material, field) for c in constituents
                        )
                        for field in (
                            "thermal_absorptance", "solar_absorptance", "visible_absorptance"
                        )
                    },
                    "user_data": {
                        "layer_code": layer.layer_code,
                        "representation": "derived_equivalent"
                        if layer.is_composite else "source_at_layer_depth",
                        "constituents": [
                            {
                                "area_fraction": c.area_fraction,
                                "source_reference": deepcopy(by_json_id[c.material.json_id]),
                            }
                            for c in constituents
                        ],
                        "carbon_mapping": "constituents_only"
                        if layer.is_composite else "source_reference",
                    },
                }
                fields["identifier"] = _identity("layer", fields)
                materials.append(fields)
                source["thickness_m"] += layer.thickness
                source["resistance_m2k_w"] += layer.r_value
                source["mass_kg_m2"] += layer.thickness * density
                source["heat_capacity_j_m2k"] += layer.thickness * capacity
        metrics = _metrics(materials)
        if any(not math.isclose(metrics[key], value, rel_tol=1e-10, abs_tol=1e-10)
               for key, value in source.items()):
            raise ValueError(f"{name}: construction export changed resistance, mass or storage")
        rsi, rse = get_boundary_resistances(role)
        u_value = 1 / (metrics["resistance_m2k_w"] + rsi + rse)
        if not math.isclose(u_value, element.u_value, rel_tol=1e-10):
            raise ValueError(f"{name}: exported U-value differs from the construction")
        context.update(rsi_m2k_w=rsi, rse_m2k_w=rse)
        hb[name] = {
            "type": "OpaqueConstruction",
            "identifier": _identity("construction", materials),
            "materials": materials,
            "user_data": context,
        }
        core[name] = {
            "layers": [
                {
                    "thickness_m": material["thickness"],
                    "material": {
                        "name": material["identifier"],
                        "conductivity_w_mk": material["conductivity"],
                        "density_kg_m3": material["density"],
                        "specific_heat_j_kgk": material["specific_heat"],
                        **{
                            field: material[field]
                            for field in (
                                "roughness", "solar_absorptance", "thermal_absorptance",
                                "visible_absorptance",
                            )
                        },
                    },
                }
                for material in materials
            ],
            "surface_resistance_m2k_w": rsi + rse,
        }
        roles[name] = {
            **metrics,
            "nominal_u_w_m2k": u_value,
            "rsi_m2k_w": rsi,
            "rse_m2k_w": rse,
            "layer_order": "outside_to_inside",
            "boundary_details": deepcopy(context["boundary_details"]),
        }
        reverse_hb = deepcopy(hb[name])
        reverse_hb["materials"].reverse()
        reverse_hb["identifier"] = _identity("reciprocal", reverse_hb["materials"])
        reverse_hb["user_data"].update(reciprocal=True, rsi_m2k_w=rse, rse_m2k_w=rsi)
        reverse_core = deepcopy(core[name])
        reverse_core["layers"].reverse()
        reciprocal[name] = {"honeybee": reverse_hb, "core": reverse_core}
    classification = {
        field: deepcopy(context_metadata[field])
        for field in ("category", "era", "state") if field in context_metadata
    }
    bundle = {
        "format_version": 1,
        "kind": "nominal_construction_handover",
        "archetype_id": archetype.archetype_id,
        "key": deepcopy(context_metadata.get("key", classification)),
        **classification,
        "declared_roles": list(hb),
        "material_references": references,
        "roof_topology": deepcopy(context_metadata.get("roof_topology")),
        "honeybee": hb,
        "core": core,
        "roles": roles,
        "reciprocal_constructions": reciprocal,
        # Existing EPSM consumers use this spelling.
        "reciprocal": deepcopy(reciprocal),
    }
    if "selection" in context_metadata:
        bundle["selection"] = deepcopy(context_metadata["selection"])
    validate_nominal_handover(bundle)
    return bundle


def _positive(value, *, minimum=0):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and value > 0 and value >= minimum)


def _fraction(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and 0 <= value <= 1)


def _validate_nominal_handover(bundle):
    expected = set(bundle.get("declared_roles", bundle["honeybee"]))
    if not expected or not expected <= {role.value for role in BuildingElement}:
        raise ValueError("Construction handover requires declared physical roles")
    if any(set(bundle[field]) != expected for field in ("honeybee", "core", "roles")):
        raise ValueError("Construction handover representations must contain the same roles")
    reciprocal = bundle.get("reciprocal_constructions", bundle.get("reciprocal", {}))
    if "reciprocal" in bundle and bundle["reciprocal"] != reciprocal:
        raise ValueError("Reciprocal construction aliases differ")
    if set(reciprocal) != expected - {"WINDOW"}:
        raise ValueError("Reciprocal constructions must contain every opaque role")
    for role in sorted(expected):
        hb, core, metrics = (bundle[field][role] for field in ("honeybee", "core", "roles"))
        if role == "WINDOW":
            if hb["type"] != "WindowConstruction" or len(hb["materials"]) != 1:
                raise ValueError("Window requires a simple whole-window construction")
            material = hb["materials"][0]
            if material["type"] != "EnergyWindowMaterialSimpleGlazSys":
                raise ValueError("Unsupported nominal window material")
            for hf, cf in (
                ("u_factor", "u_value_w_m2k"),
                ("shgc", "solar_heat_gain_coefficient"),
                ("vt", "visible_transmittance"),
            ):
                value = material[hf]
                if not (_positive(value) if hf == "u_factor" else _fraction(value)):
                    raise ValueError(f"Invalid nominal window {hf}")
                if value != core[cf]:
                    raise ValueError(f"Nominal window {hf} differs between exports")
            if not math.isclose(material["u_factor"], metrics["nominal_u_w_m2k"], rel_tol=1e-10):
                raise ValueError("Nominal window U differs from construction metrics")
            continue
        materials = hb["materials"]
        if hb["type"] != "OpaqueConstruction" or not 1 <= len(materials) <= 10:
            raise ValueError(f"Invalid nominal opaque construction: {role}")
        if len(materials) != len(core["layers"]):
            raise ValueError(f"Nominal layer count differs: {role}")
        for material, layer in zip(materials, core["layers"], strict=True):
            if material["type"] != "EnergyMaterial":
                raise ValueError(f"Invalid nominal material type: {role}")
            for hf, cf in (
                ("conductivity", "conductivity_w_mk"),
                ("density", "density_kg_m3"),
                ("specific_heat", "specific_heat_j_kgk"),
            ):
                if not _positive(material[hf], minimum=100 if hf == "specific_heat" else 0):
                    raise ValueError(f"Invalid nominal {role} {hf}")
                if material[hf] != layer["material"][cf]:
                    raise ValueError(f"Nominal material differs: {role} {hf}")
            if not _positive(material["thickness"]):
                raise ValueError(f"Invalid nominal thickness: {role}")
            if material["thickness"] != layer["thickness_m"]:
                raise ValueError(f"Nominal thickness differs: {role}")
            for field in ("thermal_absorptance", "solar_absorptance", "visible_absorptance"):
                if not _fraction(material[field]) or material[field] != layer["material"][field]:
                    raise ValueError(f"Nominal optical property differs: {role}")
            if material["roughness"] not in {
                "VeryRough", "Rough", "MediumRough", "MediumSmooth", "Smooth", "VerySmooth",
            } or material["roughness"] != layer["material"]["roughness"]:
                raise ValueError(f"Invalid nominal roughness: {role}")
        calculated = _metrics(materials)
        if any(not math.isclose(value, metrics[key], rel_tol=1e-10, abs_tol=1e-10)
               for key, value in calculated.items()):
            raise ValueError(f"Nominal resistance, thickness, mass or storage differs: {role}")
        if any(not isinstance(metrics[field], (int, float)) or isinstance(metrics[field], bool)
               or not math.isfinite(metrics[field]) or metrics[field] < 0
               for field in ("rsi_m2k_w", "rse_m2k_w")):
            raise ValueError(f"Invalid nominal surface films: {role}")
        films = metrics["rsi_m2k_w"] + metrics["rse_m2k_w"]
        if any(hb["user_data"][field] != metrics[field] for field in ("rsi_m2k_w", "rse_m2k_w")):
            raise ValueError(f"Honeybee nominal film metadata differs: {role}")
        if not math.isclose(films, core["surface_resistance_m2k_w"], abs_tol=1e-10):
            raise ValueError(f"Nominal films differ: {role}")
        if not math.isclose(1 / (calculated["resistance_m2k_w"] + films),
                            metrics["nominal_u_w_m2k"], rel_tol=1e-10):
            raise ValueError(f"Nominal U differs: {role}")
        reverse = reciprocal[role]
        if reverse["core"]["surface_resistance_m2k_w"] != core["surface_resistance_m2k_w"]:
            raise ValueError(f"Reciprocal nominal films differ: {role}")
        if (reverse["honeybee"]["user_data"]["rsi_m2k_w"] != metrics["rse_m2k_w"]
                or reverse["honeybee"]["user_data"]["rse_m2k_w"] != metrics["rsi_m2k_w"]):
            raise ValueError(f"Reciprocal film ordering differs: {role}")
        if (reverse["honeybee"]["materials"] != list(reversed(materials))
                or reverse["core"]["layers"] != list(reversed(core["layers"]))):
            raise ValueError(f"Reciprocal layer order differs: {role}")
    return {"honeybee": True, "core": True}


def validate_nominal_handover(bundle):
    """Check physical equality, storage, films and ordering without engine imports."""
    try:
        return _validate_nominal_handover(bundle)
    except (KeyError, TypeError, AttributeError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("Malformed physical construction handover") from exc
