"""Independent reference expectations and mutations of catalogue constructions."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from epsm_data import Catalogue
from epsm_data.sanity_reference import check_references

_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _ROOT / "src/epsm_data/datasets/sanity"
_CASES = _ROOT / "tests/fixtures/sanity_cases"


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture
def references():
    result = {}
    for filename in ("tabula_u_values.json", "tabula_renovations.json"):
        result.update(json.loads((_FIXTURES / filename).read_text()))
    result["policy"] = json.loads((_FIXTURES / "policy.json").read_text())["policy"]
    return result


def _run(data, catalogue, references):
    findings = []

    def emit(rule_id, severity, path, message, **details):
        findings.append({"rule_id": rule_id, "severity": severity,
                         "path": path, "message": message, **details})

    check_references(data, catalogue, emit, references)
    return findings


def _focused(catalogue, aid="sf_se01"):
    data = catalogue.resolved_dict()
    data["archetypes"] = {aid: data["archetypes"][aid]}
    return data


def _matching(findings, rule, state=None):
    return [f for f in findings if f["rule_id"] == rule
            and (state is None or any(s.endswith(":" + state) for s in f["affected"]))]


def _wall_package(references):
    refs = deepcopy(references)
    row = next(p for p in refs["renovation_packages"]
               if p["category"] == "single_family" and p["era"] == "SE.01"
               and p["state"] == "standard")
    code = row["measures"]["EXT_WALL"]
    row["measures"] = {"EXT_WALL": code}
    refs["measures"][code]["nominal_added_insulation_m"] = 0.045
    refs["measures"][code]["required_finish"] = None
    return refs, code


def test_reference_fixtures_are_finite():
    for name in ("tabula_u_values.json", "tabula_renovations.json"):
        json.dumps(json.loads((_FIXTURES / name).read_text()), allow_nan=False)


def test_reference_table_covers_residential_five_eras_all_states_zones(references):
    rows = references["u_values"]
    assert len(rows) == 30
    assert {(r["category"], r["era"], r["state"]) for r in rows} == {
        (category, f"SE.{era:02d}", state)
        for category in ("single_family", "multi_family")
        for era in range(1, 6) for state in ("existing", "standard", "advanced")
    }
    for row in rows:
        for target in row["elements"].values():
            assert set(target["values_w_m2k"]) == {"SE.Zone1", "SE.Zone2", "SE.Zone3"}
            assert all("TABULA.xlsm#'Calc.Building.Set'!" in locator
                       for locator in target["source_locators"].values())


def test_fixture_values_are_independent_retained_workbook_extracts(references):
    original = json.loads((_ROOT / "evidence/betsi_review/audit.json").read_text())
    source = {(r["category"], r["era"], r["state"], r["property"], r["source_variant"]): r
              for r in original["tabula_zone_comparisons"]}
    for row in references["u_values"]:
        for target in row["elements"].values():
            raw = source[(row["category"], row["era"], row["state"],
                          target["source_property"], target["source_variants"][0])]
            assert target["values_w_m2k"] == raw["values"]
            assert target["source_locators"] == raw["locators"]


def test_reviewed_catalogue_has_no_direct_thermal_disagreements(catalogue, references):
    findings = _run(catalogue.resolved_dict(), catalogue, references)
    # Source targets and 20% tolerance remain fixed. Ground-effective comparisons
    # remain explicitly unassessed; separate mutation tests exercise failures.
    assert not _matching(findings, "tabula.u_value")


def test_twenty_percent_boundary_inclusive_and_small_excess_fails(catalogue, references):
    data = _focused(catalogue)
    cfg = data["archetypes"]["sf_se01"]["states"]["existing"]
    eid = data["construction_sets"][cfg["construction_set_id"]]["elements"]["EXT_WALL"]
    actual = catalogue.elements[eid].u_value
    row = next(r for r in references["u_values"] if r["category"] == "single_family"
               and r["era"] == "SE.01" and r["state"] == "existing")
    target = row["elements"]["EXT_WALL"]
    target["values_w_m2k"] = dict.fromkeys(target["values_w_m2k"], actual / 1.2)
    failures = _matching(_run(data, catalogue, references), "tabula.u_value", "existing")
    assert not any(f["expected"]["element"] == "EXT_WALL" for f in failures)
    target["values_w_m2k"] = dict.fromkeys(target["values_w_m2k"], actual / 1.20001)
    failures = _matching(_run(data, catalogue, references), "tabula.u_value", "existing")
    assert any(f["expected"]["element"] == "EXT_WALL" for f in failures)


def test_missing_source_or_calculation_does_not_pass(catalogue, references):
    data = _focused(catalogue)
    row = next(r for r in references["u_values"] if r["category"] == "single_family"
               and r["era"] == "SE.01" and r["state"] == "existing")
    row["elements"]["EXT_WALL"]["source_locators"].pop("SE.Zone1")
    findings = _run(data, None, references)
    assert any(f["affected"] == ["single_family:SE.01:SE.Zone1:existing"]
               for f in _matching(findings, "tabula.reference_missing"))
    assert _matching(findings, "tabula.calculation")
    assert not _matching(findings, "tabula.u_value")


def test_cold_attic_compares_thermal_floor_not_weather_roof(catalogue, references):
    data = _focused(catalogue)
    cfg = data["archetypes"]["sf_se01"]["states"]["existing"]
    elements = data["construction_sets"][cfg["construction_set_id"]]["elements"]
    # Deliberately disagree so the reported physical boundary can be inspected.
    target = next(row for row in references["u_values"]
                  if (row["category"], row["era"], row["state"])
                  == ("single_family", "SE.01", "existing"))["elements"]["THERMAL_TOP"]
    target["values_w_m2k"] = dict.fromkeys(target["values_w_m2k"], 0.01)
    findings = _matching(_run(data, catalogue, references), "tabula.u_value", "existing")
    top = next(f for f in findings if f["expected"]["element"] == "THERMAL_TOP")
    assert top["actual"]["u_value_w_m2k"] == catalogue.elements[elements["TOP_FLOOR"]].u_value
    assert top["path"] != f"elements.{cfg['weather_shell_element_id']}"
    elements["ROOF"] = elements.pop("TOP_FLOOR")
    findings = _run(data, catalogue, references)
    assert any(f["expected"].get("element") == "THERMAL_TOP"
               for f in _matching(findings, "tabula.boundary_not_assessed", "existing"))


def _mf01_mapped_data(catalogue):
    data = _focused(catalogue, "mf_se01")
    for config in data["archetypes"]["mf_se01"]["states"].values():
        for role, logical, physical in (
            ("GROUND_FLOOR", "GROUND_FLOOR", "conditioned_basement_floor"),
            ("BASEMENT_WALL", "TABULA_WALL_2", "conditioned_basement_wall"),
        ):
            config["boundary_details"][role].update(
                physical_boundary="soil", physical_role=physical, source_mapping=logical,
                value_meaning="nominal_material_layers_not_effective_ground_u",
                layer_order="outside_to_inside",
            )
    return data


def _mf01_wall_measure_case(catalogue, references):
    """Synthetic internal addition, independent of the accepted wall recipe."""
    data = _mf01_mapped_data(catalogue)
    refs = deepcopy(references)
    package = next(row for row in refs["renovation_packages"]
                   if (row["category"], row["era"], row["state"])
                   == ("multi_family", "SE.01", "advanced"))
    package["measures"] = {"TABULA_WALL_2": package["measures"]["TABULA_WALL_2"]}
    states = data["archetypes"]["mf_se01"]["states"]
    baseline = data["construction_sets"][states["existing"]["construction_set_id"]]["elements"]
    elements = data["construction_sets"][states["advanced"]["construction_set_id"]]["elements"]
    data["materials"]["test:insulation"] = {
        "name": "Synthetic mineral insulation", "properties": {"conductivity": 0.036},
    }
    data["layers"]["test:layer"] = {
        "thickness": 0.04,
        "materials": [{"material_id": "test:insulation", "thickness": 0.04,
                       "area_fraction": 1.0}],
    }
    data["components"]["test:component"] = {
        "layers": [{"layer_id": "test:layer", "position": 0}],
    }
    data["elements"]["test:wall"] = deepcopy(data["elements"][baseline["BASEMENT_WALL"]])
    data["elements"]["test:wall"]["components"].append("test:component")
    elements["BASEMENT_WALL"] = "test:wall"
    return data, refs


def test_evidenced_mf01_ground_mapping_keeps_incompatible_sources_unassessed(catalogue, references):
    findings = _run(_mf01_mapped_data(catalogue), catalogue, references)
    unassessed = _matching(findings, "tabula.boundary_not_assessed")
    assert len(unassessed) == 6
    assert {f["actual"]["element"] for f in unassessed} == {"GROUND_FLOOR", "TABULA_WALL_2"}
    assert all(f["severity"] == "review" for f in unassessed)
    assert all(f["actual"]["status"] == "source_incompatible" for f in unassessed)
    assert all(f["actual"]["nominal_u_w_m2k"] > 0 for f in unassessed)
    assert {f["actual"]["catalogue_role"] for f in unassessed} == {"GROUND_FLOOR", "BASEMENT_WALL"}
    reviews = _matching(findings, "tabula.source_convention")
    assert len(reviews) == 6
    assert all(f["actual"]["nominal_u_w_m2k"] > 0 for f in reviews)
    assert all(f["severity"] == "review" and f["actual"]["mapping_status"] == "resolved"
               and f["expected"]["source_locators"] for f in reviews)
    assert not any(f["expected"].get("element") in {"GROUND_FLOOR", "TABULA_WALL_2"}
                   for f in _matching(findings, "tabula.u_value"))


@pytest.mark.parametrize("field", ["physical_boundary", "physical_role", "source_mapping",
                                   "value_meaning", "layer_order"])
@pytest.mark.parametrize("bad_value", [None, "incorrect"])
def test_mf01_measure_mapping_requires_matching_physical_boundary(catalogue, references, field, bad_value):
    data, refs = _mf01_wall_measure_case(catalogue, references)
    config = data["archetypes"]["mf_se01"]["states"]["advanced"]
    if bad_value is None:
        config["boundary_details"]["BASEMENT_WALL"].pop(field)
    else:
        config["boundary_details"]["BASEMENT_WALL"][field] = bad_value
    findings = _run(data, catalogue, refs)
    assert _matching(findings, "tabula.measure_mapping", "advanced")
    wall = next(f for f in _matching(findings, "tabula.boundary_not_assessed", "advanced")
                if f["actual"]["element"] == "TABULA_WALL_2")
    assert wall["actual"]["status"] == "boundary_mapping_missing"


@pytest.mark.parametrize("mutation", ["missing", "status", "reason", "locators", "extra", "role"])
def test_mf01_unknown_or_incomplete_source_descriptor_cannot_authorize_wall_mapping(
    catalogue, references, mutation,
):
    data, refs = _mf01_wall_measure_case(catalogue, references)
    reference = next(row for row in refs["u_values"]
                     if (row["category"], row["era"], row["state"])
                     == ("multi_family", "SE.01", "advanced"))
    target = reference["elements"]["TABULA_WALL_2"]
    descriptor = target["boundary_comparison"]
    if mutation == "missing":
        target.pop("boundary_comparison")
    elif mutation == "status":
        descriptor["status"] = "accepted"
    elif mutation == "reason":
        descriptor["reason"] = ""
    elif mutation == "locators":
        descriptor["source_locators"] = []
    elif mutation == "extra":
        descriptor["u_value_override"] = 0.1
    else:
        descriptor["catalogue_role"] = "EXT_WALL"
    findings = _run(data, catalogue, refs)
    assert _matching(findings, "tabula.measure_mapping", "advanced")
    assert any(f["actual"]["element"] == "TABULA_WALL_2"
               for f in _matching(findings, "tabula.boundary_not_assessed", "advanced"))


def test_mf01_internal_measure_is_checked_across_components(catalogue, references):
    data, refs = _mf01_wall_measure_case(catalogue, references)
    findings = _run(data, catalogue, refs)
    assert not _matching(findings, "tabula.measure_mapping", "advanced")
    assert not _matching(findings, "tabula.measure_thickness", "advanced")
    assert not _matching(findings, "tabula.measure_placement", "advanced")
    components = data["elements"]["test:wall"]["components"]
    components.insert(0, components.pop())
    misplaced = _matching(_run(data, catalogue, refs), "tabula.measure_placement", "advanced")
    assert len(misplaced) == 1 and misplaced[0]["severity"] == "error"
    assert misplaced[0]["expected"]["placement"] == "interior_or_warm_side"
    assert misplaced[0]["expected"]["placement_source_locator"]


def test_package_override_cannot_rewrite_physical_reference_expectations(catalogue, references):
    data, refs = _mf01_wall_measure_case(catalogue, references)
    package = next(row for row in refs["renovation_packages"]
                   if (row["category"], row["era"], row["state"])
                   == ("multi_family", "SE.01", "advanced"))
    override = package["measure_overrides"]["TABULA_WALL_2"]
    override["nominal_added_insulation_m"] = 0.999
    findings = _matching(_run(data, catalogue, refs), "tabula.reference_missing", "advanced")
    assert len(findings) == 1 and findings[0]["severity"] == "missing"
    assert set(findings[0]["expected"]["allowed_fields"]) == {"placement", "placement_source_locator"}


@pytest.mark.parametrize("aid", ["mf_se02", "mf_se03", "mf_se04", "mf_se05"])
def test_reviewed_basement_boundaries_require_explicit_era_mapping(catalogue, references, aid):
    findings = _run(_focused(catalogue, aid), catalogue, references)
    conventions = _matching(findings, "tabula.source_convention")
    assert len(conventions) == 6
    assert all(f["severity"] == "review" and f["actual"]["mapping_status"] == "resolved"
               for f in conventions)
    assert not _matching(findings, "tabula.measure_mapping", "advanced")
    unassessed = _matching(findings, "tabula.boundary_not_assessed")
    assert len(unassessed) == 6
    assert all(f["severity"] == "review" and f["actual"]["status"] == "source_incompatible"
               for f in unassessed)
    assert {(f["actual"]["element"], f["actual"]["catalogue_role"]) for f in unassessed} == {
        ("GROUND_FLOOR", "GROUND_FLOOR"), ("TABULA_WALL_2", "BASEMENT_WALL"),
    }


def test_unreviewed_mf06_does_not_infer_second_wall_mapping(catalogue, references):
    from epsm_data.sanity_reference import _mapped_boundary_role

    data = _focused(catalogue, "mf_se06")
    configs = data["archetypes"]["mf_se06"]["states"]
    assert not any("source_mapping" in config["boundary_details"]["BASEMENT_WALL"]
                   for config in configs.values())
    assert not any(row["category"] == "multi_family" and row["era"] == "SE.06"
                   for row in references["u_values"])
    # A reviewed era's source descriptor cannot supply missing physical metadata
    # to a different configuration merely because it has a basement-wall role.
    for state, config in configs.items():
        elements = data["construction_sets"][config["construction_set_id"]]["elements"]
        reviewed = next(row for row in references["u_values"]
                        if (row["category"], row["era"], row["state"])
                        == ("multi_family", "SE.02", state))
        for role in ("GROUND_FLOOR", "TABULA_WALL_2"):
            assert _mapped_boundary_role(config, elements, role, reviewed["elements"][role]) is None
    findings = _run(data, catalogue, references)
    assert not _matching(findings, "tabula.source_convention")
    coverage = _matching(findings, "era.reference_coverage")
    assert len(coverage) == 3
    assert all(f["severity"] == "review" and f["actual"]["status"] == "not_assessed"
               for f in coverage)


def test_ground_project_limitations_cover_all_authored_configurations_without_generic_duplicates(
    catalogue, references,
):
    expected = json.loads((_CASES / "reporting.json").read_text())["ground_project_limitations"]
    findings = _run(catalogue.resolved_dict(), catalogue, references)
    limitations = _matching(findings, expected["rule_id"])
    assert len(limitations) == expected["authored_configuration_count"]
    assert len({f["path"].split(".")[1] for f in limitations}) == expected["authored_family_count"]
    assert all(f["severity"] == expected["severity"] for f in limitations)
    assert all(len(f["affected"]) == expected["climate_zones_per_configuration"]
               for f in limitations)
    assert all(f["actual"]["nominal_u_w_m2k"] > 0
               and f["actual"]["status"] == "project_inputs_required" for f in limitations)
    assert all(f["expected"]["required_project_inputs"] == expected["required_project_inputs"]
               and f["expected"]["benchmark_agreement_assessed"] is expected["comparison_is_pass"]
               and f["expected"]["catalogue_ground_factors_added"] is False for f in limitations)
    assert not any("generic" in f["path"] for f in limitations)
    assert not _matching(findings, expected["unresolved_definition_rule"])
    assert references["policy"]["ground_assessment"]["project_input_severity"] == "review"
    assert references["policy"]["ground_assessment"]["unassessed_is_pass"] is False


@pytest.mark.parametrize("defect", ["missing_role", "wrong_role", "missing_element", "missing_layers",
                                     "unavailable_calculation"])
def test_unresolved_ground_fabric_remains_blocking(catalogue, references, defect):
    expected = json.loads((_CASES / "reporting.json").read_text())["ground_project_limitations"]
    data = _focused(catalogue)
    config = data["archetypes"]["sf_se01"]["states"]["existing"]
    elements = data["construction_sets"][config["construction_set_id"]]["elements"]
    identifier = elements["GROUND_FLOOR"]
    calculation = catalogue
    if defect == "missing_role":
        elements.pop("GROUND_FLOOR")
    elif defect == "wrong_role":
        data["elements"][identifier]["role"] = "EXT_WALL"
    elif defect == "missing_element":
        data["elements"].pop(identifier)
    elif defect == "missing_layers":
        data["elements"][identifier]["components"] = []
    else:
        calculation = None
    findings = _run(data, calculation, references)
    unresolved = _matching(findings, expected["unresolved_definition_rule"], "existing")
    assert len(unresolved) == 1
    assert unresolved[0]["severity"] == expected["unresolved_definition_severity"]
    assert unresolved[0]["actual"]["status"] == "definition_unresolved"
    assert unresolved[0]["actual"]["nominal_u_w_m2k"] is None
    assert not _matching(findings, expected["rule_id"], "existing")
    ground = next(f for f in _matching(findings, "tabula.boundary_not_assessed", "existing")
                  if f["actual"].get("element") == "GROUND_FLOOR")
    assert ground["severity"] == "missing"


def test_ground_reference_limitation_never_accepts_or_rejects_nominal_u_against_effective_u(
    catalogue, references,
):
    data = _focused(catalogue)
    reference = next(row for row in references["u_values"]
                     if (row["category"], row["era"], row["state"])
                     == ("single_family", "SE.01", "existing"))
    reference["elements"]["GROUND_FLOOR"]["values_w_m2k"] = dict.fromkeys(
        ("SE.Zone1", "SE.Zone2", "SE.Zone3"), 999.0,
    )
    findings = _run(data, catalogue, references)
    ground = next(f for f in _matching(findings, "tabula.boundary_not_assessed", "existing")
                  if f["actual"].get("element") == "GROUND_FLOOR")
    assert ground["severity"] == "review"
    assert ground["actual"]["nominal_u_w_m2k"] > 0
    assert ground["actual"]["status"] == "project_boundary_required"
    assert ground["expected"]["benchmark_agreement_assessed"] is False
    assert not any(f["expected"].get("element") == "GROUND_FLOOR"
                   for f in _matching(findings, "tabula.u_value", "existing"))


def test_insulation_measure_checks_added_depth_not_u_measure(catalogue, references):
    data = _focused(catalogue)
    refs, code = _wall_package(references)
    refs["measures"][code]["U_measure"] = 9999
    findings = _run(data, catalogue, refs)
    assert not any(f["expected"].get("code") == code
                   for f in _matching(findings, "tabula.measure_thickness", "standard"))
    refs["measures"][code]["nominal_added_insulation_m"] = 0.115
    findings = _run(data, catalogue, refs)
    assert any(f["actual"]["added_insulation_m"] == 0.045
               for f in _matching(findings, "tabula.measure_thickness", "standard"))


def test_measure_placement_checks_across_component_interfaces(catalogue, references):
    data = _focused(catalogue)
    refs, _ = _wall_package(references)
    cfg = data["archetypes"]["sf_se01"]["states"]["standard"]
    eid = data["construction_sets"][cfg["construction_set_id"]]["elements"]["EXT_WALL"]
    components = data["elements"][eid]["components"]
    components.append(components.pop(0))
    findings = _matching(_run(data, catalogue, refs), "tabula.measure_placement", "standard")
    assert any(f["severity"] == "error" for f in findings)


def test_required_package_finish_and_window_are_not_optional(catalogue, references):
    data = _focused(catalogue)
    states = data["archetypes"]["sf_se01"]["states"]
    baseline = data["construction_sets"][states["existing"]["construction_set_id"]]["elements"]
    standard = data["construction_sets"][states["standard"]["construction_set_id"]]["elements"]
    # Deliberately omit the finish intervention and replacement window. The
    # accepted catalogue now supplies the window, so do not rely on old defects.
    standard["EXT_WALL"] = baseline["EXT_WALL"]
    standard["WINDOW"] = baseline["WINDOW"]
    states["standard"]["boundary_details"]["EXT_WALL"].pop("layer_order")
    findings = _run(data, catalogue, references)
    assert _matching(findings, "tabula.measure_finish", "standard")
    assert _matching(findings, "tabula.measure_window", "standard")
    assert _matching(findings, "tabula.measure_placement", "standard")


def test_worsened_advanced_and_wholly_ineffective_standard_fail(catalogue, references):
    data = _focused(catalogue)
    states = data["archetypes"]["sf_se01"]["states"]
    states["advanced"]["construction_set_id"] = states["existing"]["construction_set_id"]
    findings = _run(data, catalogue, references)
    assert _matching(findings, "renovation.u_value", "advanced")
    assert _matching(findings, "renovation.improvement", "advanced")
    states["standard"]["construction_set_id"] = states["existing"]["construction_set_id"]
    findings = _run(data, catalogue, references)
    assert _matching(findings, "renovation.improvement", "standard")


def test_unchanged_individual_roles_are_allowed(catalogue, references):
    findings = _run(_focused(catalogue), catalogue, references)
    assert not _matching(findings, "renovation.u_value")
    assert not _matching(findings, "renovation.improvement")


def test_original_year_is_retained_by_renovations(catalogue, references):
    data = _focused(catalogue)
    states = data["archetypes"]["sf_se01"]["states"]
    states["standard"]["construction_year"] = 1990
    finding = _matching(_run(data, catalogue, references), "renovation.construction_year", "standard")
    assert len(finding) == 1 and finding[0]["expected"] == 1950


def test_era_assessment_is_explicit_and_cannot_waive_anachronism(catalogue, references):
    data = _focused(catalogue)
    cfg = data["archetypes"]["sf_se01"]["states"]["existing"]
    cfg.setdefault("sanity_assessment", {}).pop("as_built", None)
    assert _matching(_run(data, catalogue, references), "era.as_built_assessment")
    cfg["sanity_assessment"] = {"as_built": {"rationale": "Representative original AAC baseline.",
                                           "sources": ["evidence/sfh_baseline_user_stacks.txt"]}}
    assert not _matching(_run(data, catalogue, references), "era.as_built_assessment")
    eid = data["construction_sets"][cfg["construction_set_id"]]["elements"]["EXT_WALL"]
    cid = data["elements"][eid]["components"][0]
    lid = data["components"][cid]["layers"][0]["layer_id"]
    mid = data["layers"][lid]["materials"][0]["material_id"]
    data["materials"][mid]["first_use_year"] = 1980
    findings = _matching(_run(data, catalogue, references), "era.material_anachronism")
    assert findings and findings[0]["severity"] == "error"


def test_uncovered_eras_and_nonresidential_are_not_claimed_as_tabula(catalogue, references):
    for aid in ("sf_se06", "sf_se07", "office_se02", "school_se02"):
        findings = _run(_focused(catalogue, aid), catalogue, references)
        assert _matching(findings, "era.reference_coverage")
        assert not _matching(findings, "tabula.u_value")


def test_chronology_is_heuristic_and_advisory_with_no_equality_failure(catalogue, references):
    data = _focused(catalogue)
    findings = _matching(_run(data, catalogue, references), "renovation.chronology")
    assert len(findings) == 2
    assert all(f["severity"] == "review" for f in findings)
    assert all(f["actual"]["comparison_year"] == 1985 for f in findings)
    assert all(f["actual"]["year_basis"] == "construction_year_plus_35_heuristic" for f in findings)
    assert all(f["expected"]["hard_equality_required"] is False for f in findings)
    data["archetypes"]["sf_se01"]["states"]["standard"]["renovation_year"] = 1998
    finding = _matching(_run(data, catalogue, references), "renovation.chronology", "standard")[0]
    assert finding["actual"]["comparison_year"] == 1998
    assert finding["actual"]["year_basis"] == "explicit"
    assert finding["severity"] == "review"


@pytest.mark.parametrize("area", ["states", "boundary_details", "element", "component", "layer", "material"])
def test_incomplete_nested_authoring_records_remain_inspectable(catalogue, references, area):
    data = _focused(catalogue)
    record = data["archetypes"]["sf_se01"]
    if area == "states":
        record["states"] = None
    else:
        config = record["states"]["existing"]
        elements = data["construction_sets"][config["construction_set_id"]]["elements"]
        eid = elements["EXT_WALL"]
        cid = data["elements"][eid]["components"][0]
        lid = data["components"][cid]["layers"][0]["layer_id"]
        mid = data["layers"][lid]["materials"][0]["material_id"]
        if area == "boundary_details":
            config["boundary_details"] = None
        else:
            section, identifier = {"element": ("elements", eid), "component": ("components", cid),
                                   "layer": ("layers", lid), "material": ("materials", mid)}[area]
            data[section][identifier] = None
    findings = _run(data, None, references)
    assert not _matching(findings, "tabula.u_value")
    if area != "states":
        assert any(f["severity"] == "missing" for f in findings)


def test_timber_framing_is_not_tabula_wood_panelling(catalogue, references):
    data = _focused(catalogue)
    refs, code = _wall_package(references)
    refs["measures"][code]["required_finish"] = "wood_panelling"
    cfg = data["archetypes"]["sf_se01"]["states"]["standard"]
    eid = data["construction_sets"][cfg["construction_set_id"]]["elements"]["EXT_WALL"]
    cid = data["elements"][eid]["components"][0]
    lid = data["components"][cid]["layers"][0]["layer_id"]
    timber = "material:3035359c17bff54b"
    # Substitute framing within insulation for the actual continuous panelling.
    insulation_id = data["components"][cid]["layers"][1]["layer_id"]
    insulation = deepcopy(data["layers"][insulation_id])
    insulation["materials"][0]["area_fraction"] = 0.85
    insulation["materials"].append({"material_id": timber, "area_fraction": 0.15,
                                     "thickness": insulation["thickness"]})
    data["layers"][lid] = insulation
    findings = _matching(_run(data, catalogue, refs), "tabula.measure_finish", "standard")
    assert findings and findings[0]["severity"] == "error"


@pytest.mark.parametrize("non_insulation", ["timber", "non_product_air"])
def test_prescribed_insulation_depth_excludes_timber_panelling_and_air(
    catalogue, references, non_insulation,
):
    data = _focused(catalogue)
    refs, code = _wall_package(references)
    config = data["archetypes"]["sf_se01"]["states"]["standard"]
    identifier = data["construction_sets"][config["construction_set_id"]]["elements"]["EXT_WALL"]
    if non_insulation == "non_product_air":
        data["materials"]["test:air"] = {
            "non_product": True, "properties": {"conductivity": 0.026},
        }
        data["layers"]["test:cavity"] = {
            "thickness": 0.025, "materials": [{
                "material_id": "test:air", "area_fraction": 1.0, "thickness": 0.025,
            }],
        }
        data["components"]["test:cavity"] = {
            "layers": [{"layer_id": "test:cavity", "position": 0}],
        }
        data["elements"][identifier]["components"].insert(0, "test:cavity")
    else:
        timber = data["materials"]["material:3035359c17bff54b"]
        assert timber["material_family"] == "timber"
    findings = _run(data, catalogue, refs)
    assert not any(f["expected"].get("code") == code
                   for f in _matching(findings, "tabula.measure_thickness", "standard"))
