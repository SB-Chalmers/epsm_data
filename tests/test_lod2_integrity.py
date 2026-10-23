"""Catalogue integrity checks for partial inputs and canonical physical identity."""

from copy import deepcopy

import pytest

from epsm_data import BuildingElement, Catalogue


@pytest.fixture
def payload():
    return Catalogue.load().to_dict()


def wall_records(payload):
    config = payload["archetypes"]["mf_se02"]["states"]["existing"]
    construction = payload["construction_sets"][config["construction_set_id"]]
    eid = construction["elements"]["EXT_WALL"]
    cid = payload["elements"][eid]["components"][0]
    lid = payload["components"][cid]["layers"][0]["layer_id"]
    mid = payload["layers"][lid]["materials"][0]["material_id"]
    return eid, cid, lid, mid


def test_unequal_constituent_depth_is_incomplete_without_a_fabricated_thermal_model(payload):
    _, _, lid, _ = wall_records(payload)
    payload["layers"][lid]["materials"][0]["thickness"] += 0.01
    catalogue = Catalogue(payload)
    report = catalogue.completeness("mf_se02")
    assert not report["complete"]
    assert any("thermal_equivalence" in field for field in report["missing_values"])
    assert BuildingElement.EXT_WALL not in catalogue.get("mf_se02").construction_set.elements


@pytest.mark.parametrize("source", ["boverket", "honeybee"])
def test_external_source_record_identity_must_match_its_reference(payload, source):
    _, _, _, mid = wall_records(payload)
    material = payload["materials"][mid]
    if source == "boverket":
        payload["boverket"][material["boverket_id"]]["ResourceId"] = 999999999
    else:
        payload["honeybee"][material["honeybee_id"]]["identifier"] = "unrelated-material"
    with pytest.raises(ValueError, match="(?i)identity|identifier|resource|reference"):
        Catalogue(payload)


def test_element_notes_do_not_allow_duplicate_physical_definitions(payload):
    eid, _, _, _ = wall_records(payload)
    duplicate = deepcopy(payload["elements"][eid])
    duplicate["name"] = "Another display label"
    duplicate["notes"] = ["A descriptive note changes no physical property."]
    payload["elements"]["element:duplicate"] = duplicate
    with pytest.raises(ValueError, match="Duplicate element"):
        Catalogue(payload)


def test_reordering_position_tagged_slots_does_not_allow_duplicate_components(payload):
    original = next(record for record in payload["components"].values() if len(record["layers"]) > 1)
    duplicate = deepcopy(original)
    duplicate["layers"].reverse()
    duplicate["name"] = "Another input ordering of the same positioned layers"
    payload["components"]["component:duplicate"] = duplicate
    with pytest.raises(ValueError, match="Duplicate component"):
        Catalogue(payload)


def test_omitted_layer_thickness_is_reported_as_missing(payload):
    _, _, lid, _ = wall_records(payload)
    del payload["layers"][lid]["thickness"]
    catalogue = Catalogue(payload)
    report = catalogue.completeness("mf_se02")
    assert not report["complete"]
    assert f"layers.{lid}.thickness" in report["missing_values"]
    assert BuildingElement.EXT_WALL not in catalogue.get("mf_se02").construction_set.elements


@pytest.mark.parametrize("state", ["", 0, False])
def test_invalid_falsy_states_do_not_silently_select_existing(payload, state):
    catalogue = Catalogue(payload)
    with pytest.raises((ValueError, TypeError), match="(?i)state"):
        catalogue.get("mf_se02", state=state)


def test_loaded_catalogue_selection_never_reads_profiles_again(payload, monkeypatch):
    import epsm_data.profiles as profiles

    catalogue = Catalogue(payload)
    expected = catalogue.get("mf_se02")
    monkeypatch.setattr(profiles, "files", lambda *args: pytest.fail("Unexpected profile file I/O"))
    assert catalogue.get("mf_se02") == expected
    assert catalogue.for_year("multi_family", 1970) == expected


@pytest.mark.parametrize("omitted", [False, True])
def test_absent_envelope_performance_is_reported_incomplete(payload, omitted):
    config = payload["archetypes"]["mf_se02"]["states"]["existing"]
    if omitted:
        del config["envelope_performance"]
    else:
        config["envelope_performance"] = None
    catalogue = Catalogue(payload)
    report = catalogue.completeness("mf_se02")
    assert not report["complete"]
    assert any("envelope_performance.infiltration" in field for field in report["missing_values"])
    assert catalogue.get("mf_se02").envelope_performance is None
    assert any(
        entry["archetype_id"] == "mf_se02" and entry["state"] == "existing"
        for entry in catalogue.summary()["incomplete_archetypes"]
    )


@pytest.mark.parametrize("omitted", [False, True])
def test_absent_material_properties_record_remains_inspectable(payload, omitted):
    _, _, _, mid = wall_records(payload)
    if omitted:
        del payload["materials"][mid]["properties"]
    else:
        payload["materials"][mid]["properties"] = None
    catalogue = Catalogue(payload)
    report = catalogue.completeness("mf_se02")
    assert not report["complete"]
    assert f"materials.{mid}.properties.conductivity" in report["missing_values"]
    assert mid not in catalogue.materials
    assert BuildingElement.EXT_WALL not in catalogue.get("mf_se02").construction_set.elements


def test_missing_whole_state_still_has_an_incomplete_catalogue_slot(payload):
    del payload["archetypes"]["mf_se02"]["states"]["existing"]
    catalogue = Catalogue(payload)
    slots = catalogue.search(category="multi_family", era="SE.02", climate_zone="SE.Zone3")
    missing_slot = next(slot for slot in slots if slot.state == "existing")
    assert not missing_slot.complete
    assert "archetypes.mf_se02.states.existing" in missing_slot.missing_values
    assert catalogue.get("mf_se02").construction_set is None
    summary = catalogue.summary()
    assert summary["slot_count"] == 228
    assert any(
        entry["archetype_id"] == "mf_se02" and entry["state"] == "existing"
        for entry in summary["incomplete_archetypes"]
    )
