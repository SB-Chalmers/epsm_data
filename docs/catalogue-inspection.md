# Select and reuse a predefined archetype

The predefined catalogue and custom authoring use the same `Archetype` class.
`Catalogue.load()` explicitly reads the physical registries and bundled operating
profiles. It needs no Core, database, network or simulation engine.

```python
from epsm_data import Catalogue

catalogue = Catalogue.load()
archetype = catalogue.for_year("multi_family", 1970)
assert archetype.operating_profile.profile_id.startswith("sveby.residential")
assert archetype.hvac_template is None
assert archetype.envelope_performance.infiltration_reference_basis == "Atemp"
```

All canonical categories/configurations and explicit source variants compose
through the same authoring hierarchy. No successful calibration match is needed.
Physical recipes, material IDs, fractions, ordering and existing nominal U-values
are preserved. Effective ground properties and layered nominal U-values remain
distinct. Use the advanced `catalogue.detailed` view for structured source,
material, boundary, caveat and completeness inspection; `catalogue.parametric`
retains distinct effective-property inspection and editing.

`ids()` lists canonical archetypes; `ids(include_variants=True)` includes source
variants. Select a variant by its actual ID, never as a silent replacement for a
canonical entry. `renovation_states(id)` returns recorded choices. SE.07 starts
in 2022, accepts only `state=None` and does not inherit later edits from SE.06.

## Definitions that can be reused

| Public interface | Loaded information |
| --- | --- |
| `materials` | Read-only registry-ID to opaque `Material` objects, usable directly in `LayerMaterial` |
| `windows` | Read-only registry-ID to whole-window `WindowElement` definitions, separate from opening geometry |
| `operating_profiles` | Read-only Sveby definitions and the explicitly selected generic screening option |
| `hvac_templates` | Read-only explicit illustrative system choices, never automatically installed |
| `construction_sets()` | Explicitly construct a read-only `(archetype_id, state)` mapping; opt into source variants with `include_variants=True` |

Whole-window registry records do not contain full optical-layer `WindowMaterial`
properties; no layer material is fabricated from them. Detailed source/carbon
mapping remains available through `catalogue.detailed.resolve_material(id)`.
Index properties and representations use loaded state and perform no I/O.
`get()` and `for_year()` explicitly read the supported selected operating profile.
Custom archetypes may use the indexed definitions or independently authored ones.

SF/MF entries attach the supported residential profile; SF selection retains its
explicit permitted fallback note. Office and school attach their supported Sveby
profiles while requiring project calendars. Unsupported generic use remains
without an operating profile. Callers may explicitly select
`catalogue.operating_profiles["generic_other"]`; no fallback is automatic.

## Envelope rates preserve the recorded basis

MF definitions retain their native engineering rate in L/(s m² Atemp), including
0.20 for older Existing MF. The compatibility ACH representation is not treated
as model-volume ACH. SF, office, school and generic rates retain the recorded
TABULA source-volume basis; application requires the explicit corresponding
source reference area/volume. No conversion or geometric height is invented.
Stale or unsupported source-basis evidence leaves the rate unresolved with a
reason in its notes. Source evidence and pressure-coupling limitations remain
portable. No thermal-bridge uplift or installed HVAC is supplied without a
recorded definition.

## Inspect effective classifications

`dataset_id`, `dimensions`, `era_for_year(year)`, `get_slot(key)`, `search(**filters)`
and `summary()` preserve the existing effective-catalogue meaning. Slot keys can
be an `ArchetypeKey` or the existing five-part string. These slots describe
classification/effective scalar assumptions, rather than installed Building
systems. `summary()` explicitly calculates coverage from loaded data.

`effective_configuration()` returns a detached copy of the exact effective scalar
configuration, suitable for content identity or advanced inspection. It is not
complete physical archetype exchange; use `archetype_to_dict()` for that. No
ambiguous whole-Catalogue `to_dict()` format is introduced.

## Portable construction handover

The existing pure Data exporter accepts the same authored `Archetype` plus
explicit source/boundary context. Catalogue context comes from loaded registries:

```python
from epsm_data import export_nominal_constructions

archetype = catalogue.get("mf_se02", state="existing")
bundle = export_nominal_constructions(
    archetype,
    metadata=catalogue.nominal_metadata("mf_se02", state="existing"),
)
assert bundle["core"]["EXT_WALL"]
```

This preserves physical order, material identities, surface films, source records
and reciprocal construction relationships. Composition does not claim a target
match: context records `assessment_status="not_assessed"` and ground calibration
remains unresolved. Core owns physical conversion/engine compilation; EPSM owns
Building assembly. Independently authored constructions need explicit equivalent
source/boundary metadata for this advanced handover; format-4 archetype exchange
does not require that metadata. The calibrated-wrapper exporter remains a
compatibility adapter while consumers migrate.

Try [the catalogue authoring notebook](../examples/03_catalogue_authoring.ipynb).
