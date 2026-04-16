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
from epsm_data.domain.enums import BuildingElement
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
            n_elem = len(arch.construction_set.elements)
            logger.info(
                "    %s (%d) — %d elements",
                arch.archetype_id, arch.construction_year, n_elem,
            )
            self._log_u_values(arch)

        if self.total_skipped:
            logger.info("  Total skipped: %d (see DEBUG for details)", self.total_skipped)
            for stage, skips in self.stage_skipped.items():
                for name, reason in skips:
                    logger.debug("    [%s] %s: %s", stage, name, reason)

        logger.info("  Elapsed: %.1fs", self.elapsed_seconds)
        logger.info("─────────────────────────────────────────────────")

    @staticmethod
    def _log_u_values(arch: BuildingArchetype) -> None:
        elements = arch.construction_set.elements
        if not elements:
            logger.info("      (no U-values)")
            return

        ext_walls: list[tuple[str, float]] = []
        int_walls: list[tuple[str, float]] = []
        others: list[tuple[str, float]] = []

        for role, elem in elements.items():
            if role.is_ext_wall:
                ext_walls.append((role.value, elem.u_value))
            elif role.is_int_wall:
                int_walls.append((role.value, elem.u_value))
            else:
                others.append((role.value, elem.u_value))

        # Collect all leaf names for column alignment
        all_names = (
            [n for n, _ in others]
            + ["EXT_WALL"]
            + [n for n, _ in ext_walls]
            + ["INT_WALL"]
            + [n for n, _ in int_walls]
        )
        pad = max(len(n) for n in all_names) if all_names else 0

        for name, u in sorted(others):
            logger.info("      %-*s  %.3f W/(m\u00b2\u00b7K)", pad, name, u)

        if ext_walls:
            avg = sum(v for _, v in ext_walls) / len(ext_walls)
            logger.info("      %-*s  %.3f W/(m\u00b2\u00b7K)", pad, "EXT_WALL", avg)
            if len(ext_walls) > 1:
                for name, u in sorted(ext_walls):
                    logger.info("        %-*s  %.3f", pad, name, u)

        if int_walls:
            avg = sum(v for _, v in int_walls) / len(int_walls)
            logger.info("      %-*s  %.3f W/(m\u00b2\u00b7K)", pad, "INT_WALL", avg)
            if len(int_walls) > 1:
                for name, u in sorted(int_walls):
                    logger.info("        %-*s  %.3f", pad, name, u)


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

    return result
