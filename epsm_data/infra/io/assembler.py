"""Assemblers — map raw I/O DTOs into validated domain objects.

Each assembler reads a sheet/JSON via the low-level readers, cross-
references with already-resolved domain lookups, and returns domain
objects plus skip diagnostics.
"""

from __future__ import annotations

import logging
from pathlib import Path

from epsm_data.domain.building import BuildingArchetype, build_construction_set
from epsm_data.domain.component import Component
from epsm_data.domain.element import Element
from epsm_data.domain.enums import BuildingElement, Roughness, ShearingLayer
from epsm_data.domain.layer import Layer, LayerMaterial, resolve_fractions
from epsm_data.domain.material import OpaqueMaterial
from epsm_data.infra.api.boverket_client import parse_embodied_carbon
from epsm_data.thermal import compute_element_thermal

from .excel_reader import (
    read_building_sheet,
    read_component_sheet,
    read_element_sheet,
    read_layer_sheet,
    read_material_sheet,
)
from .json_reader import read_opaque_material_json

logger = logging.getLogger(__name__)


def assemble_materials(
    excel_path: Path,
    json_path: Path,
    resource_lookup: dict[str, dict],
) -> tuple[list[OpaqueMaterial], list[tuple[str, str]]]:
    """Build OpaqueMaterial domain objects from Excel + JSON + API data."""
    mat_rows = read_material_sheet(excel_path)
    ep_data = read_opaque_material_json(json_path)

    results: list[OpaqueMaterial] = []
    skipped: list[tuple[str, str]] = []

    for row in mat_rows.records:
        api_json = resource_lookup.get(row.boverket_id)
        if api_json is None:
            skipped.append((row.name, f"Boverket ID {row.boverket_id} not found in API"))
            continue

        props = ep_data.get(row.honeybee_id)
        if props is None:
            skipped.append((row.name, f"Honeybee ID '{row.honeybee_id}' not in JSON"))
            continue

        try:
            ec = parse_embodied_carbon(api_json, row.name)
            mat = OpaqueMaterial(
                name=row.name,
                json_id=row.honeybee_id,
                boverket_id=row.boverket_id,
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
            results.append(mat)
        except Exception as exc:
            skipped.append((row.name, str(exc)))

    logger.info("OpaqueMaterial — loaded: %d, skipped: %d", len(results), len(skipped))
    return results, skipped


def assemble_layers(
    excel_path: Path,
    mat_lookup: dict[str, OpaqueMaterial],
) -> tuple[list[Layer], list[tuple[str, str]]]:
    """Build Layer domain objects from Excel rows + resolved materials."""
    layer_rows = read_layer_sheet(excel_path)
    results: list[Layer] = []
    skipped: list[tuple[str, str]] = []

    for row in layer_rows.records:
        slot_mats: list[tuple[OpaqueMaterial, float | None]] = []
        error: str | None = None

        for slot in row.materials:
            mat = mat_lookup.get(slot.material_name)
            if mat is None:
                error = f"Material '{slot.material_name}' not found"
                break
            slot_mats.append((mat, slot.area_fraction))

        if error:
            skipped.append((row.layer_code, error))
            continue

        try:
            fracs = resolve_fractions([f for _, f in slot_mats])
        except ValueError as exc:
            skipped.append((row.layer_code, f"Fraction error: {exc}"))
            continue

        materials = tuple(
            LayerMaterial(material=mat, area_fraction=frac, thickness=row.thickness)
            for (mat, _), frac in zip(slot_mats, fracs)
        )

        try:
            layer = Layer(
                name=row.layer_code,
                layer_code=row.layer_code,
                thickness=row.thickness,
                materials=materials,
                is_composite=row.is_composite,
            )
            results.append(layer)
        except Exception as exc:
            skipped.append((row.layer_code, str(exc)))

    logger.info("Layer — loaded: %d, skipped: %d", len(results), len(skipped))
    return results, skipped


def assemble_components(
    excel_path: Path,
    layer_lookup: dict[str, Layer],
) -> tuple[list[Component], list[tuple[str, str]]]:
    """Build Component domain objects from Excel rows + resolved layers."""
    comp_rows = read_component_sheet(excel_path)
    results: list[Component] = []
    skipped: list[tuple[str, str]] = []

    for row in comp_rows.records:
        layers: list[tuple[Layer, int]] = []
        error: str | None = None

        for ref in row.layers:
            layer = layer_lookup.get(ref.layer_code)
            if layer is None:
                error = f"Layer '{ref.layer_code}' not found"
                break
            layers.append((layer, ref.layer_index))

        if error:
            skipped.append((row.component_code, error))
            continue

        try:
            shearing = ShearingLayer(row.shearing_layer)
        except ValueError:
            skipped.append((row.component_code, f"Invalid shearing layer '{row.shearing_layer}'"))
            continue

        try:
            application = BuildingElement.from_name(row.application)
            if application is None:
                skipped.append((row.component_code, f"Invalid application '{row.application}'"))
                continue
        except ValueError:
            skipped.append((row.component_code, f"Invalid application '{row.application}'"))
            continue

        try:
            comp = Component(
                name=row.component_code,
                archetype=row.archetype,
                application=application,
                layers=tuple(layers),
                shearing_layer=shearing,
            )
            results.append(comp)
        except Exception as exc:
            skipped.append((row.component_code, str(exc)))

    logger.info("Component — loaded: %d, skipped: %d", len(results), len(skipped))
    return results, skipped


def assemble_elements(
    excel_path: Path,
    comp_lookup: dict[str, Component],
) -> tuple[list[Element], list[tuple[str, str]]]:
    """Build Element domain objects from Excel rows + resolved components.

    Runs thermal validation (U-value + TABULA check) on each element.
    """
    elem_rows = read_element_sheet(excel_path)
    shearing_order = ShearingLayer.sort_order()

    results: list[Element] = []
    skipped: list[tuple[str, str]] = []

    for row in elem_rows.records:
        el_type = BuildingElement.from_name(row.element_type)
        if el_type is None:
            skipped.append((row.element_code, f"Unknown element type '{row.element_type}'"))
            continue

        comps: list[Component] = []
        seen: set[str] = set()

        for code in row.component_codes:
            if code in seen:
                continue
            seen.add(code)
            comp = comp_lookup.get(code)
            if comp is None:
                logger.warning(
                    "%s: component '%s' not loaded — skipping component",
                    row.element_code, code,
                )
                continue
            comps.append(comp)

        if not comps:
            skipped.append((row.element_code, "No components found"))
            continue

        comps.sort(
            key=lambda c: (
                shearing_order.index(c.shearing_layer)
                if c.shearing_layer in shearing_order
                else 999
            )
        )

        try:
            element = Element(
                name=row.element_code,
                archetype=row.archetype,
                age=row.construction_year,
                components=tuple(comps),
                application=el_type,
            )
            # Thermal validation
            thermal = compute_element_thermal(element)
            logger.info(
                "%s: U=%.3f W/(m²·K)%s",
                element.name,
                thermal.u_value,
                f" [TABULA ref={thermal.tabula_u_value:.3f}]" if thermal.tabula_u_value else "",
            )
            if thermal.tabula_warning:
                logger.warning("%s: %s", element.name, thermal.tabula_warning)
            results.append(element)
        except Exception as exc:
            skipped.append((row.element_code, str(exc)))

    logger.info("Element — loaded: %d, skipped: %d", len(results), len(skipped))
    return results, skipped


def assemble_buildings(
    excel_path: Path,
    elem_lookup: dict[str, Element],
) -> tuple[list[BuildingArchetype], list[tuple[str, str]]]:
    """Build BuildingArchetype domain objects from Excel rows + resolved elements."""
    bldg_rows = read_building_sheet(excel_path)
    results: list[BuildingArchetype] = []
    skipped: list[tuple[str, str]] = []

    for row in bldg_rows.records:
        elements: dict[BuildingElement, Element] = {}
        for role_str, elem_code in row.element_assignments:
            elem = elem_lookup.get(elem_code)
            if elem is None:
                logger.warning("'%s': element '%s' not loaded — skipping role", row.archetype, elem_code)
                continue
            elements[elem.application] = elem

        if not elements:
            skipped.append((row.archetype, "No elements resolved"))
            continue

        try:
            cs = build_construction_set(elements, row.construction_year)
            archetype = BuildingArchetype(
                archetype_id=row.archetype,
                display_name=row.archetype,
                construction_year=row.construction_year,
                building_typology="multi_family",
                construction_set=cs,
            )
            results.append(archetype)
        except Exception as exc:
            skipped.append((row.archetype, str(exc)))

    logger.info("BuildingArchetype — loaded: %d, skipped: %d", len(results), len(skipped))
    return results, skipped
