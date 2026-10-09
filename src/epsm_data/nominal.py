"""Role-preserving nominal Honeybee and epsm_core construction handovers.

These exports preserve the catalogue's nominal thermal/storage model. They are
not a complete building envelope or a ground/cavity simulation certification.
All third-party imports are confined to optional validation helpers.
"""

# Release contract: v1.4 preserves v1.3 roles; see evidence/lod2_v1_4/window-diagnostic.json.
from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy

from .domain import BuildingElement
from .thermal.boundary_conditions import get_boundary_resistances


def _identity(kind, value):
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()
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


def _expected_roles(key, release=None):
    if release in ("epsm-lod2-v1.3", "epsm-lod2-v1.4"):
        return {"ROOF" if key.get("category") == "office" else "TOP_FLOOR",
                "EXT_WALL", "GROUND_FLOOR", "BASEMENT_WALL", "INTERMEDIATE_FLOOR",
                "INT_WALL_NONLOADBEARING", "WINDOW"}
    if key.get("category") == "office":
        roles = {"ROOF", "EXT_WALL", "GROUND_FLOOR", "INTERMEDIATE_FLOOR", "INT_WALL_NONLOADBEARING", "WINDOW"}
        if key.get("era") == "SE.01":
            roles.add("BASEMENT_WALL")
        return roles
    if key.get("category") == "school":
        roles = {"TOP_FLOOR", "EXT_WALL", "GROUND_FLOOR", "INTERMEDIATE_FLOOR", "INT_WALL_NONLOADBEARING", "WINDOW"}
        if key.get("era") == "SE.01":
            roles.add("BASEMENT_WALL")
        return roles
    return {"TOP_FLOOR", "EXT_WALL", "GROUND_FLOOR", "BASEMENT_WALL", "INTERMEDIATE_FLOOR", "INT_WALL_NONLOADBEARING", "WINDOW"}


