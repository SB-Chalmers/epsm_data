import requests
import certifi
from Classes import EmbodiedCarbon2
# API calls + parse_material_api

def fetch_all_materials(db_version="latest", culture="en", response_type="json") -> list[dict]:
    url = f"https://api.boverket.se/klimatdatabas/api/Klimat/v2/GetAllResources/{db_version}/{culture}/{response_type}"
    print(f"Fetching resources from: {url}")
    response = requests.get(url, verify=certifi.where())
    response.raise_for_status()
    data = response.json()
    raw_list = data.get("Resources", []) if isinstance(data, dict) else data
    return [m for m in raw_list if isinstance(m, dict) and "ResourceId" in m]


def parse_material_api(material_json: dict, excel_name: str) -> EmbodiedCarbon2:
    data_items = {item["PropertyCode"]: item for item in material_json.get("DataItems", [])}
    gwp = data_items.get("GWP-GHG AR4", {})
    values = {dv["DataModuleCode"]: dv["Value"] for dv in gwp.get("DataValueItems", [])}
    conversion_factor = next(
        (c["Value"] for c in material_json.get("Conversions", []) if c["Field"] == "Volume"),
        1.0
    )
    return EmbodiedCarbon2(
        name=excel_name,
        boverket_name=material_json.get("Name"),
        resource_id=str(material_json.get("ResourceId")),
        A1_A3_conservative=values.get("A1-A3 Conservative"),
        A1_A3_typical=values.get("A1-A3 Typical"),
        A4_transport=values.get("A4"),
        A5_conservative=values.get("A5.1"),
        conservative_factor=material_json.get("ConservativeDataConversionFactor"),
        conversion_factor=conversion_factor,
        technical_service_life=material_json.get("RefServiceLifeNormal"),
        biogenic_carbon=material_json.get("CalculatedBiogenicCarbon"),
    )