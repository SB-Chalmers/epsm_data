"""Export outputs use-case.

Exports BuildingArchetype data to JSON files (dated) and generates
consumption contracts for downstream libraries like pbgenerator.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from epsm_data.domain.building import BuildingArchetype
from epsm_data.domain.enums import BuildingElement

logger = logging.getLogger(__name__)


def _require_layer_archetypes(archetypes) -> None:
    """Require material-layer archetypes before creating directories or exports."""
    for item in archetypes:
        if not isinstance(item, BuildingArchetype):
            raise TypeError("Construction exports require a material-layer BuildingArchetype")


# Element roles mapped to downstream construction set keys
_ROLE_TO_CONSTRUCTION = {
    BuildingElement.EXT_WALL: "wall",
    BuildingElement.EXT_WALL_LOW: "wall",
    BuildingElement.EXT_WALL_MEDIUM: "wall",
    BuildingElement.EXT_WALL_HIGH: "wall",
    BuildingElement.ROOF: "roof",
    BuildingElement.TOP_FLOOR: "roof",  # top floor pairs with roof
    BuildingElement.GROUND_FLOOR: "floor",
    BuildingElement.BASEMENT_FLOOR: "floor",
}


def export_json(
    archetypes: list[BuildingArchetype],
    output_dir: Path,
) -> None:
    """Export archetype data to dated JSON files (materials, layers, etc.).

    Parameters
    ----------
    archetypes : list of BuildingArchetype
        Records to traverse.
    output_dir : Path
        Destination directory, created if absent. Same-date files are replaced.

    Notes
    -----
    Mirrors the historical summary format. Use archetype_to_dict for lossless
    storage including material properties and snapshot IDs.
    """
    _require_layer_archetypes(archetypes)
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.today().strftime("%d-%m-%Y")

    # Collect all domain objects across archetypes
    all_materials: dict[str, dict] = {}
    all_layers: dict[str, dict] = {}
    all_components: dict[str, dict] = {}
    all_elements: dict[str, dict] = {}
    all_buildings: dict[str, dict] = {}

    for arch in archetypes:
        all_buildings[arch.archetype_id] = arch.to_dict()
        for _role, elem in arch.construction_set.elements.items():
            all_elements[elem.name] = elem.to_dict()
            if not hasattr(elem, "components"):
                continue
            for comp in elem.components:
                all_components[comp.name] = comp.to_dict()
                for slot in comp.layers:
                    all_layers[slot.layer.layer_code] = slot.layer.to_dict()
                    for lm in slot.layer.materials:
                        all_materials[lm.material.name] = lm.material.to_dict()

    files = {
        f"materials_{today}.json": all_materials,
        f"layers_{today}.json": all_layers,
        f"components_{today}.json": all_components,
        f"elements_{today}.json": all_elements,
        f"buildings_{today}.json": all_buildings,
    }

    for filename, data in files.items():
        path = output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Exported %d records -> %s", len(data), path)


def export_consumption_contracts(
    archetypes: list[BuildingArchetype],
    output_dir: Path,
) -> None:
    """Export per-archetype consumption contracts as JSON.

    Parameters
    ----------
    archetypes : list of BuildingArchetype
        Records to summarize.
    output_dir : Path
        Destination directory; the same-date file is replaced.

    Notes
    -----
    Contracts summarize current U-values and reference component names.
    They are not a lossless representation of the full material hierarchy.
    """
    _require_layer_archetypes(archetypes)
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.today().strftime("%d-%m-%Y")

    contracts = {arch.archetype_id: arch.to_consumption_contract() for arch in archetypes}
    path = output_dir / f"consumption_contracts_{today}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(contracts, f, indent=2, ensure_ascii=False)
    logger.info("Exported %d consumption contracts -> %s", len(contracts), path)


def export_construction_sets(
    archetypes: list[BuildingArchetype],
    output_dir: Path,
) -> None:
    """Export construction set definitions for downstream pbgenerator.

    Produces a JSON mapping archetype_id -> {wall, roof, floor} where
    each contains an ordered list of material layers with the properties
    needed by honeybee EnergyMaterial: name, thickness, conductivity,
    density, specific_heat, roughness.

    Parameters
    ----------
    archetypes : list of BuildingArchetype
        Records to flatten using the historical role mapping.
    output_dir : Path
        Destination directory; the same-date file is replaced.

    Notes
    -----
    The legacy mapping concatenates roles sharing a target key. Downstream
    consumers must select applicable roles explicitly for simulation handover.
    """
    _require_layer_archetypes(archetypes)
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.today().strftime("%d-%m-%Y")

    result: dict[str, dict] = {}

    for arch in archetypes:
        cs_def: dict[str, list[dict]] = {}

        for role, elem in arch.construction_set.elements.items():
            target_key = _ROLE_TO_CONSTRUCTION.get(role)
            if target_key is None:
                continue  # internal partitions not in downstream set

            layers: list[dict] = []
            for comp in elem.components:
                for slot in comp.layers:
                    layer = slot.layer
                    # For composite layers, use area-weighted effective properties
                    if layer.is_composite:
                        eff_conductivity = sum(
                            m.material.conductivity * m.area_fraction for m in layer.materials
                        )
                        eff_density = sum(
                            m.material.density * m.area_fraction for m in layer.materials
                        )
                        eff_specific_heat = sum(
                            m.material.specific_heat * m.area_fraction for m in layer.materials
                        )
                        # Use first material's roughness/name as representative
                        first = layer.materials[0]
                        eff_name = f"{layer.layer_code}_eff"
                        roughness = first.material.roughness.value
                    else:
                        m = layer.materials[0]
                        eff_name = m.material.name
                        eff_conductivity = m.material.conductivity
                        eff_density = m.material.density
                        eff_specific_heat = m.material.specific_heat
                        roughness = m.material.roughness.value

                    layers.append(
                        {
                            "name": eff_name,
                            "thickness": round(layer.thickness, 4),
                            "conductivity": round(eff_conductivity, 4),
                            "density": round(eff_density, 4),
                            "specific_heat": round(eff_specific_heat, 4),
                            "roughness": roughness,
                        }
                    )

            # Merge into existing key (e.g. roof = ROOF + TOP_FLOOR layers)
            if target_key in cs_def:
                cs_def[target_key].extend(layers)
            else:
                cs_def[target_key] = layers

        # Add U-values for reference
        u_values = arch.envelope_u_values
        result[arch.archetype_id] = {
            "construction_year": arch.construction_year,
            "u_values": u_values,
            **cs_def,
        }

    path = output_dir / f"construction_sets_{today}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.info("Exported %d construction sets -> %s", len(result), path)
