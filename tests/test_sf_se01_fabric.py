"""Source measures and declared period defaults for the SF SE.01 wall and attic."""

import json
from pathlib import Path

import pytest

from epsm_data import BuildingElement, Catalogue, export_nominal_constructions, load_sanity_fixture

FIXTURE = Path(__file__).parent / "fixtures/catalogue_sanity"
CASE = json.loads((FIXTURE / "cases/sf_se01.json").read_text())
STATES = ("existing", "standard", "advanced")
RENOVATIONS = ("standard", "advanced")


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture(scope="module")
def payload(catalogue):
    return catalogue.resolved_dict()


def _config(payload, state, archetype_id="sf_se01"):
    return payload["archetypes"][archetype_id]["states"][state]


def _element_id(payload, state, role, archetype_id="sf_se01"):
    config = _config(payload, state, archetype_id)
    return payload["construction_sets"][config["construction_set_id"]]["elements"][role]


def _layers(payload, element_id):
    return [
        payload["layers"][slot["layer_id"]]
        for cid in payload["elements"][element_id]["components"]
        for slot in sorted(payload["components"][cid]["layers"], key=lambda value: value["position"])
    ]


def _snapshot(payload, element_id):
    return [
        {
            "thickness_m": layer["thickness"],
            "is_composite": layer["is_composite"],
            "materials": [
                {
                    "material_id": row["material_id"],
                    "area_fraction": row["area_fraction"],
                    "thickness_m": row["thickness"],
                    "thermal_properties": {
                        field: payload["materials"][row["material_id"]]["properties"][field]
                        for field in ("conductivity", "density", "specific_heat")
                    },
                }
                for row in layer["materials"]
            ],
        }
        for layer in _layers(payload, element_id)
    ]


def _resistance(layers):
    return sum(
        layer["thickness_m"] / sum(
            row["area_fraction"] * row["thermal_properties"]["conductivity"]
            for row in layer["materials"]
        )
        for layer in layers
    )


def _single_material(payload, layer, material_id, depth):
    assert not layer["is_composite"]
    assert layer["thickness"] == depth
    assert layer["materials"] == [{
        "material_id": material_id, "area_fraction": 1.0, "thickness": depth,
    }]
    return payload["materials"][material_id]


def _source_agrees(catalogue, material):
    source = catalogue.honeybee_materials[material["honeybee_id"]]
    assert {key: source[key] for key in material["properties"]} == material["properties"]


def test_original_wall_reuses_historic_aac_definition_and_keeps_both_plaster_finishes(payload):
    expected = CASE["wall"]
    eid = _element_id(payload, "existing", "EXT_WALL")
    assert eid == expected["baseline_element_id"]
    assert eid == _element_id(payload, "existing", "EXT_WALL", "mf_se01")
    assert payload["elements"][eid]["components"] == expected["baseline_component_ids"]
    assert _snapshot(payload, eid) == expected["baseline_layers"]
    layers = _layers(payload, eid)
    assert [layer["thickness"] for layer in layers] == [
        expected["plaster_depth_each_side_m"], expected["aac_depth_m"],
        expected["plaster_depth_each_side_m"],
    ]
    _single_material(payload, layers[1], expected["aac_material_id"], expected["aac_depth_m"])


