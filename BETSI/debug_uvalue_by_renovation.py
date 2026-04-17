"""U-value distributions by component-specific renovation status.

For each envelope component (ext wall, roof, floor, windows), split
buildings into 'renovated' vs 'unrenovated' using the *component-specific*
FC3 renovation year columns — not the building-level EarliestRenovation.

FC3 component mapping:
  - Ext wall:  FC3 Byte fasad år  |  FC3 Tilläggsisolering fasad år
  - Roof:      FC3 Tilläggsisolering vind år
  - Windows:   FC3 Fönster år
  - Floor:     (no specific column — use EarliestRenovation as proxy)
"""

import glob
import pandas as pd
import numpy as np
from pathlib import Path

BETSI = str(Path(__file__).parent)

# ── Load building-level U-values from FB_Klimat ──
klimat = pd.read_csv(f"{BETSI}/FB_Klimat.csv", encoding="latin-1", sep=";", decimal=",")
klimat = klimat[klimat["Hustyp"] == "F"].copy()

# Fix decimal commas in key U-value columns
u_cols_klimat = {
    "FB52 U-medelvärde ytterväggar": "U_wall",
    "FB56 U-värde vindsbjälklag": "U_roof",
    "FB33 U-värde platta på mark/källargolv": "U_floor",
    "FB87-97 U-medelvärde fönster": "U_window",
}
for orig, short in u_cols_klimat.items():
    if orig in klimat.columns:
        klimat[short] = pd.to_numeric(
            klimat[orig].astype(str).str.replace(",", "."), errors="coerce"
        )
    else:
        klimat[short] = float("nan")

bldg = klimat[["Byggnad", "U_wall", "U_roof", "U_floor", "U_window"]].copy()

# ── Load FC3 — component-specific renovation years ──
fc3 = pd.read_csv(f"{BETSI}/FC3.csv", encoding="latin-1", sep=";", decimal=",")
fc3 = fc3[fc3["Byggnad"].str.startswith("FH", na=False)].copy()

year_cols = [c for c in fc3.columns if "år" in c.lower() and "FC3" in c]
for c in year_cols:
    fc3[c] = pd.to_numeric(fc3[c], errors="coerce")
    fc3.loc[(fc3[c] >= 9000) | (fc3[c] < 1900), c] = float("nan")

# Component-specific renovation flags
fc3["wall_renovated"] = fc3[["FC3 Byte fasad år", "FC3 Tilläggsisolering fasad år"]].notna().any(axis=1)
fc3["wall_renov_year"] = fc3[["FC3 Byte fasad år", "FC3 Tilläggsisolering fasad år"]].min(axis=1)

fc3["roof_renovated"] = fc3["FC3 Tilläggsisolering vind år"].notna()
fc3["roof_renov_year"] = fc3["FC3 Tilläggsisolering vind år"]

fc3["window_renovated"] = fc3["FC3 Fönster år"].notna()
fc3["window_renov_year"] = fc3["FC3 Fönster år"]

# Building-level earliest renovation (proxy for floor, since no floor-specific column)
fc3["EarliestRenovation"] = fc3[year_cols].min(axis=1)
fc3["any_renovated"] = fc3["EarliestRenovation"].notna()

# Merge
bldg = bldg.merge(
    fc3[["Byggnad", "wall_renovated", "wall_renov_year",
         "roof_renovated", "roof_renov_year",
         "window_renovated", "window_renov_year",
         "any_renovated", "EarliestRenovation"]],
    on="Byggnad", how="left",
)

# Fill NaN renovation flags with False for buildings not in FC3
for col in ["wall_renovated", "roof_renovated", "window_renovated", "any_renovated"]:
    bldg[col] = bldg[col].fillna(False)

# ── Load structural system / era ──
ovrigt = pd.read_csv(f"{BETSI}/FB_OVRIGT.csv", encoding="latin-1", sep=";")
ovrigt = ovrigt[ovrigt["Hustyp"] == "F"].copy()
STRUCTURE_ERA = {
    "Murverk": "pre-1960",
    "Väggar av betong": "1950-1975",
    "Alla väggar av betong": "1960-1980",
    "Träregelstomme": "mixed",
    "Pelare av betong": "1960-1980",
    "Kombination": "mixed",
    "Annat, vilken?": "other",
    "Vet inte": "unknown",
}
if "FB5 Vertikalt bärverk" in ovrigt.columns:
    ovrigt["EstimatedEra"] = ovrigt["FB5 Vertikalt bärverk"].map(
        lambda x: STRUCTURE_ERA.get(str(x).strip(), "unknown") if pd.notna(x) else "unknown"
    )
else:
    ovrigt["EstimatedEra"] = "unknown"

bldg = bldg.merge(
    ovrigt[["Byggnad", "EstimatedEra"]].drop_duplicates(),
    on="Byggnad", how="left",
)


# ──────────────────────────────────────────────────────────────
# ANALYSIS
# ──────────────────────────────────────────────────────────────

def stats_row(series, label):
    s = series.dropna()
    return {
        "Group": label,
        "n": len(s),
        "mean": s.mean(),
        "median": s.median(),
        "std": s.std(),
        "Q25": s.quantile(0.25),
        "Q75": s.quantile(0.75),
        "min": s.min(),
        "max": s.max(),
    }


