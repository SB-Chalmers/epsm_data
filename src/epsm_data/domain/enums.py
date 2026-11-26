"""Domain enumerations used across the epsm_data library."""

from __future__ import annotations

from enum import Enum


class Roughness(Enum):
    """Material surface texture (EnergyPlus convention)."""

    SMOOTH = "Smooth"
    MEDIUM_SMOOTH = "MediumSmooth"
    MEDIUM_ROUGH = "MediumRough"
    ROUGH = "Rough"
    VERY_ROUGH = "VeryRough"


class BuildingElement(Enum):
    """Role a component/element plays within the building envelope."""

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

    @property
    def is_ext_wall(self) -> bool:
        """True for any exterior wall variant (single or multi)."""
        return self in (
            BuildingElement.EXT_WALL,
            BuildingElement.EXT_WALL_LOW,
            BuildingElement.EXT_WALL_MEDIUM,
            BuildingElement.EXT_WALL_HIGH,
        )

    @property
    def is_int_wall(self) -> bool:
        """True for any interior wall variant."""
        return self in (
            BuildingElement.INT_WALL_LOADBEARING,
            BuildingElement.INT_WALL_NONLOADBEARING,
        )


class ShearingLayer(Enum):
    """Brand's shearing layers of change."""

    SKIN = "Skin"
    STRUCTURE = "Structure"
    SERVICES = "Services"
    SPACE = "Space"
    STUFF = "Stuff"

