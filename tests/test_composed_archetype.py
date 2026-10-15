"""Authoring complete and incomplete definitions without catalogue knowledge."""

import copy
import json
from uuid import UUID, uuid4

import pytest

from epsm_data import (
    Archetype,
    BuildingArchetype,
    ConstructionSet,
    HVACTemplate,
    OperatingProfile,
    RenovationEvent,
    archetype_from_dict,
    archetype_to_dict,
)


def test_incomplete_authoring_needs_no_year_classification_or_catalogue():
    archetype = Archetype("authored", "Custom building")
    assert Archetype is BuildingArchetype
    assert archetype.construction_year is None
    assert archetype.current_year is None
    assert archetype.construction_set is None
    assert archetype.window is None
    assert archetype.envelope_u_values == {}
    assert archetype.total_elements == 0
    assert set(archetype.missing_sections) == {
        "construction_set",
        "operating_profile",
        "hvac_template",
        "envelope_performance",
    }
    assert (
        archetype.with_changes(building_typology="research:unclassified").building_typology
        == "research:unclassified"
    )
    assert archetype_from_dict(archetype_to_dict(archetype)) == archetype


def test_all_composed_sections_roundtrip_without_lookup(archetype):
    from epsm_data import EnvelopePerformance

    profile = OperatingProfile(
        "custom",
        {"building_assumptions": {"use": {"occupant_density_per_m2": 0.04}}},
        source_references=("example:use",),
    )
    hvac = HVACTemplate("custom-hvac", {"airflow": {"topology": "F"}}, notes=("Explicit choice.",))
    envelope = EnvelopePerformance(
        infiltration_ach=0.2,
        infiltration_reference_basis="tabula_reference_volume",
        thermal_bridge_uplift_fraction=0.1,
        source_references=("example:envelope",),
    )
    authored = archetype.with_changes(
        operating_profile=profile,
        hvac_template=hvac,
        envelope_performance=envelope,
        source_references=["example:construction"],
        notes=["Authored."],
        construction_year=None,
        building_typology="laboratory:custom",
    )
    payload = archetype_to_dict(authored)
    assert payload["format_version"] == 4
    restored = archetype_from_dict(json.loads(json.dumps(payload)))
    assert restored == authored
    assert restored.construction_set == archetype.construction_set
    assert restored.operating_profile == profile
    assert restored.envelope_performance.infiltration_reference_basis == "tabula_reference_volume"
    assert restored.missing_sections == ()
    assert copy.deepcopy(restored) == restored
    edited = restored.with_changes(operating_profile=profile.with_changes(notes=("Independent.",)))
    assert edited.operating_profile.notes != profile.notes
    assert restored.operating_profile.notes == profile.notes


@pytest.mark.parametrize("version", [1, 2, 3])
def test_real_legacy_field_shape_remains_readable(version):
    # Fixed minimal old-window record: no field introduced by format 4 is present.
    payload = {
        "format_version": version,
        "archetype": {
            "archetype_id": "old",
            "display_name": "Old glazing",
            "construction_year": 1960,
            "building_typology": "multi_family",
            "renovation_log": [],
            "construction_set": {
                "version_id": "00000000-0000-0000-0000-000000000001",
                "valid_from_year": 1960,
                "elements": {
                    "WINDOW": {
                        "name": "old-window",
                        "archetype": "old",
                        "application": "WINDOW",
                        "u_value": 2.5,
                        "shgc": 0.7,
                        "vt": 0.65,
                        "boverket_id": None,
                    }
                },
            },
        },
    }
    old = archetype_from_dict(payload)
    assert old.window.u_value == 2.5
    assert old.operating_profile is None
    assert old.envelope_performance is None
    assert old.construction_set.version_id == UUID("00000000-0000-0000-0000-000000000001")
    assert archetype_from_dict(archetype_to_dict(old)) == old


