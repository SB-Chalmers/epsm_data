"""Independent source measures and retained fabric for the residential quick fixes."""

import json
from pathlib import Path

import pytest

from epsm_data import BuildingElement, Catalogue, load_sanity_fixture

FIXTURE = Path(__file__).parent / "fixtures/catalogue_sanity"
CASE = json.loads((FIXTURE / "cases/tabula_quick_fixes.json").read_text())
TOP_CASES = CASE["top_cases"]
WALL_CASES = CASE["wall_cases"]


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture(scope="module")
def payload(catalogue):
    return catalogue.resolved_dict()


@pytest.fixture(scope="module")
def report(catalogue):
    return catalogue.sanity_report(fixture=FIXTURE)


def _case_id(case):
    return f"{case['archetype_id']}:{case['state']}"


def _config(payload, identifier, state):
    return payload["archetypes"][identifier]["states"][state]


def _element_id(payload, identifier, state, role):
    config = _config(payload, identifier, state)
    return payload["construction_sets"][config["construction_set_id"]]["elements"][role]


def _layers(payload, element_id):
    return [
        payload["layers"][slot["layer_id"]]
        for component in payload["elements"][element_id]["components"]
        for slot in sorted(payload["components"][component]["layers"],
                           key=lambda value: value["position"])
    ]


def _snapshot(payload, element_id):
    return [
        {
            "thickness_m": layer["thickness"],
            "is_composite": layer["is_composite"],
            "materials": [
                {
                    "material_id": material["material_id"],
                    "area_fraction": material["area_fraction"],
                    "thickness_m": material["thickness"],
                    "thermal_properties": {
                        field: payload["materials"][material["material_id"]]["properties"][field]
                        for field in ("conductivity", "density", "specific_heat")
                    },
                }
                for material in layer["materials"]
            ],
        }
        for layer in _layers(payload, element_id)
    ]


def _baseline_resistance(case):
    return sum(
        layer["thickness_m"] / sum(
            material["area_fraction"] * material["thermal_properties"]["conductivity"]
            for material in layer["materials"]
        )
        for layer in case["baseline_layers"]
    )


def _material(payload, layer, expected_id):
    assert not layer["is_composite"]
    assert layer["materials"] == [{
        "material_id": expected_id, "area_fraction": 1.0, "thickness": layer["thickness"],
    }]
    return payload["materials"][expected_id]


def _affected_findings(report, case):
    return [
        finding for finding in report["findings"]
        if any(user["archetype_id"] == case["archetype_id"] and user["state"] == case["state"]
               for user in finding["affected_archetypes"])
    ]


def test_fixture_covers_exactly_selected_roof_and_wall_packages():
    assert len(TOP_CASES) == 18
    assert {case["archetype_id"] for case in TOP_CASES} == {
        *(f"sf_se{era:02d}" for era in range(1, 6)),
        *(f"mf_se{era:02d}" for era in range(2, 6)),
    }
    assert len(WALL_CASES) == 8
    assert {case["archetype_id"] for case in WALL_CASES} == {
        f"mf_se{era:02d}" for era in range(2, 6)
    }
    assert {case["state"] for case in (*TOP_CASES, *WALL_CASES)} == {"standard", "advanced"}
    assert CASE["u_value_relative_tolerance"] == 0.2


