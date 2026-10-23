# Development guide

EPSM Data is a dependency-free Python authoring library with a normalized frozen
LoD2 catalogue. Start with [catalogue inspection](catalogue-inspection.md) or
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

Optional construction drawing requires `.[visualization]`.

## Catalogue changes

Edit `src/epsm_data/datasets/lod2/catalogue.json` through a PR. The database has
materials and source records, layers, components, elements, construction sets and
archetype assignments. Reuse existing canonical IDs for identical physical
compositions. Keep Honeybee thermal links and Boverket product IDs explicit.
Preserve required units, layer order, area fractions and physical assumptions.

Run the catalogue checks and inspect `Catalogue.load().summary()`. Missing values
are reported as paths rather than replaced with defaults. Invalid supplied
physics and dangling references are rejected. Review affected users of any shared
definition. A PR and subsequent package release carry the maintenance history.

There are 28 families across four building types and seven eras. The first six
eras have three fabric alternatives; SE.07 has one. Three climate assignments
produce 228 slots from 76 physical configurations. No LoD1 or reverse-solving
workflow remains.

## Authoring and integration

Constructors and `with_changes()` create validated immutable definitions. Complete
archetype serialization is portable and deterministic for loaded catalogue data.
Operating profiles, explicit HVAC templates and declarative renovation actions
are independent inputs. See [operating profiles](operating-profiles.md) and
[platform ownership](building-application.md).

| Location | Responsibility |
| --- | --- |
| `src/epsm_data/domain` | Standard reusable physical types |
| `src/epsm_data/library.py` | Loaded LoD2 catalogue and completeness |
| `src/epsm_data/datasets/lod2` | Canonical definitions and linked source records |
| `src/epsm_data/datasets/standards` | Independent operating profiles |
| `src/epsm_data/catalogue.py`, `operations.py` | Declarative renovation definitions |
| `evidence/` | Retained source documents, outside runtime loading |
| `explorer/` | Local read-only catalogue inspection and separate remarks |
| `tests/`, `examples/` | Current contracts and runnable authoring examples |

Library calls use standard Python logging without installing console or file
handlers. The host application owns logging configuration. New integration work
should consume the public API described in the [migration guide](archetype-api-migration.md).
See [CI](ci.md) for repository checks.
