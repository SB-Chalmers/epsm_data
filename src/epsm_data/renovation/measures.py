"""Executable renovation measures; candidate definitions live in :mod:`epsm_data.renovation.candidates`."""

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from ..catalogue.serialization import _encode
from .candidates import CostEstimate
from .operations import (
    AirtightnessOperation,
    ConstructionOperation,
    DHWOperation,
    PVOperation,
    SystemOperation,
)


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
    cost : CostEstimate, optional
        Sourced unit rates per Core quantity driver, split by cost category.
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
    cost: CostEstimate | None = None
    service_life_years: float | None = None
    source_references: tuple[str, ...] = ()
    operations: tuple = ()
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
        if any(not isinstance(op, (ConstructionOperation, SystemOperation, AirtightnessOperation,
                                      PVOperation, DHWOperation))
               for op in self.operations):
            raise ValueError("operations must contain ConstructionOperation records")
        if any(not isinstance(i, str) or not i.strip() for i in self.target_element_ids) or len(set(self.target_element_ids)) != len(self.target_element_ids):
            raise ValueError("Physical element selectors must be nonempty and unique")
        if any(not isinstance(p, ParameterDefinition) for p in self.parameters):
            raise ValueError("parameters must contain ParameterDefinition objects")
        names = [p.name for p in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("Parameter names must be unique within a measure")
        if self.cost is not None and not isinstance(self.cost, CostEstimate):
            raise ValueError("cost must be a CostEstimate")
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
        result["cost"] = self.cost.to_dict() if self.cost is not None else None
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
        readers = {"replace_hvac": SystemOperation.from_dict,
                   "reduce_infiltration": AirtightnessOperation.from_dict,
                   "add_pv": PVOperation.from_dict, "reduce_dhw": DHWOperation.from_dict}
        values["operations"] = tuple(readers.get(op.get("action"), ConstructionOperation.from_dict)(op)
                                     for op in values.get("operations", ()))
        if values.get("cost") is not None:
            values["cost"] = CostEstimate.from_dict(values["cost"])
        return cls(**values)


    @property
    def is_executable(self):
        """True when the measure carries operations that can be applied to a building."""
        return bool(self.operations)

    def apply(self, construction):
        """Apply resolved operations in order; actual building selectors belong to Core."""
        if not self.operations:
            raise ValueError("Measure has no executable construction operations")
        result = construction
        for operation in self.operations:
            if not isinstance(operation, ConstructionOperation):
                raise ValueError("System changes require a Core Building")
            result = operation.apply(result)
        return result
