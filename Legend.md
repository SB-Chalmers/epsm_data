# 5/11 Progress Notes

## Summary
Started building up the **Material** dataclasses and **Layer** as well as enums that might come in use. Examples of instances are at the bottom of each file. Current Questions at the top. 

### Material
Currently matches the properties of the `.json` files in `/External database` (excluding **Thickness**) and including embodied Carbon in case we want a carbon count of some sort on this level. Has a parent class (Material) and two subclasses (Opaque and Translucent) with all of the common properties in the Material class.

### Layer
Currently contains:
- **Material**
- **Thickness**
- **R-Value** - Is calculated (incorrectly?) and not necessary to list, see example

### Component
- **Shearing Layer**
- **RSC**
- **U-value**

Element and Construction Set are empty

order is Material --> Layer --> Component -->Element --> Construction