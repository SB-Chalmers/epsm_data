"""Boverket API client placeholder.

Expected responsibilities:
- API fetch and retry logic.
- Response normalization.
- Transport-level error handling.
"""

import time
import requests
import certifi
from epsm_data.domain.material import EmbodiedCarbon

def fetch_material_resources(db_version="latest", culture="en", response_type="json", retries=3) -> list[dict]:
    """Fetch all material resources from the Boverket Klimatdatabas API.
    Retries on failure with backoff. Raises on final attempt.

    Args:
        db_version: Database version to query (default "latest").
        culture: Language/locale for response (default "en").
        response_type: Response format (default "json").
        retries: Number of attempts before raising (default 3).

    Returns:
        List of raw material dicts, each containing a "ResourceId" key.

    Raises:
        requests.RequestException: If all retry attempts fail.
    """
    url = f"https://api.boverket.se/klimatdatabas/api/Klimat/v2/GetAllResources/{db_version}/{culture}/{response_type}"
    for attempt in range(retries):
        try:
            response = requests.get(url, verify=certifi.where(), timeout=10)
            response.raise_for_status()
            data = response.json()
            raw_list = data.get("Resources", []) if isinstance(data, dict) else data
            return [m for m in raw_list if isinstance(m, dict) and "ResourceId" in m]
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # exponential backoff
            else:
                raise


def parse_material_api(material_json: dict, excel_name: str) -> EmbodiedCarbon:
    """Parse a raw Boverket API material response into an EmbodiedCarbon instance.

    Extracts GWP-GHG AR4 values (A1-A3, A4, A5) and volume conversion factor
    from the nested API response structure.

    Args:
        material_json: Raw material dict as returned by the Boverket API,
                       expected to contain "DataItems" and "Conversions" keys.
        excel_name: Human-readable material name from the Excel database,
                    used as the EmbodiedCarbon display name.

    Returns:
        EmbodiedCarbon instance populated with lifecycle carbon data.

    Note: 
        If expected fields change in the API response, this function may need to be reworked to match. 
    """
    data_items = {item["PropertyCode"]: item for item in material_json.get("DataItems", [])}
    gwp = data_items.get("GWP-GHG AR4", {})
    values = {dv["DataModuleCode"]: dv["Value"] for dv in gwp.get("DataValueItems", [])}
    conversion_factor = next(
        (c["Value"] for c in material_json.get("Conversions", []) if c["Field"] == "Volume"),
        1.0
    )
    return EmbodiedCarbon(
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
