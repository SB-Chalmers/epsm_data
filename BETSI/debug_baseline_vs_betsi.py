"""Compare all CMF archetype U-values against BETSI unrenovated medians."""
import json

# ── Current computed U-values ──
with open("output/smoke_test/elements_16-04-2026.json") as f:
    elements = json.load(f)

ENVELOPE = {"EXT_WALL", "TOP_FLOOR", "GROUND_FLOOR", "ROOF", "BASEMENT_WALL", "BASEMENT_FLOOR"}
print("=== Current Computed U-values (all archetypes) ===")
print(f"{'Archetype':14s}  {'Application':20s}  {'U-value':>8s}")
print("-" * 48)
for k, e in sorted(elements.items()):
    if e["application"] in ENVELOPE:
        print(f"{e['archetype']:14s}  {e['application']:20s}  {e['u_value']:8.4f}")

# ── BETSI unrenovated medians (from debug_uvalue_by_renovation.py results) ──
# These are per-era medians for buildings with NO component-specific renovation
print("\n\n=== BETSI Unrenovated Medians by Era ===")
print("Source: BETSI FH (FB_Klimat U-values), buildings with no FC3 renovation for that component\n")

unrenovated = {
    # Era:            wall    roof    floor   window
    "pre-1960":     (0.599,  0.314,  0.324,  2.500),
    "1950-1975":    (0.210,  0.138,  0.245,  1.900),
    "1960-1980":    (0.295,  0.138,  0.216,  1.900),
    "mixed":        (0.190,  0.136,  0.214,  2.000),
}

# CMF archetype → BETSI era mapping
archetype_era = {
    "CMF_1940_1": "pre-1960",
    "CMF_1950":   "pre-1960",
    "CMF_1960_1": "1950-1975",
    "CMF_1960_2": "1950-1975",
    "CMF_1970":   "1960-1980",
    "CMF_1980":   "1960-1980",
}

# ── Gap analysis ──
print("\n=== GAP ANALYSIS: Current vs Unrenovated BETSI Target ===\n")
print(f"{'Archetype':14s}  {'Component':14s}  {'Current':>8s}  {'Target':>8s}  {'Ratio':>7s}  {'Status'}")
print("-" * 75)

for arch, era in archetype_era.items():
    targets = unrenovated[era]
    # Map component names to target indices
    component_map = {
        "EXT_WALL": ("Wall", targets[0]),
        "TOP_FLOOR": ("Roof", targets[1]),
        "GROUND_FLOOR": ("Floor", targets[2]),
    }
    for k, e in elements.items():
        if e["archetype"] == arch and e["application"] in component_map:
            label, target = component_map[e["application"]]
            current = e["u_value"]
            ratio = current / target
            if abs(ratio - 1.0) < 0.10:
                status = "OK (<10%)"
            elif abs(ratio - 1.0) < 0.20:
                status = "Close (10-20%)"
            elif ratio > 1.0:
                status = f"TOO HIGH ({(ratio-1)*100:+.0f}%)"
            else:
                status = f"TOO LOW ({(ratio-1)*100:+.0f}%)"
            print(f"{arch:14s}  {e['application']:14s}  {current:8.3f}  {target:8.3f}  {ratio:7.2f}x  {status}")

# Window U-values come from TABULA, read from building sheet
# We know TABULA uses 2.22 for pre-1960 and 1961-75, 2.04 for 1976-85
print(f"\n{'':14s}  {'WINDOWS':14s}")
print("-" * 75)
window_tabula = {
    "CMF_1940_1": 2.22, "CMF_1950": 2.22,
    "CMF_1960_1": 2.22, "CMF_1960_2": 2.22,
    "CMF_1970": 2.22, "CMF_1980": 2.04,
}
for arch, era in archetype_era.items():
    target = unrenovated[era][3]
    current = window_tabula[arch]
    ratio = current / target
    if abs(ratio - 1.0) < 0.10:
        status = "OK (<10%)"
    elif abs(ratio - 1.0) < 0.20:
        status = "Close (10-20%)"
    elif ratio > 1.0:
        status = f"TOO HIGH ({(ratio-1)*100:+.0f}%)"
    else:
        status = f"TOO LOW ({(ratio-1)*100:+.0f}%)"
    print(f"{arch:14s}  {'WINDOW':14s}  {current:8.3f}  {target:8.3f}  {ratio:7.2f}x  {status}")
