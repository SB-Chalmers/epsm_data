"""JSON reader for material property files.

Loads local material/property JSON files, validates schema shape, and
returns typed DTOs ready for domain construction.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .dto import OpaqueMaterialProps, WindowGasProps, WindowGlazingProps

logger = logging.getLogger(__name__)

_OPAQUE_REQUIRED = frozenset(
    {
        "type",
        "identifier",
        "roughness",
        "thickness",
        "conductivity",
        "density",
        "specific_heat",
        "thermal_absorptance",
        "solar_absorptance",
        "visible_absorptance",
    }
)

_GLAZING_REQUIRED = frozenset(
    {
        "type",
        "identifier",
        "thickness",
        "conductivity",
        "solar_transmittance",
        "solar_reflectance",
        "solar_reflectance_back",
        "visible_transmittance",
        "visible_reflectance",
        "visible_reflectance_back",
        "infrared_transmittance",
        "emissivity",
        "emissivity_back",
        "dirt_correction",
    }
)

_GAS_REQUIRED = frozenset({"type", "identifier", "thickness", "gas_type"})


def read_opaque_material_json(path: Path) -> dict[str, OpaqueMaterialProps]:
    """Load opaque material properties, keyed by identifier."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Expected JSON object at top level, got {type(raw).__name__}")

    result: dict[str, OpaqueMaterialProps] = {}

    for key, entry in raw.items():
        missing = _OPAQUE_REQUIRED - set(entry)
        if missing:
            logger.warning("Opaque material '%s': missing keys %s — skipped", key, missing)
            continue

        result[key] = OpaqueMaterialProps(
            identifier=entry["identifier"],
            material_type=entry["type"],
            roughness=entry["roughness"],
            thickness=entry["thickness"],
            conductivity=entry["conductivity"],
            density=entry["density"],
            specific_heat=entry["specific_heat"],
            thermal_absorptance=entry["thermal_absorptance"],
            solar_absorptance=entry["solar_absorptance"],
            visible_absorptance=entry["visible_absorptance"],
        )

    logger.info(
        "Opaque material JSON — loaded %d / %d entries", len(result), len(raw)
    )
    return result


def read_window_material_json(
    path: Path,
) -> tuple[dict[str, WindowGlazingProps], dict[str, WindowGasProps]]:
    """Load window material properties.

    Returns two dicts: glazing entries and gas-layer entries,
    separated by their ``type`` field.
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Expected JSON object at top level, got {type(raw).__name__}")

    glazing: dict[str, WindowGlazingProps] = {}
    gas: dict[str, WindowGasProps] = {}

    for key, entry in raw.items():
        entry_type = entry.get("type", "")

        if entry_type == "EnergyWindowMaterialGlazing":
            missing = _GLAZING_REQUIRED - set(entry)
            if missing:
                logger.warning("Window glazing '%s': missing keys %s — skipped", key, missing)
                continue
            glazing[key] = WindowGlazingProps(
                identifier=entry["identifier"],
                material_type=entry["type"],
                thickness=entry["thickness"],
                conductivity=entry["conductivity"],
                solar_transmittance=entry["solar_transmittance"],
                solar_reflectance=entry["solar_reflectance"],
                solar_reflectance_back=entry["solar_reflectance_back"],
                visible_transmittance=entry["visible_transmittance"],
                visible_reflectance=entry["visible_reflectance"],
                visible_reflectance_back=entry["visible_reflectance_back"],
                infrared_transmittance=entry["infrared_transmittance"],
                emissivity=entry["emissivity"],
                emissivity_back=entry["emissivity_back"],
                dirt_correction=entry["dirt_correction"],
                solar_diffusing=entry.get("solar_diffusing", False),
            )

        elif entry_type == "EnergyWindowMaterialGas":
            missing = _GAS_REQUIRED - set(entry)
            if missing:
                logger.warning("Window gas '%s': missing keys %s — skipped", key, missing)
                continue
            gas[key] = WindowGasProps(
                identifier=entry["identifier"],
                material_type=entry["type"],
                thickness=entry["thickness"],
                gas_type=entry["gas_type"],
            )

        else:
            logger.warning("Window material '%s': unknown type '%s' — skipped", key, entry_type)

    logger.info(
        "Window material JSON — glazing: %d, gas: %d / %d total",
        len(glazing),
        len(gas),
        len(raw),
    )
    return glazing, gas
