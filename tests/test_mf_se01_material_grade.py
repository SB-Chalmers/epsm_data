"""Independently sourced historic grade, shared use and forward wall calculations."""

import json
from pathlib import Path

import pytest

from epsm_data import BuildingElement, Catalogue, Element, load_sanity_fixture

ROOT = Path(__file__).resolve().parents[1]
GRADE = json.loads((ROOT / "tests/fixtures/material_grades/mf_se01_aac.json").read_text())
MID = GRADE["material_id"]
STATES = tuple(GRADE["wall"]["expected_u_w_m2k"])


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture(scope="module")
def report(catalogue):
    return catalogue.sanity_report()


def test_historic_grade_properties_and_honeybee_record_match_independent_fixture(catalogue):
    record = catalogue.resolved_dict()["materials"][MID]
    assert record["name"] == GRADE["name"]
    assert record["properties"] == GRADE["properties"]
    assert record["honeybee_id"] == GRADE["honeybee_id"]
    assert record["boverket_id"] == GRADE["boverket_id"]
    source = catalogue.honeybee_materials[GRADE["honeybee_id"]]
    assert source["type"] == "EnergyMaterial"
    assert source["identifier"] == GRADE["honeybee_id"]
    assert {field: source[field] for field in GRADE["properties"]} == GRADE["properties"]
    assert "EPSM_mfh_lightweight_concrete" not in catalogue.honeybee_materials
    historical = GRADE["historic_thermal_basis"]
    assert record["properties"]["conductivity"] == pytest.approx(
        historical["conductivity_kcal_m_h_c"] * historical["kcal_m_h_c_to_w_m_k"]
    )


def test_material_grade_source_capture_does_not_claim_tabula_was_a_material_source():
    evidence = json.loads((ROOT / "evidence/mf_se01_wall_material.json").read_text())
    assert evidence["schema_version"] == GRADE["schema_version"]
    assert evidence["material_id"] == MID
    assert evidence["honeybee_id"] == GRADE["honeybee_id"]
    assert evidence["selection"]["grade_status"] == "representative_historic_grade"
    assert evidence["selection"]["rationale"]
    thermal = evidence["thermal"]
    assert thermal["conductivity_basis"] == "effective_masonry_including_mortar"
    historical = thermal["sources"]["density_and_conductivity"]
    assert historical["url"] == GRADE["historic_thermal_basis"]["source_url"]
    assert "p.32" in historical["locator"] and "500" in historical["locator"]
    assert historical["source_value"] == GRADE["historic_thermal_basis"]["conductivity_kcal_m_h_c"]
    assert historical["source_unit"] == "kcal/(m h °C)"
    assert historical["conversion_to_w_mk"] == GRADE["historic_thermal_basis"]["kcal_m_h_c_to_w_m_k"]
    specific_heat = thermal["sources"]["specific_heat"]
    assert specific_heat["value_j_kg_k"] == GRADE["properties"]["specific_heat"]
    assert specific_heat["approximate"] is True
    assert "Table 5.4" in specific_heat["locator"]
    assert thermal["sources"]["surface_defaults"]["status"] == "explicit_modelling_defaults"
    carbon = evidence["carbon"]
    assert carbon["boverket_id"] == GRADE["boverket_id"]
    assert carbon["source_version"] == GRADE["carbon_basis"]["source_version"]
    assert carbon["proxy"] is True
    assert carbon["applicability_density_range_kg_m3"] == GRADE["carbon_basis"]["applicable_density_range_kg_m3"]
    assert carbon["conversion_density_kg_m3"] == GRADE["carbon_basis"]["source_density_kg_m3"]
    assert carbon["density_relative_difference"] == GRADE["carbon_basis"]["density_relative_difference"]
    assert carbon["missing_modules"] == ["A5"]
    assert evidence["construction"]["layer_id"] == GRADE["wall"]["aac_layer_id"]
    assert evidence["construction"]["thickness_m"] == GRADE["wall"]["aac_thickness_m"]
    assert evidence["construction"]["mortar_treatment"]
    assert evidence["benchmark"]["u_value_w_m2k"] == GRADE["tabula_baseline"]["u_value_w_m2k"]
    assert "stock" in evidence["benchmark"]["basis"].lower()


def test_grade_remains_one_shared_material_in_sf_and_mf_se01_walls(catalogue):
    shared = catalogue.materials[MID]
    users = set()
    for aid in catalogue.ids():
        for state in catalogue.renovation_states(aid):
            archetype = catalogue.get(aid, state=state)
            for role, element in archetype.construction_set.elements.items():
                if not isinstance(element, Element):
                    continue
                for component in element.components:
                    for slot in component.layers:
                        for share in slot.layer.materials:
                            if share.material.json_id == MID:
                                assert share.material is shared
                                assert share.area_fraction == 1
                                assert share.thickness == GRADE["wall"]["aac_thickness_m"]
                                assert len(slot.layer.materials) == 1
                                users.add((aid, state, role))
    expected_users = {
        (identifier, state, BuildingElement.EXT_WALL)
        for identifier in ("mf_se01", "sf_se01") for state in STATES
    }
    assert expected_users == {
        (entry["archetype_id"], entry["state"], BuildingElement.EXT_WALL)
        for entry in GRADE["affected_configurations"]
    }
    assert users == expected_users
    for state in STATES:
        generic = catalogue.get("generic_se01", state=state)
        donor = catalogue.get("mf_se01", state=state)
        assert generic.construction_set is donor.construction_set
    layer = catalogue.resolved_dict()["layers"][GRADE["wall"]["aac_layer_id"]]
    assert layer["materials"] == [{"material_id": MID, "area_fraction": 1.0, "thickness": 0.25}]
    assert layer["is_composite"] is False


