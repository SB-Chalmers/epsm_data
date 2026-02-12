# Energy Database – Working Repository

This repository contains the working structure for the EPSM energy and material database. It includes class definitions, material extraction scripts, and generated JSON files used for energy and embodied carbon calculations.

---

# Repository Structure

```
EPSM DATA
├── ClassDefinitions/
│   ├── Components.py 
│   ├── Elements.py
│   ├── EmbodiedCarbon.py
│   ├── Layers.py
│   └── Materials.py
│
├── ExtractingMaterials/
│   ├── output/
│   │   ├── generated .json
│   ├── ExtractAll.py
│   ├── ExtractElements.py
│   └── ExtractEnergyPlus.py 
│
├── Boverket.json
├── EPSM_Enums.py
├── Legend.md
├── opaque_material.json
└── Material_Database.xlsx
```

---

# Class Definitions

The `ClassDefinitions` folder contains all core classes used in the database.  

Each class defines:

- Properties  
- Validation checks  
- Calculation methods  
- Serialization to JSON  

Additional functionality (e.g., diagrams or derived attributes) can be implemented within the relevant class.

**Note:** `Elements.py` is not yet fully integrated.

---

## Calculation Sources

The `Layers` class calculates R-values using:

- The Lambda (λ) method  
- The U-value method  

These methods are based on:

- Persson, B. P.-Å. (2018). *Tillämpad byggnadsfysik*. Studentlitteratur. Sections 8.1 & 9.2.3.  
- Chalmers lecture material https://chalmers.instructure.com/courses/9012/files/345841?module_item_id=57479 

---

## Boverket Data

`Boverket.json` is retrieved from the Boverket Climate Database API:

https://api-portal.boverket.se/reference#api=klimatdatabas

If a newer version is released, the file can be replaced with the updated API export.

---

# Extraction and JSON Generation

All extraction scripts are located in:

```
ExtractingMaterials/
```

## ExtractAll.py

Generates:

- Materials  
- Layers  
- Components  

It uses:

- `Material_Database.xlsx`  
- `Boverket.json`  
- `opaque_material.json`  

The script outputs generated JSON files into the `/output` folder.

If files are generated multiple times on the same day, the previous file will be overwritten unless renamed.

You can choose which files to generate inside the `__main__` block.

---

## ExtractElements.py

Uses:

- `Components_YYYY_MM_DD.json`

to construct element definitions and generate:

- `Elements_YYYY_MM_DD.json`

Ensure Components have been generated before running this script.

---

## ExtractEnergyPlus.py

Rewrites `opaque_material.json` to match the naming convention used in `Material_Database.xlsx`.

The output can be used with Honeybee / EnergyPlus workflows.

---

## Data Sources

`ExtractElements.py` contains U-values sourced from:

TABULA Building Typology Webtool  
https://webtool.building-typology.eu/#bm  

(Charts 1 data)
