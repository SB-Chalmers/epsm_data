"""Limited renovation catalogue: what a measure installs, never where or how much.

Each candidate carries one typed payload that says what it installs: layers added
to an element, a window swap, a ventilation system, a PV array, a hot-water
reduction or tighter joints. A measure type fixes which payload it takes and the
element roles it may touch. Core selects targets, resolves geometric quantities
and records material flows; LCA prices and assesses them. No quantity, impact or
cost total is calculated here.

Examples
--------
>>> from epsm_data import Catalogue
>>> from epsm_data.renovation import RenovationCatalogue
>>> renovations = RenovationCatalogue.load(Catalogue.load())
>>> renovations.get("insulate_wall.stone_wool_200").payload.kind
'layer_addition'
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from importlib.resources import files
from math import isfinite
from pathlib import Path
from typing import ClassVar

from ..contract import QuantityDriver
from ..domain import CarbonReference, Component, WindowElement
from ..domain.enums import BuildingElement
from ..profiles import HVACTemplate
from .operations import (
    AirtightnessOperation,
    ConstructionOperation,
    DHWOperation,
    PVOperation,
    SystemOperation,
)

COST_CATEGORIES = ("material", "labour", "subcontractor", "overhead")
VENTILATION_SYSTEMS = ("S", "F", "FT", "FTX")


def _positive(value, name, *, zero=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value)
            or value < 0 or (value == 0 and not zero)):
        raise ValueError(f"{name} must be a finite {'nonnegative' if zero else 'positive'} number")
    return float(value)


def _texts(values, name):
    values = tuple(values)
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError(f"{name} must contain nonempty text")
    return values


def _fraction(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < 1:
        raise ValueError(f"{name} must be a fraction in (0, 1)")
    return float(value)


def _driver(value):
    try:
        return QuantityDriver(value)
    except ValueError:
        raise ValueError(f"Unknown quantity driver: {value}") from None


@dataclass(frozen=True)
class CostItem:
    """One priced share of a measure, as a rate per unit of a Core quantity driver.

    Parameters
    ----------
    category : {"material", "labour", "subcontractor", "overhead"}
        Cost share, kept separate so that labour and material can be reported apart.
    rate : float
        Nonnegative amount per driver unit in the estimate's currency.
    driver : str
        A :class:`~epsm_data.contract.QuantityDriver`; Core supplies its value.
    description : str, optional
        What the rate covers, for example the source work item.
    labour_hours : float, optional
        Working hours per driver unit behind a labour rate.
    source : str, optional
        Locator of the priced item, for example a price-book code.
    """

    category: str
    rate: float
    driver: str
    description: str = ""
    labour_hours: float | None = None
    source: str = ""

    def __post_init__(self):
        if self.category not in COST_CATEGORIES:
            raise ValueError(f"Unknown cost category: {self.category}")
        object.__setattr__(self, "driver", _driver(self.driver))
        object.__setattr__(self, "rate", _positive(self.rate, "Cost rate", zero=True))
        if self.labour_hours is not None:
            object.__setattr__(self, "labour_hours",
                               _positive(self.labour_hours, "Labour hours", zero=True))

    def to_dict(self):
        return {"category": self.category, "rate": self.rate, "driver": self.driver,
                "description": self.description, "labour_hours": self.labour_hours,
                "source": self.source}


@dataclass(frozen=True)
class CostEstimate:
    """Sourced unit rates for one candidate, excluding VAT unless stated.

    ``coverage`` is "complete" only when the items price the whole measure;
    ``missing_scope`` names unpriced work so that totals are never read as complete.
    """

    currency: str
    price_year: int
    items: tuple[CostItem, ...]
    coverage: str = "complete"
    missing_scope: tuple[str, ...] = ()
    includes_vat: bool = False
    source_references: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self):
        if len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper():
            raise ValueError("Currency must be a three-letter uppercase code")
        if isinstance(self.price_year, bool) or not isinstance(self.price_year, int):
            raise ValueError("price_year must be an integer year")
        items = tuple(i if isinstance(i, CostItem) else CostItem(**i) for i in self.items)
        if not items:
            raise ValueError("A cost estimate needs at least one item")
        object.__setattr__(self, "items", items)
        if self.coverage not in {"complete", "partial"}:
            raise ValueError("coverage must be 'complete' or 'partial'")
        object.__setattr__(self, "missing_scope", _texts(self.missing_scope, "missing_scope"))
        if (self.coverage == "partial") != bool(self.missing_scope):
            raise ValueError("A partial estimate must name its missing scope, and only then")
        object.__setattr__(self, "source_references",
                           _texts(self.source_references, "source_references"))
        object.__setattr__(self, "notes", tuple(self.notes))

    @property
    def drivers(self):
        return tuple(dict.fromkeys(item.driver for item in self.items))

    def to_dict(self):
        return {"currency": self.currency, "price_year": self.price_year,
                "items": [item.to_dict() for item in self.items], "coverage": self.coverage,
                "missing_scope": list(self.missing_scope), "includes_vat": self.includes_vat,
                "source_references": list(self.source_references), "notes": list(self.notes)}

    @classmethod
    def from_dict(cls, data):
        values = dict(data)
        values["items"] = tuple(CostItem(**item) for item in values["items"])
        for name in ("missing_scope", "source_references", "notes"):
            values[name] = tuple(values.get(name, ()))
        return cls(**values)


@dataclass(frozen=True)
class Product:
    """A product installed outside the layered envelope, such as ductwork or glazing.

    Core installs ``quantity_per_driver`` units for every driver unit; ``unit`` is
    "item", "m" or "m2". Mass per unit and either a Boverket resource or a
    ``CarbonReference`` stated per the same unit let LCA assess it.
    """

    product_id: str
    description: str
    driver: str
    unit: str
    quantity_per_driver: float = 1.0
    mass_kg_per_unit: float | None = None
    boverket_id: str | None = None
    basis: str = ""
    carbon_reference: CarbonReference | None = None

    def __post_init__(self):
        if not self.product_id.strip() or not self.description.strip():
            raise ValueError("Products require an identity and description")
        object.__setattr__(self, "driver", _driver(self.driver))
        if self.unit not in {"item", "m", "m2"}:
            raise ValueError("Product unit must be item, m or m2")
        reference = self.carbon_reference
        if isinstance(reference, Mapping):
            reference = CarbonReference.from_dict(reference)
            object.__setattr__(self, "carbon_reference", reference)
        if reference is not None:
            if not isinstance(reference, CarbonReference):
                raise ValueError("carbon_reference must be a CarbonReference")
            if self.boverket_id:
                raise ValueError("Use either a Boverket record or a carbon reference, not both")
            if reference.unit != self.unit:
                raise ValueError(f"{self.product_id}: carbon reference is per {reference.unit}, "
                                 f"the product per {self.unit}")
        object.__setattr__(self, "quantity_per_driver",
                           _positive(self.quantity_per_driver, "quantity_per_driver"))
        if self.mass_kg_per_unit is not None:
            object.__setattr__(self, "mass_kg_per_unit",
                               _positive(self.mass_kg_per_unit, "mass_kg_per_unit"))

    def to_dict(self):
        return {"product_id": self.product_id, "description": self.description,
                "driver": self.driver, "unit": self.unit,
                "quantity_per_driver": self.quantity_per_driver,
                "mass_kg_per_unit": self.mass_kg_per_unit, "boverket_id": self.boverket_id,
                "basis": self.basis,
                "carbon_reference": None if self.carbon_reference is None
                else self.carbon_reference.to_dict()}


@dataclass(frozen=True)
class VentilationLayout:
    """Design assumptions Core uses to derive ventilation quantities from geometry.

    ``new_duct_systems`` maps the existing system to the number of duct networks
    (supply, exhaust) that must be installed; ``new_terminals`` names which
    terminal kinds are new for each existing system.
    """

    mechanical_vent_l_s_m2: float
    supply_area_per_terminal_m2: float
    exhaust_area_per_terminal_m2: float
    branch_length_m: float
    main_duct_m_per_m2: float
    riser_area_m2: float
    ahu_max_airflow_l_s: float
    new_duct_systems: Mapping[str, int]
    new_terminals: Mapping[str, tuple[str, ...]]
    basis: str = ""

    def __post_init__(self):
        for name in ("mechanical_vent_l_s_m2", "supply_area_per_terminal_m2",
                     "exhaust_area_per_terminal_m2", "branch_length_m", "main_duct_m_per_m2",
                     "riser_area_m2", "ahu_max_airflow_l_s"):
            object.__setattr__(self, name, _positive(getattr(self, name), name))
        systems = dict(self.new_duct_systems)
        terminals = {k: tuple(v) for k, v in dict(self.new_terminals).items()}
        if set(systems) != set(VENTILATION_SYSTEMS) or set(terminals) != set(VENTILATION_SYSTEMS):
            raise ValueError("Layouts must state new ducts and terminals for S, F, FT and FTX")
        if any(isinstance(v, bool) or v not in (0, 1, 2) for v in systems.values()):
            raise ValueError("New duct systems must be 0, 1 or 2")
        if any(set(v) - {"supply", "exhaust"} for v in terminals.values()):
            raise ValueError("Terminal kinds are supply and exhaust")
        object.__setattr__(self, "new_duct_systems", systems)
        object.__setattr__(self, "new_terminals", terminals)

    def to_dict(self):
        return {name: getattr(self, name) for name in (
            "mechanical_vent_l_s_m2", "supply_area_per_terminal_m2",
            "exhaust_area_per_terminal_m2", "branch_length_m", "main_duct_m_per_m2",
            "riser_area_m2", "ahu_max_airflow_l_s")} | {
            "new_duct_systems": dict(self.new_duct_systems),
            "new_terminals": {k: list(v) for k, v in self.new_terminals.items()},
            "basis": self.basis}



class Payload:
    """What a candidate installs. Subclasses are frozen dataclasses registered by ``kind``."""

    kind: ClassVar[str]

    @property
    def target_role(self):
        """Envelope role the payload installs on; None for building-level payloads."""
        return getattr(self, "role", None)

    def check(self, measure_type):
        """Reject a payload that contradicts its measure type."""
        if measure_type.roles and self.target_role not in measure_type.roles:
            raise ValueError(f"{measure_type.name} applies to "
                             f"{[r.value for r in measure_type.roles]}")
        if not measure_type.roles and self.target_role is not None:
            raise ValueError(f"{measure_type.name} does not target an envelope role")

    def for_type(self, measure_type):
        """Fill defaults that the measure type fixes."""
        return self

    def resolve(self, records):
        """Return a copy with referenced records attached; ``records`` holds lookups."""
        return self

    def applies_to(self, construction, *, roof_topology=None, ventilation=None):
        return True

    def operations_for(self, element):
        """Construction operations for one envelope element; None for system payloads."""
        return None

    def to_dict(self):
        result = {"kind": self.kind}
        for name in self.__dataclass_fields__:
            if self.__dataclass_fields__[name].metadata.get("resolved"):
                continue
            value = getattr(self, name)
            result[name] = (value.value if isinstance(value, BuildingElement)
                            else value.to_dict() if hasattr(value, "to_dict")
                            else list(value) if isinstance(value, tuple)
                            else dict(value) if isinstance(value, Mapping) else value)
        return result

    @staticmethod
    def from_dict(data):
        values = dict(data)
        kind = values.pop("kind")
        if kind not in PAYLOADS:
            raise ValueError(f"Unknown payload kind: {kind}")
        return PAYLOADS[kind](**values)


def _resolved():
    return field(default=None, compare=False, repr=False, metadata={"resolved": True})


@dataclass(frozen=True)
class LayerAddition(Payload):
    """Components added outside or inside an element's retained stack."""

    kind: ClassVar[str] = "layer_addition"
    role: BuildingElement
    component_ids: tuple[str, ...]
    side: str | None = None
    target_boundaries: tuple[str, ...] = ()
    roof_topologies: tuple[str, ...] = ()
    components: tuple[Component, ...] | None = _resolved()

    def __post_init__(self):
        object.__setattr__(self, "role", BuildingElement(self.role))
        for name in ("component_ids", "target_boundaries", "roof_topologies"):
            object.__setattr__(self, name, _texts(getattr(self, name), name))
        if not self.component_ids:
            raise ValueError("Layer additions must name the components they add")
        if self.side not in {None, "exterior", "interior"}:
            raise ValueError("side must be exterior or interior")
        if set(self.target_boundaries) - {"Outdoors", "Ground", "Internal"}:
            raise ValueError("Target boundaries are Outdoors, Ground or Internal")

    def for_type(self, measure_type):
        return self if self.side else replace(self, side=measure_type.placement)

    def resolve(self, records):
        return replace(self, components=tuple(records.component(i) for i in self.component_ids))

    def applies_to(self, construction, *, roof_topology=None, ventilation=None):
        if self.role not in construction.elements:
            return False
        return not (self.roof_topologies and roof_topology not in self.roof_topologies)

    def operations_for(self, element):
        """Exterior additions precede the retained stack; interior ones follow it."""
        if not self.components:
            raise ValueError("Layer addition is not resolved against a catalogue")
        start = 0 if self.side == "exterior" else len(element.components)
        return tuple(ConstructionOperation("add_component", self.role, component=component,
                                           position=start + index)
                     for index, component in enumerate(self.components))


