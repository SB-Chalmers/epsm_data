"""I/O adapters — Excel and JSON readers, plus domain assemblers."""

from .assembler import (
    assemble_buildings,
    assemble_components,
    assemble_elements,
    assemble_layers,
    assemble_materials,
)
from .dto import (
    BuildingRow,
    ComponentLayerRef,
    ComponentRow,
    ElementRow,
    LayerMaterialSlot,
    LayerRow,
    MaterialRow,
    OpaqueMaterialProps,
    ReadResult,
    WindowGasProps,
    WindowGlazingProps,
)
from .excel_reader import (
    read_building_sheet,
    read_component_sheet,
    read_element_sheet,
    read_layer_sheet,
    read_material_sheet,
)
from .json_reader import read_opaque_material_json, read_window_material_json

__all__ = [
    # Assemblers
    "assemble_buildings",
    "assemble_components",
    "assemble_elements",
    "assemble_layers",
    "assemble_materials",
    # DTOs
    "BuildingRow",
    "ComponentLayerRef",
    "ComponentRow",
    "ElementRow",
    "LayerMaterialSlot",
    "LayerRow",
    "MaterialRow",
    "OpaqueMaterialProps",
    "ReadResult",
    "WindowGasProps",
    "WindowGlazingProps",
    # Excel readers
    "read_building_sheet",
    "read_component_sheet",
    "read_element_sheet",
    "read_layer_sheet",
    "read_material_sheet",
    # JSON readers
    "read_opaque_material_json",
    "read_window_material_json",
]
