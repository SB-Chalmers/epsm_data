"""Forward checks for the declared SF SE.02 slab and source renovation measures."""

import json
from pathlib import Path

import pytest

from epsm_data import Catalogue, export_nominal_constructions, load_sanity_fixture

FIXTURES = Path(__file__).parent / "fixtures/catalogue_sanity"
CASE = json.loads((FIXTURES / "cases/sf_se02.json").read_text())
FLOOR = CASE["floor"]
STATES = ("existing", "standard", "advanced")


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture(scope="module")
def payload(catalogue):
    return catalogue.resolved_dict()


@pytest.fixture(scope="module")
def report(catalogue):
    return catalogue.sanity_report(fixture=FIXTURES)


def _config(payload, state):
    return payload["archetypes"]["sf_se02"]["states"][state]


def _floor(payload, state):
    construction = payload["construction_sets"][_config(payload, state)["construction_set_id"]]
    return payload["elements"][construction["elements"]["GROUND_FLOOR"]]


def _layers(payload, state):
    return [payload["layers"][slot["layer_id"]]
            for cid in _floor(payload, state)["components"]
            for slot in sorted(payload["components"][cid]["layers"],
                               key=lambda row: row["position"])]


def _expected_layers(state):
    layers = list(FLOOR["baseline_layers"])
    if state != "existing":
        layers += [
            {"material": "insulation",
             "thickness_m": FLOOR["states"][state]["added_insulation_m"]},
            {"material": "finish", "thickness_m": FLOOR["assembly_defaults"][
                "floating_finish_thickness_m"]},
        ]
    return layers


def _expected_metrics(state):
    """Compute from independently declared grades and dimensions, never accepted U."""
    layers = [(row["thickness_m"], FLOOR["materials"][row["material"]])
              for row in _expected_layers(state)]
    resistance = sum(depth / material["conductivity_w_mk"] for depth, material in layers)
    return {
        "thickness_m": sum(depth for depth, _ in layers),
        "resistance_m2k_w": resistance,
        "mass_kg_m2": sum(depth * material["density_kg_m3"] for depth, material in layers),
        "heat_capacity_j_m2k": sum(depth * material["density_kg_m3"]
                                   * material["specific_heat_j_kgk"]
                                   for depth, material in layers),
        "nominal_u_w_m2k": 1 / (resistance + FLOOR["assembly_defaults"][
            "surface_resistance_m2k_w"]),
    }


@pytest.mark.parametrize("state", STATES)
def test_slab_and_warm_side_renovation_match_declared_independent_stack(payload, state):
    actual = _layers(payload, state)
    expected = _expected_layers(state)
    assert len(actual) == len(expected)
    for layer, row in zip(actual, expected, strict=True):
        assert not layer["is_composite"]
        assert layer["thickness"] == row["thickness_m"]
        material = FLOOR["materials"][row["material"]]
        assert layer["materials"] == [{
            "material_id": material["material_id"], "area_fraction": 1.0,
            "thickness": row["thickness_m"],
        }]
    baseline = _floor(payload, "existing")["components"]
    assert _floor(payload, state)["components"][:len(baseline)] == baseline
    for layer, original in zip(actual, _layers(payload, "existing"), strict=False):
        assert layer is original
    assert _config(payload, state)["construction_year"] == CASE["construction_year"]
    boundary = _config(payload, state)["boundary_details"]["GROUND_FLOOR"]
    for key, value in FLOOR["boundary"].items():
        assert boundary[key] == value
    project_inputs = " ".join(boundary["project_inputs"]).casefold()
    assert all(term in project_inputs for term in ("moisture", "reinforcement", "load", "clearances"))
    if state != "existing":
        assert boundary["floor_rise_m"] == FLOOR["states"][state]["floor_rise_m"]
        assert "proxy" in boundary["finish_scope"].casefold()


def test_shared_grades_keep_exact_honeybee_properties_and_concrete_carbon_proxy(catalogue, payload):
    for grade in FLOOR["materials"].values():
        material = payload["materials"][grade["material_id"]]
        assert material["honeybee_id"] == grade["honeybee_id"]
        assert material["boverket_id"] == grade["boverket_id"]
        for property_name, fixture_name in (("conductivity", "conductivity_w_mk"),
                                            ("density", "density_kg_m3"),
                                            ("specific_heat", "specific_heat_j_kgk")):
            assert material["properties"][property_name] == grade[fixture_name]
        source = catalogue.honeybee_materials[grade["honeybee_id"]]
        assert {key: source[key] for key in material["properties"]} == material["properties"]
    finish = FLOOR["materials"]["finish"]
    density = next(row["Value"] for row in payload["boverket"][finish["boverket_id"]][
        "Conversions"] if row["Field"] == "Volume" and row["Unit"] == "kg/m³")
    assert abs(finish["density_kg_m3"] - density) / density == pytest.approx(110 / 2350)


