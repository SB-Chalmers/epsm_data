"""A predefined catalogue uses the same authored model for every source recipe."""

import json

import pytest

from epsm_data import Catalogue, Material, WindowElement, archetype_from_dict, archetype_to_dict


def test_catalogue_inspection_preserves_effective_classification_and_boundaries():
    catalogue = Catalogue.load()
    assert catalogue.dataset_id == catalogue.parametric.dataset_id
    assert catalogue.dimensions == catalogue.parametric.dimensions
    assert catalogue.era_for_year(2021) == "SE.06"
    assert catalogue.era_for_year(2022) == "SE.07"
    key = "multi_family:SE.02:SE.Zone3:existing:F"
    assert catalogue.get_slot(key) == catalogue.parametric.get_slot(key)
    assert catalogue.search(category="office", era="SE.07") == catalogue.parametric.search(category="office", era="SE.07")
    assert catalogue.summary()["slot_count"] == 1140
    assert catalogue.effective_configuration() == catalogue.parametric.to_dict()
    with pytest.raises(TypeError):
        catalogue.dimensions["eras"] = []


def test_catalogue_authoring_indexes_are_immutable_physical_definitions():
    catalogue = Catalogue.load()
    assert catalogue.materials and catalogue.windows
    assert all(isinstance(material, Material) for material in catalogue.materials.values())
    assert all(isinstance(window, WindowElement) for window in catalogue.windows.values())
    with pytest.raises(TypeError):
        catalogue.materials["new"] = next(iter(catalogue.materials.values()))
    with pytest.raises(TypeError):
        catalogue.operating_profiles["new"] = catalogue.operating_profiles["generic_other"]
    with pytest.raises(TypeError):
        catalogue.hvac_templates["new"] = next(iter(catalogue.hvac_templates.values()))
    assert "generic_other" in catalogue.operating_profiles
    assert all(template.notes for template in catalogue.hvac_templates.values())


def test_all_canonical_and_explicit_variant_constructions_are_accessible():
    catalogue = Catalogue.load()
    current = catalogue.construction_sets()
    assert len(current) == 95
    all_sources = catalogue.construction_sets(include_variants=True)
    assert ("mf_1950", "existing") in all_sources
    assert ("school_fridhem", "existing") in all_sources
    assert len(all_sources) == 97
    assert "mf_1950" not in catalogue.ids()
    assert "mf_1950" in catalogue.ids(include_variants=True)
    with pytest.raises(TypeError):
        current[("custom", None)] = next(iter(current.values()))


@pytest.mark.parametrize("archetype_id,profile", [
    ("sf_se02", "sveby.residential"), ("mf_se02", "sveby.residential"),
    ("office_se02", "sveby.office"), ("school_se02", "sveby.school"),
    ("mf_1950", "sveby.residential"), ("school_fridhem", "sveby.school"),
])
def test_supported_archetypes_carry_profiles_without_installed_hvac(archetype_id, profile):
    catalogue = Catalogue.load()
    actual = catalogue.get(archetype_id)
    assert actual.operating_profile.profile_id.startswith(profile)
    assert actual.hvac_template is None
    assert actual.envelope_performance is not None
    assert actual.construction_set == catalogue.detailed.compose(archetype_id).construction_set
    assert archetype_from_dict(json.loads(json.dumps(archetype_to_dict(actual)))) == actual
    if actual.building_typology == "single_family":
        assert any("fallback" in note for note in actual.operating_profile.notes)


def test_generic_stays_unresolved_until_caller_selects_a_profile():
    catalogue = Catalogue.load()
    generic = catalogue.get("generic_se02")
    assert generic.operating_profile is None
    assert generic.hvac_template is None
    explicit = generic.with_changes(operating_profile=catalogue.operating_profiles["generic_other"])
    assert explicit.operating_profile.profile_id == "epsm.generic_other.v1"
    assert generic.operating_profile is None


def test_native_mf_rate_and_other_source_volume_rates_keep_their_meaning():
    catalogue = Catalogue.load()
    mf = catalogue.get("mf_se02").envelope_performance
    assert mf.infiltration_l_s_m2 == .2
    assert mf.infiltration_reference_basis == "Atemp"
    assert mf.infiltration_ach is None
    sf = catalogue.get("sf_se02").envelope_performance
    assert sf.infiltration_ach == .4
    assert sf.infiltration_reference_basis == "tabula_reference_volume"
    assert sf.infiltration_l_s_m2 is None
    assert sf.thermal_bridge_uplift_fraction is None
    assert any("2.5" in reference for reference in sf.source_references)


def test_stale_infiltration_basis_is_not_reinterpreted_as_a_model_rate():
    catalogue = Catalogue.load()
    catalogue.parametric = catalogue.parametric.with_property(
        "multi_family", "SE.02", "existing", "infiltration",
        {"value": .4, "source": "proxy", "note": "Explicit new rate without reviewed area basis"})
    envelope = catalogue.get("mf_se02").envelope_performance
    assert envelope.infiltration_ach is None
    assert envelope.infiltration_l_s_m2 is None
    assert any("unresolved" in note for note in envelope.notes)


def test_loaded_index_inspection_and_representation_perform_no_io(monkeypatch):
    import epsm_data.profiles as profiles

    catalogue = Catalogue.load()
    monkeypatch.setattr(profiles, "files", lambda *args: pytest.fail("Implicit profile read"))
    assert catalogue.materials and catalogue.windows
    assert catalogue.operating_profiles and catalogue.hvac_templates
    for text in (repr(catalogue), str(catalogue)):
        assert len(text) <= 160
        assert "\n" not in text


def test_custom_catalogue_indexes_reject_mutable_untyped_definitions():
    source = Catalogue.load()
    with pytest.raises(ValueError, match="OperatingProfile"):
        Catalogue(parametric=source.parametric, detailed=source.detailed,
                  profiles={"custom": {"mutable": []}})
    with pytest.raises(ValueError, match="HVACTemplate"):
        Catalogue(parametric=source.parametric, detailed=source.detailed,
                  hvac_templates={"custom": {"mutable": []}})


def test_all_entries_use_composition_without_calibration(monkeypatch):
    import epsm_data.layered as layered

    catalogue = Catalogue.load()
    monkeypatch.setattr(layered, "_load_calibrated_archetype", lambda **kwargs: pytest.fail("Calibration requested"))
    for identifier in catalogue.ids(include_variants=True):
        states = catalogue.renovation_states(identifier) or (None,)
        for state in states:
            actual = catalogue.get(identifier, state=state)
            assert actual.construction_set.elements
    for identifier in catalogue.ids():
        if identifier.endswith("se07"):
            assert catalogue.get(identifier).construction_set.elements
            with pytest.raises(ValueError):
                catalogue.get(identifier, state="existing")