def export_nominal_constructions(calibrated):
    """Return portable, unabridged native Honeybee and core-type dictionaries.

    ``core`` is keyed by catalogue role and contains ConstructionSpec-compatible
    dictionaries, except WINDOW which is GlazingSpec-compatible. No implicit
    weather shell, thermal bridge uplift, ground temperature or building geometry
    is invented. Reporting films are metadata, never emitted material layers.
    """
    if not hasattr(calibrated, "report") or not hasattr(calibrated, "archetype"):
        raise TypeError("Nominal exports require a calibrated material-layer archetype")
    report = calibrated.report
    references = {r["json_id"]: r for r in report["material_references"].values()}
    hb, core, roles, reciprocal = {}, {}, {}, {}
    for role, element in calibrated.archetype.construction_set.elements.items():
        name = role.value
        context = {
            "construction_revision": report["revision"],
            "role": name,
            "representation": "nominal_reference_projection",
            "boundary_details": deepcopy(report["boundary_details"].get(name, {})),
        }
        if role == BuildingElement.WINDOW:
            ref = next(
                r for mid, r in report["material_references"].items() if mid.startswith("window_")
            )
            material = {
                "type": "EnergyWindowMaterialSimpleGlazSys",
                "identifier": _identity(
                    "window_material",
                    {
                        "reference": ref,
                        "u": element.u_value,
                        "shgc": element.shgc,
                        "vt": element.vt,
                    },
                ),
                "u_factor": element.u_value,
                "shgc": element.shgc,
                "vt": element.vt,
                "user_data": {
                    "source_reference": deepcopy(ref),
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
        materials, source = [], {k: 0.0 for k in _metrics([])}
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
                        f: sum(c.area_fraction * getattr(c.material, f) for c in constituents)
                        for f in ("thermal_absorptance", "solar_absorptance", "visible_absorptance")
                    },
                    "user_data": {
                        "layer_code": layer.layer_code,
                        "representation": "derived_equivalent"
                        if layer.is_composite
                        else "source_at_layer_depth",
                        "constituents": [
                            {
                                "area_fraction": c.area_fraction,
                                "source_reference": deepcopy(references[c.material.json_id]),
                            }
                            for c in constituents
                        ],
                        "carbon_mapping": "constituents_only"
                        if layer.is_composite
                        else "source_reference",
                    },
                }
                fields["identifier"] = _identity("layer", fields)
                materials.append(fields)
                source["thickness_m"] += layer.thickness
                source["resistance_m2k_w"] += layer.r_value
                source["mass_kg_m2"] += layer.thickness * density
                source["heat_capacity_j_m2k"] += layer.thickness * capacity
        if not 1 <= len(materials) <= 10:
            raise ValueError(f"{name}: core constructions support one to ten layers")
        for m in materials:
            for f in ("thickness", "conductivity", "density", "specific_heat"):
                if not math.isfinite(m[f]) or m[f] <= 0:
                    raise ValueError(f"Invalid nominal {name} {f}")
            if m["specific_heat"] < 100:
                raise ValueError("Core materials require heat capacity >= 100 J/(kg K)")
        metrics = _metrics(materials)
        if any(
            not math.isclose(metrics[k], source[k], rel_tol=1e-10, abs_tol=1e-10) for k in source
        ):
            raise ValueError(f"{name}: nominal export changed resistance, mass or storage")
        rsi, rse = get_boundary_resistances(role)
        u = 1 / (metrics["resistance_m2k_w"] + rsi + rse)
        if not math.isclose(u, element.u_value, rel_tol=1e-10):
            raise ValueError(f"{name}: exported nominal U differs from the catalogue")
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
                    "thickness_m": m["thickness"],
                    "material": {
                        "name": m["identifier"],
                        "conductivity_w_mk": m["conductivity"],
                        "density_kg_m3": m["density"],
                        "specific_heat_j_kgk": m["specific_heat"],
                        **{
                            f: m[f]
                            for f in (
                                "roughness",
                                "solar_absorptance",
                                "thermal_absorptance",
                                "visible_absorptance",
                            )
                        },
                    },
                }
                for m in materials
            ],
            "surface_resistance_m2k_w": rsi + rse,
        }
        roles[name] = {
            **metrics,
            "nominal_u_w_m2k": u,
            "rsi_m2k_w": rsi,
            "rse_m2k_w": rse,
            "layer_order": "outside_to_inside",
            "boundary_details": context["boundary_details"],
        }
        reverse_hb = deepcopy(hb[name])
        reverse_hb["materials"].reverse()
        reverse_hb["identifier"] = _identity("reciprocal", reverse_hb["materials"])
        reverse_hb["user_data"].update(reciprocal=True, rsi_m2k_w=rse, rse_m2k_w=rsi)
        reverse_core = deepcopy(core[name])
        reverse_core["layers"].reverse()
        reciprocal[name] = {"honeybee": reverse_hb, "core": reverse_core}
    expected = (
        {"ROOF", "EXT_WALL", "GROUND_FLOOR", "INTERMEDIATE_FLOOR",
         "INT_WALL_NONLOADBEARING", "WINDOW"}
        if report.get("status") == "source_and_provisional_draft"
        else _expected_roles(report["key"], report.get("dataset_release"))
    )
    if set(hb) != expected:
        raise ValueError("Nominal handover requires all declared archetype roles")
    bundle = {
        "format_version": 1,
        **({"dataset_release": report["dataset_release"],
            "construction_availability": report["construction_availability"],
            "element_presence": "caller_geometry"}
           if report.get("dataset_release") in ("epsm-lod2-v1.3", "epsm-lod2-v1.4") else {}),
        "kind": "nominal_construction_handover",
        "key": deepcopy(report["key"]),
        "role_profile": "school_source_draft" if report.get("status") == "source_and_provisional_draft" else "canonical",
        "construction_revision": report["revision"],
        "catalogue_revision": report["catalogue_revision"],
        "material_references": deepcopy(report["material_references"]),
        **({"retained_baseline_unmapped_materials": deepcopy(report["retained_baseline_unmapped_materials"])}
           if report.get("retained_baseline_unmapped_materials") else {}),
        "record_annotations": deepcopy(report["record_annotations"]),
        "sources": deepcopy(report["sources"]),
        "honeybee": hb,
        "core": core,
        "roles": roles,
        "reciprocal": reciprocal,
        "limitations": [
            "Nominal equivalent-composite model, not a full ISO 6946 assessment.",
            ("Declared equivalent cavity layers preserve fixed nominal resistance; ventilation, fixings and thermal bridges are not dynamically simulated."
             if any(x.get("cavity_nominal_r_m2k_w") for x in report.get("boundary_details", {}).values())
             else "Cavities/fixings/veneer support are boundary metadata, not simulated air or bridge layers."),
            "Ground-contact constructions are layer-only assemblies, not effective ground U-values.",
            "No geometry, monthly ground temperatures, weather shell or window mass is invented.",
            "This core checkout uses monthly ground temperatures; ground validation requires an explicit geometry/boundary study, not an established Kiva workflow.",
        ],
    }
    validation = validate_nominal_handover(bundle)
    ground = bool(report["effective_ground_calibration_complete"])
    carbon = (
        all(r["boverket_id"] for r in references.values())
        and all(r["mass_kg_m2"] is not None for r in roles.values())
        and not any(c.get("scope") == "carbon_assessment" for c in report["open_caveats"])
    )
    bundle["readiness"] = {
        "honeybee_nominal_export": validation["honeybee"],
        "core_nominal_export": validation["core"],
        "ground_validation": ground,
        "carbon_assessment": carbon,
        "simulation": ground
        and bool(report.get("weather_shell_validated"))
        and not any(c.get("scope") == "simulation" for c in report["open_caveats"]),
    }
    return bundle


