"""Source-verified density grades and explicit carbon-module coverage."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from epsm_data import Catalogue, SourceCache, load_sanity_fixture
from epsm_data.sanity_physics import _family, check_physics

FIXTURE = Path(__file__).parent / "fixtures/catalogue_sanity"
CASE = json.loads((FIXTURE / "cases/sf_se02_carbon.json").read_text())
EPS_SOURCE = "6000000131"
GRADE = "EPS 100"


def _density_findings(raw, fixture=None):
    found = []
    check_physics(raw, lambda rule, severity, path, message, **details: found.append({
        "rule_id": rule, "severity": severity, "path": path, **details,
    }), fixture=fixture or load_sanity_fixture(FIXTURE))
    return [row for row in found if row["rule_id"].startswith("density.")]


def _eps():
    observation = CASE["density_grade_references"][EPS_SOURCE][GRADE]
    return {
        "materials": {"eps": {"name": "EPS100", "kind": "opaque",
            "boverket_id": EPS_SOURCE, "carbon_source_grade": GRADE,
            "properties": {"density": 20}}},
        "boverket": {EPS_SOURCE: {"Name": "EPS, expanded polystyrene",
            "ResourceId": int(EPS_SOURCE), "InventoryUnit": "kg",
            "TechnologyDescriptionAndIncludedProcesses": observation["quote"]}},
    }


@pytest.mark.parametrize("case", CASE["taxonomy_cases"], ids=lambda row: row["name"])
def test_eps_taxonomy_accepts_grade_spelling_without_matching_unrelated_words(case):
    assert _family({"name": case["name"]}, load_sanity_fixture(FIXTURE)[
        "construction_rules"])[0] == case["family"]


def test_organized_density_expectations_match_packaged_rules_and_source_quotes():
    rules = load_sanity_fixture(FIXTURE)["construction_rules"]
    for source_id, grades in CASE["density_grade_references"].items():
        assert rules["density_grade_references"][source_id] == grades
    assert _density_findings(_eps()) == []


@pytest.mark.parametrize("change", ["missing_selector", "wrong_selector", "wrong_resource",
    "changed_source_quote", "missing_source_field", "wrong_reference_quote",
    "wrong_reference_value", "wrong_reference_unit", "wrong_reference_basis",
    "wrong_material_basis", "wrong_source_family"])
def test_unproven_grades_never_turn_unassessed_density_into_a_pass(change):
    raw, fixture = _eps(), deepcopy(load_sanity_fixture(FIXTURE))
    material, source = raw["materials"]["eps"], raw["boverket"][EPS_SOURCE]
    reference = fixture["construction_rules"]["density_grade_references"][EPS_SOURCE][GRADE]
    if change == "missing_selector":
        material.pop("carbon_source_grade")
    elif change == "wrong_selector":
        material["carbon_source_grade"] = "EPS 999"
    elif change == "wrong_resource":
        source["ResourceId"] = 6000000132
    elif change == "changed_source_quote":
        source["TechnologyDescriptionAndIncludedProcesses"] = "EPS100 has no declared density."
    elif change == "missing_source_field":
        source.pop("TechnologyDescriptionAndIncludedProcesses")
    elif change == "wrong_reference_quote":
        reference["quote"] = "20 kg/m³ was independently assumed."
    elif change == "wrong_reference_value":
        reference["value"] = 25
    elif change == "wrong_reference_unit":
        reference["unit"] = "lb/ft3"
    elif change == "wrong_reference_basis":
        reference["basis"] = "dry_bulk_volume"
    elif change == "wrong_material_basis":
        material["density_basis"] = "dry_bulk_volume"
    elif change == "wrong_source_family":
        source["Name"] = "Sawn softwood timber"
    rows = _density_findings(raw, fixture)
    assert [row["rule_id"] for row in rows] == ["density.not_assessed"]


def test_existing_volume_conversion_takes_precedence_over_a_grade_observation():
    raw = _eps()
    raw["boverket"][EPS_SOURCE]["Conversions"] = [
        {"Field": "Volume", "Unit": "kg/m³", "Value": 40}]
    rows = _density_findings(raw)
    assert len(rows) == 1 and rows[0]["rule_id"] == "density.agreement"
    assert rows[0]["expected"] == 40
    assert rows[0]["relative_difference"] == 0.5


def test_an_areal_conversion_cannot_be_replaced_with_a_grade_density():
    raw = _eps()
    raw["boverket"][EPS_SOURCE]["Conversions"] = [
        {"Field": "Area", "Unit": "kg/m²", "Value": 4}]
    assert _density_findings(raw)[0]["rule_id"] == "density.not_assessed"


def test_external_grade_density_uses_its_declared_quote_and_keeps_thermal_properties():
    data = Catalogue.load().resolved_dict()
    expected = CASE["loft"]
    material = data["materials"][expected["material_id"]]
    assert material["boverket_id"] is None
    assert material["carbon_source_grade"] == expected["grade"]
    assert material["carbon_reference_id"] == expected["reference"]["identifier"]
    assert material["properties"]["density"] == expected["thermal_density_kg_m3"]
    assert material["properties"]["conductivity"] == expected["thermal_lambda_w_mk"]
    assert expected["source_lambda_w_mk"] != expected["thermal_lambda_w_mk"]
    assert not [row for row in _density_findings(data)
                if row["path"].startswith(f"materials.{expected['material_id']}.")]


def test_eps100_density_observation_preserves_grade_properties_and_raw_source_records():
    data = Catalogue.load().resolved_dict()
    source = data["boverket"][EPS_SOURCE]
    assert not source.get("Conversions")
    for expected in CASE["eps_materials"]:
        material = data["materials"][expected["id"]]
        assert material["carbon_source_grade"] == GRADE
        assert material["properties"]["density"] == expected["density_kg_m3"]
        assert material["properties"]["conductivity"] == expected["lambda_w_mk"]
        assert material["honeybee_id"] == expected["honeybee_id"]
        assert not [row for row in _density_findings(data)
                    if row["path"].startswith(f"materials.{expected['id']}.")]


def test_loft_epd_gwp_ghg_normalization_uses_the_declared_two_kilogram_unit():
    catalogue = Catalogue.load()
    expected = CASE["loft"]
    material = catalogue.materials[expected["material_id"]]
    reference = material.carbon_reference
    assert reference.identifier == expected["reference"]["identifier"]
    assert reference.method == expected["reference"]["method"]
    assert reference.unit == "kg"
    for module, source_value in expected["source_gwp_ghg_per_declared_unit"].items():
        assert reference.modules[module] == source_value / expected["declared_unit_mass_kg"]
    assert reference.modules["A5"] > 0
    assert "A5.1" not in reference.modules
    assert not {"GWP-total", "GWP-fossil"} & set(reference.modules)


def test_boverket_waste_only_a51_stays_distinct_from_missing_full_a5():
    catalogue = Catalogue.load()
    resources = SourceCache.load().records("boverket")
    for source_id, expected in CASE["boverket_a51_values"].items():
        source = resources[source_id]
        values = {item["DataModuleCode"]: item["Value"]
                  for row in source["DataItems"] if row["PropertyCode"] == "GWP-GHG AR4"
                  for item in row["DataValueItems"]}
        assert values["A5.1"] == expected
        assert values.get("A5") is None
    affected = [row for row in catalogue.sanity_report(fixture=FIXTURE)["findings"]
                if row["rule_id"] == "carbon.modules" and any(
                    item["archetype_id"] == "sf_se02" for item in row["affected_archetypes"])]
    assert not any(row["path"].startswith("carbon_references." + CASE["loft"][
        "reference"]["identifier"]) for row in affected)
    assert all("A5" in row["missing_modules"] for row in affected)


def test_underlay_source_area_conversion_is_not_invented_into_volumetric_density():
    data = Catalogue.load().resolved_dict()
    expected = CASE["underlay"]
    material = data["materials"][expected["material_id"]]
    source = data["boverket"][expected["boverket_id"]]
    assert material["properties"]["density"] == expected["thermal_density_kg_m3"]
    assert source["Conversions"] == [{"Field": "Area", "Unit": "kg/m²",
                                       "Value": expected["source_mass_kg_m2"]}]
    layers = [layer for layer in data["layers"].values() if any(
        row["material_id"] == expected["material_id"] for row in layer["materials"])]
    assert layers and all(layer["thickness"] == expected["thickness_m"] for layer in layers)
    mass = expected["thickness_m"] * expected["thermal_density_kg_m3"]
    assert mass == pytest.approx(expected["expected_model_mass_kg_m2"])
    assert abs(mass - expected["source_mass_kg_m2"]) / expected["source_mass_kg_m2"] == (
        pytest.approx(expected["relative_areal_difference"]))
    assert any(row["rule_id"] == "density.not_assessed" and row["path"].startswith(
        f"materials.{expected['material_id']}.") for row in _density_findings(data))


def test_different_concrete_grades_keep_physics_and_distinguishable_names():
    data = Catalogue.load().resolved_dict()
    names = []
    for mid, expected in CASE["concrete_grades"].items():
        material = data["materials"][mid]
        assert all(material["properties"][key] == value for key, value in expected.items())
        assert "concrete" in material["name"].casefold()
        names.append(material["name"].casefold())
    assert len(set(names)) == len(names)
