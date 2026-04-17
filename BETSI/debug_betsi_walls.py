"""Combine FB49 (wall summary) + FB52 (layer details) into one CSV.

Output: betsi_ext_walls_combined.csv — 2075 rows, 559 buildings.
"""
import glob
import pandas as pd
from pathlib import Path
import importlib.util

# Load shared metadata
_spec = importlib.util.spec_from_file_location("_betsi_common", Path(__file__).parent / "_betsi_common.py")
_common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_common)

BETSI = _common.BETSI
MATERIAL_NAMES = _common.MATERIAL_NAMES
FACADE_NAMES = _common.FACADE_NAMES

bldg_meta = _common.load_building_metadata()

# ── Load layer files ──
fb49_path = glob.glob(f"{BETSI}/FB49*")[0]
fb52_path = glob.glob(f"{BETSI}/FB52*")[0]

fb49 = pd.read_csv(fb49_path, encoding="latin-1", sep=";", decimal=",")
fb52 = pd.read_csv(fb52_path, encoding="latin-1", sep=";", decimal=",")

fb49 = fb49[fb49["Hustyp"] == "F"].copy()
fb52 = fb52[fb52["Hustyp"] == "F"].copy()

# ── Apply translations ──
fb52["Material"] = fb52["FB52SelectKod"].map(MATERIAL_NAMES).fillna("Unknown")
fb49["FB49Fasadmaterial"] = fb49["FB49Fasadmaterial"].map(
    lambda x: FACADE_NAMES.get(str(x).strip(), str(x)) if pd.notna(x) else x
)

# ── Join everything ──
merged = fb52.merge(
    fb49[["Byggnad", "FB49YtterväggNr", "FB49Fasadmaterial",
          "FB50Ytterväggsarea m2", "FB51 Procent av ytterväggen",
          "FB52 Summa total tjocklek", "FB52 Summa R Värmemotstånd",
          "FB52 U-värde yttervägg"]],
    on=["Byggnad", "FB49YtterväggNr"],
    how="left",
)
merged = merged.merge(bldg_meta, on="Byggnad", how="left")
merged = merged.sort_values(["Byggnad", "FB49YtterväggNr", "id"])

merged = merged.rename(columns={
    "FB52SelectKod": "MaterialCode",
    "FB52SelectLambda": "Lambda_W_mK",
    "FB52SelectTjocklek": "Thickness_mm",
    "FB52R": "R_m2K_W",
    "FB49Fasadmaterial": "FacadeMaterial",
    "FB50Ytterväggsarea m2": "WallArea_m2",
    "FB51 Procent av ytterväggen": "WallPercent",
    "FB52 Summa total tjocklek": "TotalThickness_mm",
    "FB52 Summa R Värmemotstånd": "TotalR_m2K_W",
    "FB52 U-värde yttervägg": "U_value_W_m2K",
    "FB49YtterväggNr": "WallNr",
})

out = merged[[
    "Byggnad", "BuildingType", "ProductionMethod", "StructuralSystem", "EstimatedEra",
    "EarliestRenovation",
    "WallNr", "FacadeMaterial", "U_value_W_m2K",
    "TotalThickness_mm", "TotalR_m2K_W", "WallArea_m2", "WallPercent",
    "MaterialCode", "Material", "Lambda_W_mK", "Thickness_mm", "R_m2K_W",
]]

out_path = Path(__file__).parent / "betsi_ext_walls_combined.csv"
out.to_csv(out_path, index=False)
print(f"Wrote {len(out)} rows for {out['Byggnad'].nunique()} buildings to {out_path}")

# ── Summary ──
print(f"\n=== U-value statistics by EstimatedEra ===\n")
_common.print_era_summary(out)

print("=== Material frequency (all layers) ===")
print(out["Material"].value_counts().head(15).to_string())
