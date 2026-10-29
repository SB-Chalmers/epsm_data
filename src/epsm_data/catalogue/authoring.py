"""Construct archetypes from explicit composition and resolved materials."""

from collections.abc import Mapping
from typing import Any

from epsm_data.domain import (
    BuildingArchetype,
    BuildingElement,
    Component,
    Element,
    Layer,
    LayerMaterial,
    LayerSlot,
    OpaqueMaterial,
    ShearingLayer,
    WindowElement,
    build_construction_set,
)


def build_archetype(
    spec: Mapping[str, Any], *, materials: Mapping[str, OpaqueMaterial]
) -> BuildingArchetype:
    """Build an archetype without resolving sources or performing I/O.

    Parameters
    ----------
    spec : mapping
        Identity fields ``archetype_id``, ``display_name``, optional ``construction_year``
        and ``building_typology``, and an ``elements`` mapping keyed by BuildingElement
        values. Opaque elements contain ordered ``components`` with a
        ``shearing_layer`` and ordered ``layers``. Each layer specifies
        ``material_id`` (a string or list), ``thickness`` in metres, and, for
        composites, an ``area_fraction`` list summing to one. Windows specify
        whole-window ``u_value`` in W/(m² K), ``shgc``, and optionally ``vt``
        (default 0.65). Component and layer order is outside to inside.
    materials : mapping of str to OpaqueMaterial
        Validated materials keyed by the IDs referenced in ``spec``.

    Returns
    -------
    BuildingArchetype
        New construction snapshot with the supplied element roles. Downstream
        simulations validate their own completeness requirements.

    Raises
    ------
    KeyError
        A required field or material ID is missing.
    ValueError
        A role, thickness, or composite fraction is invalid.

    Examples
    --------
    >>> arch = build_archetype({
    ...     "archetype_id": "example", "display_name": "Example glazing",
    ...     "construction_year": 1960, "building_typology": "multi_family",
    ...     "elements": {"WINDOW": {"u_value": 2.5, "shgc": 0.7}},
    ... }, materials={})
    >>> arch.window.u_value
    2.5
    """
    identifier = spec["archetype_id"]
    year = spec.get("construction_year")
    elements = {}
    for role_name, element_spec in spec["elements"].items():
        role = BuildingElement(role_name)
        element_name = element_spec.get("name", f"{identifier}_{role.value}")
        if role is BuildingElement.WINDOW:
            elements[role] = WindowElement(
                name=element_name,
                archetype=identifier,
                u_value=element_spec["u_value"],
                shgc=element_spec["shgc"],
                vt=element_spec.get("vt", 0.65),
                boverket_id=element_spec.get("boverket_id"),
            )
            continue
        components = []
        for ci, component_spec in enumerate(element_spec["components"]):
            slots = []
            for li, layer_spec in enumerate(component_spec["layers"]):
                ids = layer_spec["material_id"]
                ids = [ids] if isinstance(ids, str) else list(ids)
                if not ids:
                    raise ValueError("A layer must reference at least one material")
                fractions = layer_spec.get("area_fraction")
                if fractions is None:
                    if len(ids) != 1:
                        raise ValueError("Composite layers require area_fraction")
                    fractions = [1.0]
                if not isinstance(fractions, (list, tuple)) or len(fractions) != len(ids):
                    raise ValueError("area_fraction must contain one entry per material_id")
                thickness = layer_spec["thickness"]
                # Include the component index to avoid layer ID collisions.
                layer_name = layer_spec.get("name", f"{element_name}_C{ci}_L{li}")
                layer = Layer(
                    name=layer_name,
                    layer_code=layer_name,
                    thickness=thickness,
                    materials=tuple(
                        LayerMaterial(materials[mid], fraction, thickness)
                        for mid, fraction in zip(ids, fractions, strict=True)
                    ),
                    is_composite=len(ids) > 1,
                )
                slots.append(LayerSlot(layer=layer, position=li))
            components.append(
                Component(
                    name=component_spec.get("name", f"{element_name}_C{ci}"),
                    archetype=identifier,
                    application=role,
                    layers=tuple(slots),
                    shearing_layer=ShearingLayer(component_spec["shearing_layer"]),
                )
            )
        elements[role] = Element(
            name=element_name,
            archetype=identifier,
            age=year,
            components=tuple(components),
            application=role,
        )
    return BuildingArchetype(
        archetype_id=identifier,
        display_name=spec["display_name"],
        construction_year=year,
        building_typology=spec.get("building_typology", "unknown"),
        construction_set=build_construction_set(elements, year),
    )