@dataclass(frozen=True)
class WindowSwap(Payload):
    """A window record replacing the installed one; the unit may be retained."""

    kind: ClassVar[str] = "window_swap"
    window_id: str
    typical_window_area_m2: float
    retains_existing: bool = False
    window: WindowElement | None = _resolved()

    role = BuildingElement.WINDOW

    def __post_init__(self):
        if not isinstance(self.window_id, str) or not self.window_id.strip():
            raise ValueError("Window swaps must name the window record they install")
        object.__setattr__(self, "typical_window_area_m2",
                           _positive(self.typical_window_area_m2, "typical_window_area_m2"))

    def for_type(self, measure_type):
        return replace(self, retains_existing=measure_type.retains_existing)

    def resolve(self, records):
        return replace(self, window=records.window(self.window_id))

    def applies_to(self, construction, *, roof_topology=None, ventilation=None):
        return self.role in construction.elements

    def operations_for(self, element):
        return (ConstructionOperation("replace_element", self.role, element=self.window),)


@dataclass(frozen=True)
class SystemSwap(Payload):
    """A ventilation template with the candidate's airflow and duct layout."""

    kind: ClassVar[str] = "system_swap"
    template_id: str
    layout: VentilationLayout
    airflow: Mapping = field(default_factory=dict)
    from_ventilation: tuple[str, ...] = ()
    template: HVACTemplate | None = _resolved()

    def __post_init__(self):
        if isinstance(self.layout, Mapping):
            object.__setattr__(self, "layout", VentilationLayout(**self.layout))
        object.__setattr__(self, "from_ventilation",
                           _texts(self.from_ventilation, "from_ventilation"))
        if set(self.from_ventilation) - set(VENTILATION_SYSTEMS):
            raise ValueError("from_ventilation must name S, F, FT or FTX systems")

    def resolve(self, records):
        return replace(self, template=records.template(self.template_id))

    def applies_to(self, construction, *, roof_topology=None, ventilation=None):
        return ventilation is None or not self.from_ventilation or ventilation in self.from_ventilation

    def operation(self, template_id, source_references=()):
        """The HVAC replacement with this airflow design applied to the template."""
        if self.template is None:
            raise ValueError("System swap is not resolved against a catalogue")
        values = {key: dict(value) if isinstance(value, Mapping) else value
                  for key, value in self.template.values.items()}
        values["airflow"] = {**values.get("airflow", {}), **dict(self.airflow),
                             "mechanical_vent_l_s_m2": self.layout.mechanical_vent_l_s_m2}
        template = HVACTemplate(template_id, values,
                                (*self.template.source_references, *source_references),
                                self.template.notes)
        return SystemOperation("replace_hvac", template)


