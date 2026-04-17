"""Search EP JSON for better matches for problematic materials."""
import json

with open("Data/opaque_material.json") as f:
    data = json.load(f)


def search(label, k_lo, k_hi, density_lo=None, density_hi=None):
    print(f"\n=== {label} (k={k_lo}-{k_hi}) ===")
    hits = []
    for name, p in sorted(data.items()):
        if p.get("type") != "EnergyMaterial":
            continue
        k = p.get("conductivity", 0)
        rho = p.get("density", 0)
        if k_lo <= k <= k_hi:
            if density_lo and density_hi:
                if not (density_lo <= rho <= density_hi):
                    continue
            hits.append((name, k, rho, p.get("specific_heat", 0)))
    hits.sort(key=lambda x: x[1])
    for n, k, rho, cp in hits[:15]:
        print(f"  {n:<55} k={k:.4f}  rho={rho:.0f}  cp={cp:.0f}")
    if not hits:
        print("  (no matches)")


# 1. Lightweight concrete: k=0.3-1.0, density 500-1800
search("LIGHTWEIGHT CONCRETE", 0.3, 1.0, 500, 1800)

# 2. Wood wool board: k=0.05-0.12, density 200-700
search("WOOD WOOL BOARD", 0.050, 0.120, 200, 700)

# 3. Concrete mixed with sawdust: k=0.3-0.8, density 800-1600
search("CONCRETE MIXED WITH SAWDUST", 0.3, 0.8, 800, 1600)

# 4. Coke ash: k=0.20-0.50, density 400-1200
search("COKE ASH", 0.20, 0.50, 400, 1200)

# 5. Cellular plastic: k=0.025-0.045
search("CELLULAR PLASTIC", 0.025, 0.045)

# 6. Gravel: k=0.5-2.0, density 1400-2200
search("GRAVEL", 0.5, 2.0, 1400, 2200)
