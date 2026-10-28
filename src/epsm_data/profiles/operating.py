"""Reusable Core-neutral operating and HVAC input templates.

Data owns named inputs and their sources. Consumers construct physics objects,
expand calendars, and validate the requirements of a particular simulation.
"""

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from types import MappingProxyType

from ..domain.editing import Editable

logger = logging.getLogger(__name__)


def _representation(record, identity):
    label = repr(identity)
    if len(label) > 80:
        label = repr(identity[:8] + "…")
    if len(label) > 80:
        label = "'…'"
    return f"{type(record).__name__}(id={label}, inputs={len(record.values)}, sources={len(record.source_references)})"


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


@dataclass(frozen=True, repr=False)
class OperatingProfile(Editable):
    """Portable operating assumptions, with their sources and completion notes.

    Values are finite JSON-compatible inputs, frozen defensively on construction.
    Standard records retain their source schema. Custom profiles may supply a
    ``building_assumptions`` mapping; Core owns its physical validation and
    conversion. Construction and inspection perform no I/O.
    """

    profile_id: str
    values: Mapping
    source_references: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self):
        _validate_template(self, self.profile_id)

    def __deepcopy__(self, memo):
        # All JSON containers and text sequences are frozen on construction.
        return self

    def to_dict(self):
        """Return a detached JSON-compatible record, without writing files."""
        return {
            "profile_id": self.profile_id,
            "values": _plain(self.values),
            "source_references": list(self.source_references),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data):
        """Restore a portable profile without loading a standard or catalogue."""
        return cls(**data)

    def __repr__(self):
        return _representation(self, self.profile_id)

    __str__ = __repr__

    def summary(self):
        """Inspect complete loaded inputs and requirements as detached data."""
        return self.to_dict()