@dataclass(frozen=True)
class PVArray(Payload):
    """Array orientation, roof coverage and module assumptions for roof PV sizing.

    Coverage is the share of roof area used: ``flat_roof_share`` of the footprint
    on flat roofs, ``pitched_roof_share`` of the actual roof surface otherwise.
    """

    kind: ClassVar[str] = "pv_array"
    tilt_deg: float
    azimuth_deg: float
    module_w_m2: float
    system_losses_pct: float
    flat_roof_share: float
    pitched_roof_share: float
    basis: str = ""

    def __post_init__(self):
        if not 0 <= self.tilt_deg <= 90 or not 0 <= self.azimuth_deg < 360:
            raise ValueError("PV tilt or azimuth out of range")
        _positive(self.module_w_m2, "module_w_m2")
        if not 0 <= self.system_losses_pct < 100:
            raise ValueError("PV system losses must be a percentage below 100")
        for name in ("flat_roof_share", "pitched_roof_share"):
            if not 0 < getattr(self, name) <= 1:
                raise ValueError(f"{name} must be in (0, 1]")

    def operation(self, dc_capacity_kw):
        return PVOperation("add_pv", dc_capacity_kw, self.tilt_deg, self.azimuth_deg,
                           self.system_losses_pct)


@dataclass(frozen=True)
class DHWReduction(Payload):
    """A fractional cut in domestic hot-water use."""

    kind: ClassVar[str] = "dhw_reduction"
    fraction: float

    def __post_init__(self):
        object.__setattr__(self, "fraction", _fraction(self.fraction, "DHW reduction"))

    def operation(self):
        return DHWOperation("reduce_dhw", self.fraction)


