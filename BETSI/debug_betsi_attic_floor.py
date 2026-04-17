"""Quick inspection of FC3, FB_Klimat, FB87, FB56 structure."""
import glob
import pandas as pd
from pathlib import Path

BETSI = str(Path(__file__).parent)

# FC3 columns
fc3 = pd.read_csv(f"{BETSI}/FC3.csv", encoding="latin-1", sep=";", decimal=",")
year_cols = [c for c in fc3.columns if "år" in c.lower() and "FC3" in c]
print("=== FC3 year columns ===")
for c in year_cols:
    print(f"  {c}")

# FB_Klimat U-value columns
klimat = pd.read_csv(f"{BETSI}/FB_Klimat.csv", encoding="latin-1", sep=";", decimal=",")
u_cols = [c for c in klimat.columns if any(x in c.lower() for x in ["u-", "ua-", "uvärde"])]
print("\n=== FB_Klimat U-value columns ===")
for c in u_cols:
    print(f"  {c}")

# Window data
fb87 = glob.glob(f"{BETSI}/FB87*")
if fb87:
    w = pd.read_csv(fb87[0], encoding="latin-1", sep=None, engine="python")
    print("\n=== FB87 (Window E) columns ===")
    for c in w.columns:
        print(f"  {c}")
    w_fh = w[w["Hustyp"] == "F"]
    print(f"  FH rows: {len(w_fh)}, buildings: {w_fh['Byggnad'].nunique()}")

# FB56
fb56 = glob.glob(f"{BETSI}/FB56*")
if fb56:
    r = pd.read_csv(fb56[0], encoding="latin-1", sep=None, engine="python")
    print("\n=== FB56 (Attic floor) columns ===")
    for c in r.columns:
        print(f"  {c}")
    r_fh = r[r["Hustyp"] == "F"]
    print(f"  FH rows: {len(r_fh)}, buildings: {r_fh['Byggnad'].nunique()}")
