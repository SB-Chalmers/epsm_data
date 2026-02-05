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
Built a Write to Excel workflow that builds a template `.xlsx` file. At the moment uses the same dataclasses (with some extensions) as in `Materials.py` building **BASE_FIELDS**, **OPAQUE_SPECIFIC_FIELDS** and **WINDOW_SPECIFIC_FIELDS**.

### To_Excel.py

Carbon count (currently 1 data point in `Materials.py`) is separated in ***A1-A3***, ***A4*** and ***A5*** impact and units for these are separated.
***Density*** has also been separated in two, where ***value*** is one and ***unit*** is one. This needs to be confirmed and updated/coordinated with `Materials.py`.

### Moving Forward

Planning on developing the same workflow for ***Layer*** and ***Component*** after confirmation.

order is Material --> Layer --> Component -->Element --> Construction

# 14/11 2025 Progress Notes (Djamila)
### EPSM_Enums
- embodied carbon class
    - Needs unit properties embedded

### Material
- generated ID in parent class 
- EnergyMaterial as default
    - ID from honeybee and boverket should be added in

### Layers
- Changed R-calculation for a weighted value
- plot
    - plot needs to properly visualise the Resistance

### Component
- Year Installed (Optional)

### Element
- U value
- Components + shearing layers

# 22/1 2026 Progress Notes (Djamila)

### EPSM_Enums
- Added MediumSmooth
- Units still need to be handled

### Material
- Needs tests added to the class to ensure the ranges extracted from ExtractExcel.py and so on make sense

### Layers
- plot needs to properly visualise the Resistance
- Tests here as well

### Component
- Year Installed (Optional)

### Element
- U value
- Components + shearing layers

## Extraction
Currently solely Opaque_Materials are extracted if both IDs are present. First iteration Extract.py only takes given pairs and will be removed eventually, ExtractExcel.py is the most current and also needs test/validations

diagrams can be be added where they make sense

Formatting over the entire script needs overlooking

# 22/1 2026 Progress Notes 

### EPSM_Enums
- Units still need to be handled

### Material
- Needs tests added to the class to ensure the ranges extracted from ExtractExcel.py and so on make sense

### Layers
- plot needs to properly visualise the Resistance
- thickness test for composite materials, (do all Materials have the same thickness?)
- Need to test if it flags correctly with one area fraction filled in (for composite materials)
- check wether the resistance is correct
- clean up the output log (lists everything clearly not one clump)

### Component
- Year Installed (Optional)

### Element
- U value
- Components + shearing layers

## Extraction
- Currently solely Opaque_Materials are extracted if both IDs are present. 
- First iteration Extract.py only takes given pairs and will be removed eventually, 
- ExtractLayers.py is the most current and extracts both materials and layers, for the material the class needs to be implemented properly
- Duplication logic in ExtractLayers for Layer handling needs a second look.

## Overall
- diagrams can be be added where they make sense in the classes
- Formatting over the entire script needs overlooking
- Workbook + Explanation of code
- Pytest set up
- Check for redundancies (uneccessary code duplication and so on)
- Archetype property for the layer and component

# 02/05 2026 Progress Notes 
Complete classes:

EmbodiedCarbon
Materials
Layers
Components
Element

ExtractAll outputs three jsons: Material (w embodied carbon), layers, component
Currently ExtractElement handles element .json (but does so through the component .json)

Also for every level BUT Layers, R-value is calculated by assuming the materials are in a series

Needs:
- More validation check as it for now mostly ensures the number properties are above zero
- Updated read me w sources
- Updated legend (most is mentioned here for now)
- Embodied Carbon class follows the other classes structure
- Remove redundant Extract files (and maybe rename them) but commited for now to keep the history

### EPSM_Enums
- Units still need to be handled

### Embodied Carbon 
- Separated out
- Needs a consistency check of style, as it may be old

### Material
- Could do with more tests

### Layers
- plot needs to properly visualise the Resistance
- thickness test for composite materials, (do all Materials have the same thickness?)
- Need to test if it flags correctly with one area fraction filled in (for composite materials)

### Component
- Ensure all wanted properties are included

### Element
- Needs more validation tests

## Extraction
- Currently solely Opaque_Materials are extracted if both IDs are present. 
- First iteration Extract.py only takes given pairs and will be removed eventually, 
- ExtractLayers.py is the most current and extracts both materials and layers, for the material the class needs to be implemented properly
- Duplication logic in ExtractLayers for Layer handling needs a second look.

- One for elements was added, however due to lacking an excel sheet with info its currently based off of the component names and may not produce correct Elements
- Utilizes a temporary Element class that can read dictionaries. 

## Overall
- diagrams can be be added where they make sense in the classes
- Workbook + Explanation of code
- Pytest set up
- Check for redundancies (uneccessary code duplication and so on)
- Read me needs sources and general explanation

