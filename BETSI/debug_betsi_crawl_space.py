"""Combine FB30 (crawl space floor layers) + FB_Klimat summaries into one CSV."""
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

# ── Load layer file ──
fb30_path = glob.glob(f"{BETSI}/FB30*")[0]
fb30 = pd.read_csv(fb30_path, encoding="latin-1", sep=";", decimal=",")
fb30 = fb30[fb30["Hustyp"] == "F"].copy()

fb30 = fb30.rename(columns={
    "FB30SelectKod": "MaterialCode",
    "FB30SelectLambda": "Lambda_W_mK",
    "FB30SelectTjocklek": "Thickness_mm",
    "FB30R": "R_m2K_W",
})
fb30["Material"] = fb30["MaterialCode"].map(MATERIAL_NAMES).fillna("Unknown")

# ── Summary from FB_Klimat ──
crawl_summary = klimat_fh[["Byggnad",
    "FB30 Area bjälklag ovan krypgrund m2",
    "FB30 Total tjocklek bjälklag ovan krypgrund",
    "FB30 Summa R Värmemotstånd",
    "FB30 U-värde bjälklag ovan krypgrund",
]].copy()

merged = fb30.merge(crawl_summary, on="Byggnad", how="left")
merged = merged.merge(bldg_meta, on="Byggnad", how="left")
merged = merged.sort_values(["Byggnad", "id"])

merged = merged.rename(columns={
    "FB30 Area bjälklag ovan krypgrund m2": "FloorArea_m2",
    "FB30 Total tjocklek bjälklag ovan krypgrund": "TotalThickness_mm",
    "FB30 Summa R Värmemotstånd": "TotalR_m2K_W",
    "FB30 U-värde bjälklag ovan krypgrund": "U_value_W_m2K",
})

out = merged[[
    "Byggnad", "BuildingType", "ProductionMethod", "StructuralSystem", "EstimatedEra",
    "EarliestRenovation",
    "U_value_W_m2K", "TotalThickness_mm", "TotalR_m2K_W", "FloorArea_m2",
    "MaterialCode", "Material", "Lambda_W_mK", "Thickness_mm", "R_m2K_W",
]]

out_path = Path(__file__).parent / "betsi_crawl_space_floors_combined.csv"
out.to_csv(out_path, index=False)
print(f"Wrote {len(out)} rows for {out['Byggnad'].nunique()} buildings to {out_path}")

print(f"\n=== U-value statistics by EstimatedEra ===\n")
_common.print_era_summary(out)

print("=== Material frequency (all layers) ===")
print(out["Material"].value_counts().head(15).to_string())
