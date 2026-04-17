"""Combine FB33 (ground floor layers) + FB_Klimat (U-value, area) into one CSV.

Output: betsi_ground_floors_combined.csv — 1139 rows, 537 buildings.
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
FLOOR_TYPE_EN = _common.FLOOR_TYPE_EN

bldg_meta = _common.load_building_metadata()
klimat_fh = _common.load_klimat_fh()

# ── Load layer file ──
fb33_path = glob.glob(f"{BETSI}/FB33*")[0]
fb33 = pd.read_csv(fb33_path, encoding="latin-1", sep=";", decimal=",")
fb33 = fb33[fb33["Hustyp"] == "F"].copy()

fb33["Material"] = fb33["FB33SelectKod"].map(MATERIAL_NAMES).fillna("Unknown")

# ── Floor summary from FB_Klimat ──
floor_summary = klimat_fh[["Byggnad",
    "FB32 Typ av platta på mark/källargolv",
    "FB33 Area platta på mark/källargolv, kvm",
    "FB33 Tjocklek platta på mark/källargolv",
    "FB33 Summa R värmemotstånd",
    "FB33 U-värde platta på mark/källargolv",
]].copy()

floor_summary["FloorType"] = floor_summary["FB32 Typ av platta på mark/källargolv"].map(
    lambda x: FLOOR_TYPE_EN.get(str(x).strip(), str(x)) if pd.notna(x) else ""
)

# ── Join everything ──
merged = fb33.merge(floor_summary, on="Byggnad", how="left")
merged = merged.merge(bldg_meta, on="Byggnad", how="left")
merged = merged.sort_values(["Byggnad", "id"])

merged = merged.rename(columns={
    "FB33SelectKod": "MaterialCode",
    "FB33SelectLambda": "Lambda_W_mK",
    "FB33SelectTjocklek": "Thickness_mm",
    "FB33R": "R_m2K_W",
    "FB33 Area platta på mark/källargolv, kvm": "FloorArea_m2",
    "FB33 Tjocklek platta på mark/källargolv": "TotalThickness_mm",
    "FB33 Summa R värmemotstånd": "TotalR_m2K_W",
    "FB33 U-värde platta på mark/källargolv": "U_value_W_m2K",
})

out = merged[[
    "Byggnad", "BuildingType", "ProductionMethod", "StructuralSystem", "EstimatedEra",
    "EarliestRenovation", "FloorType",
    "U_value_W_m2K", "TotalThickness_mm", "TotalR_m2K_W", "FloorArea_m2",
    "MaterialCode", "Material", "Lambda_W_mK", "Thickness_mm", "R_m2K_W",
]]

out_path = Path(__file__).parent / "betsi_ground_floors_combined.csv"
out.to_csv(out_path, index=False)
print(f"Wrote {len(out)} rows for {out['Byggnad'].nunique()} buildings to {out_path}")

# ── Summary ──
print(f"\n=== U-value statistics by EstimatedEra ===\n")
_common.print_era_summary(out)

print("=== Floor type distribution ===")
bldg = out.drop_duplicates(subset=["Byggnad"])
print(bldg["FloorType"].value_counts().to_string())

print("\n=== Material frequency (all layers) ===")
print(out["Material"].value_counts().head(15).to_string())
