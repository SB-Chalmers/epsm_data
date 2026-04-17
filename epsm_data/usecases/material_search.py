"""Search helpers for finding materials in honeybee JSON and Boverket API.

Convenience functions for discovering material identifiers when
building archetype specs manually.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from epsm_data.infra.api.boverket_client import fetch_all_materials
from epsm_data.infra.io.json_reader import read_opaque_material_json

logger = logging.getLogger(__name__)


# ── Honeybee JSON search ─────────────────────────────────────────


def search_honeybee_materials(
    query: str,
    opaque_json_path: Path,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search the honeybee opaque_material.json by keyword.

    Matches against the material identifier (case-insensitive substring).
    Returns a list of dicts with key properties for quick comparison.

    Parameters
    ----------
    query
        Search term (case-insensitive).  Supports simple terms like
        ``"brick"``, ``"gypsum"``, ``"concrete"``, or ``"wool"``.
    opaque_json_path
        Path to ``opaque_material.json``.
    limit
        Maximum results to return.

    Returns
    -------
    list[dict]
        Each dict contains: ``identifier``, ``conductivity``, ``density``,
        ``specific_heat``, ``roughness``, ``thickness`` (default from JSON).

    Example
    -------
    >>> results = search_honeybee_materials("brick", Path("Data/opaque_material.json"))
    >>> for r in results:
    ...     print(f"{r['identifier']:40s}  λ={r['conductivity']:.3f}  ρ={r['density']:.0f}")
    """
    with open(opaque_json_path, encoding="utf-8") as f:
        raw = json.load(f)

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    matches: list[dict[str, Any]] = []

    for key, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        # Only include proper EnergyMaterial entries
        if entry.get("type") != "EnergyMaterial":
            continue
        if not pattern.search(key):
            continue

        matches.append(
            {
                "identifier": entry.get("identifier", key),
                "conductivity": entry.get("conductivity"),
                "density": entry.get("density"),
                "specific_heat": entry.get("specific_heat"),
                "roughness": entry.get("roughness"),
                "thickness": entry.get("thickness"),
            }
        )
        if len(matches) >= limit:
            break

    return matches


def list_honeybee_materials(
    opaque_json_path: Path,
) -> list[str]:
    """Return all valid material identifiers from the honeybee JSON.

    Useful for seeing the full catalog at a glance.
    """
    with open(opaque_json_path, encoding="utf-8") as f:
        raw = json.load(f)

    return sorted(
        key
        for key, entry in raw.items()
        if isinstance(entry, dict) and entry.get("type") == "EnergyMaterial"
    )


# ── Boverket Klimatdatabas search ────────────────────────────────


def search_boverket_materials(
    query: str,
    *,
    api_resources: list[dict] | None = None,
    limit: int = 20,
    language: str = "en",
) -> list[dict[str, Any]]:
    """Search the Boverket Klimatdatabas for materials by keyword.

    Matches against ``Name`` (EN and SV), ``Synonyms``, and
    ``Categories`` (case-insensitive substring).

    Parameters
    ----------
    query
        Search term, e.g. ``"brick"``, ``"mineral wool"``, ``"concrete"``.
    api_resources
        Pre-fetched API resources (avoids network call).
        If *None*, fetches fresh from the Boverket API.
    limit
        Maximum results to return.
    language
        Display language for the name: ``"en"`` (default) or ``"sv"``.

    Returns
    -------
    list[dict]
        Each dict contains: ``resource_id``, ``name``, ``name_sv``,
        ``categories``, ``unit``, ``service_life``, ``conversion_factor``.

    Example
    -------
    >>> results = search_boverket_materials("brick")
    >>> for r in results:
    ...     print(f"{r['resource_id']}  {r['name']}")
    """
    if api_resources is None:
        api_resources = fetch_all_materials()

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    matches: list[dict[str, Any]] = []

    for resource in api_resources:
        # Build searchable text from multiple fields
        names = resource.get("Names", {})
        name_en = names.get("EN", "")
        name_sv = names.get("SV", "")
        synonyms = resource.get("Synonyms") or ""
        categories = resource.get("Categories", [])
        cat_names = " ".join(
            c.get("Name", "") for c in categories if isinstance(c, dict)
        )
        searchable = f"{name_en} {name_sv} {synonyms} {cat_names}"

        if not pattern.search(searchable):
            continue

        # Extract conversion factor (kg/m³)
        conversion = next(
            (c["Value"] for c in resource.get("Conversions", [])
             if isinstance(c, dict) and c.get("Field") == "Volume"),
            None,
        )

        display_name = name_en if language == "en" else name_sv

        matches.append(
            {
                "resource_id": str(resource.get("ResourceId", "")),
                "name": display_name or name_en or name_sv,
                "name_sv": name_sv,
                "categories": [
                    c.get("Name", "") for c in categories if isinstance(c, dict)
                ],
                "unit": resource.get("InventoryUnit", ""),
                "service_life": resource.get("RefServiceLifeNormal"),
                "conversion_factor": conversion,
            }
        )
        if len(matches) >= limit:
            break

    return matches


def list_boverket_materials(
    *,
    api_resources: list[dict] | None = None,
    language: str = "en",
) -> list[dict[str, str]]:
    """Return all materials from the Boverket API as (resource_id, name) pairs.

    Useful for browsing the full catalog.
    """
    if api_resources is None:
        api_resources = fetch_all_materials()

    results: list[dict[str, str]] = []
    for resource in api_resources:
        names = resource.get("Names", {})
        name_en = names.get("EN", "")
        name_sv = names.get("SV", "")
        display = name_en if language == "en" else name_sv
        results.append(
            {
                "resource_id": str(resource.get("ResourceId", "")),
                "name": display or name_en or name_sv,
            }
        )

    return sorted(results, key=lambda r: r["name"])
