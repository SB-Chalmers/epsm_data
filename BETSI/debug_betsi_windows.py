"""Combine FB87/88/91/94 (windows per orientation) + FB_Klimat summaries into one CSV."""
import glob
import pandas as pd
from pathlib import Path
import importlib.util

_spec = importlib.util.spec_from_file_location("_betsi_common", Path(__file__).parent / "_betsi_common.py")
_common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_common)

BETSI = _common.BETSI
bldg_meta = _common.load_building_metadata()

# ── Window orientation files ──
ORIENTATIONS = {
    "FB87": ("East",  "FB97"),    # FB87 file uses FB97 column prefix
    "FB88": ("North", "FB88"),
    "FB91": ("South", "FB91"),
    "FB94": ("West",  "FB94"),
}

FRAME_EN = {
    "Träfönster": "Wood", "Trä/Alu-fönster": "Wood/Aluminium",
    "PVC-fönster": "PVC", "Aluminiumfönster": "Aluminium",
    "Stålfönster": "Steel", "Annat": "Other",
}

frames = []
for fb_file, (orient, col_prefix) in ORIENTATIONS.items():
    matches = glob.glob(f"{BETSI}/{fb_file}*")
    if not matches:
        print(f"WARNING: No file found for {fb_file}")
        continue
    df = pd.read_csv(matches[0], encoding="latin-1", sep=";", decimal=",")
    df = df[df["Hustyp"] == "F"].copy()
    df["Orientation"] = orient
    df = df.rename(columns={
        f"{col_prefix}Fönstertyp": "WindowType",
        f"{col_prefix}Uvärde": "U_value_W_m2K",
        f"{col_prefix}Fönsterarea": "WindowArea_m2",
        f"{col_prefix}Karmmaterial": "FrameMaterial",
    })
    df["FrameMaterial"] = df["FrameMaterial"].map(
        lambda x: FRAME_EN.get(str(x).strip(), str(x)) if pd.notna(x) else ""
    )
    frames.append(df[["Byggnad", "Orientation", "WindowType", "U_value_W_m2K",
                       "WindowArea_m2", "FrameMaterial"]])

windows = pd.concat(frames, ignore_index=True)

# Join metadata
windows = windows.merge(bldg_meta, on="Byggnad", how="left")
windows = windows.sort_values(["Byggnad", "Orientation"])

out = windows[[
    "Byggnad", "BuildingType", "ProductionMethod", "StructuralSystem", "EstimatedEra",
    "EarliestRenovation",
    "Orientation", "WindowType", "U_value_W_m2K", "WindowArea_m2", "FrameMaterial",
]]

out_path = Path(__file__).parent / "betsi_windows_combined.csv"
out.to_csv(out_path, index=False)
print(f"Wrote {len(out)} rows for {out['Byggnad'].nunique()} buildings to {out_path}")

# ── Summary ──
print(f"\n=== Window type distribution ===")
print(out["WindowType"].value_counts().head(10).to_string())

print(f"\n=== Frame material distribution ===")
print(out["FrameMaterial"].value_counts().to_string())

print(f"\n=== U-value by orientation ===")
for orient in ["East", "North", "South", "West"]:
    s = out[out["Orientation"] == orient]["U_value_W_m2K"]
    print(f"  {orient:<6} n={len(s):>3}  median={s.median():.3f}  mean={s.mean():.3f}")

print(f"\n=== Area by orientation ===")
for orient in ["East", "North", "South", "West"]:
    s = out[out["Orientation"] == orient]["WindowArea_m2"]
    print(f"  {orient:<6} total={s.sum():.0f} m²  mean={s.mean():.1f} m²")

print(f"\n=== U-value statistics by EstimatedEra ===\n")
_common.print_era_summary(out)
