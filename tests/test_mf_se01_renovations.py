"""Independent TABULA measures, retained historic fabric and explicit completion defaults."""

import json
from pathlib import Path

import pytest

from epsm_data import (
    BuildingElement,
    Catalogue,
    export_nominal_constructions,
    load_sanity_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/catalogue_sanity"
CASE = json.loads((FIXTURE / "cases/mf_se01_renovation.json").read_text())
STATES = tuple(CASE["states"])


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture(scope="module")
def payload(catalogue):
    return catalogue.resolved_dict()


@pytest.fixture(scope="module")
def report(catalogue):
    return catalogue.sanity_report(fixture=FIXTURE)


def _config(data, state):
    return data["archetypes"]["mf_se01"]["states"][state]


def _element_id(data, state, role):
    return data["construction_sets"][_config(data, state)["construction_set_id"]]["elements"][role]


def _stack(data, state, role):
    element = data["elements"][_element_id(data, state, role)]
    return [
        data["layers"][slot["layer_id"]]
        for cid in element["components"]
        for slot in sorted(data["components"][cid]["layers"], key=lambda item: item["position"])
    ]


def _single(data, layer):
    assert not layer["is_composite"]
    assert len(layer["materials"]) == 1
    constituent = layer["materials"][0]
    assert constituent["area_fraction"] == 1
    assert constituent["thickness"] == layer["thickness"]
    return data["materials"][constituent["material_id"]]


def _signature(layer):
    return (layer["thickness"], tuple(
        (row["material_id"], row["area_fraction"], row["thickness"])
        for row in layer["materials"]
    ))


def _assert_source_consistency(catalogue, material):
    source = catalogue.honeybee_materials[material["honeybee_id"]]
    assert {field: source[field] for field in material["properties"]} == material["properties"]


def test_independent_mf_se01_package_fixture_matches_selected_tabula_measures():
    references = load_sanity_fixture(FIXTURE)
    for state, expected in CASE["states"].items():
        package = next(row for row in references["renovation_packages"]
                       if row["category"] == "multi_family" and row["era"] == "SE.01"
                       and row["state"] == state)
        assert package["source_variant"] == expected["source_variant"]
        assert str(expected["source_variant_row"]) in package["source_locator"]
        for role, key in (("EXT_WALL", "wall"), ("THERMAL_TOP", "attic"),
                          ("GROUND_FLOOR", "floor")):
            measure = references["measures"][package["measures"][role]]
            assert measure["code"] == expected[key]["measure_code"]
            assert measure["nominal_added_insulation_m"] == expected[key]["added_insulation_m"]
            assert str(expected[key]["measure_row"]) in measure["source_locator"]
        window = references["measures"][package["measures"]["WINDOW"]]
        assert window["window_u_w_m2k"] == pytest.approx(expected["window"]["u_w_m2k"])
        assert str(expected["window"]["measure_row"]) in window["source_locator"]


@pytest.mark.parametrize("state", STATES)
def test_wall_adds_actual_brick_and_insulation_package_outside_retained_aac(payload, catalogue, state):
    expected = CASE["states"][state]["wall"]
    defaults = CASE["assembly_defaults"]
    baseline = _stack(payload, "existing", "EXT_WALL")
    renovated = _stack(payload, state, "EXT_WALL")
    assert [_signature(layer) for layer in renovated[2:]] == [_signature(layer) for layer in baseline]
    assert renovated[0]["thickness"] == defaults["wall_brick_thickness_m"]
    brick = _single(payload, renovated[0])
    assert "brick" in brick["name"].casefold()
    assert brick["properties"]["conductivity"] == defaults["wall_brick_conductivity_w_mk"]
    assert brick["properties"]["density"] == defaults["wall_brick_density_kg_m3"]
    assert brick["boverket_id"] == defaults["wall_brick_boverket_id"]
    assert renovated[1]["thickness"] == expected["added_insulation_m"]
    insulation = _single(payload, renovated[1])
    assert insulation["properties"]["conductivity"] == expected["insulation_conductivity_w_mk"]
    for material in (brick, insulation):
        _assert_source_consistency(catalogue, material)
    assert _config(payload, state)["boundary_details"]["EXT_WALL"]["layer_order"] == "outside_to_inside"


@pytest.mark.parametrize("state", STATES)
def test_attic_adds_loose_glass_wool_grade_without_overwriting_shared_stone_wool(payload, catalogue, state):
    expected = CASE["states"][state]["attic"]
    defaults = CASE["assembly_defaults"]
    baseline = _stack(payload, "existing", "TOP_FLOOR")
    renovated = _stack(payload, state, "TOP_FLOOR")
    assert [_signature(layer) for layer in renovated[1:]] == [_signature(layer) for layer in baseline]
    assert renovated[0]["thickness"] == expected["added_insulation_m"]
    wool = _single(payload, renovated[0])
    assert "glass" in wool["name"].casefold()
    assert "loose" in wool["name"].casefold() or "blow" in wool["name"].casefold()
    assert wool["properties"]["conductivity"] == expected["insulation_conductivity_w_mk"]
    assert wool["properties"]["density"] == defaults["attic_density_kg_m3"]
    assert wool["boverket_id"] == defaults["attic_boverket_id"]
    assert wool["carbon_reference_id"] == defaults["attic_carbon_reference_id"]
    _assert_source_consistency(catalogue, wool)
    old = payload["materials"][CASE["baseline"]["retained_shared_attic_material_id"]]
    assert old["properties"]["conductivity"] == CASE["baseline"]["retained_shared_attic_conductivity_w_mk"]


@pytest.mark.parametrize("state", STATES)
def test_ground_floor_adds_internal_eps_and_explicit_screed_completion(payload, catalogue, state):
    expected = CASE["states"][state]["floor"]
    defaults = CASE["assembly_defaults"]
    baseline = _stack(payload, "existing", "GROUND_FLOOR")
    renovated = _stack(payload, state, "GROUND_FLOOR")
    assert [_signature(layer) for layer in renovated[:-2]] == [_signature(layer) for layer in baseline]
    assert renovated[-2]["thickness"] == expected["added_insulation_m"]
    eps = _single(payload, renovated[-2])
    assert eps["properties"]["conductivity"] == expected["insulation_conductivity_w_mk"]
    assert eps["boverket_id"] == defaults["floor_eps_boverket_id"]
    assert renovated[-1]["thickness"] == defaults["floor_screed_thickness_m"]
    screed = _single(payload, renovated[-1])
    assert screed["properties"]["conductivity"] == defaults["floor_screed_conductivity_w_mk"]
    assert screed["properties"]["density"] == defaults["floor_screed_density_kg_m3"]
    assert screed["boverket_id"] == defaults["floor_screed_boverket_id"]
    for material in (eps, screed):
        _assert_source_consistency(catalogue, material)
    assessment = _config(payload, state)["sanity_assessment"]["measure_placement"]["GROUND_FLOOR"]
    assert assessment["rationale"] and assessment["sources"]


@pytest.mark.parametrize("state", STATES)
def test_window_matches_whole_window_optics_and_correct_frame_carbon_family(payload, catalogue, state):
    expected = CASE["states"][state]["window"]
    record = payload["elements"][_element_id(payload, state, "WINDOW")]
    window = payload["materials"][record["window_material_id"]]
    assert window["properties"]["u_value"] == pytest.approx(expected["u_w_m2k"])
    assert window["properties"]["shgc"] == pytest.approx(expected["glazing_g"] * (1-expected["frame_fraction"]))
    assert window["properties"]["shgc"] == pytest.approx(expected["whole_aperture_shgc"])
    assert window["properties"]["vt"] == pytest.approx(expected["whole_aperture_vt_default"])
    assert window["boverket_id"] == expected["boverket_id"]
    source = catalogue.honeybee_materials[window["honeybee_id"]]
    assert source["type"] == "EnergyWindowMaterialSimpleGlazSys"
    assert source["u_factor"] == pytest.approx(expected["u_w_m2k"])
    assert source["shgc"] == pytest.approx(expected["whole_aperture_shgc"])
    assert source["vt"] == pytest.approx(expected["whole_aperture_vt_default"])
    old = payload["materials"][CASE["baseline"]["retained_shared_standard_window_id"]]
    assert old["properties"]["u_value"] == CASE["baseline"]["retained_shared_standard_window_u_w_m2k"]


@pytest.mark.parametrize("state", STATES)
def test_forward_u_values_follow_measures_and_renovation_does_not_rewrite_era(catalogue, payload, state):
    expected = CASE["states"][state]
    archetype = catalogue.get("mf_se01", state=state)
    assert _config(payload, state)["construction_year"] == CASE["baseline"]["construction_year"]
    assert archetype.operating_profile is catalogue.get("mf_se01").operating_profile
    for role, value in expected["expected_u_w_m2k"].items():
        element = archetype.construction_set.elements[BuildingElement(role)]
        assert element.u_value == pytest.approx(value, rel=1e-12)
        assert element.u_value < CASE["baseline"]["u_w_m2k"][role]
    generic = catalogue.get("generic_se01", state=state)
    assert generic.construction_set is archetype.construction_set
    assert generic.operating_profile is archetype.operating_profile


@pytest.mark.parametrize("state", STATES)
def test_corrected_states_pass_mapped_packages_and_keep_ground_comparisons_unassessed(report, state):
    affected = [row for row in report["findings"] if any(
        user["archetype_id"] == "mf_se01" and user["state"] == state
        for user in row["affected_archetypes"]
    )]
    assert not [row for row in affected if row["severity"] == "error"
                and row["rule_id"].startswith(("tabula.", "renovation."))]
    unassessed = [row for row in affected if row["rule_id"] == "tabula.boundary_not_assessed"]
    assert {row["actual"]["element"] for row in unassessed} == {"GROUND_FLOOR", "TABULA_WALL_2"}
    assert all(row["actual"]["status"] == CASE["boundary_resolution"]["comparison_status"]
               for row in unassessed)
    assert all(row["severity"] == "review" for row in unassessed)
    assert any(row["rule_id"] == "tabula.source_convention" and row["severity"] == "review"
               for row in affected)
    assert not any(row["rule_id"] == "tabula.measure_mapping" for row in affected)
    assert not any(row["rule_id"] == "tabula.measure_placement" for row in affected)


def test_original_mf_se01_physics_and_tabula_window_match_independent_fixture(catalogue, report):
    baseline = catalogue.get("mf_se01")
    for role, expected in CASE["baseline"]["u_w_m2k"].items():
        assert baseline.construction_set.elements[BuildingElement(role)].u_value == pytest.approx(expected, rel=1e-12)
    expected = CASE["baseline"]["window"]["tabula_comparison"]
    policy = load_sanity_fixture(FIXTURE)["policy"]
    assert policy["u_value_relative_tolerance"] == expected["relative_tolerance"]
    reference = next(row for row in load_sanity_fixture(FIXTURE)["u_values"]
                     if row["category"] == "multi_family" and row["era"] == "SE.01"
                     and row["state"] == "existing")
    assert set(reference["elements"]["WINDOW"]["values_w_m2k"].values()) == {expected["u_w_m2k"]}
    window = baseline.construction_set.elements[BuildingElement.WINDOW]
    difference = abs(window.u_value - expected["u_w_m2k"]) / expected["u_w_m2k"]
    assert difference <= expected["relative_tolerance"]
    assert not any(row["rule_id"] == "tabula.u_value" and row["expected"]["element"] == "WINDOW"
                   and any(user["archetype_id"] == "mf_se01" and user["state"] == "existing"
                           for user in row["affected_archetypes"])
                   for row in report["findings"])


def test_original_tabula_window_uses_whole_aperture_optics_and_honeybee_simple_glazing(
    payload, catalogue,
):
    expected = CASE["baseline"]["window"]
    record = payload["elements"][_element_id(payload, "existing", "WINDOW")]
    window = payload["materials"][record["window_material_id"]]
    assert window["properties"] == pytest.approx({
        "u_value": expected["u_w_m2k"],
        "shgc": expected["whole_aperture_shgc"],
        "vt": expected["whole_aperture_vt_default"],
    })
    glazing_fraction = 1 - expected["frame_fraction"]
    assert window["properties"]["shgc"] == pytest.approx(expected["glazing_g"] * glazing_fraction)
    assert window["properties"]["vt"] == pytest.approx(expected["glazing_vt_default"] * glazing_fraction)
    assert window["boverket_id"] == expected["boverket_id"]
    source = catalogue.honeybee_materials[window["honeybee_id"]]
    assert source["type"] == "EnergyWindowMaterialSimpleGlazSys"
    assert source["u_factor"] == pytest.approx(expected["u_w_m2k"])
    assert source["shgc"] == pytest.approx(expected["whole_aperture_shgc"])
    assert source["vt"] == pytest.approx(expected["whole_aperture_vt_default"])
    assert catalogue.get("generic_se01").construction_set is catalogue.get("mf_se01").construction_set
    assert catalogue.get("generic_se01").operating_profile is catalogue.get("mf_se01").operating_profile


def test_original_window_change_keeps_other_shared_older_window_users_unchanged(payload):
    expected = CASE["baseline"]["window"]
    old_id = expected["retained_shared_existing_window_id"]
    assert payload["materials"][old_id]["properties"] == expected[
        "retained_shared_existing_window_properties"]
    new_element = payload["elements"][_element_id(payload, "existing", "WINDOW")]
    assert new_element["window_material_id"] != old_id
    for archetype_id in expected["retained_shared_existing_window_users"]:
        config = payload["archetypes"][archetype_id]["states"]["existing"]
        window_id = payload["construction_sets"][config["construction_set_id"]]["elements"]["WINDOW"]
        assert payload["elements"][window_id]["window_material_id"] == old_id


def test_secondary_wall_source_measure_is_40mm_stone_wool_and_standard_has_no_addition():
    references = load_sanity_fixture(FIXTURE)
    expected = CASE["states"]["advanced"]["secondary_wall"]
    package = next(row for row in references["renovation_packages"]
                   if row["category"] == "multi_family" and row["era"] == "SE.01"
                   and row["state"] == "advanced")
    measure = references["measures"][package["measures"]["TABULA_WALL_2"]]
    assert measure["code"] == expected["measure_code"]
    assert measure["nominal_added_insulation_m"] == expected["added_insulation_m"]
    assert str(expected["measure_row"]) in measure["source_locator"]
    standard = next(row for row in references["renovation_packages"]
                    if row["category"] == "multi_family" and row["era"] == "SE.01"
                    and row["state"] == "standard")
    assert "TABULA_WALL_2" not in standard["measures"]


def test_advanced_secondary_wall_adds_internal_40mm_shared_stone_wool_and_declared_finish(
    payload, catalogue,
):
    expected = CASE["states"]["advanced"]["secondary_wall"]
    defaults = CASE["assembly_defaults"]["basement_wall_drylining"]
    baseline = _stack(payload, "existing", "BASEMENT_WALL")
    standard = _stack(payload, "standard", "BASEMENT_WALL")
    advanced = _stack(payload, "advanced", "BASEMENT_WALL")
    assert [_signature(layer) for layer in standard] == [_signature(layer) for layer in baseline]
    assert [_signature(layer) for layer in advanced[:-2]] == [_signature(layer) for layer in baseline]
    assert advanced[-2]["thickness"] == expected["added_insulation_m"]
    wool = _single(payload, advanced[-2])
    assert advanced[-2]["materials"][0]["material_id"] == defaults["insulation_material_id"]
    assert wool["properties"]["conductivity"] == expected["insulation_conductivity_w_mk"]
    assert wool["properties"]["density"] == defaults["insulation_density_kg_m3"]
    assert wool["properties"]["specific_heat"] == defaults["insulation_specific_heat_j_kgk"]
    assert wool["honeybee_id"] == defaults["insulation_honeybee_id"]
    assert wool["boverket_id"] == defaults["insulation_boverket_id"]
    assert advanced[-1]["thickness"] == defaults["finish_thickness_m"]
    assert advanced[-1]["materials"][0]["material_id"] == defaults["finish_material_id"]
    gypsum = _single(payload, advanced[-1])
    assert gypsum["properties"]["conductivity"] == defaults["finish_conductivity_w_mk"]
    for material in (wool, gypsum):
        _assert_source_consistency(catalogue, material)
    declared = _config(payload, "advanced")["boundary_details"]["BASEMENT_WALL"]
    assert "warm side" in declared["renovation"].casefold()
    assessment = _config(payload, "advanced")["sanity_assessment"]["measure_placement"][
        "TABULA_WALL_2"]
    assert assessment["rationale"] and assessment["sources"]
    declaration = json.dumps(declared).casefold()
    assert "13 mm" in declaration
    assert "default" in declaration or "assumption" in declaration


@pytest.mark.parametrize("state", ("existing", *STATES))
def test_ground_roles_resolve_to_conditioned_basement_with_source_mapping(payload, state):
    expected = CASE["boundary_resolution"]
    for role, source in expected["roles"].items():
        declared = _config(payload, state)["boundary_details"][role]
        assert declared["physical_boundary"] == expected["physical_boundary"]
        assert declared["physical_role"] == source["physical_role"]
        assert declared["source_mapping"] == source["source_mapping"]
        assert declared["value_meaning"] == expected["value_meaning"]


@pytest.mark.parametrize("state", ("existing", *STATES))
def test_effective_source_u_stays_distinct_from_forward_nominal_layers(catalogue, payload, state):
    references = load_sanity_fixture(FIXTURE)
    expected = CASE["boundary_resolution"]
    reference = next(row for row in references["u_values"]
                     if row["category"] == "multi_family" and row["era"] == "SE.01"
                     and row["state"] == state)
    for role, source in expected["roles"].items():
        historical = reference["elements"][source["source_mapping"]]
        assert all(value == pytest.approx(
            expected["workbook_output_u_w_m2k"][state][source["source_mapping"]])
            for value in historical["values_w_m2k"].values())
        # Reproduce the historical workbook convention only as a source audit;
        # its ground-inclusive U inputs must never become a nominal-layer target.
        measure_r = 0
        if state != "existing":
            measure = CASE["states"][state]["floor" if role == "GROUND_FLOOR"
                                                  else "secondary_wall"]
            if measure["added_insulation_m"]:
                measure_r = (measure["added_insulation_m"]
                             / measure["insulation_conductivity_w_mk"])
        workbook_u = 1 / (1 / source["source_input_u_w_m2k"] + measure_r
                          + expected["source_convention"][
                              "workbook_additional_unheated_space_resistance_m2k_w"])
        assert historical["values_w_m2k"]["SE.Zone1"] == pytest.approx(workbook_u)
        assert source["input_source_locator"] and source["description_source_locator"]
        assert source["border_source_locator"] and source["betsi_locator"]
        element = catalogue.get("mf_se01", state=state).construction_set.elements[
            BuildingElement(role)]
        nominal_r = sum(layer["thickness"] / _single(payload, layer)["properties"]["conductivity"]
                        for layer in _stack(payload, state, role))
        assert element.u_value == pytest.approx(1 / (nominal_r + 0.17))
        assert element.u_value != pytest.approx(source["source_input_u_w_m2k"])
        assert element.u_value != pytest.approx(workbook_u)


@pytest.mark.parametrize("state", ("existing", *STATES))
def test_ground_nominal_export_contains_only_material_resistance_and_declared_surface_films(
    catalogue, payload, state,
):
    archetype = catalogue.get("mf_se01", state=state)
    bundle = export_nominal_constructions(archetype, metadata=_config(payload, state))
    for role in CASE["boundary_resolution"]["roles"]:
        stack = _stack(payload, state, role)
        expected_r = sum(layer["thickness"] / _single(payload, layer)["properties"]["conductivity"]
                         for layer in stack)
        exported = bundle["roles"][role]
        assert exported["resistance_m2k_w"] == pytest.approx(expected_r)
        assert exported["rsi_m2k_w"] == 0.13
        assert exported["rse_m2k_w"] == 0.04
        assert bundle["core"][role]["surface_resistance_m2k_w"] == pytest.approx(0.17)
        assert exported["nominal_u_w_m2k"] == pytest.approx(1 / (expected_r + 0.17))
        hb = bundle["honeybee"][role]
        assert len(hb["materials"]) == len(stack)
        assert sum(material["thickness"] / material["conductivity"]
                   for material in hb["materials"]) == pytest.approx(expected_r)
        assert hb["user_data"]["boundary_details"]["physical_boundary"] == "soil"


def test_advanced_secondary_wall_forward_u_uses_independent_thickness_and_grade_fixture(catalogue):
    defaults = CASE["assembly_defaults"]["basement_wall_drylining"]
    measure = CASE["states"]["advanced"]["secondary_wall"]
    resistance = sum(row["thickness_m"] / row["conductivity_w_mk"]
                     for row in defaults["retained_layers"])
    resistance += measure["added_insulation_m"] / measure["insulation_conductivity_w_mk"]
    resistance += defaults["finish_thickness_m"] / defaults["finish_conductivity_w_mk"]
    expected_u = 1 / (resistance + defaults["nominal_surface_resistance_m2k_w"])
    advanced = catalogue.get("mf_se01", state="advanced").construction_set.elements[
        BuildingElement.BASEMENT_WALL]
    assert advanced.u_value == pytest.approx(expected_u, rel=1e-12)
    assert advanced.u_value < catalogue.get("mf_se01", state="standard").construction_set.elements[
        BuildingElement.BASEMENT_WALL].u_value



def _expected_floor_metrics(state, *, include_cap):
    """Forward independent grade/thickness expectations, never reverse-fit from U."""
    defaults = CASE["assembly_defaults"]
    layers = list(CASE["baseline"]["floor_retained_layers"])
    if include_cap:
        cap = defaults["floor_cap"]
        grade = cap["properties"]
        layers.append({"thickness_m": cap["thickness_m"],
                       "conductivity_w_mk": grade["conductivity"],
                       "density_kg_m3": grade["density"],
                       "specific_heat_j_kgk": grade["specific_heat"]})
    if state != "existing":
        floor = CASE["states"][state]["floor"]
        layers.extend([
            {"thickness_m": floor["added_insulation_m"],
             "conductivity_w_mk": floor["insulation_conductivity_w_mk"],
             "density_kg_m3": defaults["floor_eps_density_kg_m3"],
             "specific_heat_j_kgk": defaults["floor_eps_specific_heat_j_kgk"]},
            {"thickness_m": defaults["floor_screed_thickness_m"],
             "conductivity_w_mk": defaults["floor_screed_conductivity_w_mk"],
             "density_kg_m3": defaults["floor_screed_density_kg_m3"],
             "specific_heat_j_kgk": defaults["floor_screed_specific_heat_j_kgk"]},
        ])
    resistance = sum(layer["thickness_m"] / layer["conductivity_w_mk"] for layer in layers)
    return {
        "thickness_m": sum(layer["thickness_m"] for layer in layers),
        "resistance_m2k_w": resistance,
        "mass_kg_m2": sum(layer["thickness_m"] * layer["density_kg_m3"] for layer in layers),
        "heat_capacity_j_m2k": sum(layer["thickness_m"] * layer["density_kg_m3"]
                                   * layer["specific_heat_j_kgk"] for layer in layers),
        "nominal_u_w_m2k": 1 / (resistance + 0.17),
    }


@pytest.mark.parametrize("state", ("existing", *STATES))
def test_original_floor_has_shared_80mm_concrete_cap_above_retained_leca(payload, catalogue, state):
    retained = CASE["baseline"]["floor_retained_layers"]
    cap = CASE["assembly_defaults"]["floor_cap"]
    layers = _stack(payload, state, "GROUND_FLOOR")
    assert len(layers) == len(retained) + 1 + (2 if state != "existing" else 0)
    for layer, expected in zip(layers, retained, strict=False):
        assert layer["thickness"] == expected["thickness_m"]
        assert layer["materials"][0]["material_id"] == expected["material_id"]
        material = _single(payload, layer)
        assert material["properties"]["conductivity"] == expected["conductivity_w_mk"]
        assert material["properties"]["density"] == expected["density_kg_m3"]
        assert material["properties"]["specific_heat"] == expected["specific_heat_j_kgk"]
    cap_layer = layers[len(retained)]
    assert cap_layer["thickness"] == cap["thickness_m"]
    material = _single(payload, cap_layer)
    assert material["properties"] == cap["properties"]
    assert material["honeybee_id"] == cap["source_thermal_identifier"]
    assert catalogue.honeybee_materials[material["honeybee_id"]]["identifier"] == (
        cap["source_thermal_identifier"])
    assert material["boverket_id"] == cap["boverket_id"]
    assert "concrete" in material["name"].casefold()
    assert "mf" not in material["name"].casefold()
    _assert_source_consistency(catalogue, material)
    assert len([record for record in payload["materials"].values()
                if record.get("kind") == "opaque"
                and record["properties"] == cap["properties"]
                and record.get("boverket_id") == cap["boverket_id"]]) == 1
    original_layer = _stack(payload, "existing", "GROUND_FLOOR")[len(retained)]
    # Shared definitions are represented by the same normalized layer record.
    assert cap_layer is original_layer
    assert _config(payload, state)["construction_year"] == CASE["baseline"]["construction_year"]
    archetype = catalogue.get("mf_se01", state=state)
    generic = catalogue.get("generic_se01", state=state)
    assert generic.construction_set is archetype.construction_set
    assert generic.operating_profile is archetype.operating_profile


@pytest.mark.parametrize("state", ("existing", *STATES))
def test_floor_cap_forward_resistance_mass_and_heat_capacity_match_independent_grade_fixture(
    catalogue, payload, state,
):
    cap = CASE["assembly_defaults"]["floor_cap"]
    expected = _expected_floor_metrics(state, include_cap=True)
    prior = _expected_floor_metrics(state, include_cap=False)
    assert expected["resistance_m2k_w"] - prior["resistance_m2k_w"] == pytest.approx(
        cap["expected_added_resistance_m2k_w"])
    assert expected["mass_kg_m2"] - prior["mass_kg_m2"] == pytest.approx(
        cap["expected_added_mass_kg_m2"])
    assert expected["heat_capacity_j_m2k"] - prior["heat_capacity_j_m2k"] == pytest.approx(
        cap["expected_added_heat_capacity_j_m2k"])
    archetype = catalogue.get("mf_se01", state=state)
    bundle = export_nominal_constructions(archetype, metadata=_config(payload, state))
    actual = bundle["roles"]["GROUND_FLOOR"]
    for key, value in expected.items():
        assert actual[key] == pytest.approx(value, rel=1e-12)
    assert actual["nominal_u_w_m2k"] < prior["nominal_u_w_m2k"]


def test_floor_cap_carbon_proxy_density_is_comparable_and_within_policy(payload, report):
    cap = CASE["assembly_defaults"]["floor_cap"]
    material_id = _stack(payload, "existing", "GROUND_FLOOR")[2]["materials"][0]["material_id"]
    material = payload["materials"][material_id]
    source = payload["boverket"][material["boverket_id"]]
    assert source["InventoryUnit"] == "kg"
    source_density = next(row["Value"] for row in source["Conversions"]
                          if row["Field"] == "Volume" and row["Unit"] == "kg/m³")
    assert source_density == cap["boverket_source_density_kg_m3"]
    difference = abs(material["properties"]["density"] - source_density) / source_density
    assert difference == pytest.approx(110 / 2350)
    assert difference <= 0.2
    assert not [row for row in report["findings"]
                if row["rule_id"] == "density.agreement"
                and row["path"].startswith(f"materials.{material_id}.")]
