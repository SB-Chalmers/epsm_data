# One archetype route and explicit inspection

See EPSM's [supported package manifest](https://github.com/SB-Chalmers/epsm/blob/main/compatibility.json)
and [platform version guidance](https://github.com/SB-Chalmers/epsm/blob/main/docs/platform-compatibility.md)
for the current coordinated interfaces.

Use `Catalogue.get()` or `for_year()` for predefined physical definitions. They
return the same `Archetype` used for custom authoring and do not require a target
match. `with_changes()` retains immutable editing. Core owns physical conversion,
calendars and compilation; EPSM owns geometry-to-archetype assembly and reports.

The coordinated consumer migration and installed-wheel checks precede removal of
the old interfaces. No source records, thermal targets, physical recipes or
scientific assessment algorithms change in this cleanup. Historical study imports
and dated reviews describe their original APIs; they are not current usage guides.

| Earlier interface | Current public route |
| --- | --- |
| `load_calibrated_archetype(...).archetype` for selection | `Catalogue.load(...).get(id, state=...)` |
| `load_parametric_catalogue(...)` | `Catalogue.load(parametric_path=...).parametric` for distinct effective-property inspection; use Catalogue inspection methods for common classification |
| `load_detailed_catalogue(...)` | `Catalogue.load(detailed_path=...).detailed` for sources, materials, boundaries, caveats and completeness |
| Explicit calibrated result/report | `catalogue.assess(id, state=...)`; returns the existing advanced evidence wrapper |
| `load_school_reference(...)` | `catalogue.source_reference("school_fridhem")` for draft source evidence; select the physical definition with `get()` |
| `load_office_reference(...)` | Inspect `detailed.review("office_se05", "existing")`, `detailed.resolve_material(id)`, `nominal_metadata()` and `assess()`; see the known limitation below |
| `Archetype.to_dict()`, `to_consumption_contract()`, `export_json()`, `export_consumption_contracts()` | `archetype_to_dict()` / `archetype_from_dict()` for complete format-4 exchange; `summary()` for explicit inspection |
| Lossy `export_construction_sets()` | Role-preserving `export_nominal_constructions(archetype, metadata=...)`; select applicable roles explicitly |
| `epsm_data.application.resolve_building_archetype` or root alias | `epsm.catalogue_application.resolve_building_archetype`; whole Building application uses `building.apply_archetype()` |
| `epsm_data.release.core_inputs` / `apply_attic_ventilation` | Same named functions in `epsm.catalogue_release` |
| `epsm_data.validate_native_handover` | `epsm.catalogue_validation.validate_native_handover`; pure `validate_nominal_handover` remains in Data |

Old construction-loader implementation functions are now private. Their algorithms
remain internal assessment/registry machinery, rather than competing selection
routes. `Catalogue.assess` can fail target acceptance without preventing `get`.
Supported alternatives such as `mf_1950` retain their separate recorded-target
assessment, including its original source and target revision. References such as
`school_fridhem` lack an assessment schema: an explicit unavailable-assessment
error leaves their physical definitions and source records accessible.

```python
import json
from epsm_data import Catalogue, archetype_from_dict, archetype_to_dict
from epsm_data import export_nominal_constructions

catalogue = Catalogue.load()
archetype = catalogue.get("mf_se02", state="existing")
restored = archetype_from_dict(json.loads(json.dumps(archetype_to_dict(archetype))))
assert restored == archetype
bundle = export_nominal_constructions(
    archetype, metadata=catalogue.nominal_metadata("mf_se02", state="existing")
)
assert "BASEMENT_WALL" in bundle["core"]
assessment = catalogue.assess("mf_se02", state="existing")
assert assessment.archetype.construction_set == archetype.construction_set
```

Complete format-4 exchange preserves profiles, templates, unresolved envelope
bases, provenance, material identities and physical order without catalogue
lookup. Readers for saved formats 1–3 remain unchanged. The earlier calibrated
wrapper remains accepted by the pure nominal exporter as an advanced assessment
adapter. Pure material/layer/construction serializers and distinct assessment
wrapper exports remain available.

The historical office-only reference loader already fails on the starting
catalogue: at least one `office_*` material lacks its expected
`user_data.source_thermal_properties`. `source_reference("office_se05")` reports
that missing source metadata explicitly. It neither fabricates source properties
nor labels applied values as measured evidence. This is not a complete one-to-one
replacement for that historical report. The working detailed, material, nominal
context and canonical assessment views preserve available evidence. Complete
caller-supplied source records can still use the original internal algorithm;
scientific/source corrections require separate reviewed changes.
