"""Independent late-era representative recipes, fixed TABULA references and shared grades."""

import json
from pathlib import Path

import pytest

from epsm_data import BuildingElement, Catalogue, export_nominal_constructions, load_sanity_fixture

FIXTURE = Path(__file__).parent / "fixtures/catalogue_sanity"
CASES = tuple(json.loads((FIXTURE / f"cases/sf_se{era:02}.json").read_text()) for era in (4, 5))
STATES = ("existing", "standard", "advanced")
ROLE_KEYS = {"EXT_WALL": "wall", "TOP_FLOOR": "attic", "GROUND_FLOOR": "floor"}


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


def _config(payload, case, state):
    return payload["archetypes"][case["archetype_id"]]["states"][state]


def _element_id(payload, case, state, role):
    cfg = _config(payload, case, state)
    return payload["construction_sets"][cfg["construction_set_id"]]["elements"][role]


def _layers(payload, eid):
    return [(slot["layer_id"], payload["layers"][slot["layer_id"]])
            for cid in payload["elements"][eid]["components"]
            for slot in sorted(payload["components"][cid]["layers"], key=lambda row: row["position"])]


def _snapshot(payload, eid):
    return [{"thickness_m": layer["thickness"], "is_composite": layer["is_composite"],
             "materials": [{"material_id": row["material_id"],
                            "area_fraction": row["area_fraction"],
                            "thickness_m": row["thickness"],
                            "thermal_properties": {key: payload["materials"][row["material_id"]][
                                "properties"][key] for key in ("conductivity", "density", "specific_heat")}}
                           for row in layer["materials"]]}
            for _, layer in _layers(payload, eid)]


def _single(payload, mid, depth):
    return {"thickness_m": depth, "is_composite": False, "materials": [{
        "material_id": mid, "area_fraction": 1.0, "thickness_m": depth,
        "thermal_properties": {key: payload["materials"][mid]["properties"][key]
                               for key in ("conductivity", "density", "specific_heat")},
    }]}


def _expected_layers(payload, case, state, role):
    expected = case[ROLE_KEYS[role]]
    baseline = expected["baseline_layers" if role == "GROUND_FLOOR" else "original_layers"]
    if state == "existing":
        return baseline
    depth = expected["states"][state]["added_insulation_m"]
    if role == "EXT_WALL":
        return [_single(payload, expected["renovation_panel_material_id"], .022),
                _single(payload, expected["renovation_insulation_material_id"], depth), *baseline]
    if role == "TOP_FLOOR":
        return [_single(payload, expected["renovation_insulation_material_id"], depth), *baseline]
    return [*baseline, _single(payload, expected["new_eps_material_id"], depth),
            _single(payload, expected["finish_material_id"], .05)]


def _resistance(layers):
    return sum(layer["thickness_m"] / sum(row["area_fraction"] * row["thermal_properties"][
        "conductivity"] for row in layer["materials"]) for layer in layers)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["archetype_id"])
def test_period_sources_keep_nominal_defaults_distinct_from_stock_means(case):
    assert "no layer recipe" in case["sources"]["scope"]
    assert case["wall"]["inside_cross_frame_layer_id"] == "layer:02be60731d729b92"
    assert "not this70mm selection" in case["wall"]["history_scope"]
    assert case["wall"]["timber_fraction_each_framed_layer"] == .15
    assert case["attic"]["joist_width_m"] / case["attic"]["joist_centres_m"] == .0625
    assert case["attic"]["timber_fraction"] == .0625
    assert case["attic"]["framed_depth_m"] == .2
    assert case["attic"]["continuous_original_wool_m"] == .1
    assert case["u_value_relative_tolerance"] == .2


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["archetype_id"])
@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("role", ROLE_KEYS)
def test_nominal_physical_layers_and_forward_export_match_independent_recipe(
    catalogue, payload, case, state, role,
):
    eid = _element_id(payload, case, state, role)
    expected = _expected_layers(payload, case, state, role)
    assert _snapshot(payload, eid) == expected
    bundle = export_nominal_constructions(catalogue.get(case["archetype_id"], state=state),
                                          metadata=_config(payload, case, state))
    nominal = bundle["roles"][role]
    assert nominal["resistance_m2k_w"] == pytest.approx(_resistance(expected), rel=1e-12)
    assert nominal["nominal_u_w_m2k"] == pytest.approx(
        1 / (case["nominal_surface_resistance_m2k_w"] + _resistance(expected)), rel=1e-12)
    if role != "GROUND_FLOOR":
        assert nominal["nominal_u_w_m2k"] == pytest.approx(
            case[ROLE_KEYS[role]]["states"][state]["expected_u_w_m2k"], rel=1e-12)
    else:
        mass = sum(row["area_fraction"] * row["thickness_m"] * row["thermal_properties"]["density"]
                   for layer in expected for row in layer["materials"])
        capacity = sum(row["area_fraction"] * row["thickness_m"] * row["thermal_properties"][
            "density"] * row["thermal_properties"]["specific_heat"]
                       for layer in expected for row in layer["materials"])
        assert nominal["mass_kg_m2"] == pytest.approx(mass)
        assert nominal["heat_capacity_j_m2k"] == pytest.approx(capacity)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["archetype_id"])
