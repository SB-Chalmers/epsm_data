"""SF SE.01 whole-window defaults transcribed from TABULA and shared renovations."""

import json
from pathlib import Path

import pytest

from epsm_data import BuildingElement, Catalogue, load_sanity_fixture

FIXTURE = Path(__file__).parent / "fixtures/catalogue_sanity"
CASE = json.loads((FIXTURE / "cases/sf_se01.json").read_text())
WINDOW = CASE["window"]
STATES = tuple(WINDOW["states"])


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture(scope="module")
def payload(catalogue):
    return catalogue.resolved_dict()


@pytest.fixture(scope="module")
def references():
    return load_sanity_fixture(FIXTURE)


@pytest.fixture(scope="module")
def report(catalogue):
    return catalogue.sanity_report(fixture=FIXTURE)


def _window(payload, state):
    config = payload["archetypes"][CASE["archetype_id"]]["states"][state]
    element_id = payload["construction_sets"][config["construction_set_id"]]["elements"]["WINDOW"]
    material_id = payload["elements"][element_id]["window_material_id"]
    return element_id, material_id, payload["materials"][material_id]


def test_window_fixture_records_original_and_replacement_source_conventions():
    assert CASE["archetype_id"] == "sf_se01"
    assert CASE["category"] == "single_family"
    assert CASE["era"] == "SE.01"
    assert set(STATES) == {"existing", "standard", "advanced"}
    original = WINDOW["states"]["existing"]
    assert original["source_variant"] == "SE.N.SFH.01.Gen.ReEx.001.001"
    assert original["construction_code"] == "SE.Window.ReEx.01.01"
    assert original["properties"]["u_value"] == 2.34
    assert original["glazing_g"] == 0.8
    assert original["frame_fraction"] == 0.3
    assert original["source_locators"]["u_value"] == "TABULA.xlsm#Calc.Building.Set!AT2621"
    assert original["source_locators"]["glazing_g"] == "TABULA.xlsm#Calc.Building.Set!AW2621"
    assert original["source_locators"]["frame_fraction"] == "TABULA.xlsm#Calc.Building.Set!GS2621"
    assert original["source_locators"]["stock_mean_basis"] == "TABULA.xlsm#Tab.Building.Constr!K317"
    assert CASE["u_value_relative_tolerance"] == 0.2


@pytest.mark.parametrize("state", STATES)
def test_sf01_windows_have_whole_aperture_optics_and_consistent_honeybee_link(
    catalogue, payload, state,
):
    expected = WINDOW["states"][state]
    _, _, material = _window(payload, state)
    assert material["kind"] == "window"
    assert material["properties"] == pytest.approx(expected["properties"])
    assert material["boverket_id"] == expected["boverket_id"]
    glazing_fraction = 1 - expected["frame_fraction"]
    assert material["properties"]["shgc"] == pytest.approx(expected["glazing_g"] * glazing_fraction)
    assert material["properties"]["vt"] == pytest.approx(
        expected["glazing_vt_default"] * glazing_fraction)
    source = catalogue.honeybee_materials[material["honeybee_id"]]
    assert source["type"] == "EnergyWindowMaterialSimpleGlazSys"
    assert source["u_factor"] == pytest.approx(expected["properties"]["u_value"])
    assert source["shgc"] == pytest.approx(expected["properties"]["shgc"])
    assert source["vt"] == pytest.approx(expected["properties"]["vt"])


@pytest.mark.parametrize("state", ("standard", "advanced"))
def test_sf01_replacement_windows_share_accepted_mf01_definitions(catalogue, payload, state):
    expected = WINDOW["states"][state]
    element_id, material_id, material = _window(payload, state)
    assert element_id == expected["shared_element_id"]
    assert material_id == expected["shared_material_id"]
    assert material["honeybee_id"] == expected["honeybee_id"]
    sf = catalogue.get(CASE["archetype_id"], state=state)
    mf = catalogue.get("mf_se01", state=state)
    assert sf.construction_set.elements[BuildingElement.WINDOW] is mf.construction_set.elements[
        BuildingElement.WINDOW]


@pytest.mark.parametrize("state", ("standard", "advanced"))
def test_sf01_window_replacements_match_independent_tabula_package(references, state):
    expected = WINDOW["states"][state]
    package = next(row for row in references["renovation_packages"]
                   if row["category"] == CASE["category"] and row["era"] == CASE["era"]
                   and row["state"] == state)
    assert package["source_variant"] == expected["source_variant"]
    measure = references["measures"][package["measures"]["WINDOW"]]
    assert measure["code"] == expected["measure_code"]
    assert measure["window_u_w_m2k"] == pytest.approx(expected["properties"]["u_value"])


@pytest.mark.parametrize("state", STATES)
def test_sf01_windows_pass_each_zone_source_benchmark_without_wider_tolerance(
    catalogue, references, report, state,
):
    expected = WINDOW["states"][state]
    reference = next(row for row in references["u_values"]
                     if row["category"] == CASE["category"] and row["era"] == CASE["era"]
                     and row["state"] == state)["elements"]["WINDOW"]
    assert references["policy"]["u_value_relative_tolerance"] == 0.2
    assert reference["source_locators"] == expected["benchmark_locators"]
    assert set(reference["values_w_m2k"]) == {"SE.Zone1", "SE.Zone2", "SE.Zone3"}
    actual = catalogue.get(CASE["archetype_id"], state=state).construction_set.elements[
        BuildingElement.WINDOW].u_value
    for value in reference["values_w_m2k"].values():
        assert value == pytest.approx(expected["properties"]["u_value"])
        assert actual == pytest.approx(expected["properties"]["u_value"])
        assert abs(actual - value) / value <= CASE["u_value_relative_tolerance"]
    failures = [finding for finding in report["findings"]
                if finding["rule_id"] in {
                    "tabula.u_value", "tabula.reference_missing", "tabula.calculation",
                }
                and finding.get("expected", {}).get("element") == "WINDOW"
                and any(user["archetype_id"] == CASE["archetype_id"] and user["state"] == state
                        for user in finding["affected_archetypes"])]
    assert not failures


def test_sf01_windows_and_renovations_preserve_the_1950_original_year(catalogue, report):
    values = {}
    for state in STATES:
        selected = catalogue.get(CASE["archetype_id"], state=state)
        assert selected.construction_year == CASE["construction_year"] == 1950
        values[state] = selected.construction_set.elements[BuildingElement.WINDOW].u_value
    assert values["advanced"] < values["standard"] < values["existing"]
    assert not [finding for finding in report["findings"]
                if finding["rule_id"] == "renovation.construction_year"
                and any(user["archetype_id"] == CASE["archetype_id"]
                        for user in finding["affected_archetypes"])]


def test_original_window_proxy_and_unmeasured_vt_are_visible(payload):
    _, _, original = _window(payload, "existing")
    notes = " ".join(original["notes"]).lower()
    assert "tabula" in notes and "proxy" in notes
    assert "visible transmittance" in notes or "glazing vt" in notes
    assert "default" in notes
