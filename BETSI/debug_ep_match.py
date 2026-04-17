import pandas as pd
import json

# Load Excel materials
df = pd.read_excel("Data/Material_Database.xlsx", sheet_name="Opaque_Materials")
# Load EP JSON
with open("Data/opaque_material.json") as f:
    ep = json.load(f)

# Materials used in CMF_1960_1_EXT_WALL
targets = ["brick", "mortar", "eternit_board", "plaster_board", "asphalt_board", "mineral_wool", "wooden_stud"]

for _, row in df.iterrows():
    name = str(row.get("Material Name", "")).strip()
    if name in targets:
        ep_id = str(row.get("Honeybee Identifier", "")).strip()
        hb_conf = row.get("Honeybee Match Confidence", "N/A")
        ep_data = ep.get(ep_id, {})
        print(f"\n{name}")
        print(f"  Honeybee ID:      {ep_id}")
        print(f"  HB confidence:    {hb_conf}")
        print(f"  EP conductivity:  {ep_data.get('conductivity', 'NOT FOUND')}")
        print(f"  EP thickness:     {ep_data.get('thickness', 'NOT FOUND')}")
        print(f"  EP density:       {ep_data.get('density', 'NOT FOUND')}")
        print(f"  EP type:          {ep_data.get('type', 'NOT FOUND')}")
