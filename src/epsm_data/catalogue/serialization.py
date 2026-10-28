"""Lossless portable archetype records, independent of source ingestion.

The versioned nested format includes material properties and UUIDs. The older
to_dict/consumption views remain useful summaries but are not round-trip formats.
"""

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from uuid import UUID

from ..domain import (
    BuildingArchetype,
    BuildingElement,
    CarbonReference,
    Component,
    ConstructionSet,
    Element,
    EmbodiedCarbon,
    EnvelopePerformance,
    Layer,
    LayerMaterial,
    LayerSlot,
    OpaqueMaterial,
    RenovationEvent,
    Roughness,
    ShearingLayer,
    WindowElement,
)
from ..profiles import HVACTemplate, OperatingProfile


def _encode(value):
    if isinstance(value, (UUID, Enum)):
        return str(value) if isinstance(value, UUID) else value.value
    if is_dataclass(value):
        return {f.name: _encode(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
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
        Complete JSON-compatible format-version-4 record, including optional
        profiles and unresolved sections. Versions 1–3 remain readable.

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
    return {"format_version": 4, "archetype": encoded}


def _material(data):
    values = dict(data)
    values["uuid"] = UUID(values["uuid"])
    values["roughness"] = Roughness(values["roughness"])
    if values.get("carbon_reference") is not None:
        values["carbon_reference"] = CarbonReference.from_dict(values["carbon_reference"])
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
    if type(data.get("format_version")) is not int or data["format_version"] not in (1, 2, 3, 4):
        raise ValueError("Unsupported archetype format_version")
    values = dict(data["archetype"])
    if values.get("construction_set") is not None:
        values["construction_set"] = construction_set_from_dict(values["construction_set"])
    for name, definition in (
        ("operating_profile", OperatingProfile),
        ("hvac_template", HVACTemplate),
        ("envelope_performance", EnvelopePerformance),
    ):
        if values.get(name) is not None:
            values[name] = definition.from_dict(values[name])
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


def element_to_dict(element: Element | WindowElement) -> dict:
    """Serialize the full physical hierarchy, preserving outside-to-inside order."""
    return _encode(element)


def element_from_dict(data: dict) -> Element | WindowElement:
    """Restore a self-contained physical element without loading a catalogue."""
    values = dict(data)
    role = BuildingElement(values["application"])
    # A WINDOW role may hold a full material stack. Only the simple glazing
    # representation lacks components; the role alone does not identify its type.
    if role is BuildingElement.WINDOW and "components" not in values:
        values.pop("application")
        if values.get("carbon_reference") is not None:
            values["carbon_reference"] = CarbonReference.from_dict(values["carbon_reference"])
        return WindowElement(**values)
    values["application"] = role
    values["components"] = tuple(_component(c) for c in values["components"])
    return Element(**values)


def construction_set_to_dict(construction: ConstructionSet) -> dict:
    """Lossless construction record; IDs identify this composition, not a release."""
    return _encode(construction)


def construction_set_from_dict(data: dict) -> ConstructionSet:
    """Restore and validate a construction record with no catalogue dependency."""
    values = dict(data)
    values["elements"] = {
        BuildingElement(role): element_from_dict(element)
        for role, element in values["elements"].items()
    }
    values["version_id"] = UUID(values["version_id"])
    return ConstructionSet(**values)
