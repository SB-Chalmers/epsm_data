from enum import Enum

# Roughness enum for material surface texture
class Roughness(Enum):
    SMOOTH = "Smooth"
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
    