"""Offline representative Standard/Advanced packages for MF SE.02.

Material registration and nominal calibration do not certify ground boundaries,
cavities, buildability, glazing optics or carbon completeness. Honeybee is optional.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from epsm_data._logging import operation as logged_operation

from .detailed import _load_detailed_catalogue
from .domain import (
    BuildingElement,
    Component,
    EmbodiedCarbon,
    Layer,
    LayerMaterial,
    LayerSlot,
    OpaqueMaterial,
    Roughness,
    ShearingLayer,
    WindowElement,
)
from .layered import (
    GROUND_ROLES,
    ROLE_MAP,
    CalibratedArchetype,
    _digest,
    _load_calibrated_archetype,
    _number,
)
from .parametric import ArchetypeKey, EffectiveProperty, _load_parametric_catalogue
from .thermal import compute_element_thermal


def honeybee_material_dict(material: OpaqueMaterial, thickness: float, *, notes=None, caveats=None) -> dict:
    """Represent a homogeneous material at a layer depth in Honeybee's schema.

    No stock-library match or whole composite-construction conversion is implied.
    Convert with honeybee_energy.material.dictutil.dict_to_material when installed.
    """
    _number(thickness, "Honeybee thickness")
    for field in ("conductivity", "density", "specific_heat"):
        _number(getattr(material, field), f"Honeybee {field}")
    for field in ("thermal_absorptance", "solar_absorptance", "visible_absorptance"):
        value = _number(getattr(material, field), field, positive=False)
        if value > 1:
            raise ValueError(f"Invalid {field}")
    identity = _digest({"material": material.to_dict(), "thickness": thickness})
    label = re.sub(r"[^A-Za-z0-9_]", "_", material.name)[:50]
    return {
        "type": "EnergyMaterial", "identifier": f"EPSM_{label}_{identity[:16]}",
        "display_name": material.name, "thickness": thickness,
        "roughness": material.roughness.value,
        "user_data": {
            "epsm_material_id": material.json_id, "epsm_material_uuid": str(material.uuid),
            "boverket_id": material.boverket_id, "mapping_kind": "property_matched_custom",
            "notes": deepcopy(notes or []), "caveats": deepcopy(caveats or []),
        },
        **{field: getattr(material, field) for field in (
            "conductivity", "density", "specific_heat", "thermal_absorptance",
            "solar_absorptance", "visible_absorptance",
        )},
    }


def _opaque(record, sources):
    if (record.get("mapping_status") not in {"matched_generic_family", "reviewed_proxy"}
            or record.get("honeybee_type") != "EnergyMaterial"):
        raise ValueError("New opaque materials require Boverket and Honeybee matches")
    if record.get("source") not in sources or not record.get("locator") or not record.get("note"):
        raise ValueError("Material registration requires source, locator and note")
    evidence = record.get("thermal_evidence", {})
    if set(evidence) != {"conductivity", "density", "specific_heat"}:
        raise ValueError("Material requires evidence for all three thermal properties")
    for item in evidence.values():
        if item.get("source") not in sources or not item.get("note"):
            raise ValueError("Dangling material thermal evidence")
    props = deepcopy(record["properties"])
    carbon = props["embodied_carbon"]
    if not props["boverket_id"] or carbon is None or carbon["resource_id"] != props["boverket_id"]:
        raise ValueError("New material Boverket and carbon IDs must agree")
    for field in ("conductivity", "density", "specific_heat"):
        _number(props[field], f"material {field}")
    props["uuid"] = uuid5(NAMESPACE_URL, f"epsm_data:renovation_material:{_digest(props)}")
    props["roughness"] = Roughness(props["roughness"])
    props["embodied_carbon"] = EmbodiedCarbon(**carbon)
    material = OpaqueMaterial(**props)
    # Registration prototype, not a construction prescription.
    honeybee_material_dict(material, 0.05)
    return material


def _window(record, sources, identity):
    if (record.get("mapping_status") not in {"matched_generic_family", "reviewed_proxy"}
            or record.get("honeybee_type") != "EnergyWindowMaterialSimpleGlazSys"):
        raise ValueError("Replacement window requires reviewed Boverket and Honeybee matches")
    if (record.get("source") not in sources or record.get("optics_source") not in sources
            or not record.get("locator") or not record.get("note") or not record.get("optics_note")):
        raise ValueError("Window requires sourced mapping and explicit optical evidence")
    carbon = record.get("embodied_carbon")
    if not record.get("boverket_id") or carbon is None or carbon["resource_id"] != record["boverket_id"]:
        raise ValueError("Window Boverket and carbon IDs must agree")
    EmbodiedCarbon(**carbon)
    for field in ("u_value", "shgc", "vt"):
        value = _number(record[field], f"window {field}")
        if field != "u_value" and value > 1:
            raise ValueError(f"Invalid window {field}")
    element = WindowElement(
        name=f"{identity}_WINDOW", archetype=identity,
        u_value=record["u_value"], shgc=record["shgc"], vt=record["vt"],
        boverket_id=int(record["boverket_id"]),
    )
    hb = {
        "type": "EnergyWindowMaterialSimpleGlazSys",
        "identifier": f"EPSM_WINDOW_{_digest(record)[:20]}",
        "display_name": record["name"], "u_factor": record["u_value"],
        "shgc": record["shgc"], "vt": record["vt"],
        "user_data": {
            "boverket_id": record["boverket_id"], "mapping_status": record["mapping_status"],
            "mapping_note": record["note"], "optics_note": record["optics_note"],
            "epsm_material_id": record.get("registry_id"),
            "notes": deepcopy(record.get("notes", [])), "caveats": deepcopy(record.get("caveats", [])),
        },
    }
    return element, hb


@logged_operation("catalogue.renovation.load")
def load_renovation_package(state, path=None, *, base_path=None, catalogue=None, detailed=None) -> CalibratedArchetype:
    """Build Standard or Advanced directly from Existing; never compound states.

    ``path`` selects shared registries; ``base_path`` optionally selects a
    separate Existing registry copy. Captured base/LoD1 drift is reported.
    All three new opaque materials are registered before operations are applied.
    """
    if state not in {"standard", "advanced"}:
        raise ValueError("Renovation package state must be standard or advanced")
    detailed = detailed if detailed is not None else _load_detailed_catalogue(path, catalogue=catalogue)
    definition = detailed.renovation_inputs()
    if (definition.get("format_version") != 1
            or (definition.get("category"), definition.get("era")) != ("multi_family", "SE.02")
            or set(definition.get("states", {})) != {"standard", "advanced"}):
        raise ValueError("Only MF SE.02 Standard and Advanced packages are supported")
    tolerance = _number(definition["states"][state]["tolerance_percent"], "renovation tolerance")
    if tolerance not in (2, 5):
        raise ValueError("MF SE.02 nominal acceptance requires 2% or 5% tolerance")
    catalogue = catalogue if catalogue is not None else _load_parametric_catalogue()
    base = _load_calibrated_archetype(base_path if base_path is not None else path, catalogue=catalogue,
                                   detailed=detailed if base_path is None else None)
    sources = {**base.report["sources"], **definition["sources"]}
    new_materials = {mid: _opaque(record, sources) for mid, record in definition["materials"].items()}
    if not new_materials:
        raise ValueError("Renovation material registry must not be empty")
    if len({m.json_id for m in new_materials.values()}) != len(new_materials):
        raise ValueError("Duplicate registered material identities")
    # Recover the existing immutable objects, rather than inventing new carbon
    # or thermal records for EPS, brick and mortar used again in the renovation.
    by_id = {slot.material.json_id: slot.material
             for element in base.archetype.construction_set.elements.values()
             if hasattr(element, "components") for component in element.components
             for layer in component.layers for slot in layer.layer.materials}
    reused = definition["reused_materials"]
    if len(reused) != len(set(reused)) or set(reused) & set(new_materials):
        raise ValueError("Duplicate/redefined reused material")
    materials = dict(new_materials)
    for mid in reused:
        review = base.report["materials"].get(mid)
        if review is None or review["mapping_status"] not in {"matched_generic_family", "reviewed_proxy"}:
            raise ValueError(f"Reused material must already have a reviewed match: {mid}")
        materials[mid] = by_id[review["properties"]["json_id"]]

    variant = definition["states"][state]
    identity = variant["identity"]["archetype_id"]
    key = ArchetypeKey(**variant["key"])
    live_slot = catalogue.get_slot(key)
    live = {**live_slot.construction_set.properties, "infiltration": live_slot.infiltration}
    captured = variant["target_snapshot"]
    if set(captured) != set(live):
        raise ValueError("Renovation target snapshot requires all eight properties")
    catalogue_data = catalogue.to_dict()
    known_sources = catalogue_data["sources"]
    for prop, reference in captured.items():
        _number(reference["value"], f"renovation target {prop}", positive=prop != "infiltration")
        if reference.get("source") not in known_sources or reference.get("unit") != live[prop].unit:
            raise ValueError(f"Invalid renovation target source/unit: {prop}")
        if reference.get("curve") not in catalogue_data["curves"]:
            raise ValueError(f"Unknown renovation target curve: {prop}")
        EffectiveProperty(**reference)
    drift = [prop for prop in live if live[prop].to_dict() != captured[prop]]
    base_drift = base.report["revision"] != variant["base_revision"]
    elements = dict(base.archetype.construction_set.elements)
    hb_variants = {}
    registered = {
        mid: {**deepcopy(definition["materials"][mid]), "properties": material.to_dict(),
              "honeybee_registration": honeybee_material_dict(
                  material, 0.05, notes=definition["materials"][mid]["notes"],
                  caveats=definition["materials"][mid]["caveats"])}
        for mid, material in new_materials.items()
    }
    window, hb_window = _window(variant["window"], sources, identity)
    seen = set()
    operations = variant["operations"]
    for oi, operation in enumerate(operations):
        role = BuildingElement(operation["role"])
        if role in seen:
            raise ValueError("Duplicate renovation operation for an element")
        seen.add(role)
        if (operation.get("source") not in sources or not operation.get("source_measure")
                or not operation.get("note")):
            raise ValueError("Renovation operation requires measure evidence")
        if operation["action"] == "replace_window":
            if role != BuildingElement.WINDOW or operation.get("material") != "window":
                raise ValueError("Window replacement must reference the registered window")
            elements[role] = window
            hb_variants[hb_window["identifier"]] = hb_window
            continue
        if operation["action"] not in {"add_component", "replace_exterior"} or role.value not in {"TOP_FLOOR", "EXT_WALL", "GROUND_FLOOR", "BASEMENT_WALL"}:
            raise ValueError("Unsupported renovation operation")
        _number(operation["source_thickness_mm"], "source measure thickness")
        slots = []
        for li, layer_spec in enumerate(operation["layers"]):
            depth = _number(layer_spec["thickness_mm"], "renovation thickness")
            choices = layer_spec["allowed_thickness_mm"]
            if not choices or len(set(choices)) != len(choices):
                raise ValueError("Thickness choices must be nonempty and unique")
            for choice in choices:
                _number(choice, "allowed renovation thickness")
            if not any(math.isclose(depth, choice, rel_tol=0, abs_tol=1e-8) for choice in choices):
                raise ValueError("Renovation depth is outside practical thickness choices")
            ids = layer_spec["material_id"]
            ids = [ids] if isinstance(ids, str) else ids
            if not ids or len(set(ids)) != len(ids) or any(mid not in materials for mid in ids):
                raise ValueError("Unknown or duplicate registered renovation material")
            fractions = layer_spec.get("area_fraction", [1.0] if len(ids) == 1 else [])
            if len(fractions) != len(ids):
                raise ValueError("Composite renovation layer requires all fractions")
            depth /= 1000
            layer = Layer(
                name=f"{identity}_{role.value}_R{oi}_L{li}",
                layer_code=f"{identity}_{role.value}_R{oi}_L{li}", thickness=depth,
                materials=tuple(LayerMaterial(materials[mid], fraction, depth)
                                for mid, fraction in zip(ids, fractions, strict=True)),
                is_composite=len(ids) > 1,
            )
            slots.append(LayerSlot(layer, li))
            for mid in ids:
                review = definition["materials"].get(mid, base.report["materials"].get(mid))
                hb = honeybee_material_dict(materials[mid], depth,
                                           notes=review["notes"], caveats=review["caveats"])
                hb_variants[hb["identifier"]] = hb
        component = Component(
            name=f"{identity}_{role.value}_RENOVATION", archetype=identity,
            application=role, layers=tuple(slots),
            shearing_layer=ShearingLayer(operation["shearing_layer"]),
        )
        old = elements[role]
        if operation["action"] == "replace_exterior":
            count = operation["remove_components"]
            if role != BuildingElement.EXT_WALL or not 0 < count < len(old.components):
                raise ValueError("Invalid exterior-component removal")
            old = replace(old, components=old.components[count:])
        if operation["position"] == "outside":
            components = (component, *old.components)
        elif operation["position"] == "before_inside_finish" and role == BuildingElement.GROUND_FLOOR:
            components = (*old.components[:-1], component, old.components[-1])
        else:
            raise ValueError("Unsupported renovation layer position")
        elements[role] = replace(old, name=f"{identity}_{role.value}", archetype=identity,
                                 components=components)
    unchanged = variant["unchanged_roles"]
    if (len(unchanged) != len(set(unchanged)) or set(unchanged) & {r.value for r in seen}
            or set(unchanged) | {r.value for r in seen} != {r.value for r in elements}):
        raise ValueError("Every construction role must be modified or explicitly unchanged")
    # Explicit unchanged roles allow evidence-informed packages to omit
    # inaccessible ground interventions or unnecessary envelope additions.
    if "WINDOW" not in {r.value for r in seen}:
        raise ValueError("Package requires an explicit replacement window")
    revision = _digest({"definition": definition, "state": state, "base_revision": base.report["revision"]})
    construction = replace(base.archetype.construction_set, elements=elements,
                           version_id=uuid5(NAMESPACE_URL, f"epsm_data:renovation:{revision}"))
    archetype = replace(base.archetype, archetype_id=identity,
                        display_name=variant["identity"]["display_name"],
                        construction_set=construction)
    rows = {}
    for prop, role in {**ROLE_MAP, **GROUND_ROLES}.items():
        element = elements[BuildingElement(role)]
        ground = prop in GROUND_ROLES
        difference = 100 * (element.u_value / captured[prop]["value"] - 1)
        rows[prop] = {
            "role": role, "target_u": captured[prop]["value"], "assembly_u": element.u_value,
            "difference_percent": None if ground else difference,
            "within_tolerance": None if ground else abs(difference) <= tolerance + 1e-10,
            "status": "effective_boundary_pending" if ground else (
                "simple_window_target_with_assumed_optics" if role == "WINDOW" else "nominal_layer_calibration"),
            "target_evidence": deepcopy(captured[prop]),
            "thermal": None if role == "WINDOW" else asdict(compute_element_thermal(element)),
        }
    report = {
        "identity": {"archetype_id": identity, "display_name": archetype.display_name},
        "key": key.to_dict(), "scope_note": variant["scope_note"], "revision": revision,
        "base_revision": base.report["revision"], "base_revision_drift": base_drift,
        "catalogue_revision": _digest(catalogue.to_dict()), "target_drift": drift,
        "tolerance_percent": tolerance, "unit": "W/(m2 K)",
        "method": base.report["method"], "construction_schema_complete": True,
        "nominal_calibration_complete": all(rows[p]["within_tolerance"] for p in ROLE_MAP)
        and not drift and not base_drift and base.report["nominal_calibration_complete"],
        "renovation_material_registration_complete": True,
        "renovation_package_complete": False,
        "effective_ground_calibration_complete": False,
        "lod2_complete": False, "simulation_ready": False, "carbon_assessment_ready": False,
        "elements": rows, "registered_renovation_materials": registered,
        "reused_materials": {mid: deepcopy(base.report["materials"][mid]) for mid in reused},
        "window_registration": deepcopy(variant["window"]),
        "honeybee_materials": list(hb_variants.values()),
        "honeybee_mapping_kind": "property_matched_custom_materials",
        "honeybee_construction_ready": False,
        "pending_carbon_mappings": deepcopy(base.report["pending_carbon_mappings"]),
        "window_assumptions": {"shgc": window.shgc, "vt": window.vt, "physical_panes": None},
        "infiltration": deepcopy(captured["infiltration"]),
        "operations": deepcopy(operations), "unchanged_roles": list(unchanged),
        "assumptions": ["Each state derives independently from Existing; ventilation/zones do not alter layers.",
                        "TABULA source thicknesses and calibrated representative depths are separate evidence.",
                        "Windows specify whole-system U, not a reconstructed pane stack."],
        "pending": list(dict.fromkeys(c["note"] for c in variant["review_annotations"]["open_caveats"])),
        "sources": sources,
        **deepcopy(variant["review_annotations"]),
    }
    result = CalibratedArchetype(archetype, EffectiveProperty(**captured["infiltration"]), report)
    from .nominal import catalogue_lod2_checks

    acceptance = catalogue_lod2_checks(result)
    report.update(lod2_complete=acceptance["lod2_complete"], lod2_checks=acceptance["checks"],
                  renovation_package_complete=acceptance["lod2_complete"],
                  honeybee_construction_ready=acceptance["readiness"]["honeybee_nominal_export"],
                  core_construction_ready=acceptance["readiness"]["core_nominal_export"])
    return result


def instantiate_renovation_honeybee_materials(package):
    """Return real Honeybee objects keyed by identifier when Honeybee is installed.

    This is material conversion only, not composite construction/surface export.
    EPSM's default installation and offline package loader do not require Honeybee.
    """
    from honeybee_energy.material.dictutil import dict_to_material

    records = package.report["honeybee_materials"]
    records = [*records, *(record["honeybee_registration"] for record in
                          package.report["registered_renovation_materials"].values())]
    return {record["identifier"]: dict_to_material(deepcopy(record)) for record in records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", choices=("standard", "advanced"), default="standard")
    parser.add_argument("--path", type=Path, help="Shared registry directory or canonical registry JSON")
    parser.add_argument("--base-path", type=Path, help="Separate registry copy for Existing")
    parser.add_argument("--check", action="store_true", help="Check nominal calibration and evidence drift only")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true")
    output.add_argument("--export", action="store_true")
    parser.add_argument("--catalogue", type=Path, help="LoD1 catalogue JSON; omit for live defaults")
    args = parser.parse_args()
    result = load_renovation_package(args.state, args.path, base_path=args.base_path,
                                     catalogue=_load_parametric_catalogue(args.catalogue))
    if args.json or args.export:
        print(json.dumps(result.to_dict() if args.export else result.report,
                         indent=2, ensure_ascii=False, allow_nan=False))
    else:
        print(result.archetype.display_name)
        for prop, row in result.report["elements"].items():
            difference = row["difference_percent"]
            gap = "boundary pending" if difference is None else f"{difference:+.2f}%"
            print(f"{prop:22} target {row['target_u']:.4f} assembly {row['assembly_u']:.4f}  {gap}")
        print(f"Effective infiltration: {result.infiltration.value:g} ACH")
        print(f"Nominal calibration complete: {result.report['nominal_calibration_complete']}")
        print(f"Catalogue LoD2 complete: {result.report['lod2_complete']}; ground/simulation validation remains separate.")
    if args.check and not result.report["nominal_calibration_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
