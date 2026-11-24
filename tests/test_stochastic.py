"""Optional per-building operating draws: reproducible, inside sourced ranges, off by default."""

import pytest

from epsm_data import (
    OperatingDistribution,
    sample_operating_values,
    select_operating_distributions,
    select_operating_profile,
)


@pytest.mark.parametrize("era", ["SE.01", "SE.03", "SE.06", "SE.07"])
def test_draws_stay_inside_sourced_ranges(era):
    d = select_operating_distributions("single_family", era=era)
    assert set(d.levers) == {"heating_setpoint_c", "air_change_fraction", "household_electricity_kwh_m2_year"}
    for i in range(500):
        v = sample_operating_values(d, f"house-{i}", seed=20261124)
        for name, value in v.items():
            lo, hi = sorted((d.levers[name].low, d.levers[name].high))
            assert lo <= value <= hi


def test_same_seed_and_key_give_same_values_and_keys_differ():
    d = select_operating_distributions("single_family", era="SE.04")
    a = sample_operating_values(d, "b1", seed=1)
    assert a == sample_operating_values(d, "b1", seed=1)
    assert a != sample_operating_values(d, "b2", seed=1)
    assert a != sample_operating_values(d, "b1", seed=2)


def test_deterministic_default_is_released_catalogue():
    d = select_operating_distributions("single_family", era="SE.02")
    released = sample_operating_values(d, "b1", seed=1, stochastic=False)
    assert released == {"heating_setpoint_c": 21.0, "air_change_fraction": 0.0,
                         "household_electricity_kwh_m2_year": 21.0}
    sveby = select_operating_profile("single_family").values["use"]
    assert released["heating_setpoint_c"] == sveby["heating_setpoint_c"]
    assert released["household_electricity_kwh_m2_year"] == sveby["household_electricity_kwh_m2_year"]


def test_advanced_state_keeps_released_values():
    d = select_operating_distributions("single_family", era="SE.05")
    assert d.applies_to_states == ("existing", "standard")
    assert sample_operating_values(d, "b1", seed=1, state="advanced") == d.released_values()
    assert sample_operating_values(d, "b1", seed=1, state="existing") == sample_operating_values(
        d, "b1", seed=1, state="standard")


def test_uniform_draws_cover_the_range_evenly():
    d = select_operating_distributions("single_family", era="SE.05")
    xs = [sample_operating_values(d, f"h{i}", seed=7)["household_electricity_kwh_m2_year"] for i in range(4000)]
    mean = sum(xs) / len(xs)
    assert abs(mean - 25.5) < 0.2


def test_downward_range_and_untested_types():
    d = select_operating_distributions("single_family", era="SE.01")
    assert d.levers["heating_setpoint_c"].high == 20.8 < d.levers["heating_setpoint_c"].low
    assert d.evidence_status == "not_adopted"
    with pytest.raises(ValueError, match="No operating distributions"):
        select_operating_distributions("multi_family", era="SE.01")
    with pytest.raises(ValueError, match="needs an era"):
        select_operating_distributions("single_family", era="SE.99")


def test_triangular_quantiles_and_validation():
    t = OperatingDistribution("x", "triangular", 0.0, 10.0, 5.0, "1", "test source", mode=2.0)
    assert t.quantile(0.0) == 0.0
    assert t.quantile(0.2) == pytest.approx(2.0)
    assert t.quantile(0.999999) == pytest.approx(10.0, abs=0.02)
    with pytest.raises(ValueError):
        OperatingDistribution("x", "normal", 0.0, 1.0, 0.0, "1", "s")
    with pytest.raises(ValueError):
        OperatingDistribution("x", "triangular", 0.0, 1.0, 0.0, "1", "s", mode=3.0)
    with pytest.raises(ValueError):
        OperatingDistribution("x", "uniform", 0.0, 1.0, 0.0, "1", " ")