@pytest.mark.parametrize("state", RENOVATIONS)
def test_wall_adds_actual_wood_panel_and_facade_board_outside_all_original_aac_components(
    payload, catalogue, state,
):
    expected = CASE["wall"]
    baseline_id = _element_id(payload, "existing", "EXT_WALL")
    renovated_id = _element_id(payload, state, "EXT_WALL")
    baseline = payload["elements"][baseline_id]["components"]
    renovated = payload["elements"][renovated_id]["components"]
    assert renovated[-len(baseline):] == baseline
    layers = _layers(payload, renovated_id)
    assert _snapshot(payload, renovated_id)[2:] == expected["baseline_layers"]
    cladding = _single_material(
        payload, layers[0], expected["cladding_material_id"], expected["cladding_depth_m"],
    )
    insulation = _single_material(
        payload, layers[1], expected["insulation_material_id"],
        expected["states"][state]["added_insulation_m"],
    )
    assert insulation["properties"]["conductivity"] == expected["insulation_conductivity_w_mk"]
    assert insulation["properties"]["density"] == expected["insulation_density_kg_m3"]
    assert insulation["properties"]["specific_heat"] == expected["insulation_specific_heat_j_kgk"]
    assert insulation["boverket_id"] == expected["insulation_boverket_id"]
    for material in (cladding, insulation):
        _source_agrees(catalogue, material)
    details = _config(payload, state)["boundary_details"]["EXT_WALL"]
    assert details["layer_order"] == "outside_to_inside"
    declared = json.dumps(details).casefold()
    assert "ventilat" in declared and "nominal" in declared


def test_original_attic_has_supported_fill_range_and_nominal_joist_geometry(payload):
    expected = CASE["attic"]
    eid = _element_id(payload, "existing", "TOP_FLOOR")
    assert _snapshot(payload, eid) == expected["original_layers"]
    overfill, framed, boards, plaster = _layers(payload, eid)
    assert overfill["thickness"] == expected["overfill_depth_m"]
    assert not overfill["is_composite"]
    assert framed["thickness"] == expected["joist_depth_m"]
    assert framed["is_composite"]
    assert framed["materials"][0]["area_fraction"] == expected["timber_fraction"]
    assert expected["timber_fraction"] == expected["joist_width_m"] / expected["joist_centres_m"]
    assert sum(row["area_fraction"] for row in framed["materials"]) == 1
    assert overfill["thickness"] + framed["thickness"] == expected["total_original_fill_depth_m"]
    assert expected["total_original_fill_depth_m"] == 0.25
    assert boards["thickness"] == 0.022
    assert plaster["thickness"] == 0.015


@pytest.mark.parametrize("state", RENOVATIONS)
def test_attic_adds_existing_shared_loose_wool_component_and_retains_entire_new_baseline(
    payload, catalogue, state,
):
    expected = CASE["attic"]
    baseline_id = _element_id(payload, "existing", "TOP_FLOOR")
    renovated_id = _element_id(payload, state, "TOP_FLOOR")
    baseline = payload["elements"][baseline_id]["components"]
    assert payload["elements"][renovated_id]["components"] == [
        expected["shared_addition_component_ids"][state], *baseline,
    ]
    assert _snapshot(payload, renovated_id)[1:] == expected["original_layers"]
    wool = _single_material(
        payload, _layers(payload, renovated_id)[0], expected["renovation_material_id"],
        expected["states"][state]["added_insulation_m"],
    )
    assert wool["properties"]["conductivity"] == expected["renovation_conductivity_w_mk"]
    assert wool["properties"]["density"] == expected["renovation_density_kg_m3"]
    assert wool["boverket_id"] == expected["renovation_boverket_id"]
    assert wool["carbon_reference_id"] == expected["renovation_carbon_reference_id"]
    _source_agrees(catalogue, wool)
    sf = catalogue.get("sf_se01", state=state).construction_set.elements[BuildingElement.TOP_FLOOR]
    mf = catalogue.get("mf_se01", state=state).construction_set.elements[BuildingElement.TOP_FLOOR]
    assert sf.components[0] is mf.components[0]


@pytest.mark.parametrize("state", STATES)
def test_fabric_uses_fixed_tabula_benchmarks_and_forward_u_values(payload, catalogue, state):
    refs = load_sanity_fixture(FIXTURE)
    reference = next(row for row in refs["u_values"] if row["category"] == "single_family"
                     and row["era"] == "SE.01" and row["state"] == state)
    defaults = CASE["engineering_defaults"]
    assert refs["policy"]["u_value_relative_tolerance"] == defaults["u_value_relative_tolerance"]
    for key, role, target in (("wall", "EXT_WALL", "EXT_WALL"),
                              ("attic", "TOP_FLOOR", "THERMAL_TOP")):
        expected = CASE[key]["states"][state]
        assert reference["elements"][target] == expected["tabula"]
        eid = _element_id(payload, state, role)
        calculated = 1 / (defaults["nominal_surface_resistance_m2k_w"]
                          + _resistance(_snapshot(payload, eid)))
        actual = catalogue.get("sf_se01", state=state).construction_set.elements[BuildingElement(role)]
        assert actual.u_value == pytest.approx(calculated, rel=1e-12)
        assert actual.u_value == pytest.approx(expected["expected_u_w_m2k"], rel=1e-12)
        for benchmark in expected["tabula"]["values_w_m2k"].values():
            assert abs(actual.u_value - benchmark) / benchmark <= defaults["u_value_relative_tolerance"]


