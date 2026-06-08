"""Count unique materials across all BETSI component files."""
import pandas as pd
import glob
from pathlib import Path

BETSI = str(Path(__file__).parent)
MATERIAL_NAMES = {
    1: "Mineral wool boards", 2: "Brick", 3: "Calcium silicate",
    4: "Leca block", 5: "Cellular plastic XPS/EPS", 6: "Mineral wool loose",
    7: "Wood shavings/sawdust", 8: "Wood", 9: "Aerated concrete",
    10: "Concrete", 11: "Cork", 12: "Glass", 13: "Steel",
    14: "Lightweight aggregate block", 15: "Lightweight concrete (cast)",
    16: "Cellular glass/foam glass", 17: "Polyurethane foam",
    18: "Asphalt board/felt", 19: "Mineral wool (older)",
    20: "Mineral wool (modern)", 21: "Air gap", 22: "Gypsum board",
    23: "Plaster/render", 24: "Plywood/fibreboard", 25: "Plastic foil",
    26: "Window", 27: "Lightweight concrete block",
    28: "Timber frame+insulation", 29: "Other", 30: "Insulation board (other)",
}

files = {
    "FB52 (ext wall)": "FB52*",
    "FB56 (attic)": "FB56*",
    "FB62 (sloped roof)": "FB62*",
    "FB33 (ground floor)": "FB33*",
    "FB30 (crawl floor)": "FB30*",
    "FB47 (basement wall)": "FB47*",
    "FB40 (basement floor)": "FB40*",
    "FB59 (knee wall)": "FB59*",
}

all_codes = set()
code_by_file = {}
counts_by_file = {}  # label -> Series(code -> count)

for label, pat in files.items():
    matches = glob.glob(f"{BETSI}/{pat}")
    if not matches:
        continue
    df = pd.read_csv(matches[0], sep=";", decimal=",", encoding="latin-1")
    fh = df[df["Hustyp"] == "F"]
    kod_col = [c for c in df.columns if "SelectKod" in c][0]
    series = fh[kod_col].dropna().astype(int)
    counts = series.value_counts().sort_index()
    codes = set(counts.index)
    all_codes |= codes
    code_by_file[label] = codes
    counts_by_file[label] = counts

# Build a combined DataFrame: rows=material codes, cols=component files
all_labels = list(files.keys())
count_df = pd.DataFrame(
    {label: counts_by_file[label] for label in all_labels if label in counts_by_file}
).fillna(0).astype(int)
count_df.index = count_df.index.astype(int)
count_df["TOTAL"] = count_df.sum(axis=1)
count_df = count_df.sort_values("TOTAL", ascending=False)

print(f"Unique material codes across all components: {len(all_codes)}")
print()
# Header
col_abbrev = {
    "FB52 (ext wall)": "ExtWall",
    "FB56 (attic)": "Attic",
    "FB62 (sloped roof)": "SlopedRoof",
    "FB33 (ground floor)": "GndFloor",
    "FB30 (crawl floor)": "CrawlFloor",
    "FB47 (basement wall)": "BsmtWall",
    "FB40 (basement floor)": "BsmtFloor",
    "FB59 (knee wall)": "KneeWall",
}
headers = [col_abbrev.get(l, l) for l in all_labels if l in counts_by_file] + ["TOTAL"]
print(f"{'Code':>4}  {'Material':<35} " + "  ".join(f"{h:>10}" for h in headers))
print("-" * (42 + 12 * len(headers)))
for code, row in count_df.iterrows():
    name = MATERIAL_NAMES.get(code, f"???({code})")
    vals = "  ".join(f"{row.get(l, 0):>10,}" for l in ([l for l in all_labels if l in counts_by_file] + ["TOTAL"]))
    print(f"{code:>4}  {name:<35} {vals}")

# Summary: insulation-only codes
INSULATION_CODES = {1, 5, 6, 7, 11, 16, 17, 19, 20, 28, 30}
print()
print("=== Insulation materials only (ranked by total rows) ===")
ins_df = count_df[count_df.index.isin(INSULATION_CODES)]
ins_total = ins_df["TOTAL"].sum()
for code, row in ins_df.iterrows():
    name = MATERIAL_NAMES.get(code, f"???({code})")
    pct = row["TOTAL"] / ins_total * 100 if ins_total else 0
    print(f"  {code:>2}  {name:<35} {row['TOTAL']:>6,}  ({pct:5.1f}%)")
