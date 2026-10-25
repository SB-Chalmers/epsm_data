"""SF SE.02 attic source measures, nominal geometry and shared-definition guards."""

import json
from pathlib import Path

import pytest

from epsm_data import BuildingElement, Catalogue, export_nominal_constructions, load_sanity_fixture

FIXTURE = Path(__file__).parent / "fixtures/catalogue_sanity"
CASE = json.loads((FIXTURE / "cases/sf_se02.json").read_text())
ATTIC = CASE["attic"]
STATES = ("existing", "standard", "advanced")


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture(scope="module")
def payload(catalogue):
    return catalogue.resolved_dict()


def _config(payload, state, archetype_id="sf_se02"):
    return payload["archetypes"][archetype_id]["states"][state]


def _top_id(payload, state, archetype_id="sf_se02"):
    config = _config(payload, state, archetype_id)
    return payload["construction_sets"][config["construction_set_id"]]["elements"]["TOP_FLOOR"]


def _layers(payload, element_id):
    return [
        payload["layers"][slot["layer_id"]]
        for cid in payload["elements"][element_id]["components"]
        for slot in sorted(payload["components"][cid]["layers"], key=lambda row: row["position"])
    ]


def _snapshot(payload, element_id):
    return [
        {
            "thickness_m": layer["thickness"], "is_composite": layer["is_composite"],
            "materials": [
                {
                    "material_id": row["material_id"], "area_fraction": row["area_fraction"],
                    "thickness_m": row["thickness"], "thermal_properties": {
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


def _single(payload, layer, material_id, depth):
    assert not layer["is_composite"]
    assert layer["thickness"] == depth
    assert layer["materials"] == [{
        "material_id": material_id, "area_fraction": 1.0, "thickness": depth,
    }]
    return payload["materials"][material_id]


def _assert_source(catalogue, material):
    source = catalogue.honeybee_materials[material["honeybee_id"]]
    assert {key: source[key] for key in material["properties"]} == material["properties"]


def test_original_attic_combines_period_depth_with_declared_regular_framing(payload, catalogue):
    eid = _top_id(payload, "existing")
    assert _snapshot(payload, eid) == ATTIC["original_layers"]
    continuous, framed, boards, gypsum = _layers(payload, eid)
    wool = _single(
        payload, continuous, ATTIC["wool_material_id"], ATTIC["continuous_wool_depth_m"],
    )
    assert framed["is_composite"]
    assert framed["thickness"] == ATTIC["framed_depth_m"] == 0.15
    assert framed["materials"][0]["area_fraction"] == ATTIC["timber_fraction"]
    assert ATTIC["timber_fraction"] == ATTIC["joist_width_m"] / ATTIC["joist_centres_m"]
    assert ATTIC["timber_fraction"] == 0.0625
    assert sum(row["area_fraction"] for row in framed["materials"]) == 1
    assert continuous["thickness"] + framed["thickness"] == ATTIC["total_original_insulation_depth_m"]
    assert ATTIC["total_original_insulation_depth_m"] == 0.18
    assert boards["thickness"] == 0.022
    assert gypsum["thickness"] == 0.013
    assert wool["properties"]["conductivity"] == ATTIC["wool_conductivity_w_mk"]
    assert wool["properties"]["density"] == ATTIC["wool_density_kg_m3"]
    assert wool["properties"]["specific_heat"] == ATTIC["wool_specific_heat_j_kgk"]
    assert wool["boverket_id"] == ATTIC["wool_boverket_id"]
    _assert_source(catalogue, wool)


@pytest.mark.parametrize("state", ("standard", "advanced"))
def test_renovation_keeps_original_ceiling_and_adds_shared_tabula_loose_wool(payload, catalogue, state):
    baseline_id = _top_id(payload, "existing")
    renovated_id = _top_id(payload, state)
    baseline_components = payload["elements"][baseline_id]["components"]
    assert payload["elements"][renovated_id]["components"] == [
        ATTIC["shared_addition_component_ids"][state], *baseline_components,
    ]
    assert _snapshot(payload, renovated_id)[1:] == ATTIC["original_layers"]
    wool = _single(
        payload, _layers(payload, renovated_id)[0], ATTIC["renovation_material_id"],
        ATTIC["states"][state]["added_insulation_m"],
    )
    assert wool["properties"]["conductivity"] == ATTIC["renovation_conductivity_w_mk"]
    assert wool["properties"]["density"] == ATTIC["renovation_density_kg_m3"]
    assert wool["boverket_id"] == ATTIC["renovation_boverket_id"]
    assert wool["carbon_reference_id"] == ATTIC["renovation_carbon_reference_id"]
    _assert_source(catalogue, wool)
    sf = catalogue.get("sf_se02", state=state).construction_set.elements[BuildingElement.TOP_FLOOR]
    mf = catalogue.get("mf_se01", state=state).construction_set.elements[BuildingElement.TOP_FLOOR]
    assert sf.components[0] is mf.components[0]


@pytest.mark.parametrize("state", STATES)
def test_forward_calculation_agrees_with_fixed_tabula_reference_for_every_zone(payload, catalogue, state):
    expected = ATTIC["states"][state]
    refs = load_sanity_fixture(FIXTURE)
    reference = next(row for row in refs["u_values"] if row["category"] == "single_family"
                     and row["era"] == "SE.02" and row["state"] == state)
    assert reference["elements"]["THERMAL_TOP"] == expected["tabula"]
    defaults = CASE["attic_defaults"]
    assert refs["policy"]["u_value_relative_tolerance"] == defaults["u_value_relative_tolerance"]
    forward = 1 / (defaults["nominal_surface_resistance_m2k_w"]
                   + _resistance(_snapshot(payload, _top_id(payload, state))))
    element = catalogue.get("sf_se02", state=state).construction_set.elements[BuildingElement.TOP_FLOOR]
    assert element.u_value == pytest.approx(forward, rel=1e-12)
    assert element.u_value == pytest.approx(expected["expected_u_w_m2k"], rel=1e-12)
    for target in expected["tabula"]["values_w_m2k"].values():
        assert abs(forward - target) / target <= defaults["u_value_relative_tolerance"]
    if state != "existing":
        package = next(row for row in refs["renovation_packages"]
                       if row["category"] == "single_family" and row["era"] == "SE.02"
                       and row["state"] == state)
        measure = refs["measures"][package["measures"]["THERMAL_TOP"]]
        assert measure["code"] == expected["measure_code"]
        assert measure["nominal_added_insulation_m"] == expected["added_insulation_m"]
        assert str(expected["measure_row"]) in measure["source_locator"]


@pytest.mark.parametrize("state", STATES)
def test_year_normal_use_and_cold_attic_weather_roof_are_consistent(payload, catalogue, state):
    config = _config(payload, state)
    assert config["construction_year"] == CASE["construction_year"] == 1970
    assert config["roof_topology"] == ATTIC["roof_topology"] == "cold_attic"
    assert config["weather_shell_element_id"] == ATTIC["weather_shell_element_id"]
    assert config["weather_shell_element_id"] != _top_id(payload, state)
    assert config["boundary_details"]["TOP_FLOOR"]["layer_order"] == "outside_to_inside"
    assert (catalogue.get("sf_se02", state=state).operating_profile.to_dict()
            == catalogue.get("sf_se02").operating_profile.to_dict())


@pytest.mark.parametrize("state", STATES)
def test_nominal_export_retains_continuous_wool_and_framed_layer_without_losing_mass(
    payload, catalogue, state,
):
    config = _config(payload, state)
    bundle = export_nominal_constructions(
        catalogue.get("sf_se02", state=state), metadata={"boundary_details": config["boundary_details"]},
    )
    original = _snapshot(payload, _top_id(payload, state))
    exported = bundle["honeybee"]["TOP_FLOOR"]["materials"]
    assert len(exported) == len(original)
    assert [row["thickness"] for row in exported] == [row["thickness_m"] for row in original]
    assert sum(row["thickness"] / row["conductivity"] for row in exported) == pytest.approx(
        _resistance(original), rel=1e-12,
    )
    original_mass = sum(layer["thickness_m"] * sum(
        row["area_fraction"] * row["thermal_properties"]["density"] for row in layer["materials"]
    ) for layer in original)
    assert sum(row["thickness"] * row["density"] for row in exported) == pytest.approx(
        original_mass, rel=1e-12,
    )
    assert bundle["roles"]["TOP_FLOOR"]["nominal_u_w_m2k"] == pytest.approx(
        ATTIC["states"][state]["expected_u_w_m2k"], rel=1e-12,
    )


def test_chosen_ceiling_improves_in_both_independent_renovation_states(catalogue):
    values = [catalogue.get("sf_se02", state=state).construction_set.elements[
        BuildingElement.TOP_FLOOR
    ].u_value for state in STATES]
    assert values[2] < values[1] < values[0]


def test_school_ceiling_and_shared_stock_materials_are_not_rewritten(payload):
    expected = CASE["attic_preservation"]
    for state, guard in expected["school_top_states"].items():
        eid = _top_id(payload, state, "school_se02")
        assert eid == guard["element_id"]
        assert payload["elements"][eid]["components"] == guard["component_ids"]
        assert _snapshot(payload, eid) == guard["layers"]
    for mid, guard in expected["material_properties"].items():
        for field in ("honeybee_id", "boverket_id", "properties"):
            assert payload["materials"][mid][field] == guard[field]
