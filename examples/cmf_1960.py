"""Offline, provisional CMF_1960_1 reconstruction; never changes LoD1 anchors.

Run ``python -m examples.cmf_1960`` for a comparison, ``--json`` for the
thermal breakdown, or ``--export-reconstructed`` for a portable archetype.
Carbon records in the curated snapshot are unreviewed schema placeholders
and must not be used for carbon assessment.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from dataclasses import asdict, replace
from importlib.resources import files
from pathlib import Path
from uuid import UUID

from epsm_data import (
    ArchetypeKey,
    Catalogue,
    EmbodiedCarbon,
    OpaqueMaterial,
    Roughness,
    archetype_to_dict,
    build_archetype,
)
from epsm_data.domain import BuildingElement
from epsm_data.thermal import compute_element_thermal

DATA_PATH = files("epsm_data.datasets.layered").joinpath("evidence", "cmf_1960_reconstruction.json")
LOD1_PROPERTIES = {
    "TOP_FLOOR": "roof",
    "EXT_WALL": "external_wall",
    "GROUND_FLOOR": "ground_floor",
    "BASEMENT_WALL": "basement_wall",
    "INTERMEDIATE_FLOOR": "intermediate_floor",
    "INT_WALL_NONLOADBEARING": "internal_wall",
}


def load_reconstruction(path=None):
    """Read the curated example, without opening any archived resource."""
    resource = Path(path) if path is not None else DATA_PATH
    with resource.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if data["format_version"] != 1:
        raise ValueError("Unsupported CMF reconstruction format")
    return data


def resolved_materials(data):
    """Instantiate the retained material schema from complete explicit records."""
    materials = {}
    for key, record in data["materials"].items():
        fields = dict(record)
        fields["roughness"] = Roughness(fields["roughness"])
        fields["uuid"] = UUID(fields["uuid"])
        fields["embodied_carbon"] = EmbodiedCarbon(**fields["embodied_carbon"])
        materials[key] = OpaqueMaterial(**fields)
    return materials


def build_cases(data=None):
    """Return independent archive and assumed physical-stack snapshots."""
    data = data if data is not None else load_reconstruction()
    materials = resolved_materials(data)
    return {
        "archive": build_archetype(data["archive_recipe"], materials=materials),
        "reconstructed": build_archetype(data["reconstructed_recipe"], materials=materials),
    }


def _boundary_case(element, *, rsi, rse, extra_resistance=0.0, omit_outer=False):
    result = compute_element_thermal(element)
    layer_resistance = sum(c.r_sum for c in result.component_results)
    if omit_outer:
        layer_resistance -= result.component_results[0].r_sum
    return {
        "u_value": 1 / (rsi + layer_resistance + extra_resistance + rse),
        "rsi": rsi,
        "rse": rse,
        "additional_resistance": extra_resistance,
        "excluded_outer_cladding": omit_outer,
        "status": "diagnostic_boundary_assumption",
    }


def analyse(data=None):
    """Calculate reproducible assembly results, references and sensitivity cases.

    The schema uses area-weighted conductivity within composite layers, not
    the complete ISO 6946 combined-method calculation. Ground results exclude
    ISO 13370 geometry/soil corrections. No thickness is fitted to a target.
    """
    data = data if data is not None else load_reconstruction()
    cases = build_cases(data)
    references = Catalogue.load().get_slot(
        ArchetypeKey("multi_family", "SE.02", "SE.Zone3", "existing", "FTX")
    ).construction_set.u_values
    rows = {}
    for role, element in cases["reconstructed"].construction_set.elements.items():
        name = role.value
        archived = cases["archive"].construction_set.elements[role]
        recipe = data["reconstructed_recipe"]["elements"][name]
        property_name = LOD1_PROPERTIES.get(name)
        rows[name] = {
            "archive_u": compute_element_thermal(archived).u_value,
            "reconstructed_u": element.u_value,
            "lod1_property": property_name,
            "lod1_reference_u": references.get(property_name),
            "nominal_solid_thickness_mm": 1000 * sum(
                layer["thickness"]
                for component in recipe["components"]
                for layer in component["layers"]
            ),
            "ordered_components": recipe["components"],
            "thermal": asdict(compute_element_thermal(element)),
            "notes": data["element_notes"][name],
        }

    elements = cases["reconstructed"].construction_set.elements
    wall = elements[BuildingElement.EXT_WALL]
    sensitivities = {
        "wall_brick_unventilated_cavity": _boundary_case(
            wall, rsi=0.13, rse=0.04, extra_resistance=0.18
        ),
        "wall_well_ventilated_cavity": _boundary_case(
            wall, rsi=0.13, rse=0.13, omit_outer=True
        ),
        "attic_upward_heat_flow": _boundary_case(
            elements[BuildingElement.TOP_FLOOR], rsi=0.10, rse=0.04
        ),
        "intermediate_floor_upward_heat_flow": _boundary_case(
            elements[BuildingElement.INTERMEDIATE_FLOOR], rsi=0.10, rse=0.10
        ),
        "intermediate_floor_downward_heat_flow": _boundary_case(
            elements[BuildingElement.INTERMEDIATE_FLOOR], rsi=0.17, rse=0.17
        ),
    }
    materials = resolved_materials(data)
    board_spec = deepcopy(data["reconstructed_recipe"])
    board_spec["elements"]["EXT_WALL"]["components"][0]["layers"] = [
        {"material_id": "eternit_board", "thickness": 0.009}
    ]
    board = build_archetype(board_spec, materials=materials)
    sensitivities["wall_board_series_only"] = {
        "u_value": board.construction_set.elements[BuildingElement.EXT_WALL].u_value,
        "note": "Alternative historical facade, not an installation recommendation. "
        "No cavity resistance or unknown facade area weighting applied.",
    }
    attic_spec = deepcopy(data["reconstructed_recipe"])
    attic_layers = attic_spec["elements"]["TOP_FLOOR"]["components"][0]["layers"]
    # Preserve the 30 mm blanket and reduce only the 200 mm carpet to 70 mm.
    attic_layers[0]["thickness"] = 0.07
    attic = build_archetype(attic_spec, materials=materials)
    sensitivities["attic_100mm_mineral_wool"] = {
        "u_value": attic.construction_set.elements[BuildingElement.TOP_FLOOR].u_value,
        "note": "Era plausibility sensitivity, not proof of original thickness. "
        "Uses retained-schema surface films.",
    }
    eps_materials = dict(materials)
    eps_materials["cellular_plastic"] = replace(
        materials["cellular_plastic"], conductivity=0.040
    )
    eps = build_archetype(data["reconstructed_recipe"], materials=eps_materials)
    for role in (BuildingElement.GROUND_FLOOR, BuildingElement.BASEMENT_FLOOR):
        sensitivities[f"{role.value.lower()}_eps_lambda_0040"] = {
            "u_value": eps.construction_set.elements[role].u_value,
            "note": "Assumed conductivity sensitivity, not verified period EPS. "
            "Assembly only, not effective ground-boundary U-value.",
        }
    return {
        "classification": data["classification"],
        "status": data["status"],
        "unit": "W/(m2 K)",
        "method": "Retained schema: series resistance and area-weighted layer conductivity",
        "active_catalogue_modified": False,
        "elements": rows,
        "sensitivities": sensitivities,
        "window": {"lod1_u": references["window"], "layer_details": None,
                   "shgc": None, "vt": None},
        "review_notes": data["review_notes"],
        "sources": data["sources"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Thermal report to stdout")
    output.add_argument("--export-reconstructed", action="store_true",
                        help="Portable material-layer archetype to stdout (provisional)")
    args = parser.parse_args()
    if args.export_reconstructed:
        print(json.dumps(archetype_to_dict(build_cases()["reconstructed"]), indent=2))
        return
    report = analyse()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
        return
    print("CMF_1960_1: PROVISIONAL reconstruction; active LoD1 catalogue unchanged")
    print("U-values in W/(m2 K); default retained-schema surface films")
    print(f"{'Role':27} {'Archive':>9} {'Draft':>9} {'LoD1 ref':>10} {'Solid mm':>10}")
    for name, row in report["elements"].items():
        reference = row["lod1_reference_u"]
        ref_text = f"{reference:.3f}" if reference is not None else "-"
        print(f"{name:27} {row['archive_u']:9.3f} {row['reconstructed_u']:9.3f} "
              f"{ref_text:>10} {row['nominal_solid_thickness_mm']:10.1f}")
    print("\nDiagnostic sensitivities:")
    for name, case in report["sensitivities"].items():
        print(f"  {name}: {case['u_value']:.3f}")
    print("\nTOP_FLOOR is the insulated attic boundary, not the ROOF covering.")
    print("Ground/slab and basement assembly U-values are not effective ground values.")
    print("Layer order/thickness changes, material properties and cavity cases need review.")
    print("Window details pending; legacy carbon records are not assessed.")


if __name__ == "__main__":
    main()