@pytest.mark.parametrize(
    "kwargs",
    [
        {"infiltration_ach": -0.1, "infiltration_reference_basis": "conditioned_volume"},
        {"infiltration_ach": float("nan"), "infiltration_reference_basis": "conditioned_volume"},
        {"infiltration_ach": True, "infiltration_reference_basis": "conditioned_volume"},
        {"infiltration_ach": 0.2},
        {"infiltration_ach": 0.2, "infiltration_reference_basis": "Atemp"},
        {"infiltration_l_s_m2": 0.1, "infiltration_reference_basis": "conditioned_volume"},
        {
            "infiltration_ach": 0.2,
            "infiltration_l_s_m2": 0.1,
            "infiltration_reference_basis": "Atemp",
        },
        {"thermal_bridge_uplift_fraction": float("inf")},
        {"thermal_bridge_uplift_fraction": -0.1},
    ],
)
def test_invalid_envelope_inputs_fail_at_authoring(kwargs):
    from epsm_data import EnvelopePerformance

    with pytest.raises(ValueError):
        EnvelopePerformance(**kwargs)


def test_explicit_zero_and_unresolved_envelope_are_distinct():
    from epsm_data import EnvelopePerformance

    unknown = EnvelopePerformance()
    zero = EnvelopePerformance(
        infiltration_l_s_m2=0,
        infiltration_reference_basis="Atemp",
        thermal_bridge_uplift_fraction=0,
    )
    assert unknown.infiltration_l_s_m2 is None
    assert zero.infiltration_l_s_m2 == 0
    assert zero != unknown
    assert EnvelopePerformance.from_dict(zero.to_dict()) == zero
    for definition in (unknown, zero, zero.with_changes(notes=("\n😀" * 1000,))):
        assert len(repr(definition)) <= 160
        assert "\n" not in str(definition)


def test_recipe_authoring_allows_unknown_year(archetype):
    from epsm_data import build_archetype

    authored = build_archetype(
        {
            "archetype_id": "undated",
            "display_name": "Unknown year",
            "elements": {"WINDOW": {"u_value": 1.4, "shgc": 0.6}},
        },
        materials={},
    )
    assert authored.construction_year is None
    assert authored.construction_set.valid_from_year is None
    assert authored.window.u_value == 1.4


def test_renovation_and_caller_lists_do_not_lose_or_mutate_composed_inputs(archetype):
    profile = OperatingProfile("authored", {"custom": [1, 2]})
    removed = ["old component"]
    event = RenovationEvent(
        "example", 2030, "user", removed, [], archetype.construction_set.version_id, uuid4()
    )
    events = [event]
    source = archetype.with_changes(
        operating_profile=profile, renovation_log=events, notes=["Before."]
    )
    removed.append("unexpected mutation")
    events.clear()
    assert source.renovation_log[0].removed_components == ("old component",)
    assert len(source.renovation_log) == 1
    changed = source.with_renovation(event, ConstructionSet())
    assert changed.operating_profile == profile
    assert changed.notes == source.notes
    assert len(changed.renovation_log) == 2
    assert len(source.renovation_log) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"construction_year": True},
        {"construction_year": 0},
        {"construction_set": {}},
        {"operating_profile": {}},
        {"hvac_template": {}},
        {"envelope_performance": {}},
        {"source_references": [""]},
    ],
)
def test_invalid_supplied_sections_fail_at_authoring(kwargs):
    with pytest.raises(ValueError):
        Archetype("custom", "Custom", **kwargs)


def test_summary_and_representation_are_safe_for_partial_objects(monkeypatch):
    import epsm_data.profiles as profiles

    monkeypatch.setattr(profiles, "files", lambda *args: pytest.fail("Unexpected resource lookup"))
    archetype = Archetype("\n😀" * 1000, "Custom")
    for text in (repr(archetype), str(archetype)):
        assert len(text) <= 160
        assert "\n" not in text
        assert "BuildingArchetype" in text
    assert archetype.summary()["missing_sections"]
    assert archetype.summary()["archetype_id"] == archetype.archetype_id
