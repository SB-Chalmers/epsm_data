"""Shared manual carbon sources preserve known factors and explicit module gaps."""

import json

import pytest

from epsm_data import (
    Catalogue,
    archetype_from_dict,
    archetype_to_dict,
    export_nominal_constructions,
)

SAND = "material:4857e866ed223064"
TAGENE = "EPD-IES-0005222:003"


def test_tagene_proxy_is_shared_without_changing_sand_thermal_properties():
    catalogue = Catalogue.load()
    material = catalogue.materials[SAND]
    reference = catalogue.carbon_references[TAGENE]
    assert material.carbon_reference is reference
    assert material.boverket_id is None
    assert material.embodied_carbon is None
    assert (material.conductivity, material.density, material.specific_heat) == (0.4, 1600, 800)
    assert reference.modules == {"A1A3": 2.0 / 1000, "A4": None, "A5": None}
    assert reference.declared_unit == "1000 kg product"
    assert reference.unit == "kg"
    assert reference.proxy_for and "sand" in reference.proxy_for.lower()
    assert "15804" in reference.method and "GWP-GHG" in reference.method
    assert set(reference.factors()) == {"A1A3"}
    assert reference.factors()["A1A3"].value == 0.002
    assert "Boverket" not in reference.factors()["A1A3"].source
    with pytest.raises(TypeError):
        catalogue.carbon_references["another"] = reference


def test_six_sand_users_keep_optional_module_reviews_without_fabric_gaps():
    catalogue = Catalogue.load()
    affected = set()
    for slot in catalogue.search():
        report = catalogue.completeness(slot.archetype_id, state=slot.state)
        assert report["complete"] and slot.complete
    findings = [row for row in catalogue.sanity_report()["findings"]
                if row["rule_id"] == "carbon.modules" and TAGENE in row["path"]]
    assert len(findings) == 1 and findings[0]["severity"] == "review"
    assert findings[0]["missing_modules"] == ["A4", "A5"]
    affected.update((row["archetype_id"], row["state"])
                    for row in findings[0]["affected_archetypes"])
    assert affected == {
        (identifier, state)
        for identifier in ("office_se01", "school_se01")
        for state in ("existing", "standard", "advanced")
    }
    assert catalogue.summary()["incomplete_slots"] == 0
    assert catalogue.summary()["complete_slots"] == 228


def test_explicitly_supplied_optional_modules_become_known_factors():
    payload = Catalogue.load().resolved_dict()
    payload["carbon_references"][TAGENE]["modules"].update(A4=0.01, A5=0)
    authored = Catalogue(payload)
    assert authored.summary()["incomplete_slots"] == 0
    assert authored.materials[SAND].carbon_reference.modules["A5"] == 0
    assert set(authored.materials[SAND].carbon_reference.factors()) == {"A1A3", "A4", "A5"}


def test_omitted_module_remains_missing_and_is_never_inferred_as_zero():
    payload = Catalogue.load().resolved_dict()
    del payload["carbon_references"][TAGENE]["modules"]["A4"]
    authored = Catalogue(payload)
    assert authored.completeness("office_se01")["complete"]
    assert "A4" not in authored.materials[SAND].carbon_reference.factors()


@pytest.mark.parametrize("fault", ["identity", "dangling", "ambiguous"])
def test_external_carbon_links_reject_wrong_or_ambiguous_sources(fault):
    payload = Catalogue.load().resolved_dict()
    if fault == "identity":
        payload["carbon_references"][TAGENE]["identifier"] = "different-source"
    elif fault == "dangling":
        payload["materials"][SAND]["carbon_reference_id"] = "absent-source"
    else:
        payload["materials"][SAND]["boverket_id"] = next(iter(payload["boverket"]))
    with pytest.raises(ValueError, match="(?i)identifier|reference|choose"):
        Catalogue(payload)


def test_legacy_catalogue_without_external_section_still_reports_missing_mapping():
    payload = Catalogue.load().resolved_dict()
    del payload["carbon_references"]
    for material in payload["materials"].values():
        material.pop("carbon_reference_id", None)
    authored = Catalogue(payload)
    assert not authored.carbon_references
    assert authored.completeness("office_se01")["missing_values"] == (
        f"materials.{SAND}.boverket_id",
    )


def test_portable_and_nominal_exports_keep_proxy_source_and_unknown_modules():
    catalogue = Catalogue.load()
    archetype = catalogue.get("office_se01")
    restored = archetype_from_dict(json.loads(json.dumps(archetype_to_dict(archetype))))
    assert restored == archetype
    expected = catalogue.carbon_references[TAGENE].to_dict()
    for metadata in (None, catalogue.nominal_metadata("office_se01")):
        bundle = export_nominal_constructions(restored, metadata=metadata)
        reference = bundle["material_references"][SAND]
        assert reference["carbon_reference"] == expected
        assert reference["carbon_reference_id"] == TAGENE
        assert reference["boverket_id"] is None


def test_external_window_source_uses_same_placeholder_validation():
    payload = Catalogue.load().resolved_dict()
    config = payload["archetypes"]["mf_se02"]["states"]["existing"]
    construction = payload["construction_sets"][config["construction_set_id"]]
    window = payload["elements"][construction["elements"]["WINDOW"]]
    material = payload["materials"][window["window_material_id"]]
    material["boverket_id"] = None
    material["carbon_reference_id"] = TAGENE
    # This synthetic assignment exercises authoring mechanics, not product equivalence.
    authored = Catalogue(payload)
    assert authored.get("mf_se02").window.carbon_reference.identifier == TAGENE
    assert authored.completeness("mf_se02")["complete"]


def test_missing_base_production_remains_a_catalogue_gap():
    payload = Catalogue.load().resolved_dict()
    payload["carbon_references"][TAGENE]["modules"]["A1A3"] = None
    authored = Catalogue(payload)
    assert authored.completeness("office_se01")["missing_values"] == (
        f"carbon_references.{TAGENE}.modules.A1A3",)
    assert not authored.materials[SAND].carbon_reference.factors()


def test_partial_boverket_source_preserves_base_without_fabricating_legacy_fields():
    payload = Catalogue.load().resolved_dict()
    mid = next(mid for mid, material in payload["materials"].items()
               if material["kind"] == "opaque" and material.get("boverket_id"))
    source_id = payload["materials"][mid]["boverket_id"]
    source = payload["boverket"][source_id]
    for item in source["DataItems"]:
        if item["PropertyCode"] == "GWP-GHG AR4":
            item["DataValueItems"] = [row for row in item["DataValueItems"]
                                     if row["DataModuleCode"] not in {"A4", "A5.1"}]
    authored = Catalogue(payload)
    assert authored.materials[mid].embodied_carbon is None
    assert authored.summary()["incomplete_slots"] == 0
    finding = next(row for row in authored.sanity_report()["findings"]
                   if row["rule_id"] == "carbon.modules" and row["path"] == f"boverket.{source_id}.DataItems")
    assert finding["severity"] == "review"
    assert "A1-A3 Conservative" in finding["known_modules"]
    assert not finding["legacy_embodied_carbon_available"]
