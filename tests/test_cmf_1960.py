"""Provisional CMF reconstruction diagnostics, independent of archived files."""

import json
from pathlib import Path

import pytest

from epsm_data import archetype_from_dict, archetype_to_dict
from epsm_data.domain import BuildingElement
from examples.cmf_1960 import analyse, build_cases, load_reconstruction


def test_curated_archive_reproduces_all_captured_u_values():
    data = load_reconstruction()
    archive = build_cases(data)["archive"]
    for role, element in archive.construction_set.elements.items():
        key = "wall" if role is BuildingElement.EXT_WALL else role.value
        assert element.u_value == pytest.approx(data["archive_expected_u"][key], rel=1e-12)


def test_assumed_floor_and_partition_layers_are_explicit():
    data = load_reconstruction()
    elements = data["reconstructed_recipe"]["elements"]
    floor_layers = [layer for component in elements["INTERMEDIATE_FLOOR"]["components"]
                    for layer in component["layers"]]
    assert [layer["material_id"] for layer in floor_layers] == [
        "linoleum", "woodfiber_board", "concrete", "plaster"
    ]
    assert [layer["thickness"] for layer in floor_layers] == [0.0025, 0.013, 0.16, 0.005]
    wall_layers = [layer for component in elements["INT_WALL_NONLOADBEARING"]["components"]
                   for layer in component["layers"]]
    assert wall_layers[0]["material_id"] == wall_layers[-1]["material_id"] == "gypsum_board"
    assert sum(layer["thickness"] for layer in wall_layers) == pytest.approx(0.096)
    # Legacy material assumptions retained, rather than silently fitted to targets.
    assert data["materials"]["cellular_plastic"]["conductivity"] == pytest.approx(0.02997993733)
    assert data["status"] == "provisional_reconstruction_not_lod2_complete"


def test_reconstruction_differences_and_boundary_meanings():
    rows = analyse()["elements"]
    assert rows["INTERMEDIATE_FLOOR"]["reconstructed_u"] == pytest.approx(1.859155, abs=1e-5)
    assert rows["INT_WALL_NONLOADBEARING"]["reconstructed_u"] == pytest.approx(0.555766, abs=1e-5)
    assert rows["TOP_FLOOR"]["lod1_property"] == "roof"
    assert rows["ROOF"]["lod1_property"] is None
    assert rows["BASEMENT_FLOOR"]["lod1_property"] is None
    assert rows["BASEMENT_WALL"]["reconstructed_u"] > 3.0
    assert rows["BASEMENT_WALL"]["lod1_reference_u"] < 1.0
    assert rows["INT_WALL_NONLOADBEARING"]["lod1_reference_u"] == pytest.approx(
        __import__("epsm_data").Catalogue.load().parametric.resolve_construction("multi_family", "SE.02", "existing").u_values["internal_wall"]
    )


def test_cavity_and_material_sensitivities_are_separate():
    report = analyse()
    cases = report["sensitivities"]
    wall = report["elements"]["EXT_WALL"]["reconstructed_u"]
    assert cases["wall_brick_unventilated_cavity"]["u_value"] < wall
    assert cases["wall_well_ventilated_cavity"]["excluded_outer_cladding"]
    assert cases["wall_well_ventilated_cavity"]["rse"] == 0.13
    assert cases["wall_well_ventilated_cavity"]["u_value"] > wall
    assert cases["attic_100mm_mineral_wool"]["u_value"] > 0.4
    assert cases["ground_floor_eps_lambda_0040"]["u_value"] > (
        report["elements"]["GROUND_FLOOR"]["reconstructed_u"]
    )
    assert cases["intermediate_floor_upward_heat_flow"]["u_value"] > (
        cases["intermediate_floor_downward_heat_flow"]["u_value"]
    )


def test_portable_schema_round_trip():
    draft = build_cases()["reconstructed"]
    restored = archetype_from_dict(json.loads(json.dumps(archetype_to_dict(draft))))
    for role, element in draft.construction_set.elements.items():
        assert restored.construction_set.elements[role].u_value == element.u_value
    assert BuildingElement.WINDOW not in restored.construction_set.elements


def test_report_is_deterministic_offline_and_does_not_change_lod1(monkeypatch):
    catalogue_path = Path(__file__).resolve().parents[1] / (
        "src/epsm_data/datasets/parametric/catalogue.json"
    )
    original = catalogue_path.read_bytes()
    original_open = Path.open

    def no_archive_access(path, *args, **kwargs):
        assert "ARCHIVE" not in path.parts
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", no_archive_access)
    report = analyse()
    assert report == analyse()
    json.dumps(report, allow_nan=False)
    assert report["window"]["layer_details"] is None
    assert report["window"]["shgc"] is None
    assert not report["active_catalogue_modified"]
    assert catalogue_path.read_bytes() == original
