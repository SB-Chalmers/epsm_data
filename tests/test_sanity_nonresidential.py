"""Independent physical mutations, not a snapshot of accepted catalogue U-values."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from epsm_data import Catalogue, load_sanity_fixture
from epsm_data.sanity import _operation
from epsm_data.sanity_nonresidential import (
    _metrics,
    check_nonresidential,
    validate_nonresidential_fixture,
)


@pytest.fixture
def fixture():
    return load_sanity_fixture()


@pytest.fixture
def raw():
    materials = {
        "concrete": {"name": "Concrete", "material_family": "concrete", "properties": {
            "conductivity": 1.7, "density": 2300, "specific_heat": 880}},
        "wool": {"name": "Mineral wool", "material_family": "mineral_wool", "properties": {
            "conductivity": .036, "density": 30, "specific_heat": 1000}},
        "timber": {"name": "Timber", "material_family": "timber", "properties": {
            "conductivity": .13, "density": 500, "specific_heat": 1600}},
        "window": {"kind": "window", "properties": {"u_value": 2, "shgc": .5, "vt": .65}},
    }
    data = {"materials": materials, "layers": {}, "components": {}, "elements": {},
            "construction_sets": {"set": {"elements": {}}}, "archetypes": {}}
    for role, material, depth in (("EXT_WALL", "concrete", .2), ("ROOF", "wool", .15),
                                  ("GROUND_FLOOR", "concrete", .1),
                                  ("BASEMENT_WALL", "concrete", .2),
                                  ("INTERMEDIATE_FLOOR", "concrete", .2)):
        data["layers"][role] = {"thickness": depth, "materials": [
            {"material_id": material, "area_fraction": 1, "thickness": depth}]}
        data["components"][role] = {"layers": [{"layer_id": role, "position": 0}]}
        data["elements"][role] = {"role": role, "components": [role],
                                  "side_convention": "top_to_bottom" if role == "INTERMEDIATE_FLOOR"
                                  else "outside_to_inside"}
        data["construction_sets"]["set"]["elements"][role] = role
    data["elements"]["window"] = {"role": "WINDOW", "window_material_id": "window"}
    data["layers"]["wall_insulation"] = {"thickness": .1, "materials": [
        {"material_id": "wool", "area_fraction": 1, "thickness": .1}]}
    data["components"]["EXT_WALL"]["layers"].append({"layer_id": "wall_insulation", "position": 1})
    data["construction_sets"]["set"]["elements"]["WINDOW"] = "window"
    note = {"rationale": "Explicit synthetic engineering assumption", "sources": ["test source"]}
    data["archetypes"]["office"] = {"category": "office", "era": "SE.02", "states": {
        "existing": {"construction_set_id": "set", "roof_topology": "compact",
                     "construction_year": 1965, "weather_shell_element_id": "ROOF",
                     "boundary_details": {role: {"layer_order": "upper_room_to_lower_room"
                                                  if role == "INTERMEDIATE_FLOOR" else "outside_to_inside"}
                                          for role in data["construction_sets"]["set"]["elements"]},
                     "sanity_assessment": {"as_built": note, "window_optics": note}}}}
    return data


def run(raw, fixture):
    result = []

    def emit(rule_id, severity, path, message, **details):
        result.append({"rule_id": rule_id, "severity": severity, "path": path,
                       "message": message, **details})

    # Independent homogeneous series-resistance calculation for these toy
    # inputs. The implementation consumes forward domain U-values separately
    # from layer depth, mass and capacity.
    definitions = {"window": SimpleNamespace(u_value=raw["materials"]["window"]["properties"]["u_value"])}
    for eid, element in raw["elements"].items():
        if element.get("role") == "WINDOW":
            continue
        resistance = .26 if element["role"] == "INTERMEDIATE_FLOOR" else .17
        for cid in element["components"]:
            for slot in raw["components"][cid]["layers"]:
                layer = raw["layers"][slot["layer_id"]]
                share = layer["materials"][0]
                resistance += share["thickness"] / raw["materials"][share["material_id"]]["properties"]["conductivity"]
        definitions[eid] = SimpleNamespace(u_value=1 / resistance)
    catalogue = SimpleNamespace(elements=definitions)
    check_nonresidential(raw, catalogue, emit, fixture)
    return result


def test_concrete_capacity_has_correct_dimensions(raw, fixture):
    metric = _metrics(raw, "GROUND_FLOOR", fixture["construction_rules"])
    assert metric["mass_kg_m2"] == pytest.approx(230)  # .1 m * 2300 kg/m3
    assert metric["capacity_kj_m2k"] == pytest.approx(202.4)  # 230 kg/m2 * .88 kJ/kgK


def test_independent_plausible_input_and_checks_are_read_only(raw, fixture):
    before, policy = deepcopy(raw), deepcopy(fixture)
    assert run(raw, fixture) == []
    assert raw == before and fixture == policy


def test_too_little_structural_mass_is_a_review_not_calibrated_target(raw, fixture):
    raw["layers"]["EXT_WALL"]["thickness"] = .001
    raw["layers"]["EXT_WALL"]["materials"][0]["thickness"] = .001
    findings = run(raw, fixture)
    row = next(f for f in findings if f["rule_id"] == "nonres.period_range")
    assert row["severity"] == "review"
    assert row["actual"]["wall_capacity_kj_m2k"] == pytest.approx(5.024)  # includes wool
    assert not row["expected"]["independent_validation"]


def test_wrong_conductivity_is_caught_with_correct_insulation_depth_and_mass(raw, fixture):
    raw["archetypes"]["office"]["era"] = "SE.06"
    raw["materials"]["wool"]["name"] = "Unspecified porous insulation proxy"
    # Still inside the policy's insulation conductivity domain, so its 100 mm
    # wall depth remains counted. The altered resistance must be screened too.
    raw["materials"]["wool"]["properties"]["conductivity"] = .09
    findings = run(raw, fixture)
    assert any(f["rule_id"] == "nonres.period_range" and "wall_u_w_m2k" in f["actual"]
               for f in findings)
    assert not any(f["rule_id"] == "nonres.period_range" and
                   "wall_capacity_kj_m2k" in f["actual"] for f in findings)
    assert not any(f["rule_id"] == "nonres.period_range" and
                   "wall_insulation_m" in f["actual"] for f in findings)


@pytest.mark.parametrize("field,value", [("shgc", .99), ("vt", .01)])
def test_window_optics_have_independent_broad_screens(raw, fixture, field, value):
    raw["materials"]["window"]["properties"][field] = value
    assert any(f["rule_id"] == "nonres.period_range" and field in f["actual"]
               for f in run(raw, fixture))


def test_period_proxy_does_not_establish_window_evidence(raw, fixture):
    del raw["archetypes"]["office"]["states"]["existing"]["sanity_assessment"]["window_optics"]
    assert any(f["rule_id"] == "nonres.window_evidence" and f["severity"] == "review"
               for f in run(raw, fixture))


def test_unheated_basement_requires_separate_soil_floor(raw, fixture):
    raw["archetypes"]["office"]["era"] = "SE.01"
    config = raw["archetypes"]["office"]["states"]["existing"]
    config["foundation_context"] = "unheated_basement"
    config["boundary_details"]["GROUND_FLOOR"].update(
        physical_role="basement_ceiling", physical_boundary="conditioned_to_unconditioned")
    findings = run(raw, fixture)
    assert any(f["rule_id"] == "construction.nonres_boundary" and f["severity"] == "missing"
               and f["actual"]["missing_role"] == "BASEMENT_FLOOR" for f in findings)


def test_timber_ceiling_cannot_masquerade_as_soil_concrete(raw, fixture):
    raw["archetypes"]["office"]["era"] = "SE.01"
    config = raw["archetypes"]["office"]["states"]["existing"]
    config["foundation_context"] = "unheated_basement"
    roles = raw["construction_sets"]["set"]["elements"]
    roles["BASEMENT_FLOOR"] = "soil"
    raw["elements"]["soil"] = {"role": "BASEMENT_FLOOR", "components": ["GROUND_FLOOR"],
                               "side_convention": "outside_to_inside"}
    raw["layers"]["GROUND_FLOOR"]["materials"][0]["material_id"] = "timber"
    config["boundary_details"]["GROUND_FLOOR"].update(
        physical_role="basement_ceiling", physical_boundary="conditioned_to_unconditioned")
    config["boundary_details"]["BASEMENT_FLOOR"] = {
        "physical_role": "basement_floor", "physical_boundary": "soil", "layer_order": "outside_to_inside"}
    assert any(f["rule_id"] == "construction.nonres_boundary" and f["severity"] == "error"
               and "timber/shavings" in f["message"] for f in run(raw, fixture))


def test_side_conventions_are_physical_not_just_valid_strings(raw, fixture):
    raw["elements"]["INTERMEDIATE_FLOOR"]["side_convention"] = "outside_to_inside"
    assert any(f["rule_id"] == "construction.nonres_side" and f["severity"] == "error"
               for f in run(raw, fixture))


def test_cold_attic_cannot_claim_weather_boundary_for_thermal_ceiling(raw, fixture):
    config = raw["archetypes"]["office"]["states"]["existing"]
    roles = raw["construction_sets"]["set"]["elements"]
    roles["TOP_FLOOR"] = roles.pop("ROOF")
    config["roof_topology"] = "cold_attic"
    config["boundary_details"]["TOP_FLOOR"] = {
        "physical_role": "weather_roof", "physical_boundary": "outdoors", "layer_order": "outside_to_inside"}
    assert any(f["rule_id"] == "construction.nonres_boundary" and f["severity"] == "error"
               for f in run(raw, fixture))


def test_malformed_raw_optics_or_order_are_reported_without_crash(raw, fixture):
    raw["materials"]["window"]["properties"]["shgc"] = []
    raw["elements"]["INTERMEDIATE_FLOOR"]["side_convention"] = []
    assert {r["rule_id"] for r in run(raw, fixture)} >= {
        "nonres.calculation", "construction.nonres_side"}


def test_renovation_retention_and_buildability_are_not_inferred_from_lower_u(raw, fixture):
    states = raw["archetypes"]["office"]["states"]
    states["standard"] = deepcopy(states["existing"])
    states["standard"]["construction_set_id"] = "renovated"
    raw["construction_sets"]["renovated"] = deepcopy(raw["construction_sets"]["set"])
    raw["construction_sets"]["renovated"]["elements"]["EXT_WALL"] = "newwall"
    raw["elements"]["newwall"] = {"role": "EXT_WALL", "components": ["ROOF"],
                                  "side_convention": "outside_to_inside"}
    ids = {f["rule_id"] for f in run(raw, fixture)}
    assert {"nonres.retained_fabric", "nonres.renovation_rationale"} <= ids


@pytest.mark.parametrize("placement,expected_review", [("outside_structure", False), ("inside_structure", True)])
def test_identical_insulation_boards_do_not_create_false_placement_violations(raw, fixture, placement, expected_review):
    raw["components"]["ROOF"]["layers"].append({"layer_id": "GROUND_FLOOR", "position": 1})
    states = raw["archetypes"]["office"]["states"]
    states["standard"] = deepcopy(states["existing"])
    states["standard"]["construction_set_id"] = "renovated"
    raw["construction_sets"]["renovated"] = deepcopy(raw["construction_sets"]["set"])
    raw["construction_sets"]["renovated"]["elements"]["ROOF"] = "newroof"
    order = ["ROOF", "ROOF", "GROUND_FLOOR"] if placement == "outside_structure" else ["ROOF", "GROUND_FLOOR", "ROOF"]
    raw["components"]["newroof"] = {"layers": [{"layer_id": lid, "position": i} for i, lid in enumerate(order)]}
    raw["elements"]["newroof"] = {"role": "ROOF", "components": ["newroof"], "side_convention": "outside_to_inside"}
    findings = run(raw, fixture)
    assert any(f["rule_id"] == "nonres.renovation_placement" for f in findings) == expected_review


def test_residential_reference_checks_are_not_replaced(raw, fixture):
    raw["archetypes"]["office"]["category"] = "single_family"
    raw["materials"]["window"]["properties"]["shgc"] = .99
    assert run(raw, fixture) == []


def test_nonres_fixture_rejects_inverted_or_missing_period_ranges(fixture):
    data = deepcopy(fixture["nonresidential_construction"])
    data["period_screens"][0]["wall_insulation_m"] = [.2, 0]
    with pytest.raises(ValueError, match="range"):
        validate_nonresidential_fixture(data)
    del data["period_screens"][0]
    with pytest.raises(ValueError, match="coverage"):
        validate_nonresidential_fixture(data)


def test_older_explicit_four_file_bundle_remains_valid_and_not_assessed(raw, tmp_path):
    maintained = Path(__file__).parent / "fixtures/catalogue_sanity"
    for name in ("policy.json", "construction_rules.json", "tabula_u_values.json", "tabula_renovations.json"):
        (tmp_path / name).write_bytes((maintained / name).read_bytes())
    older = load_sanity_fixture(tmp_path)
    assert "nonresidential_construction" not in older
    findings = run(raw, older)
    assert len(findings) == 1 and findings[0]["rule_id"] == "nonres.reference_not_assessed"
    assert findings[0]["severity"] == "review"


def test_all_38_nonresidential_profiles_declare_atemp_and_calendar():
    catalogue = Catalogue.load()
    selections = []
    for category in ("office", "school"):
        for aid in catalogue.ids(category=category):
            for state in catalogue.renovation_states(aid) or (None,):
                profile = catalogue.get(aid, state=state).operating_profile
                assert profile.values["area_basis"] == "Atemp"
                assert {"load_reference_area_m2", "calendar"} <= set(profile.values["requirements"])
                selections.append((aid, state))
    assert len(selections) == 38
    findings = []
    _operation(catalogue.resolved_dict(), catalogue,
               lambda rule, severity, path, message, **kw: findings.append((rule, path)))
    assert not any(rule == "operation.reference_area" and any(
        f"archetypes.{aid}." in path for aid, _ in selections
    ) for rule, path in findings)
