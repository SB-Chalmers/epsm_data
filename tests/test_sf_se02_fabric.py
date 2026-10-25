"""Independent period geometry, TABULA measures and retained SF SE.02 windows."""

import json
from pathlib import Path

import pytest

from epsm_data import BuildingElement, Catalogue, export_nominal_constructions, load_sanity_fixture

FIXTURE = Path(__file__).parent / "fixtures/catalogue_sanity"
CASE = json.loads((FIXTURE / "cases/sf_se02.json").read_text())
STATES = ("existing", "standard", "advanced")
RENOVATIONS = ("standard", "advanced")


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


def _config(payload, state, identifier="sf_se02"):
    return payload["archetypes"][identifier]["states"][state]


def _element_id(payload, state, role, identifier="sf_se02"):
    config = _config(payload, state, identifier)
    return payload["construction_sets"][config["construction_set_id"]]["elements"][role]


def _layers(payload, element_id):
    return [(slot["layer_id"], payload["layers"][slot["layer_id"]])
            for cid in payload["elements"][element_id]["components"]
            for slot in sorted(payload["components"][cid]["layers"], key=lambda row: row["position"])]


def _snapshot(payload, element_id):
    return [{
        "thickness_m": layer["thickness"],
        "is_composite": layer["is_composite"],
        "materials": [{
            "material_id": row["material_id"],
            "area_fraction": row["area_fraction"],
            "thickness_m": row["thickness"],
            "thermal_properties": {field: payload["materials"][row["material_id"]]["properties"][field]
                                   for field in ("conductivity", "density", "specific_heat")},
        } for row in layer["materials"]],
    } for _, layer in _layers(payload, element_id)]


def _resistance(layers):
    return sum(layer["thickness_m"] / sum(
        row["area_fraction"] * row["thermal_properties"]["conductivity"]
        for row in layer["materials"]
    ) for layer in layers)


def _single(layer, material_id, depth):
    assert layer["thickness"] == depth
    assert not layer["is_composite"]
    assert layer["materials"] == [{
        "material_id": material_id, "area_fraction": 1.0, "thickness": depth,
    }]


def test_sf02_wall_fixture_distinguishes_stock_mean_from_period_layer_evidence():
    wall = CASE["wall"]
    assert wall["source_reference"]["construction_code"] == "SE.Wall.ReEx.02.01"
    assert wall["source_reference"]["link_locator"] == "TABULA.xlsm#Tab.Building!BF810"
    assert wall["source_reference"]["u_w_m2k"] == 0.31
    assert "no physical layer recipe" in wall["source_reference"]["basis"]
    assert "pp39–40" in wall["period_source"]["locator"]
    assert "Figure2222b" in wall["period_source"]["locator"]
    assert wall["main_frame_depth_m"] == 0.1
    assert wall["inside_cross_frame_depth_m"] == 0.05
    assert wall["framing_fraction"] == 0.15


def test_original_wall_adds_windboard_and_retains_the_fixed_cross_frame_core(payload):
    expected = CASE["wall"]
    eid = _element_id(payload, "existing", "EXT_WALL")
    assert _snapshot(payload, eid) == expected["original_layers"]
    layers = _layers(payload, eid)
    assert [layer["thickness"] for _, layer in layers] == [0.012, 0.1, 0.05, 0.013]
    _single(layers[0][1], expected["windboard"]["material_id"], 0.012)
    assert layers[1][0] == expected["retained_main_frame_layer_id"]
    assert layers[3][0] == expected["retained_gypsum_layer_id"]
    assert _snapshot(payload, eid)[1:] == expected["retained_framed_core_layers"]
    for _, layer in layers[1:3]:
        assert layer["is_composite"]
        assert [row["area_fraction"] for row in layer["materials"]] == [0.15, 0.85]
        assert all(row["thickness"] == layer["thickness"] for row in layer["materials"])
    assert len(layers) == 4


@pytest.mark.parametrize("state", STATES)
def test_remaining_cladding_and_cavity_omissions_are_explicit_after_windboard_completion(payload, state):
    details = _config(payload, state)["boundary_details"]["EXT_WALL"]
    assert details["layer_order"] == "outside_to_inside"
    assert details["weather_skin_status"] == CASE["wall"]["weather_skin_status"]
    assert details["weather_skin_status"] == "windboard_quantified_cladding_cavity_unquantified"
    layers = _layers(payload, _element_id(payload, state, "EXT_WALL"))
    assert len(layers) == (4 if state == "existing" else 6)


