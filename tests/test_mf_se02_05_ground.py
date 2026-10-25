"""MF basement additions follow source measures without fitting ground U-values."""

import json
from pathlib import Path

import pytest

from epsm_data import Catalogue, export_nominal_constructions, load_sanity_fixture

FIXTURES = Path(__file__).parent / 'fixtures/catalogue_sanity'
CASE = json.loads((FIXTURES / 'cases/mf_se02_05_ground.json').read_text())
AIDS = tuple(CASE['archetypes'])
STATES = ('existing', 'standard', 'advanced')
ROLES = ('GROUND_FLOOR', 'BASEMENT_WALL')


@pytest.fixture(scope='module')
def catalogue():
    return Catalogue.load()


@pytest.fixture(scope='module')
def payload(catalogue):
    return catalogue.resolved_dict()


@pytest.fixture(scope='module')
def report(catalogue):
    return catalogue.sanity_report(fixture=FIXTURES)


def _config(payload, aid, state):
    return payload['archetypes'][aid]['states'][state]


def _element(payload, aid, state, role):
    cs = payload['construction_sets'][_config(payload, aid, state)['construction_set_id']]
    return payload['elements'][cs['elements'][role]]


def _layers(payload, aid, state, role):
    return [payload['layers'][slot['layer_id']]
            for cid in _element(payload, aid, state, role)['components']
            for slot in sorted(payload['components'][cid]['layers'],
                               key=lambda value: value['position'])]


def _expected_layers(aid, state, role):
    expected = CASE['archetypes'][aid]
    rows = list(expected['floor_baseline_layers' if role == 'GROUND_FLOOR'
                         else 'wall_baseline_layers'])
    if role == 'GROUND_FLOOR' and state != 'existing':
        rows += [{'material': 'insulation', 'thickness_m': expected['states'][state][
            'floor_added_eps_m']}, {'material': 'finish', 'thickness_m': 0.05}]
    elif role == 'BASEMENT_WALL' and state == 'advanced':
        rows += [{'material': 'wool', 'thickness_m': 0.04},
                 {'material': 'gypsum', 'thickness_m': 0.013}]
    return rows


@pytest.mark.parametrize('aid', AIDS)
@pytest.mark.parametrize('state', STATES)
def test_original_mineral_fabric_is_retained_and_additions_follow_source_placement(
    payload, catalogue, aid, state,
):
    expected = CASE['archetypes'][aid]
    for role in ROLES:
        actual = _layers(payload, aid, state, role)
        rows = _expected_layers(aid, state, role)
        assert len(actual) == len(rows)
        for layer, row in zip(actual, rows, strict=True):
            grade = CASE['materials'][row['material']]
            assert not layer['is_composite']
            assert layer['thickness'] == row['thickness_m']
            assert layer['materials'] == [{'material_id': grade['material_id'],
                                          'area_fraction': 1.0,
                                          'thickness': row['thickness_m']}]
        baseline = _element(payload, aid, 'existing', role)['components']
        components = _element(payload, aid, state, role)['components']
        assert components[:len(baseline)] == baseline
        details = _config(payload, aid, state)['boundary_details'][role]
        for key, value in CASE['boundary_metadata'][role].items():
            assert details[key] == value
        if role == 'GROUND_FLOOR':
            assert baseline[-1] == CASE['shared_components']['bonded_finish']
            if state != 'existing':
                assert components[-1] == CASE['shared_components']['floating_finish']
                assert details['floor_rise_m'] == expected['states'][state]['floor_rise_m']
        elif state == 'advanced':
            assert components[-1] == CASE['shared_components']['basement_internal_lining']
        else:
            assert components == baseline
    assert _config(payload, aid, state)['construction_year'] == expected['construction_year']
    archetype = catalogue.get(aid, state=state)
    generic = catalogue.get(aid.replace('mf_', 'generic_'), state=state)
    assert generic.construction_set is archetype.construction_set
    assert generic.operating_profile is archetype.operating_profile


