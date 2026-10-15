"""Export the actual matrix handover and its evidence, without changing data.

Reference: EPSM Data LoD2 v1.3 README/claim register. Seven available construction
roles are not seven surfaces present in every building. Ground references retain
their legacy effective meaning; comparison with nominal layer U is informational,
not a reason to tune insulation to soil-effective values.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from epsm_data._logging import configure_cli

from .detailed import _load_detailed_catalogue
from .layered import _load_calibrated_archetype
from .parametric import ArchetypeKey, _load_parametric_catalogue

ROLE_MAP = {
    "EXT_WALL": "external_wall",
    "TOP_FLOOR": "roof",
    "ROOF": "roof",
    "GROUND_FLOOR": "ground_floor",
    "BASEMENT_WALL": "basement_wall",
    "INTERMEDIATE_FLOOR": "intermediate_floor",
    "INT_WALL": "internal_wall",
    "WINDOW": "window",
    "INT_WALL_NONLOADBEARING": "internal_wall",
}


def audit_matrix(*, catalogue=None, detailed=None):
    """Return canonical state/property evidence and nominal export values.

    Both catalogue and detailed sources are optional caller-owned copies. This
    audit performs no EPC fitting, engine runs or edits. Evidence weakness is
    retained verbatim in the records; no confidence intervals are invented.
    """
    cat = catalogue or _load_parametric_catalogue()
    data = detailed or _load_detailed_catalogue(catalogue=cat)
    states = []
    for aid, arch in sorted(data.archetypes.items()):
        if arch.get("catalogue_assignment", "canonical") != "canonical":
            continue
        for state, definition in sorted(arch["states"].items()):
            if definition.get("release_profile") not in ("lod2-v1", "complete_recipe"):
                continue
            model = _load_calibrated_archetype(
                archetype_id=aid, renovation_state=state, catalogue=cat, detailed=data
            )
            bundle = model.to_nominal_dict()
            slot = cat.get_slot(ArchetypeKey(**definition["key"]))
            properties = {}
            for role, item in bundle["roles"].items():
                prop = ROLE_MAP[role]
                reference = slot.properties[prop]
                nominal = item["nominal_u_w_m2k"]
                ground = prop in ("ground_floor", "basement_wall")
                properties[prop] = {
                    "catalogue_reference_u_w_m2k": reference.value,
                    "exported_nominal_u_w_m2k": nominal,
                    "reference_kind": "legacy_effective_ground" if ground else "nominal_fabric",
                    "difference_percent": 100 * (nominal / reference.value - 1),
                    "comparison": "different_physical_quantities"
                    if ground
                    else "nominal_alignment",
                    "evidence": reference.to_dict(),
                }
            states.append(
                {
                    "archetype_id": aid,
                    "state": state,
                    "key": definition["key"],
                    "properties": properties,
                    "infiltration": slot.infiltration.to_dict(),
                    "window": bundle["core"]["WINDOW"],
                    "readiness": bundle["readiness"],
                    "source_ids": definition["source_ids"],
                    "caveats": definition.get("caveats", []),
                    "element_presence": "caller_geometry",
                    "annual_building_validation": "pending",
                }
            )
    return {
        "schema_version": 1,
        "catalogue_changed": False,
        "canonical_states": len(states),
        "classification_slots": len(cat.slots),
        "states": states,
        "interpretation": "Construction/evidence audit; no building-accuracy claim",
    }


def main(argv=None):
    """Write an explicitly requested audit file; refuse to overwrite evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-level",
        choices=("OFF", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
        help="Status output on stderr",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    with configure_cli(args.log_level, "epsm_data"):
        if args.output.exists():
            raise FileExistsError(args.output)
        result = audit_matrix()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
