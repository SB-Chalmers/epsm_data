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

EPSM Data is the offline authoring library and curated LoD2 construction catalogue
for the EPSM platform. It provides the same immutable hierarchy for catalogue and
custom definitions:

**Material → Layer → Component → Element / Window → ConstructionSet → Archetype**

Materials link thermal properties to Honeybee records and embodied-carbon inputs
to Boverket resource IDs. Shared physical definitions occur once and are reused
through references. Geometry, building occurrences and simulation belong to Core
and the wider [EPSM platform](https://github.com/SB-Chalmers/epsm/blob/main/docs/platform.md).

## Catalogue

The bundled catalogue contains **28 archetype families, 76 physical configurations
and 228 climate-zone assignments**:

- Four building types: single-family, multi-family, office and school.
- Seven construction eras: SE.01–SE.07.
- Existing, Standard and Advanced for SE.01–SE.06; one configuration for SE.07.
- Three climate zones. Zones classify the shared construction definitions.

SE.06 covers 2006–2021; SE.07 starts in 2022. Catalogue loading uses accepted LoD2
compositions directly. There are no LoD1 targets, inverse U-value solving,
calibration operations or internal definition-version workflows. Forward thermal
calculations remain available. Missing values are reported explicitly.

## Use

Requires Python 3.11 or newer:

```sh
python -m pip install -e .
python examples/archetype.py
```

```python
from epsm_data import Catalogue

catalogue = Catalogue.load()
archetype = catalogue.get("mf_se02", state="existing")
report = catalogue.completeness("mf_se02", state="existing")
print(report["complete"], report["missing_values"])
print(catalogue.summary())
```

`Catalogue.load(path)` also accepts a complete normalized catalogue JSON file.
Repeated loads produce deterministic identities and exchange data. Loaded indexes
are read-only; use the standard authoring constructors and `with_changes()` for
project definitions. Operating profiles and renovation definitions remain
independently available.

## Maintain

Correct the canonical JSON definitions in
`src/epsm_data/datasets/lod2/catalogue.json` through a pull request. Review shared
references, validate physical values and completeness, then publish the package.
Git carries the change history. Saved studies should preserve their actual inputs
and package/catalogue identification alongside results.

```sh
python -m pytest -q
python -m explorer.server
```

## Documentation

- [Catalogue inspection](docs/catalogue-inspection.md)
- [Authoring and exchange](docs/archetype-authoring.md)
- [Shared construction composition](docs/catalogue-composition.md)
- [Operating profiles](docs/operating-profiles.md)
- [Platform ownership](docs/building-application.md)
- [Migration guide](docs/archetype-api-migration.md)
- [Examples](examples/README.md) and [development guide](docs/guide.md)

## License and attribution

EPSM-owned software and documentation use the [MIT license](LICENSE). Honeybee,
Boverket and other third-party source data retain their providers' terms and
attribution. Retained source documents live in `evidence/`; they are separate from
the runtime catalogue.

Developed at Chalmers University of Technology for the EPSM research platform.
Funded by the Swedish Energy Agency, project P2024-04053. Partners: Lindholmen
Science Park AB, Sinom AB and Stiftelsen Chalmers Industriteknik.

Lead developer: Sanjay Somanath. Principal investigator: Alexander Hollberg.
Contributors: Yinan Yu and Dag Wästberg.
