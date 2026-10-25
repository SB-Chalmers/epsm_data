"""Source-defined window corrections, shared definitions and untouched assignments."""

import json
from pathlib import Path

import pytest

from epsm_data import BuildingElement, Catalogue, load_sanity_fixture

FIXTURE = Path(__file__).parent / "fixtures/catalogue_sanity"
CASE = json.loads((FIXTURE / "cases/tabula_quick_fixes.json").read_text())
WINDOW = CASE["window"]
STANDARD = WINDOW["standard_replacements"]
BASELINES = WINDOW["baseline_replacements"]
CHANGED = (*STANDARD, *BASELINES)
MF_CHANGED = tuple(case for case in CHANGED if case["category"] == "multi_family")


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


def _case_id(case):
    return f"{case['archetype_id']}:{case['state']}"


def _window(payload, identifier, state):
    config = payload["archetypes"][identifier]["states"][state]
    element_id = payload["construction_sets"][config["construction_set_id"]]["elements"]["WINDOW"]
    material_id = payload["elements"][element_id]["window_material_id"]
    return element_id, material_id, payload["materials"][material_id]


def _reference(references, case):
    return next(row for row in references["u_values"]
                if all(row[key] == case[key] for key in ("category", "era", "state")))


def _assert_simple_glazing(catalogue, material, expected):
    assert material["properties"] == pytest.approx(expected)
    source = catalogue.honeybee_materials[material["honeybee_id"]]
    assert source["type"] == "EnergyWindowMaterialSimpleGlazSys"
    assert source["u_factor"] == pytest.approx(expected["u_value"])
    assert source["shgc"] == pytest.approx(expected["shgc"])
    assert source["vt"] == pytest.approx(expected["vt"])


def test_fixture_bounds_exactly_thirteen_window_replacements():
    assert len(STANDARD) == 9
    assert {case["archetype_id"] for case in STANDARD} == {
        *(f"sf_se{era:02d}" for era in range(1, 6)),
        *(f"mf_se{era:02d}" for era in range(2, 6)),
    }
    assert {case["state"] for case in STANDARD} == {"standard"}
    assert {case["archetype_id"] for case in BASELINES} == {
        "sf_se02", "sf_se03", "mf_se03", "mf_se04",
    }
    assert {case["state"] for case in BASELINES} == {"existing"}
    assert len(CHANGED) == 13
    assert CASE["u_value_relative_tolerance"] == 0.2


@pytest.mark.parametrize("case", STANDARD, ids=_case_id)
def test_standard_windows_reuse_accepted_mf_se01_definition(catalogue, payload, case):
    expected = WINDOW["standard_shared"]
    element_id, material_id, material = _window(payload, case["archetype_id"], case["state"])
    assert element_id == expected["element_id"]
    assert material_id == expected["material_id"]
    assert material["honeybee_id"] == expected["honeybee_id"]
    assert material["boverket_id"] == expected["boverket_id"]
    _assert_simple_glazing(catalogue, material, expected["properties"])
    donor = catalogue.get("mf_se01", state="standard").construction_set.elements[
        BuildingElement.WINDOW]
    selected = catalogue.get(case["archetype_id"], state="standard").construction_set.elements[
        BuildingElement.WINDOW]
    assert selected is donor


def test_standard_window_has_one_shared_physical_definition(payload):
    expected = WINDOW["standard_shared"]
    matches = [identifier for identifier, material in payload["materials"].items()
               if material["kind"] == "window"
               and material["properties"] == expected["properties"]
               and material["boverket_id"] == expected["boverket_id"]]
    assert matches == [expected["material_id"]]


@pytest.mark.parametrize("case", BASELINES, ids=_case_id)
def test_original_windows_use_tabula_whole_window_and_explicit_optical_defaults(
    catalogue, payload, case,
):
    _, _, material = _window(payload, case["archetype_id"], case["state"])
    _assert_simple_glazing(catalogue, material, case["properties"])
    assert material["boverket_id"] == WINDOW["baseline_carbon_proxy_id"]
    assert material["properties"]["shgc"] == pytest.approx(
        case["glazing_g"] * (1 - case["frame_fraction"]))
    assert material["properties"]["vt"] == pytest.approx(
        case["glazing_vt_default"] * (1 - case["frame_fraction"]))
    notes = " ".join(material["notes"]).lower()
    assert "tabula" in notes and "not a verified historic product" in notes
    assert "proxy" in notes and "visible transmittance" in notes and "default" in notes


@pytest.mark.parametrize("case", STANDARD, ids=_case_id)
def test_standard_window_package_and_optics_match_independent_source_measure(references, case):
    expected = WINDOW["standard_shared"]
    package = next(row for row in references["renovation_packages"]
                   if all(row[key] == case[key] for key in ("category", "era", "state")))
    assert package["source_variant"] == case["source_variant"]
    measure = references["measures"][package["measures"]["WINDOW"]]
    assert measure["code"] == expected["measure_code"]
    assert measure["window_u_w_m2k"] == pytest.approx(expected["properties"]["u_value"])
    assert expected["properties"]["shgc"] == pytest.approx(
        expected["glazing_g"] * (1 - expected["frame_fraction"]))
    assert expected["properties"]["vt"] == pytest.approx(
        expected["glazing_vt_default"] * (1 - expected["frame_fraction"]))


