# Development guide

EPSM Data is a dependency-free offline library with one normalized LoD2 catalogue.
Start with [catalogue inspection](catalogue-inspection.md) or
[custom authoring](archetype-authoring.md).

## Local development

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check src tests explorer examples
python -m explorer.server
```

Construction drawing uses the optional `visualization` extra. Refreshing geographic
boundaries uses `geography`; ordinary catalogue and climate lookup need neither.

## Catalogue maintenance

Edit `src/epsm_data/datasets/lod2/catalogue.json` through a pull request. Reuse
canonical IDs for identical compositions. Preserve units, physical order, area
fractions and source locators. Review all users of a changed shared definition.

Run the tests and inspect `Catalogue.load().summary()` and `sanity_report()`.
Supplied invalid physics and dangling references are errors. Missing values stay
visible. Update the independent fixtures only when the underlying contract or
reviewed source interpretation changes.

| Location | Responsibility |
| --- | --- |
| `src/epsm_data/domain` | Immutable physical types and editing |
| `src/epsm_data/library.py` | Catalogue loading, selection and completeness |
| `src/epsm_data/datasets/lod2` | Canonical physical and source records |
| `src/epsm_data/datasets/standards` | Reusable operating profiles |
| `src/epsm_data/catalogue.py`, `operations.py` | Declarative renovation definitions |
| `src/epsm_data/datasets/sanity` | Packaged forward-check references |
| `evidence/` | Source evidence, outside runtime loading |
| `explorer/` | Local catalogue inspection and separate remarks |
| `tests/`, `examples/` | Behavioral contracts and runnable examples |

The host configures Python logging. Library import installs no output handler.
See [CI](ci.md) for automated checks and [building application](building-application.md)
for package responsibilities.
