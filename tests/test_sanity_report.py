"""Independent fixtures exercise reporting, shared impact and read-only checks."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from epsm_data import Catalogue, check_catalogue, load_sanity_fixture
from epsm_data.cli import main
from epsm_data.sanity import FIXTURE_FILES

FIXTURE = Path(__file__).parent / "fixtures/catalogue_sanity"
CASES = json.loads((FIXTURE / "cases/reporting.json").read_text())


@pytest.fixture(scope="module")
def fixture():
    return load_sanity_fixture(FIXTURE)


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


def test_packaged_expectations_are_exact_mirror_of_maintained_test_fixture():
    from importlib.resources import files

    packaged = files("epsm_data.datasets.sanity")
    assert set(FIXTURE_FILES) == {
        "policy.json", "construction_rules.json", "tabula_u_values.json", "tabula_renovations.json",
        "nonresidential_construction.json",
    }
    for filename in FIXTURE_FILES:
        assert (FIXTURE / filename).read_bytes() == packaged.joinpath(filename).read_bytes(), filename
    assert load_sanity_fixture() == load_sanity_fixture(FIXTURE)


def test_fixture_policies_are_the_agreed_values(fixture):
    assert fixture["fixture_id"] == "epsm-catalogue-sanity"
    assert fixture["policy"]["u_value_relative_tolerance"] == 0.2
    assert fixture["policy"]["density_review_relative_difference"] == 0.2
    assert fixture["policy"]["density_prominent_relative_difference"] == 0.5
    assert fixture["policy"]["generic_fallback"]["donor_category"] == "multi_family"
    assert not fixture["policy"]["generic_fallback"]["is_average"]


def test_reports_are_deterministic_portable_and_leave_all_inputs_unchanged(catalogue, fixture):
    before, expected = catalogue.to_dict(), deepcopy(fixture)
    report = catalogue.sanity_report(fixture=fixture)
    assert catalogue.to_dict() == before
    assert fixture == expected
    assert check_catalogue(before, fixture=fixture) == report
    assert catalogue.sanity_report(fixture=FIXTURE) == report
    assert json.loads(json.dumps(report, allow_nan=False)) == report
    assert report["summary"]["status"] == "review"
    assert report["summary"]["finding_count"] == len(report["findings"])
    assert report["summary"]["blocking_count"] == sum(
        row["severity"] in {"error", "missing"} for row in report["findings"]
    )


def test_reference_export_and_expanded_physics_have_identical_sanity(catalogue, fixture):
    reference, resolved = catalogue.to_dict(), catalogue.resolved_dict()
    assert reference["schema_version"] == 2
    assert resolved["schema_version"] == 1
    assert not {"thermal", "boverket", "carbon_references"} & reference.keys()
    expected = catalogue.sanity_report(fixture=fixture)
    assert check_catalogue(reference, fixture=fixture) == expected
    assert check_catalogue(resolved, fixture=fixture) == expected


@pytest.mark.parametrize("fault", ["version", "reference", "malformed_reference"])
def test_unresolvable_reference_payload_reports_failure_without_fallback(catalogue, fixture, fault):
    payload = catalogue.to_dict()
    if fault == "version":
        source = next(iter(payload["source_versions"]))
        payload["source_versions"][source] = "not-the-captured-release"
    else:
        material = next(iter(payload["materials"].values()))
        material["thermal_ref"] = [] if fault == "malformed_reference" else {
            "source": "unknown-source", "identifier": "unknown-record"}
    report = check_catalogue(payload, fixture=fixture)
    assert report["summary"]["status"] == "blocked"
    assert report["readiness"]["thermal_inputs"]["status"] == "blocked"
    assert len(report["findings"]) == 4
    assert any(row["rule_id"] == "catalogue.hydration" and row["severity"] == "error"
               and row["assessment"] == "not_assessed" for row in report["findings"])
    assert not any(row["rule_id"] == "catalogue.section" for row in report["findings"])


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda case: case["name"])
def test_raw_bad_inputs_report_every_user_of_the_shared_definition(catalogue, fixture, case):
    data = catalogue.resolved_dict()
    data[case["section"]][case["identifier"]].update(case["changes"])
    original = deepcopy(data)
    report = check_catalogue(data, fixture=fixture)
    matches = [row for row in report["findings"] if row["rule_id"] == case["expected_rule"]
               and row["path"].startswith(f"{case['section']}.{case['identifier']}")]
    assert matches
    assert {row["severity"] for row in matches} == {case["expected_severity"]}
    users = matches[0]["affected_archetypes"]
    assert {user["archetype_id"] for user in users} == set(case["expected_users"])
    assert {user["state"] for user in users} == set(case["expected_states"])
    assert all(user["climate_zones"] == ["SE.Zone1", "SE.Zone2", "SE.Zone3"] for user in users)
    assert data == original


def test_optional_carbon_coverage_does_not_block_catalogue_readiness(catalogue, fixture):
    report = catalogue.sanity_report(fixture=fixture)
    carbon = [row for row in report["findings"] if row["rule_id"] == "carbon.modules"
              and CASES["source_module_placeholder"]["source_id"] in json.dumps(row)]
    assert carbon
    assert all(row["severity"] == "review" for row in carbon)
    assert report["readiness"]["carbon_inputs"]["status"] == "review"
    assert report["readiness"]["thermal_inputs"]["error_count"] == 0
    assert report["project_requirements"]
    assert any("calendar" in row["project_inputs"] for row in report["project_requirements"])


def test_missing_base_production_still_blocks_carbon_readiness(catalogue, fixture):
    payload = catalogue.resolved_dict()
    reference = payload["carbon_references"][CASES["source_module_placeholder"]["source_id"]]
    reference["modules"]["A1A3"] = None
    report = check_catalogue(payload, fixture=fixture)
    assert any(row["rule_id"] == "carbon.modules" and row["severity"] == "missing"
               and "A1A3" in row["missing_modules"] for row in report["findings"])
    assert report["readiness"]["carbon_inputs"]["status"] == "blocked"


def test_deliberate_wall_deviation_is_reported_without_repairing_layers(catalogue, fixture):
    probe = CASES["residential_wall_deviation_probe"]
    payload = catalogue.resolved_dict()
    config = payload["archetypes"][probe["archetype_id"]]["states"][probe["state"]]
    eid = payload["construction_sets"][config["construction_set_id"]]["elements"][probe["role"]]
    layers = [payload["layers"][slot["layer_id"]]
              for cid in payload["elements"][eid]["components"]
              for slot in payload["components"][cid]["layers"]]
    layer = next(layer for layer in layers if any(
        row["material_id"] == probe["material_id"] for row in layer["materials"]))
    assert layer["thickness"] == probe["accepted_layer_depth_m"]
    layer["thickness"] = probe["deliberate_layer_depth_m"]
    for row in layer["materials"]:
        row["thickness"] = probe["deliberate_layer_depth_m"]
    changed = deepcopy(payload)
    report = check_catalogue(payload, fixture=fixture)
    failures = [row for row in report["findings"] if row["rule_id"] == probe["expected_rule"]
                and row["expected"].get("element") == probe["role"]
                and any(user["archetype_id"] == probe["archetype_id"]
                        and user["state"] == probe["state"]
                        for user in row["affected_archetypes"])]
    assert failures and all(row["severity"] == probe["expected_severity"] for row in failures)
    assert all(row["expected"]["relative_tolerance"] == .2 for row in failures)
    assert payload == changed
    original = catalogue.resolved_dict()
    original_layers = [original["layers"][slot["layer_id"]]
                       for cid in original["elements"][eid]["components"]
                       for slot in original["components"][cid]["layers"]]
    assert any(row["thickness"] == probe["accepted_layer_depth_m"]
               and any(material["material_id"] == probe["material_id"]
                       for material in row["materials"]) for row in original_layers)


def test_corrected_residential_wall_reference_cases_pass_without_widening_tolerance(catalogue, fixture):
    from epsm_data import BuildingElement

    report = catalogue.sanity_report(fixture=fixture)
    assert fixture["policy"]["u_value_relative_tolerance"] == 0.2
    for case in CASES["residential_wall_reference_passes"]:
        wall = catalogue.get(case["archetype_id"], state=case["state"]).construction_set.elements[
            BuildingElement.EXT_WALL
        ]
        assert wall.u_value == pytest.approx(case["actual_u_w_m2k"], rel=1e-12)
        assert abs(wall.u_value / case["expected_u_w_m2k"] - 1) <= 0.2
        failures = [
            row for row in report["findings"]
            if row["rule_id"] in {"tabula.u_value", "tabula.reference_missing", "tabula.calculation"}
            and row.get("expected", {}).get("element") == "EXT_WALL"
            and any(user["archetype_id"] == case["archetype_id"] and user["state"] == case["state"]
                    for user in row["affected_archetypes"])
        ]
        assert not failures

def test_one_zone_reference_failure_does_not_mark_other_zones(catalogue, fixture):
    custom = deepcopy(fixture)
    target = next(row for row in custom["u_values"] if row["category"] == "single_family"
                  and row["era"] == "SE.01" and row["state"] == "existing")
    actual = catalogue.get("sf_se01").construction_set.elements
    from epsm_data import BuildingElement

    value = actual[BuildingElement.EXT_WALL].u_value
    target["elements"]["EXT_WALL"]["values_w_m2k"] = {
        "SE.Zone1": value / 2, "SE.Zone2": value, "SE.Zone3": value
    }
    report = check_catalogue(catalogue, fixture=custom)
    matches = [row for row in report["findings"] if row["rule_id"] == "tabula.u_value"
               and "EXT_WALL" in json.dumps(row)
               and any(user["archetype_id"] == "sf_se01" and user["state"] == "existing"
                       for user in row["affected_archetypes"])]
    assert matches
    assert {zone for row in matches for user in row["affected_archetypes"]
            for zone in user["climate_zones"]} == {"SE.Zone1"}


def test_se07_extra_state_is_an_error_even_for_raw_unloadable_input(catalogue, fixture):
    payload = catalogue.resolved_dict()
    payload["archetypes"]["mf_se07"]["states"]["standard"] = deepcopy(
        payload["archetypes"]["mf_se07"]["states"]["default"]
    )
    report = check_catalogue(payload, fixture=fixture)
    assert any(row["rule_id"] == "catalogue.se07" and row["severity"] == "error"
               for row in report["findings"])


def test_generic_fallback_contract_is_checked(catalogue, fixture, monkeypatch):
    original = catalogue.for_year

    def wrong_donor(category, year, *, state=None):
        return original("single_family" if category == "generic" else category, year, state=state)

    monkeypatch.setattr(catalogue, "for_year", wrong_donor)
    report = catalogue.sanity_report(fixture=fixture)
    matches = [row for row in report["findings"] if row["rule_id"] == "generic.fallback"]
    assert matches and all(row["generic_fallback_affected"] for row in matches)


def test_cli_uses_selected_fixture_and_reports_errors_without_requiring_valid_load(tmp_path, catalogue, capsys):
    payload = catalogue.resolved_dict()
    payload["materials"]["material:4857e866ed223064"]["thermal_id"] = "missing-reference"
    source = tmp_path / "catalogue.json"
    source.write_text(json.dumps(payload))
    assert main(["--sanity", "--fixture", str(FIXTURE), "--path", str(source), "--check"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["fixture_id"] == "epsm-catalogue-sanity"
    assert any(row["rule_id"] == "reference.dangling" for row in report["findings"])
    assert main(["--sanity", "--fixture", str(FIXTURE), "--path", str(source)]) == 0
    capsys.readouterr()


def test_bad_fixture_is_not_silently_replaced_with_an_arbitrary_default(catalogue, fixture):
    changed = deepcopy(fixture)
    changed["policy"]["u_value_relative_tolerance"] = None
    with pytest.raises(ValueError, match="policy"):
        check_catalogue(catalogue, fixture=changed)


@pytest.mark.parametrize("value", [[], {}])
def test_malformed_topology_returns_diagnostics(catalogue, fixture, value):
    payload = catalogue.resolved_dict()
    payload["archetypes"]["sf_se01"]["states"]["existing"]["roof_topology"] = value
    report = check_catalogue(payload, fixture=fixture)
    assert any(row["rule_id"] == "construction.boundary" and row["severity"] == "error"
               for row in report["findings"])


@pytest.mark.parametrize("field", ["weather_shell_element_id", "envelope_performance", "reference_height_m"])
def test_required_configuration_gaps_are_not_lost(catalogue, fixture, field):
    payload = catalogue.resolved_dict()
    del payload["archetypes"]["sf_se01"]["states"]["existing"][field]
    report = check_catalogue(payload, fixture=fixture)
    assert any(field in row["path"] and row["severity"] == "missing" for row in report["findings"])
    assert report["readiness"]["thermal_inputs"]["missing_count"] > 0


def test_unknown_thermal_source_blocks_thermal_readiness(catalogue, fixture):
    payload = catalogue.resolved_dict()
    payload["materials"]["material:3035359c17bff54b"]["thermal_id"] = None
    report = check_catalogue(payload, fixture=fixture)
    assert report["readiness"]["thermal_inputs"]["status"] == "blocked"


def test_invalid_nonfinite_identity_is_still_json_portable(catalogue, fixture):
    payload = catalogue.resolved_dict()
    payload["dataset_id"] = float("nan")
    report = check_catalogue(payload, fixture=fixture)
    assert report["dataset_id"] == "nan"
    assert json.loads(json.dumps(report, allow_nan=False)) == report


@pytest.mark.parametrize("change", ["construction_tables", "generic_donor", "generic_label"])
def test_malformed_or_contradictory_fixture_is_rejected_before_checks(catalogue, fixture, change):
    changed = deepcopy(fixture)
    if change == "construction_tables":
        changed["construction_rules"] = {"schema_version": 1}
    elif change == "generic_donor":
        changed["policy"]["generic_fallback"]["donor_category"] = "single_family"
    else:
        changed["policy"]["generic_fallback"]["assumption_label"] = "An average"
    with pytest.raises(ValueError, match="fixture"):
        check_catalogue(catalogue, fixture=changed)


def test_unused_duplicate_reports_the_original_shared_definition_users(catalogue, fixture):
    payload = catalogue.resolved_dict()
    payload["materials"]["material:unused_duplicate"] = deepcopy(payload["materials"]["material:4857e866ed223064"])
    report = check_catalogue(payload, fixture=fixture)
    findings = [row for row in report["findings"] if row["rule_id"] == "definition.duplicate"
                and row["path"].endswith("material:unused_duplicate")]
    assert findings
    assert {user["archetype_id"] for user in findings[0]["affected_archetypes"]} == {
        "office_se01", "school_se01"
    }