@pytest.mark.parametrize("case", CHANGED, ids=_case_id)
def test_corrected_windows_pass_all_three_zone_benchmarks_without_wider_tolerance(
    catalogue, references, report, case,
):
    benchmark = _reference(references, case)["elements"]["WINDOW"]
    expected = (WINDOW["standard_shared"] if case["state"] == "standard" else case)["properties"]
    assert references["policy"]["u_value_relative_tolerance"] == 0.2
    assert set(benchmark["values_w_m2k"]) == {"SE.Zone1", "SE.Zone2", "SE.Zone3"}
    assert set(benchmark["source_locators"]) == set(benchmark["values_w_m2k"])
    actual = catalogue.get(case["archetype_id"], state=case["state"]).construction_set.elements[
        BuildingElement.WINDOW].u_value
    for zone, value in benchmark["values_w_m2k"].items():
        assert benchmark["source_locators"][zone].startswith("TABULA.xlsm#")
        assert value == pytest.approx(expected["u_value"])
        assert actual == pytest.approx(expected["u_value"])
        assert abs(actual - value) / value <= CASE["u_value_relative_tolerance"]
    failures = [finding for finding in report["findings"]
                if finding["rule_id"] in {
                    "tabula.u_value", "tabula.reference_missing", "tabula.calculation",
                }
                and finding.get("expected", {}).get("element") == "WINDOW"
                and any(user["archetype_id"] == case["archetype_id"]
                        and user["state"] == case["state"]
                        for user in finding["affected_archetypes"])]
    assert not failures


def test_every_other_window_assignment_and_shared_definition_is_preserved(payload, catalogue):
    changed = {(case["archetype_id"], case["state"]) for case in CHANGED}
    preserved = set()
    for group in WINDOW["unchanged"]["definition_groups"]:
        for user in group["users"]:
            identifier, state = user["archetype_id"], user["state"]
            key = (identifier, state)
            assert key not in changed
            assert key not in preserved
            preserved.add(key)
            element_id, material_id, material = _window(payload, identifier, state)
            assert element_id == group["element_id"]
            assert material_id == group["material_id"]
            assert material["honeybee_id"] == group["honeybee_id"]
            assert material["properties"] == group["properties"]
    all_configs = {(identifier, state) for identifier, archetype in payload["archetypes"].items()
                   for state in archetype["states"]}
    reviewed = set()
    for case in WINDOW["reviewed_elsewhere"]:
        key = (case["archetype_id"], case["state"])
        assert key not in preserved | changed | reviewed
        reviewed.add(key)
        independent = json.loads((FIXTURE / case["fixture"]).read_text())
        assert independent["archetype_id"] == case["archetype_id"]
        expected = independent
        for name in case["section"].split("."):
            expected = expected[name]
        source_era = independent["era"].removeprefix("SE.")
        assert expected["source_variant"].startswith(f"SE.N.SFH.{source_era}.")
        element_id, material_id, material = _window(payload, *key)
        _assert_simple_glazing(catalogue, material, expected["properties"])
        assert material["boverket_id"] == expected["boverket_id"]
        expected_element = expected.get("shared_element_id", expected.get("element_id"))
        expected_material = expected.get("shared_material_id", expected.get("material_id"))
        if expected_element:
            assert element_id == expected_element
            assert material_id == expected_material
    assert reviewed == {
        ("sf_se01", "existing"), ("sf_se01", "advanced"),
        ("sf_se02", "advanced"), ("sf_se03", "advanced"),
        ("sf_se04", "advanced"), ("sf_se05", "advanced"),
    }
    assert len(preserved) == 57
    assert preserved | changed | reviewed == all_configs
    assert all(key in preserved | reviewed for key in all_configs if key[1] == "advanced")


@pytest.mark.parametrize("case", MF_CHANGED, ids=_case_id)
def test_generic_inherits_corrected_mf_fabric_and_operation(catalogue, case):
    alias = "generic_se" + case["era"].removeprefix("SE.")
    generic = catalogue.get(alias, state=case["state"])
    donor = catalogue.get(case["archetype_id"], state=case["state"])
    assert generic.construction_set is donor.construction_set
    assert generic.operating_profile is donor.operating_profile
    assert generic.construction_year == donor.construction_year


def test_office_se05_renovations_retain_original_year_and_construction_sets(payload, report):
    expected = CASE["office_se05"]
    states = payload["archetypes"]["office_se05"]["states"]
    assert set(states) == set(expected["states"])
    for state, config in states.items():
        assert config["construction_year"] == expected["construction_year"]
        assert config["construction_set_id"] == expected["states"][state]["construction_set_id"]
        floor = config["boundary_details"]["INTERMEDIATE_FLOOR"]
        assert floor["layer_order"] == expected["intermediate_floor_order"]
        assert floor["source_layer_order"] == expected["intermediate_floor_source_order"]
    assert not [finding for finding in report["findings"]
                if finding["rule_id"] == "renovation.construction_year"
                and any(user["archetype_id"] == "office_se05"
                        for user in finding["affected_archetypes"])]