@pytest.mark.parametrize("state", STATES)
def test_original_and_renovated_wall_u_values_are_forward_calculated(catalogue, state):
    expected = GRADE["wall"]
    wall = catalogue.get("mf_se01", state=state).construction_set.elements[BuildingElement.EXT_WALL]
    original_resistance = (
        expected["inside_surface_resistance_m2_k_w"]
        + expected["outside_surface_resistance_m2_k_w"]
        + 2 * expected["plaster_thickness_each_side_m"] / expected["plaster_conductivity_w_m_k"]
        + expected["aac_thickness_m"] / GRADE["properties"]["conductivity"]
    )
    brick_resistance = (
        expected["renovation_brick_thickness_m"]
        / expected["renovation_brick_conductivity_w_m_k"]
        if state != "existing" else 0
    )
    forward_u = 1 / (
        original_resistance + brick_resistance
        + expected["added_insulation_m"][state]
        / expected["renovation_insulation_conductivity_w_m_k"]
    )
    assert forward_u == pytest.approx(expected["expected_u_w_m2k"][state], rel=1e-12)
    assert wall.u_value == pytest.approx(forward_u, rel=1e-12)
    if state == "existing":
        stack = [
            (share.material.json_id, share.thickness)
            for component in wall.components for slot in component.layers
            for share in slot.layer.materials
        ]
        assert stack == [
            (expected["plaster_material_id"], expected["plaster_thickness_each_side_m"]),
            (MID, expected["aac_thickness_m"]),
            (expected["plaster_material_id"], expected["plaster_thickness_each_side_m"]),
        ]


def test_boverket_aac_proxy_preserves_published_density_and_partial_modules(catalogue, report):
    expected = GRADE["carbon_basis"]
    source = catalogue.boverket_resources[GRADE["boverket_id"]]
    assert source["Name"] == expected["name"]
    assert source["SourceVersion"] == expected["source_version"]
    assert source["InventoryUnit"] == expected["inventory_unit"]
    conversion = [item["Value"] for item in source["Conversions"]
                  if item["Field"] == "Volume" and item["Unit"] == "kg/m³"]
    assert conversion == [expected["source_density_kg_m3"]]
    modules = {
        module["DataModuleCode"]: module["Value"]
        for item in source["DataItems"] if item["PropertyCode"] == "GWP-GHG AR4"
        for module in item["DataValueItems"]
    }
    assert modules == expected["modules_kgco2e_per_kg"]
    assert "A5" not in modules
    assert catalogue.materials[MID].density == GRADE["properties"]["density"]
    assert catalogue.materials[MID].embodied_carbon.conversion_factor == expected["source_density_kg_m3"]
    density = [row for row in report["findings"] if row["rule_id"] == "density.agreement"
               and row["path"] == f"materials.{MID}.properties.density"]
    assert len(density) == 1
    assert density[0]["severity"] == "review"
    assert density[0]["relative_difference"] == expected["density_relative_difference"]
    assert {(user["archetype_id"], user["state"]) for user in density[0]["affected_archetypes"]} == {
        (identifier, state) for identifier in ("mf_se01", "sf_se01") for state in STATES
    }
    assert density[0]["generic_fallback_affected"] is True
    gaps = [row for row in report["findings"] if row["rule_id"] == "carbon.modules"
            and row["path"].startswith(f"boverket.{GRADE['boverket_id']}.")]
    assert len(gaps) == 1
    assert gaps[0]["missing_modules"] == ["A5"]
    assert gaps[0]["partial_modules"] == ["A5.1"]


def test_tabula_baseline_is_unchanged_and_now_within_agreed_tolerance(catalogue, report):
    reference = load_sanity_fixture()
    expected = GRADE["tabula_baseline"]
    row = next(item for item in reference["u_values"] if item["category"] == "multi_family"
               and item["era"] == "SE.01" and item["state"] == "existing")
    assert row["elements"]["EXT_WALL"]["values_w_m2k"] == dict.fromkeys(
        expected["climate_zones"], expected["u_value_w_m2k"]
    )
    assert reference["policy"]["u_value_relative_tolerance"] == expected["relative_tolerance"]
    wall = catalogue.get("mf_se01").construction_set.elements[BuildingElement.EXT_WALL]
    assert abs(wall.u_value - expected["u_value_w_m2k"]) / expected["u_value_w_m2k"] <= expected["relative_tolerance"]
    assert not any(
        finding["rule_id"] == "tabula.u_value"
        and finding["expected"].get("element") == "EXT_WALL"
        and any(user["archetype_id"] == "mf_se01" and user["state"] == "existing"
                for user in finding["affected_archetypes"])
        for finding in report["findings"]
    )
