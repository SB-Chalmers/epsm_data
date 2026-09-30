"""Small, editable Swedish archetypes resolved from anchors and scaling curves.

Validate and summarize with ``python -m epsm_data.parametric --check --summary``.
All catalogue operations are offline; edits are explicit JSON changes or immutable
``with_anchor`` / ``with_override`` replacements followed by caller-owned saving.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass, replace
from importlib.resources import files
from itertools import product
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

CATEGORIES = ("single_family", "multi_family", "office", "school", "generic")
CATEGORY_LABELS = dict(zip(CATEGORIES, ("SF", "MF", "Office", "School", "Generic"), strict=True))
ERAS = {
    "SE.01": (1, 1960),
    "SE.02": (1961, 1975),
    "SE.03": (1976, 1985),
    "SE.04": (1986, 1995),
    "SE.05": (1996, 2005),
    "SE.06": (2006, None),
}
ZONES = ("SE.Zone1", "SE.Zone2", "SE.Zone3")
STATES = ("existing", "standard", "advanced")
SYSTEMS = ("S", "F", "FT", "FTX")
ELEMENTS = (
    "ground_floor",
    "intermediate_floor",
    "external_wall",
    "internal_wall",
    "roof",
    "basement_wall",
    "window",
)
PROPERTIES = (*ELEMENTS, "infiltration")


def content_hash(value: Any) -> str:
    """Stable review identity independent of JSON whitespace and dictionary order."""
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _number(value: Any, name: str, *, positive: bool = True) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
        or (value <= 0 if positive else value < 0)
    ):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")


def era_for_year(year: int) -> str:
    """Resolve a positive construction year; SE.06 is the open modern cohort."""
    if isinstance(year, bool) or not isinstance(year, int) or year < 1:
        raise ValueError("construction year must be a positive integer")
    return next(
        era for era, (start, end) in ERAS.items() if year >= start and (end is None or year <= end)
    )


@dataclass(frozen=True, slots=True)
class ArchetypeKey:
    category: str
    era: str
    climate_zone: str
    renovation_state: str
    ventilation_system: str

    def __post_init__(self) -> None:
        for name, choices in (
            ("category", CATEGORIES),
            ("era", ERAS),
            ("climate_zone", ZONES),
            ("renovation_state", STATES),
            ("ventilation_system", SYSTEMS),
        ):
            if not isinstance(getattr(self, name), str) or getattr(self, name) not in choices:
                raise ValueError(f"Unknown {name}: {getattr(self, name)}")

    @property
    def id(self) -> str:
        return ":".join(
            (
                self.category,
                self.era,
                self.climate_zone,
                self.renovation_state,
                self.ventilation_system,
            )
        )

    def to_dict(self) -> dict[str, str]:
        return dict(
            category=self.category,
            era=self.era,
            climate_zone=self.climate_zone,
            renovation_state=self.renovation_state,
            ventilation_system=self.ventilation_system,
        )


@dataclass(frozen=True, slots=True)
class EffectiveProperty:
    value: float | None
    unit: str
    source: str | None
    anchor: Mapping[str, Any] | None
    curve: str
    mode: str
    boundary: str
    curve_source: str
    assumed: bool = False
    override: Mapping[str, Any] | None = None
    scaling_factor: float | None = None
    unclipped_value: float | None = None
    guardrail: Mapping[str, Any] | None = None

    evidence: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return dict(
            **({"evidence": _plain(self.evidence)} if self.evidence is not None else {}),
            value=self.value,
            unit=self.unit,
            source=self.source,
            anchor=_plain(self.anchor),
            curve=self.curve,
            mode=self.mode,
            boundary=self.boundary,
            curve_source=self.curve_source,
            assumed=self.assumed,
            override=_plain(self.override),
            scaling_factor=self.scaling_factor,
            unclipped_value=self.unclipped_value,
            guardrail=_plain(self.guardrail),
        )


@dataclass(frozen=True, slots=True)
class EffectiveConstructionSet:
    """Effective boundary properties; independent of the material-layer models."""

    category: str
    era: str
    renovation_state: str
    properties: Mapping[str, EffectiveProperty]

    @property
    def u_values(self) -> Mapping[str, float | None]:
        return MappingProxyType({role: prop.value for role, prop in self.properties.items()})

    def to_dict(self) -> dict[str, Any]:
        return dict(
            category=self.category,
            era=self.era,
            renovation_state=self.renovation_state,
            properties={role: prop.to_dict() for role, prop in self.properties.items()},
        )


@dataclass(frozen=True, slots=True)
class ArchetypeSlot:
    key: ArchetypeKey
    construction_set: EffectiveConstructionSet
    infiltration: EffectiveProperty
    lod: int = 1

    @property
    def slot_id(self) -> str:
        return self.key.id

    @property
    def properties(self) -> Mapping[str, EffectiveProperty]:
        return MappingProxyType(
            {**self.construction_set.properties, "infiltration": self.infiltration}
        )

    @property
    def missing_properties(self) -> tuple[str, ...]:
        return tuple(role for role, prop in self.properties.items() if prop.value is None)

    @property
    def lod1_complete(self) -> bool:
        return not self.missing_properties

    def to_dict(self) -> dict[str, Any]:
        return dict(
            slot_id=self.slot_id,
            key=self.key.to_dict(),
            lod=self.lod,
            construction_set=self.construction_set.to_dict(),
            infiltration=self.infiltration.to_dict(),
            lod1_complete=self.lod1_complete,
            missing_properties=list(self.missing_properties),
        )


class ParametricCatalogue:
    """Validated immutable configuration; the expanded matrix is never stored."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        data = copy.deepcopy(_plain(payload))
        self._data = data
        try:
            self._validate()
            # Validate derived numbers too, without persisting the expanded grid.
            for category, era, state, role in product(CATEGORIES, ERAS, STATES, PROPERTIES):
                self._resolve_property(category, era, state, role)
        except (KeyError, TypeError, AttributeError, OverflowError) as exc:
            raise ValueError(f"Malformed catalogue: {exc}") from exc
        self.dataset_id = data["dataset_id"]
        self.release_id = content_hash(data)
        self.dimensions = _freeze(data["dimensions"])
        self.sources = _freeze(data["sources"])

    def _validate(self) -> None:
        d = self._data
        if (
            type(d.get("schema_version")) is not int
            or d["schema_version"] != 1
            or not isinstance(d.get("dataset_id"), str)
        ):
            raise ValueError("Expected catalogue schema_version 1 and dataset_id")
        if not d["dataset_id"].strip():
            raise ValueError("dataset_id must not be empty")
        dimensions = d["dimensions"]
        if set(dimensions) != {"categories", "eras", "zones", "states", "ventilation"}:
            raise ValueError("Expected exactly five classification dimensions")
        for name, choices in (
            ("categories", CATEGORIES),
            ("eras", ERAS),
            ("zones", ZONES),
            ("states", STATES),
            ("ventilation", SYSTEMS),
        ):
            values = dimensions[name]
            if len(values) != len(choices) or set(values) != set(choices):
                raise ValueError(f"dimensions.{name} must contain exactly {tuple(choices)}")
        if dimensions["categories"] != CATEGORY_LABELS:
            raise ValueError("Category labels must be SF, MF, Office, School, Generic")
        for era, bounds in ERAS.items():
            if dimensions["eras"][era] != list(bounds):
                raise ValueError(f"Invalid era bounds for {era}")
        if set(d["categories"]) != set(CATEGORIES):
            raise ValueError("Category definitions must cover all five categories")
        metadata = d.get("claim_metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("claim_metadata must be an object")
        for key, claim in metadata.items():
            parts = key.split(":")
            if len(parts) != 4 or any(p not in choices for p, choices in zip(parts, (CATEGORIES, ERAS, STATES, PROPERTIES))):
                raise ValueError("Invalid claim key")
            if not isinstance(claim, dict) or claim.get("classification") not in {
                "direct_evidence", "family_with_representative_dimensions", "transferred_analogue",
                "engineering_assumption", "derived_result", "unclassified"}:
                raise ValueError("Invalid evidence classification")
            if claim.get("source") not in d["sources"] or not claim.get("locator"):
                raise ValueError("Claim requires a source and locator")
            if "nominal_u_value" in claim:
                _number(claim["nominal_u_value"], "nominal_u_value")
        for source in d["sources"].values():
            if not isinstance(source.get("title"), str) or not source["title"].strip():
                raise ValueError("Every source requires a title")
        guardrail = d.get("performance_guardrail")
        if guardrail is not None:
            if not isinstance(guardrail, dict) or set(guardrail) != {
                "margin_percent",
                "benchmarks",
                "source",
                "note",
            }:
                raise ValueError("Invalid performance_guardrail definition")
            _number(guardrail["margin_percent"], "guardrail margin_percent", positive=False)
            self._source(guardrail["source"])
            benchmarks = guardrail["benchmarks"]
            if (
                not isinstance(benchmarks, dict)
                or not benchmarks
                or set(benchmarks) - {"roof", "external_wall", "window"}
            ):
                raise ValueError("Guardrail benchmarks support Roof, External Wall and Window only")
            if not isinstance(guardrail["note"], str) or not guardrail["note"].strip():
                raise ValueError("Guardrail requires an explanatory note")
            for role, value in benchmarks.items():
                _number(value, f"guardrail benchmark {role}")
                _number(value * (1 + guardrail["margin_percent"] / 100), f"guardrail limit {role}")
        for cid, curve in d["curves"].items():
            if curve["property"] not in PROPERTIES:
                raise ValueError(f"Unknown curve property in {cid}")
            self._source(curve["source"])
            if not isinstance(curve.get("boundary"), str) or not curve["boundary"].strip():
                raise ValueError(f"Curve {cid} requires boundary meaning")
            for era, source in curve.get("era_sources", {}).items():
                if era not in ERAS:
                    raise ValueError(f"Unknown curve era: {era}")
                self._source(source)
            if "proxy" in curve:
                if curve.get("state_invariant") is not True:
                    raise ValueError("Proxy curves require state_invariant=true")
                if "values" in curve:
                    raise ValueError("A curve cannot have both proxy and values")
            else:
                if set(curve["values"]) != set(ERAS):
                    raise ValueError(f"Curve {cid} must cover six eras")
                for era, row in curve["values"].items():
                    if set(row) != set(STATES):
                        raise ValueError(f"Curve {cid}/{era} must cover three states")
                    for value in row.values():
                        _number(value, f"curve {cid} ratio")
            self._curve_values(cid)
        for category, spec in d["categories"].items():
            if set(spec["curves"]) != set(PROPERTIES):
                raise ValueError(f"{category} must assign all eight property curves")
            for role, cid in spec["curves"].items():
                if cid not in d["curves"] or d["curves"][cid]["property"] != role:
                    raise ValueError(f"Dangling or mismatched curve {cid} for {category}/{role}")
            if set(spec["anchors"]) - set(PROPERTIES):
                raise ValueError(f"Unknown anchor property for {category}")
            for role, anchor in spec["anchors"].items():
                self._reference(anchor, role)
            seen = set()
            for override in spec["overrides"]:
                role = override["property"]
                if role not in PROPERTIES:
                    raise ValueError(f"Unknown override property: {role}")
                self._reference(override, role)
                key = (role, override["era"], override["state"])
                if key in seen:
                    raise ValueError(f"Duplicate override for {category}/{key}")
                seen.add(key)
            if "infiltration_from" in spec and spec["infiltration_from"] not in CATEGORIES:
                raise ValueError("Unknown infiltration_from category")
        for category in CATEGORIES:
            self._anchor(category, "infiltration")

    def _source(self, source: str) -> None:
        if source not in self._data["sources"]:
            raise ValueError(f"Dangling source: {source}")

    def _reference(self, ref: Mapping[str, Any], role: str) -> None:
        if ref["era"] not in ERAS or ref["state"] not in STATES:
            raise ValueError("Reference requires a known era and state")
        if ref["value"] is not None:
            _number(ref["value"], role, positive=role != "infiltration")
            self._source(ref["source"])
            if not any(isinstance(ref.get(k), str) and ref[k].strip() for k in ("locator", "note")):
                raise ValueError("Reference requires a locator or explanatory note")
        elif ref.get("source") is not None:
            self._source(ref["source"])

    def _curve_values(self, cid: str, visited: tuple[str, ...] = ()) -> dict[str, Any]:
        if cid in visited or cid not in self._data["curves"]:
            raise ValueError(f"Cyclic or dangling proxy curve: {cid}")
        curve = self._data["curves"][cid]
        if "proxy" in curve:
            parent = self._curve_values(curve["proxy"], (*visited, cid))
            return {era: dict.fromkeys(STATES, row["existing"]) for era, row in parent.items()}
        return curve["values"]

    def _anchor(self, category: str, role: str, visited: tuple[str, ...] = ()):
        if category in visited:
            raise ValueError("Cyclic infiltration inheritance")
        spec = self._data["categories"][category]
        if role in spec["anchors"]:
            return spec["anchors"][role], category
        if role == "infiltration" and "infiltration_from" in spec:
            return self._anchor(spec["infiltration_from"], role, (*visited, category))
        return None, category

    def _claim_evidence(self, category, era, state, role, raw):
        metadata = self._data.get("claim_metadata", {}).get(f"{category}:{era}:{state}:{role}")
        if metadata is None:
            return None
        metadata = copy.deepcopy(metadata)
        basis = {k: raw.to_dict()[k] for k in
                 ("value", "source", "anchor", "curve", "boundary", "override", "scaling_factor")}
        if metadata.get("basis_signature") != content_hash(basis):
            metadata.update(classification="unclassified", basis_stale=True,
                            limitations="The property resolution changed since this evidence review; review before reuse.")
        return _freeze(metadata)

    def _resolve_property(
        self, category: str, era: str, state: str, role: str
    ) -> EffectiveProperty:
        raw = self._resolve_unclipped_property(category, era, state, role)
        result = replace(raw, unclipped_value=raw.value, evidence=self._claim_evidence(category, era, state, role, raw))
        policy = self._data.get("performance_guardrail")
        if policy is None or role not in policy["benchmarks"] or raw.value is None:
            return result
        benchmark = policy["benchmarks"][role]
        limit = benchmark * (1 + policy["margin_percent"] / 100)
        historical_tabula = (
            category in ("single_family", "multi_family")
            and era != "SE.06"
            and raw.source == "tabula"
        )
        protected = raw.mode in ("direct", "overridden") or historical_tabula
        value = raw.value
        effective_limit = limit
        reason = "Existing value retained; renovation guardrail not applied"
        if protected:
            reason = "Supplied anchor, override or captured historical TABULA target retained"
        elif state in ("standard", "advanced"):
            existing = self._resolve_property(category, era, "existing", role).value
            ceiling = existing
            if state == "advanced":
                standard = self._resolve_property(category, era, "standard", role).value
                if standard is not None:
                    ceiling = standard if ceiling is None else min(ceiling, standard)
            effective_limit = limit if ceiling is None else min(limit, ceiling)
            value = max(value, effective_limit)
            if ceiling is not None:
                value = min(value, ceiling)
            if existing is not None and existing < limit:
                reason = (
                    "Existing already beats the limit; no further derived renovation improvement"
                )
            elif ceiling is not None and ceiling < limit:
                reason = "Better Standard reference retained; Advanced cannot become worse"
            else:
                reason = "Derived renovation value bounded by benchmark and renovation ordering"
        evidence = dict(
            source=policy["source"],
            benchmark=benchmark,
            margin_percent=policy["margin_percent"],
            lower_bound=limit,
            effective_lower_bound=effective_limit,
            applied=value != raw.value,
            protected=protected,
            below_nominal_limit=value < limit,
            reason=reason,
        )
        return replace(
            result,
            value=value,
            assumed=raw.assumed or value != raw.value,
            guardrail=_freeze(evidence),
        )

    def _resolve_unclipped_property(
        self, category: str, era: str, state: str, role: str
    ) -> EffectiveProperty:
        spec = self._data["categories"][category]
        cid = spec["curves"][role]
        curve = self._data["curves"][cid]
        curve_source = curve.get("era_sources", {}).get(era, curve["source"])
        anchor, origin = self._anchor(category, role)
        context = _freeze({**anchor, "category": origin}) if anchor is not None else None
        unit = "1/h" if role == "infiltration" else "W/(m²K)"
        override = next(
            (
                o
                for o in spec["overrides"]
                if (o["property"], o["era"], o["state"]) == (role, era, state)
            ),
            None,
        )
        if override is not None:
            return EffectiveProperty(
                override["value"],
                unit,
                override.get("source"),
                context,
                cid,
                "overridden" if override["value"] is not None else "pending",
                curve["boundary"],
                curve_source,
                override.get("source") != "tabula",
                _freeze({**override, "category": category}),
            )
        if anchor is None or anchor["value"] is None:
            return EffectiveProperty(
                None, unit, None, context, cid, "pending", curve["boundary"], curve_source
            )
        values = self._curve_values(cid)
        factor = values[era][state] / values[anchor["era"]][anchor["state"]]
        value = anchor["value"] * factor
        _number(value, role, positive=role != "infiltration")
        # Preserve direct inputs bit-for-bit instead of applying a floating-point ratio.
        mode = "inherited" if origin != category else "scaled"
        if era == anchor["era"] and state == anchor["state"]:
            value = anchor["value"]
            if origin == category:
                mode = "direct"
        assumed = (
            origin != category
            or curve_source != "tabula"
            or anchor["source"] != "tabula"
            or (category not in ("single_family", "multi_family") and role != "infiltration")
        )
        return EffectiveProperty(
            value,
            unit,
            anchor["source"],
            context,
            cid,
            mode,
            curve["boundary"],
            curve_source,
            assumed,
            scaling_factor=factor,
        )

    def resolve_construction(self, category: str, era: str, state: str) -> EffectiveConstructionSet:
        ArchetypeKey(category, era, ZONES[0], state, SYSTEMS[0])
        return EffectiveConstructionSet(
            category,
            era,
            state,
            MappingProxyType(
                {role: self._resolve_property(category, era, state, role) for role in ELEMENTS}
            ),
        )

    def get_slot(self, key: ArchetypeKey | str) -> ArchetypeSlot:
        if isinstance(key, str):
            parts = key.split(":")
            if len(parts) != 5:
                raise ValueError("Slot ID requires five classification fields")
            key = ArchetypeKey(*parts)
        if not isinstance(key, ArchetypeKey):
            raise ValueError("Expected ArchetypeKey or slot ID")
        return ArchetypeSlot(
            key,
            self.resolve_construction(key.category, key.era, key.renovation_state),
            self._resolve_property(key.category, key.era, key.renovation_state, "infiltration"),
        )

    resolve = get_slot

    @property
    def slots(self) -> tuple[ArchetypeSlot, ...]:
        return tuple(
            self.get_slot(ArchetypeKey(*parts))
            for parts in product(CATEGORIES, ERAS, ZONES, STATES, SYSTEMS)
        )

    def search(
        self,
        *,
        category=None,
        era=None,
        climate_zone=None,
        renovation_state=None,
        ventilation_system=None,
        lod1_complete_only=False,
    ) -> tuple[ArchetypeSlot, ...]:
        filters = (category, era, climate_zone, renovation_state, ventilation_system)
        choices = (CATEGORIES, ERAS, ZONES, STATES, SYSTEMS)
        for value, allowed in zip(filters, choices, strict=True):
            if value is not None and value not in allowed:
                raise ValueError(f"Unknown filter: {value}")
        selected = (
            (value,) if value is not None else allowed
            for value, allowed in zip(filters, choices, strict=True)
        )
        slots = (self.get_slot(ArchetypeKey(*parts)) for parts in product(*selected))
        return tuple(s for s in slots if not lod1_complete_only or s.lod1_complete)

    def summary(self) -> dict[str, Any]:
        slots = self.slots
        missing = Counter(role for s in slots for role in s.missing_properties)
        return dict(
            dataset_id=self.dataset_id,
            release_id=self.release_id,
            slot_count=len(slots),
            lod1_complete=sum(s.lod1_complete for s in slots),
            lod1_pending=sum(not s.lod1_complete for s in slots),
            missing_properties=dict(missing),
            by_category={
                c: dict(
                    total=sum(s.key.category == c for s in slots),
                    complete=sum(s.key.category == c and s.lod1_complete for s in slots),
                )
                for c in CATEGORIES
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Return editable configuration, including references and overrides only."""
        return copy.deepcopy(self._data)

    def with_anchor(self, category: str, role: str, reference: Mapping[str, Any]):
        if category not in CATEGORIES or role not in PROPERTIES:
            raise ValueError("Unknown category or property")
        payload = self.to_dict()
        payload["categories"][category]["anchors"][role] = _plain(reference)
        return type(self)(payload)

    def with_override(self, category: str, role: str, reference: Mapping[str, Any]):
        if category not in CATEGORIES or role not in PROPERTIES:
            raise ValueError("Unknown category or property")
        payload = self.to_dict()
        override = {**_plain(reference), "property": role}
        entries = payload["categories"][category]["overrides"]
        entries[:] = [
            o
            for o in entries
            if (o["property"], o["era"], o["state"])
            != (role, override.get("era"), override.get("state"))
        ]
        entries.append(override)
        return type(self)(payload)


def load_parametric_catalogue(path: str | Path | None = None) -> ParametricCatalogue:
    resource = (
        Path(path)
        if path is not None
        else files("epsm_data.datasets.parametric").joinpath("catalogue.json")
    )
    try:
        payload = json.loads(resource.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError(f"Invalid catalogue JSON: {exc}") from exc
    return ParametricCatalogue(payload)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, help="Caller-owned editable JSON catalogue")
    parser.add_argument("--check", action="store_true", help="Validate the catalogue and all slots")
    parser.add_argument("--summary", action="store_true", help="Print completeness summary as JSON")
    args = parser.parse_args(argv)
    try:
        catalogue = load_parametric_catalogue(args.catalogue)
        summary = catalogue.summary()
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.summary or not args.check:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(
            f"Valid catalogue: {summary['slot_count']} slots; "
            f"{summary['lod1_complete']} LoD1 complete; {summary['lod1_pending']} pending"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
