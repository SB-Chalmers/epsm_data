"""Fridhemsskolan source depths and explicitly provisional school layers."""

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
from .usecases.build_archetype import build_archetype

ROLE_PROPERTIES = {
    "EXT_WALL": "external_wall",
    "ROOF": "roof",
    "GROUND_FLOOR": "ground_floor",
    "INTERMEDIATE_FLOOR": "intermediate_floor",
    "INT_WALL_NONLOADBEARING": "internal_wall",
    "WINDOW": "window",
}


def validate_school_evidence(state, assemblies):
    """Require explicit provenance for every authored source/provisional depth."""
    if set(state["assemblies"]) != set(ROLE_PROPERTIES):
        raise ValueError("School representative requires six roles and one window")
    if set(state["source_u_values"]) != {"EXT_WALL", "ROOF", "GROUND_FLOOR", "WINDOW"}:
        raise ValueError("School source U-values must cover the four reported roles")
    for value in state["source_u_values"].values():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError("Invalid school source U-value")
    for role, aid in state["assemblies"].items():
        assembly = assemblies[aid]
        if assembly.get("evidence_status") not in {"source_reported", "provisional", "mixed"}:
            raise ValueError("School assemblies require explicit evidence status")
        for component in assembly.get("components", []):
            for layer in component["layers"]:
                if layer.get("evidence_status") not in {"source_reported", "provisional"}:
                    raise ValueError("School depths require source/provisional labels")
                if (
                    role in {"INT_WALL_NONLOADBEARING", "INTERMEDIATE_FLOOR"}
                    and layer["evidence_status"] != "provisional"
                ):
                    raise ValueError("School internal assemblies remain provisional")
        if role == "WINDOW":
            panes = assembly["boundary_details"]["provisional_glazing_layers"]
            if len(panes) != 5 or any(
                layer.get("evidence_status") != "provisional" for layer in panes
            ):
                raise ValueError("School detailed glazing must remain provisional")
    basement = state["provisional_hypotheses"]["hus2_basement_wall"]
    if basement.get("active") is not False or basement.get("evidence_status") != "provisional":
        raise ValueError("Hus 2 basement must remain an inactive provisional hypothesis")


@dataclass(frozen=True)
class SchoolReference:
    """One draft school representative; its report preserves all evidence labels."""

    archetype: BuildingArchetype
    report: dict

    def to_dict(self):
        return {
            "format_version": 1,
            "kind": "school_source_and_provisional_layers",
            "construction": archetype_to_dict(self.archetype),
            "thermal_reference": {
                "unit": "W/(m²K)",
                "source_u_values": deepcopy(self.report["source_u_values"]),
                "window": deepcopy(self.report["window"]),
                "meaning": "PUB-611 source U-values and provisional nominal model; separate PUB-003 opaque and school-period window LoD1 targets remain distinct.",
            },
            "evidence": deepcopy(self.report),
        }

    def to_nominal_dict(self):
        from .nominal import export_nominal_constructions

        bundle = export_nominal_constructions(self)
        bundle["kind"] = "source_and_provisional_construction_handover"
        bundle["limitations"].extend(self.report["limitations"])
        for role, row in bundle["honeybee"].items():
            row["user_data"].update(
                evidence_status=self.report["assembly_evidence"][role]["evidence_status"],
                acceptance="draft_not_lod2_accepted",
            )
            if role != "WINDOW":
                layers = [
                    layer
                    for c in self.report["assembly_evidence"][role]["components"]
                    for layer in c["layers"]
                ]
                for native, source in zip(row["materials"], layers, strict=True):
                    native["user_data"].update(
                        depth_evidence_status=source["evidence_status"],
                        density_heat_capacity_surfaces="provisional",
                    )
                bundle["reciprocal"][role]["honeybee"]["materials"] = deepcopy(
                    list(reversed(row["materials"]))
                )
                bundle["reciprocal"][role]["honeybee"]["user_data"].update(
                    evidence_status=self.report["assembly_evidence"][role]["evidence_status"],
                    acceptance="draft_not_lod2_accepted",
                )
        return bundle


