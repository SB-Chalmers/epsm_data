"""Build baseline archetypes use-case.

Orchestrates the full pipeline: fetch API data, then run assemblers
in dependency order to produce BuildingArchetype instances.
"""

from __future__ import annotations

import logging
from pathlib import Path

from epsm_data.domain.building import BuildingArchetype
from epsm_data.infra.api.boverket_client import build_resource_lookup, fetch_all_materials
from epsm_data.infra.io.assembler import (
    assemble_buildings,
    assemble_components,
    assemble_elements,
    assemble_layers,
    assemble_materials,
)

logger = logging.getLogger(__name__)


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
    materials, _ = assemble_materials(excel_path, opaque_json_path, resource_lookup)
    mat_lookup = {m.name: m for m in materials}

    # Stage 2: Layers
    layers, _ = assemble_layers(excel_path, mat_lookup)
    layer_lookup = {l.layer_code: l for l in layers}

    # Stage 3: Components
    components, _ = assemble_components(excel_path, layer_lookup)
    comp_lookup = {c.name: c for c in components}

    # Stage 4: Elements (includes thermal validation)
    elements, _ = assemble_elements(excel_path, comp_lookup)
    elem_lookup = {e.name: e for e in elements}

    # Stage 5: Buildings
    archetypes, _ = assemble_buildings(excel_path, elem_lookup)

    return archetypes
