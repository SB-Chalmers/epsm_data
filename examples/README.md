# EPSM Data examples

Four short notebooks, in reading order. Each runs offline from the catalogue bundled
with the package; none needs EPSM Core, a database, a network connection or a
simulation engine.

## Setup

Use Python 3.11 or newer and install the package from this checkout:

```bash
python -m pip install -e ".[visualization]"
```

The `visualization` extra adds matplotlib, which only notebook 04 needs. Start Jupyter
in `examples/` and select the kernel of the environment you installed into. The
committed notebooks keep their outputs so you can read them without running them.

## Notebooks

1. [Select an archetype](01_select_an_archetype.ipynb). Load the catalogue, see what
   it covers (four building types, eras SE.01–SE.07, three renovation states, three
   climate zones) and select the archetype for a building by type, construction year
   and state. Inspect its U-values, window, infiltration, thermal-bridge assumption
   and sources.
2. [Operation and systems](02_operation_and_systems.ipynb). Choose an operating
   profile (Sveby normal use or measured stock operation by era), the BEN DHW
   coefficient, a ventilation template for an observed system and the facade
   window-to-wall ratios.
3. [Author and edit](03_author_and_edit.ipynb). Build a small archetype from your own
   materials, edit archetypes without changing the originals, save and restore one as
   JSON, and export and check the construction handover that EPSM Core reads.
4. [Renovation states and sections](04_renovation_states_and_sections.ipynb). Compare
   the existing, standard and advanced states of one archetype, see what each
   renovation changes and draw the constructions as sections. Needs the
   `visualization` extra.

`tests/test_examples.py` runs every notebook from a fresh kernel as part of the test
suite.