@dataclass(frozen=True)
class Airtightness(Payload):
    """A nominal infiltration reduction for a fully renovated envelope."""

    kind: ClassVar[str] = "airtightness"
    nominal_reduction: float

    def __post_init__(self):
        object.__setattr__(self, "nominal_reduction",
                           _fraction(self.nominal_reduction, "Infiltration reduction"))

    def operation(self, envelope_share):
        """The reduction scaled by the share of envelope area its hosts renovated."""
        if not 0 < envelope_share <= 1:
            raise ValueError("Renovated envelope share must be in (0, 1]")
        return AirtightnessOperation("reduce_infiltration", self.nominal_reduction * envelope_share)


PAYLOADS = {cls.kind: cls for cls in (LayerAddition, WindowSwap, SystemSwap, PVArray,
                                       DHWReduction, Airtightness)}


@dataclass(frozen=True)
class MeasureType:
    """Fixed physical meaning of one renovation measure type and the payload it takes."""

    name: str
    payload: type[Payload]
    roles: tuple[BuildingElement, ...] = ()
    placement: str | None = None
    description: str = ""
    retains_existing: bool = False
    needs_products: bool = False
    hosts: tuple[str, ...] = ()
    priced_with_host: bool = False

    @property
    def standalone(self):
        """Dependent types are only applied with one of their host measure types."""
        return not self.hosts


