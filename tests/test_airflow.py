"""Verify TABULA/Core reference-volume conservation, not an accuracy claim.

References: TABULA CommonCalculationMethod eq.(7), printed pp.12–13;
packaged datasets/parametric/airflow_review.json.
"""

import pytest

from epsm_data.airflow import infiltration_handoff
from epsm_data.parametric import load_parametric_catalogue


def baseline():
    return load_parametric_catalogue().get_slot(
        "single_family:SE.02:SE.Zone3:existing:F"
    ).infiltration


@pytest.mark.parametrize("volume", [2500, 3600, 4941])
def test_source_flow_is_conserved_for_different_model_volumes(volume):
    prop = baseline()
    handoff = infiltration_handoff(prop, reference_area_m2=1000,
                                   conditioned_volume_m3=volume)
    assert handoff["source_ach"] == 0.4
    assert handoff["reference_volume_m3"] == 2500
    assert handoff["additional_flow_m3_s"] == pytest.approx(1000 / 3600)
    # Sum over multiple unequal Core zones conserves the source total flow.
    ach = handoff["core_envelope_infiltration_ach"]
    assert sum(ach * v / 3600 for v in [volume * .2, volume * .8]) == pytest.approx(1000 / 3600)
    assert handoff["additional_flow_l_s_per_reference_m2"] == pytest.approx(.4 * 2.5 / 3.6)
    assert prop.value == .4  # source catalogue must not be mutated


@pytest.mark.parametrize("bad", [0, -1, True, float("nan"), float("inf"), "1000"])
def test_invalid_volume_and_area_rejected(bad):
    with pytest.raises(ValueError, match="finite and positive"):
        infiltration_handoff(baseline(), reference_area_m2=bad, conditioned_volume_m3=3600)
    with pytest.raises(ValueError, match="finite and positive"):
        infiltration_handoff(baseline(), reference_area_m2=1000, conditioned_volume_m3=bad)


def test_changed_source_must_be_reviewed_before_conversion():
    cat = load_parametric_catalogue().with_override("single_family", "infiltration", {
        "era": "SE.02", "state": "existing", "value": .17,
        "source": "tabula", "note": "caller quantity with unknown volume basis"})
    prop = cat.get_slot("single_family:SE.02:SE.Zone3:existing:F").infiltration
    with pytest.raises(ValueError, match="current source-volume"):
        infiltration_handoff(prop, reference_area_m2=1000, conditioned_volume_m3=3600)


def test_every_matrix_infiltration_assignment_is_explicitly_assumed():
    cat = load_parametric_catalogue()
    for slot in cat.slots:
        assert slot.infiltration.assumed
        evidence = slot.infiltration.evidence
        assert not evidence.get("basis_stale")
        assert evidence["airflow_basis"]["reference_height_m"] == 2.5
        assert evidence["airflow_basis"]["quantity"] == "additional_infiltration_surcharge"


def test_building_handoff_distinguishes_source_and_core_rates():
    pytest.importorskip("epsm_core")
    from epsm_data.application import resolve_building_archetype

    args = dict(category="single_family", construction_year=1970,
                climate_zone="SE.Zone3", ventilation="F")
    legacy = resolve_building_archetype(**args)
    assert legacy["infiltration_ach"] == .4
    assert legacy["infiltration_reference_basis"] == "tabula_reference_volume_conversion_required"
    converted = resolve_building_archetype(**args, tabula_reference_area_m2=1000,
                                          conditioned_volume_m3=4000)
    assert converted["infiltration_ach"] == .25
    assert converted["infiltration_source_ach"] == .4
    assert converted["infiltration_reference_basis"] == "core_conditioned_volume"
    assert converted["envelope"] == legacy["envelope"]
    assert converted["glazing"] == legacy["glazing"]
    with pytest.raises(ValueError, match="both"):
        resolve_building_archetype(**args, tabula_reference_area_m2=1000)


@pytest.mark.parametrize("era,values", [
    ("SE.01", (.20, .10, .10)), ("SE.02", (.20, .10, .10)),
    ("SE.03", (.10, .10, .05)), ("SE.04", (.10, .10, .05)),
    ("SE.05", (.10, .10, .025)), ("SE.06", (.10, .10, .025)),
])
def test_mf_native_area_defaults_cover_every_matrix_slot(era, values):
    """MF engineering review: area flow conserved regardless of zone volume.

    Ventilation topology is independent of envelope airtightness. Sveby 2.0
    chapter 6 provides ventilation guidance, not these infiltration values.
    """
    from epsm_data.application import resolve_building_archetype
    cat = load_parametric_catalogue()
    for state, q in zip(("existing", "standard", "advanced"), values):
        for zone in ("SE.Zone1", "SE.Zone2", "SE.Zone3"):
            for topology in ("S", "F", "FT", "FTX"):
                prop = cat.get_slot(f"multi_family:{era}:{zone}:{state}:{topology}").infiltration
                assert prop.value == pytest.approx(q * 3.6 / 2.5)
                assert not prop.evidence.get("basis_stale")
                handoff = infiltration_handoff(prop, reference_area_m2=1000, conditioned_volume_m3=4000)
                assert handoff["additional_flow_m3_s"] == pytest.approx(q)
        years = {"SE.01":1930,"SE.02":1970,"SE.03":1980,"SE.04":1995,"SE.05":2005,"SE.06":2020}
        resolved = resolve_building_archetype(category="multi_family", construction_year=years[era], climate_zone="SE.Zone3", ventilation="F", default_state=state)
        assert resolved["core_airflow_inputs"] == {"envelope_infiltration_ach":0, "envelope_infiltration_l_s_m2":q}
        assert resolved["infiltration_reference_basis"] == "atemp_area_rate"


def test_mf_revision_does_not_change_inherited_nonresidential_values():
    cat = load_parametric_catalogue()
    for category in ("office", "school", "generic", "single_family"):
        prop = cat.get_slot(f"{category}:SE.02:SE.Zone3:existing:F").infiltration
        assert prop.value == .4
        assert "additional_flow_l_s_per_reference_m2" not in prop.evidence["airflow_basis"]
