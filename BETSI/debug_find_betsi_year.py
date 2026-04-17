"""Check all BETSI files for construction year data for FH buildings."""
import pandas as pd
import glob, os
from pathlib import Path

betsi = str(Path(__file__).parent)

# FX.csv specifically
fx = pd.read_csv(f"{betsi}/FX.csv", sep=";", decimal=",", encoding="latin-1")
print("=== FX.csv ===")
print("All columns:", fx.columns.tolist())
fh = fx[fx["Byggnad"].str.startswith("FH", na=False)]
print(f"FH rows: {len(fh)}")
if len(fh) > 0:
    print(fh.head(3).to_string())

print()

# Check Uppräkningstal for ald column
ut_files = glob.glob(f"{betsi}/Uppr*kningstal*.csv")
for f in ut_files:
    df = pd.read_csv(f, sep=";", decimal=",", encoding="latin-1")
    if "ald" in df.columns:
        print(f"\n=== {os.path.basename(f)} - ald column ===")
        print("ald value counts:")
        print(df["ald"].value_counts().sort_index())
        # Is there any FH?
        if "Byggnad" in df.columns:
            fh = df[df["Byggnad"].str.startswith("FH", na=False)]
            print(f"FH rows with ald: {len(fh)}")

# Check FF, FG, FD, FE for year columns
for fn in ["FF.csv", "FG.csv", "FD.csv", "FE.csv"]:
    try:
        df = pd.read_csv(f"{betsi}/{fn}", sep=";", decimal=",", encoding="latin-1")
        fh = df[df["Byggnad"].str.startswith("FH", na=False)]
        yc = [c for c in df.columns if any(x in c.lower() for x in ["år", "ald", "period", "bygg"])]
        if yc and len(fh) > 0:
            print(f"\n=== {fn}: FH rows={len(fh)}, year cols={yc} ===")
            for c in yc:
                vals = fh[c].dropna()
                if len(vals) > 0:
                    print(f"  {c}: nunique={vals.nunique()}, sample={vals.head(5).tolist()}")
    except Exception as e:
        print(f"{fn}: {e}")
