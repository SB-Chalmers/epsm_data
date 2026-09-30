# EPSM Data

Offline Swedish building-archetype data and construction library. The frozen
LoD2 v1.3 baseline contains 90 canonical construction states and 1,080
classification slots: five categories, six eras, three climate zones, three
renovation states and four ventilation classifications. Seven construction roles
are available per state; building geometry determines which are present.

## Install and check

Requires Python 3.11 or newer. The core package has no external dependencies.

```sh
python -m pip install -e '.[dev]'
python -m epsm_data.parametric --check --summary
python -m epsm_data.detailed --check --lod2
python -m pytest -q
```

Install `.[visualization]` for section drawings and graph tools. Honeybee Energy
and `epsm_core` integrations require their respective optional installations.

## Use the catalogue

```python
from epsm_data import ArchetypeKey, load_parametric_catalogue

catalogue = load_parametric_catalogue()
slot = catalogue.get_slot(
    ArchetypeKey("multi_family", "SE.02", "SE.Zone3", "existing", "FTX")
)
print(slot.construction_set.u_values)
print(slot.infiltration.value)  # effective background air changes per hour
```

The active data live in `src/epsm_data/datasets/parametric` and
`src/epsm_data/datasets/layered`. Loading does not require source workbooks,
a database, an archive, or network access. Caller-owned catalogues remain
supported through explicit paths and immutable anchor/override operations.
Use separate copies for experiments to preserve this baseline.

Categories are SF, MF, Office, School and Generic. Generic explicitly follows
the corresponding MF physical construction; it is not a national stock average.
Climate and ventilation classifications do not modify the construction values.
Existing describes original period fabric; Standard and Advanced are independent
renovations of Existing. See [examples](examples) for construction, renovation,
and section-drawing usage.

## Explore and export

```sh
python -m explorer.server
python -m epsm_data.layered --state existing --export
python -m epsm_data.layered --state advanced --nominal-export
```

Open [the local explorer](http://127.0.0.1:8765) to browse construction layers,
thermal values and evidence. [Explorer documentation](explorer/README.md)
describes filters and remarks. Remarks are stored separately in the ignored
`data/local/explorer-notes.sqlite`; preserve that file when backing up local work.

Python callers can use `load_calibrated_archetype` and its `to_nominal_dict()`
method for role-preserving exports. `epsm_data.release.core_inputs` provides
optional native `epsm_core` inputs. Geometry, weather, operation, HVAC, ground
boundaries and attic ventilation remain caller inputs.

## Retained calibration tool

```sh
python -m tools.recalibrate_mf_se02
```

This existing tool previews a bounded, discrete thickness and framing-fraction
search for MF SE.02 against nominal U-value targets. Conductivity stays fixed;
ground roles are excluded. It prints candidate counts and selections as JSON
and never edits the packaged recipes. Its historical reference choices and
2% target criterion are specific to this archetype, so a feasible candidate is
not automatically a replacement for the reviewed current recipe. A null selection
means no feasible candidate under those bounds.

This is not calibration against EPCs or measured building energy use. Automatic
sample-based calibration and subsequent building validation are future work.

## Frozen baseline and evidence

`epsm-data-baseline-v1.3` identifies the local Git freeze. [BASELINE.json](BASELINE.json)
records SHA-256 hashes of every packaged dataset file, including packaged evidence.
The package version remains `0.3.0.dev0`; the construction release is LoD2 v1.3.
The regression suite checks the manifest and current packaged data.

[Cited evidence](evidence) and packaged provenance remain maintained. The
[current release note](evidence/lod2_v1_3/README.md) explains the construction
review, and the [claim register](evidence/lod2_v1_3/claims.json) records its evidence
and limitations. Older reports retained here support current citations; they
are not instructions to rebuild or overwrite the baseline.

EPC validation remains pending. Nominal layer U-values and legacy effective
ground values are distinct. Construction availability does not establish soil,
moisture, annual-energy or carbon readiness. Source transfers, assumed layer
choices and unresolved material mappings retain their documented limitations.

Retired authoring scripts, release workflows, reproduction tests, intermediate
snapshots and generated outputs are preserved locally under ignored `ARCHIVE/`.
They are not shipped or available in fresh clones. The dated archive contains
`relocations.json` and original tests/README for historical context. Git history
is unchanged; ongoing runtime outputs, caches and local databases stay ignored.

The legacy source-study helpers `load_office_reference()` and
`load_renovation_package()` predate the current seven-role/full-recipe layout and
are not compatible with the bundled v1.3 defaults. Their implementations are
preserved unchanged. For current office and renovation constructions, use
`load_calibrated_archetype(archetype_id="office_se05", renovation_state="standard")`
(or the desired archetype/state). Their former reproduction workflows and the
source-study office drawing example are archived.

Some immutable dataset locators name original archive paths. Their cited source
JSON files are also retained in `evidence/historical_sources`; the
[source index](evidence/source-index.json) maps original locators to tracked
copies and records their hashes. No runtime operation needs `ARCHIVE/`.
