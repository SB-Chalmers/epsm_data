"""Calibrated Office SE.05 Existing layers and preserved Poirazis source evidence."""

from __future__ import annotations

import argparse
import json
import math
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from .domain import BuildingArchetype, EmbodiedCarbon, OpaqueMaterial, Roughness
from .layered import _digest
from .parametric import ArchetypeKey, load_parametric_catalogue
from .serialization import archetype_to_dict
from .thermal.boundary_conditions import get_boundary_resistances
from .usecases.build_archetype import build_archetype

SOURCE_ROLES = {
    "EXT_WALL_LONG",
    "EXT_WALL_SHORT",
    "ROOF",
    "GROUND_FLOOR",
    "INTERMEDIATE_FLOOR",
    "INT_WALL_NONLOADBEARING",
}
ROLE_PROPERTIES = {
    "EXT_WALL": "external_wall",
    "ROOF": "roof",
    "GROUND_FLOOR": "ground_floor",
    "INTERMEDIATE_FLOOR": "intermediate_floor",
    "INT_WALL_NONLOADBEARING": "internal_wall",
    "WINDOW": "window",
}
OFFICE_ROLES = set(ROLE_PROPERTIES)


def validate_office_evidence(state):
    """Reject incomplete, nonfinite or inconsistent source evidence at load time."""

    def positive(value):
        return (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(value)
            and value > 0
        )

    if state.get("tolerance_percent") not in (2, 5):
        raise ValueError("Office nominal acceptance requires 2% or 5% tolerance")
    if state.get("u_value_basis") != "applied":
        raise ValueError("Office thermal reference must use applied source U-values")
    values = state.get("source_u_values", {})
    if set(values) != SOURCE_ROLES:
        raise ValueError("Office source U-values must cover all six opaque roles")
    for row in values.values():
        if any(not positive(row.get(f)) for f in ("table_5_1", "theoretical", "applied")):
            raise ValueError("Office source U-values must be finite and positive")
        if not row.get("locator"):
            raise ValueError("Office U evidence requires a source locator")
    window = state.get("source_window_aggregation", {})
    if (
        any(
            not positive(window.get(field))
            for field in ("whole_window_u", "glazing_area_fraction", "total_window_area_m2")
        )
        or window["glazing_area_fraction"] > 1
    ):
        raise ValueError("Office requires one finite representative window aggregation")
    if not window.get("locator") or window.get("unshaded") is not True:
        raise ValueError(
            "Office representative window requires source evidence and an unshaded base state"
        )
    areas = state.get("facade_areas_m2", {})
    if set(areas) != {"opaque_long", "opaque_short", "window_long", "window_short"}:
        raise ValueError("Office facade weighting requires all four source areas")
    if not all(positive(v) for v in areas.values()):
        raise ValueError("Office facade areas must be positive")

    originals = state.get("source_assemblies", {})
    if set(originals) != SOURCE_ROLES or any(not a.get("components") for a in originals.values()):
        raise ValueError("Office source evidence must retain all six original stacks")
    expected_roles = OFFICE_ROLES | ({"BASEMENT_WALL"} if state.get("dataset_release") == "epsm-lod2-v1.3" else set())
    if set(state.get("assemblies", {})) != expected_roles:
        raise ValueError("Office requires one wall and one window in the representative recipe")
    optics = state.get("window_optics", {})
    if any(
        not positive(optics.get(f)) or optics[f] > 1
        for f in (
            "glazing_shgc",
            "single_pane_vt",
            "single_pane_visible_reflectance",
            "glazing_vt",
            "shgc",
            "vt",
        )
    ):
        raise ValueError("Office optical evidence requires finite fractions")
    if optics.get("pane_count") != 3 or optics.get("frame_optical_contribution") != 0:
        raise ValueError("Office optical model requires three panes and zero frame contribution")
    if optics["single_pane_vt"] + optics["single_pane_visible_reflectance"] > 1:
        raise ValueError("Office pane transmission plus reflection cannot exceed one")
    t, r = optics["single_pane_vt"], optics["single_pane_visible_reflectance"]
    for _ in range(2):
        den = 1 - r * optics["single_pane_visible_reflectance"]
        t, r = (
            t * optics["single_pane_vt"] / den,
            optics["single_pane_visible_reflectance"] + optics["single_pane_vt"] ** 2 * r / den,
        )
    if not math.isclose(t, optics["glazing_vt"], rel_tol=1e-10):
        raise ValueError("Office glazing VT disagrees with pane composition")
    if not math.isclose(
        window["total_window_area_m2"], areas["window_long"] + areas["window_short"], rel_tol=1e-10
    ):
        raise ValueError("Office window aggregation disagrees with total facade window area")
    for field, glazing in (("shgc", optics["glazing_shgc"]), ("vt", t)):
        if not math.isclose(
            glazing * window["glazing_area_fraction"], optics[field], rel_tol=1e-10
        ):
            raise ValueError("Office representative optics disagree with weighted glazing fraction")


