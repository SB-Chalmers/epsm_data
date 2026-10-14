"""The current catalogue stays complete without a frozen historical release."""
import hashlib
import json
from pathlib import Path

from epsm_data import load_detailed_catalogue, load_parametric_catalogue
from epsm_data.layered import load_calibrated_archetype
from epsm_data.nominal import validate_nominal_handover

ROOT = Path(__file__).resolve().parents[1]


def test_one_current_catalogue_has_no_live_history_chain():
    payload = load_parametric_catalogue().to_dict()
    assert payload['schema_version'] == 2
    assert len(payload['resolved']) == 95
    assert not {'categories', 'claim_metadata', 'performance_guardrail'} & set(payload)
    assert not (ROOT / 'BASELINE.json').exists()
    assert not (ROOT / 'cohort_profiles/current.json').exists()


def test_current_catalogue_coverage_and_nominal_exports():
    cat = load_parametric_catalogue()
    data = load_detailed_catalogue(catalogue=cat)
    assert cat.summary()['slot_count'] == 1140
    assert cat.summary()['lod1_complete'] == 1140
    count = 0
    for aid, archetype in data.archetypes.items():
        if archetype.get('catalogue_assignment', 'canonical') != 'canonical':
            continue
        for state, spec in archetype['states'].items():
            count += 1
            assert len(spec['assemblies']) == 7
            model = load_calibrated_archetype(detailed=data, catalogue=cat,
                                             archetype_id=aid, renovation_state=state)
            bundle = model.to_nominal_dict()
            validate_nominal_handover(bundle)
            assert len(bundle['roles']) == 7
            assert not bundle['readiness']['ground_validation']
    assert count == 95


def test_renovations_are_independent_and_preserve_retained_fabric():
    from epsm_data.domain import BuildingElement

    base = load_calibrated_archetype()
    before = base.to_dict()
    packages = {
        state: load_calibrated_archetype(renovation_state=state)
        for state in ('standard', 'advanced')
    }
    for package in packages.values():
        for role in (BuildingElement.GROUND_FLOOR, BuildingElement.BASEMENT_WALL,
                     BuildingElement.INTERMEDIATE_FLOOR, BuildingElement.INT_WALL_NONLOADBEARING):
            def fabric(element):
                return [(slot.layer.thickness, tuple(
                    (m.area_fraction, m.material.conductivity, m.material.density,
                     m.material.specific_heat) for m in slot.layer.materials
                )) for component in element.components for slot in component.layers]
            assert fabric(package.archetype.construction_set.elements[role]) == fabric(base.archetype.construction_set.elements[role])
        assert package.report['nominal_calibration_complete']
        assert package.report['target_drift'] == []
    for prop in ('roof', 'external_wall', 'window'):
        assert packages['advanced'].report['elements'][prop]['assembly_u'] <= packages['standard'].report['elements'][prop]['assembly_u'] <= base.report['elements'][prop]['assembly_u']
    assert base.to_dict() == before
    # Loading Advanced has no effect on a later independent Standard construction.
    assert load_calibrated_archetype(renovation_state='standard').to_dict() == packages['standard'].to_dict()


def test_historical_source_copies_match_provenance_index():
    index = json.loads((ROOT / 'evidence/source-index.json').read_text())
    assert index['files']
    for record in index['files']:
        path = ROOT / record['retained_path']
        assert 'ARCHIVE' not in path.parts
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
