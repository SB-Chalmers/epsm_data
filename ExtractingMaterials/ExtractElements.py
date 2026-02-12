# python -m ExtractingMaterials.ExtractElements
import json
import os
from datetime import datetime
from typing import List

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

#U-values according to tabula
# Always referenced charts 1 
# 1960 and earlier: https://webtool.building-typology.eu/#vares
# 1961...1975: https://webtool.building-typology.eu/#vares 
Tabula_CMF = {
  "CMF_1940" : { 
    "roof" : 0.36, #W/(m2K)
    "wall" : 0.58, # W/(m2K)
    "window" : 2.22, # W/(m2K)
    "floor":  0.32 #W/(m2K)
  },
  "CMF_1950" : { 
    "roof" : 0.36, #W/(m2K)
    "wall" : 0.58, # W/(m2K)
    "window" : 2.22, # W/(m2K)
    "floor":  0.32 #W/(m2K)
  },
  "CMF_1960" : {
    "roof" : 0.20, # W/(m2K)	
    "wall" : 0.41, # W/(m2K)	
    "window" : 2.22, # W/(m2K)
    "floor": 0.26 #W/(m2K)
  }
}

# Automatically pick the latest Components_*.json file
components_files = sorted(
    [f for f in os.listdir(OUTPUT_DIR) if f.startswith("Components_") and f.endswith(".json")], 
    reverse=True
)
if not components_files:
    raise FileNotFoundError("No Components_*.json file found in output folder.")

COMPONENTS_JSON = os.path.join(OUTPUT_DIR, components_files[0])

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Element class
class Element:  # Reading everything as dicts (hense a new defintion of Elements here)
    """Represents a construction element consisting of multiple components."""
    DEFAULT_RSI = 0.13
    DEFAULT_RSE = 0.04

    def __init__(self, name: str, archetype: str, components: List[dict]):
        self.name = name
        self.archetype = archetype
        self.components = components
        self.rsi = self.DEFAULT_RSI
        self.rse = self.DEFAULT_RSE

    @property
    def r_value_total(self) -> float:
        total_r = sum(comp.get("r_value_total", 0) for comp in self.components)
        return self.rsi + total_r + self.rse # Assuming The components are all in a series here

    @property
    def u_value_total(self) -> float:
        r_total = self.r_value_total
        return round(1 / r_total, 5) if r_total > 0 else 0

    @property
    def age(self) -> int | None:
        ages = [comp.get("age") for comp in self.components if comp.get("age") is not None]
        return max(ages) if ages else None

    def validate(self) -> list:
        """Return a list of warnings for this element."""
        warnings = []
        if not self.components:
            warnings.append("Element has no components")
        if any("layers" not in c or not c["layers"] for c in self.components):
            warnings.append("One or more components missing layers")
        return warnings
    
    def check_tabula_threshold(self, tabula_data: dict) -> tuple[str | None, str | None, float | None]:
        """
        Compare calculated U-value against Tabula threshold.
        Returns: (warning_message, matched_type, tabula_u_value)
        """
        name_upper = self.name.upper()
        
        # Find matching archetype in name
        matched_archetype = None
        for archetype_key in tabula_data.keys():
            if archetype_key.upper() in name_upper:
                matched_archetype = archetype_key
                break
        
        if matched_archetype is None:
            return ("CANT FIND ARCHETYPE", None, None)
        
        # Find matching element type in name
        element_types = ["roof", "wall", "window", "floor"]
        matched_type = None
        
        for elem_type in element_types:
            if elem_type.upper() in name_upper:
                matched_type = elem_type
                break
        
        if matched_type is None:
            return ("CANT FIND TABULA U-VALUE", None, None)
        
        # Get Tabula U-value
        tabula_u_value = tabula_data[matched_archetype][matched_type]
        calculated_u_value = self.u_value_total
        
        # Compare values
        if calculated_u_value > tabula_u_value:
            warning = f"{matched_archetype} {matched_type}:{tabula_u_value} -- {calculated_u_value:.5}"
            return (warning, matched_type, tabula_u_value)
           
        
        return (None, matched_type, tabula_u_value)

    def to_dict(self):
        return {
            "name": self.name,
            "archetype": self.archetype,
            "rsi": self.rsi,
            "rse": self.rse,
            "r_value_total": self.r_value_total,
            "u_value_total": self.u_value_total,
            "age": self.age,
            "components": self.components
        }

# Load components JSON
with open(COMPONENTS_JSON, "r", encoding="utf-8") as f:
    components_data = json.load(f)