@pytest.mark.parametrize("state", RENOVATIONS)
def test_sf02_renovations_reuse_sf01_panel_and_actual_45_70mm_wool_package(
    catalogue, payload, state,
):
    wall = CASE["wall"]
    expected = wall["states"][state]
    baseline_id = _element_id(payload, "existing", "EXT_WALL")
    eid = _element_id(payload, state, "EXT_WALL")
    original_components = payload["elements"][baseline_id]["components"]
    assert payload["elements"][eid]["components"] == [
        expected["shared_addition_component_id"], *original_components,
    ]
    assert _snapshot(payload, eid)[2:] == wall["original_layers"]
    layers = _layers(payload, eid)
    assert layers[0][0] == wall["renovation_cladding_layer_id"]
    _single(layers[0][1], wall["renovation_cladding_material_id"], wall["renovation_cladding_depth_m"])
    _single(layers[1][1], wall["renovation_insulation_material_id"], expected["added_insulation_m"])
    sf02 = catalogue.get("sf_se02", state=state).construction_set.elements[BuildingElement.EXT_WALL]
    sf01 = catalogue.get("sf_se01", state=state).construction_set.elements[BuildingElement.EXT_WALL]
    assert sf02.components[0] is sf01.components[0]


@pytest.mark.parametrize("state", STATES)
def test_sf02_wall_is_calculated_forward_and_passes_fixed_zone_benchmarks(
    catalogue, payload, references, state,
):
    wall, expected = CASE["wall"], CASE["wall"]["states"][state]
    reference = next(row for row in references["u_values"] if row["category"] == CASE["category"]
                     and row["era"] == CASE["era"] and row["state"] == state)
    assert reference["elements"]["EXT_WALL"] == expected["tabula"]
    assert references["policy"]["u_value_relative_tolerance"] == CASE["u_value_relative_tolerance"] == 0.2
    actual = catalogue.get("sf_se02", state=state).construction_set.elements[BuildingElement.EXT_WALL]
    resistance = wall["nominal_surface_resistance_m2k_w"] + _resistance(wall["original_layers"])
    if state != "existing":
        resistance += expected["added_insulation_m"] / wall["renovation_insulation_conductivity_w_mk"]
        resistance += wall["renovation_cladding_depth_m"] / wall["retained_framed_core_layers"][0][
            "materials"][0]["thermal_properties"]["conductivity"]
    assert actual.u_value == pytest.approx(1 / resistance, rel=1e-12)
    assert actual.u_value == pytest.approx(expected["expected_u_w_m2k"], rel=1e-12)
    count = len(wall["original_layers"])
    assert _snapshot(payload, _element_id(payload, state, "EXT_WALL"))[-count:] == wall["original_layers"]
    for value in expected["tabula"]["values_w_m2k"].values():
        assert abs(actual.u_value - value) / value <= CASE["u_value_relative_tolerance"]


@pytest.mark.parametrize("state", RENOVATIONS)
def test_sf02_wall_and_window_follow_actual_tabula_measures(references, state):
    package = next(row for row in references["renovation_packages"]
                   if row["category"] == CASE["category"] and row["era"] == CASE["era"]
                   and row["state"] == state)
    wall = CASE["wall"]["states"][state]
    measure = references["measures"][package["measures"]["EXT_WALL"]]
    assert package["source_variant"] == wall["source_variant"]
    assert measure["code"] == wall["measure_code"]
    assert measure["nominal_added_insulation_m"] == wall["added_insulation_m"]
    assert str(wall["measure_row"]) in measure["source_locator"]
    window = references["measures"][package["measures"]["WINDOW"]]
    assert window["code"] == CASE["window"]["states"][state]["measure_code"]
    assert window["window_u_w_m2k"] == pytest.approx(
        CASE["window"]["states"][state]["properties"]["u_value"])


@pytest.mark.parametrize("state", STATES)
def test_sf02_windows_keep_canonical_source_links_and_whole_aperture_optics(
    catalogue, payload, references, state,
):
    expected = CASE["window"]["states"][state]
    eid = _element_id(payload, state, "WINDOW")
    material_id = payload["elements"][eid]["window_material_id"]
    material = payload["materials"][material_id]
    assert eid == expected["element_id"]
    assert material_id == expected["material_id"]
    assert material["honeybee_id"] == expected["honeybee_id"]
    assert material["boverket_id"] == expected["boverket_id"]
    assert material["properties"] == pytest.approx(expected["properties"])
    assert material["properties"]["shgc"] == pytest.approx(
        expected["glazing_g"] * (1 - expected["frame_fraction"]))
    assert material["properties"]["vt"] == pytest.approx(
        expected["glazing_vt_default"] * (1 - expected["frame_fraction"]))
    source = catalogue.honeybee_materials[material["honeybee_id"]]
    assert source["type"] == "EnergyWindowMaterialSimpleGlazSys"
    assert source["u_factor"] == pytest.approx(expected["properties"]["u_value"])
    assert source["shgc"] == pytest.approx(expected["properties"]["shgc"])
    assert source["vt"] == pytest.approx(expected["properties"]["vt"])
    reference = next(row for row in references["u_values"] if row["category"] == CASE["category"]
                     and row["era"] == CASE["era"] and row["state"] == state)["elements"]["WINDOW"]
    assert reference == expected["tabula"]
    for value in reference["values_w_m2k"].values():
        assert material["properties"]["u_value"] == pytest.approx(value)
    if state != "existing":
        donor = catalogue.get(expected["shared_donor_archetype_id"], state=state)
        assert catalogue.get("sf_se02", state=state).construction_set.elements[
            BuildingElement.WINDOW] is donor.construction_set.elements[BuildingElement.WINDOW]


