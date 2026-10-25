"""Deterministic reference-linked LoD2 catalogue, independent of curation history."""

import json
from copy import deepcopy
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from uuid import NAMESPACE_URL, uuid5

from ._logging import operation as logged_operation
from .carbon_scope import retained_stock_assessments
from .classification import (
    CATEGORIES,
    CATEGORY_LABELS,
    ERAS,
    GENERIC_ASSUMPTION_LABEL,
    GENERIC_DONOR_CATEGORY,
    SELECTION_CATEGORIES,
    STATES,
    ZONES,
    ArchetypeKey,
    ArchetypeSlot,
    content_hash,
    era_for_year,
    freeze,
    states_for_era,
)
from .domain import (
    Archetype,
    BuildingElement,
    CarbonReference,
    Component,
    ConstructionSet,
    Element,
    EnvelopePerformance,
    Layer,
    LayerMaterial,
    LayerSlot,
    Material,
    WindowElement,
)
from .sources import OPAQUE_FIELDS, WINDOW_FIELDS, boverket_carbon_modules, carbon_record

REQUIRED_ROLES = (
    "EXT_WALL",
    "GROUND_FLOOR",
    "BASEMENT_WALL",
    "INTERMEDIATE_FLOOR",
    "INT_WALL_NONLOADBEARING",
    "WINDOW",
)
SECTIONS = (
    "materials",
    "honeybee",
    "boverket",
    "carbon_references",
    "layers",
    "components",
    "elements",
    "construction_sets",
    "archetypes",
)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _state(record, state):
    if record["era"] == "SE.07":
        if state is not None:
            raise ValueError("SE.07 has no renovation states; use state=None")
        return "default"
    selected = "existing" if state is None else state
    if selected not in STATES:
        raise ValueError(f"Unknown state: {selected}")
    return selected


