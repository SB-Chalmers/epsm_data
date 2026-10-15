"""Physical composition is independent of catalogue target acceptance."""

import json

import pytest

from epsm_data import Catalogue, archetype_to_dict, load_detailed_catalogue
from epsm_data.layered import load_calibrated_archetype


@pytest.mark.parametrize("state", ["existing", "standard", "advanced"])
def test_pilot_matches_existing_physical_composition_and_identities(state):
    catalogue = Catalogue.load()
    expected = load_calibrated_archetype(
        archetype_id="mf_se02", renovation_state=state,
        detailed=catalogue.detailed, catalogue=catalogue.parametric,
    ).archetype
    actual = catalogue.detailed.compose("mf_se02", state=state)
    assert actual.construction_set == expected.construction_set
    assert actual.envelope_u_values == expected.envelope_u_values
    assert actual.source_references and actual.notes
    assert actual.construction_set == catalogue.get("mf_se02", state=state).construction_set
    assert actual.operating_profile is None and actual.hvac_template is None


def test_pilot_ignores_target_acceptance_and_never_calls_calibrated_loader(monkeypatch):
    import epsm_data.layered as layered

    catalogue = Catalogue.load()
    before = catalogue.get("mf_se02")
    edited = catalogue.parametric.with_property(
        "multi_family", "SE.02", "existing", "roof",
        {"value": 0.9, "source": "proxy", "note": "Explicit test target edit"},
    )
    catalogue.parametric = edited
    monkeypatch.setattr(layered, "load_calibrated_archetype",
                        lambda **kwargs: pytest.fail("Composition requested calibration"))
    assert catalogue.get("mf_se02") == before


def test_valid_material_edit_changes_composition_without_retuning_or_acceptance(detailed_copy):
    path, records = detailed_copy
    original = load_detailed_catalogue().compose("mf_se02")
    records["honeybee"]["materials"]["EPSM_cellular_plastic"]["conductivity"] = 0.08
    for name, payload in records.items():
        (path / f"{name}.json").write_text(json.dumps(payload))
    edited = load_detailed_catalogue(path).compose("mf_se02")
    assert edited.envelope_u_values["GROUND_FLOOR"] > original.envelope_u_values["GROUND_FLOOR"]
    assert edited.construction_set.version_id != original.construction_set.version_id
    assert edited.source_references == original.source_references


def test_invalid_physical_material_is_rejected(detailed_copy):
    path, records = detailed_copy
    records["honeybee"]["materials"]["EPSM_cellular_plastic"]["conductivity"] = -0.1
    for name, payload in records.items():
        (path / f"{name}.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="conductivity"):
        load_detailed_catalogue(path).compose("mf_se02")


def test_composition_keeps_review_notes_and_exports_without_lookup():
    from epsm_data import archetype_from_dict

    catalogue = Catalogue.load()
    actual = catalogue.get("mf_se02")
    review = catalogue.detailed.review("mf_se02", "existing")
    for note in review["notes"]:
        assert note in actual.notes
    for caveat in review["open_caveats"]:
        assert any(caveat["note"] in note for note in actual.notes)
    for annotation in review["record_annotations"]:
        for note in annotation["notes"]:
            assert any(note in retained for retained in actual.notes)
    for caveat in review["caveats"]:
        if caveat.get("resolution"):
            assert any(caveat["resolution"] in note for note in actual.notes)
    assert archetype_from_dict(json.loads(json.dumps(archetype_to_dict(actual)))) == actual


def test_composition_defaults_and_unknown_selection_are_explicit():
    detailed = load_detailed_catalogue()
    assert detailed.compose("mf_se02") == detailed.compose("mf_se02", state="existing")
    with pytest.raises(KeyError):
        detailed.compose("missing")
    with pytest.raises(KeyError):
        detailed.compose("mf_se02", state="unrecognised")


@pytest.mark.parametrize("archetype_id", ["mf_1950", "school_fridhem"])
def test_explicit_source_variant_composition_preserves_its_identity_and_notes(archetype_id):
    detailed = load_detailed_catalogue()
    expected = detailed.archetypes[archetype_id]["states"]["existing"]["identity"]
    actual = detailed.compose(archetype_id)
    assert actual.archetype_id == expected["archetype_id"]
    assert actual.source_references and actual.notes
    assert actual.renovation_log == ()


def test_loaded_registry_composition_performs_no_resource_access(monkeypatch):
    import epsm_data.detailed as detailed_module

    detailed = load_detailed_catalogue()
    monkeypatch.setattr(detailed_module, "files",
                        lambda *args: pytest.fail("Composition read packaged resources"))
    monkeypatch.setattr(detailed_module, "load_parametric_catalogue",
                        lambda *args: pytest.fail("Composition loaded target catalogue"))
    assert detailed.compose("mf_se02").total_elements == 7
