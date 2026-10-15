# EPSM Data examples

Use Python 3.11 or newer and install this repository's development revision:
`python -m pip install .`. The profile notebook needs only the installed package
and a Python notebook kernel. Select that environment's kernel and run each
notebook from a fresh kernel. No sibling source imports are needed.

| Example | Task and requirements |
| --- | --- |
| [01 Operating profiles](01_operating_profiles.ipynb) | Inspect immutable definitions, explicit BEN DHW and portable editing offline; no files are written. |
| [02 Author an archetype](02_author_archetype.ipynb) | Assemble materials through a composed archetype and round-trip format 4 offline; no files are written. |
| [Archetype script](archetype.py) | Inspect a predefined construction archetype. |
| [Renovation script](renovations.py) | Inspect existing renovation definitions. |

Older drawing scripts require the `visualization` extra. Source editions are
recorded on the returned objects; selecting one is an assumption, not a measured
building observation. Notebook outputs and execution counts are cleared before
commit. Installed-wheel execution is recorded in the pull request.