def _resolve_material_sources(definition, cache):
    """Resolve named references from one checked source cache into runtime values."""
    versions = definition.get("source_versions")
    if not isinstance(versions, dict) or not versions:
        raise ValueError("Reference catalogue requires source_versions")
    manifest = cache.manifest["sources"]
    records = {}
    for source, release in versions.items():
        if not isinstance(source, str) or not isinstance(release, str) or not release:
            raise ValueError("Source pins require string source IDs and releases")
        if source not in manifest or manifest[source]["release"] != release:
            raise ValueError(f"Source release mismatch for {source}: expected {release}")
        records[source] = cache.records(source)

    payload = deepcopy(definition)
    payload.pop("source_versions")
    payload["schema_version"] = 1
    for section in ("honeybee", "boverket", "carbon_references"):
        if section in definition:
            raise ValueError(f"Reference catalogue must not embed {section} records")
        payload[section] = {}
    def reference(value, kinds, path):
        if (not isinstance(value, dict) or set(value) != {"source", "identifier"}
                or not all(isinstance(item, str) and item for item in value.values())):
            raise ValueError(f"Invalid source reference at {path}")
        source, identifier = value["source"], value["identifier"]
        if source not in records or manifest[source]["kind"] not in kinds:
            raise ValueError(f"Unpinned or incompatible source at {path}: {source}")
        if identifier not in records[source]:
            raise ValueError(f"Unknown cached source identifier at {path}: {identifier}")
        record = records[source][identifier]
        kind = manifest[source]["kind"]
        section = ("boverket" if kind == "boverket" else "carbon_references"
                   if kind == "carbon_reference" else "honeybee")
        if identifier in payload[section] and payload[section][identifier] != record:
            raise ValueError(f"Conflicting cached source identifier: {identifier}")
        payload[section][identifier] = record
        return source, identifier, record

    materials = definition.get("materials")
    if not isinstance(materials, dict):
        raise ValueError("materials must be an ID-to-definition mapping")
    for mid, mapping in materials.items():
        if not isinstance(mapping, dict):
            raise ValueError(f"Invalid material mapping: {mid}")
        if any(field in mapping for field in (
            "properties", "name", "honeybee_id", "boverket_id", "carbon_reference_id"
        )):
            raise ValueError(f"Material mapping must use source references without copied properties: {mid}")
        name = mapping.get("epsm_material_name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"epsm_material_name is required for {mid}")
        _, hid, thermal = reference(mapping.get("thermal_ref"), {"honeybee", "epsm_authored"},
                                    f"materials.{mid}.thermal_ref")
        kind = mapping.get("kind")
        if kind not in {"opaque", "window"}:
            raise ValueError(f"Unknown material kind: {mid}")
        fields = ({field: field for field in OPAQUE_FIELDS} if kind == "opaque" else
                  dict(zip(WINDOW_FIELDS, ("u_factor", "shgc", "vt"), strict=True)))
        resolved = {key: deepcopy(value) for key, value in mapping.items()
                    if key not in {"epsm_material_name", "thermal_ref", "carbon_ref"}}
        resolved.update(name=name, honeybee_id=hid, boverket_id=None,
                        properties={field: thermal[source_field] for field, source_field in fields.items()
                                    if source_field in thermal})
        if mapping.get("carbon_ref") is not None:
            source, identifier, _ = reference(mapping["carbon_ref"], {"boverket", "carbon_reference"},
                                               f"materials.{mid}.carbon_ref")
            field = "boverket_id" if manifest[source]["kind"] == "boverket" else "carbon_reference_id"
            resolved[field] = identifier
        payload["materials"][mid] = resolved
    return payload


class Catalogue:
    """Loaded physical definitions and their 228 climate-zone assignments.

    Loading performs explicit local file I/O. Inspection and selection use only
    captured data. Missing values remain inspectable through completeness();
    invalid supplied physics and dangling references are rejected. Incomplete
    leaves are not replaced with invented material properties.
    """

    def __init__(self, data, *, renovations=None, profiles=None, hvac_templates=None, source_cache=None):
        self._definition = deepcopy(data)
        self._source_cache = None
        if data.get("schema_version") == 2:
            from .source_cache import SourceCache

            self._source_cache = (source_cache if isinstance(source_cache, SourceCache)
                                  else SourceCache.load(source_cache))
            payload = _resolve_material_sources(data, self._source_cache)
        else:
            payload = deepcopy(data)
        json.dumps(payload, allow_nan=False)
        if payload.get("schema_version") != 1:
            raise ValueError("Unsupported LoD2 catalogue schema_version")
        if not isinstance(payload.get("dataset_id"), str) or not payload["dataset_id"].strip():
            raise ValueError("dataset_id is required")
        payload.setdefault("carbon_references", {})
        for section in SECTIONS:
            if not isinstance(payload.get(section), dict):
                raise ValueError(f"{section} must be an ID-to-definition mapping")
            if any(not isinstance(key, str) or not key for key in payload[section]):
                raise ValueError(f"{section} requires nonempty stable IDs")
        self._data = payload
        self._missing = {section: {} for section in SECTIONS}
        self._material_records = freeze(payload["materials"])
        self._boverket = freeze(payload["boverket"])
        self._honeybee = freeze(payload["honeybee"])
        self._carbon_references = {}
        from .catalogue import RenovationCatalogue
        from .profiles import available_operating_profiles
        from .reference import reference_hvac_template

        self.renovations = renovations if renovations is not None else RenovationCatalogue()
        self._profiles = MappingProxyType(
            dict(available_operating_profiles() if profiles is None else profiles)
        )
        self._hvac = MappingProxyType(
            dict(
                {"illustrative_reference_ftx": reference_hvac_template()}
                if hvac_templates is None
                else hvac_templates
            )
        )
        self._validate_sources()
        self._retained_stock = retained_stock_assessments(payload)
        self._hydrate()
        self._validate_classification()

    @classmethod
    @logged_operation("catalogue.load")
    def load(cls, path=None, *, renovations=None, source_cache=None):
        """Read the packaged catalogue or an explicit JSON file/directory."""
        target = (
            files("epsm_data.datasets.lod2").joinpath("catalogue.json")
            if path is None
            else Path(path)
        )
        if path is not None and target.is_dir():
            target = target / "catalogue.json"
        payload = json.loads(
            target.read_text(encoding="utf-8"),
            object_pairs_hook=_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"Nonfinite value: {value}")
            ),
        )
        return cls(payload, renovations=renovations, source_cache=source_cache)

    def _need(self, record, fields, path, missing):
        for field in fields:
            if record.get(field) is None or record.get(field) == "":
                missing.append(f"{path}.{field}")

    def _reference(self, section, identifier, path, missing):
        if identifier is None or identifier == "":
            missing.append(path)
            return None
        if identifier not in self._data[section]:
            raise ValueError(f"Dangling reference at {path}: {identifier}")
        missing.extend(self._missing[section].get(identifier, ()))
        return identifier

    @staticmethod
    def _unique(records, signature, section):
        seen = {}
        for identifier, record in records.items():
            physical = signature(record)
            if physical is None:
                continue
            key = content_hash(physical)
            if key in seen:
                raise ValueError(
                    f"Duplicate {section} definitions: {seen[key]} and {identifier}; reuse one ID"
                )
            seen[key] = identifier

    def _validate_sources(self):
        for identifier, record in self._data["honeybee"].items():
            if record.get("identifier") != identifier:
                raise ValueError(f"Honeybee identifier disagrees with source key: {identifier}")
        for identifier, record in self._data["boverket"].items():
            if str(record.get("ResourceId")) != identifier:
                raise ValueError(f"Boverket ResourceId disagrees with source key: {identifier}")

        for identifier, record in self._data["carbon_references"].items():
            if record.get("identifier") != identifier:
                raise ValueError(f"Carbon reference identifier disagrees with source key: {identifier}")
            try:
                reference = CarbonReference.from_dict(record)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"carbon_references.{identifier}: {exc}") from exc
            self._carbon_references[identifier] = reference
            self._missing["carbon_references"][identifier] = tuple(
                f"carbon_references.{identifier}.modules.{module}"
                for module in ("A1A3",)
                if reference.modules.get(module) is None
            )
        self._carbon_references = MappingProxyType(self._carbon_references)

    def _hydrate(self):
        data = self._data
        self._unique(
            data["materials"],
            lambda r: {
                "kind": r.get("kind"),
                "properties": r.get("properties"),
                "boverket_id": r.get("boverket_id"),
                "carbon_reference_id": r.get("carbon_reference_id"),
            },
            "material",
        )
        materials, windows = {}, {}
        for mid, record in data["materials"].items():
            path, missing = f"materials.{mid}", []
            kind, props = record.get("kind"), record.get("properties") or {}
            fields = OPAQUE_FIELDS if kind == "opaque" else WINDOW_FIELDS
            if kind not in ("opaque", "window"):
                raise ValueError(f"{path}: unknown material kind")
            physical_missing = []
            self._need(props, fields, path + ".properties", physical_missing)
            missing.extend(physical_missing)
            hid = self._reference(
                "honeybee", record.get("honeybee_id"), path + ".honeybee_id", missing
            )
            bov = record.get("boverket_id")
            external_id = record.get("carbon_reference_id")
            if bov is not None and external_id is not None:
                raise ValueError(f"{path}: choose Boverket or an external carbon reference")
            external_id = (
                self._reference(
                    "carbon_references", external_id, path + ".carbon_reference_id", missing
                )
                if external_id is not None
                else None
            )
            if (bov is None and record.get("carbon_reference_id") is None
                    and not (record.get("non_product", False) and mid not in self._retained_stock)
                    and not self._retained_stock.get(mid, {}).get("eligible", False)):
                missing.append(path + ".boverket_id")
            elif bov is not None:
                self._reference("boverket", str(bov), path + ".boverket_id", missing)
            external = self._carbon_references.get(external_id)
            if hid is not None:
                hb = data["honeybee"][hid]
                expected_type = (
                    "EnergyMaterial" if kind == "opaque" else "EnergyWindowMaterialSimpleGlazSys"
                )
                if hb.get("type") != expected_type:
                    raise ValueError(f"{path}: linked Honeybee material has wrong type")
                source_fields = (
                    dict(zip(WINDOW_FIELDS, ("u_factor", "shgc", "vt"), strict=True))
                    if kind == "window"
                    else {f: f for f in fields}
                )
                for field, source_field in source_fields.items():
                    if hb.get(source_field) is None:
                        missing.append(f"honeybee.{hid}.{source_field}")
                    elif props.get(field) is not None and props[field] != hb[source_field]:
                        raise ValueError(f"{path}: {field} disagrees with linked Honeybee record")
            carbon_values = boverket_carbon_modules(data["boverket"][str(bov)]) if bov is not None else {}
            carbon = (
                carbon_record(data["boverket"][str(bov)], record["name"])
                if bov is not None
                else None
            )
            if bov is not None and not any(
                carbon_values.get(module) is not None
                for module in ("A1-A3 Conservative", "A1-A3 Typical")
            ):
                missing.append(path + ".carbon_factors.A1A3")
            if not physical_missing:
                if kind == "opaque":
                    materials[mid] = Material(
                        name=record["name"],
                        json_id=mid,
                        boverket_id=str(bov) if bov is not None else None,
                        material_type=record.get("material_type", "catalogue"),
                        embodied_carbon=carbon,
                        carbon_reference=external,
                        uuid=uuid5(NAMESPACE_URL, f"epsm:material:{mid}"),
                        **{field: props[field] for field in fields},
                    )
                else:
                    windows[mid] = WindowElement(
                        record["name"],
                        "catalogue",
                        boverket_id=str(bov) if bov is not None else None,
                        carbon_reference=external,
                        **props,
                    )
            self._missing["materials"][mid] = tuple(missing)
        self._materials, self._windows = MappingProxyType(materials), MappingProxyType(windows)

        layers = {}
        self._unique(
            data["layers"],
            lambda r: (
                None
                if r.get("thickness") is None or not r.get("materials")
                else {
                    "thickness": r["thickness"],
                    "materials": r["materials"],
                    "is_composite": r.get("is_composite", False),
                }
            ),
            "layer",
        )
        for lid, record in data["layers"].items():
            path, missing, shares = f"layers.{lid}", [], []
            self._need(record, ("thickness",), path, missing)
            if not record.get("materials"):
                missing.append(path + ".materials")
            buildable = record.get("thickness") is not None
            for index, share in enumerate(record.get("materials", ())):
                base = f"{path}.materials.{index}"
                self._reference(
                    "materials", share.get("material_id"), base + ".material_id", missing
                )
                self._need(share, ("area_fraction", "thickness"), base, missing)
                ref = share.get("material_id")
                if ref in data["materials"] and data["materials"][ref]["kind"] != "opaque":
                    raise ValueError(f"{base}: layers require opaque materials")
                material = materials.get(ref)
                if (
                    material is None
                    or share.get("area_fraction") is None
                    or share.get("thickness") is None
                ):
                    buildable = False
                else:
                    shares.append(
                        LayerMaterial(material, share["area_fraction"], share["thickness"])
                    )
            if any(share.thickness != record.get("thickness") for share in shares):
                missing.append(path + ".thermal_equivalence")
                buildable = False
            if buildable and shares:
                layers[lid] = Layer(
                    record["name"],
                    lid,
                    record["thickness"],
                    tuple(shares),
                    record.get("is_composite", False),
                )
            self._missing["layers"][lid] = tuple(missing)
        self._layers = MappingProxyType(layers)

        components = {}
        self._unique(
            data["components"],
            lambda r: (
                None
                if any(r.get(k) is None for k in ("application", "shearing_layer", "layers"))
                else {
                    "application": r["application"],
                    "shearing_layer": r["shearing_layer"],
                    "layers": sorted(
                        ({key: value for key, value in slot.items() if key != "layer_function"}
                         for slot in r["layers"]),
                        key=lambda slot: (slot.get("position") is None, slot.get("position") or 0),
                    ),
                }
            ),
            "component",
        )
        for cid, record in data["components"].items():
            path, missing, slots = f"components.{cid}", [], []
            self._need(record, ("application", "shearing_layer"), path, missing)
            if not record.get("layers"):
                missing.append(path + ".layers")
            for index, slot in enumerate(record.get("layers", ())):
                self._reference(
                    "layers", slot.get("layer_id"), f"{path}.layers.{index}.layer_id", missing
                )
                self._need(slot, ("position",), f"{path}.layers.{index}", missing)
                if slot.get("layer_id") in layers and slot.get("position") is not None:
                    slots.append(LayerSlot(layers[slot["layer_id"]], slot["position"]))
            if (
                len(slots) == len(record.get("layers", ()))
                and slots
                and record.get("application")
                and record.get("shearing_layer")
            ):
                components[cid] = Component(
                    record["name"],
                    "catalogue",
                    record["application"],
                    tuple(slots),
                    record["shearing_layer"],
                )
            self._missing["components"][cid] = tuple(missing)
        self._components = MappingProxyType(components)

        elements = {}
        self._unique(
            data["elements"],
            lambda r: (
                None
                if not r.get("role")
                else {
                    "role": r["role"],
                    "components": r.get("components"),
                    "window_material_id": r.get("window_material_id"),
                }
            ),
            "element",
        )
        for eid, record in data["elements"].items():
            path, missing = f"elements.{eid}", []
            self._need(record, ("role",), path, missing)
            if record.get("role") == "WINDOW":
                mid = self._reference(
                    "materials",
                    record.get("window_material_id"),
                    path + ".window_material_id",
                    missing,
                )
                if mid in data["materials"] and data["materials"][mid]["kind"] != "window":
                    raise ValueError(f"{path}: window requires a window material")
                if mid in windows:
                    elements[eid] = replace(windows[mid], name=f"{windows[mid].name} [{mid}]")
            else:
                children = []
                if not record.get("components"):
                    missing.append(path + ".components")
                for index, cid in enumerate(record.get("components", ())):
                    self._reference("components", cid, f"{path}.components.{index}", missing)
                    if cid in components:
                        children.append(components[cid])
                if (
                    children
                    and len(children) == len(record.get("components", ()))
                    and record.get("role")
                ):
                    elements[eid] = Element(
                        record["name"], "catalogue", None, tuple(children), record["role"]
                    )
            self._missing["elements"][eid] = tuple(missing)
        self._elements = MappingProxyType(elements)

        constructions = {}
        self._unique(
            data["construction_sets"], lambda r: r.get("elements") or None, "construction set"
        )
        for sid, record in data["construction_sets"].items():
            path, missing, assignments = f"construction_sets.{sid}", [], {}
            roles = record.get("elements", {})
            for role in REQUIRED_ROLES:
                self._need(roles, (role,), path + ".elements", missing)
            if not (roles.get("TOP_FLOOR") or roles.get("ROOF")):
                missing.append(path + ".elements.TOP_FLOOR_or_ROOF")
            for role, eid in roles.items():
                self._reference("elements", eid, f"{path}.elements.{role}", missing)
                if eid in elements:
                    assignments[BuildingElement(role)] = elements[eid]
            constructions[sid] = ConstructionSet(
                uuid5(NAMESPACE_URL, f"epsm:construction:{sid}"), elements=assignments
            )
            self._missing["construction_sets"][sid] = tuple(dict.fromkeys(missing))
        self._construction_sets = MappingProxyType(constructions)

    def _validate_classification(self):
        classified = {}
        for aid, record in self._data["archetypes"].items():
            category, era = record.get("category"), record.get("era")
            if category not in CATEGORIES or era not in ERAS:
                raise ValueError(f"{aid}: unknown category or era")
            pair = category, era
            if pair in classified:
                raise ValueError(f"Duplicate archetype classification: {pair}")
            classified[pair] = aid
            expected = {state or "default" for state in states_for_era(era)}
            if set(record.get("states", {})) - expected:
                raise ValueError(f"{aid}: invalid states for {era}")
            for state, config in record.get("states", {}).items():
                missing = []
                self._reference(
                    "construction_sets",
                    config.get("construction_set_id"),
                    f"archetypes.{aid}.states.{state}.construction_set_id",
                    missing,
                )
                envelope = config.get("envelope_performance")
                if envelope:
                    EnvelopePerformance(**envelope)
                if config.get("weather_shell_element_id") is not None:
                    self._reference(
                        "elements",
                        config["weather_shell_element_id"],
                        f"archetypes.{aid}.states.{state}.weather_shell_element_id",
                        missing,
                    )
                    shell = self._elements.get(config["weather_shell_element_id"])
                    if shell is not None and shell.application != BuildingElement.ROOF:
                        raise ValueError(f"{aid}: weather shell must be a ROOF element")
                height = config.get("reference_height_m")
                if height is not None:
                    import math

                    if (
                        isinstance(height, bool)
                        or not isinstance(height, (int, float))
                        or not math.isfinite(height)
                        or height <= 0
                    ):
                        raise ValueError(f"{aid}: reference_height_m must be finite and positive")
        self._classified = classified

    @property
    def dataset_id(self):
        return self._data["dataset_id"]

    @property
    def dimensions(self):
        return freeze(
            {"categories": CATEGORY_LABELS, "eras": ERAS, "zones": ZONES, "states": STATES}
        )

    materials = property(lambda self: self._materials)
    windows = property(lambda self: self._windows)
    material_records = property(lambda self: self._material_records)
    material_mappings = property(lambda self: freeze(self._definition["materials"]))
    source_versions = property(lambda self: freeze(self._definition.get("source_versions", {})))
    layers = property(lambda self: self._layers)
    components = property(lambda self: self._components)
    elements = property(lambda self: self._elements)
    construction_sets = property(lambda self: self._construction_sets)
    honeybee_materials = property(lambda self: self._honeybee)
    boverket_resources = property(lambda self: self._boverket)
    carbon_references = property(lambda self: self._carbon_references)
    archetype_records = property(lambda self: freeze(self._data["archetypes"]))
    operating_profiles = property(lambda self: self._profiles)
    hvac_templates = property(lambda self: self._hvac)
    era_for_year = staticmethod(era_for_year)

    def __repr__(self):
        return f"Catalogue(id={self.dataset_id!r}, families={len(self.ids())}, configurations={len(self.search()) // 3})"

    __str__ = __repr__

    def to_dict(self):
        """Return the stored catalogue, retaining material names and source references."""
        return deepcopy(self._definition)

    def resolved_dict(self):
        """Return a detached snapshot with the captured source properties resolved."""
        return deepcopy(self._data)

    def check_sources(self, *, online=False, timeout=3):
        """Check captured source integrity and, explicitly, upstream release versions."""
        if self._source_cache is None:
            raise ValueError("This self-contained catalogue has no source cache")
        return self._source_cache.check_versions(online=online, timeout=timeout)

    def _resolve_selection(self, archetype_id):
        """Resolve only explicit aliases; generic selections reuse an MF donor."""
        aid = self._data.get("aliases", {}).get("archetypes", {}).get(archetype_id, archetype_id)
        if isinstance(aid, str) and aid.startswith("generic_se"):
            era = "SE." + aid.removeprefix("generic_se")
            if era not in ERAS:
                raise KeyError(archetype_id)
            return self._classified[(GENERIC_DONOR_CATEGORY, era)], True
        return aid, False

    def sanity_report(self, *, fixture=None):
        """Check stored definitions forward, without changing the catalogue."""
        from .sanity import check_catalogue

        return check_catalogue(self, fixture=fixture)

    def ids(self, *, category=None):
        """List authored IDs; generic explicitly returns its MF donor IDs."""
        if category is not None and category not in SELECTION_CATEGORIES:
            raise ValueError(f"Unknown category: {category}")
        if category == "generic":
            category = GENERIC_DONOR_CATEGORY
        return tuple(
            aid
            for aid, record in self._data["archetypes"].items()
            if category is None or record["category"] == category
        )

    def renovation_states(self, archetype_id):
        aid, _ = self._resolve_selection(archetype_id)
        record = self._data["archetypes"][aid]
        return () if record["era"] == "SE.07" else STATES

    def completeness(self, archetype_id, *, state=None):
        """Report missing LoD2 fabric values/links, independently of model readiness."""
        aid, _ = self._resolve_selection(archetype_id)
        record = self._data["archetypes"][aid]
        selected = _state(record, state)
        path = f"archetypes.{aid}.states.{selected}"
        config = record.get("states", {}).get(selected)
        missing = []
        if config is None:
            missing.append(path)
        else:
            self._reference(
                "construction_sets",
                config.get("construction_set_id"),
                path + ".construction_set_id",
                missing,
            )
            if config.get("roof_topology") not in ("cold_attic", "compact"):
                missing.append(path + ".roof_topology")
            self._reference(
                "elements",
                config.get("weather_shell_element_id"),
                path + ".weather_shell_element_id",
                missing,
            )
            envelope = config.get("envelope_performance") or {}
            if (
                envelope.get("infiltration_ach") is None
                and envelope.get("infiltration_l_s_m2") is None
            ):
                missing.append(path + ".envelope_performance.infiltration")
            if (
                envelope.get("infiltration_reference_basis") == "tabula_reference_volume"
                and config.get("reference_height_m") is None
            ):
                missing.append(path + ".reference_height_m")
        missing = tuple(dict.fromkeys(missing))
        return {"complete": not missing, "missing_values": missing}

    @logged_operation("catalogue.select", level=10)
    def get(self, archetype_id, *, state=None):
        """Return shared physical definitions; incomplete configurations stay inspectable."""
        aid, generic = self._resolve_selection(archetype_id)
        record = self._data["archetypes"][aid]
        selected = _state(record, state)
        config = record.get("states", {}).get(selected, {})
        profile_name = {
            "single_family": "sveby_residential_v2",
            "multi_family": "sveby_residential_v2",
            "office": "sveby_office_v1",
            "school": "sveby_school_v1",
        }[record["category"]]
        profile = self._profiles.get(profile_name)
        if profile is not None and record["category"] == "single_family":
            profile = profile.with_changes(
                notes=profile.notes
                + (
                    "Explicit single-family fallback permitted by Sveby residential 2.0; primary scope is multi-family.",
                )
            )
        missing = self.completeness(aid, state=state)["missing_values"]
        return Archetype(
            archetype_id="generic_se" + record["era"].removeprefix("SE.") if generic else aid,
            display_name=GENERIC_ASSUMPTION_LABEL if generic else record["name"]
            + (" · " + selected if selected != "default" else ""),
            construction_year=config.get("construction_year"),
            building_typology="generic" if generic else record["category"],
            construction_set=self._construction_sets.get(config.get("construction_set_id")),
            operating_profile=profile,
            envelope_performance=EnvelopePerformance(**config["envelope_performance"])
            if config.get("envelope_performance")
            else None,
            source_references=(f"LoD2 donor archetype: {aid}",) if generic else (),
            notes=tuple("Missing LoD2 value: " + field for field in missing)
            + tuple(
                f"Retained existing stock without quantified carbon: {mid}. {assessment['reason']} "
                "Original production is outside this retained-stock assessment; installing, "
                "replacing, removing or including this stock in LCA still requires factors."
                for mid, assessment in self._retained_stock.items()
                if assessment["eligible"] and aid in assessment["archetypes"]
            )
            + (
                (
                    GENERIC_ASSUMPTION_LABEL,
                    f"Requested category: generic; donor category: multi_family; donor archetype: {aid}; "
                    f"era: {record['era']}; state: {selected}.",
                    "Representative modelling assumption; verify suitability for the building's actual use.",
                )
                if generic else ()
            ),
        )

    def for_year(self, category, construction_year, *, state=None):
        """Select an era; generic explicitly borrows MF fabric and residential operation."""
        if category not in SELECTION_CATEGORIES:
            raise ValueError(f"Unknown category: {category}")
        era = era_for_year(construction_year)
        if category == "generic":
            return self.get("generic_se" + era.removeprefix("SE."), state=state)
        return self.get(self._classified[(category, era)], state=state)

    def search(self, *, category=None, era=None, climate_zone=None, state=None):
        """List authored zone assignments, or explicit virtual generic/MF assignments.

        The unfiltered matrix excludes generic; requesting it returns generic keys
        linked to the unchanged MF donor IDs and physical definitions.
        """
        for field, value, choices in (
            ("category", category, SELECTION_CATEGORIES),
            ("era", era, ERAS),
            ("climate_zone", climate_zone, ZONES),
            ("state", state, STATES),
        ):
            if value is not None and value not in choices:
                raise ValueError(f"Unknown {field}: {value}")
        result = []
        for aid in self.ids(category=category):
            record = self._data["archetypes"][aid]
            if era is not None and record["era"] != era:
                continue
            for variant in states_for_era(record["era"]):
                if state is not None and variant != state:
                    continue
                selected = variant or "default"
                config = record.get("states", {}).get(selected, {})
                missing = self.completeness(aid, state=variant)["missing_values"]
                for zone in ZONES:
                    if climate_zone is None or zone == climate_zone:
                        result.append(
                            ArchetypeSlot(
                                ArchetypeKey(category or record["category"], record["era"], zone, variant),
                                aid,
                                config.get("construction_set_id"),
                                missing,
                            )
                        )
        return tuple(result)

    def get_slot(self, key):
        if isinstance(key, str):
            parts = key.split(":")
            if len(parts) != 4:
                raise ValueError("LoD2 slot IDs contain category:era:zone:state")
            key = ArchetypeKey(*parts[:3], None if parts[3] == "default" else parts[3])
        if not isinstance(key, ArchetypeKey):
            raise TypeError("key must be an ArchetypeKey or slot ID")
        return next(
            slot
            for slot in self.search(
                category=key.category, era=key.era, climate_zone=key.climate_zone
            )
            if slot.key == key
        )

    def summary(self):
        slots = self.search()
        return {
            "dataset_id": self.dataset_id,
            "archetype_count": len(self.ids()),
            "configuration_count": len(slots) // len(ZONES),
            "slot_count": len(slots),
            "complete_slots": sum(slot.complete for slot in slots),
            "incomplete_slots": sum(not slot.complete for slot in slots),
            "expected_slot_count": 228,
            "missing_families": tuple(
                f"{category}:{era}"
                for category in CATEGORIES
                for era in ERAS
                if (category, era) not in self._classified
            ),
            "incomplete_archetypes": tuple(
                {
                    "archetype_id": slot.archetype_id,
                    "state": slot.state,
                    "missing_values": slot.missing_values,
                }
                for slot in slots
                if not slot.complete and slot.key.climate_zone == ZONES[0]
            ),
        }

    def nominal_metadata(self, archetype_id, *, state=None):
        """Return direct physical/export context; no calibration or evidence workflow."""
        aid, generic = self._resolve_selection(archetype_id)
        record = self._data["archetypes"][aid]
        config = record["states"][_state(record, state)]
        active = set()
        sid = config.get("construction_set_id")
        element_ids = list(
            self._data["construction_sets"].get(sid, {}).get("elements", {}).values()
        )
        if config.get("weather_shell_element_id"):
            element_ids.append(config["weather_shell_element_id"])
        for eid in element_ids:
            element = self._data["elements"][eid]
            if element.get("role") == "WINDOW":
                active.add(element.get("window_material_id"))
            for cid in element.get("components", ()):
                for slot in self._data["components"][cid]["layers"]:
                    active.update(
                        share["material_id"]
                        for share in self._data["layers"][slot["layer_id"]]["materials"]
                    )
        refs = {
            mid: {
                "registry_id": mid,
                "json_id": mid,
                "kind": "simple_window"
                if self._data["materials"][mid]["kind"] == "window"
                else "opaque",
                "honeybee_id": self._data["materials"][mid].get("honeybee_id"),
                "boverket_id": self._data["materials"][mid].get("boverket_id"),
                **(
                    {
                        "carbon_reference_id": self._data["materials"][mid]["carbon_reference_id"],
                        "carbon_reference": self._carbon_references[
                            self._data["materials"][mid]["carbon_reference_id"]
                        ].to_dict(),
                    }
                    if self._data["materials"][mid].get("carbon_reference_id")
                    else {}
                ),
                "properties": deepcopy(self._data["materials"][mid]["properties"]),
            }
            for mid in sorted(active)
            if mid is not None
        }
        shell = self._elements.get(config.get("weather_shell_element_id"))
        weather_shell = None
        if shell is not None:
            from .nominal import export_nominal_constructions

            shell_archetype = Archetype(
                "weather_shell",
                "Representative weather shell",
                construction_set=ConstructionSet(
                    uuid5(NAMESPACE_URL, "epsm:weather-shell"),
                    elements={BuildingElement.ROOF: shell},
                ),
            )
            weather_shell = export_nominal_constructions(shell_archetype)["core"]["ROOF"]
        return {
            "weather_shell": weather_shell,
            "reference_height_m": config.get("reference_height_m"),
            "dataset_id": self.dataset_id,
            "category": "generic" if generic else record["category"],
            **(
                {"selection": {
                    "requested_category": "generic",
                    "donor_category": GENERIC_DONOR_CATEGORY,
                    "donor_archetype_id": aid,
                    "assumption_label": GENERIC_ASSUMPTION_LABEL,
                }} if generic else {}
            ),
            "era": record["era"],
            "state": None if record["era"] == "SE.07" else _state(record, state),
            "roof_topology": config.get("roof_topology"),
            "boundary_details": deepcopy(config.get("boundary_details", {})),
            "material_references": refs,
        }