MEASURE_TYPES = {m.name: m for m in (
    MeasureType("insulate_wall", LayerAddition, (BuildingElement.EXT_WALL,), "exterior",
                "Add insulation and a finish to the wall; outside by default."),
    MeasureType("insulate_roof", LayerAddition, (BuildingElement.TOP_FLOOR, BuildingElement.ROOF),
                "exterior", "Add insulation on the cold side of the attic floor or flat roof."),
    MeasureType("insulate_basement", LayerAddition,
                (BuildingElement.BASEMENT_WALL, BuildingElement.GROUND_FLOOR), "interior",
                "Add insulation to ground-contact elements or under an unheated basement ceiling."),
    MeasureType("replace_window", WindowSwap, (BuildingElement.WINDOW,),
                description="Remove the whole window unit and install a new one."),
    MeasureType("upgrade_window", WindowSwap, (BuildingElement.WINDOW,),
                description="Retain the existing frame and sashes and install new glazing.",
                retains_existing=True, needs_products=True),
    MeasureType("upgrade_ventilation", SystemSwap,
                description="Install a new ventilation system and the ductwork it needs."),
    MeasureType("install_pv", PVArray,
                description="Install a roof PV array sized from the available roof area."),
    MeasureType("reduce_dhw", DHWReduction,
                description="Install low-flow taps and shower heads that reduce hot-water use."),
    MeasureType("seal_envelope", Airtightness,
                description="Tighter joints achieved by the host work; never applied by itself.",
                hosts=("replace_window", "insulate_wall"), priced_with_host=True),
)}


