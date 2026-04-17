"""Check FC3 renovation years for FH buildings and compute earliest renovation."""
import pandas as pd
from pathlib import Path

betsi = str(Path(__file__).parent)
fc3 = pd.read_csv(f"{betsi}/FC3.csv", sep=";", decimal=",", encoding="latin-1")
fh = fc3[fc3["Byggnad"].str.startswith("FH", na=False)]
year_cols = [c for c in fc3.columns if "år" in c.lower() and "FC3" in c]

print(f"FH rows: {len(fh)}, year cols: {len(year_cols)}")
for c in year_cols:
    vals = fh[c].dropna()
    vals = vals[(vals < 9000) & (vals > 1900)]
    if len(vals) > 0:
        print(f"  {c}: n={len(vals)}, min={vals.min():.0f}, max={vals.max():.0f}")

# Compute earliest renovation year per building
fh_years = fh[["Byggnad"] + year_cols].copy()
for c in year_cols:
    fh_years[c] = pd.to_numeric(fh_years[c], errors="coerce")
    fh_years.loc[fh_years[c] >= 9000, c] = float("nan")
    fh_years.loc[fh_years[c] < 1900, c] = float("nan")

fh_years["EarliestRenovation"] = fh_years[year_cols].min(axis=1)
valid = fh_years[fh_years["EarliestRenovation"].notna()]
total = fh["Byggnad"].nunique()
print(f"\nBuildings with any renovation year: {len(valid)} / {total}")
print(f"Earliest renovation range: {valid['EarliestRenovation'].min():.0f} - {valid['EarliestRenovation'].max():.0f}")
print(valid["EarliestRenovation"].describe())