@pytest.mark.parametrize("state", STATES)
def test_fixed_source_benchmarks_and_actual_renovation_measures_are_preserved(
    catalogue, references, case, state,
):
    source = next(row for row in references["u_values"] if (row["category"], row["era"], row[
        "state"]) == (case["category"], case["era"], state))
    for role, key in ROLE_KEYS.items():
        reference_role = "THERMAL_TOP" if role == "TOP_FLOOR" else role
        assert source["elements"][reference_role] == case[key]["states"][state]["tabula"]
        if role != "GROUND_FLOOR":
            actual = catalogue.get(case["archetype_id"], state=state).construction_set.elements[
                BuildingElement(role)].u_value
            assert all(abs(actual / value - 1) <= .2 for value in source["elements"][
                reference_role]["values_w_m2k"].values())
    assert source["elements"]["WINDOW"] == case["window"]["states"][state]["tabula"]
    assert references["policy"]["u_value_relative_tolerance"] == .2
    if state != "existing":
        package = next(row for row in references["renovation_packages"] if (
            row["category"], row["era"], row["state"]) == (case["category"], case["era"], state))
        for role, key in ROLE_KEYS.items():
            source_role = "THERMAL_TOP" if role == "TOP_FLOOR" else role
            measure = references["measures"][package["measures"][source_role]]
            assert measure["nominal_added_insulation_m"] == case[key]["states"][state][
                "added_insulation_m"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["archetype_id"])
@pytest.mark.parametrize("state", STATES)
def test_shared_packages_keep_originals_and_project_limits_visible(catalogue, payload, report, case, state):
    wall = payload["elements"][_element_id(payload, case, state, "EXT_WALL")]
    original_wall = payload["elements"][_element_id(payload, case, "existing", "EXT_WALL")]
    assert original_wall["components"][0] == case["wall"]["windboard_component_id"]
    assert _config(payload, case, state)["boundary_details"]["EXT_WALL"]["weather_skin_status"] == (
        "windboard_quantified_cladding_cavity_unquantified")
    if state != "existing":
        assert wall["components"] == [case["wall"][f"{state}_addition_component_id"],
                                      *original_wall["components"]]
        floor = payload["elements"][_element_id(payload, case, state, "GROUND_FLOOR")]
        baseline = payload["elements"][_element_id(payload, case, "existing", "GROUND_FLOOR")]
        assert floor["components"][:len(baseline["components"])] == baseline["components"]
        assert floor["components"][-1] == case["floor"]["floating_finish_component_id"]
        attic = catalogue.get(case["archetype_id"], state=state).construction_set.elements[
            BuildingElement.TOP_FLOOR]
        donor = catalogue.get("sf_se03", state=state).construction_set.elements[BuildingElement.TOP_FLOOR]
        assert attic.components[0] is donor.components[0]
    assert _config(payload, case, state)["construction_year"] == case["construction_year"]
    ground = _config(payload, case, state)["boundary_details"]["GROUND_FLOOR"]
    assert ground["physical_boundary"] == "soil"
    assert ground["value_meaning"] == "nominal_material_layers_not_effective_ground_u"
    findings = [row for row in report["findings"] if any(u["archetype_id"] == case["archetype_id"]
                and u["state"] == state for u in row["affected_archetypes"])]
    assert any(row["rule_id"] == "tabula.boundary_not_assessed" and row["actual"].get(
        "element") == "GROUND_FLOOR" for row in findings)
    assert not [row for row in findings if row["severity"] == "error"]
    coverage = [row for row in findings if row["rule_id"] == "carbon.modules"]
    assert coverage and all(row["severity"] == "review" for row in coverage)
    assert all("A5" in row["missing_modules"] and "A5.1" in row["partial_modules"]
               for row in coverage)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["archetype_id"])
@pytest.mark.parametrize("state", STATES)
def test_window_references_and_native_simple_glazing_stay_consistent(catalogue, payload, case, state):
    expected = case["window"]["states"][state]
    eid = _element_id(payload, case, state, "WINDOW")
    assert eid == expected["element_id"]
    mid = payload["elements"][eid]["window_material_id"]
    assert mid == expected["material_id"]
    material = payload["materials"][mid]
    assert material["properties"] == expected["properties"]
    assert material["honeybee_id"] == expected["honeybee_id"]
    assert material["boverket_id"] == expected["boverket_id"]
    hb = catalogue.honeybee_materials[material["honeybee_id"]]
    assert hb["u_factor"] == pytest.approx(material["properties"]["u_value"])
    assert hb["shgc"] == pytest.approx(material["properties"]["shgc"])
    assert hb["vt"] == pytest.approx(material["properties"]["vt"])
    assert all(abs(material["properties"]["u_value"] / value - 1) <= .2
               for value in expected["tabula"]["values_w_m2k"].values())
    if state != "existing":
        selected = catalogue.get(case["archetype_id"], state=state).construction_set.elements[
            BuildingElement.WINDOW]
        donor = catalogue.get("mf_se01", state=state).construction_set.elements[BuildingElement.WINDOW]
        assert selected is donor


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["archetype_id"])
def test_shared_school_assignments_and_material_properties_are_preserved(payload, catalogue, case):
    guard = case["preservation"]
    for state, roles in guard["school_states"].items():
        cfg = payload["archetypes"][guard["school_archetype_id"]]["states"][state]
        actual = payload["construction_sets"][cfg["construction_set_id"]]["elements"]
        for role, expected in roles.items():
            assert actual[role] == expected["element_id"]
            assert _snapshot(payload, actual[role]) == expected["layers"]
    for mid, expected in guard["material_records"].items():
        material = payload["materials"][mid]
        assert {key: material.get(key) for key in expected} == expected
        hb = catalogue.honeybee_materials[expected["honeybee_id"]]
        assert {key: hb[key] for key in material["properties"]} == material["properties"]
