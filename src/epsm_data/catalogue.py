"""Caller-populated renovation definitions; application belongs to simulation code."""

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Literal


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

    def __post_init__(self) -> None:
        for field in ("measure_id", "category", "name", "description", "target"):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} must not be empty")
        for field in ("parameters", "applicability_notes", "source_references"):
            object.__setattr__(self, field, tuple(getattr(self, field)))
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
        result = asdict(self)
        for field in ("parameters", "applicability_notes", "source_references"):
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
        if values.get("cost") is not None:
            values["cost"] = Cost(**values["cost"])
        return cls(**values)


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