@pytest.mark.parametrize("case", TOP_CASES, ids=_case_id)
def test_thermal_top_adds_shared_source_depth_outside_unchanged_cold_attic_floor(
    catalogue, payload, case,
):
    identifier, state = case["archetype_id"], case["state"]
    role, measure = BuildingElement.TOP_FLOOR, CASE["top_measure"]
    baseline = catalogue.get(identifier).construction_set.elements[role]
    renovated = catalogue.get(identifier, state=state).construction_set.elements[role]
    baseline_id = _element_id(payload, identifier, "existing", role.value)
    renovated_id = _element_id(payload, identifier, state, role.value)
    assert baseline_id == case["baseline_element_id"]
    assert payload["elements"][baseline_id]["components"] == case["baseline_component_ids"]
    assert _snapshot(payload, baseline_id) == case["baseline_layers"]
    assert baseline.u_value == pytest.approx(case["baseline_u_w_m2k"], rel=1e-12)
    addition = measure["shared_addition_component_ids"][state]
    assert payload["elements"][renovated_id]["components"] == [
        addition, *case["baseline_component_ids"],
    ]
    assert renovated.components[0] is catalogue.components[addition]
    assert len(renovated.components) == len(baseline.components) + 1
    assert all(current is retained for current, retained in zip(
        renovated.components[1:], baseline.components,
    ))
    layers = _layers(payload, renovated_id)
    assert layers[0]["thickness"] == case["added_insulation_m"]
    assert case["added_insulation_m"] == measure["added_insulation_m"][state]
    wool = _material(payload, layers[0], measure["material_id"])
    assert wool["properties"] == measure["properties"]
    assert wool["honeybee_id"] == measure["honeybee_id"]
    assert wool["boverket_id"] == measure["boverket_id"]
    assert wool["carbon_reference_id"] == measure["carbon_reference_id"]
    for variant in ("existing", "standard", "advanced"):
        metadata = _config(payload, identifier, variant)
        assert metadata["roof_topology"] == case["roof_topology"] == "cold_attic"
        assert metadata["weather_shell_element_id"] == case["weather_shell_element_id"]
    assert _config(payload, identifier, state)["boundary_details"][role.value][
        "layer_order"] == "outside_to_inside"


@pytest.mark.parametrize("case", WALL_CASES, ids=_case_id)
def test_mf_wall_reuses_actual_brick_package_outside_unchanged_baseline(catalogue, payload, case):
    identifier, state = case["archetype_id"], case["state"]
    role, measure = BuildingElement.EXT_WALL, CASE["wall_measure"]
    baseline = catalogue.get(identifier).construction_set.elements[role]
    renovated = catalogue.get(identifier, state=state).construction_set.elements[role]
    baseline_id = _element_id(payload, identifier, "existing", role.value)
    renovated_id = _element_id(payload, identifier, state, role.value)
    assert baseline_id == case["baseline_element_id"]
    assert payload["elements"][baseline_id]["components"] == case["baseline_component_ids"]
    assert _snapshot(payload, baseline_id) == case["baseline_layers"]
    assert baseline.u_value == pytest.approx(case["baseline_u_w_m2k"], rel=1e-12)
    addition = measure["shared_addition_component_ids"][state]
    assert payload["elements"][renovated_id]["components"] == [
        addition, *case["baseline_component_ids"],
    ]
    assert renovated.components[0] is catalogue.components[addition]
    assert len(renovated.components) == len(baseline.components) + 1
    assert all(current is retained for current, retained in zip(
        renovated.components[1:], baseline.components,
    ))
    layers = _layers(payload, renovated_id)
    assert layers[0]["thickness"] == measure["brick_thickness_m"] == 0.12
    brick = _material(payload, layers[0], measure["brick_material_id"])
    assert brick["properties"] == measure["brick_properties"]
    assert layers[1]["thickness"] == case["added_insulation_m"]
    assert case["added_insulation_m"] == measure["added_insulation_m"][state]
    wool = _material(payload, layers[1], measure["insulation_material_id"])
    assert wool["properties"] == measure["insulation_properties"]
    assert _config(payload, identifier, state)["boundary_details"][role.value][
        "layer_order"] == "outside_to_inside"


@pytest.mark.parametrize("case", TOP_CASES, ids=_case_id)
def test_thermal_top_forward_u_and_source_acceptance_keep_two_original_fabric_disagreements(
    catalogue, report, case,
):
    measure = CASE["top_measure"]
    resistance = (_baseline_resistance(case)
                  + case["added_insulation_m"] / measure["properties"]["conductivity"]
                  + CASE["nominal_surface_resistance_m2k_w"])
    actual = catalogue.get(case["archetype_id"], state=case["state"]).construction_set.elements[
        BuildingElement.TOP_FLOOR].u_value
    assert actual == pytest.approx(1 / resistance, rel=1e-12)
    assert actual == pytest.approx(case["expected_u_w_m2k"], rel=1e-12)
    assert actual < case["baseline_u_w_m2k"]
    passed = abs(actual / case["tabula_u_w_m2k"] - 1) <= CASE["u_value_relative_tolerance"]
    assert passed is case["expected_tabula_u_pass"]
    affected = _affected_findings(report, case)
    failures = [finding for finding in affected if finding["rule_id"] == "tabula.u_value"
                and finding["expected"]["element"] == "THERMAL_TOP"]
    assert len(failures) == (0 if case["expected_tabula_u_pass"] else 1)
    assert all(finding["severity"] == "error" for finding in failures)
    assert not any(finding["rule_id"] == "tabula.measure_thickness"
                   and finding["expected"].get("code", "").startswith("SE.Ceiling.")
                   for finding in affected)


