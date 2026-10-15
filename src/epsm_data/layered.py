"""First calibrated layered representative: MF SE.02 Existing.

No archived resources, source services, or simulation adapters are used.
Nominal calibration is not a claim of effective ground calibration or LoD2
completeness. Run ``python -m epsm_data.layered --check`` for its report.
"""

# Release contract: v1.4 preserves v1.3 roles; see evidence/lod2_v1_4/window-diagnostic.json.
from __future__ import annotations

import argparse
import hashlib
import json
import math
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from epsm_data._logging import operation as logged_operation

from .detailed import _load_detailed_catalogue
from .domain import BuildingArchetype, BuildingElement, EmbodiedCarbon, OpaqueMaterial, Roughness
from .parametric import ERAS, ArchetypeKey, EffectiveProperty, _load_parametric_catalogue
from .serialization import archetype_to_dict
from .thermal import compute_element_thermal
from .usecases.build_archetype import build_archetype

ROLE_MAP = {
    "roof": "TOP_FLOOR",
    "external_wall": "EXT_WALL",
    "intermediate_floor": "INTERMEDIATE_FLOOR",
    "internal_wall": "INT_WALL_NONLOADBEARING",
    "window": "WINDOW",
}
OFFICE_ROLE_MAP = {**ROLE_MAP, "roof": "ROOF"}
GROUND_ROLES = {"ground_floor": "GROUND_FLOOR", "basement_wall": "BASEMENT_WALL"}


@dataclass(frozen=True, repr=False)
class CalibratedArchetype:
    """Material-layer archetype plus separate infiltration and calibration evidence."""

    archetype: BuildingArchetype
    infiltration: EffectiveProperty
    report: dict

    def __repr__(self):
        label = repr(self.archetype.archetype_id)
        if len(label) > 65:
            label = repr(self.archetype.archetype_id[:8] + "…")
        if len(label) > 65:
            label = "'…'"
        return f"CalibratedArchetype(id={label}, elements={self.archetype.total_elements})"

    __str__ = __repr__

    def summary(self):
        """Return loaded identity and physical element count without I/O."""
        return {"archetype_id": self.archetype.archetype_id,
                "elements": self.archetype.total_elements,
                "status": self.report.get("status")}

    def to_nominal_dict(self):
        """Role-preserving Honeybee/core handover, with modelling limitations."""
        from .nominal import export_nominal_constructions

        return export_nominal_constructions(self)

    def to_dict(self) -> dict:
        """Portable bundle; decode ``construction`` with archetype_from_dict.

        Keep the calibration evidence with the construction when transferring
        it: optical proxies, ground and cavity limitations are not material layers.
        """
        return {
            "format_version": 1,
            "kind": "calibrated_representative",
            "construction": archetype_to_dict(self.archetype),
            "infiltration": self.infiltration.to_dict(),
            "calibration": deepcopy(self.report),
        }


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _number(value, label, *, positive=True):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (value <= 0 if positive else value < 0)):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