@dataclass(frozen=True)
class OfficeReference:
    """One calibrated representative recipe, with original thesis evidence."""

    archetype: BuildingArchetype
    report: dict

    def to_dict(self):
        return {
            "format_version": 1,
            "kind": "office_calibrated_representative",
            "construction": archetype_to_dict(self.archetype),
            "thermal_reference": {
                "basis": "applied",
                "unit": "W/(m²K)",
                "opaque_u_values": {
                    role: row["u_value"]
                    for role, row in self.report["elements"].items()
                    if role != "WINDOW"
                },
                "window": {
                    field: self.report["window"][field] for field in ("u_value", "shgc", "vt")
                },
                "construction_u_value_meaning": "Calibrated layer U using EPSM reference films, assessed against the declared tolerance and unchanged applied LoD1 targets.",
            },
            "evidence": deepcopy(self.report),
        }

    def to_nominal_dict(self):
        from .nominal import export_nominal_constructions

        return export_nominal_constructions(self)


def _calibrate(spec, definition, detailed, materials):
    """Bounded depth search with fixed conductivities and linked symmetric gaps."""
    from .domain import BuildingElement

    selections = {}
    for role, aid in definition["assemblies"].items():
        assembly = detailed.assemblies[aid]
        constraint = assembly.get("calibration")
        if constraint is None:
            continue
        layers = spec["elements"][role]["components"]
        addresses = constraint["linked_depths"]
        original = [layers[ci]["layers"][li]["source_thickness_m"] for ci, li in addresses]
        target = definition["target_snapshot"][ROLE_PROPERTIES[role]]["value"]
        films = sum(get_boundary_resistances(BuildingElement(role)))
        candidates = []
        for depth in constraint["allowed_thickness_mm"]:
            projected = deepcopy(layers)
            for ci, li in addresses:
                projected[ci]["layers"][li]["thickness"] = depth / 1000
            resistance = sum(
                layer["thickness"] / materials[layer["material_id"]].conductivity
                for c in projected
                for layer in c["layers"]
            )
            u = 1 / (resistance + films)
            error = abs(u / target - 1)
            # Keep the historical selection preference independent of acceptance.
            if error <= 0.02:
                candidates.append((sum(abs(depth / 1000 - d) for d in original), error, depth))
        if not candidates:
            raise ValueError(f"{role}: no allowed thickness matches the applied LoD1 target")
        selected = min(candidates)[2]
        for ci, li in addresses:
            layers[ci]["layers"][li]["thickness"] = selected / 1000
        selections[role] = {
            "source_thicknesses_mm": [d * 1000 for d in original],
            "selected_thickness_mm": selected,
            "allowed_thickness_mm": constraint["allowed_thickness_mm"],
        }
    return selections


def _storage(layers, properties):
    solid = [
        layer
        for layer in layers
        if properties[layer["material_id"]].get("material_type") != "air_gap_equivalent"
    ]
    return {
        "thickness_m": sum(layer["thickness"] for layer in layers),
        "solid_mass_kg_m2": sum(
            layer["thickness"] * properties[layer["material_id"]]["density"] for layer in solid
        ),
        "solid_heat_capacity_j_m2k": sum(
            layer["thickness"]
            * properties[layer["material_id"]]["density"]
            * properties[layer["material_id"]]["specific_heat"]
            for layer in solid
        ),
    }


