"""Deterministic reference-linked LoD2 catalogue, independent of curation history."""

import json
from copy import deepcopy
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from uuid import NAMESPACE_URL, uuid5

from ._logging import operation as logged_operation
from .classification import (
    CATEGORIES,
    CATEGORY_LABELS,
    ERAS,
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
from .sources import OPAQUE_FIELDS, WINDOW_FIELDS, carbon_record

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


class Catalogue:
    """Loaded physical definitions and their 228 climate-zone assignments.

    Loading performs explicit local file I/O. Inspection and selection use only
    captured data. Missing values remain inspectable through completeness();
    invalid supplied physics and dangling references are rejected. Incomplete
    leaves are not replaced with invented material properties.
    """

    def __init__(self, data, *, renovations=None, profiles=None, hvac_templates=None):
        payload = deepcopy(data)
        json.dumps(payload, allow_nan=False)
        if payload.get("schema_version") != 1:
            raise ValueError("Unsupported LoD2 catalogue schema_version")
        if not isinstance(payload.get("dataset_id"), str) or not payload["dataset_id"].strip():
            raise ValueError("dataset_id is required")
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
        self._hydrate()
        self._validate_classification()

    @classmethod
    @logged_operation("catalogue.load")
    def load(cls, path=None, *, renovations=None):
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
        return cls(payload, renovations=renovations)

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

    def _hydrate(self):
        data = self._data
        self._unique(
            data["materials"],
            lambda r: {
                "kind": r.get("kind"),
                "properties": r.get("properties"),
                "boverket_id": r.get("boverket_id"),
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
            if bov is None and not record.get("non_product", False):
                missing.append(path + ".boverket_id")
            elif bov is not None:
                self._reference("boverket", str(bov), path + ".boverket_id", missing)
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
            carbon = (
                carbon_record(data["boverket"][str(bov)], record["name"])
                if bov is not None
                else None
            )
            if bov is not None and carbon is None:
                missing.append(path + ".carbon_factors")
            if not physical_missing:
                if kind == "opaque":
                    materials[mid] = Material(
                        name=record["name"],
                        json_id=mid,
                        boverket_id=str(bov) if bov is not None else None,
                        material_type=record.get("material_type", "catalogue"),
                        embodied_carbon=carbon,
                        uuid=uuid5(NAMESPACE_URL, f"epsm:material:{mid}"),
                        **{field: props[field] for field in fields},
                    )
                else:
                    windows[mid] = WindowElement(
                        record["name"],
                        "catalogue",
                        boverket_id=str(bov) if bov is not None else None,
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
                        r["layers"],
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
    layers = property(lambda self: self._layers)
    components = property(lambda self: self._components)
    elements = property(lambda self: self._elements)
    construction_sets = property(lambda self: self._construction_sets)
    honeybee_materials = property(lambda self: self._honeybee)
    boverket_resources = property(lambda self: self._boverket)
    archetype_records = property(lambda self: freeze(self._data["archetypes"]))
    operating_profiles = property(lambda self: self._profiles)
    hvac_templates = property(lambda self: self._hvac)
    era_for_year = staticmethod(era_for_year)

    def __repr__(self):
        return f"Catalogue(id={self.dataset_id!r}, families={len(self.ids())}, configurations={len(self.search()) // 3})"

    __str__ = __repr__

    def to_dict(self):
        """Return detached normalized definitions for explicit authoring/saving."""
        return deepcopy(self._data)

    def ids(self, *, category=None):
        if category is not None and category not in CATEGORIES:
            raise ValueError(f"Unknown category: {category}")
        return tuple(
            aid
            for aid, record in self._data["archetypes"].items()
            if category is None or record["category"] == category
        )

    def renovation_states(self, archetype_id):
        record = self._data["archetypes"][archetype_id]
        return () if record["era"] == "SE.07" else STATES

    def completeness(self, archetype_id, *, state=None):
        """Report missing LoD2 fabric values/links, independently of model readiness."""
        record = self._data["archetypes"][archetype_id]
        selected = _state(record, state)
        path = f"archetypes.{archetype_id}.states.{selected}"
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
        aid = self._data.get("aliases", {}).get("archetypes", {}).get(archetype_id, archetype_id)
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
            archetype_id=aid,
            display_name=record["name"] + (" · " + selected if selected != "default" else ""),
            construction_year=config.get("construction_year"),
            building_typology=record["category"],
            construction_set=self._construction_sets.get(config.get("construction_set_id")),
            operating_profile=profile,
            envelope_performance=EnvelopePerformance(**config["envelope_performance"])
            if config.get("envelope_performance")
            else None,
            notes=tuple("Missing LoD2 value: " + field for field in missing),
        )

    def for_year(self, category, construction_year, *, state=None):
        return self.get(self._classified[(category, era_for_year(construction_year))], state=state)

    def search(self, *, category=None, era=None, climate_zone=None, state=None):
        """List zone assignments; physical definitions are shared across zones."""
        for field, value, choices in (
            ("category", category, CATEGORIES),
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
                                ArchetypeKey(record["category"], record["era"], zone, variant),
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
        record = self._data["archetypes"][archetype_id]
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
            "category": record["category"],
            "era": record["era"],
            "state": None if record["era"] == "SE.07" else _state(record, state),
            "roof_topology": config.get("roof_topology"),
            "boundary_details": deepcopy(config.get("boundary_details", {})),
            "material_references": refs,
        }