def print_comparison(component_name, u_col, renov_col, df):
    """Print renovated vs unrenovated U-value comparison."""
    valid = df[df[u_col].notna() & (df[u_col] > 0)].copy()
    if len(valid) == 0:
        print(f"\n{'='*70}\n{component_name}: No valid U-value data\n")
        return

    renovated = valid[valid[renov_col] == True]
    unrenovated = valid[valid[renov_col] == False]

    rows = [
        stats_row(valid[u_col], "All buildings"),
        stats_row(unrenovated[u_col], "Unrenovated"),
        stats_row(renovated[u_col], "Renovated"),
    ]

    print(f"\n{'='*70}")
    print(f"  {component_name} — U-value [W/(m²·K)]")
    print(f"  Renovation column: {renov_col}")
    print(f"{'='*70}")
    tbl = pd.DataFrame(rows)
    tbl[["mean", "median", "std", "Q25", "Q75", "min", "max"]] = tbl[
        ["mean", "median", "std", "Q25", "Q75", "min", "max"]
    ].round(3)
    print(tbl.to_string(index=False))

    if len(renovated) > 0 and len(unrenovated) > 0:
        delta = unrenovated[u_col].median() - renovated[u_col].median()
        pct = delta / unrenovated[u_col].median() * 100
        print(f"\n  Δ median (unrenovated − renovated) = {delta:.3f} W/(m²·K)  ({pct:+.1f}%)")
    else:
        print(f"\n  (Cannot compute delta — one group is empty)")

    # Per-era breakdown
    eras_order = ["pre-1960", "1950-1975", "1960-1980", "mixed"]
    print(f"\n  Per-era breakdown:")
    print(f"  {'Era':<14} {'Unrenov n':>9} {'Unrenov med':>11} {'Renov n':>8} {'Renov med':>10} {'Δ median':>9}")
    print(f"  {'-'*14} {'-'*9} {'-'*11} {'-'*8} {'-'*10} {'-'*9}")
    for era in eras_order:
        era_df = valid[valid["EstimatedEra"] == era]
        unr = era_df[era_df[renov_col] == False][u_col].dropna()
        ren = era_df[era_df[renov_col] == True][u_col].dropna()
        unr_med = unr.median() if len(unr) > 0 else float("nan")
        ren_med = ren.median() if len(ren) > 0 else float("nan")
        delta = unr_med - ren_med if not (np.isnan(unr_med) or np.isnan(ren_med)) else float("nan")
        print(f"  {era:<14} {len(unr):>9} {unr_med:>11.3f} {len(ren):>8} {ren_med:>10.3f} {delta:>9.3f}")


print("\n" + "#" * 70)
print("#  U-VALUE DISTRIBUTIONS BY COMPONENT-SPECIFIC RENOVATION STATUS")
print("#  Source: BETSI FH buildings (FB_Klimat U-values + FC3 renovation years)")
print("#" * 70)

# 1. Exterior walls
print_comparison(
    "EXTERIOR WALLS",
    "U_wall", "wall_renovated", bldg,
)

# 2. Roof (attic floor)
print_comparison(
    "ROOF / ATTIC FLOOR (vindsbjälklag)",
    "U_roof", "roof_renovated", bldg,
)

# 3. Windows
print_comparison(
    "WINDOWS",
    "U_window", "window_renovated", bldg,
)

# 4. Ground floor — no specific renovation column, use any_renovated
print_comparison(
    "GROUND FLOOR (any renovation as proxy)",
    "U_floor", "any_renovated", bldg,
)

# ── Renovation year vs U-value correlation ──
print(f"\n{'='*70}")
print(f"  RENOVATION YEAR vs U-VALUE (for renovated buildings only)")
print(f"{'='*70}")

for name, u_col, year_col, flag_col in [
    ("Ext wall", "U_wall", "wall_renov_year", "wall_renovated"),
    ("Roof", "U_roof", "roof_renov_year", "roof_renovated"),
    ("Windows", "U_window", "window_renov_year", "window_renovated"),
]:
    subset = bldg[(bldg[flag_col] == True) & bldg[u_col].notna() & (bldg[u_col] > 0) & bldg[year_col].notna()]
    if len(subset) < 5:
        print(f"\n  {name}: too few data points ({len(subset)})")
        continue
    corr = subset[[u_col, year_col]].corr().iloc[0, 1]
    print(f"\n  {name}: n={len(subset)}, Pearson r = {corr:.3f}")

    # Decade bins
    subset = subset.copy()
    subset["decade"] = (subset[year_col] // 10 * 10).astype(int)
    decade_stats = subset.groupby("decade")[u_col].agg(["count", "median", "mean"]).round(3)
    decade_stats.columns = ["n", "median_U", "mean_U"]
    print(decade_stats.to_string())

# ── Summary counts ──
print(f"\n{'='*70}")
print(f"  RENOVATION COUNTS SUMMARY")
print(f"{'='*70}")
total = len(bldg)
print(f"  Total FH buildings in FB_Klimat: {total}")
print(f"  Wall renovated (facade replacement or insulation added): {bldg['wall_renovated'].sum()} ({bldg['wall_renovated'].mean()*100:.1f}%)")
print(f"  Roof insulation added: {bldg['roof_renovated'].sum()} ({bldg['roof_renovated'].mean()*100:.1f}%)")
print(f"  Windows replaced: {bldg['window_renovated'].sum()} ({bldg['window_renovated'].mean()*100:.1f}%)")
print(f"  Any renovation recorded: {bldg['any_renovated'].sum()} ({bldg['any_renovated'].mean()*100:.1f}%)")
