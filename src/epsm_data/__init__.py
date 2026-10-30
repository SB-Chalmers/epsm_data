"""Swedish LoD2 building archetypes and the construction, operation and source data behind them.

Subpackages, by job:

- ``domain``: the shared construction classes (materials to archetypes) that Core builds on;
- ``catalogue``: the archetype catalogue, authoring, exchange and Core handover;
- ``profiles`` and ``templates``: operating profiles; ventilation and facade templates;
- ``renovation``: the renovation catalogue, executable measures and the changes they make;
- ``contract``: names shared with Core and LCA (quantity drivers, carriers, end uses);
- ``sanity``: read-only screens of the catalogue;
- ``sources``: pinned material and carbon source records;
- ``climate_zones``, ``carbon`` and ``plotting``: single-purpose modules.

Imports perform no dataset loading, network calls or database operations.
"""

import logging as _stdlib_logging
import sys as _sys

from . import _compat
from ._version import __version__
from .catalogue import (
    ArchetypeKey,
    ArchetypeSlot,
    Catalogue,
    archetype_from_dict,
    archetype_to_dict,
    build_archetype,
    construction_set_from_dict,
    construction_set_to_dict,
    export_nominal_constructions,
    reference_construction_set,
    reference_hvac_template,
    validate_nominal_handover,
)
from .climate_zones import (
    AmbiguousClimateZoneError,
    build_climate_zone_boundaries,
    climate_zone_for_building,
    climate_zone_for_county,
    climate_zone_for_point,
)
from .contract import Carrier, EndUse, QuantityDriver, boundary_name
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
from .profiles import (
    HVACTemplate,
    OperatingProfile,
    available_operating_profiles,
    load_generic_other_template,
    load_operating_profile,
    load_standard_record,
    select_dhw_profile,
    select_epc_comparison_terms,
    select_operating_profile,
)
from .renovation import (
    MEASURE_TYPES,
    PAYLOADS,
    Airtightness,
    AirtightnessOperation,
    ConstructionOperation,
    CostEstimate,
    CostItem,
    DHWOperation,
    DHWReduction,
    LayerAddition,
    ParameterDefinition,
    Payload,
    Product,
    PVArray,
    PVOperation,
    RenovationCandidate,
    RenovationCatalogue,
    RenovationMeasure,
    SystemOperation,
    SystemSwap,
    VentilationLayout,
    WindowSwap,
)
from .sanity import check_catalogue, load_sanity_fixture
from .sources import SourceCache
from .templates import (
    facade_assumptions,
    heating_delivery_template,
    ventilation_template_id,
    ventilation_templates,
)

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
    "AirtightnessOperation",
    "DHWOperation",
    "PVOperation",
    "PVArray",
    "PAYLOADS",
    "Payload",
    "LayerAddition",
    "WindowSwap",
    "SystemSwap",
    "DHWReduction",
    "Airtightness",
    "Carrier",
    "EndUse",
    "QuantityDriver",
    "boundary_name",
    "RenovationCatalogue",
    "RenovationMeasure",
    "RenovationEvent",
    "CostEstimate",
    "CostItem",
    "MEASURE_TYPES",
    "Product",
    "RenovationCandidate",
    "VentilationLayout",
    "ParameterDefinition",
    "OperatingProfile",
    "HVACTemplate",
    "available_operating_profiles",
    "load_generic_other_template",
    "load_operating_profile",
    "load_standard_record",
    "select_dhw_profile",
    "select_epc_comparison_terms",
    "select_operating_profile",
    "reference_construction_set",
    "reference_hvac_template",
    "export_nominal_constructions",
    "validate_nominal_handover",
    "facade_assumptions",
    "heating_delivery_template",
    "ventilation_template_id",
    "ventilation_templates",
]

_compat.register(_sys.modules[__name__])

# A library emits no output until its host selects handlers.
_stdlib_logging.getLogger("epsm_data").addHandler(_stdlib_logging.NullHandler())
