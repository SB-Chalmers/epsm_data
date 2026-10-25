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

EPSM Data is a dependency-free Python library and the curated LoD2 construction
catalogue for the EPSM platform. Catalogue selections and custom definitions use
the same immutable hierarchy:

**Material → Layer → Component → Element / Window → ConstructionSet → Archetype**

## Use the catalogue

Requires Python 3.11 or newer. Install from this checkout:

```sh
python -m pip install -e .
```

```python
from epsm_data import BuildingElement, Catalogue

catalogue = Catalogue.load()
archetype = catalogue.for_year("multi_family", 1970, state="existing")
wall = archetype.construction_set.elements[BuildingElement.EXT_WALL]
print(wall.u_value)
print(catalogue.completeness("mf_se02", state="existing"))
print(catalogue.sanity_report()["summary"])
```

The catalogue includes **28 families, 76 physical configurations and 228
climate-zone assignments**:

- Single-family, multi-family, office and school.
- Seven construction eras, SE.01–SE.07.
- Existing, Standard and Advanced states for SE.01–SE.06; one state for SE.07.
- Three Swedish climate zones sharing the stored physical definitions.

SE.06 covers 2006–2021; SE.07 starts in 2022. These are reusable stock
representatives: an address, measured building record or individual survey is
optional.

## Sources and checks

Every thermal grade is an EPSM-authored record with stated provenance: a Swedish
product declaration or EPD, a Swedish design value, a TABULA grade or a documented
derivation. Embodied carbon links to pinned Boverket resources or declared EPDs.
All sources are cached offline; `catalogue.check_sources()` verifies them and
online version checks are an explicit request.

Forward sanity checks compare the residential configurations with TABULA U-values
and renovation packages, screen materials and assemblies, and keep every
assumption or gap visible. They never repair the catalogue.

`catalogue.to_dict()` exports the reference-only catalogue;
`catalogue.resolved_dict()` expands its physical and source data for auditing and
custom authoring.

## Author and inspect

Create project definitions with constructors and `with_changes()`, save complete
archetypes as portable JSON, or export forward nominal construction properties.
Operating profiles and renovation definitions are independently reusable.

- [Catalogue selection and inspection](docs/catalogue-inspection.md)
- [Custom authoring and exchange](docs/archetype-authoring.md)
- [Construction composition and source mappings](docs/catalogue-composition.md)
- [Pinned source cache and version checks](docs/source-cache.md)
- [Sanity checks](docs/catalogue-sanity.md)
- [Operating profiles](docs/operating-profiles.md)
- [Offline climate-zone lookup](docs/climate-zones.md)
- [Platform ownership](docs/building-application.md)
- [Examples](examples/README.md) and [development guide](docs/guide.md)

## Maintain

Correct the canonical JSON in `src/epsm_data/datasets/lod2/catalogue.json` through
a pull request. Review shared references, run the tests and the sanity report,
then publish the package. Git carries the change history; saved studies should
preserve their actual inputs and package/catalogue identification.

```sh
python -m pytest -q
python -m epsm_data.cli --sanity --check
python -m explorer.server
```

Geometry, building occurrences and simulation belong to Core and the wider
[EPSM platform](https://github.com/SB-Chalmers/epsm/blob/main/docs/platform.md).

## License and attribution

EPSM-owned software and documentation use the [MIT license](LICENSE). Boverket,
EPD and other third-party source data retain their providers' terms and
attribution. Retained source documents live in `evidence/`; they are separate from
the runtime catalogue.

Developed at Chalmers University of Technology for the EPSM research platform.
Funded by the Swedish Energy Agency, project P2024-04053. Partners: Lindholmen
Science Park AB, Sinom AB and Stiftelsen Chalmers Industriteknik.

Lead developer: Sanjay Somanath. Principal investigator: Alexander Hollberg.
Contributors: Yinan Yu and Dag Wästberg.
