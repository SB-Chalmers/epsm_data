"""First calibrated representative and its explicit limits."""

import json
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import pytest

from epsm_data import (
    archetype_from_dict,
    load_calibrated_archetype,
    load_detailed_catalogue,
    load_parametric_catalogue,
)
from epsm_data.domain import BuildingElement


@pytest.fixture
def definition_copy(detailed_copy):
    return detailed_copy


def save_definition(path, definition):
    for name, data in definition.items():
        (path / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")


def test_bundled_calibrated_representative_and_all_nominal_matches():
    result = load_calibrated_archetype()
    report = result.report
    assert report["nominal_calibration_complete"]
    assert report["construction_schema_complete"]
    assert report["target_drift"] == []
    assert len(result.archetype.construction_set.elements) == 7
    assert result.infiltration.value == pytest.approx(.20 * 3.6 / 2.5)
    expected = {"roof": 0.200218, "external_wall": 0.414420,
                "intermediate_floor": 1.821706, "internal_wall": 0.573883,
                "window": 2.2}  # v1.4 provisional MF SE.02 default; see release evidence.
    for prop, target in expected.items():
        row = report["elements"][prop]
        assert row["assembly_u"] == pytest.approx(target, abs=2e-5)
        assert row["within_tolerance"]
        assert abs(row["difference_percent"]) <= 2
    assert BuildingElement.TOP_FLOOR in result.archetype.construction_set.elements
    assert BuildingElement.ROOF not in result.archetype.construction_set.elements


def test_foundation_limits_and_optical_assumptions_not_hidden():
    report = load_calibrated_archetype().report
    for prop in ("ground_floor", "basement_wall"):
        row = report["elements"][prop]
        assert row["status"] == "effective_boundary_pending"
        assert row["within_tolerance"] is None
        assert row["difference_percent"] is None
    assert not report["simulation_ready"]
    assert not report["effective_ground_calibration_complete"]
    assert report["lod2_complete"]
    assert report["window_assumptions"] == {"shgc": 0.7, "vt": 0.75, "physical_panes": None}
    assert "cavity omitted" in report["method"]
    assert report["pending"]


def test_reviewed_materials_use_correct_families_and_independent_thermal_evidence():
    report = load_calibrated_archetype().report
    materials = report["materials"]
    wool = materials["mineral_wool"]["properties"]
    assert wool["boverket_id"] == "6000000123"
    assert (wool["density"], wool["conductivity"], wool["specific_heat"]) == (29, 0.036, 1030)
    eps = materials["cellular_plastic"]["properties"]
    assert eps["boverket_id"] == "6000000131"
    assert eps["density"] == 20
    assert eps["conductivity"] == 0.037
    assert eps["embodied_carbon"]["conversion_factor"] is None
    assert eps["embodied_carbon"]["A1_A3_conservative"] == 4
    for key in ("gypsum_board", "plaster_board"):
        assert materials[key]["boverket_id"] == "6000000020"
    board = materials["woodfiber_board"]["properties"]
    assert (board["density"], board["conductivity"], board["specific_heat"]) == (230, 0.07, 2100)
    assert materials["woodfiber_board"]["candidate_boverket_id"] == "6000000136"
    assert "linoleum" not in materials
    assert materials["rubber_floor_finish"]["properties"]["conductivity"] == 0.17
    assert materials["woodfiber_board"]["mapping_status"] == "reviewed_proxy"
    for review in materials.values():
        assert set(review["thermal_evidence"]) == {"density", "conductivity", "specific_heat"}
        if review["mapping_status"] == "matched_generic_family":
            properties = review["properties"]
            assert properties["boverket_id"] == properties["embodied_carbon"]["resource_id"]


def test_pending_mappings_are_null_not_false_resolved_records_or_zero_impacts():
    result = load_calibrated_archetype()
    assert result.report["pending_carbon_mappings"] == []
    assert not result.report["carbon_assessment_ready"]
    for mid in ("asphalt_board", "cardboard", "linoleum"):
        material = load_detailed_catalogue().resolve_material(mid)
        assert material["boverket_id"] is None
        assert material["properties"]["embodied_carbon"] is None
        assert mid not in result.report["materials"]
    bundle = result.to_dict()
    assert bundle["construction"]["format_version"] == 2
    assert archetype_from_dict(bundle["construction"]) == result.archetype


def test_portable_export_and_deterministic_revisions():
    first = load_calibrated_archetype()
    second = load_calibrated_archetype()
    assert first.to_dict() == second.to_dict()
    bundle = json.loads(json.dumps(first.to_dict(), allow_nan=False))
    restored = archetype_from_dict(bundle["construction"])
    assert restored == first.archetype
    assert bundle["infiltration"]["value"] == pytest.approx(.20 * 3.6 / 2.5)
    assert bundle["calibration"]["pending"]


def test_lod1_evidence_drift_does_not_retune_construction():
    original = load_calibrated_archetype()
    catalogue = load_parametric_catalogue().with_anchor(
        "multi_family", "internal_wall",
        {"value": 0.65, "era": "SE.02", "state": "existing",
         "source": "cmf_1960_1_internal", "note": "Test of future evidence replacement"},
    )
    changed = load_calibrated_archetype(catalogue=catalogue)
    assert changed.report["target_drift"] == ["internal_wall"]
    assert not changed.report["nominal_calibration_complete"]
    assert original.archetype == changed.archetype
    assert changed.report["elements"]["internal_wall"]["target_u"] == original.report["elements"]["internal_wall"]["target_u"]


def test_allowed_edit_changes_revision_and_reports_mismatch(definition_copy):
    path, definition = definition_copy
    original = load_calibrated_archetype(path)
    slab = definition["assemblies"]["assemblies"][definition["archetypes"]["archetypes"]["mf_se02"]["states"]["existing"]["assemblies"]["INTERMEDIATE_FLOOR"]]["components"][0]["layers"][2]
    slab["thickness"] = 0.25
    save_definition(path, definition)
    changed = load_calibrated_archetype(path)
    assert changed.report["revision"] != original.report["revision"]
    assert not changed.report["nominal_calibration_complete"]
    assert not changed.report["elements"]["intermediate_floor"]["within_tolerance"]


@pytest.mark.parametrize("mutation", ["fractional_thickness", "nonfinite_window",
                                     "duplicate_constraint", "invalid_scope", "unknown_source",
                                     "missing_role", "assembly_ref", "false_pending_mapping",
                                     "carbon_id_mismatch", "nonstandard_framing", "thermal_source"])
def test_invalid_calibrated_definitions_rejected(definition_copy, mutation):
    path, definition = definition_copy
    state = definition["archetypes"]["archetypes"]["mf_se02"]["states"]["existing"]
    assemblies = definition["assemblies"]["assemblies"]
    materials = definition["materials"]["materials"]
    honeybee = definition["honeybee"]["materials"]
    if mutation == "fractional_thickness":
        assemblies["mf_se02_existing_intermediate_floor"]["components"][0]["layers"][0]["thickness"] = 0.00317
    elif mutation == "nonfinite_window":
        honeybee["EPSM_window_existing"]["shgc"] = float("nan")
    elif mutation == "duplicate_constraint":
        a = assemblies["mf_se02_existing_top_floor"]
        a["thickness_constraints"].append(a["thickness_constraints"][0])
    elif mutation == "invalid_scope":
        state["key"]["era"] = "SE.03"
    elif mutation == "unknown_source":
        state["target_snapshot"]["roof"]["source"] = "unregistered"
    elif mutation == "missing_role":
        del state["assemblies"]["TOP_FLOOR"]
    elif mutation == "assembly_ref":
        state["assemblies"]["TOP_FLOOR"] = "missing_assembly"
    elif mutation == "false_pending_mapping":
        materials["linoleum"]["boverket_id"] = "6000000020"
    elif mutation == "carbon_id_mismatch":
        resource = next(r for r in definition["boverket"]["Resources"] if r["ResourceId"] == 6000000131)
        resource["ResourceId"] = 6000000210
    elif mutation == "nonstandard_framing":
        assemblies["mf_se02_existing_ext_wall"]["components"][2]["layers"][0]["area_fraction"] = [0.829, 0.171]
    elif mutation == "thermal_source":
        honeybee["EPSM_mineral_wool"]["user_data"]["thermal_evidence"]["density"]["source"] = "missing"
    save_definition(path, definition)
    with pytest.raises(ValueError):
        load_calibrated_archetype(path)


def test_cli_export_and_failed_check(definition_copy):
    command = [sys.executable, "-m", "epsm_data.layered", "--catalogue",
               "src/epsm_data/datasets/parametric/catalogue.json", "--path", "src/epsm_data/datasets/layered"]
    exported = subprocess.run(command + ["--check", "--export"], capture_output=True,
                              text=True, check=True)
    assert json.loads(exported.stdout)["calibration"]["nominal_calibration_complete"]
    assert not exported.stderr
    path, definition = definition_copy
    definition["assemblies"]["assemblies"][definition["archetypes"]["archetypes"]["mf_se02"]["states"]["existing"]["assemblies"]["TOP_FLOOR"]]["components"][0]["layers"][0]["thickness"] = 0.05
    save_definition(path, definition)
    checked = subprocess.run(command + ["--path", str(path), "--check", "--json"],
                             capture_output=True, text=True)
    assert checked.returncode == 1
    assert not json.loads(checked.stdout)["nominal_calibration_complete"]


def test_load_is_offline_and_does_not_change_catalogue(monkeypatch):
    path = files("epsm_data.datasets.parametric").joinpath("catalogue.json")
    before = path.read_bytes()
    source = files("epsm_data.datasets.layered").joinpath("evidence", "cmf_1960_reconstruction.json")
    source_before = source.read_bytes()
    original_open = Path.open

    def checked_open(resource, *args, **kwargs):
        assert "ARCHIVE" not in resource.parts
        return original_open(resource, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked_open)
    assert load_calibrated_archetype().report["nominal_calibration_complete"]
    assert path.read_bytes() == before
    assert source.read_bytes() == source_before
    archived_properties = json.loads(source_before)["materials"]
    assert archived_properties["mineral_wool_carpet"]["density"] == pytest.approx(265.0006059195773)
    assert archived_properties["cellular_plastic"]["boverket_id"] == "6000000210"
