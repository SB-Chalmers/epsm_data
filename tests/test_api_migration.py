"""One authoring route retains distinct assessment and inspection capabilities."""

import importlib

import pytest

from epsm_data import Catalogue, archetype_from_dict, archetype_to_dict

RETIRED = (
    'load_parametric_catalogue', 'load_detailed_catalogue', 'load_calibrated_archetype',
    'load_school_reference', 'load_office_reference', 'resolve_building_archetype',
    'validate_native_handover', 'export_json', 'export_consumption_contracts',
    'export_construction_sets',
)


@pytest.mark.parametrize('name', RETIRED)
def test_retired_root_facades_are_not_public(name):
    import epsm_data
    assert name not in epsm_data.__all__
    assert not hasattr(epsm_data, name)


@pytest.mark.parametrize('name', ['epsm_data.application', 'epsm_data.release',
                                 'epsm_data.usecases.export_outputs'])
def test_retired_integration_and_lossy_export_modules_are_absent(name):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(name)


def test_public_assessment_is_explicit_and_separate_from_composition(monkeypatch):
    catalogue = Catalogue.load()
    authored = catalogue.get('mf_se02')
    assessment = catalogue.assess('mf_se02')
    assert assessment.archetype.construction_set == authored.construction_set
    assert assessment.report['nominal_calibration_complete']
    assert assessment.summary()['archetype_id'] == authored.archetype_id
    for value in (repr(assessment), str(assessment)):
        assert len(value) <= 160 and '\n' not in value
    assert archetype_from_dict(archetype_to_dict(authored)) == authored
    assert not hasattr(authored, 'to_consumption_contract')
    assert not hasattr(authored, 'to_dict')


def test_source_references_remain_distinct_inspection_and_do_not_require_acceptance():
    catalogue = Catalogue.load()
    school = catalogue.source_reference('school_fridhem')
    assert school.report['status'] == 'source_and_provisional_draft'
    assert school.to_nominal_dict()['kind'] == 'source_and_provisional_construction_handover'
    before = catalogue.detailed.to_dict()
    with pytest.raises(ValueError, match='missing source metadata'):
        catalogue.source_reference('office_se05')
    assert catalogue.detailed.to_dict() == before
    for result in (school,):
        assert result.summary()['archetype_id'] == result.archetype.archetype_id
        assert len(repr(result)) <= 160
    assert catalogue.get('school_fridhem').construction_set.elements
    with pytest.raises(ValueError, match='assessment'):
        catalogue.assess('school_fridhem')
    with pytest.raises(ValueError, match='source reference'):
        catalogue.source_reference('mf_se02')


@pytest.mark.parametrize("identifier", ["line\n" + "x" * 1000, "\0" * 1000])
def test_advanced_results_have_bounded_representation_for_hostile_ids(identifier):
    catalogue = Catalogue.load()
    from epsm_data import OfficeReference
    office = OfficeReference(catalogue.get('office_se05'), {})
    for value in (catalogue.assess('mf_se02'), catalogue.source_reference('school_fridhem'), office):
        from dataclasses import replace
        changed = replace(value, archetype=value.archetype.with_changes(archetype_id=identifier))
        assert len(repr(changed)) <= 160
        assert '\n' not in repr(changed)


def test_advanced_operations_use_loaded_registry_without_resource_access(monkeypatch):
    catalogue = Catalogue.load()
    def denied(*args, **kwargs):
        pytest.fail('Assessment or source inspection loaded a resource')
    for name in ('epsm_data.layered', 'epsm_data.school', 'epsm_data.office', 'epsm_data.detailed'):
        module = importlib.import_module(name)
        if hasattr(module, 'files'):
            monkeypatch.setattr(module, 'files', denied)
    assert catalogue.assess('mf_se02').report
    assert catalogue.source_reference('school_fridhem').report


def test_detailed_inspection_view_has_bounded_no_io_representation(monkeypatch):
    catalogue = Catalogue.load()
    import epsm_data.detailed as detailed_module
    monkeypatch.setattr(detailed_module, 'files', lambda *args: pytest.fail('Implicit resource read'))
    assert len(repr(catalogue.detailed)) <= 160
    assert '\n' not in str(catalogue.detailed)
    assert catalogue.detailed.summary()['archetypes'] == len(catalogue.detailed.archetypes)


def test_supported_mf_source_alternative_retains_complete_assessment():
    from epsm_data.layered import _load_calibrated_archetype
    catalogue = Catalogue.load()
    expected = _load_calibrated_archetype(archetype_id="mf_1950", detailed=catalogue.detailed,
                                          catalogue=catalogue.parametric)
    actual = catalogue.assess("mf_1950")
    assert actual.report == expected.report
    assert actual.archetype.construction_set == expected.archetype.construction_set
    assert actual.report["target_catalogue_revision"]
