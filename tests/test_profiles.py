"""Shared physical graph, safe editing, renovation and source input boundaries."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from epsm_data import (
    HVACTemplate,
    OperatingProfile,
    load_operating_profile,
)


def test_selection_keeps_sveby_and_ben_dhw_separate():
    from epsm_data import select_dhw_profile, select_operating_profile

    residential = select_operating_profile("multi_family")
    assert residential.values["use"]["dhw_kwh_m2_year"] == 21
    ben = select_dhw_profile("multi_family", purpose="epc_normal_use")
    assert ben.values["dhw_kwh_m2_year"] == 25
    assert ben.values["area_basis"] == "Atemp"
    assert ben.values["source_locator"]
    assert "production efficiency" in ben.values["energy_boundary"]
    assert OperatingProfile.from_dict(json.loads(json.dumps(ben.to_dict()))) == ben
    with pytest.raises(TypeError):
        select_dhw_profile("multi_family")


@pytest.mark.parametrize("era, setpoint", [("SE.01", 22.2), ("SE.02", 22.6), ("SE.05", 23.0), ("SE.07", 23.0)])
def test_measured_use_substitutes_betsi_setpoints_by_era(era, setpoint):
    from epsm_data import select_operating_profile

    sveby = select_operating_profile("multi_family")
    measured = select_operating_profile("multi_family", standard="measured", era=era)
    assert measured.values["use"]["heating_setpoint_c"] == setpoint
    assert sveby.values["use"]["heating_setpoint_c"] == 21.0
    assert measured.profile_id == f"epsm.measured_use.v1.multi_family.{era}"
    assert measured.values["measured_use"]["base_profile_id"] == sveby.profile_id
    assert measured.values["measured_use"]["ventilation"]["S"]["total_air_change_ach"] == 0.39
    unchanged = {k: v for k, v in measured.values["use"].items() if k != "heating_setpoint_c"}
    assert unchanged == {k: v for k, v in sveby.values["use"].items() if k != "heating_setpoint_c"}
    assert OperatingProfile.from_dict(json.loads(json.dumps(measured.to_dict()))) == measured


def test_measured_office_ventilation_and_explicit_selection_rules():
    from epsm_data import available_operating_profiles, select_operating_profile

    office = select_operating_profile("office", standard="measured")
    assert office.values["use"]["mechanical_vent_l_s_m2"] == 1.6
    assert (office.values["operation_inputs"]["ventilation_start_hour"],
            office.values["operation_inputs"]["ventilation_hours"]) == (6, 14)
    for building_type in ("single_family", "school"):
        profile = select_operating_profile(building_type, standard="measured")
        assert profile.values == select_operating_profile(building_type).values
        assert "no value adopted" in profile.notes[-1]
    with pytest.raises(ValueError, match="requires an era"):
        select_operating_profile("multi_family", standard="measured")
    with pytest.raises(ValueError, match="does not vary with era"):
        select_operating_profile("multi_family", era="SE.01")
    assert "measured_use_v1" not in available_operating_profiles()


@pytest.mark.parametrize(
    "building_type,name",
    [
        ("single_family", "sveby_residential_v2"),
        ("multi_family", "sveby_residential_v2"),
        ("office", "sveby_office_v1"),
        ("school", "sveby_school_v1"),
    ],
)
def test_supported_selection_and_requirements(building_type, name):
    from epsm_data import select_operating_profile

    profile = select_operating_profile(building_type)
    assert profile.profile_id == load_operating_profile(name).profile_id
    assert building_type in profile.values["applicability"]["building_types"]
    assert "load_reference_area_m2" in profile.values["requirements"]
    if building_type in ("office", "school"):
        assert "calendar" in profile.values["requirements"]
    if building_type == "single_family":
        assert any("fallback" in note.lower() for note in profile.notes)


def test_unsupported_selections_do_not_silently_choose_generic():
    from epsm_data import select_dhw_profile, select_operating_profile

    for kwargs in (
        {"building_type": "hotel"},
        {"building_type": "office", "version": "2"},
        {"building_type": "office", "standard": "unknown"},
    ):
        with pytest.raises(ValueError):
            select_operating_profile(**kwargs)
    for kwargs in (
        {"building_type": "hotel", "purpose": "epc_normal_use"},
        {"building_type": "office", "purpose": "actual_use"},
        {"building_type": "office", "purpose": "epc_normal_use", "version": "2"},
    ):
        with pytest.raises(ValueError):
            select_dhw_profile(**kwargs)


def test_profile_index_and_inputs_are_independent_and_immutable():
    from epsm_data import available_operating_profiles

    index = available_operating_profiles()
    assert set(index) == {
        "sveby_residential_v2",
        "sveby_office_v1",
        "sveby_school_v1",
        "generic_other",
    }
    with pytest.raises(TypeError):
        index["other"] = index["generic_other"]
    with pytest.raises(TypeError):
        index["sveby_office_v1"].values["operation_inputs"]["occupant_density_per_m2"] = 2
    detached = index["sveby_office_v1"].to_dict()
    detached["values"]["operation_inputs"]["occupant_density_per_m2"] = 2
    assert (
        available_operating_profiles()["sveby_office_v1"].values["operation_inputs"][
            "occupant_density_per_m2"
        ]
        == 0.05
    )
    assert "screening" in " ".join(index["generic_other"].notes)


def test_profile_inspection_is_bounded_and_has_no_io(monkeypatch):
    import epsm_data.profiles.operating as profiles

    profile = OperatingProfile("\\n😀" * 1000, {"large": list(range(1000))})
    monkeypatch.setattr(
        profiles, "files", lambda *args: pytest.fail("representation read resources")
    )
    for text in (repr(profile), str(profile)):
        assert len(text) <= 160
        assert "\n" not in text
        assert "OperatingProfile" in text
    assert profile.summary()["profile_id"] == profile.profile_id


def test_profile_selection_works_without_core_epsm_or_import_time_reads():
    import epsm_data

    code = """
