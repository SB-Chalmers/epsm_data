"""Lossless portable archetype records, independent of source ingestion.

The versioned nested format includes material properties and UUIDs. The older
to_dict/consumption views remain useful summaries but are not round-trip formats.
"""

from dataclasses import fields, is_dataclass
from enum import Enum
from uuid import UUID

from .domain import (
    BuildingArchetype,
    BuildingElement,
    Component,
    ConstructionSet,
    Element,
    EmbodiedCarbon,
    Layer,
    LayerMaterial,
    LayerSlot,
    OpaqueMaterial,
    RenovationEvent,
    Roughness,
    ShearingLayer,
    WindowElement,
)


def _encode(value):
    if isinstance(value, (UUID, Enum)):
        return str(value) if isinstance(value, UUID) else value.value
    if is_dataclass(value):
        return {f.name: _encode(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {_encode(k): _encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    return value


def archetype_to_dict(archetype: BuildingArchetype) -> dict:
    """Serialize an archetype, including resolved materials and revision IDs.

    Parameters
    ----------
    archetype : BuildingArchetype
        Record to encode.

    Returns
    -------
    dict
        JSON-compatible record; version 2 is used for unknown carbon volume conversion,
        version 3 for explicitly pending material carbon mappings. Older records remain readable.

    Examples
    --------
    >>> from epsm_data import build_archetype
    >>> arch = build_archetype({
    ...     "archetype_id": "demo", "display_name": "Demo", "construction_year": 1960,
    ...     "building_typology": "multi_family",
    ...     "elements": {"WINDOW": {"u_value": 2.5, "shgc": 0.7}},
    ... }, materials={})
    >>> archetype_from_dict(archetype_to_dict(arch)) == arch
    True
    """
    encoded = _encode(archetype)
    version = 3 if _has_pending_carbon(encoded) else (2 if _has_unknown_conversion(encoded) else 1)
    return {"format_version": version, "archetype": encoded}


def _has_pending_carbon(value):
    if isinstance(value, dict):
        return ("embodied_carbon" in value and value["embodied_carbon"] is None) or any(
            _has_pending_carbon(child) for child in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(_has_pending_carbon(child) for child in value)
    return False


def _has_unknown_conversion(value):
    if isinstance(value, dict):
        return ("conversion_factor" in value and value["conversion_factor"] is None) or any(
            _has_unknown_conversion(child) for child in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(_has_unknown_conversion(child) for child in value)
    return False


def _material(data):
    values = dict(data)
    values["uuid"] = UUID(values["uuid"])
    values["roughness"] = Roughness(values["roughness"])
    carbon = values["embodied_carbon"]
    values["embodied_carbon"] = EmbodiedCarbon(**carbon) if carbon is not None else None
    return OpaqueMaterial(**values)


def _component(data):
    values = dict(data)
    slots = []
    for slot in values["layers"]:
        layer = dict(slot["layer"])
        layer["materials"] = tuple(
            LayerMaterial(
                material=_material(m["material"]),
                area_fraction=m["area_fraction"],
                thickness=m["thickness"],
            )
            for m in layer["materials"]
        )
        slots.append(LayerSlot(layer=Layer(**layer), position=slot["position"]))
    values["layers"] = tuple(slots)
    values["application"] = BuildingElement(values["application"])
    values["shearing_layer"] = ShearingLayer(values["shearing_layer"])
    return Component(**values)


def archetype_from_dict(data: dict) -> BuildingArchetype:
    """Restore a versioned archetype record without source or registry lookups.

    Parameters
    ----------
    data : dict
        Record produced by :func:`archetype_to_dict`.

    Returns
    -------
    BuildingArchetype
        Validated hierarchy with preserved material and construction UUIDs.

    Raises
    ------
    ValueError
        The format version or a domain value is invalid.
    KeyError
        A required record field is missing.
    """
    if data.get("format_version") not in (1, 2, 3):
        raise ValueError("Unsupported archetype format_version")
    values = dict(data["archetype"])
    construction = dict(values["construction_set"])
    elements = {}
    for key, raw in construction["elements"].items():
        role = BuildingElement(key)
        element = dict(raw)
        if BuildingElement(element["application"]) != role:
            raise ValueError("Element application must match its construction role")
        if role is BuildingElement.WINDOW:
            element.pop("application")
            elements[role] = WindowElement(**element)
        else:
            element["application"] = role
            element["components"] = tuple(_component(c) for c in element["components"])
            elements[role] = Element(**element)
    construction["elements"] = elements
    construction["version_id"] = UUID(construction["version_id"])
    values["construction_set"] = ConstructionSet(**construction)
    events = []
    for raw in values.get("renovation_log", ()):
        event = dict(raw)
        for field in ("construction_set_before", "construction_set_after"):
            event[field] = UUID(event[field])
        for field in ("removed_components", "added_components"):
            event[field] = tuple(event[field])
        events.append(RenovationEvent(**event))
    values["renovation_log"] = tuple(events)
    return BuildingArchetype(**values)
