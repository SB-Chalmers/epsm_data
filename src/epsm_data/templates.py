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


HEAT_PUMP_TYPES = ("ground", "exhaust_air", "air_water", "air_air")


def heating_delivery_template(carrier="heat_pump", *, heat_pump_type=None, era=None):
    """The sourced heating-delivery ``HVACTemplate`` for a carrier.

    The heat-pump template gives a seasonal COP as a delivery section, so a consumer
    selects it as it selects a ventilation template. Without ``heat_pump_type`` it is
    the Swedish field average 2.75. With the building's pump type (``ground``,
    ``exhaust_air``, ``air_water`` or ``air_air``, as read from its EPC) it is the
    sourced value for that type; exhaust air also needs ``era`` (radiators before
    2006, floor heating from 2006) and falls back to the field average without it.
    Unsupported carriers or pump types raise ValueError.
    """
    table = _table("heating_delivery_v1")
    if carrier not in table["templates"]:
        raise ValueError(f"No heating delivery template for carrier: {carrier!r}")
    record = table["templates"][carrier]
    template_id, cop = record["template_id"], record["seasonal_cop"]
    notes = [record["source_locator"], record["note"], table["basis"]]
    if heat_pump_type is not None:
        if carrier != "heat_pump" or heat_pump_type not in HEAT_PUMP_TYPES:
            raise ValueError(f"Unknown heat-pump type {heat_pump_type!r}; use one of {HEAT_PUMP_TYPES}")
        typed = record["seasonal_cop_by_pump_type"][heat_pump_type]
        by_era = typed.get("seasonal_cop_by_era")
        if by_era is None or era in by_era:
            cop = typed["seasonal_cop"] if by_era is None else by_era[era]
            template_id = f"epsm.heating.heat_pump_{heat_pump_type}"
            notes = [typed["source_locator"], record["pump_type_note"], table["basis"]]
    return HVACTemplate(
        template_id=template_id,
        values={"delivery": {"heating": {
            "carrier": carrier,
            "heat_pump_cop": {"values": [cop] * 24},
            "source": template_id,
        }}},
        source_references=(table["source_uri"],),
        notes=tuple(notes),
    )


VENTILATION_SYSTEMS = ("S", "F", "FT", "FTX")


def ventilation_template_id(category, era, state, ventilation=None):
    """Ventilation template ID for a configuration, such as ``epsm.ventilation.FTX_075``.

    ``state`` ``"advanced"`` always installs FTX 0.80. Any other state (``"existing"``,
    ``"standard"`` or None for SE.07) keeps the existing system: the observed
    ``ventilation`` (S, F, FT or FTX) when given, otherwise the era default for the
    category. An observed FTX takes the recovery typical of its era: 0.75 before 1976
    (assumed retrofitted), 0.60 for 1976–2005, and the period value from 2006.
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
