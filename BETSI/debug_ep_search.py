import json

with open("Data/opaque_material.json") as f:
    data = json.load(f)

keywords = ["cement", "fiber", "fibre", "board", "sheet", "siding", "slate", "ite", "calcium"]

for name, entry in sorted(data.items()):
    if entry.get("type") != "EnergyMaterial":
        continue
    k = entry.get("conductivity", 0)
    d = entry.get("density", 0)
    nl = name.lower()
    if any(w in nl for w in keywords):
        print(f"  {name:50s}  k={k:.3f}  density={d:.0f}  t={entry.get('thickness',0):.4f}")
