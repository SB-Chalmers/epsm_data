"""Simple per-archetype system templates and facade window-to-wall assumptions."""

import json
from functools import cache
from importlib.resources import files

from .profiles import HVACTemplate


@cache
def _table(name):
    resource = files("epsm_data.datasets.profiles").joinpath(f"{name}.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def ventilation_templates():
    """All ventilation templates by id, as airflow-only ``HVACTemplate`` records."""
    table = _table("ventilation_templates")
    return {
        identifier: HVACTemplate(
            template_id=identifier,
            values={"airflow": dict(record["airflow"])},
            source_references=("epsm_data:ventilation_templates.json",),
            notes=(record["note"], table["basis"]),
        )
        for identifier, record in table["templates"].items()
    }


def heating_delivery_template(carrier="heat_pump"):
    """The sourced heating-delivery ``HVACTemplate`` for a carrier.

    The heat-pump template gives the Swedish field-average seasonal COP as a
    delivery section, so a consumer selects it as it selects a ventilation
    template. Unsupported carriers raise ValueError.
    """
    table = _table("heating_delivery_v1")
    if carrier not in table["templates"]:
        raise ValueError(f"No heating delivery template for carrier: {carrier!r}")
    record = table["templates"][carrier]
    cop = record["seasonal_cop"]
    return HVACTemplate(
        template_id=record["template_id"],
        values={"delivery": {"heating": {
            "carrier": carrier,
            "heat_pump_cop": {"values": [cop] * 24},
            "source": record["template_id"],
        }}},
        source_references=(table["source_uri"],),
        notes=(record["source_locator"], record["note"], table["basis"]),
    )


VENTILATION_SYSTEMS = ("S", "F", "FT", "FTX")


def ventilation_template_id(category, era, state, ventilation=None):
    """Ventilation template ID for a configuration, such as ``epsm.ventilation.FTX_075``.

    ``state`` ``"advanced"`` always installs FTX 0.80. Any other state (``"existing"``,
    ``"standard"`` or None for SE.07) keeps the existing system: the observed
    ``ventilation`` (S, F, FT or FTX) when given, otherwise the era default for the
    category. An observed FTX takes the recovery typical of its era: 0.75 before 1976
    (assumed retrofitted), 0.60 for 1976–2005 and the period value from 2006.
    """
    table = _table("ventilation_templates")
    if category not in table["default_by_era"]:
        raise ValueError(f"No ventilation assignment for category: {category}")
    if ventilation is not None and ventilation not in VENTILATION_SYSTEMS:
        raise ValueError(f"Unknown ventilation system {ventilation!r}; use one of {VENTILATION_SYSTEMS}")
    rule = table["renovation"].get(state, "existing")
    if rule != "existing":
        key = rule
    elif ventilation is None:
        key = table["default_by_era"][category][era]
    elif ventilation == "FTX":
        key = table["observed_ftx_by_era"][era]
    else:
        key = ventilation
    return f"epsm.ventilation.{key}"


def facade_assumptions(category):
    """Default and N/E/S/W window-to-wall ratios with their basis for a building type."""
    table = _table("facade_assumptions")
    if category not in table["types"]:
        raise ValueError(f"No facade assumptions for category: {category}")
    record = table["types"][category]
    return {
        "default_wwr": record["default_wwr"],
        "wwr_by_orientation": dict(record["wwr_by_orientation"]),
        "orientation_rule": table["orientation_rule"],
        "basis": record["basis"],
        "tier": record["tier"],
    }
