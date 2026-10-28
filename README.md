# EPSM Data

<!-- EPSM introduction: Pocket CAD -->
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/welcome/epsm_data-dark.png">
  <img src="docs/assets/welcome/epsm_data.png" width="160" height="160" alt="EPSM Data — Three material and assumption panels; the middle panel is the effective selection.">
</picture>

Meet the materials and constructions behind an EPSM building. EPSM Data helps
you find, inspect and author reusable materials, layered constructions,
archetypes, operating profiles and renovation measures. Explore the catalogue
offline, without Core, a database or a simulation engine.

**[Explore the EPSM platform →](https://github.com/SB-Chalmers/epsm/blob/main/docs/platform.md)**
<!-- /EPSM introduction -->

EPSM Data is a Python library and the catalogue of representative Swedish
buildings (LoD2 archetypes) for the EPSM platform. It serves researchers and
developers who need typical constructions, operating profiles and renovation
states for a Swedish building type and construction era. It has no runtime
dependencies and works offline. It owns:

- **Construction classes** shared with Core: Material → Layer → Component →
  Element / Window → ConstructionSet → Archetype.
- **The catalogue**: four building types, eras SE.01–SE.07, three renovation
  states and three climate zones (228 assignments of 76 configurations).
- **Operating profiles, system templates, renovation definitions**, pinned
  thermal and carbon **sources**, and **sanity checks** against TABULA.

Geometry, buildings and simulation belong to `epsm_core` and `epsm`; life-cycle
assessment to `epsm_lca`; stock records to `epsm_db`.

## Install

Requires Python 3.11 or newer. Optional extras: `visualization` for section
drawings and `geography` for rebuilding climate-zone boundaries.

```sh
python -m pip install -e .
```

## Quick start

```python
from epsm_data import Catalogue, climate_zone_for_point

catalogue = Catalogue.load()
archetype = catalogue.for_year("multi_family", 1970, state="existing")
print(archetype.envelope_u_values["EXT_WALL"])  # W/(m² K)
print(catalogue.completeness("mf_se02", state="existing"))
print(catalogue.sanity_report()["summary"])
print(climate_zone_for_point(674571.866, 6580743.008))  # SE.Zone3
```

## Documentation

- [Catalogue](docs/catalogue.md): types, eras, states, selection, composition, Core handover
- [Authoring](docs/authoring.md): write, edit and save archetypes; apply them to a building
- [Profiles](docs/profiles.md): operating profiles, ventilation templates, window-to-wall ratios
- [Sources](docs/sources.md): the pinned source cache, thermal and carbon records
- [Sanity checks](docs/sanity.md): the screens, the report and the `epsm-catalogue` command
- [Climate zones](docs/climate-zones.md): offline location-to-zone lookup
- [Validation](docs/validation.md): the measured-data validation contract

Notebooks: [01 Select an archetype](examples/01_select_an_archetype.ipynb),
[02 Operation and systems](examples/02_operation_and_systems.ipynb),
[03 Author and edit](examples/03_author_and_edit.ipynb) and
[04 Renovation states and sections](examples/04_renovation_states_and_sections.ipynb).

## Layout

```text
src/epsm_data/
├── domain/          shared construction classes, Material to Archetype
├── catalogue/       selection, keys, authoring, serialization, Core handover
├── profiles.py      operating profiles (Sveby, measured use, BEN hot water)
├── templates.py     ventilation templates and facade window ratios
├── renovation/      renovation measures and the operations they make
├── sanity/          read-only screens of the catalogue
├── sources/         the pinned source cache and its records
├── datasets/        bundled data: lod2, profiles, sources, sanity, climate_zones
├── climate_zones.py location-to-zone lookup
├── carbon.py        retained-stock carbon scope
├── plotting.py      construction section drawings
└── cli.py           the epsm-catalogue command
```

`evidence/` holds source documents; it is not loaded at run time.

## Development

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check src tests examples
epsm-catalogue --sanity --check
```

Edit the catalogue in `src/epsm_data/datasets/lod2/catalogue.json` through a
pull request. Reuse IDs for identical compositions, keep units, layer order,
fractions and source locators, and check every construction that shares a changed
definition. After a deliberate physical change, refresh the regression snapshot
`tests/fixtures/lod2-physics.json` with `python tests/test_catalogue_physics.py`
and review both diffs together.

Pull requests run [ci.yml](.github/workflows/ci.yml) (Ruff, tests, wheel build).
Before a release, run the manual [tests.yml](.github/workflows/tests.yml), which
also covers both extras. The library adds no logging handler.

## License and attribution

EPSM-owned software and documentation use the [MIT license](LICENSE). Boverket,
EPD and other third-party source data keep their providers' terms and
attribution.

Developed at Chalmers University of Technology for the EPSM research platform.
Funded by the Swedish Energy Agency, project P2024-04053. Partners: Lindholmen
Science Park AB, Sinom AB and Stiftelsen Chalmers Industriteknik.

Lead developer: Sanjay Somanath. Principal investigator: Alexander Hollberg.
Contributors: Yinan Yu and Dag Wästberg.
