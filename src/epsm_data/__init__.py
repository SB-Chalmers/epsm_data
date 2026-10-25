"""Deterministic LoD2 catalogue and linked material-to-archetype authoring.

Imports perform no dataset loading, network calls, or database operations.
"""

import logging as _stdlib_logging

from ._version import __version__
from .catalogue import Catalogue, Cost, ParameterDefinition, RenovationCatalogue, RenovationMeasure
from .classification import ArchetypeKey, ArchetypeSlot
from .climate_zones import (
    AmbiguousClimateZoneError,
    build_climate_zone_boundaries,
    climate_zone_for_building,
    climate_zone_for_county,
    climate_zone_for_point,
)
from .domain import (
    Archetype,
    BuildingArchetype,
    BuildingElement,
    CarbonReference,
    Component,
    ConstructionSet,
    Element,
    EmbodiedCarbon,
    EnvelopePerformance,
    EnvironmentalFactor,
    Layer,
    LayerMaterial,
    LayerSlot,
    Material,
    OpaqueMaterial,
    RenovationEvent,
    Roughness,
    ShearingLayer,
    WindowElement,
    WindowMaterial,
    build_construction_set,
)
from .nominal import export_nominal_constructions, validate_nominal_handover
from .operations import ConstructionOperation, SystemOperation
from .profiles import (
    HVACTemplate,
    OperatingProfile,
    available_operating_profiles,
    load_generic_other_template,
    load_operating_profile,
    load_standard_record,
    select_dhw_profile,
    select_operating_profile,
)
from .reference import reference_construction_set, reference_hvac_template
from .sanity import check_catalogue, load_sanity_fixture
from .serialization import (
    archetype_from_dict,
    archetype_to_dict,
    construction_set_from_dict,
    construction_set_to_dict,
)
from .source_cache import SourceCache
from .usecases.build_archetype import build_archetype

__all__ = [
    "__version__",
    "Catalogue",
    "check_catalogue",
    "load_sanity_fixture",
    "SourceCache",
    "AmbiguousClimateZoneError",
    "build_climate_zone_boundaries",
    "climate_zone_for_building",
    "climate_zone_for_county",
    "climate_zone_for_point",
    "ArchetypeKey",
    "ArchetypeSlot",
    "Archetype",
    "BuildingArchetype",
    "BuildingElement",
    "Component",
    "ConstructionSet",
    "Element",
    "CarbonReference",
    "EmbodiedCarbon",
    "EnvelopePerformance",
    "EnvironmentalFactor",
    "Layer",
    "LayerMaterial",
    "LayerSlot",
    "Material",
    "OpaqueMaterial",
    "Roughness",
    "ShearingLayer",
    "WindowElement",
    "WindowMaterial",
    "build_construction_set",
    "build_archetype",
    "archetype_from_dict",
    "archetype_to_dict",
    "construction_set_from_dict",
    "construction_set_to_dict",
    "ConstructionOperation",
    "SystemOperation",
    "RenovationCatalogue",
    "RenovationMeasure",
    "RenovationEvent",
    "Cost",
    "ParameterDefinition",
    "OperatingProfile",
    "HVACTemplate",
    "available_operating_profiles",
    "load_generic_other_template",
    "load_operating_profile",
    "load_standard_record",
    "select_dhw_profile",
    "select_operating_profile",
    "reference_construction_set",
    "reference_hvac_template",
    "export_nominal_constructions",
    "validate_nominal_handover",
]

# A library emits no output until its host selects handlers.

_stdlib_logging.getLogger("epsm_data").addHandler(_stdlib_logging.NullHandler())