@dataclass(frozen=True)
class RenovationCandidate:
    """One installable option: identity, sources, cost and the payload it installs.

    ``companion_candidates`` are the resolved dependent candidates named by
    ``companions``; they are attached by the catalogue and not serialized.
    """

    candidate_id: str
    measure_type: str
    name: str
    payload: Payload
    description: str = ""
    performance: Mapping = field(default_factory=dict)
    service_life_years: float | None = None
    products: tuple[Product, ...] = ()
    cost: CostEstimate | None = None
    companions: tuple[str, ...] = ()
    source_references: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    companion_candidates: tuple = field(default=(), compare=False, repr=False)

    def __post_init__(self):
        kind = MEASURE_TYPES.get(self.measure_type)
        if kind is None:
            raise ValueError(f"Unknown measure type: {self.measure_type}")
        if not self.candidate_id.strip() or not self.name.strip():
            raise ValueError("Candidates require an identity and a name")
        payload = Payload.from_dict(self.payload) if isinstance(self.payload, Mapping) else self.payload
        if not isinstance(payload, kind.payload):
            raise ValueError(f"{self.measure_type} takes a {kind.payload.kind} payload")
        payload.check(kind)
        object.__setattr__(self, "payload", payload.for_type(kind))
        for name in ("source_references", "notes", "companions"):
            object.__setattr__(self, name, _texts(getattr(self, name), name))
        object.__setattr__(self, "products", tuple(
            p if isinstance(p, Product) else Product(**p) for p in self.products))
        if isinstance(self.cost, Mapping):
            object.__setattr__(self, "cost", CostEstimate.from_dict(self.cost))
        if kind.needs_products and not self.products:
            raise ValueError(f"{self.measure_type} must name the product it installs")
        if not kind.standalone and (self.products or self.companions):
            raise ValueError("Dependent measures add no products and have no companions")
        if self.companions and self.measure_type not in {
                h for t in MEASURE_TYPES.values() for h in t.hosts}:
            raise ValueError(f"{self.measure_type} cannot host dependent measures")
        if self.service_life_years is not None:
            object.__setattr__(self, "service_life_years",
                               _positive(self.service_life_years, "service_life_years"))

    @property
    def kind(self):
        return MEASURE_TYPES[self.measure_type]

    @property
    def role(self):
        return self.payload.target_role

    def applies_to(self, construction, *, roof_topology=None, ventilation=None):
        """Whether the candidate can be installed on a construction set or system."""
        if not self.kind.standalone:
            return any(set(MEASURE_TYPES[h].roles) & set(construction.elements)
                       for h in self.kind.hosts)
        return self.payload.applies_to(construction, roof_topology=roof_topology,
                                       ventilation=ventilation)

    def to_dict(self):
        return {"candidate_id": self.candidate_id, "measure_type": self.measure_type,
                "name": self.name, "description": self.description,
                "payload": self.payload.to_dict(), "performance": dict(self.performance),
                "service_life_years": self.service_life_years,
                "products": [p.to_dict() for p in self.products],
                "cost": self.cost.to_dict() if self.cost else None,
                "companions": list(self.companions),
                "source_references": list(self.source_references), "notes": list(self.notes)}


class _Records:
    """Reference lookups for payload resolution: renovation records first, then LoD2."""

    def __init__(self, library, components, windows):
        self.library, self.components, self.windows = library, components, windows

    def component(self, identifier):
        return self.components.get(identifier) or self.library.components[identifier]

    def window(self, identifier):
        return self.windows.get(identifier) or self.library.windows[identifier]

    def template(self, identifier):
        return self.library.hvac_templates[identifier]