@pytest.mark.parametrize("case", WALL_CASES, ids=_case_id)
def test_mf_wall_forward_u_agrees_with_matching_tabula_package(catalogue, report, case):
    measure = CASE["wall_measure"]
    resistance = (_baseline_resistance(case)
                  + measure["brick_thickness_m"] / measure["brick_properties"]["conductivity"]
                  + case["added_insulation_m"] / measure["insulation_properties"]["conductivity"]
                  + CASE["nominal_surface_resistance_m2k_w"])
    actual = catalogue.get(case["archetype_id"], state=case["state"]).construction_set.elements[
        BuildingElement.EXT_WALL].u_value
    assert actual == pytest.approx(1 / resistance, rel=1e-12)
    assert actual == pytest.approx(case["expected_u_w_m2k"], rel=1e-12)
    assert actual < case["baseline_u_w_m2k"]
    assert case["expected_tabula_u_pass"] is True
    assert abs(actual / case["tabula_u_w_m2k"] - 1) <= CASE["u_value_relative_tolerance"]
    affected = _affected_findings(report, case)
    assert not any(finding["rule_id"] == "tabula.u_value"
                   and finding["expected"]["element"] == "EXT_WALL" for finding in affected)
    assert not any(finding["rule_id"] in {"tabula.measure_thickness", "tabula.measure_finish"}
                   and finding["expected"].get("code", "").startswith("SE.Wall.")
                   and "brick" in finding["expected"]["code"] for finding in affected)


def test_top_and_wall_fixture_targets_keep_matching_source_values_and_locators():
    references = load_sanity_fixture(FIXTURE)
    for role, cases, category in (("THERMAL_TOP", TOP_CASES, None),
                                  ("EXT_WALL", WALL_CASES, "multi_family")):
        for case in cases:
            kind = category or ("single_family" if case["archetype_id"].startswith("sf_")
                                else "multi_family")
            reference = next(row for row in references["u_values"] if (
                row["category"], row["era"], row["state"]
            ) == (kind, case["era"], case["state"]))["elements"][role]
            assert all(value == case["tabula_u_w_m2k"]
                       for value in reference["values_w_m2k"].values())
            assert reference["source_locators"] == case["tabula_source_locators"]
    failures = {(case["archetype_id"], case["state"]) for case in TOP_CASES
                if not case["expected_tabula_u_pass"]}
    assert failures == {(case["archetype_id"], case["state"])
                        for case in CASE["retained_top_failures"]}
    assert failures == set()


def test_mf_se02_existing_cavity_stays_behind_retained_brick_after_two_new_layers(payload):
    expected = CASE["mf_se02_facade_cavity"]
    original = _config(payload, "mf_se02", "existing")["boundary_details"]["EXT_WALL"]
    assert original["facade_cavity"] == expected["baseline"]
    for state in ("standard", "advanced"):
        boundary = _config(payload, "mf_se02", state)["boundary_details"]["EXT_WALL"]
        cavity = boundary["facade_cavity"]
        assert cavity["after_layer"] == expected["renovation_after_layer"] == 3
        assert cavity["ventilation"] == expected["renovation_ventilation"]
        assert cavity["nominal_projection"] == expected["renovation_nominal_projection"]
        layers = _layers(payload, _element_id(payload, "mf_se02", state, "EXT_WALL"))
        original_layers = _layers(payload, _element_id(payload, "mf_se02", "existing", "EXT_WALL"))
        assert layers[cavity["after_layer"] - 1] is original_layers[0]
