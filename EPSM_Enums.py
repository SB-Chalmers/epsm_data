from enum import Enum
from dataclasses import dataclass

# Roughness enum for material surface texture
class Roughness(Enum):
    SMOOTH = "Smooth"
    MEDIUM_SMOOTH = "MediumSmooth"
    MEDIUM_ROUGH = "MediumRough"
    ROUGH = "Rough"
    VERY_ROUGH = "VeryRough"

# Brands Shearing Layers 
class ShearingLayer(Enum):
    Skin = "Skin"
    Structure = "Structure"
    Services = "Services"
    Space = "Space"
    Stuff = "Stuff"