class RenovationCatalogue:
    """Candidates per measure type with their resolved records and cost overlays.

    The catalogue is independent of archetype renovation states.

    Parameters
    ----------
    candidates : iterable of RenovationCandidate, optional
        Definitions with unique identities.
    boverket_resources : mapping, optional
        Source records for products' Boverket references.
    """

    def __init__(self, candidates: Iterable[RenovationCandidate] = (), *,
                 boverket_resources=None, dataset_id=None):
        self._candidates = {}
        for candidate in candidates:
            if candidate.candidate_id in self._candidates:
                raise ValueError(f"Duplicate candidate: {candidate.candidate_id}")
            self._candidates[candidate.candidate_id] = candidate
        for candidate in self._candidates.values():
            for companion_id in candidate.companions:
                companion = self._candidates.get(companion_id)
                if companion is None or candidate.measure_type not in companion.kind.hosts:
                    raise ValueError(f"{candidate.candidate_id} names {companion_id}, which it "
                                     "cannot host")
            object.__setattr__(candidate, "companion_candidates",
                               tuple(self._candidates[i] for i in candidate.companions))
        self.boverket_resources = dict(boverket_resources or {})
        self.dataset_id = dataset_id

    def __iter__(self):
        return iter(self._candidates.values())

    def __len__(self):
        return len(self._candidates)

    def __contains__(self, candidate_id):
        return candidate_id in self._candidates

    def get(self, candidate_id):
        return self._candidates[candidate_id]

    def filter(self, measure_type=None, *, role=None):
        role = None if role is None else BuildingElement(role)
        return tuple(c for c in self if (measure_type is None or c.measure_type == measure_type)
                     and (role is None or c.role == role))

    @classmethod
    def load(cls, library, path=None, *, costs=None):
        """Load candidates and resolve their references against a loaded LoD2 catalogue.

        Parameters
        ----------
        library : epsm_data.Catalogue
            Source of components, window records and ventilation templates.
        path : path-like, optional
            Renovation dataset; the bundled one by default.
        costs : path-like or mapping, optional
            Cost overlay keyed by candidate ID, ``"<measure_type>/<role>"`` or
            ``"<measure_type>"``; the most specific key wins. Licensed price data
            belongs in such an overlay, outside the repository.
        """
        if path is None:
            source = files("epsm_data.datasets.renovation").joinpath("catalogue.json")
            data = json.loads(source.read_text(encoding="utf-8"))
        else:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != 2:
            raise ValueError("Unsupported renovation catalogue schema")
        overlay = _cost_overlay(costs)
        records = _Records(library, _physical_records(data, library),
                           {key: WindowElement(**record)
                            for key, record in data.get("windows", {}).items()})
        candidates = []
        for record in data["candidates"]:
            values = dict(record)
            payload = Payload.from_dict(values["payload"])
            try:
                values["payload"] = payload.resolve(records)
            except KeyError as error:
                raise ValueError(f"{values['candidate_id']} references unknown record {error}") from None
            role = payload.target_role.value if payload.target_role else None
            for key in (values["candidate_id"], f"{values['measure_type']}/{role}",
                        values["measure_type"]):
                if key in overlay:
                    values["cost"] = overlay[key]
                    break
            candidates.append(RenovationCandidate(**values))
        referenced = {p.boverket_id for c in candidates for p in c.products if p.boverket_id}
        return cls(candidates, boverket_resources=_boverket_resources(referenced),
                   dataset_id=data.get("dataset_id"))

    def readiness(self, library):
        """Check that every measure type can be installed on every archetype as it stands.

        Each archetype is tested in its current construction: Existing where the
        archetype has renovation states, otherwise its single default state. The
        Standard and Advanced states are earlier renovations of the stock, not
        outcomes of this catalogue, so they are never targets or references here.

        Returns
        -------
        dict
            Per measure type: candidate and priced counts, archetypes with at least
            one installable candidate and the archetypes without one. ``ready`` is
            True when every type has candidates and no applicable archetype is
            left without an installable candidate.
        """
        bases = {}
        for archetype_id, record in library.archetype_records.items():
            state = "existing" if "existing" in record["states"] else None
            details = record["states"]["existing" if state else next(iter(record["states"]))]
            bases[archetype_id] = (library.get(archetype_id, state=state).construction_set,
                                   details.get("roof_topology"))
        types, failures = {}, []
        for name, kind in MEASURE_TYPES.items():
            candidates = self.filter(name)
            installable, uncovered = set(), []
            for archetype_id, (construction, topology) in bases.items():
                if kind.roles and not set(kind.roles) & set(construction.elements):
                    continue
                for candidate in candidates:
                    if not candidate.applies_to(construction, roof_topology=topology):
                        continue
                    try:
                        if candidate.role is not None:
                            result = construction
                            for operation in candidate.payload.operations_for(
                                    construction.elements[candidate.role]):
                                result = operation.apply(result)
                    except ValueError as error:
                        failures.append({"candidate_id": candidate.candidate_id,
                                         "archetype_id": archetype_id, "error": str(error)})
                        continue
                    installable.add(archetype_id)
                if archetype_id not in installable:
                    uncovered.append(archetype_id)
            # Dependent work priced with its host needs no estimate of its own.
            types[name] = {"candidates": len(candidates),
                           "priced": sum(c.cost is not None or kind.priced_with_host
                                         for c in candidates),
                           "fully_priced": sum(kind.priced_with_host or (
                               c.cost is not None and c.cost.coverage == "complete")
                               for c in candidates),
                           "archetypes": len(installable), "uncovered": sorted(uncovered)}
        return {"ready": all(t["candidates"] and not t["uncovered"] for t in types.values())
                and not failures,
                "archetypes": len(bases), "measure_types": types, "failures": failures}


