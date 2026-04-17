"""Combine FB47 (basement wall layers) + FB_Klimat summaries into one CSV."""
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
fb47_path = glob.glob(f"{BETSI}/FB47*")[0]
fb47 = pd.read_csv(fb47_path, encoding="latin-1", sep=";", decimal=",")
fb47 = fb47[fb47["Hustyp"] == "F"].copy()

fb47 = fb47.rename(columns={
    "FB47SelectKod": "MaterialCode",
    "FB47SelectLambda": "Lambda_W_mK",
    "FB47SelectTjocklek": "Thickness_mm",
    "FB47R": "R_m2K_W",
})
fb47["Material"] = fb47["MaterialCode"].map(MATERIAL_NAMES).fillna("Unknown")

# ── Summary from FB_Klimat ──
wall_summary = klimat_fh[["Byggnad",
    "FB42 Area källarvägg under mark",
    "FB46 Källarväggens area ovan mark",
    "FB47 Källarväggens totala tjocklek",
    "FB47 Summa R Värmemotstånd",
    "FB47 U-värde källarvägg under mark",
    "FB47 U-värde källarvägg ovan mark",
]].copy()

merged = fb47.merge(wall_summary, on="Byggnad", how="left")
merged = merged.merge(bldg_meta, on="Byggnad", how="left")
merged = merged.sort_values(["Byggnad", "id"])

merged = merged.rename(columns={
    "FB47 Källarväggens totala tjocklek": "TotalThickness_mm",
    "FB47 Summa R Värmemotstånd": "TotalR_m2K_W",
    "FB47 U-värde källarvägg under mark": "U_value_below_grade_W_m2K",
    "FB47 U-värde källarvägg ovan mark": "U_value_above_grade_W_m2K",
    "FB42 Area källarvägg under mark": "WallArea_below_grade_m2",
    "FB46 Källarväggens area ovan mark": "WallArea_above_grade_m2",
})

out = merged[[
    "Byggnad", "BuildingType", "ProductionMethod", "StructuralSystem", "EstimatedEra",
    "EarliestRenovation",
    "U_value_below_grade_W_m2K", "U_value_above_grade_W_m2K",
    "TotalThickness_mm", "TotalR_m2K_W",
    "WallArea_below_grade_m2", "WallArea_above_grade_m2",
    "MaterialCode", "Material", "Lambda_W_mK", "Thickness_mm", "R_m2K_W",
]]

out_path = Path(__file__).parent / "betsi_basement_walls_combined.csv"
out.to_csv(out_path, index=False)
print(f"Wrote {len(out)} rows for {out['Byggnad'].nunique()} buildings to {out_path}")

print(f"\n=== U-value statistics (below grade) by EstimatedEra ===\n")
_common.print_era_summary(out, u_col="U_value_below_grade_W_m2K")

print("=== Material frequency (all layers) ===")
print(out["Material"].value_counts().head(15).to_string())
