# Energy Database – Working Repository

This repository contains the working structure for the EPSM energy and material database. It includes class definitions, material extraction scripts, and generated JSON files as well as a database used for energy and embodied carbon calculations.

Any class specific checks should be defined within the class however anything cross-field is done externally in the instance loader. 

---

## Class Structure
![WindowMaterial will be implemented so that it can ideally be used interchangeably with OpaqueMaterial](image.png)

# Repository Structure

All scripts are in the NewSchema folder
- Classes.py contains all class defintions and enums.
- DataFetcher.py makes an API request to the klimatdatabas as well as creates EmbodiedCarbon objects based up on the Material_Database.xlsx
- InstanceLoader.py instantiates all other objects (OpaqueMaterial, Layers, Components, Elements, Buildings). Currently WindowMaterial has not been implemented. 
- Exporter.py serialses every object for .json files
- DB.py defines epsm.db
- DBExporter.py
- main.py is the main entrypoint and executes InstanceLoader, Exporter and DBexporter.
- Graph.py defines and loads a graph of the database, it needs to be run separately. 
---

# Class Definitions

The `Classes` folder contains all core classes used in the database.  

Each class defines:

- Properties  
- Validation checks  
- Calculation methods (for calculated properties)  
- Serialization to JSON (to dict method) 

Additional functionality (e.g., diagrams or derived attributes) can be implemented within the relevant class. 


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

---

# JSON Generation

All extraction scripts are located in:

```
output/
```
---



## EnergyPlusConverter.py

Rewrites `opaque_material.json` to match the naming convention used in `Material_Database.xlsx`.
The output is utilised in grasshopper.

---

## Data Sources

`ExtractElements.py` contains U-values sourced from:

TABULA Building Typology Webtool  
https://webtool.building-typology.eu/#bm  

(Charts 1 data)
