"""Check all BETSI FB files for layer-by-layer component data (wall, roof, floor, etc.)."""
import pandas as pd
import glob
import os
from pathlib import Path

BETSI = str(Path(__file__).parent)

# Our archetype needs: EXT_WALL, ROOF, GROUND_FLOOR, BASEMENT_WALL, BASEMENT_FLOOR, windows
# BETSI files we know about:
#   FB49/FB52 - Yttervägg (ext wall) ✓
#   FB56 - Vindsbjälklag (attic floor)
#   FB62 - Snedtak (sloped roof)
#   FB30 - Kryp Bjälklag (crawl space floor)
#   FB33 - Kryp PPM (crawl space ground)
#   FB40 - Källare (basement)
#   FB47 - Källarvägg (basement wall)
#   FB87-94 - Fönster (windows by orientation)

files_to_check = {
    "FB56 Vindsbjl": "ATTIC_FLOOR / ROOF",
    "FB62 Snedtak": "SLOPED_ROOF",
    "FB30 Kryp Bjl": "CRAWL_SPACE_FLOOR",
    "FB33 Kryp PPM": "CRAWL_SPACE_GROUND",
    "FB40 K": "BASEMENT",
    "FB47 K": "BASEMENT_WALL",
    "FB87 F": "WINDOW_EAST",
    "FB88 F": "WINDOW_NORTH",
    "FB91 F": "WINDOW_SOUTH",
    "FB94 F": "WINDOW_WEST",
    "FB59 St": "KNEE_WALL",
}

print("=" * 80)
print("BETSI COMPONENT DATA COVERAGE FOR ARCHETYPE CONSTRUCTION")
print("=" * 80)

for prefix, component in files_to_check.items():
    matches = glob.glob(f"{BETSI}/{prefix}*")
    if not matches:
        print(f"\n--- {component}: NO FILE FOUND for {prefix}* ---")
        continue
    fpath = matches[0]
    fname = os.path.basename(fpath)
    try:
        df = pd.read_csv(fpath, sep=";", decimal=",", encoding="latin-1")
        fh = df[df["Byggnad"].str.startswith("FH", na=False)] if "Byggnad" in df.columns else df
        
        print(f"\n{'='*60}")
        print(f"{component}: {fname}")
        print(f"  Rows: {len(df)} total, {len(fh)} FH")
        print(f"  Columns ({len(df.columns)}):")
        
        # Categorize columns
        lambda_cols = [c for c in df.columns if "lambda" in c.lower() or "Lambda" in c]
        thickness_cols = [c for c in df.columns if "tjocklek" in c.lower() or "thick" in c.lower()]
        r_cols = [c for c in df.columns if c.lower().startswith("r ") or "värmemotstånd" in c.lower() or c.endswith("R")]
        u_cols = [c for c in df.columns if "u-värde" in c.lower() or "u_value" in c.lower()]
        material_cols = [c for c in df.columns if "material" in c.lower() or "kod" in c.lower() or "select" in c.lower()]
        area_cols = [c for c in df.columns if "area" in c.lower() or "yta" in c.lower()]
        
        if lambda_cols:
            print(f"  Lambda cols: {lambda_cols}")
        if thickness_cols:
            print(f"  Thickness cols: {thickness_cols}")
        if r_cols:
            print(f"  R-value cols: {r_cols}")
        if u_cols:
            print(f"  U-value cols: {u_cols}")
        if material_cols:
            print(f"  Material cols: {material_cols}")
        if area_cols:
            print(f"  Area cols: {area_cols}")
        
        # Check for layer-by-layer data (multiple rows per building = layers)
        if "Byggnad" in fh.columns:
            rows_per_bldg = fh.groupby("Byggnad").size()
            print(f"  Rows/building: min={rows_per_bldg.min()}, median={rows_per_bldg.median():.0f}, max={rows_per_bldg.max()}")
        
        # Show all columns for context
        print(f"  All columns: {df.columns.tolist()}")
        
        # Show sample FH row
        if len(fh) > 0:
            print(f"  Sample FH row:")
            sample = fh.iloc[0]
            for col in df.columns:
                val = sample[col]
                if pd.notna(val) and str(val).strip():
                    print(f"    {col}: {val}")
    except Exception as e:
        print(f"\n--- {component}: ERROR reading {fname}: {e} ---")

# Also check FC1/FC2 condition files for component info
print(f"\n{'='*60}")
print("FC1/FC2 CONDITION FILES")
fc_files = glob.glob(f"{BETSI}/FC1*.csv") + glob.glob(f"{BETSI}/FC2*.csv")
for fpath in sorted(fc_files):
    fname = os.path.basename(fpath)
    try:
        df = pd.read_csv(fpath, sep=";", decimal=",", encoding="latin-1")
        fh = df[df["Byggnad"].str.startswith("FH", na=False)] if "Byggnad" in df.columns else pd.DataFrame()
        print(f"  {fname}: {len(fh)} FH rows, {len(df.columns)} cols")
    except:
        print(f"  {fname}: error reading")
