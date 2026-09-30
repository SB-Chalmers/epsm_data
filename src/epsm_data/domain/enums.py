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

    @classmethod
    def from_name(cls, name: str) -> BuildingElement | None:
        """Match by value, longest-first to avoid partial hits."""
        upper = name.strip().upper()
        for member in sorted(cls, key=lambda m: len(m.value), reverse=True):
            if member.value == upper:
                return member
        return None

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

    # Ordered from outermost to innermost (useful for sorting).
    @classmethod
    def sort_order(cls) -> list[ShearingLayer]:
        """Return the historical outside-to-inside grouping order.

        Returns
        -------
        list of ShearingLayer
            Skin, Space, Structure, Services, Stuff. Source pipelines use this
            historical convention; explicit builder recipes preserve caller order.
        """
        return [cls.SKIN, cls.SPACE, cls.STRUCTURE, cls.SERVICES, cls.STUFF]


class ComponentState(Enum):
    """Lifecycle state of a component."""

    ORIGINAL = "original"
    RENOVATED = "renovated"
    DEGRADED = "degraded"
    REPLACED = "replaced"


class RenovationMeasureType(Enum):
    """Category of renovation measure."""

    INSULATION_ADD = "insulation_add"
    INSULATION_REPLACE = "insulation_replace"
    WINDOW_REPLACE = "window_replace"
    ROOF_REPLACE = "roof_replace"
    VENTILATION_INSTALL_FTX = "ventilation_install_ftx"
    FACADE_RECLADDING = "facade_recladding"
