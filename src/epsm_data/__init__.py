"""Swedish parametric archetypes and retained material-layer construction APIs.

Imports perform no dataset loading, network calls, or database operations.
"""

from ._version import __version__
from .catalogue import Catalogue, Cost, ParameterDefinition, RenovationCatalogue, RenovationMeasure
from .domain import (
    Archetype,
    BuildingArchetype,
    BuildingElement,
    Component,
    ConstructionSet,
    Element,
    EmbodiedCarbon,
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
from .serialization import (
    archetype_from_dict,
    archetype_to_dict,
    construction_set_from_dict,
    construction_set_to_dict,
)
from .usecases.build_archetype import build_archetype
from .usecases.export_outputs import (
    export_construction_sets,
    export_consumption_contracts,
    export_json,
)

_PARAMETRIC_EXPORTS = {
    "ArchetypeKey",
    "ArchetypeSlot",
    "EffectiveConstructionSet",
    "EffectiveProperty",
    "ParametricCatalogue",
    "load_parametric_catalogue",
}
_LAYERED_EXPORTS = {"CalibratedArchetype", "load_calibrated_archetype"}
_DETAILED_EXPORTS = {"DetailedCatalogue", "load_detailed_catalogue"}
_SCHOOL_EXPORTS = {"SchoolReference", "load_school_reference"}
_OFFICE_EXPORTS = {"OfficeReference", "load_office_reference"}
_NOMINAL_EXPORTS = {"export_nominal_constructions", "validate_nominal_handover", "validate_native_handover"}
_RENOVATION_EXPORTS = {
    "load_renovation_package", "honeybee_material_dict", "instantiate_renovation_honeybee_materials",
}


def __getattr__(name):
    # Lazy imports also permit python -m epsm_data.parametric without runpy warnings.
    if name == "resolve_building_archetype":
        from .application import resolve_building_archetype

        return resolve_building_archetype
    if name in _PARAMETRIC_EXPORTS:
        from . import parametric

        return getattr(parametric, name)
    if name in _LAYERED_EXPORTS:
        from . import layered

        return getattr(layered, name)
    if name in _RENOVATION_EXPORTS:
        from . import renovation

        return getattr(renovation, name)
    if name in _DETAILED_EXPORTS:
        from . import detailed

        return getattr(detailed, name)
    if name in _SCHOOL_EXPORTS:
        from . import school

        return getattr(school, name)
    if name in _OFFICE_EXPORTS:
        from . import office

        return getattr(office, name)
    if name in _NOMINAL_EXPORTS:
        from . import nominal

        return getattr(nominal, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "available_operating_profiles", "select_operating_profile", "select_dhw_profile",
    "OperatingProfile", "HVACTemplate", "load_operating_profile", "load_standard_record", "load_generic_other_template",
    "Catalogue",
    "reference_construction_set",
    "ConstructionOperation", "SystemOperation", "reference_hvac_template",
    "Archetype", "Material", "EnvironmentalFactor",
    "construction_set_from_dict", "construction_set_to_dict",
    "resolve_building_archetype",
    "__version__",
    "ArchetypeKey",
    "ArchetypeSlot",
    "EffectiveConstructionSet",
    "EffectiveProperty",
    "ParametricCatalogue",
    "load_parametric_catalogue",
    "CalibratedArchetype",
    "load_calibrated_archetype",
    "DetailedCatalogue",
    "load_detailed_catalogue",
    "SchoolReference",
    "load_school_reference",
    "OfficeReference",
    "load_office_reference",
    "export_nominal_constructions",
    "validate_native_handover",
    "validate_nominal_handover",
    "load_renovation_package",
    "honeybee_material_dict",
    "instantiate_renovation_honeybee_materials",
    "Cost",
    "ParameterDefinition",
    "RenovationCatalogue",
    "RenovationMeasure",
    "BuildingArchetype",
    "BuildingElement",
    "Component",
    "ConstructionSet",
    "Element",
    "EmbodiedCarbon",
    "Layer",
    "LayerMaterial",
    "LayerSlot",
    "OpaqueMaterial",
    "RenovationEvent",
    "Roughness",
    "ShearingLayer",
    "WindowElement",
    "WindowMaterial",
    "build_construction_set",
    "build_archetype",
    "archetype_to_dict",
    "archetype_from_dict",
    "export_construction_sets",
    "export_consumption_contracts",
    "export_json",
    "resolve_building_archetype",
]
