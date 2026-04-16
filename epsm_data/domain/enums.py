"""Domain enums placeholder.

Expected contents:
- BuildingElement - Y
- ShearingLayer - Y
- Roughness - Y
- RenovationMeasureType
- ComponentState
"""

from enum import Enum
class Roughness(Enum):
    SMOOTH = "Smooth"
    MEDIUM_SMOOTH = "MediumSmooth"
    MEDIUM_ROUGH = "MediumRough"
    ROUGH = "Rough"
    VERY_ROUGH = "VeryRough" 

class BuildingElement(Enum): 
    ROOF = "ROOF"
    TOP_FLOOR = "TOP_FLOOR"
    INTERMEDIATE_FLOOR = "INTERMEDIATE_FLOOR"
    GROUND_FLOOR = "GROUND_FLOOR"
    BASEMENT_FLOOR = "BASEMENT_FLOOR"
    EXT_WALL = "EXT_WALL"
    EXT_WALL_LOW = "EXT_WALL_LOW"
    EXT_WALL_MEDIUM = "EXT_WALL_MEDIUM"
    EXT_WALL_HIGH = "EXT_WALL_HIGH"
    BASEMENT_WALL = "BASEMENT_WALL"
    INT_WALL_LOADBEARING = "INT_WALL_LOADBEARING"
    INT_WALL_NONLOADBEARING = "INT_WALL_NONLOADBEARING"
    WINDOW = "WINDOW"

    @classmethod
    def from_name(cls, name: str) -> "BuildingElement | None":
        name_upper = name.strip().upper()
        for member in sorted(cls, key=lambda m: len(m.value), reverse=True):
            if member.value == name_upper:
                return member
        return None

class ShearingLayer(Enum):
    Skin = "Skin"
    Structure = "Structure"
    Services = "Services"
    Space = "Space"
    Stuff = "Stuff"