def load_school_reference(path=None, *, detailed=None, catalogue=None):
    """Load the shared JSON offline without changing LoD1 or tuning source depths."""
    from .detailed import load_detailed_catalogue

    catalogue = catalogue if catalogue is not None else load_parametric_catalogue()
    detailed = (
        detailed if detailed is not None else load_detailed_catalogue(path, catalogue=catalogue)
    )
    definition, snapshot = detailed.existing_inputs("school_fridhem")
    validate_school_evidence(definition, detailed.assemblies)
    materials = {}
    for mid, values in snapshot["materials"].items():
        fields = deepcopy(values)
        fields["uuid"] = uuid5(NAMESPACE_URL, f"epsm_data:material:{_digest(fields)}")
        fields["roughness"] = Roughness(fields["roughness"])
        fields["embodied_carbon"] = (
            EmbodiedCarbon(**fields["embodied_carbon"]) if fields["embodied_carbon"] else None
        )
        materials[mid] = OpaqueMaterial(**fields)
    archetype = build_archetype(snapshot[definition["source_recipe"]], materials=materials)
    revision = _digest({"definition": definition, "snapshot": snapshot})
    archetype = replace(
        archetype,
        construction_set=replace(
            archetype.construction_set,
            version_id=uuid5(NAMESPACE_URL, f"epsm_data:school:{revision}"),
        ),
    )
    slot = catalogue.get_slot(ArchetypeKey(**definition["key"]))
    live = {**slot.construction_set.properties, "infiltration": slot.infiltration}
    drift = [p for p in live if live[p].to_dict() != definition["target_snapshot"][p]]
    rows = {}
    for role, element in archetype.construction_set.elements.items():
        name = role.value
        row = {
            "assembly_u": element.u_value,
            "source_u": definition["source_u_values"].get(name),
            "lod1_target_u": live[ROLE_PROPERTIES[name]].value,
        }
        row["difference_from_lod1_percent"] = 100 * (row["assembly_u"] / row["lod1_target_u"] - 1)
        if name != "WINDOW":
            row["thickness_m"] = sum(
                slot.layer.thickness for c in element.components for slot in c.layers
            )
        rows[name] = row
    refs = detailed.material_references("school_fridhem")
    review = detailed.review("school_fridhem", "existing")
    blockers = [c for c in review["blocking_caveats"] if c.get("scope", "catalogue") == "catalogue"]
    report = {
        "key": definition["key"],
        "revision": revision,
        "catalogue_revision": _digest(catalogue.to_dict()),
        "status": "source_and_provisional_draft",
        "sources": definition["sources"],
        "elements": rows,
        "role_properties": dict(ROLE_PROPERTIES),
        "source_u_values": definition["source_u_values"],
        "window": {
            "u_value": archetype.window.u_value,
            "shgc": archetype.window.shgc,
            "vt": archetype.window.vt,
            "u_shgc_status": "source_reported_hus1",
            "vt_status": "provisional",
            "detailed_layers_status": "provisional",
        },
        "assembly_evidence": {
            role: detailed.assemblies[aid] for role, aid in definition["assemblies"].items()
        },
        "provisional_hypotheses": definition["provisional_hypotheses"],
        "source_block_variations": definition["source_block_variations"],
        "material_references": refs,
        "record_annotations": review["record_annotations"],
        "boundary_details": review["boundary_details"],
        "open_caveats": review["open_caveats"],
        "blocking_caveats": blockers,
        "target_snapshot": definition["target_snapshot"],
        "target_drift": drift,
        "effective_ground_calibration_complete": False,
        "limitations": [
            "PUB-611 is a 2017 student thesis with no DOI; PUB-003 supplies separate opaque school LoD1 anchors and a user-supplied period profile supplies the window target.",
            "Hus 1/3 source depths are retained; added wall cladding, partition, intermediate floor and detailed glazing are provisional.",
            "The representative uses the Hus 1 window; Hus 3 has a different published window retained only in the evidence note.",
            "VT=.65, density, specific heat, EPS conductivity and surfaces are provisional; solar transmittance .6 is not VT.",
            "Table 3-1 and roof Figure 8-12 disagree on gypsum/framing order; physical roof orientation is unresolved.",
            "Framing/insulation zones are serial equivalents, not verified framing geometry; source macadam is not validated effective ground physics.",
            "Hus 2 variations and provisional basement are inactive evidence; no basement is added to the selected representative.",
            "No source depths are tuned to the separate school LoD1 targets. School catalogue LoD2, complete carbon, ground and simulation readiness are not accepted.",
        ],
    }
    result = SchoolReference(archetype, report)
    bundle = result.to_nominal_dict()
    checks = {
        "construction_builder_supported": True,
        "construction_schema": set(rows) == set(ROLE_PROPERTIES),
        "honeybee_material_references": all(r["honeybee_id"] for r in refs.values()),
        "boverket_material_references": all(
            r["mapping_status"] != "pending" for r in refs.values()
        ),
        "captured_targets_unchanged": not drift,
        "no_open_blocking_catalogue_caveats": not blockers,
        "thermal_and_optical_evidence_reviewed": not any(
            c.get("scope", "catalogue") == "catalogue" for c in review["open_caveats"]
        ),
        "nominal_u_alignment": not drift
        and all(abs(row["difference_from_lod1_percent"]) <= 2 for row in rows.values()),
        "honeybee_nominal_export": bundle["readiness"]["honeybee_nominal_export"],
        "core_nominal_export": bundle["readiness"]["core_nominal_export"],
    }
    report.update(
        lod2_checks=checks, lod2_complete=all(checks.values()), readiness=bundle["readiness"]
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path)
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--nominal", action="store_true")
    parser.add_argument("--catalogue", type=Path, help="LoD1 catalogue JSON; omit for live defaults")
    args = parser.parse_args()
    result = load_school_reference(args.path, catalogue=load_parametric_catalogue(args.catalogue))
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