@pytest.mark.parametrize("state", RENOVATIONS)
def test_retained_wall_and_attic_follow_actual_package_measures(state):
    refs = load_sanity_fixture(FIXTURE)
    package = next(row for row in refs["renovation_packages"] if row["category"] == "single_family"
                   and row["era"] == "SE.01" and row["state"] == state)
    for key, target in (("wall", "EXT_WALL"), ("attic", "THERMAL_TOP")):
        expected = CASE[key]["states"][state]
        measure = refs["measures"][package["measures"][target]]
        assert measure["code"] == expected["measure_code"]
        assert measure["nominal_added_insulation_m"] == expected["added_insulation_m"]
        assert str(expected["measure_row"]) in measure["source_locator"]


@pytest.mark.parametrize("state", STATES)
def test_era_normal_use_and_separate_weather_roof_are_preserved(payload, catalogue, state):
    config = _config(payload, state)
    assert config["construction_year"] == CASE["construction_year"] == 1950
    assert config["roof_topology"] == CASE["attic"]["roof_topology"] == "cold_attic"
    assert config["weather_shell_element_id"] == CASE["attic"]["weather_shell_element_id"]
    assert config["weather_shell_element_id"] != _element_id(payload, state, "TOP_FLOOR")
    assert config["boundary_details"]["TOP_FLOOR"]["layer_order"] == "outside_to_inside"
    assert (catalogue.get("sf_se01", state=state).operating_profile.to_dict()
            == catalogue.get("sf_se01").operating_profile.to_dict())
    mf = catalogue.get("mf_se01", state=state)
    generic = catalogue.get("generic_se01", state=state)
    assert generic.construction_set is mf.construction_set
    assert generic.operating_profile is mf.operating_profile


@pytest.mark.parametrize("state", STATES)
def test_nominal_export_preserves_all_wall_and_attic_layers_including_cladding(payload, catalogue, state):
    config = _config(payload, state)
    bundle = export_nominal_constructions(
        catalogue.get("sf_se01", state=state), metadata={"boundary_details": config["boundary_details"]},
    )
    for key, role in (("wall", "EXT_WALL"), ("attic", "TOP_FLOOR")):
        original = _snapshot(payload, _element_id(payload, state, role))
        exported = bundle["honeybee"][role]["materials"]
        assert len(exported) == len(original)
        assert [row["thickness"] for row in exported] == [row["thickness_m"] for row in original]
        assert sum(row["thickness"] / row["conductivity"] for row in exported) == pytest.approx(
            _resistance(original), rel=1e-12,
        )
        assert bundle["roles"][role]["nominal_u_w_m2k"] == pytest.approx(
            CASE[key]["states"][state]["expected_u_w_m2k"], rel=1e-12,
        )


def test_existing_school_ceiling_and_shared_material_properties_remain_unchanged(payload):
    expected = CASE["preservation"]
    for state, guard in expected["school_top_states"].items():
        eid = _element_id(payload, state, "TOP_FLOOR", "school_se01")
        assert eid == guard["element_id"]
        assert payload["elements"][eid]["components"] == guard["component_ids"]
        assert _snapshot(payload, eid) == guard["layers"]
    for mid, guard in expected["material_properties"].items():
        actual = payload["materials"][mid]
        for field in ("honeybee_id", "boverket_id", "properties"):
            assert actual[field] == guard[field]
