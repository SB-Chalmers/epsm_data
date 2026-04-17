"""Count unique materials across all BETSI component files."""
import pandas as pd
import glob
from pathlib import Path

BETSI = str(Path(__file__).parent)
MATERIAL_NAMES = {
    1: "Mineral wool boards", 2: "Brick", 3: "Calcium silicate",
    4: "Leca block", 5: "Cellular plastic XPS/EPS", 6: "Mineral wool loose",
    7: "Wood shavings/sawdust", 8: "Wood", 9: "Aerated concrete",
    10: "Concrete", 11: "Cork", 12: "Glass", 13: "Steel",
    14: "Lightweight aggregate block", 15: "Lightweight concrete (cast)",
    16: "Cellular glass/foam glass", 17: "Polyurethane foam",
    18: "Asphalt board/felt", 19: "Mineral wool (older)",
    20: "Mineral wool (modern)", 21: "Air gap", 22: "Gypsum board",
    23: "Plaster/render", 24: "Plywood/fibreboard", 25: "Plastic foil",
    26: "Window", 27: "Lightweight concrete block",
    28: "Timber frame+insulation", 29: "Other", 30: "Insulation board (other)",
}

files = {
    "FB52 (ext wall)": "FB52*",
    "FB56 (attic)": "FB56*",
    "FB62 (sloped roof)": "FB62*",
    "FB33 (ground floor)": "FB33*",
    "FB30 (crawl floor)": "FB30*",
    "FB47 (basement wall)": "FB47*",
    "FB40 (basement floor)": "FB40*",
    "FB59 (knee wall)": "FB59*",
}

all_codes = set()
code_by_file = {}

for label, pat in files.items():
    matches = glob.glob(f"{BETSI}/{pat}")
    if not matches:
        continue
    df = pd.read_csv(matches[0], sep=";", decimal=",", encoding="latin-1")
    fh = df[df["Hustyp"] == "F"]
    kod_col = [c for c in df.columns if "SelectKod" in c][0]
    codes = set(fh[kod_col].dropna().astype(int).unique())
    all_codes |= codes
    code_by_file[label] = codes

print(f"Unique material codes across all components: {len(all_codes)}")
print()
for code in sorted(all_codes):
    name = MATERIAL_NAMES.get(code, "???")
    where = [l for l, c in code_by_file.items() if code in c]
    print(f"  {code:>2}  {name:<35} used in: {', '.join(where)}")
