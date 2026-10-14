"""Reusable Core-neutral operating and HVAC input templates.

Data owns named inputs and their sources. Consumers construct physics objects,
expand calendars, and validate the requirements of a particular simulation.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from types import MappingProxyType

from .domain.editing import Editable


def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(v) for v in value)
    return value


def _plain(value):
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    return value


def _validate_template(record, identity):
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError("Template identity must be nonempty")
    if not isinstance(record.values, Mapping):
        raise ValueError("Template values must be a mapping")
    try:
        json.dumps(_plain(record.values), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Template inputs must be finite JSON-compatible data") from exc
    for field in ("source_references", "notes"):
        value = tuple(getattr(record, field))
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError(f"{field} must contain nonempty text")
        object.__setattr__(record, field, value)
    object.__setattr__(record, "values", _freeze(record.values))


@dataclass(frozen=True)
class OperatingProfile(Editable):
    profile_id: str
    values: Mapping
    source_references: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self):
        _validate_template(self, self.profile_id)

    def to_dict(self):
        return {"profile_id": self.profile_id, "values": _plain(self.values),
                "source_references": list(self.source_references), "notes": list(self.notes)}

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass(frozen=True)
class HVACTemplate(Editable):
    template_id: str
    values: Mapping
    source_references: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self):
        _validate_template(self, self.template_id)

    def to_dict(self):
        return {"template_id": self.template_id, "values": _plain(self.values),
                "source_references": list(self.source_references), "notes": list(self.notes)}

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


STANDARD_PROFILES = (
    "sveby_residential_v2", "sveby_office_v1", "sveby_school_v1",
    "dhw_epc_normal_use_v1", "generic_other",
)


def load_standard_record(name):
    """Return a defensive record; source edition IDs are provenance, not release chains."""
    if name not in STANDARD_PROFILES:
        raise ValueError(f"Unknown named profile: {name}")
    resource = files("epsm_data.datasets.standards").joinpath(f"{name}.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def load_operating_profile(name):
    values = load_standard_record(name)
    return OperatingProfile(values["profile_id"], values,
                            (values["source_uri"],), tuple(values.get("notes", ())))


def load_generic_other_template():
    """Plain inputs consumed by Core's calendar and UseSpec factory."""
    return load_standard_record("generic_other")
