# epsm_data

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)](https://github.com/SB-Chalmers/epsm_data/actions/workflows/ci.yml) [![Releases](https://img.shields.io/badge/releases-GitHub-181717?logo=github&logoColor=white)](https://github.com/SB-Chalmers/epsm_data/releases) [![Issues](https://img.shields.io/badge/issues-GitHub-181717?logo=github&logoColor=white)](https://github.com/SB-Chalmers/epsm_data/issues)

Author and reuse building materials, constructions, archetypes, operating
profiles and renovation measures. The package provides EPSM's shared physical
definitions and current construction catalogue without requiring Core, a database
or a simulation engine.

## Getting started

Use Python 3.11 or newer. From a terminal on macOS or Linux:

```sh
git clone https://github.com/SB-Chalmers/epsm_data.git
cd epsm_data
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python examples/archetype.py
```

The example authors and serializes an illustrative construction entirely offline.
To select a bundled archetype:

```python
from epsm_data import Catalogue

catalogue = Catalogue.load()
archetype = catalogue.for_year("multi_family", 1970)
construction = archetype.construction_set
```

Catalogue records retain their sources and assumptions. Core assigns definitions
to building geometry; EPSM owns catalogue-to-building application.

## Documentation

- [Catalogue inspection and reuse](docs/catalogue-inspection.md)
- [Archetype authoring and exchange](docs/archetype-authoring.md)
- [Operating profiles](docs/operating-profiles.md)
- [Examples and notebooks](examples/README.md)
- [Project guide and development](docs/guide.md)

## License

A repository software license has not been specified. Consult the retained source
records and attribution before reusing catalogue data.