def validate_nominal_handover(bundle):
    """Validate portable nominal payloads without third-party dependencies.

    Native library validation is available separately. These checks compare both
    representations with catalogue metrics, including reciprocal ordering.
    """
    expected = (
        {"ROOF", "EXT_WALL", "GROUND_FLOOR", "INTERMEDIATE_FLOOR",
         "INT_WALL_NONLOADBEARING", "WINDOW"}
        if bundle.get("role_profile") == "school_source_draft"
        else _expected_roles(bundle["key"], bundle.get("dataset_release"))
    )
    if any(set(bundle[field]) != expected for field in ("honeybee", "core", "roles")):
        raise ValueError("Nominal handover requires all declared archetype roles")
    for role in expected:
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
                v = material[hf]
                if not math.isfinite(v) or (v <= 0 if hf == "u_factor" else not 0 <= v <= 1):
                    raise ValueError(f"Invalid nominal window {hf}")
                if v != core[cf]:
                    raise ValueError(f"Nominal window {hf} differs between exports")
            if not math.isclose(material["u_factor"], metrics["nominal_u_w_m2k"], rel_tol=1e-10):
                raise ValueError("Nominal window U differs from catalogue")
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
                v = material[hf]
                if not math.isfinite(v) or v <= 0 or (hf == "specific_heat" and v < 100):
                    raise ValueError(f"Invalid nominal {role} {hf}")
                if v != layer["material"][cf]:
                    raise ValueError(f"Nominal material differs: {role} {hf}")
            if not math.isfinite(material["thickness"]) or material["thickness"] <= 0:
                raise ValueError(f"Invalid nominal thickness: {role}")
            if material["thickness"] != layer["thickness_m"]:
                raise ValueError(f"Nominal thickness differs: {role}")
            for field in ("thermal_absorptance", "solar_absorptance", "visible_absorptance"):
                if not 0 <= material[field] <= 1 or material[field] != layer["material"][field]:
                    raise ValueError(f"Nominal optical property differs: {role}")
            roughness_values = {
                "VeryRough",
                "Rough",
                "MediumRough",
                "MediumSmooth",
                "Smooth",
                "VerySmooth",
            }
            if (
                material["roughness"] not in roughness_values
                or material["roughness"] != layer["material"]["roughness"]
            ):
                raise ValueError(f"Invalid nominal roughness: {role}")
        calculated = _metrics(materials)
        if any(
            not math.isclose(v, metrics[k], rel_tol=1e-10, abs_tol=1e-10)
            for k, v in calculated.items()
        ):
            raise ValueError(f"Nominal resistance, thickness, mass or storage differs: {role}")
        films = metrics["rsi_m2k_w"] + metrics["rse_m2k_w"]
        if any(hb["user_data"][field] != metrics[field] for field in ("rsi_m2k_w", "rse_m2k_w")):
            raise ValueError(f"Honeybee nominal film metadata differs: {role}")
        if not math.isclose(films, core["surface_resistance_m2k_w"], abs_tol=1e-10):
            raise ValueError(f"Nominal films differ: {role}")
        if not math.isclose(
            1 / (calculated["resistance_m2k_w"] + films), metrics["nominal_u_w_m2k"], rel_tol=1e-10
        ):
            raise ValueError(f"Nominal U differs: {role}")
        reverse = bundle["reciprocal"][role]
        if reverse["core"]["surface_resistance_m2k_w"] != core["surface_resistance_m2k_w"]:
            raise ValueError(f"Reciprocal nominal films differ: {role}")
        if (
            reverse["honeybee"]["user_data"]["rsi_m2k_w"] != metrics["rse_m2k_w"]
            or reverse["honeybee"]["user_data"]["rse_m2k_w"] != metrics["rsi_m2k_w"]
        ):
            raise ValueError(f"Reciprocal film ordering differs: {role}")
        if reverse["honeybee"]["materials"] != list(reversed(materials)) or reverse["core"][
            "layers"
        ] != list(reversed(core["layers"])):
            raise ValueError(f"Reciprocal layer order differs: {role}")
    return {"honeybee": True, "core": True}


