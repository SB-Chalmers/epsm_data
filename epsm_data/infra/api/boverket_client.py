"""Boverket climate database API client.

Fetches material resources from the Boverket Klimatdatabas v2 API
and parses them into domain EmbodiedCarbon objects.
"""

from __future__ import annotations

import logging
import time

import certifi
import requests

from epsm_data.domain.material import EmbodiedCarbon

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.boverket.se/klimatdatabas/api/Klimat/v2/GetAllResources"
_DEFAULT_TIMEOUT = 30  # seconds
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2.0  # seconds, doubled each retry


def fetch_all_materials(
    db_version: str = "latest",
    culture: str = "en",
    response_type: str = "json",
    timeout: int = _DEFAULT_TIMEOUT,
) -> list[dict]:
    """Fetch all material resources from the Boverket API.

    Returns a list of raw resource dicts (each with ``ResourceId``).
    Retries up to 3 times on transient failures.
    """
    url = f"{_BASE_URL}/{db_version}/{culture}/{response_type}"
    logger.info("Fetching resources from: %s", url)

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.get(url, verify=certifi.where(), timeout=timeout)
            response.raise_for_status()
            data = response.json()
            raw_list = data.get("Resources", []) if isinstance(data, dict) else data
            results = [m for m in raw_list if isinstance(m, dict) and "ResourceId" in m]
            logger.info("Fetched %d material resources", len(results))
            return results
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BACKOFF * attempt
                logger.warning(
                    "Attempt %d/%d failed (%s), retrying in %.1fs",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    wait,
                )
                time.sleep(wait)
            else:
                logger.error("All %d attempts failed", _MAX_RETRIES)

    raise last_exc  # type: ignore[misc]


def parse_embodied_carbon(material_json: dict, display_name: str) -> EmbodiedCarbon:
    """Parse a raw Boverket resource dict into an EmbodiedCarbon domain object."""
    data_items = {
        item["PropertyCode"]: item for item in material_json.get("DataItems", [])
    }
    gwp = data_items.get("GWP-GHG AR4", {})
    values = {
        dv["DataModuleCode"]: dv["Value"] for dv in gwp.get("DataValueItems", [])
    }
    conversion_factor = next(
        (c["Value"] for c in material_json.get("Conversions", []) if c["Field"] == "Volume"),
        1.0,
    )
    return EmbodiedCarbon(
        name=display_name,
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


def build_resource_lookup(resources: list[dict]) -> dict[str, dict]:
    """Build a ResourceId -> resource dict lookup from the API response."""
    return {str(r["ResourceId"]): r for r in resources}