@dataclass(frozen=True, repr=False)
class HVACTemplate(Editable):
    """Portable, immutable system inputs; Core owns installed-system validation."""

    template_id: str
    values: Mapping
    source_references: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self):
        _validate_template(self, self.template_id)

    def __deepcopy__(self, memo):
        # All JSON containers and text sequences are frozen on construction.
        return self

    def to_dict(self):
        """Return a JSON-compatible mapping."""
        return {
            "template_id": self.template_id,
            "values": _plain(self.values),
            "source_references": list(self.source_references),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild a template from ``to_dict`` output."""
        return cls(**data)

    def __repr__(self):
        return _representation(self, self.template_id)

    __str__ = __repr__

    def summary(self):
        """Inspect complete loaded system inputs without I/O."""
        return self.to_dict()


STANDARD_PROFILES = (
    "sveby_residential_v2",
    "sveby_office_v1",
    "sveby_school_v1",
    "dhw_epc_normal_use_v1",
    "generic_other",
    "measured_use_v1",
)

_IDENTITIES = dict(
    zip(
        STANDARD_PROFILES,
        (
            "sveby.residential.v2.0.2024-11-11",
            "sveby.office.v1.0.2012-10-10",
            "sveby.school.v1.0.2016-05-16",
            "ben.dhw.normal_use.v1",
            "epsm.generic_other.v1",
            "epsm.measured_use.v1",
        ),
    )
)


def load_standard_record(name):
    """Read one bundled JSON record, validating source identity and structure.

    Reads packaged files only, never the source URI. Returns detached plain data.
    Unknown names or malformed records raise ValueError; absent package files
    raise FileNotFoundError. Source editions are provenance, not release chains.
    """
    if name not in STANDARD_PROFILES:
        raise ValueError(f"Unknown named profile: {name}")
    resource = files("epsm_data.datasets.profiles").joinpath(f"{name}.json")
    record = json.loads(resource.read_text(encoding="utf-8"))
    if (
        not isinstance(record, dict)
        or record.get("profile_id") != _IDENTITIES[name]
        or not isinstance(record.get("source_uri"), str)
        or not record["source_uri"]
    ):
        raise ValueError(f"Bundled profile {name!r} has an unexpected source identity")
    if name.startswith("sveby_") and (
        record.get("schema_version") != 1
        or not isinstance(record.get("use"), dict)
        or not isinstance(record.get("applicability"), dict)
        or not isinstance(record.get("requirements"), list)
    ):
        raise ValueError(f"Bundled profile {name!r} has an unsupported structure")
    # Use the same finite/portable boundary as custom definitions.
    OperatingProfile(record["profile_id"], record)
    logger.debug("Loaded operating definition %s", record["profile_id"])
    return record


def load_operating_profile(name):
    """Read a named immutable definition from packaged data, with no Core import.

    The explicit ``generic_other`` record is a labelled screening assumption.
    BEN's aggregate record is inspectable here; use ``select_dhw_profile`` for
    a type-specific coefficient and source locator.
    """
    values = load_standard_record(name)
    return OperatingProfile(
        values["profile_id"], values, (values["source_uri"],), tuple(values.get("notes", ()))
    )


def load_generic_other_template():
    """Plain inputs consumed by Core's calendar and UseSpec factory."""
    return load_standard_record("generic_other")


def available_operating_profiles():
    """Read the immutable operating-profile index and applicability metadata.

    Keys are names accepted by :func:`load_operating_profile`. Each value is a
    portable definition whose ``values`` includes applicability and requirements.
    BEN DHW and measured use are separate explicit selections, not complete
    operating profiles. This reads four packaged records; no catalogue, network
    or Core is needed.
    """
    return MappingProxyType(
        {
            name: load_operating_profile(name)
            for name in STANDARD_PROFILES
            if name not in ("dhw_epc_normal_use_v1", "measured_use_v1")
        }
    )


def select_operating_profile(building_type, *, standard="sveby", version=None, era=None):
    """Read a supported operating definition for an explicitly selected use.

    Supports single_family/multi_family (residential 2), office (1) and school
    (1). Version accepts the source major edition, e.g. ``"2"`` or ``"2.0"``.
    A small-house selection records Sveby's permitted residential fallback.
    Unsupported uses, standards and versions raise ValueError; no generic
    fallback, installed HVAC, project calendar or reference area is inferred.

    ``standard="measured"`` returns the same Sveby record with the measured
    Swedish stock-operation values of ``measured_use_v1`` substituted, for
    simulating existing buildings against measured energy use. Inputs that vary
    with construction era require ``era`` (``"SE.01"`` to ``"SE.07"``). A use
    with no adopted measured value returns its Sveby record with a note saying
    so. The record keeps the Sveby schema, so Core resolves it unchanged.

    Examples
    --------
    >>> profile = select_operating_profile("multi_family")
    >>> profile.values["use"]["dhw_kwh_m2_year"]
    21.0
    """
    names = {
        "single_family": ("sveby_residential_v2", "2"),
        "multi_family": ("sveby_residential_v2", "2"),
        "office": ("sveby_office_v1", "1"),
        "school": ("sveby_school_v1", "1"),
    }
    if standard not in ("sveby", "measured") or building_type not in names:
        raise ValueError(f"Unsupported operating profile selection: {standard}/{building_type}")
    if era is not None and standard != "measured":
        raise ValueError("era selects measured-use values; Sveby normal use does not vary with era")
    name, edition = names[building_type]
    if version not in (None, edition, f"{edition}.0"):
        raise ValueError(f"Unsupported {building_type} operating profile version: {version!r}")
    profile = load_operating_profile(name)
    if building_type == "single_family":
        profile = profile.with_changes(
            notes=profile.notes
            + (
                "Explicit single-family fallback permitted by Sveby residential 2.0; primary scope is multi-family.",
            )
        )
    if standard == "measured":
        profile = _measured_use(profile, building_type, era)
    return profile


def _measured_use(profile, building_type, era):
    """Substitute the adopted measured-use values into a selected Sveby profile."""
    record = load_standard_record("measured_use_v1")
    overrides = record["types"].get(building_type)
    if overrides is None:
        return profile.with_changes(
            notes=profile.notes
            + (f"Measured use: no value adopted for {building_type}. {record['not_adopted'][building_type]}",)
        )
    values = _plain(profile.values)
    changed = []
    for section in ("use", "operation_inputs"):
        for key, value in overrides.get(section, {}).items():
            if key.endswith("_by_era"):
                if era not in value:
                    raise ValueError(f"Measured {building_type} {key} requires an era in {sorted(value)}")
                key, value = key.removesuffix("_by_era"), value[era]
            values[section][key] = value
            changed.append(f"{section}.{key}")
    identity = f"{record['profile_id']}.{building_type}" + (f".{era}" if era else "")
    values["profile_id"] = identity
    values["measured_use"] = {
        "profile_id": record["profile_id"],
        "base_profile_id": profile.profile_id,
        "era": era,
        "changed": changed,
        "ventilation": overrides.get("ventilation", {}),
        "source_locators": overrides["source_locators"],
        "selection_note": record["selection_note"],
    }
    return OperatingProfile(
        identity,
        values,
        profile.source_references + (record["source_uri"],),
        profile.notes + ("Measured use replaces " + ", ".join(changed) + " with measured stock operation.",),
    )


def select_dhw_profile(building_type, *, purpose, version="1"):
    """Read an explicitly selected BEN normal-use useful DHW coefficient.

    ``purpose="epc_normal_use"`` is mandatory. Version ``"1"`` represents BEN
    BFS 2016:12 amended by BFS 2017:6, before production efficiency. Values use
    Atemp and exclude circulation/storage losses. This changes no operating
    profile and supplies no calendar. Unsupported selectors raise ValueError.
    """
    if purpose != "epc_normal_use" or version != "1":
        raise ValueError(f"Unsupported DHW selection: purpose={purpose!r}, version={version!r}")
    data = load_standard_record("dhw_epc_normal_use_v1")
    if building_type not in data["dhw_kwh_m2_year_by_type"]:
        raise ValueError(f"Unsupported DHW building type: {building_type!r}")
    values = {
        key: data[key]
        for key in (
            "schema_version",
            "purpose",
            "version",
            "area_basis",
            "source_uri",
            "standard_name",
            "energy_boundary",
            "excluded",
            "selection_note",
        )
    }
    values.update(
        profile_id=f"{data['profile_id']}.{building_type}",
        building_type=building_type,
        dhw_kwh_m2_year=data["dhw_kwh_m2_year_by_type"][building_type],
        source_locator=data["source_locator_by_type"][building_type],
    )
    return OperatingProfile(
        values["profile_id"], values, (data["source_uri"],), (data["selection_note"],)
    )
