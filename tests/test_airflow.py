"""Reference conversion conserves flow independently of building volume."""

import pytest

from epsm_data import Catalogue
from epsm_data.airflow import infiltration_handoff


@pytest.mark.parametrize("volume", [1500, 2500, 4000])
def test_declared_reference_flow_is_conserved(volume):
    catalogue = Catalogue.load()
    source = catalogue.get("sf_se02").envelope_performance
    height = catalogue.nominal_metadata("sf_se02")["reference_height_m"]
    result = infiltration_handoff(
        source, reference_area_m2=1000, conditioned_volume_m3=volume, reference_height_m=height
    )
    assert source.infiltration_ach == 0.4
    assert result["reference_volume_m3"] == 2500
    assert result["core_envelope_infiltration_ach"] * volume == pytest.approx(1000)


@pytest.mark.parametrize("bad", [0, -1, True, float("nan"), float("inf"), "1000"])
def test_unknown_or_invalid_reference_values_fail(bad):
    source = Catalogue.load().get("sf_se02").envelope_performance
    with pytest.raises(ValueError, match="finite and positive"):
        infiltration_handoff(
            source, reference_area_m2=bad, conditioned_volume_m3=3600, reference_height_m=2.5
        )
