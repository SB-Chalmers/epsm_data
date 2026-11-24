"""Optional per-building draws of operating values inside sourced ranges.

The catalogue is deterministic by default and stays so: nothing here is applied
unless a caller asks for it. ``select_operating_distributions`` reads the sourced
ranges for a building type and era; ``sample_operating_values`` turns them into
one building's values. The same seed and building key always give the same
values, on any machine, without numpy.

The ranges were tested against EPC measurements (see ``evidence_note`` in the
record and docs/validation.md): per-building draws did not improve match over
one fixed value, so use them for uncertainty bands, not as a calibration.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .profiles import load_standard_record

_RECORD = "operating_distributions_v1"
_KINDS = ("uniform", "triangular")


@dataclass(frozen=True)
class OperatingDistribution:
    """One lever's sourced range, its released value, and how to draw from it.

    ``low`` and ``high`` bound the draw; ``high`` may be below ``low`` (a range
    that runs downwards). ``mode`` is used only by ``triangular``.
    """

    name: str
    kind: str
    low: float
    high: float
    released: float
    unit: str
    source_locator: str
    mode: float | None = None

    def __post_init__(self):
        if self.kind not in _KINDS:
            raise ValueError(f"Unsupported distribution kind: {self.kind!r}")
        for field in ("low", "high", "released"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{self.name}: {field} must be a finite number")
        lo, hi = sorted((self.low, self.high))
        if self.kind == "triangular" and (self.mode is None or not lo <= self.mode <= hi):
            raise ValueError(f"{self.name}: triangular needs a mode inside the range")
        if not self.source_locator.strip():
            raise ValueError(f"{self.name}: a source locator is required")

    def quantile(self, u: float) -> float:
        """Value at cumulative probability ``u`` in [0, 1)."""
        if not 0.0 <= u < 1.0:
            raise ValueError("u must be in [0, 1)")
        if self.low == self.high:
            return float(self.low)
        if self.kind == "uniform":
            return self.low + u * (self.high - self.low)
        lo, hi = sorted((self.low, self.high))
        c = (self.mode - lo) / (hi - lo)
        if u < c:
            return lo + math.sqrt(u * (hi - lo) * (self.mode - lo))
        return hi - math.sqrt((1 - u) * (hi - lo) * (hi - self.mode))


@dataclass(frozen=True)
class OperatingDistributions:
    """The levers for one building type and era, plus where they apply."""

    building_type: str
    era: str
    applies_to_states: tuple[str, ...]
    levers: Mapping[str, OperatingDistribution]
    source_uri: str
    evidence_status: str
    evidence_note: str

    def __post_init__(self):
        object.__setattr__(self, "levers", MappingProxyType(dict(self.levers)))
        object.__setattr__(self, "applies_to_states", tuple(self.applies_to_states))

    def released_values(self) -> dict[str, float]:
        """The deterministic catalogue values: what every building gets by default."""
        return {name: float(d.released) for name, d in self.levers.items()}


def select_operating_distributions(building_type, *, era):
    """Read the sourced operating ranges for a building type and era.

    Only ``single_family`` has sourced ranges today; other types raise
    ValueError naming why. ``era`` is ``"SE.01"`` to ``"SE.07"``.

    Examples
    --------
    >>> d = select_operating_distributions("single_family", era="SE.03")
    >>> d.levers["heating_setpoint_c"].high
    21.7
    """
    record = load_standard_record(_RECORD)
    spec = record["types"].get(building_type)
    if spec is None:
        reason = record["not_defined"].get(building_type, "unknown building type")
        raise ValueError(f"No operating distributions for {building_type!r}: {reason}")
    levers = {}
    for name, raw in spec["levers"].items():
        high = raw.get("high")
        if "high_by_era" in raw:
            if era not in raw["high_by_era"]:
                raise ValueError(f"{building_type} {name} needs an era in {sorted(raw['high_by_era'])}")
            high = raw["high_by_era"][era]
        levers[name] = OperatingDistribution(
            name=name, kind=raw["kind"], low=raw["low"], high=high, released=raw["released"],
            unit=raw["unit"], source_locator=raw["source_locator"], mode=raw.get("mode"))
    return OperatingDistributions(
        building_type=building_type, era=era, applies_to_states=tuple(spec["applies_to_states"]),
        levers=levers, source_uri=record["source_uri"], evidence_status=record["evidence_status"],
        evidence_note=record["evidence_note"])


def _unit_draw(seed, key, lever):
    digest = hashlib.sha256(f"{seed}:{key}:{lever}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def sample_operating_values(distributions, building_key, *, seed, stochastic=True, state=None):
    """One building's operating values: a reproducible draw, or the released values.

    Parameters
    ----------
    distributions : OperatingDistributions
        From ``select_operating_distributions``.
    building_key : str
        A stable building identity, e.g. the lake building id.
    seed : int or str
        Campaign seed; the same seed and key always give the same draw.
    stochastic : bool, default True
        False returns the released (deterministic) values, so one code path can
        run both arms of a comparison.
    state : str, optional
        Catalogue state. A state outside ``applies_to_states`` (e.g. Advanced)
        gets the released values.

    Returns
    -------
    dict of str to float
        Lever name to value. The same draw is used for every state it applies
        to, because it stands for the household and its system.
    """
    if not isinstance(distributions, OperatingDistributions):
        raise TypeError("distributions must come from select_operating_distributions")
    if not isinstance(building_key, str) or not building_key.strip():
        raise ValueError("building_key must be nonempty text")
    if not stochastic or (state is not None and state not in distributions.applies_to_states):
        return distributions.released_values()
    return {name: d.quantile(_unit_draw(seed, building_key, name)) for name, d in distributions.levers.items()}
