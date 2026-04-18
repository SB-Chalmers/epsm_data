"""epsm_data — Building archetype library for energy modelling.

This package defines building archetypes: material properties, thermal
performance, renovation measures, and aging behavior.  It is geometry-
and site-agnostic by design.

A downstream library (e.g. pbgenerator) consumes archetypes via the
consumption contract to instantiate geolocated buildings and run full
energy simulations.

Workflow:
    from epsm_data import run_build_baseline, export_json

    archetypes = run_build_baseline(excel_path, json_path)
    export_json(archetypes, output_dir)
"""

from epsm_data.config.logging import setup_logging
from epsm_data.domain import (
    BuildingArchetype,
    BuildingElement,
    Component,
    ComponentState,
    ConstructionSet,
    Element,
    EmbodiedCarbon,
    Layer,
    LayerMaterial,
    OpaqueMaterial,
    RenovationMeasureType,
    Roughness,
    ShearingLayer,
    WindowMaterial,
)
from epsm_data.usecases.build_baseline import PipelineResult, run_build_baseline
from epsm_data.usecases.build_from_spec import build_archetype_from_spec
from epsm_data.usecases.material_search import (
    list_boverket_materials,
    list_honeybee_materials,
    search_boverket_materials,
    search_honeybee_materials,
)
from epsm_data.usecases.export_outputs import (
    export_construction_sets,
    export_consumption_contracts,
    export_json,
)
from epsm_data.reporting.section_drawing import plot_sections

__all__ = [
    # config
    "setup_logging",
    # usecases
    "run_build_baseline",
    "build_archetype_from_spec",
    "PipelineResult",
    "export_json",
    "export_consumption_contracts",
    "export_construction_sets",
    # reporting / visualization
    "plot_sections",
    # material search
    "search_honeybee_materials",
    "list_honeybee_materials",
    "search_boverket_materials",
    "list_boverket_materials",
    # domain — core types
    "BuildingArchetype",
    "ConstructionSet",
    "Element",
    "Component",
    "Layer",
    "LayerMaterial",
    "OpaqueMaterial",
    "WindowMaterial",
    "EmbodiedCarbon",
    # domain — enums
    "BuildingElement",
    "ComponentState",
    "RenovationMeasureType",
    "Roughness",
    "ShearingLayer",
]
