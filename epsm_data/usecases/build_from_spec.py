"""Build archetypes from a plain dict specification.

Thermal properties are resolved from the honeybee JSON; embodied-carbon
data is resolved from the Boverket API.  The caller only needs to
specify *composition* — material references, thicknesses, and assembly
structure.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from epsm_data.domain.building import (
    BuildingArchetype,
    build_construction_set,
)
from epsm_data.domain.component import Component, LayerSlot
from epsm_data.domain.element import Element, WindowElement
from epsm_data.domain.enums import BuildingElement, Roughness, ShearingLayer
from epsm_data.domain.layer import Layer, LayerMaterial
from epsm_data.domain.material import OpaqueMaterial
from epsm_data.infra.api.boverket_client import (
    build_resource_lookup,
    fetch_all_materials,
    parse_embodied_carbon,
)
from epsm_data.infra.io.json_reader import read_opaque_material_json

logger = logging.getLogger(__name__)

_REQUIRED_ELEMENTS = frozenset(
    {
        BuildingElement.ROOF,
        BuildingElement.TOP_FLOOR,
        BuildingElement.INTERMEDIATE_FLOOR,
        BuildingElement.GROUND_FLOOR,
        BuildingElement.BASEMENT_FLOOR,
        BuildingElement.BASEMENT_WALL,
        BuildingElement.EXT_WALL,
        BuildingElement.WINDOW,
    }
)


# ── public API ────────────────────────────────────────────────────


def build_archetype_from_spec(
    spec: dict[str, Any],
    opaque_json_path: Path,
    *,
    api_resources: list[dict] | None = None,
    skip_api: bool = False,
) -> BuildingArchetype:
    """Build a single archetype from a dict specification.

    Parameters
    ----------
    spec
        Archetype recipe.  Required top-level keys:

        * ``archetype_id`` — unique identifier (e.g. ``"CUSTOM_1960"``)
        * ``display_name`` — human-readable label
        * ``construction_year`` — int
        * ``building_typology`` — ``"multi_family"`` or ``"single_family"``
        * ``elements`` — dict of element-role → element spec (see below)

        Each **opaque element** spec (keyed by ``BuildingElement`` value,
        e.g. ``"EXT_WALL"``, ``"ROOF"``)::

            {
                "components": [
                    {
                        "shearing_layer": "Skin",  # ShearingLayer value
                        "layers": [
                            {
                                "honeybee_id": "Face Brick",
                                "boverket_id": "12345",
                                "thickness": 0.12,
                                "name": "Face Brick 120mm",  # optional
                            },
                            ...
                        ],
                    },
                ],
            }

        Composite layers (multiple materials at the same depth)::

            {
                "honeybee_id": ["Stud", "Mineral Wool"],
                "boverket_id": ["111", "222"],
                "thickness": 0.15,
                "area_fraction": [0.15, 0.85],
            }

        **Window** element spec (keyed by ``"WINDOW"``)::

            {
                "u_value": 2.8,
                "shgc": 0.70,        # optional, default 0.70
                "vt": 0.65,          # optional, default 0.65
                "boverket_id": 999,  # optional
            }

    opaque_json_path
        Path to ``opaque_material.json`` (honeybee thermal properties).
    api_resources
        Pre-fetched Boverket API resources.  Pass this to avoid the
        network call (useful when building many archetypes).
    skip_api
        If *True*, skip the Boverket API entirely and create materials
        **without** embodied-carbon data.  For testing / quick drafts.

    Returns
    -------
    BuildingArchetype
        Fully resolved archetype with thermal + LCA data.
    """
    archetype_id = spec["archetype_id"]
    construction_year = spec["construction_year"]

    # ── resolve data sources ──────────────────────────────────────
    ep_data = read_opaque_material_json(opaque_json_path)

    resource_lookup: dict[str, dict] = {}
    if api_resources is not None:
        resource_lookup = build_resource_lookup(api_resources)
    elif not skip_api:
        resource_lookup = build_resource_lookup(fetch_all_materials())

    # ── build elements ────────────────────────────────────────────
    elements: dict[BuildingElement, Element | WindowElement] = {}

    for role_key, elem_spec in spec["elements"].items():
        role = BuildingElement(role_key)

        if role is BuildingElement.WINDOW:
            elements[role] = _build_window(elem_spec, archetype_id)
        else:
            elements[role] = _build_opaque_element(
                elem_spec,
                role,
                archetype_id,
                construction_year,
                ep_data,
                resource_lookup,
                skip_api,
            )

    # ── validate required elements ────────────────────────────────
    provided = set(elements)
    missing = _REQUIRED_ELEMENTS - provided
    if missing:
        missing_names = sorted(m.value for m in missing)
        raise ValueError(
            f"Archetype '{archetype_id}' is missing required elements: "
            f"{', '.join(missing_names)}"
        )

    cs = build_construction_set(elements, construction_year)

    return BuildingArchetype(
        archetype_id=archetype_id,
        display_name=spec["display_name"],
        construction_year=construction_year,
        building_typology=spec["building_typology"],
        construction_set=cs,
    )


# ── internal helpers ──────────────────────────────────────────────


def _build_window(
    spec: dict[str, Any],
    archetype_id: str,
) -> WindowElement:
    return WindowElement(
        name=f"{archetype_id}_WINDOW",
        archetype=archetype_id,
        u_value=spec["u_value"],
        shgc=spec.get("shgc", 0.70),
        vt=spec.get("vt", 0.65),
        boverket_id=spec.get("boverket_id"),
    )


def _build_opaque_element(
    spec: dict[str, Any],
    role: BuildingElement,
    archetype_id: str,
    construction_year: int,
    ep_data: dict,
    resource_lookup: dict[str, dict],
    skip_api: bool,
) -> Element:
    components: list[Component] = []

    for comp_idx, comp_spec in enumerate(spec["components"]):
        shearing_layer = ShearingLayer(comp_spec["shearing_layer"])
        layer_slots: list[LayerSlot] = []

        for lay_idx, lay_spec in enumerate(comp_spec["layers"]):
            layer = _build_layer(
                lay_spec, lay_idx, archetype_id, role,
                ep_data, resource_lookup, skip_api,
            )
            layer_slots.append(LayerSlot(layer=layer, position=lay_idx))

        comp_name = f"{archetype_id}_{role.value}_C{comp_idx}"
        components.append(
            Component(
                name=comp_name,
                archetype=archetype_id,
                application=role,
                layers=tuple(layer_slots),
                shearing_layer=shearing_layer,
            )
        )

    elem_name = f"{archetype_id}_{role.value}"
    return Element(
        name=elem_name,
        archetype=archetype_id,
        age=construction_year,
        components=tuple(components),
        application=role,
    )


def _build_layer(
    spec: dict[str, Any],
    index: int,
    archetype_id: str,
    role: BuildingElement,
    ep_data: dict,
    resource_lookup: dict[str, dict],
    skip_api: bool,
) -> Layer:
    thickness = spec["thickness"]

    # Normalise to lists for uniform handling (single or composite)
    honeybee_ids = spec["honeybee_id"]
    boverket_ids = spec["boverket_id"]
    is_list = isinstance(honeybee_ids, list)
    if not is_list:
        honeybee_ids = [honeybee_ids]
        boverket_ids = [boverket_ids]

    fractions = spec.get("area_fraction")
    if fractions is None:
        fractions = [1.0] if len(honeybee_ids) == 1 else None
    if not isinstance(fractions, list):
        fractions = [fractions]

    if fractions is None:
        raise ValueError(
            f"Composite layer at index {index} for {role.value} "
            f"requires 'area_fraction'."
        )

    if len(honeybee_ids) != len(boverket_ids):
        raise ValueError(
            f"Layer {index}: honeybee_id count ({len(honeybee_ids)}) "
            f"!= boverket_id count ({len(boverket_ids)})."
        )

    layer_materials: list[LayerMaterial] = []
    for hb_id, bov_id, frac in zip(honeybee_ids, boverket_ids, fractions):
        mat = _resolve_material(
            hb_id, str(bov_id), ep_data, resource_lookup, skip_api,
        )
        layer_materials.append(
            LayerMaterial(material=mat, area_fraction=frac, thickness=thickness)
        )

    is_composite = len(layer_materials) > 1
    layer_name = spec.get("name", f"{archetype_id}_{role.value}_L{index}")
    layer_code = layer_name

    return Layer(
        name=layer_name,
        layer_code=layer_code,
        thickness=thickness,
        materials=tuple(layer_materials),
        is_composite=is_composite,
    )


# Material cache to avoid re-resolving the same honeybee+boverket pair
_material_cache: dict[tuple[str, str], OpaqueMaterial] = {}


def _resolve_material(
    honeybee_id: str,
    boverket_id: str,
    ep_data: dict,
    resource_lookup: dict[str, dict],
    skip_api: bool,
) -> OpaqueMaterial:
    cache_key = (honeybee_id, boverket_id)
    if cache_key in _material_cache:
        return _material_cache[cache_key]

    # ── thermal properties from honeybee JSON ─────────────────────
    props = ep_data.get(honeybee_id)
    if props is None:
        available = ", ".join(sorted(ep_data)[:10])
        raise KeyError(
            f"Honeybee ID '{honeybee_id}' not found in opaque_material.json. "
            f"Available (first 10): {available}"
        )

    # ── embodied carbon from Boverket API ─────────────────────────
    if skip_api:
        from epsm_data.domain.material import EmbodiedCarbon

        ec = EmbodiedCarbon(
            name=honeybee_id,
            resource_id=boverket_id,
            boverket_name="(skipped)",
            A1_A3_conservative=0.0,
            A1_A3_typical=0.0,
            A4_transport=0.0,
            A5_conservative=0.0,
            conservative_factor=1.0,
            conversion_factor=1.0,
            technical_service_life="0",
            biogenic_carbon=0.0,
        )
    else:
        api_json = resource_lookup.get(boverket_id)
        if api_json is None:
            raise KeyError(
                f"Boverket ID '{boverket_id}' not found in API resources."
            )
        ec = parse_embodied_carbon(api_json, honeybee_id)

    mat = OpaqueMaterial(
        name=honeybee_id,
        json_id=honeybee_id,
        boverket_id=boverket_id,
        material_type=props.material_type,
        roughness=Roughness(props.roughness),
        density=props.density,
        specific_heat=props.specific_heat,
        thermal_absorptance=props.thermal_absorptance,
        solar_absorptance=props.solar_absorptance,
        visible_absorptance=props.visible_absorptance,
        conductivity=props.conductivity,
        embodied_carbon=ec,
    )
    _material_cache[cache_key] = mat
    return mat
