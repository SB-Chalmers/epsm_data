"""Combine FB56 (attic floor) + FB62 (sloped roof) layers + FB_Klimat summaries into one CSV."""
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

bldg_meta = _common.load_building_metadata()
klimat_fh = _common.load_klimat_fh()

# ── Load layer files ──
fb56_path = glob.glob(f"{BETSI}/FB56*")[0]
fb56 = pd.read_csv(fb56_path, encoding="latin-1", sep=";", decimal=",")
fb56 = fb56[fb56["Hustyp"] == "F"].copy()
fb56["RoofType"] = "Attic floor (horizontal)"

fb62_path = glob.glob(f"{BETSI}/FB62*")[0]
fb62 = pd.read_csv(fb62_path, encoding="latin-1", sep=";", decimal=",")
fb62 = fb62[fb62["Hustyp"] == "F"].copy()
fb62["RoofType"] = "Sloped roof (rafters)"

# Normalize column names: FB56SelectKod → SelectKod, etc.
def normalize_layer_cols(df, prefix):
    return df.rename(columns={
        f"{prefix}SelectKod": "MaterialCode",
        f"{prefix}SelectLambda": "Lambda_W_mK",
        f"{prefix}SelectTjocklek": "Thickness_mm",
        f"{prefix}R": "R_m2K_W",
    })

fb56 = normalize_layer_cols(fb56, "FB56")
fb62 = normalize_layer_cols(fb62, "FB62")

# Combine
layers = pd.concat([fb56, fb62], ignore_index=True)
layers["Material"] = layers["MaterialCode"].map(MATERIAL_NAMES).fillna("Unknown")

# ── Summary from FB_Klimat ──
roof_summary = klimat_fh[["Byggnad",
    "FB56 Area horisontell vindsbjälklag m2",
    "FB56 U-värde vindsbjälklag",
    "FB56 Total tjocklek horisontellt vindsbjälklag",
    "FB56 Summa R Värmemotstånd",
    "FB62 U-värde snedtak",
    "FB62 Total tjocklek snedtak",
    "FB62 Summa R värmemotstånd",
    "FB61 Area snedtak",
]].copy()

# Pick the right summary per building+type
layers = layers.merge(roof_summary, on="Byggnad", how="left")

# Assign U-value, area, thickness, R based on type
layers["U_value_W_m2K"] = layers.apply(
    lambda r: r["FB56 U-värde vindsbjälklag"] if r["RoofType"].startswith("Attic")
    else r["FB62 U-värde snedtak"], axis=1
)
layers["TotalThickness_mm"] = layers.apply(
    lambda r: r["FB56 Total tjocklek horisontellt vindsbjälklag"] if r["RoofType"].startswith("Attic")
    else r["FB62 Total tjocklek snedtak"], axis=1
)
layers["TotalR_m2K_W"] = layers.apply(
    lambda r: r["FB56 Summa R Värmemotstånd"] if r["RoofType"].startswith("Attic")
    else r["FB62 Summa R värmemotstånd"], axis=1
)
layers["RoofArea_m2"] = layers.apply(
    lambda r: r["FB56 Area horisontell vindsbjälklag m2"] if r["RoofType"].startswith("Attic")
    else r["FB61 Area snedtak"], axis=1
)

# Join metadata
layers = layers.merge(bldg_meta, on="Byggnad", how="left")
layers = layers.sort_values(["Byggnad", "RoofType", "id"])

# Select columns
out = layers[[
    "Byggnad", "BuildingType", "ProductionMethod", "StructuralSystem", "EstimatedEra",
    "EarliestRenovation", "RoofType",
    "U_value_W_m2K", "TotalThickness_mm", "TotalR_m2K_W", "RoofArea_m2",
    "MaterialCode", "Material", "Lambda_W_mK", "Thickness_mm", "R_m2K_W",
]]

out_path = Path(__file__).parent / "betsi_roofs_combined.csv"
out.to_csv(out_path, index=False)
print(f"Wrote {len(out)} rows for {out['Byggnad'].nunique()} buildings to {out_path}")

# ── Summary ──
print(f"\n=== Roof type distribution ===")
bldg_types = out.drop_duplicates(subset=["Byggnad", "RoofType"])
print(bldg_types["RoofType"].value_counts().to_string())

print(f"\n=== U-value statistics by EstimatedEra ===\n")
_common.print_era_summary(out)

print("=== Material frequency (all layers) ===")
print(out["Material"].value_counts().head(15).to_string())
