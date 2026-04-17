"""Combine FB40 (basement floor layers) + FB_Klimat summaries into one CSV."""
import glob
import pandas as pd
from pathlib import Path
import importlib.util

_spec = importlib.util.spec_from_file_location("_betsi_common", Path(__file__).parent / "_betsi_common.py")
_common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_common)

BETSI = _common.BETSI
MATERIAL_NAMES = _common.MATERIAL_NAMES

bldg_meta = _common.load_building_metadata()
klimat_fh = _common.load_klimat_fh()

# ── Load layer file (FB40 file uses FB41 column prefix) ──
fb40_path = glob.glob(f"{BETSI}/FB40*")[0]
fb40 = pd.read_csv(fb40_path, encoding="latin-1", sep=";", decimal=",")
fb40 = fb40[fb40["Hustyp"] == "F"].copy()

fb40 = fb40.rename(columns={
    "FB41SelectKod": "MaterialCode",
    "FB41SelectLambda": "Lambda_W_mK",
    "FB41SelectTjocklek": "Thickness_mm",
    "FB41R": "R_m2K_W",
})
fb40["Material"] = fb40["MaterialCode"].map(MATERIAL_NAMES).fillna("Unknown")

# ── Summary from FB_Klimat ──
floor_summary = klimat_fh[["Byggnad",
    "FB40 Källare",
    "FB41 Källare uppvärmd",
    "FB41 Area bjälklag ovan ouppvärmd källare m2",
    "FB41 Total tjocklek m2",
    "FB41 Summa R Värmemotstånd",
    "FB41 U-värde bjälklag ovan ouppvärmd källare",
]].copy()

merged = fb40.merge(floor_summary, on="Byggnad", how="left")
merged = merged.merge(bldg_meta, on="Byggnad", how="left")
merged = merged.sort_values(["Byggnad", "id"])

merged = merged.rename(columns={
    "FB41 Area bjälklag ovan ouppvärmd källare m2": "FloorArea_m2",
    "FB41 Total tjocklek m2": "TotalThickness_mm",
    "FB41 Summa R Värmemotstånd": "TotalR_m2K_W",
    "FB41 U-värde bjälklag ovan ouppvärmd källare": "U_value_W_m2K",
    "FB40 Källare": "HasBasement",
    "FB41 Källare uppvärmd": "BasementHeated",
})

out = merged[[
    "Byggnad", "BuildingType", "ProductionMethod", "StructuralSystem", "EstimatedEra",
    "EarliestRenovation", "HasBasement", "BasementHeated",
    "U_value_W_m2K", "TotalThickness_mm", "TotalR_m2K_W", "FloorArea_m2",
    "MaterialCode", "Material", "Lambda_W_mK", "Thickness_mm", "R_m2K_W",
]]

out_path = Path(__file__).parent / "betsi_basement_floors_combined.csv"
out.to_csv(out_path, index=False)
print(f"Wrote {len(out)} rows for {out['Byggnad'].nunique()} buildings to {out_path}")

print(f"\n=== U-value statistics by EstimatedEra ===\n")
_common.print_era_summary(out)

print("=== Material frequency (all layers) ===")
print(out["Material"].value_counts().head(15).to_string())