@pytest.mark.parametrize('aid', AIDS)
@pytest.mark.parametrize('state', STATES)
@pytest.mark.parametrize('role', ROLES)
def test_forward_export_uses_only_declared_layers_and_preserves_ground_limitations(
    catalogue, payload, aid, state, role,
):
    bundle = export_nominal_constructions(catalogue.get(aid, state=state),
                                          metadata=_config(payload, aid, state))
    actual = bundle['roles'][role]
    pairs = [(row['thickness_m'], CASE['materials'][row['material']])
             for row in _expected_layers(aid, state, role)]
    resistance = sum(depth / grade['conductivity_w_mk'] for depth, grade in pairs)
    expected = {
        'resistance_m2k_w': resistance,
        'thickness_m': sum(depth for depth, _ in pairs),
        'mass_kg_m2': sum(depth * grade['density_kg_m3'] for depth, grade in pairs),
        'heat_capacity_j_m2k': sum(depth * grade['density_kg_m3']
                                   * grade['specific_heat_j_kgk'] for depth, grade in pairs),
        'nominal_u_w_m2k': 1 / (resistance + 0.17),
    }
    for key, value in expected.items():
        assert actual[key] == pytest.approx(value, rel=1e-12)
    assert actual['rsi_m2k_w'] + actual['rse_m2k_w'] == pytest.approx(0.17)
    hb = bundle['honeybee'][role]
    assert sum(row['thickness'] / row['conductivity'] for row in hb['materials']) == (
        pytest.approx(resistance, rel=1e-12))
    logical_role = role if role == 'GROUND_FLOOR' else 'TABULA_WALL_2'
    source_u = CASE['archetypes'][aid]['source']['states'][state][logical_role]
    assert actual['nominal_u_w_m2k'] != pytest.approx(source_u)
    assert catalogue.completeness(aid, state=state)['complete']


@pytest.mark.parametrize('aid', AIDS)
def test_source_benchmarks_measures_and_boundary_descriptors_preserve_their_meaning(aid):
    references = load_sanity_fixture(FIXTURES)
    expected = CASE['archetypes'][aid]
    era = 'SE.' + aid[-2:]
    source = expected['source']
    for state in STATES:
        reference = next(row for row in references['u_values']
                         if (row['category'], row['era'], row['state'])
                         == ('multi_family', era, state))
        for role in ('GROUND_FLOOR', 'TABULA_WALL_2'):
            target = reference['elements'][role]
            assert all(value == pytest.approx(source['states'][state][role])
                       for value in target['values_w_m2k'].values())
            descriptor = target['boundary_comparison']
            assert descriptor['status'] == 'source_incompatible'
            assert descriptor['physical_boundary'] == 'soil'
            assert str(source['building_row']) in ' '.join(descriptor['source_locators'])
            assert 'ISO 13370' in descriptor['reason']
        if state == 'existing':
            continue
        package = next(row for row in references['renovation_packages']
                       if (row['category'], row['era'], row['state'])
                       == ('multi_family', era, state))
        assert str(source['states'][state]['variant_row']) in package['source_locator']
        floor = references['measures'][package['measures']['GROUND_FLOOR']]
        assert floor['code'] == CASE['sources']['floor_measures'][state]['code']
        assert floor['nominal_added_insulation_m'] == expected['states'][state]['floor_added_eps_m']
        if state == 'advanced':
            wall = references['measures'][package['measures']['TABULA_WALL_2']]
            assert wall['code'] == CASE['sources']['wall_measure']['code']
            assert wall['nominal_added_insulation_m'] == 0.04
        extra_r = expected['states'][state]['floor_added_eps_m'] / 0.036
        assert source['states'][state]['GROUND_FLOOR'] == pytest.approx(
            1 / (1 / source['floor_input_u_w_m2k'] + extra_r + 0.3))


@pytest.mark.parametrize('aid', AIDS)
@pytest.mark.parametrize('state', STATES)
def test_mapped_ground_measures_pass_while_incompatible_u_remains_unassessed(report, aid, state):
    findings = [row for row in report['findings'] if any(
        user['archetype_id'] == aid and user['state'] == state
        for user in row['affected_archetypes'])]
    unassessed = [row for row in findings if row['rule_id'] == 'tabula.boundary_not_assessed']
    assert {row['actual']['element'] for row in unassessed} == {'GROUND_FLOOR', 'TABULA_WALL_2'}
    assert all(row['severity'] == 'review' and row['actual']['status'] == 'source_incompatible'
               for row in unassessed)
    assert sum(row['rule_id'] == 'tabula.source_convention' for row in findings) == 2
    codes = {value['code'] for value in CASE['sources']['floor_measures'].values()}
    codes.add(CASE['sources']['wall_measure']['code'])
    assert not [row for row in findings if row['rule_id'].startswith('tabula.measure_')
                and row['expected'].get('code') in codes]
    assert not [row for row in findings if row['rule_id'] == 'tabula.u_value'
                and row['expected']['element'] in ('GROUND_FLOOR', 'TABULA_WALL_2')]


def test_shared_grades_match_independent_properties_and_registered_honeybee_sources(
    payload, catalogue,
):
    for grade in CASE['materials'].values():
        record = payload['materials'][grade['material_id']]
        assert record['honeybee_id'] == grade['honeybee_id']
        assert record['boverket_id'] == grade['boverket_id']
        for key, fixture_key in [('conductivity', 'conductivity_w_mk'),
                                 ('density', 'density_kg_m3'),
                                 ('specific_heat', 'specific_heat_j_kgk')]:
            assert record['properties'][key] == grade[fixture_key]
        source = catalogue.honeybee_materials[grade['honeybee_id']]
        assert {key: source[key] for key in record['properties']} == record['properties']
