# Operating profiles

Bundled profiles supply reusable Swedish normal-use coefficients. Selection reads
local JSON and returns an immutable `OperatingProfile`.

```python
from epsm_data import available_operating_profiles, select_operating_profile

profiles = available_operating_profiles()
profile = select_operating_profile("multi_family")
assert profile.values["use"]["dhw_kwh_m2_year"] == 21
print(profile.values["requirements"])
```

`select_operating_profile(building_type, standard="sveby", version=None)` supports
`single_family`, `multi_family`, `office` and `school`. Residential uses Sveby 2.0;
office and school use their 1.0 editions. Omitting `version` selects the supported
edition. Single-family uses the residential fallback permitted by that source.

Sveby intensities use **Atemp**. Office and school schedules need a declared
calendar and active dates; representative study calendars are valid inputs.
Core expands schedules and applies area-based values to the building. Installed
ventilation, recovery, heating and cooling are separate system inputs.

The index includes an explicit `generic_other` screening profile, loaded by name
with `load_operating_profile("generic_other")`. It is a declared assumption for
an otherwise unsupported use. `load_standard_record(name)` returns detached source
data; `load_operating_profile(name)` returns the immutable descriptor.

## BEN normal-use hot water

```python
from epsm_data import select_dhw_profile

ben = select_dhw_profile("multi_family", purpose="epc_normal_use")
assert ben.values["dhw_kwh_m2_year"] == 25
assert ben.values["area_basis"] == "Atemp"
```

This selects useful thermal DHW under BEN BFS 2016:12 amended by BFS 2017:6,
before production efficiency. It excludes circulation and storage losses.
Supported types are `single_family`, `multi_family`, `office`, `school` and
`non_residential`. Purpose is explicit and the resource retains its source edition.
The selection leaves the Sveby profile unchanged.

## Custom definitions and exchange

`OperatingProfile(profile_id, values, source_references=(), notes=())` freezes
finite JSON-compatible values. For a custom Core handoff, place partial `use`,
`airflow` and `facade` inputs under `values["building_assumptions"]`.
`HVACTemplate` similarly carries independently reusable system inputs.

`to_dict()` / `from_dict()` preserve profiles without lookup. `with_changes()`
creates a validated replacement. The [offline profile notebook](../examples/01_operating_profiles.ipynb)
shows selection and inspection.