@pytest.mark.parametrize("state", STATES)
def test_exported_floor_resistance_mass_and_heat_capacity_follow_independent_forward_values(
    catalogue, payload, state,
):
    bundle = export_nominal_constructions(catalogue.get("sf_se02", state=state),
                                          metadata=_config(payload, state))
    actual = bundle["roles"]["GROUND_FLOOR"]
    for key, value in _expected_metrics(state).items():
        assert actual[key] == pytest.approx(value, rel=1e-12)
    hb = bundle["honeybee"]["GROUND_FLOOR"]
    assert sum(row["thickness"] / row["conductivity"] for row in hb["materials"]) == (
        pytest.approx(actual["resistance_m2k_w"]))
    assert actual["rsi_m2k_w"] + actual["rse_m2k_w"] == pytest.approx(0.17)
    assert actual["nominal_u_w_m2k"] != pytest.approx(
        FLOOR["states"][state]["workbook_output_u_w_m2k"])
    assert catalogue.completeness("sf_se02", state=state)["complete"]


def test_independent_tabula_measures_keep_original_ground_u_distinct_from_nominal_construction():
    references = load_sanity_fixture(FIXTURES)
    for state, expected in FLOOR["states"].items():
        benchmark = next(row for row in references["u_values"]
                         if (row["category"], row["era"], row["state"])
                         == ("single_family", "SE.02", state))
        assert all(value == pytest.approx(expected["workbook_output_u_w_m2k"])
                   for value in benchmark["elements"]["GROUND_FLOOR"]["values_w_m2k"].values())
        measure_r = 0
        if state != "existing":
            package = next(row for row in references["renovation_packages"]
                           if (row["category"], row["era"], row["state"])
                           == ("single_family", "SE.02", state))
            measure = references["measures"][package["measures"]["GROUND_FLOOR"]]
            assert measure["code"] == expected["measure_code"]
            assert measure["nominal_added_insulation_m"] == expected["added_insulation_m"]
            assert str(expected["source_variant_row"]) in package["source_locator"]
            assert expected["measure_locator"]
            measure_r = expected["added_insulation_m"] / FLOOR["materials"]["insulation"][
                "conductivity_w_mk"]
        # This reproduces the source workbook only, not an accepted floor U target.
        assert expected["workbook_output_u_w_m2k"] == pytest.approx(
            1 / (1 / FLOOR["source"]["input_u_w_m2k"] + measure_r))
    assert FLOOR["source"]["input_u_locator"] and FLOOR["source"]["betsi_locators"]


@pytest.mark.parametrize("state", STATES)
def test_effective_ground_u_remains_unassessed_after_measure_and_boundary_correction(report, state):
    findings = [row for row in report["findings"] if any(
        user["archetype_id"] == "sf_se02" and user["state"] == state
        for user in row["affected_archetypes"])]
    assert any(row["rule_id"] == "tabula.boundary_not_assessed"
               and row["actual"]["element"] == "GROUND_FLOOR" for row in findings)
    assert not any(row["rule_id"] == "tabula.u_value"
                   and row["expected"]["element"] == "GROUND_FLOOR" for row in findings)
    if state != "existing":
        assert not any(row["rule_id"].startswith("tabula.measure_")
                       and row["expected"].get("code") == FLOOR["states"][state]["measure_code"]
                       for row in findings)


def test_renovations_raise_the_floor_and_improve_nominal_performance(catalogue, payload):
    metrics = {state: export_nominal_constructions(catalogue.get("sf_se02", state=state),
                                                   metadata=_config(payload, state))[
        "roles"]["GROUND_FLOOR"] for state in STATES}
    baseline, standard, advanced = (metrics[state] for state in STATES)
    assert advanced["nominal_u_w_m2k"] < standard["nominal_u_w_m2k"] < baseline[
        "nominal_u_w_m2k"]
    for state in ("standard", "advanced"):
        actual = metrics[state]
        assert actual["thickness_m"] - baseline["thickness_m"] == pytest.approx(
            FLOOR["states"][state]["floor_rise_m"])
        assert actual["mass_kg_m2"] > baseline["mass_kg_m2"]
        assert actual["heat_capacity_j_m2k"] > baseline["heat_capacity_j_m2k"]
