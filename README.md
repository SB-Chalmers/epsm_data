# EPSM Data

Offline Swedish building-archetype and construction library. **All current
archetypes are frozen as of 9 October 2026:** database **1.5.0**, construction
release **LoD2 v1.4**, Python package **0.3.0.dev1**. The freeze preserves the
current values and assumptions; it does not establish building prediction accuracy.

## Start here

Use the local explorer to inspect archetypes, construction layers, U-values,
airflow assumptions and evidence:

```sh
.venv/bin/python -m explorer.server
```

Open [localhost:8765](http://127.0.0.1:8765). See the
[explorer guide](explorer/README.md) for filters, detailed constructions and remarks.
For a fresh installation, use Python 3.11 or newer:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

The core library has no external dependencies. Section drawings need
`.[visualization]`; native simulation inputs need a compatible `epsm_core`
installation. Honeybee integration needs Honeybee Energy.

## Read the frozen catalogue

```python
from epsm_data import ArchetypeKey, load_parametric_catalogue

catalogue = load_parametric_catalogue()
slot = catalogue.get_slot(
    ArchetypeKey("multi_family", "SE.02", "SE.Zone3", "existing", "FTX")
)
print(slot.construction_set.u_values)
print(slot.infiltration.to_dict())  # inspect units, reference basis and evidence
```

For physical layers and portable, role-preserving exports:

```python
from epsm_data import load_calibrated_archetype

model = load_calibrated_archetype(
    archetype_id="mf_se02", renovation_state="existing"
)
bundle = model.to_nominal_dict()
print(bundle["roles"])
print(bundle["readiness"])
```

The matrix contains **30 canonical archetypes**, **90 construction states** and
**1,080 classification slots**: five categories, six eras, three climate zones,
three renovation states and four ventilation classifications. Every canonical
state supplies seven construction roles. Geometry determines which roles are
present. Two additional source variants bring the detailed registry to
**32 archetypes and 92 states**; they are frozen too and do not add matrix slots.

Climate and ventilation classifications do not change construction values.
Standard and Advanced are independent renovations of Existing. Existing is an
original-era representative with a documented provisional surviving-stock window
exception for MF SE.02; it does not establish actual renovation history.
Generic follows MF physical constructions except the MF-only SE.02 existing
window update: Generic retains 2.8 W/(m²K), MF uses 2.2.

## Apply data to a building

Use `resolve_building_archetype` for explicit category/year classification and
independently evidenced component choices. See
[building application](docs/building-application.md) before creating a Core spec.
Geometry, weather, operation, HVAC, ground boundaries and attic exchange remain
caller inputs.

MF additional infiltration defaults use **L/s/m² Atemp**. Use the resolver's
`core_airflow_inputs` with Atemp as Core's load reference area. The legacy ACH
representation uses a 2.5 m reference height; it must not silently be applied to
another model volume. Other categories retain their source reference convention.
See [airflow definitions and handoff](docs/airflow-review-notes.md).

## What the validation supports

The completed 5 October study covers 85 buildings in 54 Gothenburg properties,
limited to MF SE.02 Existing / exhaust ventilation F / district heat. The final
selection retains the baseline with **no fitted overrides**: **54/85 within 20%**,
MAE **14.302 kWh/m²/year**. The accuracy target was not met; support remains
provisional and independent confirmation is pending. Other cells are unvalidated.

Read the [validation results](docs/mf-se02-data15-validation.md). The
[current cohort profile](cohort_profiles/2026-10-05-v2/README.md) supersedes the
historical ACH-based v1 profile and defaults to parent fallback while provisional.
Nominal construction acceptance is separate from ground, carbon and annual
simulation validation.

## Freeze and checks

[BASELINE.json](BASELINE.json) pins every packaged dataset by SHA-256. The local
Git tag `epsm-data-baseline-v1.5.0` identifies this freeze. The
[freeze record](docs/frozen-baseline.md) describes its scope, checks and remaining
limitations. The older `epsm-data-baseline-v1.3` tag remains historical.

```sh
.venv/bin/python -m epsm_data.parametric --check --summary
.venv/bin/python -m epsm_data.layered --check
.venv/bin/python -m pytest -q
```

Use separate catalogue/registry copies for experiments. A future default change
needs a new reviewed baseline and updated checksums; do not overwrite historical
evidence or fit defaults from a building's heating residual.

## Repository map

| Location | Purpose |
| --- | --- |
| `src/epsm_data/datasets/` | Frozen packaged catalogue, recipes, materials and evidence |
| `src/epsm_data/` | Loaders, exports and building application APIs |
| `explorer/` | Local viewer |
| `docs/` | Current usage, freeze and validation guidance |
| `evidence/` | Cited sources and historical release records |
| `cohort_profiles/current.json` | Current profile pointer; dated versions preserve history |
| `examples/` | Construction, renovation and section examples |
| `tests/` | Dataset integrity and runtime contracts |
| `ARCHIVE/` | Ignored local development history; absent from fresh clones |

Runtime needs no archive, source workbooks, database or network connection.
[The source index](evidence/source-index.json) maps historical locators to retained
source copies. Explorer remarks live separately in ignored
`data/local/explorer-notes.sqlite`; preserve that file when backing up local work.

`load_office_reference()` and `load_renovation_package()` are retained legacy
source-study APIs and are incompatible with the bundled full-recipe defaults.
For current office/renovation data, use `load_calibrated_archetype` with the desired
archetype and state. `tools.recalibrate_mf_se02` remains a read-only historical
thickness/framing search against nominal targets; its results are not approved
changes to this frozen baseline.
