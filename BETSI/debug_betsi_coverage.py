"""Check per-building coverage: how many FH buildings have data for each component?"""
import pandas as pd
import glob
from pathlib import Path

BETSI = str(Path(__file__).parent)

def load_fh(pattern):
    matches = glob.glob(f"{BETSI}/{pattern}")
    if not matches:
        return set()
    df = pd.read_csv(matches[0], sep=";", decimal=",", encoding="latin-1")
    fh = df[df["Byggnad"].str.startswith("FH", na=False)]
    return set(fh["Byggnad"].unique())

components = {
    "EXT_WALL (FB49/52)": load_fh("FB49*"),
    "ATTIC_FLOOR (FB56)": load_fh("FB56*"),
    "SLOPED_ROOF (FB62)": load_fh("FB62*"),
    "GROUND_FLOOR (FB33)": load_fh("FB33*"),
    "CRAWL_FLOOR (FB30)": load_fh("FB30*"),
    "BASEMENT_FLOOR (FB40)": load_fh("FB40*"),
    "BASEMENT_WALL (FB47)": load_fh("FB47*"),
    "KNEE_WALL (FB59)": load_fh("FB59*"),
    "WINDOW_E (FB87)": load_fh("FB87*"),
    "WINDOW_N (FB88)": load_fh("FB88*"),
    "WINDOW_S (FB91)": load_fh("FB91*"),
    "WINDOW_V (FB94)": load_fh("FB94*"),
}

# Also get metadata
fa = pd.read_csv(f"{BETSI}/FA.csv", sep=";", decimal=",", encoding="latin-1")
all_fh = set(fa[fa["Hustyp"] == "F"]["Byggnad"].unique())

print(f"Total FH buildings: {len(all_fh)}")
print(f"\n{'Component':<30} {'Buildings':>10} {'%':>6}")
print("-" * 50)
for comp, bldgs in components.items():
    pct = 100 * len(bldgs) / len(all_fh) if all_fh else 0
    print(f"{comp:<30} {len(bldgs):>10} {pct:>5.1f}%")

# Core envelope = EXT_WALL + (ATTIC_FLOOR or SLOPED_ROOF) + (GROUND_FLOOR or BASEMENT_FLOOR or CRAWL_FLOOR) + any window
ext_wall = components["EXT_WALL (FB49/52)"]
roof = components["ATTIC_FLOOR (FB56)"] | components["SLOPED_ROOF (FB62)"]
floor = components["GROUND_FLOOR (FB33)"] | components["CRAWL_FLOOR (FB30)"] | components["BASEMENT_FLOOR (FB40)"]
windows = components["WINDOW_E (FB87)"] | components["WINDOW_N (FB88)"] | components["WINDOW_S (FB91)"] | components["WINDOW_V (FB94)"]

core = ext_wall & roof & floor & windows
print(f"\n{'='*50}")
print(f"Core envelope (wall + roof/attic + floor + window):")
print(f"  EXT_WALL:          {len(ext_wall):>4}")
print(f"  ROOF (attic|slope):{len(roof):>4}")
print(f"  FLOOR (ground|crawl|basement): {len(floor):>4}")
print(f"  WINDOWS (any dir): {len(windows):>4}")
print(f"  ALL FOUR:          {len(core):>4} / {len(all_fh)} ({100*len(core)/len(all_fh):.1f}%)")

# What does a "complete" building look like?
print(f"\n{'='*50}")
print("Sample complete building (FH1001):")
for comp, bldgs in components.items():
    has = "FH1001" in bldgs
    print(f"  {comp:<30} {'YES' if has else 'no'}")

# Check how many layers each component has (i.e. material-level construction detail)
print(f"\n{'='*50}")
print("Layer detail: same material code system as FB52?")
for prefix, label in [("FB56", "ATTIC"), ("FB62", "SLOPED_ROOF"), ("FB33", "GROUND"), 
                       ("FB30", "CRAWL"), ("FB47", "BASEMENT_WALL")]:
    matches = glob.glob(f"{BETSI}/{prefix}*")
    if not matches:
        continue
    df = pd.read_csv(matches[0], sep=";", decimal=",", encoding="latin-1")
    kod_col = [c for c in df.columns if "SelectKod" in c][0]
    fh = df[df["Hustyp"] == "F"]
    codes = fh[kod_col].dropna().astype(int).value_counts().sort_index()
    print(f"\n  {label} ({prefix}) material codes:")
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "_betsi_common", Path(__file__).parent / "_betsi_common.py")
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    MATERIAL_NAMES = _mod.MATERIAL_NAMES
    for code, n in codes.items():
        name = MATERIAL_NAMES.get(code, "?")
        print(f"    {code:>2} {name:<35} n={n}")
