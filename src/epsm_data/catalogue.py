"""Caller-populated renovation definitions; application belongs to simulation code."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Literal

from epsm_data._logging import operation as logged_operation

from .operations import ConstructionOperation, SystemOperation
from .serialization import _encode


@dataclass(frozen=True)
class Cost:
    """Describe a cost with an explicit basis.

    Parameters
    ----------
    amount : float
        Non-negative amount per unit; no price or exchange-rate defaults.
    currency : str
        Three-letter uppercase currency code, for example "SEK".
    unit : str
        Basis such as "m2_window", "m2_floor_area", or "installation".
    """

    amount: float
    currency: str
    unit: str

    def __post_init__(self) -> None:
        if not isfinite(self.amount) or self.amount < 0:
            raise ValueError("Cost amount must be finite and non-negative")
        if len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper():
            raise ValueError("Currency must be a three-letter uppercase code")
        if not self.unit.strip():
            raise ValueError("Cost unit must be explicit")


@dataclass(frozen=True)
class ParameterDefinition:
    """Describe a parameter that a workflow must resolve before application.

    Parameters
    ----------
    name : str
        Unique parameter name within a measure.
    kind : {"number", "integer", "string", "boolean"}
        Portable parameter type, serialized as text rather than Python types.
    description : str
        Meaning and any constraints that consumers must understand.
    unit : str, optional
        Explicit physical unit; use "1" for dimensionless quantities.
    required : bool, optional
        Whether the workflow must provide a value. Defaults to True.

    Notes
    -----
    Definitions describe inputs. Core performs physics-specific validation.
    """

    name: str
    kind: Literal["number", "integer", "string", "boolean"]
    description: str
    unit: str | None = None
    required: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.description.strip():
            raise ValueError("Parameter name and description are required")
        if self.kind not in {"number", "integer", "string", "boolean"}:
            raise ValueError(f"Unsupported parameter kind: {self.kind}")
        if not isinstance(self.required, bool):
            raise ValueError("required must be a boolean")


@dataclass(frozen=True)
class RenovationMeasure:
    """Define a catalogue measure without choosing when or how to execute it.

    Parameters
    ----------
    measure_id : str
        Stable caller-assigned identity.
    category : str
        Caller-defined grouping, for example "envelope" or "systems".
    name, description, target : str
        Display name, explanation, and affected subsystem.
    parameters : tuple of ParameterDefinition, optional
        Inputs to be resolved by a workflow.
    applicability_notes : tuple of str, optional
        Human-readable applicability guidance, not executable policy.
    cost : Cost, optional
        Sourced cost estimate with explicit currency and basis.
    service_life_years : float, optional
        Positive service-life estimate; no aging behavior is attached.
    source_references : tuple of str, optional
        Source locators or citations supplied by the catalogue author.
        Empty means unsourced; it does not imply validation.

    Examples
    --------
    >>> measure = RenovationMeasure(
    ...     "example.windows", "envelope", "Replace windows",
    ...     "Illustrative definition", "window",
    ...     parameters=(ParameterDefinition("u_value", "number", "Target U", "W/(m2 K)"),),
    ... )
    >>> measure.measure_id
    'example.windows'
    """

    measure_id: str
    category: str
    name: str
    description: str
    target: str
    parameters: tuple[ParameterDefinition, ...] = ()
    applicability_notes: tuple[str, ...] = ()
    cost: Cost | None = None
    service_life_years: float | None = None
    source_references: tuple[str, ...] = ()
    operations: tuple[ConstructionOperation | SystemOperation, ...] = ()
    target_element_ids: tuple[str, ...] = ()
    requires_measure_ids: tuple[str, ...] = ()
    incompatible_measure_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in ("measure_id", "category", "name", "description", "target"):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} must not be empty")
        for field in ("parameters", "applicability_notes", "source_references", "operations", "target_element_ids", "requires_measure_ids", "incompatible_measure_ids"):
            object.__setattr__(self, field, tuple(getattr(self, field)))
        for field in ("requires_measure_ids", "incompatible_measure_ids"):
            values = getattr(self, field)
            if (any(not isinstance(value, str) or not value.strip() for value in values)
                    or len(set(values)) != len(values) or self.measure_id in values):
                raise ValueError(f"{field} must contain unique other measure identities")
        if set(self.requires_measure_ids) & set(self.incompatible_measure_ids):
            raise ValueError("A measure cannot both require and prohibit the same measure")
        if any(not isinstance(op, (ConstructionOperation, SystemOperation)) for op in self.operations):
            raise ValueError("operations must contain ConstructionOperation records")
        if any(not isinstance(i, str) or not i.strip() for i in self.target_element_ids) or len(set(self.target_element_ids)) != len(self.target_element_ids):
            raise ValueError("Physical element selectors must be nonempty and unique")
        if any(not isinstance(p, ParameterDefinition) for p in self.parameters):
            raise ValueError("parameters must contain ParameterDefinition objects")
        names = [p.name for p in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("Parameter names must be unique within a measure")
        if self.cost is not None and not isinstance(self.cost, Cost):
            raise ValueError("cost must be a Cost object")
        if self.service_life_years is not None and (
            not isfinite(self.service_life_years) or self.service_life_years <= 0
        ):
            raise ValueError("Service life must be finite and positive")

    def to_dict(self) -> dict:
        """Return JSON-compatible definition data.

        Returns
        -------
        dict
            Nested parameter and cost definitions; no application state.
        """
        result = _encode(self)
        for field in ("parameters", "applicability_notes", "source_references", "operations", "target_element_ids"):
            result[field] = list(result[field])
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "RenovationMeasure":
        """Restore and validate a serialized measure.

        Parameters
        ----------
        data : dict
            Output of :meth:`to_dict`, optionally passed through JSON.

        Returns
        -------
        RenovationMeasure
            Validated definition.

        Raises
        ------
        ValueError
            A cost, parameter, identity, or service-life value is invalid.
        """
        values = dict(data)
        values["parameters"] = tuple(ParameterDefinition(**p) for p in values.get("parameters", ()))
        values["operations"] = tuple((SystemOperation.from_dict(op) if op.get("action") == "replace_hvac" else ConstructionOperation.from_dict(op)) for op in values.get("operations", ()))
        if values.get("cost") is not None:
            values["cost"] = Cost(**values["cost"])
        return cls(**values)


    @property
    def is_executable(self):
        return bool(self.operations)

    def apply(self, construction):
        """Apply resolved operations in order; actual building selectors belong to Core."""
        if not self.operations:
            raise ValueError("Measure has no executable construction operations")
        result = construction
        for operation in self.operations:
            if isinstance(operation, SystemOperation):
                raise ValueError("System changes require a Core Building")
            result = operation.apply(result)
        return result


class RenovationCatalogue:
    """Index caller-supplied measures without loading defaults or external data.

    Parameters
    ----------
    measures : iterable of RenovationMeasure, optional
        Initial definitions. Duplicate identities raise ValueError.
    """

    def __init__(self, measures: Iterable[RenovationMeasure] = ()) -> None:
        self._measures: dict[str, RenovationMeasure] = {}
        for measure in measures:
            self.add(measure)

    def __iter__(self):
        return iter(self._measures.values())

    def __len__(self):
        return len(self._measures)

    def add(self, measure: RenovationMeasure) -> None:
        """Add a definition.

        Parameters
        ----------
        measure : RenovationMeasure
            Definition with an unused identity.

        Raises
        ------
        ValueError
            The identity already exists. Replacement must be explicit outside
            this in-memory catalogue.
        """
        if measure.measure_id in self._measures:
            raise ValueError(f"Duplicate measure: {measure.measure_id}")
        self._measures[measure.measure_id] = measure

    @logged_operation("catalogue.select", level=10)
    def get(self, measure_id: str) -> RenovationMeasure:
        """Look up a definition by its exact identity.

        Parameters
        ----------
        measure_id : str
            Catalogue identity.

        Returns
        -------
        RenovationMeasure
            Matching definition.

        Raises
        ------
        KeyError
            The identity is unknown.
        """
        return self._measures[measure_id]

    def filter(self, *, category: str | None = None) -> tuple[RenovationMeasure, ...]:
        """Select definitions in insertion order.

        Parameters
        ----------
        category : str, optional
            Exact category; None selects all definitions.

        Returns
        -------
        tuple of RenovationMeasure
            Matching definitions.
        """
        return tuple(
            m for m in self._measures.values() if category is None or m.category == category
        )

    def applicable(self, construction, *, applied_measure_ids=()):
        """Return executable measures whose complete ordered operations apply."""
        result = []
        applied = set(applied_measure_ids)
        for measure in self:
            if not set(measure.requires_measure_ids) <= applied or set(measure.incompatible_measure_ids) & applied:
                continue
            if any(prior in self._measures and measure.measure_id in self._measures[prior].incompatible_measure_ids
                   for prior in applied):
                continue
            try:
                if not measure.operations:
                    continue
                result_construction = construction
                for operation in measure.operations:
                    if isinstance(operation, ConstructionOperation):
                        result_construction = operation.apply(result_construction)
            except ValueError:
                continue
            result.append(measure)
        return tuple(result)

    def to_dict(self):
        return {"measures": [measure.to_dict() for measure in self]}

    @classmethod
    def from_dict(cls, data):
        return cls(RenovationMeasure.from_dict(item) for item in data["measures"])


class Catalogue:
    """Predefined authored archetypes and reusable definitions, usable without Core.

    ``Catalogue.load().for_year("multi_family", 2022)`` returns the shared
    Archetype with physical composition, supported operating definitions and
    explicit envelope reference bases. Installed systems and project calendars
    remain caller choices. ``parametric`` and ``detailed`` retain distinct
    advanced effective-property and source-review inspection.
    """

    def __init__(self, *, parametric, detailed, renovations=None, profiles=None, hvac_templates=None):
        from .detailed import _opaque_material
        from .domain import WindowElement
        from .profiles import HVACTemplate, OperatingProfile

        for name, records, expected in (("profiles", profiles, OperatingProfile),
                                       ("hvac_templates", hvac_templates, HVACTemplate)):
            if records is not None and (not isinstance(records, Mapping) or any(
                    not isinstance(key, str) or not key.strip() or not isinstance(value, expected)
                    for key, value in records.items())):
                raise ValueError(f"{name} must map nonempty IDs to {expected.__name__} definitions")

        self.parametric = parametric
        self.detailed = detailed
        self.renovations = renovations if renovations is not None else RenovationCatalogue()
        materials, windows = {}, {}
        for mid in detailed.materials:
            record = detailed.resolve_material(mid)
            properties = record["properties"]
            if record["kind"] == "opaque":
                materials[mid] = _opaque_material(properties)
            else:
                windows[mid] = WindowElement(name=properties["name"], archetype=f"catalogue:{mid}",
                    u_value=properties["u_value"], shgc=properties["shgc"], vt=properties["vt"],
                    boverket_id=properties["boverket_id"])
        self._materials = MappingProxyType(materials)
        self._windows = MappingProxyType(windows)
        self._operating_profiles = MappingProxyType(dict(profiles or {}))
        self._hvac_templates = MappingProxyType(dict(hvac_templates or {}))
        self._archetype_count = len(detailed.archetypes)

    @property
    def materials(self):
        """Loaded opaque Material objects, keyed by registry ID and safe to reuse."""
        return self._materials

    @property
    def windows(self):
        """Loaded whole-window definitions, independent of opening geometry."""
        return self._windows

    @property
    def operating_profiles(self):
        """Read-only loaded profiles; generic_other is an explicit screening choice."""
        return self._operating_profiles

    @property
    def hvac_templates(self):
        """Read-only explicit system choices; none is automatically installed."""
        return self._hvac_templates

    def __repr__(self):
        label = repr(self.dataset_id)
        if len(label) > 60:
            label = repr(self.dataset_id[:8] + "…")
        if len(label) > 60:
            label = "'…'"
        return (f"Catalogue(id={label}, archetypes={self._archetype_count}, "
                f"materials={len(self.materials)}, profiles={len(self.operating_profiles)})")

    __str__ = __repr__

    @classmethod
    @logged_operation("catalogue.load")
    def load(cls, *, parametric_path=None, detailed_path=None, renovations=None):
        """Read and validate packaged or explicit registries and bundled profiles.

        Returns detached authoring indexes and source definitions without Core,
        network access or engine execution. File I/O occurs only on this call
        and explicit named-profile selection during get/for_year.
        """
        from .detailed import load_detailed_catalogue
        from .parametric import load_parametric_catalogue
        from .profiles import available_operating_profiles
        from .reference import reference_hvac_template

        parametric = load_parametric_catalogue(parametric_path)
        return cls(parametric=parametric,
                   detailed=load_detailed_catalogue(detailed_path, catalogue=parametric),
                   renovations=renovations, profiles=available_operating_profiles(),
                   hvac_templates={"illustrative_reference_ftx": reference_hvac_template()})

    @property
    def dataset_id(self):
        """Loaded effective catalogue identity, independent of package version."""
        return self.parametric.dataset_id

    @property
    def dimensions(self):
        """Read-only classification dimensions from the loaded catalogue."""
        return self.parametric.dimensions

    @staticmethod
    def era_for_year(year):
        """Classify an explicit positive construction year; SE.07 begins in 2022."""
        from .parametric import era_for_year

        return era_for_year(year)

    def get_slot(self, key):
        """Inspect effective scalar properties and source evidence by classification."""
        return self.parametric.get_slot(key)

    def search(self, **filters):
        """Inspect matching effective slots using the documented classification filters."""
        return self.parametric.search(**filters)

    def summary(self):
        """Calculate coverage of the loaded effective catalogue, without I/O."""
        return self.parametric.summary()

    def effective_configuration(self):
        """Return detached effective scalar configuration for inspection or content identity.

        This is exactly the advanced parametric view's configuration, not a
        physical archetype exchange record. Use archetype_to_dict for that.
        """
        return self.parametric.to_dict()

    def nominal_metadata(self, archetype_id, *, state=None):
        """Prepare portable construction-export context from already loaded records.

        Source, material, boundary, role and revision metadata retain their
        existing meaning; no calibration loader, target match or engine is
        requested. Ground/weather validation stays unverified. The recorded key
        is source classification context, never an installed-system selection.
        Use this with export_nominal_constructions(archetype, metadata=...).
        Unknown IDs/states raise KeyError; SE.07 rejects a renovation state.
        """
        from .parametric import ArchetypeKey, content_hash

        record = self.detailed.archetypes[archetype_id]
        if record["era"] == "SE.07" and state is not None:
            raise ValueError("SE.07 has no renovation states")
        if record["era"] != "SE.07" and state is None:
            state = "existing"
        definition, snapshot = self.detailed.state_inputs(archetype_id, state)
        return {
            "dataset_release": definition.get("dataset_release"),
            "construction_availability": list(definition["included_roles"]),
            "key": ArchetypeKey(**definition["key"]).to_dict(),
            "revision": content_hash({"definition": definition, "source_snapshot": snapshot}),
            "catalogue_revision": content_hash(self.effective_configuration()),
            "sources": {**snapshot["sources"], **definition["sources"]},
            **definition["review_annotations"],
            "effective_ground_calibration_complete": False,
            "assessment_status": "not_assessed",
            **({"status": "source_and_provisional_draft"}
               if record.get("representation") == "source_layer_draft" else {}),
        }

    def ids(self, *, category=None, include_variants=False):
        """List loaded archetype IDs; source variants require an explicit opt-in."""
        return tuple(aid for aid, record in self.detailed.archetypes.items()
                     if (include_variants or record.get("catalogue_assignment", "canonical") == "canonical")
                     and (category is None or record["category"] == category))

    def construction_sets(self, *, include_variants=False):
        """Compose a read-only (identifier, state) index from loaded physical recipes.

        This explicit operation constructs objects; no calibration is requested.
        Source variants are opt-in. SE.07 is keyed with state None.
        """
        return MappingProxyType({(identifier, state): self.detailed.compose(identifier, state=state).construction_set
            for identifier in self.ids(include_variants=include_variants)
            for state in (self.renovation_states(identifier) or (None,))})

    def renovation_states(self, archetype_id):
        """Recorded renovation choices; an empty tuple denotes SE.07's single configuration."""
        return tuple(state for state in self.detailed.archetypes[archetype_id]["states"]
                     if state is not None)

    @logged_operation("catalogue.select", level=10)
    def get(self, archetype_id, *, state=None):
        """Compose a predefined archetype, supported profile and explicit envelope basis.

        Reads the selected bundled operating profile on request. Composition uses
        loaded physical recipes and never requires a successful calibration. HVAC
        is never inferred. Unsupported operating uses remain unresolved.
        """
        from .profiles import select_operating_profile

        archetype = self.detailed.compose(archetype_id, state=state)
        category = self.detailed.archetypes[archetype_id]["category"]
        profile = select_operating_profile(category) if category in (
            "single_family", "multi_family", "office", "school") else None
        return archetype.with_changes(operating_profile=profile,
            envelope_performance=self._envelope_definition(archetype_id, state))

    def _envelope_definition(self, archetype_id, state):
        import json

        from .domain import EnvelopePerformance

        record = self.detailed.archetypes[archetype_id]
        if record["era"] != "SE.07" and state is None:
            state = "existing"
        # These current definitions have no climate-zone or installed-topology
        # dependence; retain the owner's property without selecting either.
        effective = self.detailed.target_catalogue(archetype_id, self.parametric)
        infiltration = effective._resolve_property(record["category"], record["era"], state, "infiltration")
        evidence = infiltration.evidence or {}
        basis = evidence.get("airflow_basis", {})
        references = (json.dumps(infiltration.to_dict(), sort_keys=True, ensure_ascii=False, allow_nan=False),)
        notes = tuple(str(value) for value in (
            evidence.get("decision"), evidence.get("limitations"), basis.get("interpretation"),
            basis.get("pressure_coupling")) if value)
        if evidence.get("basis_stale") or not basis or infiltration.value is None:
            return EnvelopePerformance(source_references=references,
                notes=notes + ("Infiltration remains unresolved: source reference basis is absent or stale.",))
        native = basis.get("additional_flow_l_s_per_reference_m2")
        if basis.get("native_unit") == "L/(s m² Atemp)" and native is not None:
            return EnvelopePerformance(infiltration_l_s_m2=native,
                infiltration_reference_basis="Atemp", source_references=references, notes=notes)
        if basis.get("reference_volume") == "tabula_reference_area_times_reference_height":
            return EnvelopePerformance(infiltration_ach=infiltration.value,
                infiltration_reference_basis="tabula_reference_volume", source_references=references, notes=notes)
        return EnvelopePerformance(source_references=references,
            notes=notes + ("Infiltration remains unresolved: unsupported source reference basis.",))

    @logged_operation("catalogue.select.year", level=10)
    def for_year(self, category, construction_year, *, state=None):
        """Select a canonical composed archetype from an explicit type and year.

        Reads the supported named operating profile as get does; no HVAC,
        calendar, reference area or geometry is inferred.
        """
        from .parametric import era_for_year

        era = era_for_year(construction_year)
        candidates = [aid for aid in self.ids(category=category)
                      if self.detailed.archetypes[aid]["era"] == era]
        if len(candidates) != 1:
            raise ValueError(f"Expected one current archetype for {category}/{era}")
        return self.get(candidates[0], state=state)
