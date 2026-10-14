"""Shared physical graph, safe editing, renovation and source input boundaries."""

import json

import pytest

from epsm_data import (
    HVACTemplate,
    OperatingProfile,
    load_operating_profile,
)


@pytest.mark.parametrize("name", ["sveby_residential_v2","sveby_office_v1","sveby_school_v1","dhw_epc_normal_use_v1","generic_other"])
def test_named_operating_profiles_are_independent_plain_data(name):
    profile = load_operating_profile(name)
    assert OperatingProfile.from_dict(json.loads(json.dumps(profile.to_dict()))) == profile
    assert profile.source_references
    with pytest.raises(TypeError):
        profile.values["profile_id"] = "bad"


def test_hvac_template_rejects_nonportable_values():
    with pytest.raises(ValueError):
        HVACTemplate("bad",{"recovery":float("nan")})

