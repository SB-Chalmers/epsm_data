"""JSON exporter.

Serializes domain objects to dated JSON files.
"""

import json
import os
from datetime import datetime
from epsm_data.domain.material import OpaqueMaterial
from epsm_data.domain.layer import Layer
from epsm_data.domain.component import Components
from epsm_data.domain.element import Elements, WindowElement
from epsm_data.domain.building import BuildingArchetype


def export_all(
    materials: list[OpaqueMaterial],
    layers: list[Layer],
    components: list[Components],
    elements: list[Elements],
    buildings: list[BuildingArchetype],
    window_elements: list[WindowElement],
    output_dir: str = "output",
) -> None:
    """Serialize all domain objects to dated JSON files in the output directory."""
    from epsm_data.domain.element import WindowElement as WE
    os.makedirs(output_dir, exist_ok=True)
    today = datetime.today().strftime("%d-%m-%Y")

    files = {
        f"materials_{today}.json":        {m.name: m.to_dict() for m in materials},
        f"layers_{today}.json":           {l.layer_code: l.to_dict() for l in layers},
        f"components_{today}.json":       {c.name: c.to_dict() for c in components},
        f"elements_{today}.json":         {e.name: e.to_dict() for e in elements},
        f"window_elements_{today}.json":  {w.name: w.to_dict() for w in window_elements},
        f"buildings_{today}.json":        {b.archetype_id: b.to_dict() for b in buildings},
    }

    for filename, data in files.items():
        path = os.path.join(output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Exported {len(data)} records -> {path}")