@logged_operation("catalogue.archetype.load", level=10)
def _load_calibrated_archetype(path=None, *, catalogue=None, renovation_state=None,
                              renovation_path=None, detailed=None,
                              archetype_id="mf_se02") -> CalibratedArchetype:
    """Build the bundled or caller-edited calibrated definition, entirely offline.

    ``path`` is a shared registry directory or canonical registry JSON. Layer
    constraints reject nonstandard choices rather than silently rounding them.
    Targets are captured evidence: changing the live LoD1 catalogue reports
    target drift and never automatically retunes thicknesses.

    Standard/Advanced select independent packages in archetypes.json.
    ``renovation_path`` can select a separate registry copy for those packages.
    """
    detailed = detailed if detailed is not None else _load_detailed_catalogue(path, catalogue=catalogue)
    if renovation_state is None and detailed.archetypes[archetype_id]["era"] != "SE.07":
        renovation_state = "existing"
    if detailed.archetypes[archetype_id]["era"] == "SE.07" and renovation_state is not None:
        raise ValueError("SE.07 has no renovation states")
    full_recipe = detailed.archetypes[archetype_id]["states"][renovation_state].get("release_profile") in ("lod2-v1", "complete_recipe")
    if renovation_state != "existing" and archetype_id == "mf_se02" and not full_recipe:
        from .renovation import load_renovation_package

        return load_renovation_package(renovation_state,
                                       renovation_path if renovation_path is not None else path,
                                       base_path=path, catalogue=catalogue,
                                       detailed=detailed if renovation_path is None else None)
    if renovation_path is not None:
        raise ValueError("renovation_path applies only to Standard or Advanced")
    detailed = detailed if detailed is not None else _load_detailed_catalogue(path, catalogue=catalogue)
    definition, snapshot = detailed.state_inputs(archetype_id, renovation_state)
    tolerance = _number(definition["tolerance_percent"], "tolerance_percent")
    if tolerance not in (2, 5):
        raise ValueError("MF nominal acceptance requires 2% or 5% tolerance")
    key = ArchetypeKey(**definition["key"])
    role_map = OFFICE_ROLE_MAP if key.category == "office" else ROLE_MAP
    if definition["calibrated_roles"] != role_map:
        raise ValueError("Only the five declared above-ground/window roles are nominally calibrated")
    if key.category not in {"multi_family", "single_family", "office", "school", "generic"} or key.renovation_state != renovation_state:
        raise ValueError("This builder requires a matching supported state")
    if (not definition.get("sources") or not isinstance(definition.get("assumptions"), list)
            or not isinstance(definition.get("pending"), list)):
        raise ValueError("Calibrated definitions require sources and review annotation lists")

    spec = deepcopy(snapshot[definition["source_recipe"]])
    spec.update(definition["identity"])
    start, end = ERAS[key.era]
    if (spec["building_typology"] != key.category or not start <= spec["construction_year"]
            or (end is not None and spec["construction_year"] > end)):
        raise ValueError("Representative identity/year must agree with the MF era")
    for role, patch in definition["element_patches"].items():
        BuildingElement(role)
        spec["elements"][role] = deepcopy(patch)
    included = definition["included_roles"]
    ground_roles = {"ground_floor": "GROUND_FLOOR"}
    if key.category not in {"office", "school"} or key.era == "SE.01" or definition.get("dataset_release") in ("epsm-lod2-v1.3", "epsm-lod2-v1.4", "current"):
        ground_roles["basement_wall"] = "BASEMENT_WALL"
    if len(included) != len(set(role_map.values()) | set(ground_roles.values())) or set(included) != set(role_map.values()) | set(ground_roles.values()):
        raise ValueError("The calibrated MF construction set must contain exactly seven roles")
    spec["elements"] = {role: spec["elements"][role] for role in included}
    seen = set()
    for constraint in definition["layer_constraints"]:
        address = (constraint["role"], constraint["component"], constraint["layer"])
        if address in seen:
            raise ValueError(f"Duplicate thickness constraint: {address}")
        seen.add(address)
        allowed = constraint["allowed_thickness_mm"]
        if not allowed or len(set(allowed)) != len(allowed):
            raise ValueError("Thickness choices must be nonempty and unique")
        for value in allowed:
            _number(value, "allowed thickness")
        role, component_index, layer_index = address
        for index in (component_index, layer_index):
            if isinstance(index, bool) or not isinstance(index, int) or index < 0:
                raise ValueError("Layer constraint indices must be nonnegative integers")
        layer = spec["elements"][role]["components"][component_index]["layers"][layer_index]
        thickness = _number(layer["thickness"], "layer thickness") * 1000
        if not any(math.isclose(thickness, value, rel_tol=0, abs_tol=1e-8) for value in allowed):
            raise ValueError(f"Thickness {thickness:g} mm is outside declared practical choices: {address}")
    window = spec["elements"]["WINDOW"]
    for field in ("u_value", "shgc", "vt"):
        _number(window[field], f"window {field}")

    seen_framing = set()
    for constraint in definition.get("framing_constraints", []):
        address = (constraint["role"], constraint["component"], constraint["layer"])
        if address in seen_framing:
            raise ValueError(f"Duplicate framing constraint: {address}")
        seen_framing.add(address)
        role, ci, li = address
        for index in (ci, li):
            if isinstance(index, bool) or not isinstance(index, int) or index < 0:
                raise ValueError("Framing constraint indices must be nonnegative integers")
        layer = spec["elements"][role]["components"][ci]["layers"][li]
        ids = layer["material_id"]
        if not isinstance(ids, list) or constraint["material_id"] not in ids:
            raise ValueError(f"Framing constraint must reference a composite material: {address}")
        allowed = constraint["allowed_area_fractions"]
        if not allowed or len(set(allowed)) != len(allowed):
            raise ValueError("Framing choices must be nonempty and unique")
        for fraction in allowed:
            if _number(fraction, "framing fraction", positive=False) > 1:
                raise ValueError("Framing fractions must be between zero and one")
        selected = layer["area_fraction"][ids.index(constraint["material_id"])]
        if not any(math.isclose(selected, fraction, rel_tol=0, abs_tol=1e-8) for fraction in allowed):
            raise ValueError(f"Framing share outside declared choices: {address}")

    used_ids = set()
    for role, element_spec in spec["elements"].items():
        if role == "WINDOW":
            continue
        for component in element_spec["components"]:
            for layer in component["layers"]:
                ids = layer["material_id"]
                used_ids.update([ids] if isinstance(ids, str) else ids)
    reviews = definition.get("material_reviews", {})
    if not used_ids <= set(reviews):
        raise ValueError("Every instantiated material requires an explicit mapping/thermal review")
    materials = {}
    material_report = {}
    for mid in sorted(used_ids):
        fields = deepcopy(snapshot["materials"][mid])
        review = deepcopy(reviews[mid])
        if review["source"] not in definition["sources"] or not review.get("note"):
            raise ValueError(f"Material review needs a source and note: {mid}")
        fields.update(deepcopy(review["properties"]))
        status = review["mapping_status"]
        if status not in ("matched_generic_family", "reviewed_proxy", "pending", "not_applicable"):
            raise ValueError(f"Unknown material mapping status: {mid}")
        carbon = fields["embodied_carbon"]
        if status in {"pending", "not_applicable"}:
            if fields["boverket_id"] is not None or carbon is not None:
                raise ValueError(f"Pending material mappings must have null ID and carbon: {mid}")
        elif (not fields["boverket_id"] or carbon is None
              or fields["boverket_id"] != carbon["resource_id"]):
            raise ValueError(f"Matched material IDs must agree with the carbon record: {mid}")
        for item in review["thermal_evidence"].values():
            if item["source"] not in definition["sources"] or not item.get("note"):
                raise ValueError(f"Dangling thermal evidence: {mid}")
        for field in ("conductivity", "density", "specific_heat"):
            _number(fields[field], f"material {mid} {field}")
        fields["uuid"] = uuid5(NAMESPACE_URL, f"epsm_data:material:{_digest(fields)}")
        fields["roughness"] = Roughness(fields["roughness"])
        fields["embodied_carbon"] = EmbodiedCarbon(**carbon) if carbon is not None else None
        materials[mid] = OpaqueMaterial(**fields)
        material_report[mid] = {
            **review,
            "boverket_id": fields["boverket_id"],
            "properties": materials[mid].to_dict(),
        }
    archetype = build_archetype(spec, materials=materials)
    revision = _digest({"definition": definition, "source_snapshot": snapshot})
    archetype = replace(archetype, construction_set=replace(
        archetype.construction_set,
        version_id=uuid5(NAMESPACE_URL, f"epsm_data:layered:{revision}"),
    ))

    catalogue = catalogue if catalogue is not None else _load_parametric_catalogue()
    target_catalogue = detailed.target_catalogue(archetype_id, catalogue)
    slot = target_catalogue.get_slot(key)
    live = {**slot.construction_set.properties, "infiltration": slot.infiltration}
    captured = definition["target_snapshot"]
    if set(captured) != set(live):
        raise ValueError("Target snapshot must contain all seven U-values and infiltration")
    for prop, reference in captured.items():
        _number(reference["value"], f"target {prop}", positive=prop != "infiltration")
        if reference.get("source") not in catalogue.to_dict()["sources"]:
            raise ValueError(f"Unknown target source: {reference.get('source')}")
        if reference["unit"] != live[prop].unit:
            raise ValueError(f"Invalid target unit for {prop}")
    drift = [prop for prop in live if live[prop].to_dict() != captured[prop]]
    rows = {}
    for prop, role_name in {**role_map, **ground_roles}.items():
        element = archetype.construction_set.elements[BuildingElement(role_name)]
        target = captured[prop]["value"]
        ground = prop in GROUND_ROLES
        opaque = role_name != "WINDOW"
        rows[prop] = {
            "role": role_name,
            "target_u": target,
            "assembly_u": element.u_value,
            "difference_percent": None if ground else 100 * (element.u_value / target - 1),
            "within_tolerance": None if ground else abs(100 * (element.u_value / target - 1)) <= tolerance + 1e-10,
            "status": "effective_boundary_pending" if ground else (
                "simple_window_target_with_assumed_optics" if not opaque else "nominal_layer_calibration"
            ),
            "target_evidence": deepcopy(captured[prop]),
            "thermal": asdict(compute_element_thermal(element)) if opaque else None,
        }
    report = {
        "dataset_release": definition.get("dataset_release"),
        "construction_availability": list(included),
        "element_presence": "caller_geometry",
        "identity": definition["identity"],
        "key": key.to_dict(),
        "scope_note": definition["scope_note"],
        "revision": revision,
        "catalogue_revision": _digest(catalogue.to_dict()),
        "target_catalogue_revision": _digest(target_catalogue.to_dict()),
        "catalogue_assignment": detailed.archetypes[archetype_id].get("catalogue_assignment", "canonical"),
        "target_drift": drift,
        "unit": "W/(m2 K)",
        "tolerance_percent": tolerance,
        "method": ("Retained-schema reference films and area-weighted layer conductivity; explicit cavity equivalents included"
                   if any(x.get("cavity_nominal_r_m2k_w") for x in definition["review_annotations"].get("boundary_details", {}).values())
                   else "Retained-schema reference films and area-weighted layer conductivity; cavity omitted"),
        "construction_schema_complete": True,
        "nominal_calibration_complete": all(rows[prop]["within_tolerance"] for prop in role_map) and not drift,
        "effective_ground_calibration_complete": False,
        "lod2_complete": False,
        "simulation_ready": False,
        "elements": rows,
        "materials": material_report,
        "pending_carbon_mappings": [mid for mid in sorted(used_ids)
                                    if reviews[mid]["mapping_status"] == "pending"],
        "carbon_assessment_ready": False,
        "window_assumptions": {"shgc": window["shgc"], "vt": window["vt"], "physical_panes": None},
        "infiltration": deepcopy(captured["infiltration"]),
        "assumptions": definition["assumptions"],
        "pending": definition["pending"],
        "sources": {**snapshot["sources"], **definition["sources"]},
        **deepcopy(definition["review_annotations"]),
    }
    # Captured infiltration and construction belong to the same revision; live
    # target changes are reported above, not applied selectively to the bundle.
    infiltration = EffectiveProperty(**captured["infiltration"])
    result = CalibratedArchetype(archetype, infiltration, report)
    from .nominal import catalogue_lod2_checks

    acceptance = catalogue_lod2_checks(result)
    report.update(lod2_complete=acceptance["lod2_complete"], lod2_checks=acceptance["checks"],
                  honeybee_construction_ready=acceptance["readiness"]["honeybee_nominal_export"],
                  core_construction_ready=acceptance["readiness"]["core_nominal_export"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, help="Shared registry directory or canonical registry JSON")
    parser.add_argument("--state", choices=("existing", "standard", "advanced"), default="existing")
    parser.add_argument("--renovation-path", type=Path, help="Separate registry copy for renovation packages")
    parser.add_argument("--check", action="store_true", help="Fail on nominal mismatch or target drift")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Calibration report to stdout")
    output.add_argument("--export", action="store_true", help="Portable construction/evidence bundle to stdout")
    output.add_argument("--nominal-export", action="store_true", help="Role-preserving Honeybee/core nominal constructions")
    parser.add_argument("--catalogue", type=Path, help="LoD1 catalogue JSON; omit for live defaults")
    args = parser.parse_args()
    calibrated = _load_calibrated_archetype(args.path, renovation_state=args.state,
                                          renovation_path=args.renovation_path,
                                          catalogue=_load_parametric_catalogue(args.catalogue))
    report = calibrated.report
    if args.json or args.export or args.nominal_export:
        payload = calibrated.to_nominal_dict() if args.nominal_export else (calibrated.to_dict() if args.export else report)
        print(json.dumps(payload,
                         indent=2, ensure_ascii=False, allow_nan=False))
    else:
        print(calibrated.archetype.display_name + ": not verified as-built")
        print(f"Nominal tolerance: {report['tolerance_percent']:g}%; U-values in W/(m2 K)")
        print(f"{'Property':22} {'LoD1':>8} {'Assembly':>10} {'Difference':>12}")
        for prop, row in report["elements"].items():
            difference = row["difference_percent"]
            text = f"{difference:+.2f}%" if difference is not None else "boundary gap"
            print(f"{prop:22} {row['target_u']:8.3f} {row['assembly_u']:10.3f} {text:>12}")
        print(f"Effective infiltration: {calibrated.infiltration.value:g} ACH")
        print(f"Nominal calibration complete: {report['nominal_calibration_complete']}")
        print("Pending carbon mappings:", ", ".join(report["pending_carbon_mappings"]))
        print(f"Catalogue LoD2 complete: {report['lod2_complete']}; ground/simulation validation remains separate.")
        if report["target_drift"]:
            print("Changed LoD1 evidence:", ", ".join(report["target_drift"]))
    if args.check and not report["nominal_calibration_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
