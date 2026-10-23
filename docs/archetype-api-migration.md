# Migrate to the frozen LoD2 catalogue

The public catalogue now reads accepted physical definitions from
`datasets/lod2/catalogue.json`. The LoD1, parametric, calibration, detailed-review
and internal version workflows have been removed.

| Previous interface | Current interface |
| --- | --- |
| `Catalogue.load(parametric_path=..., detailed_path=...)` | `Catalogue.load(path=None)` with one normalized LoD2 file |
| `catalogue.parametric` or `catalogue.detailed` | Public catalogue selection and read-only definition indexes |
| Five-part slot ID ending with a ventilation system | `category:era:zone:state`, with `default` for SE.07 |
| `construction_sets()` keyed by family/state | `construction_sets` mapping keyed by canonical construction-set ID |
| `effective_configuration()` | `to_dict()` for the complete normalized catalogue |
| `assess(...)`, source-review and calibration reports | `completeness(id, state=...)` for missing fabric values |
| LoD1 scalar edits or reverse solving | Edit accepted material/layer/construction definitions |
| Source-specific school/CMF catalogue variants | The four canonical building types and seven eras |

```python
import json
from epsm_data import Catalogue, archetype_from_dict, archetype_to_dict

catalogue = Catalogue.load()
archetype = catalogue.get("mf_se02", state="existing")
slot = catalogue.get_slot("multi_family:SE.02:SE.Zone3:existing")
assert archetype.construction_set is catalogue.construction_sets[slot.construction_set_id]
restored = archetype_from_dict(json.loads(json.dumps(archetype_to_dict(archetype))))
assert restored == archetype
```

SE.01–SE.06 have Existing, Standard and Advanced alternatives. SE.07 has one
configuration with `state=None`. Climate-zone assignments reuse physical
constructions. No generic fifth building type or ventilation matrix remains.

Standard material-to-archetype authoring, portable serialization, operating
profiles and declarative renovation definitions remain available. Exchange-format
identification allows files to remain readable; it is separate from the removed
catalogue revision-management workflow.

EPSM and Studio adapters must migrate to the same public selection, indexes and
completeness report. Save actual resolved inputs with completed building runs.
Git and package releases provide catalogue maintenance history.