import importlib.abc
import importlib.resources
import sys
class BlockConsumers(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('epsm_core', 'epsm'):
            raise AssertionError('Consumer import: ' + fullname)
sys.meta_path.insert(0, BlockConsumers())
original = importlib.resources.files
def denied(*args, **kwargs):
    raise AssertionError('Import-time resource read')
importlib.resources.files = denied
import epsm_data
importlib.resources.files = original
import epsm_data.profiles.operating
epsm_data.profiles.operating.files = original
assert epsm_data.select_operating_profile('school').values['reference_active_days'] == 220
assert epsm_data.select_dhw_profile('single_family', purpose='epc_normal_use').values['dhw_kwh_m2_year'] == 20
"""
    environment = {**os.environ, "PYTHONPATH": str(Path(epsm_data.__file__).parent.parent)}
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=environment
    )
    assert result.returncode == 0, result.stderr


def test_source_loader_rejects_wrong_identity(monkeypatch):
    import epsm_data.profiles.operating as profiles

    class Resource:
        def joinpath(self, *args):
            return self

        def read_text(self, **kwargs):
            return json.dumps({"profile_id": "wrong", "source_uri": "test:source"})

    monkeypatch.setattr(profiles, "files", lambda *args: Resource())
    with pytest.raises(ValueError, match="source identity"):
        profiles.load_standard_record("sveby_office_v1")


def test_existing_clock_and_zone_definitions_are_preserved():
    from epsm_data import select_operating_profile

    office = select_operating_profile("office").values
    assert office["operation_inputs"]["occupancy_start_hour"] == 8
    assert office["operation_inputs"]["occupancy_hours"] == 9
    assert office["operation_inputs"]["ventilation_start_hour"] == 7
    assert office["operation_inputs"]["ventilation_hours"] == 12
    school = select_operating_profile("school").values
    assert school["operation_inputs"]["mechanical_vent_l_s_m2"] == 3
    assert school["operation_inputs"]["service_mechanical_vent_l_s_m2"] == 0.35
    assert school["completion_inputs"]["operating_start_hour"] == 7
    assert school["completion_inputs"]["occupancy_start_hour"] == 9


@pytest.mark.parametrize(
    "name",
    [
        "sveby_residential_v2",
        "sveby_office_v1",
        "sveby_school_v1",
        "dhw_epc_normal_use_v1",
        "generic_other",
    ],
)
def test_named_operating_profiles_are_independent_plain_data(name):
    profile = load_operating_profile(name)
    assert OperatingProfile.from_dict(json.loads(json.dumps(profile.to_dict()))) == profile
    assert profile.source_references
    with pytest.raises(TypeError):
        profile.values["profile_id"] = "bad"


def test_hvac_template_rejects_nonportable_values():
    with pytest.raises(ValueError):
        HVACTemplate("bad", {"recovery": float("nan")})
