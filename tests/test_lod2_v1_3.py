"""Release-independent checks for the v1.3 construction/evidence contract."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from epsm_data.detailed import load_detailed_catalogue
from epsm_data.layered import load_calibrated_archetype
from epsm_data.nominal import validate_nominal_handover
from epsm_data.parametric import ArchetypeKey, ParametricCatalogue, load_parametric_catalogue
from epsm_data.release import core_inputs

WORK = Path(__file__).resolve().parents[1] / "evidence/lod2_v1_3"


@pytest.fixture(scope='module')
def candidate_v13():
    cat = load_parametric_catalogue()
    data = load_detailed_catalogue(catalogue=cat)
    return data, cat



def test_all_seven_roles_are_available_without_presence(candidate_v13):
    detailed, cat = candidate_v13
    for aid, arch in detailed.archetypes.items():
        if arch.get('catalogue_assignment', 'canonical') != 'canonical':
            continue
        for state, spec in arch['states'].items():
            assert len(spec['assemblies']) == 7
            assert spec['element_presence'] == 'caller_geometry'
            basement = detailed.assemblies[spec['assemblies']['BASEMENT_WALL']]
            assert basement['boundary_details']['presence'] == 'optional_geometry_selected'
            assert 'woodfiber_board' not in [x['material_id'] for c in basement['components'] for x in c['layers']]
            slot = cat.get_slot(ArchetypeKey(**spec['key']))
            assert all(v.evidence and not v.evidence.get('basis_stale') for v in slot.properties.values())


def test_effective_ground_preserved_and_nominal_distinguished(candidate_v13):
    detailed, cat = candidate_v13
    for slot in cat.slots:
        for role in ('ground_floor', 'basement_wall'):
            evidence = slot.properties[role].evidence
            assert evidence['value_kind'] == 'legacy_effective_ground_reference'
            assert evidence['nominal_u_value'] > 0
    model = load_calibrated_archetype(detailed=detailed, catalogue=cat, archetype_id='office_se05')
    nominal = model.to_nominal_dict()
    slot = cat.get_slot('office:SE.05:SE.Zone3:existing:F')
    assert nominal['roles']['BASEMENT_WALL']['nominal_u_w_m2k'] == pytest.approx(slot.properties['basement_wall'].evidence['nominal_u_value'])
    assert not nominal['readiness']['ground_validation']
    assert nominal['element_presence'] == 'caller_geometry'


def test_no_missing_role_or_floor_substitution(candidate_v13):
    detailed, cat = candidate_v13
    bundle = load_calibrated_archetype(detailed=detailed, catalogue=cat, archetype_id='school_se05').to_nominal_dict()
    bad = deepcopy(bundle)
    for field in ('core', 'honeybee', 'roles'):
        bad[field].pop('BASEMENT_WALL')
    with pytest.raises(ValueError, match='declared archetype roles'):
        validate_nominal_handover(bad)
    pytest.importorskip('epsm_core')
    native = core_inputs('school_se05', detailed=detailed, catalogue=cat)
    assert native['envelope'].basement_wall != native['envelope'].ground
    # A small explicit fake models a supported legacy caller with six roles.
    from types import SimpleNamespace
    from unittest.mock import patch
    old_bundle = deepcopy(bundle)
    old_bundle['core'].pop('BASEMENT_WALL')
    with patch('epsm_data.release.load_calibrated_archetype', return_value=SimpleNamespace(
        to_nominal_dict=lambda: old_bundle
    )):
        with pytest.raises(ValueError, match='No basement-wall recipe'):
            core_inputs('school_se05', detailed=detailed, catalogue=cat)


def test_claims_have_inputs_and_do_not_promote_missing_evidence(candidate_v13):
    claims = json.loads((WORK / 'claims.json').read_text())['claims']
    primary = {k: v for k, v in claims.items() if k.count(':') == 3}
    assert len(primary) == 720
    for claim in claims.values():
        assert claim['classification'] != 'direct_evidence'
        assert claim['source'] and claim['locator']
        for target in claim.get('input_claim_ids', []) + claim.get('material_claim_ids', []):
            assert target in claims
    detailed, cat = candidate_v13
    for era in cat.dimensions['eras']:
        for state in ('existing', 'standard', 'advanced'):
            assert cat.resolve_construction('generic', era, state).u_values == cat.resolve_construction('multi_family', era, state).u_values


def test_changed_anchor_or_override_marks_evidence_stale(candidate_v13):
    _, cat = candidate_v13
    changed = cat.with_override('office', 'basement_wall', {
        'era': 'SE.05', 'state': 'existing', 'value': .1,
        'source': 'v1_3_construction_review', 'note': 'caller test'})
    prop = changed.resolve_construction('office', 'SE.05', 'existing').properties['basement_wall']
    assert prop.evidence['classification'] == 'unclassified'
    assert prop.evidence['basis_stale']
    bad = cat.to_dict()
    bad['claim_metadata']['office:SE.05:existing:basement_wall']['source'] = 'missing'
    with pytest.raises(ValueError, match='source and locator'):
        ParametricCatalogue(bad)