def _physical_records(data, library):
    """Build renovation-only materials, layers and components; LoD2 records stay untouched.

    Materials state their thermal properties and a Boverket reference; layers may
    mix them with LoD2 materials by ID. Returns components by ID.
    """
    from uuid import NAMESPACE_URL, uuid5

    from ..domain import Layer, LayerMaterial, LayerSlot, OpaqueMaterial
    from ..domain.enums import ShearingLayer
    from ..sources.records import carbon_record

    records = data.get("materials", {})
    resources = _boverket_resources({r["boverket_id"] for r in records.values() if r.get("boverket_id")})
    materials = {}
    for mid, record in records.items():
        values = {k: v for k, v in record.items() if k not in {"basis"}}
        bov = values.get("boverket_id")
        values.update(json_id=mid, material_type="renovation",
                      embodied_carbon=carbon_record(resources[bov], values["name"]) if bov else None,
                      uuid=uuid5(NAMESPACE_URL, f"epsm:material:{mid}"))
        materials[mid] = OpaqueMaterial(**values)
    layers = {}
    for lid, record in data.get("layers", {}).items():
        shares = tuple(LayerMaterial(materials.get(m["material_id"]) or library.materials[m["material_id"]],
                                     m.get("area_fraction", 1.0), m["thickness"])
                       for m in record["materials"])
        layers[lid] = Layer(record["name"], lid, record["thickness"], shares)
    components = {}
    for cid, record in data.get("components", {}).items():
        slots = tuple(LayerSlot(layers.get(lid) or library.layers[lid], position)
                      for position, lid in enumerate(record["layers"]))
        components[cid] = Component(record["name"], "renovation",
                                    BuildingElement(record["application"]), slots,
                                    ShearingLayer(record["shearing_layer"]))
    return components


def _cost_overlay(costs):
    if costs is None:
        return {}
    data = costs if isinstance(costs, Mapping) else json.loads(Path(costs).read_text(encoding="utf-8"))
    data = data.get("costs", data)
    return {key: CostEstimate.from_dict(value) for key, value in data.items()}


def _boverket_resources(identifiers):
    if not identifiers:
        return {}
    source = files("epsm_data.datasets.sources").joinpath("boverket.json")
    resources = json.loads(source.read_text(encoding="utf-8"))["Resources"]
    found = {str(r["ResourceId"]): r for r in resources if str(r["ResourceId"]) in identifiers}
    missing = set(identifiers) - set(found)
    if missing:
        raise ValueError(f"Boverket resources are not in the pinned source: {sorted(missing)}")
    return found
