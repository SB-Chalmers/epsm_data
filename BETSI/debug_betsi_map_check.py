"""Cross-reference BETSI material codes against our existing EP material mappings."""
import pandas as pd
import json

# BETSI materials with their lambda values from the data
BETSI_MATERIALS = {
    1: "Mineral wool boards",
    2: "Brick",
    3: "Calcium silicate",
    4: "Leca block",
    5: "Cellular plastic XPS/EPS",
    6: "Mineral wool loose",
    7: "Wood shavings/sawdust",
    8: "Wood",
    9: "Aerated concrete",
    10: "Concrete",
    11: "Cork",
    12: "Glass",
    13: "Steel",
    14: "Lightweight aggregate block",
    15: "Lightweight concrete (cast)",
    16: "Cellular glass/foam glass",
    17: "Polyurethane foam",
    18: "Asphalt board/felt",
    19: "Mineral wool (older)",
    20: "Mineral wool (modern)",
    21: "Air gap",
    22: "Gypsum board",
    23: "Plaster/render",
    24: "Plywood/fibreboard",
    25: "Plastic foil",
    26: "Window",
    27: "Lightweight concrete block",
    28: "Timber frame+insulation",
    29: "Other",
    30: "Insulation board (other)",
}

# Load our existing EP materials
with open("Data/opaque_material.json") as f:
    ep_data = json.load(f)

ep_materials = {}
for name, props in ep_data.items():
    if isinstance(props, dict) and "conductivity" in props:
        ep_materials[name] = props["conductivity"]

# Load our Excel material database to see what we've already mapped
excel_path = "Data/Material_Database.xlsx"
try:
    mat_df = pd.read_excel(excel_path, sheet_name="Opaque_Materials")
    print(f"Excel Opaque_Materials: {len(mat_df)} rows")
    print(f"Columns: {mat_df.columns.tolist()}")
    print()
    
    # Show our existing materials and their EP mappings
    print("=" * 90)
    print("OUR EXISTING MATERIALS vs BETSI CODES")
    print("=" * 90)
    
    for _, row in mat_df.iterrows():
        name = row.get("Material Name", row.get("Name", ""))
        hb_id = row.get("Honeybee Identifier", "")
        k_val = ep_materials.get(hb_id, "?") if pd.notna(hb_id) and hb_id else "unmapped"
        print(f"  {str(name):<40} -> {str(hb_id):<45} (k={k_val})")
except Exception as e:
    print(f"Excel read error: {e}")

# Now try to match
print()
print("=" * 90)
print("BETSI CODE -> OUR MATERIAL MAPPING STATUS")
print("=" * 90)

# Manual mapping based on material names
BETSI_TO_OURS = {
    1: "mineral_wool",          # Mineral wool boards
    2: "brick",                 # Brick
    3: None,                    # Calcium silicate - do we have?
    4: "leca",                  # Leca block
    5: "cellular_plastic",      # Cellular plastic XPS/EPS
    6: "mineral_wool",          # Mineral wool loose (same material, diff form)
    7: "wood_shavings",         # Wood shavings/sawdust
    8: "wood",                  # Wood
    9: "aerated_concrete",      # Aerated concrete
    10: "concrete",             # Concrete
    11: None,                   # Cork
    12: None,                   # Glass
    13: None,                   # Steel
    14: "leca",                 # Lightweight aggregate block (similar to leca?)
    15: "lightweight_concrete", # Lightweight concrete (cast)
    16: None,                   # Cellular glass/foam glass
    17: None,                   # Polyurethane foam
    18: "asphalt_board",        # Asphalt board/felt
    19: "mineral_wool",         # Mineral wool (older)
    20: "mineral_wool",         # Mineral wool (modern)
    21: None,                   # Air gap (not a material)
    22: "gypsum_board",         # Gypsum board
    23: "plaster",              # Plaster/render
    24: "wood_fiber_board",     # Plywood/fibreboard
    25: None,                   # Plastic foil (negligible)
    26: None,                   # Window (not opaque)
    27: "lightweight_concrete", # Lightweight concrete block
    28: None,                   # Timber frame+insulation (composite)
    29: None,                   # Other
    30: None,                   # Insulation board (other)
}

# Check which of our material names actually exist in the Excel
our_names = set()
if 'mat_df' in dir():
    name_col = "Material Name" if "Material Name" in mat_df.columns else mat_df.columns[0]
    our_names = set(mat_df[name_col].dropna().str.strip().str.lower())

mapped = 0
unmapped = 0
not_needed = 0

for code in sorted(BETSI_MATERIALS.keys()):
    betsi_name = BETSI_MATERIALS[code]
    our_match = BETSI_TO_OURS.get(code)
    
    if code in (0, 21, 25, 26, 29, 31, 32, 99):
        status = "SKIP (not a real opaque material)"
        not_needed += 1
    elif our_match:
        # Check if it exists in our Excel
        found = any(our_match.replace("_", " ") in n or our_match in n for n in our_names)
        if found:
            status = f"MAPPED -> {our_match}"
            mapped += 1
        else:
            status = f"LIKELY -> {our_match} (check Excel)"
            mapped += 1  # still counts as conceptually mapped
    else:
        status = "UNMAPPED - needs new material"
        unmapped += 1
    
    print(f"  {code:>2}  {betsi_name:<35} {status}")

print(f"\nSummary: {mapped} mapped, {unmapped} unmapped, {not_needed} skipped")
print(f"Unmapped codes that need new EP materials:")
for code in sorted(BETSI_MATERIALS.keys()):
    if BETSI_TO_OURS.get(code) is None and code not in (0, 21, 25, 26, 29, 31, 32, 99):
        print(f"  {code:>2}  {BETSI_MATERIALS[code]}")
