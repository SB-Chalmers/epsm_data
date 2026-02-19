import json
import os
from datetime import datetime
from Classes import OpaqueMaterial2, Layer2, Components2, Element2


OUTPUT_DIR = "output"


def export_all(
    materials: list[OpaqueMaterial2],
    layers: list[Layer2],
    components: list[Components2],
    elements: list[Element2],
) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = datetime.today().strftime("%Y-%m-%d")

    files = {
        f"materials_{today}.json": {m.name: m.to_dict() for m in materials},
        f"layers_{today}.json":    {l.layer_code: l.to_dict() for l in layers},
        f"components_{today}.json":{c.name: c.to_dict() for c in components},
        f"elements_{today}.json":  {e.name: e.to_dict() for e in elements},
    }

    for filename, data in files.items():
        path = os.path.join(OUTPUT_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Exported {len(data)} records → {path}")