"""Classification of the frozen Swedish LoD2 catalogue; no physics or inference."""

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType

CATEGORIES = ("single_family", "multi_family", "office", "school")
# Selection fallback only: never an authored family or extra default matrix axis.
SELECTION_CATEGORIES = (*CATEGORIES, "generic")
GENERIC_DONOR_CATEGORY = "multi_family"
GENERIC_ASSUMPTION_LABEL = "Unknown building type — multifamily assumption"
CATEGORY_LABELS = dict(zip(CATEGORIES, ("SF", "MF", "Office", "School"), strict=True))
ERAS = {
    "SE.01": (1, 1960),
    "SE.02": (1961, 1975),
    "SE.03": (1976, 1985),
    "SE.04": (1986, 1995),
    "SE.05": (1996, 2005),
    "SE.06": (2006, 2021),
    "SE.07": (2022, None),
}
ZONES = ("SE.Zone1", "SE.Zone2", "SE.Zone3")
STATES = ("existing", "standard", "advanced")


def states_for_era(era):
    """Return the three older-era variants, or SE.07's single configuration."""
    if era not in ERAS:
        raise ValueError(f"Unknown era: {era}")
    return (None,) if era == "SE.07" else STATES


def era_for_year(year):
    """Classify an explicit construction year; SE.07 begins in 2022."""
    if isinstance(year, bool) or not isinstance(year, int) or year < 1:
        raise ValueError("construction year must be a positive integer")
    return next(
        era for era, (start, end) in ERAS.items() if start <= year and (end is None or year <= end)
    )


def content_hash(value):
    """Hash finite portable content, independently of dictionary ordering."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(freeze(child) for child in value)
    return value


def plain(value):
    from collections.abc import Mapping

    if isinstance(value, Mapping):
        return {key: plain(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(child) for child in value]
    return value


@dataclass(frozen=True, slots=True)
class ArchetypeKey:
    """One catalogue assignment; climate does not select weather or HVAC."""

    category: str
    era: str
    climate_zone: str
    renovation_state: str | None = None

    def __post_init__(self):
        for field, choices in (("category", SELECTION_CATEGORIES), ("era", ERAS), ("climate_zone", ZONES)):
            if getattr(self, field) not in choices:
                raise ValueError(f"Unknown {field}: {getattr(self, field)}")
        if self.renovation_state not in states_for_era(self.era):
            raise ValueError(f"Invalid state for {self.era}: {self.renovation_state}")

    @property
    def id(self):
        return ":".join(
            (self.category, self.era, self.climate_zone, self.renovation_state or "default")
        )

    def to_dict(self):
        return {
            "category": self.category,
            "era": self.era,
            "climate_zone": self.climate_zone,
            "renovation_state": self.renovation_state,
        }


@dataclass(frozen=True, slots=True)
class ArchetypeSlot:
    """A zone assignment to a shared physical definition, with missing values."""

    key: ArchetypeKey
    archetype_id: str
    construction_set_id: str | None
    missing_values: tuple[str, ...] = ()

    @property
    def slot_id(self):
        return self.key.id

    @property
    def state(self):
        return self.key.renovation_state

    @property
    def complete(self):
        return not self.missing_values

    @property
    def selection(self):
        """Expose the donor assumption for a virtual generic assignment."""
        if self.key.category != "generic":
            return None
        return {
            "requested_category": "generic",
            "donor_category": GENERIC_DONOR_CATEGORY,
            "donor_archetype_id": self.archetype_id,
            "assumption_label": GENERIC_ASSUMPTION_LABEL,
        }

    def to_dict(self):
        return {
            "slot_id": self.slot_id,
            "key": self.key.to_dict(),
            "archetype_id": self.archetype_id,
            "construction_set_id": self.construction_set_id,
            "complete": self.complete,
            "missing_values": list(self.missing_values),
            **({"selection": self.selection} if self.selection is not None else {}),
        }
