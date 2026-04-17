"""Check BETSI for intermediate floor and regular roof data."""
import pandas as pd
import glob
import os
from pathlib import Path

BETSI = str(Path(__file__).parent)

# List ALL FB files
all_fb = sorted(glob.glob(f"{BETSI}/FB*"))
print("All FB files:")
for f in all_fb:
    print(f"  {os.path.basename(f)}")

# Check FB_OVRIGT for intermediate floor + roof columns
ovrigt = pd.read_csv(f"{BETSI}/FB_OVRIGT.csv", sep=";", decimal=",", encoding="latin-1")
fh = ovrigt[ovrigt["Hustyp"] == "F"]

# Intermediate floor columns
bjl_cols = [c for c in ovrigt.columns if "bjälklag" in c.lower() or "FB4" in c or "FB2" in c]
print("\n=== Intermediate floor columns in FB_OVRIGT ===")
for c in bjl_cols:
    vals = fh[c].dropna()
    if len(vals) > 0:
        print(f"  {c}: n={len(vals)}")
        vc = vals.value_counts().head(8)
        for v, n in vc.items():
            print(f"    {v}: {n}")

# Roof/tak columns
tak_cols = [c for c in ovrigt.columns if "tak" in c.lower()]
print("\n=== Roof/tak columns in FB_OVRIGT ===")
for c in tak_cols[:10]:
    vals = fh[c].dropna()
    if len(vals) > 0:
        print(f"  {c}: n={len(vals)}")
        vc = vals.value_counts().head(5)
        for v, n in vc.items():
            print(f"    {v}: {n}")

# Check FC1/FC2 Tak for roof type info
for fn in ["FC1 Tak.csv", "FC2 Tak.csv"]:
    matches = glob.glob(f"{BETSI}/{fn}")
    if matches:
        df = pd.read_csv(matches[0], sep=";", decimal=",", encoding="latin-1")
        print(f"\n=== {fn} ===")
        print(f"  Columns: {df.columns.tolist()}")
        print(f"  Rows: {len(df)}")

# Check what FB56 (attic) vs FB62 (sloped roof) actually represent
# FB56 = vindsbjälklag = attic floor slab (horizontal insulated ceiling)
# FB62 = snedtak = sloped roof (insulated in the roof slope)
# What about flat roof? Does it show up somewhere?

# Check FB_Klimat
klim = pd.read_csv(f"{BETSI}/FB_Klimat.csv", sep=";", decimal=",", encoding="latin-1")
kfh = klim[klim["Hustyp"] == "F"]
print(f"\n=== FB_Klimat ===")
print(f"  Columns: {klim.columns.tolist()}")
print(f"  FH rows: {len(kfh)}")

# Summary: which buildings have ONLY sloped roof (no attic floor)?
fb56_bldgs = set()
fb62_bldgs = set()
for m in glob.glob(f"{BETSI}/FB56*"):
    df = pd.read_csv(m, sep=";", decimal=",", encoding="latin-1")
    fb56_bldgs = set(df[df["Hustyp"] == "F"]["Byggnad"])
for m in glob.glob(f"{BETSI}/FB62*"):
    df = pd.read_csv(m, sep=";", decimal=",", encoding="latin-1")
    fb62_bldgs = set(df[df["Hustyp"] == "F"]["Byggnad"])

only_slope = fb62_bldgs - fb56_bldgs
only_attic = fb56_bldgs - fb62_bldgs
both = fb56_bldgs & fb62_bldgs
neither = 559 - len(fb56_bldgs | fb62_bldgs)

print(f"\n=== Roof type distribution ===")
print(f"  Only attic floor (FB56):       {len(only_attic)}")
print(f"  Only sloped roof (FB62):       {len(only_slope)}")
print(f"  Both (attic + sloped):         {len(both)}")
print(f"  Neither:                       {neither}")