def load_office_reference(path=None, *, detailed=None, catalogue=None) -> OfficeReference:
    """Build and verify the office recipe from bundled JSON, entirely offline."""
    from .detailed import load_detailed_catalogue

    catalogue = catalogue if catalogue is not None else load_parametric_catalogue()
    detailed = (
        detailed if detailed is not None else load_detailed_catalogue(path, catalogue=catalogue)
    )
    definition, snapshot = detailed.existing_inputs("office_se05")
    validate_office_evidence(definition)
    spec = snapshot[definition["source_recipe"]]
    materials = {}
    for mid, values in snapshot["materials"].items():
        fields = deepcopy(values)
        fields["uuid"] = uuid5(NAMESPACE_URL, f"epsm_data:material:{_digest(fields)}")
        fields["roughness"] = Roughness(fields["roughness"])
        carbon = fields["embodied_carbon"]
        fields["embodied_carbon"] = EmbodiedCarbon(**carbon) if carbon else None
        materials[mid] = OpaqueMaterial(**fields)
    selections = _calibrate(spec, definition, detailed, materials)
    archetype = build_archetype(spec, materials=materials)
    revision = _digest({"definition": definition, "calibrated_snapshot": snapshot})
    archetype = replace(
        archetype,
        construction_set=replace(
            archetype.construction_set,
            version_id=uuid5(NAMESPACE_URL, f"epsm_data:office:{revision}"),
        ),
    )
    rows = {}
    source_properties = {
        mid: {
            **record["user_data"]["source_thermal_properties"],
            "material_type": record["user_data"]["epsm_material_type"],
        }
        for mid, link in detailed.materials.items()
        if mid.startswith("office_")
        for record in [detailed.honeybee_materials[link["honeybee_id"]]]
    }
    for role, element in archetype.construction_set.elements.items():
        name = role.value
        target = definition["target_snapshot"][ROLE_PROPERTIES[name]]["value"]
        row = {
            "u_value": target,
            "u_value_basis": "applied",
            "assembly_u": element.u_value,
            "applied_u": target,
            "difference_from_applied_percent": 100 * (element.u_value / target - 1),
        }
        if name != "WINDOW":
            layers = [layer for c in spec["elements"][name]["components"] for layer in c["layers"]]
            source_role = "EXT_WALL_LONG" if name == "EXT_WALL" else name
            original = [
                layer
                for c in definition["source_assemblies"][source_role]["components"]
                for layer in c["layers"]
            ]
            source = definition["source_u_values"][source_role]
            row.update(_storage(layers, snapshot["materials"]))
            row.update(
                source_metrics=_storage(original, source_properties),
                calibration=selections.get(name),
                source_locator=source["locator"],
                table_5_1_u=source["table_5_1"],
                theoretical_u=source["theoretical"],
                source_applied_u=source["applied"],
                nominal_films=dict(zip(("rsi", "rse"), get_boundary_resistances(role))),
            )
        else:
            row.update(
                shgc=element.shgc,
                vt=element.vt,
                thickness_m=None,
                solid_mass_kg_m2=None,
                solid_heat_capacity_j_m2k=None,
            )
        rows[name] = row
    areas = definition["facade_areas_m2"]
    weighted = {
        "external_wall": {
            "u_value": (
                areas["opaque_long"] * definition["source_u_values"]["EXT_WALL_LONG"]["applied"]
                + areas["opaque_short"] * definition["source_u_values"]["EXT_WALL_SHORT"]["applied"]
            )
            / (areas["opaque_long"] + areas["opaque_short"])
        },
        "window": {"u_value": definition["source_window_aggregation"]["whole_window_u"]},
    }

    slot = catalogue.get_slot(ArchetypeKey(**definition["key"]))
    live = {**slot.construction_set.properties, "infiltration": slot.infiltration}
    drift = [p for p in live if live[p].to_dict() != definition["target_snapshot"][p]]
    refs = detailed.material_references("office_se05")
    pending = [mid for mid, ref in refs.items() if ref["mapping_status"] == "pending"]
    review = detailed.review("office_se05", "existing")
    blockers = [c for c in review["blocking_caveats"] if c.get("scope", "catalogue") == "catalogue"]
    checks = {
        "construction_builder_supported": True,
        "construction_schema": set(rows) == OFFICE_ROLES,
        "representative_source_alignment": all(
            math.isclose(
                row["u_value"], definition["target_snapshot"][prop]["value"], rel_tol=1e-10
            )
            for prop, row in weighted.items()
        )
        and all(
            math.isclose(
                getattr(archetype.window, field), definition["window_optics"][field], rel_tol=1e-10
            )
            for field in ("shgc", "vt")
        ),
        "honeybee_material_references": all(ref["honeybee_id"] for ref in refs.values()),
        "boverket_material_references": not pending,
        "no_open_blocking_catalogue_caveats": not blockers,
        "thermal_and_optical_evidence_reviewed": not any(
            c.get("scope", "catalogue") == "catalogue" for c in review["open_caveats"]
        ),
        "nominal_u_alignment": not drift
        and all(
            abs(row["assembly_u"] / live[ROLE_PROPERTIES[role]].value - 1) <= definition["tolerance_percent"] / 100 + 1e-12
            for role, row in rows.items()
        ),
        "captured_targets_unchanged": not drift,
    }
    report = {
        "status": "calibrated_representative",
        "lod2_fitting": review.get("lod2_fitting"),
        "u_value_basis": "applied",
        "key": definition["key"],
        "revision": revision,
        "catalogue_revision": _digest(catalogue.to_dict()),
        "sources": definition["sources"],
        "elements": rows,
        "role_properties": dict(ROLE_PROPERTIES),
        "window": deepcopy(rows["WINDOW"]),
        "source_window_aggregation": deepcopy(definition["source_window_aggregation"]),
        "source_assemblies": deepcopy(definition["source_assemblies"]),
        "source_material_properties": deepcopy(source_properties),
        "source_u_values": deepcopy(definition["source_u_values"]),
        "window_optics": deepcopy(definition["window_optics"]),
        "facade_areas_m2": areas,
        "area_weighted_reference": weighted,
        "target_snapshot": definition["target_snapshot"],
        "target_drift": drift,
        "material_references": refs,
        "pending_boverket_references": pending,
        "non_product_materials": [
            mid for mid, r in refs.items() if r["mapping_status"] == "not_applicable"
        ],
        "record_annotations": review["record_annotations"],
        "boundary_details": review["boundary_details"],
        "blocking_caveats": blockers,
        "open_caveats": review["open_caveats"],
        "effective_ground_calibration_complete": False,
        "limitations": [
            "One representative wall and window preserve weighted LoD1 targets; facade-specific source recipes are evidence only.",
            "Bounded thickness calibration preserves conductivities but changes representative mass and heat capacity, including the approved 160 mm floor slab.",
            "Serial stud and tabulated air-gap entries are numerical equivalents, not physical framing or cavity ventilation geometry.",
            "EPS density 20 kg/m³ replaces source 1000 kg/m³ in the representative only.",
            "Clear-pane VT transfer, zero frame transmission, surface properties and product-family proxies are reviewed assumptions.",
            "Linoleum/tile surrogates and missing window mass prevent a complete carbon assessment.",
            "Ground boundaries and omitted ceiling plenum need validation before full building simulation; no basement is invented.",
        ],
    }
    result = OfficeReference(archetype, report)
    bundle = result.to_nominal_dict()
    for k in ("honeybee_nominal_export", "core_nominal_export"):
        checks[k] = bundle["readiness"][k]
    report.update(
        lod2_checks=checks, lod2_complete=all(checks.values()), readiness=bundle["readiness"]
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, help="Shared registry directory")
    parser.add_argument(
        "--export", action="store_true", help="Include portable construction layers"
    )
    parser.add_argument(
        "--nominal", action="store_true", help="Export Honeybee and core nominal constructions"
    )
    parser.add_argument(
        "--check", action="store_true", help="Require office catalogue LoD2 acceptance"
    )
    parser.add_argument("--catalogue", type=Path, help="LoD1 catalogue JSON; omit for live defaults")
    args = parser.parse_args()
    result = load_office_reference(args.path, catalogue=load_parametric_catalogue(args.catalogue))
    if args.check and not result.report["lod2_complete"]:
        parser.exit(1, "Office LoD2 acceptance failed; inspect the report.\n")
    print(
        json.dumps(
            result.to_nominal_dict()
            if args.nominal
            else result.to_dict()
            if args.export
            else result.report,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
