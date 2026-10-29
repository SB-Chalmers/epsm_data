"""Write the bundled renovation catalogue from authored candidate definitions.

The catalogue is independent of archetype renovation states: Standard and
Advanced describe buildings that were renovated before they entered the stock,
not measures to apply. Candidates only reuse the shared LoD2 physical library
(components and window records) for what they install. Costs are never written
here; supply them as an overlay.

Run: python tools/build_renovation_catalogue.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from epsm_data.contract import QuantityDriver  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "src" / "epsm_data" / "datasets"
SERVICE_LIFE = {"insulate_wall": 50, "insulate_roof": 50, "insulate_basement": 50,
                "replace_window": 40, "upgrade_window": 25, "upgrade_ventilation": 25,
                "seal_envelope": 40, "install_pv": 30, "reduce_dhw": 15}
SERVICE_LIFE_BASIS = ("EPSM assumption: reference service lives for Swedish residential "
                      "building parts; replace with a sourced table before B4 assessment.")
INSULANTS = ("wool", "eps", "insulation", "cellulose", "fibre")
TYPICAL_WINDOW_M2 = 1.08  # 9x12 module, the unit priced by Swedish renovation price books

BIO_BASIS = ("EPSM representative open-attic / batt grade; verify lambda and density against the "
             "installed product's declaration. Carbon from the Boverket generic record, "
             "excluding biogenic storage.")
MATERIALS = {
    "renovation:material:cellulose_loose_fill": {
        "name": "Cellulose loose fill, open attic, lambda 0.040 W/(m K), 30 kg/m³",
        "conductivity": 0.040, "density": 30.0, "specific_heat": 1900.0,
        "boverket_id": "6000000137", "basis": BIO_BASIS},
    "renovation:material:wood_fibre_loose_fill": {
        "name": "Wood-fibre loose fill, open attic, lambda 0.039 W/(m K), 35 kg/m³",
        "conductivity": 0.039, "density": 35.0, "specific_heat": 2100.0,
        "boverket_id": "6000000135", "basis": BIO_BASIS},
    "renovation:material:wood_fibre_batts": {
        "name": "Wood-fibre batts, lambda 0.038 W/(m K), 50 kg/m³",
        "conductivity": 0.038, "density": 50.0, "specific_heat": 2100.0,
        "boverket_id": "6000000136", "basis": BIO_BASIS},
}
for record in MATERIALS.values():
    record.update(roughness="MediumRough", thermal_absorptance=0.9, solar_absorptance=0.7,
                  visible_absorptance=0.7)
GYPSUM, STONE_WOOL_BATTS, STONE_WOOL_BOARD = (
    "material:1fd89c413e7a4ed7", "material:8c0e602f796d38cb", "material:a224c4024cbc6c40")


def layer(name, material_id, thickness):
    return {"name": name, "thickness": thickness,
            "materials": [{"material_id": material_id, "thickness": thickness}]}


LAYERS = {
    "renovation:layer:cellulose_300": layer("Cellulose loose fill, 300 mm",
                                            "renovation:material:cellulose_loose_fill", 0.3),
    "renovation:layer:wood_fibre_loose_300": layer("Wood-fibre loose fill, 300 mm",
                                                   "renovation:material:wood_fibre_loose_fill", 0.3),
    "renovation:layer:wood_fibre_batts_70": layer("Wood-fibre batts, 70 mm",
                                                  "renovation:material:wood_fibre_batts", 0.07),
    "renovation:layer:stone_wool_batts_70": layer("Stone wool batts, 70 mm", STONE_WOOL_BATTS, 0.07),
    "renovation:layer:gypsum_13": layer("Gypsum plasterboard, 13 mm", GYPSUM, 0.013),
    "renovation:layer:stone_wool_board_100": layer("Stone wool board, 100 mm", STONE_WOOL_BOARD, 0.1),
}
COMPONENTS = {
    "renovation:component:attic_cellulose_300": {
        "name": "Attic cellulose loose fill, 300 mm", "application": "TOP_FLOOR",
        "shearing_layer": "Structure", "layers": ["renovation:layer:cellulose_300"]},
    "renovation:component:attic_wood_fibre_300": {
        "name": "Attic wood-fibre loose fill, 300 mm", "application": "TOP_FLOOR",
        "shearing_layer": "Structure", "layers": ["renovation:layer:wood_fibre_loose_300"]},
    "renovation:component:interior_wood_fibre_70_gypsum": {
        "name": "Interior wood-fibre lining, 70 mm, gypsum finish", "application": "EXT_WALL",
        "shearing_layer": "Space",
        "layers": ["renovation:layer:wood_fibre_batts_70", "renovation:layer:gypsum_13"]},
    "renovation:component:interior_stone_wool_70_gypsum": {
        "name": "Interior stone-wool lining, 70 mm, gypsum finish", "application": "EXT_WALL",
        "shearing_layer": "Space",
        "layers": ["renovation:layer:stone_wool_batts_70", "renovation:layer:gypsum_13"]},
    "renovation:component:basement_ceiling_stone_wool_100": {
        "name": "Stone wool board under the basement ceiling, 100 mm", "application": "GROUND_FLOOR",
        "shearing_layer": "Space", "layers": ["renovation:layer:stone_wool_board_100"]},
}

# (candidate_id, measure_type, role, component IDs outside-to-inside, roof topologies, options)
LAYERED = [
    ("insulate_wall.stone_wool_100", "insulate_wall", "EXT_WALL",
     ["component:172370f6bea077c1"], [], {}),
    ("insulate_wall.stone_wool_200", "insulate_wall", "EXT_WALL",
     ["component:50eec349effbca6e"], [], {}),
    ("insulate_wall.stone_wool_50_brick_facing", "insulate_wall", "EXT_WALL",
     ["component:983324a412153218"], [], {}),
    ("insulate_roof.attic_loose_glass_wool_200", "insulate_roof", "TOP_FLOOR",
     ["component:67a9e0724a681f18"], ["cold_attic"], {"target_boundaries": ["Outdoors", "Internal"]}),
    ("insulate_roof.attic_loose_stone_wool_300", "insulate_roof", "TOP_FLOOR",
     ["component:b83bab46ec6ff688"], ["cold_attic"], {"target_boundaries": ["Outdoors", "Internal"]}),
    ("insulate_roof.attic_loose_glass_wool_500", "insulate_roof", "TOP_FLOOR",
     ["component:c2126357402a00ec"], ["cold_attic"], {"target_boundaries": ["Outdoors", "Internal"]}),
    ("insulate_roof.roof_stone_wool_board_150", "insulate_roof", "ROOF",
     ["component:33e9e17f807b82bd"], ["compact"], {}),
    ("insulate_roof.roof_stone_wool_board_250", "insulate_roof", "ROOF",
     ["component:e2a8e8a67b26fcbe"], ["compact"], {}),
    ("insulate_basement.wall_stone_wool_40_gypsum", "insulate_basement", "BASEMENT_WALL",
     ["component:a3bd46f13bee5daa"], [], {}),
    ("insulate_basement.floor_eps_45_screed_50", "insulate_basement", "GROUND_FLOOR",
     ["component:3a0a0011bb08284a", "component:51a4bcd2ee5b9126"], [], {}),
    ("insulate_roof.attic_cellulose_300", "insulate_roof", "TOP_FLOOR",
     ["renovation:component:attic_cellulose_300"], ["cold_attic"], {"target_boundaries": ["Outdoors", "Internal"]}),
    ("insulate_roof.attic_wood_fibre_300", "insulate_roof", "TOP_FLOOR",
     ["renovation:component:attic_wood_fibre_300"], ["cold_attic"], {"target_boundaries": ["Outdoors", "Internal"]}),
    ("insulate_wall.interior_wood_fibre_70", "insulate_wall", "EXT_WALL",
     ["renovation:component:interior_wood_fibre_70_gypsum"], [], {"side": "interior"}),
    ("insulate_wall.interior_stone_wool_70", "insulate_wall", "EXT_WALL",
     ["renovation:component:interior_stone_wool_70_gypsum"], [], {"side": "interior"}),
    ("insulate_basement.ceiling_stone_wool_100", "insulate_basement", "GROUND_FLOOR",
     ["renovation:component:basement_ceiling_stone_wool_100"], [],
     {"side": "exterior", "target_boundaries": ["Internal"],
      "description": "Insulation fixed under the floor above an unheated basement."}),
]
WINDOWS = [
    ("replace_window.u_1_22", "window:21eac0c64cab887c"),
    ("replace_window.u_0_90", "window:2a97a2809618c594"),
    ("replace_window.u_0_76", "window:a89c0fe5b1650304"),
]

UPGRADE_WINDOW = {
    "candidate_id": "upgrade_window.insulating_glass_inner_sash",
    "measure_type": "upgrade_window",
    "name": "Low-e insulating glass unit fitted in the inner sash of a coupled window",
    "description": ("Existing coupled frames and sashes are retained and refurbished; the "
                    "inner single pane is replaced by a low-e double insulating glass unit."),
    "role": "WINDOW",
    "window_id": "renovation:window:coupled_ig_u130",
    "performance": {"window_u_w_m2k": 1.3, "shgc": 0.5},
    "typical_window_area_m2": TYPICAL_WINDOW_M2,
    "products": [{
        "product_id": "insulating_glass_unit.double_low_e",
        "description": "Double insulating glass unit (4-16-4), low-e",
        "driver": "window_area_m2", "unit": "m2", "quantity_per_driver": 0.75,
        "mass_kg_per_unit": 20.0, "boverket_id": "6000000175",
        "basis": ("Glazed share 0.75 of window area is an EPSM assumption; mass is the "
                  "Boverket resource's 20 kg/m2 area conversion."),
    }],
    "source_references": ["EPSM assumption: retrofit U 1.3 W/(m2 K) for coupled windows "
                          "with an added low-e unit; verify against product data."],
}
UPGRADE_WINDOW_RECORD = {
    "name": "Coupled window with added low-e insulating glass unit, U=1.3 W/(m² K)",
    "archetype": "renovation", "u_value": 1.3, "shgc": 0.5, "vt": 0.6, "boverket_id": None,
}
SEALING = {
    "candidate_id": "seal_envelope.renovated_joints",
    "measure_type": "seal_envelope",
    "name": "Tightened joints at renovated windows and walls",
    "description": ("Window replacement and wall insulation are assumed to meet new-construction "
                    "airtightness where they renovate; sealant and tape are part of the host "
                    "work item, so no product or cost is added."),
    "infiltration_reduction": 0.2,
    "source_references": ["EPSM nominal default: 20 % lower envelope infiltration when the whole "
                          "envelope is renovated, scaled by the renovated share. Replace with "
                          "measured retrofit airtightness when available."],
}
TERMINAL_PRODUCTS = [
    {"product_id": "terminal.supply", "description": "Supply air terminal",
     "driver": "supply_terminal_count", "unit": "item", "mass_kg_per_unit": 0.5,
     "boverket_id": "6000000221", "basis": "Proxy: assessed as galvanised steel."},
    {"product_id": "terminal.exhaust", "description": "Exhaust air valve",
     "driver": "exhaust_terminal_count", "unit": "item", "mass_kg_per_unit": 0.5,
     "boverket_id": "6000000221", "basis": "Proxy: assessed as galvanised steel."},
]
DUCT = {"product_id": "duct.galvanised_steel_d160", "description": "Spiral duct, galvanised steel, Ø160",
        "driver": "duct_length_m", "unit": "m", "mass_kg_per_unit": 2.6, "boverket_id": "6000000221",
        "basis": "0.6 mm wall, 2.37 kg/m plus 10 % fittings and hangers."}
LAYOUT_BASIS = ("BBR 6:251 minimum outdoor airflow 0.35 l/(s m2). Terminal densities, branch and "
                "main duct lengths, riser spacing and unit size are EPSM design assumptions for "
                "multi-family retrofits; calibrate against project data.")
BALANCED_LAYOUT = {
    "mechanical_vent_l_s_m2": 0.35, "supply_area_per_terminal_m2": 15.0,
    "exhaust_area_per_terminal_m2": 25.0, "branch_length_m": 4.0,
    "main_duct_m_per_m2": 0.08, "riser_area_m2": 120.0, "ahu_max_airflow_l_s": 300.0,
    "new_duct_systems": {"S": 2, "F": 1, "FT": 0, "FTX": 0},
    "new_terminals": {"S": ["supply", "exhaust"], "F": ["supply"], "FT": [], "FTX": []},
    "basis": LAYOUT_BASIS,
}


def ftx(effectiveness, template):
    percent = round(effectiveness * 100)
    return {
        "candidate_id": f"upgrade_ventilation.ftx_{percent:03d}",
        "measure_type": "upgrade_ventilation",
        "name": f"Balanced ventilation with heat recovery (FTX), effectiveness {effectiveness:.2f}",
        "description": ("Central air handling units with heat recovery, new supply and exhaust "
                        "ductwork as required by the existing system, and room terminals."),
        "template_id": template,
        "airflow": {"natural_exchange_ach": 0.0},
        "from_ventilation": ["S", "F", "FT", "FTX"],
        "performance": {"sensible_recovery_effectiveness": effectiveness,
                        "mechanical_vent_l_s_m2": 0.35},
        "layout": BALANCED_LAYOUT,
        "products": [DUCT,
                     {"product_id": "ahu.ftx_300", "description": "Air handling unit with heat recovery, 300 l/s",
                      "driver": "ahu_count", "unit": "item", "mass_kg_per_unit": 280.0,
                      "boverket_id": "6000000221",
                      "basis": ("Proxy: unit mass assessed as galvanised steel; no Boverket generic record "
                                "exists for air handling units. Replace with an EPD.")},
                     *TERMINAL_PRODUCTS],
        "source_references": [f"epsm_data:ventilation_templates.json ({template.rsplit('.', 1)[1]})"],
    }


EXHAUST = {
    "candidate_id": "upgrade_ventilation.f",
    "measure_type": "upgrade_ventilation",
    "name": "Mechanical exhaust ventilation (F) replacing self-draught",
    "description": ("Roof-mounted exhaust fans on new exhaust ductwork; outdoor air enters through "
                    "trickle vents. The low-cost alternative to FTX for self-draught buildings."),
    "template_id": "epsm.ventilation.F",
    "airflow": {"natural_exchange_ach": 0.0},
    "from_ventilation": ["S"],
    "performance": {"mechanical_vent_l_s_m2": 0.35},
    "layout": BALANCED_LAYOUT | {
        "new_duct_systems": {"S": 1, "F": 0, "FT": 0, "FTX": 0},
        "new_terminals": {"S": ["exhaust"], "F": [], "FT": [], "FTX": []}},
    "products": [DUCT,
                 {"product_id": "fan.exhaust_300", "description": "Roof exhaust fan, 300 l/s",
                  "driver": "ahu_count", "unit": "item", "mass_kg_per_unit": 45.0,
                  "boverket_id": "6000000221",
                  "basis": "Proxy: fan mass assessed as galvanised steel. Replace with an EPD."},
                 TERMINAL_PRODUCTS[1]],
    "source_references": ["epsm_data:ventilation_templates.json (F)"],
}
PV_SOURCE = "IEA PVPS National Survey Report Sweden 2024, turnkey price excl. VAT, 10-100 kW"
PV = {
    "candidate_id": "install_pv.roof_south_15",
    "measure_type": "install_pv",
    "name": "Roof PV, due south, 15° tilt",
    "description": ("Mono-Si array on 80 % of a flat roof's footprint or 30 % of a pitched roof's "
                    "surface, at 130 W per m2 of roof used, with 12 % system losses."),
    "pv": {"tilt_deg": 15.0, "azimuth_deg": 180.0, "module_w_m2": 130.0,
           "system_losses_pct": 12.0, "flat_roof_share": 0.8, "pitched_roof_share": 0.3,
           "basis": ("EPSM defaults. 130 W/m2 of roof used is conservative against modern mono-Si "
                     "modules (about 209 W/m2 of module, IEA PVPS T12 2023) and covers spacing "
                     "and setbacks.")},
    "products": [
        {"product_id": "pv.module_mono_si", "description": "Mono-Si PV modules",
         "driver": "pv_capacity_kwp", "unit": "m2", "quantity_per_driver": round(1000 / 209, 3),
         "mass_kg_per_unit": 23.0, "boverket_id": "6000000203",
         "basis": ("Module area at 209 W/m2 (20.9 % efficiency, IEA PVPS T12 2023); Boverket "
                   "6000000203 is stated per m2 of module.")},
        {"product_id": "pv.balance_of_system", "description": "Inverter, mounting and cabling, per kWp",
         "driver": "pv_capacity_kwp", "unit": "item",
         "carbon_reference": {
             "identifier": "epsm-derived:pv.balance_of_system",
             "name": "PV balance of system (inverter, mounting, cabling), per kWp",
             "url": ("https://iea-pvps.org/wp-content/uploads/2024/05/"
                     "Slides_IEA-PVPS-T12_Fact-Sheet-update-2023_v2.0.pdf"),
             "method": "Life-cycle GWP from IEA PVPS Task 12 harmonised LCA, reported as A1-A3",
             "unit": "item", "modules": {"A1A3": 460.0, "A4": None, "A5": None},
             "notes": ["Derived: 3 kWp rooftop, Europe; system 35.8 minus module 20.2 g CO2e/kWh "
                       "at 976 kWh/kWp over 30 years. A life-cycle value including one inverter "
                       "replacement, used as A1-A3. One item is one kWp."]},
         "basis": "No Boverket generic record exists for inverters or mounting."},
    ],
    "cost": {"currency": "SEK", "price_year": 2024, "items": [
        {"category": "material", "rate": 7320.0, "driver": "pv_capacity_kwp",
         "description": "Modules, inverter, mounting and electronics", "source": PV_SOURCE},
        {"category": "labour", "rate": 3981.0, "driver": "pv_capacity_kwp",
         "description": "Installation", "source": PV_SOURCE},
        {"category": "overhead", "rate": 799.0, "driver": "pv_capacity_kwp",
         "description": "Other costs", "source": PV_SOURCE}],
        "source_references": [PV_SOURCE,
                              "IEA PVPS NSR Sweden 2023 Table 11: villa cost split 60.5/32.9/6.6 %"],
        "notes": ["12,100 SEK/kWp gross before subsidy; split by the only published (villa) cost "
                  "structure. 100-250 kW systems averaged 9,400 SEK/kWp."]},
    "source_references": [PV_SOURCE],
}
DHW_COST_SOURCE = "SBUF 11488 (NCC Teknik, 2009): 6,300 SEK per apartment for shower, basin and kitchen fittings"
DHW = {
    "candidate_id": "reduce_dhw.low_flow_fittings",
    "measure_type": "reduce_dhw",
    "name": "Low-flow mixers and shower heads",
    "description": "Shower, washbasin and kitchen mixers replaced with energy-class A low-flow fittings.",
    "dhw_reduction": 0.25,
    "products": [
        {"product_id": "dhw.low_flow_fitting_set", "description": "Low-flow fitting set, per m2 Atemp",
         "driver": "floor_area_m2", "unit": "m2", "mass_kg_per_unit": 0.042,
         "carbon_reference": {
             "identifier": "epsm-derived:dhw.low_flow_fitting_set",
             "name": "Low-flow mixer set, per m2 Atemp",
             "url": ("https://api.environdec.com/api/v1/EPDLibrary/Files/"
                     "4b820f7d-0204-4462-f105-08daa04473b0/Data"),
             "method": "EN 15804+A2 GWP-GHG A1-A3 of two product EPDs, combined by EPSM",
             "unit": "m2", "modules": {"A1A3": 0.2, "A4": None, "A5": None},
             "notes": ["Three mixers per 100 m2 apartment: Gustavsberg Atlantic basin mixer EPD "
                       "S-P-07034 (4.96 kg CO2e/kg x 1.21 kg) for basin and kitchen, FM Mattsson "
                       "MMIX II EPD-IES-0014428 (4.51 kg CO2e/kg x 1.78 kg) for shower: 20 kg "
                       "CO2e per apartment."]},
         "basis": "Removed fittings are not inventoried."}],
    "cost": {"currency": "SEK", "price_year": 2026, "items": [
        {"category": "subcontractor", "rate": 90.0, "driver": "floor_area_m2",
         "description": "Fittings supplied and installed by a plumber", "source": DHW_COST_SOURCE}],
        "source_references": [DHW_COST_SOURCE],
        "notes": ["63 SEK/m2 Atemp at 2009 prices (100 m2 apartments) escalated by an assumed "
                  "45 % to 2026; not index-based. VAT treatment of the source is not stated."]},
    "source_references": [
        "RISE/E2B2 field study, five rental blocks in Borås: 28 % less hot water, no decay; "
        "0.25 used as a rounded-down default",
        "SBUF 11488: 20-40 % hot-water saving"],
}
VENTILATION = [ftx(0.8, "epsm.ventilation.FTX_080"), ftx(0.75, "epsm.ventilation.FTX_075"), EXHAUST]


PAYLOAD_KIND = {"insulate_wall": "layer_addition", "insulate_roof": "layer_addition",
                "insulate_basement": "layer_addition", "replace_window": "window_swap",
                "upgrade_window": "window_swap", "upgrade_ventilation": "system_swap",
                "install_pv": "pv_array", "reduce_dhw": "dhw_reduction",
                "seal_envelope": "airtightness"}
PAYLOAD_FIELDS = {
    "layer_addition": ("role", "component_ids", "side", "target_boundaries", "roof_topologies"),
    "window_swap": ("window_id", "typical_window_area_m2"),
    "system_swap": ("template_id", "layout", "airflow", "from_ventilation"),
    "dhw_reduction": ("fraction",),
    "airtightness": ("nominal_reduction",),
}
RENAMED = {"dhw_reduction": "fraction", "infiltration_reduction": "nominal_reduction"}


def with_payload(record):
    """Move what a candidate installs into its typed payload (schema 2)."""
    record = {RENAMED.get(k, k): v for k, v in record.items()}
    kind = PAYLOAD_KIND[record["measure_type"]]
    payload = dict(record.pop("pv")) if kind == "pv_array" else {}
    for name in PAYLOAD_FIELDS.get(kind, ()):
        if name in record:
            payload[name] = record.pop(name)
    record.pop("role", None)
    return {**record, "payload": {"kind": kind, **payload}}


def main():
    lod2 = json.loads((ROOT / "lod2" / "catalogue.json").read_text(encoding="utf-8"))
    components = lod2["components"] | {
        cid: dict(c, layers=[{"layer_id": lid} for lid in c["layers"]]) for cid, c in COMPONENTS.items()}
    layers, materials = lod2["layers"] | LAYERS, lod2["materials"]
    candidates = []
    for candidate_id, measure, role, component_ids, topologies, options in LAYERED:
        stack = [layers[s["layer_id"]] for c in component_ids for s in components[c]["layers"]]
        if any(components[c]["application"] != role for c in component_ids):
            raise ValueError(f"{candidate_id}: components must apply to {role}")
        candidates.append({
            "candidate_id": candidate_id, "measure_type": measure, "role": role,
            "name": " + ".join(layer["name"] for layer in stack),
            "component_ids": component_ids, "roof_topologies": topologies,
            "performance": {"nominal_added_insulation_m": round(sum(
                layer["thickness"] for layer in stack
                if any(term in layer["name"].casefold() for term in INSULANTS)), 4)},
            "source_references": ["Physical records: " + ", ".join(component_ids)],
            **({"companions": [SEALING["candidate_id"]]} if measure == "insulate_wall" else {}),
            **options})
    for candidate_id, window_id in WINDOWS:
        candidates.append({
            "candidate_id": candidate_id, "measure_type": "replace_window", "role": "WINDOW",
            "name": "New window: " + materials[window_id]["epsm_material_name"],
            "window_id": window_id, "typical_window_area_m2": TYPICAL_WINDOW_M2,
            "companions": [SEALING["candidate_id"]],
            "source_references": [f"epsm_data LoD2 window record {window_id}"]})
    candidates.extend((UPGRADE_WINDOW, *VENTILATION, PV, DHW, SEALING))
    for record in candidates:
        record["service_life_years"] = SERVICE_LIFE[record["measure_type"]]
        record["notes"] = [SERVICE_LIFE_BASIS]
    candidates = [with_payload(record) for record in candidates]
    result = {
        "schema_version": 2,
        "dataset_id": "epsm.renovation/1",
        "lod2_dataset_id": lod2["dataset_id"],
        "measure_types": ["insulate_wall", "insulate_roof", "insulate_basement",
                          "replace_window", "upgrade_window", "upgrade_ventilation",
                          "install_pv", "reduce_dhw", "seal_envelope"],
        "quantity_drivers": [d.value for d in QuantityDriver],
        "candidates": candidates,
        "windows": {UPGRADE_WINDOW["window_id"]: UPGRADE_WINDOW_RECORD},
        "materials": MATERIALS,
        "layers": LAYERS,
        "components": COMPONENTS,
    }
    target = ROOT / "renovation" / "catalogue.json"
    target.parent.mkdir(exist_ok=True)
    (target.parent / "__init__.py").touch()
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(candidates)} candidates -> {target}")


if __name__ == "__main__":
    main()
