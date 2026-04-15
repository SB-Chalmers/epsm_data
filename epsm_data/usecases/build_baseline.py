"""Build baseline archetypes use-case.

Orchestrates the full pipeline: fetch API data, then run assemblers
in dependency order to produce BuildingArchetype instances.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
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


@dataclass
class PipelineResult:
    """Structured report from a pipeline run."""

    archetypes: list[BuildingArchetype]
    stage_counts: dict[str, int] = field(default_factory=dict)
    stage_skipped: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    @property
    def total_skipped(self) -> int:
        return sum(len(v) for v in self.stage_skipped.values())

    def log_summary(self) -> None:
        """Emit a structured summary to the epsm_data logger."""
        logger.info("── Pipeline Summary ─────────────────────────────")
        for stage, count in self.stage_counts.items():
            skipped = len(self.stage_skipped.get(stage, []))
            logger.info("  %-14s  loaded: %3d   skipped: %3d", stage, count, skipped)

        logger.info("  %-14s  %d archetype(s)", "Result", len(self.archetypes))

        for arch in self.archetypes:
            u = arch.envelope_u_values
            wall_s = f"wall={u['wall']:.3f}" if "wall" in u else "wall=N/A"
            roof_s = f"roof={u.get('ROOF', 0):.3f}" if "ROOF" in u else "roof=N/A"
            logger.info(
                "    %s (%d) — %s, %s, elements=%d",
                arch.archetype_id, arch.construction_year,
                wall_s, roof_s, len(arch.construction_set.elements),
            )

        if self.total_skipped:
            logger.info("  Total skipped: %d (see DEBUG for details)", self.total_skipped)
            for stage, skips in self.stage_skipped.items():
                for name, reason in skips:
                    logger.debug("    [%s] %s: %s", stage, name, reason)

        logger.info("  Elapsed: %.1fs", self.elapsed_seconds)
        logger.info("─────────────────────────────────────────────────")


def run_build_baseline(
    excel_path: Path,
    opaque_json_path: Path,
    *,
    skip_api: bool = False,
    api_resources: list[dict] | None = None,
) -> PipelineResult:
    """Load, validate, and construct baseline BuildingArchetype instances.

    Parameters
    ----------
    excel_path : Path to Material_Database.xlsx
    opaque_json_path : Path to opaque_material.json
    skip_api : If True, skip Boverket API call (requires api_resources)
    api_resources : Pre-fetched API resources (avoids network call)

    Returns
    -------
    PipelineResult with archetypes and structured diagnostics.
    """
    t0 = time.monotonic()

    # Fetch Boverket API data
    if api_resources is not None:
        resources = api_resources
    elif skip_api:
        raise ValueError("skip_api=True but no api_resources provided")
    else:
        resources = fetch_all_materials()
    resource_lookup = build_resource_lookup(resources)

    counts: dict[str, int] = {}
    skipped: dict[str, list[tuple[str, str]]] = {}

    # Stage 1: Materials
    materials, mat_skip = assemble_materials(excel_path, opaque_json_path, resource_lookup)
    mat_lookup = {m.name: m for m in materials}
    counts["Materials"] = len(materials)
    skipped["Materials"] = mat_skip

    # Stage 2: Layers
    layers, lay_skip = assemble_layers(excel_path, mat_lookup)
    layer_lookup = {l.layer_code: l for l in layers}
    counts["Layers"] = len(layers)
    skipped["Layers"] = lay_skip

    # Stage 3: Components
    components, comp_skip = assemble_components(excel_path, layer_lookup)
    comp_lookup = {c.name: c for c in components}
    counts["Components"] = len(components)
    skipped["Components"] = comp_skip

    # Stage 4: Elements (includes thermal validation)
    elements, elem_skip = assemble_elements(excel_path, comp_lookup)
    elem_lookup = {e.name: e for e in elements}
    counts["Elements"] = len(elements)
    skipped["Elements"] = elem_skip

    # Stage 5: Buildings
    archetypes, bldg_skip = assemble_buildings(excel_path, elem_lookup)
    counts["Buildings"] = len(archetypes)
    skipped["Buildings"] = bldg_skip

    result = PipelineResult(
        archetypes=archetypes,
        stage_counts=counts,
        stage_skipped=skipped,
        elapsed_seconds=time.monotonic() - t0,
    )
    result.log_summary()

    return result
