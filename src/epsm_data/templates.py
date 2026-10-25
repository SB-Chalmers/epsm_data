"""Simple per-archetype ventilation templates and facade window-to-wall assumptions."""

import json
from functools import cache
from importlib.resources import files

from .profiles import HVACTemplate

_STANDARDS = files("epsm_data.datasets.standards")


@cache
def _table(name):
    return json.loads(_STANDARDS.joinpath(f"{name}.json").read_text(encoding="utf-8"))


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


VENTILATION_SYSTEMS = ("S", "F", "FT", "FTX")


def ventilation_template_id(category, era, state, ventilation=None):
    """Template id for a configuration and an optional observed system (S, F, FT, FTX).

    Without an observed system the era default applies. Standard keeps the existing
    system; Advanced installs FTX 0.80.
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
