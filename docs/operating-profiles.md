# Operating profiles and explicit selections

Data owns reusable definitions and sources. Core expands calendars, validates
physical inputs and creates schedules; EPSM combines them with a Building.
Selecting a profile reads bundled JSON only, with no database or network access.

```python
from epsm_data import available_operating_profiles, select_operating_profile

profiles = available_operating_profiles()
profile = select_operating_profile("multi_family")
assert profile.values["use"]["dhw_kwh_m2_year"] == 21
requirements = profile.values["requirements"]
```

The read-only index contains the residential, office, school and explicit generic
profiles. Its values are the same immutable `OperatingProfile` objects returned
by named loading. `values["applicability"]` states supported building types;
`values["requirements"]` identifies caller inputs. Each access reads fresh
packaged records; editing a detached `to_dict()` cannot change a later load.

`select_operating_profile(building_type, standard="sveby", version=None)` supports
`single_family`, `multi_family`, `office` and `school`. Residential uses Sveby 2.0,
office and school use their published 1.0 editions. Specify `version="2"` or
`"2.0"` for residential, `"1"` or `"1.0"` for office/school. An omitted version
selects the currently supported edition. Single-family selection records the
source's permitted residential fallback in `notes`. Unsupported selections raise
`ValueError`; no hotel, retail or other use silently becomes the generic profile.

Office/school need an explicit project calendar. All profiles require a compatible
load reference area; the published Sveby intensities use Atemp. Selecting minimum
ventilation flow does not select an installed ventilation topology, heating
carrier, recovery system or cooling installation. The existing source records
retain their limitations and separate completion assumptions. `operation_inputs`
contains operating coefficients transferred unchanged from Core; this move does
not independently verify those source mappings. Existing source locators remain
available.
`completion_inputs` contains existing EPSM clock placements and fallback choices.
This transfer changes no coefficient, physical calculation or schedule.

## BEN DHW is a separate choice

```python
from epsm_data import select_dhw_profile

ben = select_dhw_profile("multi_family", purpose="epc_normal_use")
assert ben.values["dhw_kwh_m2_year"] == 25
assert ben.values["area_basis"] == "Atemp"
```

This selects the historical BEN BFS 2016:12, amended by BFS 2017:6, useful thermal
DHW coefficient before production efficiency. It excludes circulation/storage
losses and does not change a Sveby profile. Supported types are `single_family`,
`multi_family`, `office`, `school` and `non_residential`. The purpose is mandatory;
only resource version `"1"` is supported. Sources, the type-specific locator,
energy boundary and exclusions remain in the portable descriptor.

## Authoring and exchange

`OperatingProfile(profile_id, values, source_references=(), notes=())` accepts
finite JSON-compatible values and freezes nested containers. For a custom Core
handoff, put caller-authored partial `use`, `airflow` and `facade` values under
`values["building_assumptions"]`; Core owns physical validation and missing-input
requirements. Standard records retain their source structure. No catalogue is
needed to construct or deserialize either form.

`to_dict()` / `OperatingProfile.from_dict()` preserve the complete profile without
lookup. `with_changes()` returns a validated independent replacement. `summary()`
returns all loaded inputs; `repr()` and `str()` stay bounded and perform no I/O.

Existing `load_operating_profile(name)`, `load_standard_record(name)` and
`load_generic_other_template()` remain available. Load `generic_other` explicitly
when a labelled screening assumption is appropriate. It is not a published
normal-use standard. This PR adds selectors; it removes no existing API.

Try [the offline profile notebook](../examples/01_operating_profiles.ipynb).