# Validate archetypes against Tabula data
unique_archetypes = set(comp.get("archetype") for comp in components_data.values() if comp.get("archetype"))
missing_tabula = unique_archetypes - set(Tabula_CMF.keys())

if missing_tabula:
    print(f"\033[93m[WARNING]\033[0m Archetypes missing from Tabula data: {missing_tabula}")
    print(f"Available Tabula archetypes: {set(Tabula_CMF.keys())}\n")

# Group components into elements based on base name
elements_dict = {}
skipped_elements = []

for comp_name, comp_dict in components_data.items():
    # Base name = everything before last two parts (e.g., "_SKIN_1")
    parts = comp_name.rsplit("_", 2)
    if len(parts) < 3:
        skipped_elements.append((comp_name, "Cannot parse component name for base name"))
        continue
    base_name = parts[0]

    if base_name not in elements_dict:
        elements_dict[base_name] = []
    elements_dict[base_name].append(comp_dict)

# Create Element objects, validate components
elements = []
SHEARING_ORDER = ["Rsi", "Skin", "Space", "Structure", "Rse"]
EXPECTED_LAYERS = ["Skin", "Space", "Structure"]
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

total_warnings = 0  # Track all warnings
tabula_warnings = 0  # Track Tabula threshold warnings
warnings_details = []  # Store warning details for export

for base_name, comps in elements_dict.items():
    # Sort components by shearing_layer
    comps_sorted = sorted(
        comps,
        key=lambda x: SHEARING_ORDER.index(
            x["layers"][0]["shearing_layer"]
        ) if x.get("layers") and x["layers"][0]["shearing_layer"] in SHEARING_ORDER else 999
    )

    # Check for missing shearing layers
    present_layers = [
        comp["layers"][0]["shearing_layer"] if comp.get("layers") and comp["layers"][0].get("shearing_layer") else None
        for comp in comps_sorted
    ]
    missing_layers = [layer for layer in EXPECTED_LAYERS if layer not in present_layers]
    if missing_layers:
        print(f"{YELLOW}[ELEMENT WARNING]{RESET} {base_name} missing shearing layers: {', '.join(missing_layers)}")
        total_warnings += 1

    archetype = comps_sorted[0].get("archetype", "Unknown")
    element = Element(name=base_name, archetype=archetype, components=comps_sorted)

    # Validate element
    warnings = element.validate()
    if warnings:
        for w in warnings:
            print(f"{YELLOW}[ELEMENT WARNING]{RESET} {base_name}: {w}")
        total_warnings += len(warnings)

    # Check Tabula U-value threshold
    tabula_warning, matched_type, tabula_u_value = element.check_tabula_threshold(Tabula_CMF)
    if tabula_warning:
        print(f"{RED}[TABULA WARNING]{RESET} {base_name}: {tabula_warning}")
        tabula_warnings += 1
        total_warnings += 1
        
        # Store warning details for export
        warnings_details.append({
            "element": element.name,
            "archetype": element.archetype,
            "warning": tabula_warning,
            "calculated_u_value": element.u_value_total,
            "tabula_u_value": tabula_u_value,
            "r_value_total": element.r_value_total
        })

    elements.append(element)

# Export elements JSON
today = datetime.today().strftime("%Y-%m-%d")
elements_file = os.path.join(OUTPUT_DIR, f"Elements_{today}.json")

with open(elements_file, "w", encoding="utf-8") as f:
    json.dump({e.name: e.to_dict() for e in elements}, f, indent=4)

# Export warnings report
warnings_file = os.path.join(OUTPUT_DIR, f"Warnings_{today}.json")
warnings_report = {
    "report_date": today,
    "total_elements": len(elements),
    "total_warnings": total_warnings,
    "tabula_warnings": tabula_warnings,
    "missing_tabula_archetypes": list(missing_tabula) if missing_tabula else [],
    "available_tabula_archetypes": list(Tabula_CMF.keys()),
    "details": warnings_details
}

with open(warnings_file, "w", encoding="utf-8") as f:
    json.dump(warnings_report, f, indent=4)

# Print skipped elements
if skipped_elements:
    print(f"\n{RED}Skipped elements due to parsing issues:{RESET}")
    for name, reason in skipped_elements:
        print(f"- {name}: {reason}")

# Summary
print(f"\nProcessed elements: {len(elements)}")
print(f"Skipped elements: {len(skipped_elements)}")
print(f"Total warnings: {total_warnings}")
print(f"Tabula threshold warnings: {tabula_warnings}")
print(f"Exported elements JSON to: {elements_file}")
print(f"Exported warnings report to: {warnings_file}")
