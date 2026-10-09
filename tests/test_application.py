"""Component selection must preserve unrelated physical inputs and evidence."""

import pytest

from epsm_data.application import resolve_building_archetype


def resolve(**kwargs):
    """A known-era test building, without energy observations."""
    return resolve_building_archetype(
        category="multi_family",
        construction_year=1970,
        climate_zone="SE.Zone3",
        ventilation="F",
        **kwargs,
    )


def test_window_replacement_preserves_walls_and_leakage():
    pytest.importorskip("epsm_core")
    original = resolve()
    changed = resolve(
        component_states={"window": "standard"},
        component_sources={"window": "dated replacement record"},
    )
    assert changed["envelope"] == original["envelope"]
    assert changed["infiltration_ach"] == original["infiltration_ach"]
    assert changed["glazing"].u_value_w_m2k < original["glazing"].u_value_w_m2k
    assert changed["assignment"]["components"]["airtightness"]["status"] == "assumed"


def test_component_states_require_independent_sources():
    pytest.importorskip("epsm_core")
    with pytest.raises(ValueError, match="independent source"):
        resolve(component_states={"wall": "advanced"})
    with pytest.raises(ValueError, match="Unknown component"):
        resolve(component_states={"best_heating_error": "advanced"})


def test_legacy_attic_adapter_rejects_native_double_counting():
    from epsm_data.release import apply_attic_ventilation

    model = {
        "Zone": {"main_attic": {"part_of_total_floor_area": "No"}},
        "ZoneInfiltration:DesignFlowRate": {
            "native": {"zone_or_zonelist_or_space_or_spacelist_name": "main_attic"}
        },
    }
    with pytest.raises(ValueError, match="already assigned"):
        apply_attic_ventilation(model, outdoor_air_ach=0.5)


@pytest.mark.parametrize("category", ["single_family", "multi_family", "office", "school"])
@pytest.mark.parametrize("year", [1955, 1970, 1980, 1990, 2000, 2015])
def test_all_category_era_parents_resolve(category, year):
    pytest.importorskip("epsm_core")
    result = resolve_building_archetype(
        category=category, construction_year=year, climate_zone="SE.Zone3", ventilation="FTX"
    )
    assert result["assignment"]["category"] == category
    assert result["requirements"]["empirical_validation"].startswith("pending")