def validate_native_handover(bundle):
    """Optionally validate/roundtrip with installed Honeybee and core types."""
    from epsm_core.specs.facade import GlazingSpec
    from epsm_core.specs.physics import ConstructionSpec
    from honeybee_energy.construction.dictutil import dict_to_construction

    validate_nominal_handover(bundle)
    for role, record in bundle["honeybee"].items():
        native = dict_to_construction(record)
        reconstructed = dict_to_construction(native.to_dict())
        if native != reconstructed:
            raise ValueError(f"Honeybee roundtrip mismatch: {role}")
        for material, source in zip(native.materials, record["materials"], strict=True):
            fields = (
                ("u_factor", "shgc", "vt")
                if role == "WINDOW"
                else (
                    "thickness",
                    "conductivity",
                    "density",
                    "specific_heat",
                    "thermal_absorptance",
                    "solar_absorptance",
                    "visible_absorptance",
                )
            )
            if any(
                not math.isclose(getattr(material, f), source[f], rel_tol=1e-10) for f in fields
            ):
                raise ValueError(f"Honeybee changed nominal properties: {role}")
        if role == "WINDOW":
            GlazingSpec(**bundle["core"][role])
        else:
            value = ConstructionSpec(**bundle["core"][role])
            if not math.isclose(
                value.u_value_w_m2k, bundle["roles"][role]["nominal_u_w_m2k"], rel_tol=1e-10
            ):
                raise ValueError(f"Core nominal U mismatch: {role}")
            reverse = bundle["reciprocal"][role]
            dict_to_construction(reverse["honeybee"])
            ConstructionSpec(**reverse["core"])
    return {"honeybee": True, "core": True}


def catalogue_lod2_checks(calibrated):
    """Data/export acceptance only; scope-specific simulation caveats stay open."""
    report = calibrated.report
    refs = report["material_references"]
    active_ids = set(refs)
    hb_ids = {r["honeybee_id"] for r in refs.values()}
    open_data = [
        c
        for c in report["open_caveats"]
        if c.get("scope", "catalogue") == "catalogue"
        and not (c["owner_type"] == "material" and c["owner_id"] not in active_ids)
        and not (c["owner_type"] == "honeybee" and c["owner_id"] not in hb_ids)
    ]
    exported = export_nominal_constructions(calibrated)
    checks = {
        "construction_schema": report["construction_schema_complete"],
        "honeybee_material_references": all(r["honeybee_id"] for r in refs.values()),
        "boverket_material_references": all(r["boverket_id"] or r["mapping_status"] == "not_applicable"
                                             for r in refs.values()),
        "thermal_and_optical_evidence_reviewed": not any(
            c.get("topic") in {"thermal", "optics"} for c in open_data
        ),
        "no_open_blocking_catalogue_caveats": not any(
            c["severity"] == "blocking" for c in open_data
        ),
        "nominal_u_alignment": report["nominal_calibration_complete"],
        "honeybee_nominal_export": exported["readiness"]["honeybee_nominal_export"],
        "core_nominal_export": exported["readiness"]["core_nominal_export"],
    }
    if report.get("dataset_release") in ("epsm-lod2-v1.3", "epsm-lod2-v1.4"):
        checks["seven_role_library"] = len(exported["roles"]) == 7
        checks["presence_is_geometry_owned"] = exported["element_presence"] == "caller_geometry"
    retained = set(report.get("retained_baseline_unmapped_materials", []))
    if retained:
        # Verified against actual equal floors in all states by DetailedCatalogue.
        # This is intervention-scope acceptance, not complete baseline carbon data.
        checks.pop("boverket_material_references")
        checks["boverket_intervention_scope_references"] = all(
            r["boverket_id"] or r["mapping_status"] == "not_applicable" or mid in retained
            for mid, r in refs.items())
    return {
        "checks": checks,
        "lod2_complete": all(checks.values()),
        "open_catalogue_caveats": open_data,
        "readiness": exported["readiness"],
    }
