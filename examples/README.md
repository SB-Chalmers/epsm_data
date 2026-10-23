# EPSM Data examples

Install Python 3.11+ and this package with `python -m pip install -e .`. Select that
environment's notebook kernel. Examples run offline without Core, a database or a
simulation engine. Notebook outputs and execution counts are cleared in source.

| Example | Task |
| --- | --- |
| [01 Operating profiles](01_operating_profiles.ipynb) | Inspect and edit independent portable operating definitions |
| [02 Author an archetype](02_author_archetype.ipynb) | Build the material-to-archetype hierarchy and round-trip complete exchange |
| [03 Catalogue authoring](03_catalogue_authoring.ipynb) | Select LoD2 fabric, reuse canonical definitions and inspect missing values |
| [Archetype script](archetype.py) | Author a synthetic wall/window example |
| [Catalogue composition](catalogue_composition.py) | Inspect all three fabric alternatives and their completeness |
| [Renovations](renovations.py) | Author explicit construction and system actions |
| [Sections](sections.py) | Draw the accepted MF SE.02 constructions; requires `.[visualization]` |

Catalogue selections are reusable representative definitions. Actual geometry,
site conditions and installed systems belong to the consuming project. No example
runs LoD1 solving, calibration or an evidence-acceptance workflow.
