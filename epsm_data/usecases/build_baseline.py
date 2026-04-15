"""Build baseline archetypes use-case.

Loads raw data (Excel, JSON, API) via infra adapters, constructs
validated domain objects, and returns BuildingArchetype instances with
baseline ConstructionSets ready for export or simulation.
"""

from __future__ import annotations

import logging
from pathlib import Path

from epsm_data.domain.building import BuildingArchetype, build_construction_set
from epsm_data.domain.component import Component
from epsm_data.domain.element import Element
from epsm_data.domain.enums import BuildingElement, Roughness, ShearingLayer
from epsm_data.domain.layer import Layer, LayerMaterial
from epsm_data.domain.material import EmbodiedCarbon, OpaqueMaterial
from epsm_data.infra.api.boverket_client import (
    build_resource_lookup,
    fetch_all_materials,
    parse_embodied_carbon,
)
from epsm_data.infra.io.dto import ReadResult
from epsm_data.infra.io.excel_reader import (
    read_building_sheet,
    read_component_sheet,
    read_element_sheet,
    read_layer_sheet,
    read_material_sheet,
)
from epsm_data.infra.io.json_reader import read_opaque_material_json
from epsm_data.thermal import compute_element_thermal

logger = logging.getLogger(__name__)


# ── fraction resolution ───────────────────────────────────────────


def _resolve_fractions(raw: list[float | None]) -> list[float]:
    """Fill in missing area fractions so they sum to 1.0."""
    missing = [i for i, f in enumerate(raw) if f is None]
    if not missing:
        return list(raw)  # type: ignore[arg-type]
    known_sum = sum(f for f in raw if f is not None)
    if known_sum > 1.0:
        raise ValueError(f"Known fractions sum to {known_sum:.4f}, exceeds 1.0.")
    fill = (1.0 - known_sum) / len(missing)
    result = list(raw)
    for i in missing:
        result[i] = fill
    return result  # type: ignore[return-value]


def _parse_age(archetype: str) -> int | None:
    """Extract a 4-digit year from an archetype name."""
    for part in archetype.split("_"):
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


# ── pipeline stages ───────────────────────────────────────────────


def _load_opaque_materials(
    excel_path: Path,
    json_path: Path,
    resource_lookup: dict[str, dict],
) -> tuple[list[OpaqueMaterial], list[tuple[str, str]]]:
    """Stage 1: build OpaqueMaterial domain objects."""
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


def _load_layers(
    excel_path: Path,
    mat_lookup: dict[str, OpaqueMaterial],
) -> tuple[list[Layer], list[tuple[str, str]]]:
    """Stage 2: build Layer domain objects."""
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
            fracs = _resolve_fractions([f for _, f in slot_mats])
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


def _load_components(
    excel_path: Path,
    layer_lookup: dict[str, Layer],
) -> tuple[list[Component], list[tuple[str, str]]]:
    """Stage 3: build Component domain objects."""
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


def _load_elements(
    excel_path: Path,
    comp_lookup: dict[str, Component],
) -> tuple[list[Element], list[tuple[str, str]]]:
    """Stage 4: build Element domain objects."""
    elem_rows = read_element_sheet(excel_path)
    shearing_order = ShearingLayer.sort_order()

    results: list[Element] = []
    skipped: list[tuple[str, str]] = []

    for row in elem_rows.records:
        age = _parse_age(row.archetype)
        if age is None:
            skipped.append((row.element_code, f"Could not parse age from '{row.archetype}'"))
            continue

        el_type = BuildingElement.from_name(row.element_type)
        if el_type is None:
            skipped.append((row.element_code, f"Unknown element type '{row.element_type}'"))
            continue

        comps: list[Component] = []
        error: str | None = None
        seen: set[str] = set()

        for code in row.component_codes:
            if code in seen:
                continue
            seen.add(code)
            comp = comp_lookup.get(code)
            if comp is None:
                error = f"Component '{code}' not found"
                break
            comps.append(comp)

        if error:
            skipped.append((row.element_code, error))
            continue
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
                age=age,
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


def _load_buildings(
    excel_path: Path,
    elem_lookup: dict[str, Element],
) -> tuple[list[BuildingArchetype], list[tuple[str, str]]]:
    """Stage 5: build BuildingArchetype domain objects."""
    bldg_rows = read_building_sheet(excel_path)
    results: list[BuildingArchetype] = []
    skipped: list[tuple[str, str]] = []

    for row in bldg_rows.records:
        age = _parse_age(row.archetype)
        if age is None:
            skipped.append((row.archetype, f"Could not parse age from '{row.archetype}'"))
            continue

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
            cs = build_construction_set(elements, age)
            archetype = BuildingArchetype(
                archetype_id=row.archetype,
                display_name=row.archetype,
                construction_year=age,
                building_typology="multi_family",
                construction_set=cs,
            )
            results.append(archetype)
        except Exception as exc:
            skipped.append((row.archetype, str(exc)))

    logger.info("BuildingArchetype — loaded: %d, skipped: %d", len(results), len(skipped))
    return results, skipped


# ── public entry point ────────────────────────────────────────────


def run_build_baseline(
    excel_path: Path,
    opaque_json_path: Path,
    *,
    skip_api: bool = False,
    api_resources: list[dict] | None = None,
) -> list[BuildingArchetype]:
    """Load, validate, and construct baseline BuildingArchetype instances.

    Parameters
    ----------
    excel_path : Path to Material_Database.xlsx
    opaque_json_path : Path to opaque_material.json
    skip_api : If True, skip Boverket API call (requires api_resources)
    api_resources : Pre-fetched API resources (avoids network call)
    """
    # Fetch Boverket API data
    if api_resources is not None:
        resources = api_resources
    elif skip_api:
        raise ValueError("skip_api=True but no api_resources provided")
    else:
        resources = fetch_all_materials()
    resource_lookup = build_resource_lookup(resources)

    # Stage 1: Materials
    materials, _ = _load_opaque_materials(excel_path, opaque_json_path, resource_lookup)
    mat_lookup = {m.name: m for m in materials}

    # Stage 2: Layers
    layers, _ = _load_layers(excel_path, mat_lookup)
    layer_lookup = {l.layer_code: l for l in layers}

    # Stage 3: Components
    components, _ = _load_components(excel_path, layer_lookup)
    comp_lookup = {c.name: c for c in components}

    # Stage 4: Elements
    elements, _ = _load_elements(excel_path, comp_lookup)
    elem_lookup = {e.name: e for e in elements}

    # Stage 5: Buildings
    archetypes, _ = _load_buildings(excel_path, elem_lookup)

    return archetypes
