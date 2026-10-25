"""Retained-stock carbon scope requires proof and never manufactures LCA factors."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from epsm_data import Catalogue, export_nominal_constructions
from epsm_data.carbon_scope import retained_stock_assessments
from epsm_data.sanity import check_catalogue

CASE = json.loads((Path(__file__).parent / "fixtures/catalogue_sanity/cases/retained_stock_carbon.json").read_text())
STOCK = tuple(row["id"] for row in CASE["stock_materials"])


def _synthetic():
    return deepcopy(CASE["synthetic"])


def _declared_payload():
    data = Catalogue.load().resolved_dict()
    for mid in STOCK:
        data["materials"][mid].pop("boverket_id", None)
        data["materials"][mid].pop("carbon_reference_id", None)
        data["materials"][mid]["carbon_assessment"] = deepcopy(CASE["declaration"])
    return data


def test_shared_baseline_occurrences_and_new_other_products_can_qualify():
    assessment = retained_stock_assessments(_synthetic())["stock"]
    assert assessment["eligible"]
    assert assessment["archetypes"] == ("example",)
    assert assessment["issue"] is None


def test_single_default_configuration_can_qualify_without_renovation_states():
    data = _synthetic()
    data["archetypes"]["example"]["states"] = {"default": {"construction_set_id": "baseline"}}
    assert retained_stock_assessments(data)["stock"]["eligible"]


@pytest.mark.parametrize("declaration", [None, {}, {"status": "retained_existing_unmapped"},
    {"status": "retained_existing_unmapped", "reason": " "},
    {"status": "new_product", "reason": "It happens to be used in a renovation."}])
def test_incomplete_or_wrong_declarations_never_waive_sources(declaration):
    data = _synthetic()
    data["materials"]["stock"]["carbon_assessment"] = declaration
    assert not retained_stock_assessments(data)["stock"]["eligible"]


@pytest.mark.parametrize("field,value", [("boverket_id", "6000000000"),
    ("carbon_reference_id", "test:epd"), ("non_product", True),
    ("embodied_carbon", {"A1A3": 0})])
def test_existing_stock_cannot_also_claim_source_factors_or_non_product_exemption(field, value):
    data = _synthetic()
    data["materials"]["stock"][field] = value
    assessment = retained_stock_assessments(data)["stock"]
    assert not assessment["eligible"] and assessment["issue"]


@pytest.mark.parametrize("change", ["added_occurrence", "new_role", "relocated", "changed_layer",
                                   "introduced", "removed", "weather_shell", "broken_reference"])
def test_stock_tags_cannot_hide_changed_or_unproven_occurrences(change):
    data = _synthetic()
    element = data["elements"]["renovated"]
    if change == "added_occurrence":
        element["components"].append("original_stock")
    elif change == "new_role":
        data["construction_sets"]["renovation"]["elements"]["INT_WALL_NONLOADBEARING"] = "original"
    elif change == "relocated":
        element["components"] = ["original_stock", "original_outer", "addition"]
    elif change == "changed_layer":
        data["layers"]["changed"] = deepcopy(data["layers"]["stock_layer"])
        data["layers"]["changed"]["thickness"] = 0.2
        data["layers"]["changed"]["materials"][0]["thickness"] = 0.2
        data["components"]["changed"] = {"layers": [{"layer_id": "changed", "position": 0}]}
        element["components"][-1] = "changed"
    elif change == "introduced":
        data["elements"]["original"]["components"] = ["original_outer"]
    elif change == "removed":
        element["components"] = ["addition", "original_outer"]
    elif change == "weather_shell":
        data["archetypes"]["example"]["states"]["advanced"]["weather_shell_element_id"] = "original"
    elif change == "broken_reference":
        element["components"].append("missing_component")
    assessment = retained_stock_assessments(data)["stock"]
    assert not assessment["eligible"] and assessment["issue"]


def test_missing_baseline_and_unused_records_do_not_prove_stock():
    data = _synthetic()
    del data["archetypes"]["example"]["states"]["existing"]
    assert not retained_stock_assessments(data)["stock"]["eligible"]
    data = _synthetic()
    for element in data["elements"].values():
        element["components"] = ["original_outer"]
    assert not retained_stock_assessments(data)["stock"]["eligible"]


def test_real_shared_materials_require_every_affected_archetype_and_keep_carbon_unknown():
    data = _declared_payload()
    assessment = retained_stock_assessments(data)
    catalogue = Catalogue(data)
    for row in CASE["stock_materials"]:
        mid = row["id"]
        assert assessment[mid]["eligible"]
        assert list(assessment[mid]["archetypes"]) == row["archetypes"]
        material = catalogue.materials[mid]
        assert material.boverket_id is None
        assert material.carbon_reference is None
        assert material.embodied_carbon is None
        assert {key: material.to_dict()[key] for key in data["materials"][mid]["properties"]} == (
            data["materials"][mid]["properties"])
        for aid in row["archetypes"]:
            for state in catalogue.renovation_states(aid) or (None,):
                completeness = catalogue.completeness(aid, state=state)
                assert f"materials.{mid}.boverket_id" not in completeness["missing_values"]
                assert any(mid in note and "without quantified carbon" in note
                           for note in catalogue.get(aid, state=state).notes)
    sand = catalogue.materials["material:4857e866ed223064"]
    assert sand.carbon_reference.identifier == "EPD-IES-0005222:003"
    assert dict(sand.carbon_reference.modules) == {"A1A3": 0.002, "A4": None, "A5": None}
    bundle = export_nominal_constructions(catalogue.get("mf_se01"))
    for ref in bundle["material_references"].values():
        if ref.get("json_id") in STOCK:
            assert ref["boverket_id"] is None
            assert not ref.get("carbon_reference_id") and not ref.get("carbon_reference")


def test_sanity_reports_contextual_stock_review_and_all_affected_families():
    report = check_catalogue(_declared_payload())
    for case in CASE["stock_materials"]:
        path = f"materials.{case['id']}"
        rows = [row for row in report["findings"] if row["path"] == path]
        stock = next(row for row in rows if row["rule_id"] == "carbon.existing_stock")
        assert stock["severity"] == "review"
        assert "unquantified" in stock["expected"]
        assert {row["archetype_id"] for row in stock["affected_archetypes"]} == set(case["archetypes"])
        assert not any(row["rule_id"] == "carbon.source" for row in rows)
    assert report["readiness"]["carbon_inputs"]["status"] != "pass"


def test_a_new_real_occurrence_revokes_the_exception_and_reports_missing_source():
    data = _declared_payload()
    aid, state, mid = "mf_se01", "advanced", STOCK[0]
    config = data["archetypes"][aid]["states"][state]
    construction = data["construction_sets"][config["construction_set_id"]]
    eid = construction["elements"]["TOP_FLOOR"]
    element = deepcopy(data["elements"][eid])
    stock_component = next(cid for cid in element["components"]
                           if any(share["material_id"] == mid
                                  for slot in data["components"][cid]["layers"]
                                  for share in data["layers"][slot["layer_id"]]["materials"]))
    element["components"].append(stock_component)
    data["elements"]["test:new_stock_occurrence"] = element
    construction["elements"]["TOP_FLOOR"] = "test:new_stock_occurrence"
    assert not retained_stock_assessments(data)[mid]["eligible"]
    catalogue = Catalogue(data)
    assert f"materials.{mid}.boverket_id" in catalogue.completeness(aid, state=state)["missing_values"]
    findings = catalogue.sanity_report()["findings"]
    assert any(row["rule_id"] == "carbon.existing_stock_invalid" and row["severity"] == "error"
               and row["path"] == f"materials.{mid}.carbon_assessment" for row in findings)
    assert any(row["rule_id"] == "carbon.source" and row["severity"] == "missing"
               and row["path"] == f"materials.{mid}" for row in findings)


def test_untagged_unknown_product_still_requires_carbon_source():
    data = _declared_payload()
    mid = STOCK[0]
    del data["materials"][mid]["carbon_assessment"]
    catalogue = Catalogue(data)
    assert f"materials.{mid}.boverket_id" in catalogue.completeness("mf_se01")["missing_values"]
    assert any(row["rule_id"] == "carbon.source" and row["path"] == f"materials.{mid}"
               for row in catalogue.sanity_report()["findings"])


@pytest.mark.parametrize("conflict", ["boverket_id", "non_product"])
def test_invalid_stock_source_or_exemption_conflicts_are_visible_and_never_waived(conflict):
    data = _declared_payload()
    mid = STOCK[0]
    data["materials"][mid][conflict] = "6000000089" if conflict == "boverket_id" else True
    catalogue = Catalogue(data)
    findings = catalogue.sanity_report()["findings"]
    assert any(row["rule_id"] == "carbon.existing_stock_invalid" and row["severity"] == "error"
               and row["path"] == f"materials.{mid}.carbon_assessment" for row in findings)
    assert not any(row["rule_id"] == "carbon.existing_stock"
                   and row["path"] == f"materials.{mid}" for row in findings)
    if conflict == "non_product":
        assert f"materials.{mid}.boverket_id" in catalogue.completeness("mf_se01")["missing_values"]
        assert any(row["rule_id"] == "carbon.source" and row["severity"] == "missing"
                   and row["path"] == f"materials.{mid}" for row in findings)
