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


def ventilation_template_id(category, era, state):
    """Template id for a catalogue configuration; Standard keeps the existing system."""
    table = _table("ventilation_templates")
    if category not in table["assignment"]:
        raise ValueError(f"No ventilation assignment for category: {category}")
    rule = table["renovation"].get(state, "existing")
    key = table["assignment"][category][era] if rule == "existing" else rule
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
