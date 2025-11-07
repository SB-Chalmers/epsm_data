# 5/11 Progress Notes (Djamila)

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

# 7/11 2025 Progress Notes (Johan)

## Summary
Built a Write to Excel workflow that builds a template .xlsx file. At the moment uses the same dataclasses (with some extensions) as in Materials.py building BASE_FIELDS, OPAQUE_SPECIFIC_FIELDS and WINDOW_SPECIFIC_FIELDS.

### To_Excel.py

Carbon count (currently 1 data point in Materials.py) is separated in ***A1-A3***, ***A4*** and ***A5*** impact and units for these are separated.
***Density*** has also been separated in two, where ***value*** is one and ***unit*** is one. This needs to be confirmed and updated/coordinated with Materials.py.

### Moving Forward

Planning on developing the same workflow for ***Layer*** and ***Component*** after confirmation.