@pytest.mark.parametrize("state", STATES)
def test_sf02_retains_1970_original_year_and_normal_residential_operation(catalogue, payload, state):
    selected = catalogue.get("sf_se02", state=state)
    assert selected.construction_year == CASE["construction_year"] == 1970
    assert _config(payload, state)["construction_year"] == CASE["construction_year"]
    assert selected.operating_profile.to_dict() == catalogue.get("sf_se02").operating_profile.to_dict()
    assert selected.operating_profile.to_dict() == catalogue.get("sf_se01").operating_profile.to_dict()


@pytest.mark.parametrize("state", STATES)
def test_nominal_export_preserves_cross_frame_and_incoming_wall_package(catalogue, payload, state):
    config = _config(payload, state)
    bundle = export_nominal_constructions(
        catalogue.get("sf_se02", state=state), metadata={"boundary_details": config["boundary_details"]},
    )
    expected = _snapshot(payload, _element_id(payload, state, "EXT_WALL"))
    exported = bundle["honeybee"]["EXT_WALL"]["materials"]
    assert [row["thickness"] for row in exported] == [row["thickness_m"] for row in expected]
    assert sum(row["thickness"] / row["conductivity"] for row in exported) == pytest.approx(
        _resistance(expected), rel=1e-12)
    assert bundle["roles"]["EXT_WALL"]["nominal_u_w_m2k"] == pytest.approx(
        CASE["wall"]["states"][state]["expected_u_w_m2k"], rel=1e-12)


def test_sf02_update_keeps_school_wall_and_shared_thermal_grade_properties_unchanged(catalogue, payload):
    guards = CASE["wall_preservation"]
    for state, expected in guards["school_se02_states"].items():
        eid = _element_id(payload, state, "EXT_WALL", "school_se02")
        assert eid == expected["element_id"]
        assert payload["elements"][eid]["components"] == expected["component_ids"]
        assert _snapshot(payload, eid) == expected["layers"]
    for mid, expected in guards["material_records"].items():
        material = payload["materials"][mid]
        assert material["honeybee_id"] == expected["honeybee_id"]
        assert material["boverket_id"] == expected["boverket_id"]
        assert material["properties"] == expected["properties"]
        source = catalogue.honeybee_materials[material["honeybee_id"]]
        assert {key: source[key] for key in material["properties"]} == material["properties"]


def test_reviewed_sf02_has_no_sanity_errors_while_module_limits_remain_visible(report):
    findings = [finding for finding in report["findings"]
                if any(user["archetype_id"] == CASE["archetype_id"]
                       for user in finding["affected_archetypes"])]
    assert not [finding for finding in findings if finding["severity"] == "error"]
    coverage = [finding for finding in findings if finding["rule_id"] == "carbon.modules"]
    assert coverage and all(finding["severity"] == "review" for finding in coverage)
    assert all("A5" in finding["missing_modules"] and "A5.1" in finding["partial_modules"]
               for finding in coverage)


def test_windboard_is_retained_in_all_states_with_unknown_carbon_and_supported_thermal_link(
    catalogue, payload, report,
):
    expected = CASE["wall"]["windboard"]
    baseline_id = _element_id(payload, "existing", "EXT_WALL")
    component_id = payload["elements"][baseline_id]["components"][0]
    slot = payload["components"][component_id]["layers"][0]
    assert slot["layer_function"] == expected["layer_function"] == "wind_barrier"
    assert len(payload["components"][component_id]["layers"]) == 1
    for state in STATES:
        eid = _element_id(payload, state, "EXT_WALL")
        index = 0 if state == "existing" else 1
        assert payload["elements"][eid]["components"][index] == component_id
    material = payload["materials"][expected["material_id"]]
    assert material["properties"] == expected["properties"]
    assert material["boverket_id"] is None
    assert material["carbon_assessment"]["status"] == "retained_existing_unmapped"
    source = catalogue.honeybee_materials[expected["honeybee_id"]]
    assert {key: source[key] for key in material["properties"]} == material["properties"]
    assert expected["thickness_m"] / material["properties"]["conductivity"] == pytest.approx(
        expected["expected_added_resistance_m2k_w"])
    mass = expected["thickness_m"] * material["properties"]["density"]
    assert mass == pytest.approx(expected["expected_added_mass_kg_m2"])
    assert mass * material["properties"]["specific_heat"] == pytest.approx(
        expected["expected_added_heat_capacity_j_m2k"])
    findings = [finding for finding in report["findings"]
                if finding["rule_id"] == "carbon.existing_stock"
                and expected["material_id"] in finding["path"]]
    assert findings and all(finding["severity"] == "review" for finding in findings)
    assert {user["state"] for finding in findings for user in finding["affected_archetypes"]
            if user["archetype_id"] == "sf_se02"} == set(STATES)
