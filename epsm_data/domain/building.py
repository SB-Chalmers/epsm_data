"""Building archetype entity.

The BuildingArchetype is the central stateful container in THIS library.
It is a reusable template — NOT a geolocated building instance.

─────────────────────────────────────────────────────────────────────
ARCHITECTURAL BOUNDARY
─────────────────────────────────────────────────────────────────────
epsm_data defines *archetypes*: material stacks, thermal properties,
renovation histories, and aging behavior — independent of geometry,
orientation, climate zone, or site.

A downstream library (e.g. building_sim) instantiates a
*GeolocatedBuilding* by combining:

    GeolocatedBuilding = BuildingArchetype + FootprintGeometry + SiteContext

This means the archetype must expose a clean, serializable contract
that the downstream library can consume without importing epsm_data
internals.

─────────────────────────────────────────────────────────────────────
CORE CONCEPT
─────────────────────────────────────────────────────────────────────
A BuildingArchetype holds a *construction set* — the full collection
of elements that define its thermal envelope and internal partitions
at a point in time.  Renovation measures mutate the construction set
and produce a new version while preserving the previous one.

─────────────────────────────────────────────────────────────────────
DATASTRUCTURE GUIDANCE
─────────────────────────────────────────────────────────────────────

class BuildingArchetype:
    # ── identity ──
    archetype_id: str                  # e.g. "CMF_1950"
    display_name: str                  # human-readable label
    construction_year: int             # original year built
    building_typology: str             # e.g. "multi_family" | "single_family"

    # ── current construction set (mutable over time) ──
    construction_set: ConstructionSet  # see below

    # ── renovation history (append-only log) ──
    renovation_log: list[RenovationEvent]  # ordered by applied_year

    # ── derived / cached ──
    @property
    def current_year(self) -> int:
        '''Latest year reflected in the state (construction_year + events).'''
        ...

    @property
    def envelope_u_values(self) -> dict[str, float]:
        '''Current U-values keyed by element role.'''
        ...

    def to_consumption_contract(self) -> dict:
        '''Export archetype state as a flat, serializable dict that the
        downstream geolocated-building library can consume.

        Must include:
        - archetype_id, construction_year
        - per-element-role: U-value, component list, layer stack
        - renovation_log summary
        - service-life metadata per component
        - degradation state / performance factors
        '''
        ...

class ConstructionSet:
    '''Immutable snapshot of the archetype's physical makeup at one point.

    version_id: UUID
    valid_from_year: int
    elements: dict[BuildingElement, Element]   # role -> element instance
    '''
    ...


class RenovationEvent:
    '''One applied measure with full provenance.

    measure_id: str               # catalog key, e.g. "ventilation.install_ftx"
    applied_year: int
    trigger: str                  # "end_of_life" | "policy" | "piggyback" | "user"
    removed_components: list      # what was taken out
    added_components: list        # what was put in
    construction_set_before: UUID # version ref
    construction_set_after: UUID  # version ref
    cost_sek: float | None
    embodied_carbon_delta: float | None
    '''
    ...

─────────────────────────────────────────────────────────────────────
DOWNSTREAM CONSUMPTION CONTRACT
─────────────────────────────────────────────────────────────────────
The downstream library should be able to do:

    from epsm_data import load_archetype

    archetype = load_archetype("CMF_1950")
    contract  = archetype.to_consumption_contract()

    # In downstream library:
    building = GeolocatedBuilding(
        archetype=contract,
        footprint=footprint_polygon,
        orientation_deg=45,
        climate_zone="Stockholm",
        num_floors=4,
        heated_area_m2=2400,
    )
    results = building.run_energy_simulation()

The contract dict must be self-contained — no object references back
into epsm_data internals.

─────────────────────────────────────────────────────────────────────
KEY DESIGN RULES
─────────────────────────────────────────────────────────────────────
1. The BuildingArchetype must hold ACTUAL Element/Component objects,
   not just name strings.  U-values must be computable at any point.

2. ConstructionSet is immutable.  Applying a measure creates a NEW
   ConstructionSet and appends a RenovationEvent to the log.

3. The renovation_log is the audit trail.  It must never be cleared.

4. Multiple scenarios can share the same archetype identity but diverge
   at different RenovationEvents (branching history). 
   
   How does this work in practice?

5. The consumption contract is the ONLY coupling point between
   epsm_data and the downstream geolocated-building library.
   Keep it stable and versioned.
"""

from dataclasses import dataclass, field
from typing import Tuple, ClassVar
from epsm_data.domain.enums import BuildingElement
from epsm_data.domain.element import Elements, WindowElement
from datetime import datetime
from uuid import UUID, uuid4

@dataclass(frozen=True)
class ConstructionSet:
    version_id: UUID
    valid_from_year: int
    elements: dict[BuildingElement, Elements | WindowElement]

    def __post_init__(self):
        if not self.elements:
            raise ValueError("ConstructionSet must contain at least one element.")
        # if not (9 <= len(self.elements) <= 13):
        #    raise ValueError(f"ConstructionSet has {len(self.elements)} elements, expected between 9 and 13 for a complete building.")
        if self.valid_from_year < 1800 or self.valid_from_year > datetime.now().year:
            raise ValueError(f"valid_from_year {self.valid_from_year} is out of realistic range.")
        

    @property
    def u_values(self) -> dict[str, float]:
        return {role.value: element.u_value for role, element in self.elements.items()}

    def to_dict(self) -> dict:
        return {
            "version_id": str(self.version_id),
            "valid_from_year": self.valid_from_year,
            "elements": [
                {
                    "element_name": element.name,
                    "element_type": role.value,
                }
                for role, element in self.elements.items()
            ],
        }
    
@dataclass(frozen=True)
class RenovationEvent:
    '''One applied measure with full provenance.'''
    measure_id: str               # catalog key, e.g. "ventilation.install_ftx"
    applied_year: int
    trigger: str                  # "end_of_life" | "policy" | "piggyback" | "user"
    removed_components: tuple[str, ...]      # what was taken out
    added_components: tuple[str, ...]        # what was put in
    construction_set_before: UUID # version ref
    construction_set_after: UUID  # version ref
    cost_sek: float | None
    embodied_carbon_delta: float | None

    VALID_TRIGGERS: ClassVar[tuple] = ("end_of_life", "policy", "piggyback", "user")

    def __post_init__(self):
        if self.trigger not in self.VALID_TRIGGERS:
            raise ValueError(f"Invalid trigger '{self.trigger}'. Must be one of {self.VALID_TRIGGERS}.")

    def to_dict(self) -> dict:
        return {
            "measure_id": self.measure_id,
            "applied_year": self.applied_year,
            "trigger": self.trigger,
            "removed_components": list(self.removed_components),
            "added_components": list(self.added_components),
            "construction_set_before": str(self.construction_set_before),
            "construction_set_after": str(self.construction_set_after),
            "cost_sek": self.cost_sek,
            "embodied_carbon_delta": self.embodied_carbon_delta,
        }



@dataclass # Mutable
class BuildingArchetype:
    archetype_id: str
    display_name: str
    construction_year: int
    building_typology: str
    construction_set: ConstructionSet
    heating_system: str
    ventilation_system: str
    renovation_log: list[RenovationEvent] = field(default_factory=list)
    cold_attic: bool = False
    window_to_wall_ratio: float = 0.2
    infiltration_rate: float = 0.5


    def __post_init__(self):
        if self.construction_year < 1800 or self.construction_year > datetime.now().year:
            raise ValueError(f"Construction year {self.construction_year} is out of realistic range.")
        if not self.archetype_id:
            raise ValueError("Archetype ID cannot be empty.")
        if not self.display_name:
            raise ValueError("Display name cannot be empty.")
        if self.building_typology not in ("multi_family", "single_family"):
            raise ValueError(f"Invalid building typology: {self.building_typology}")
        if self.cold_attic is None:
            raise ValueError("cold_attic must be a boolean value.")
        if self.window_to_wall_ratio < 0 or self.window_to_wall_ratio > 1:
            raise ValueError("window_to_wall_ratio must be between 0 and 1.")
        if self.window_to_wall_ratio > 0.5:
            raise ValueError("window_to_wall_ratio above 0.5 is unusually high")
        if self.infiltration_rate < 0:
            raise ValueError("infiltration_rate cannot be negative.")
        # if self.heating_system == "unknown":
        #     raise ValueError("heating_system must be specified.")
        # if self.ventilation_system == "unknown":
        #     raise ValueError("ventilation_system must be specified.")
        
    @property
    def current_year(self) -> int:
        if self.renovation_log:
            return max(e.applied_year for e in self.renovation_log)
        return self.construction_year

    @property
    def envelope_u_values(self) -> dict[str, float]:
        return self.construction_set.u_values
    
    def apply_renovation(
        self,
        event: RenovationEvent,
        new_elements: dict[BuildingElement, Elements],
    ) -> None:
        # 1. validate applied_year is not before current_year
        # 2. save the current construction_set version_id as old_version_id
        # ...
            raise NotImplementedError("apply_renovation not yet implemented.")
    
    def to_dict(self) -> dict:
        return {
            "archetype_id": self.archetype_id,
            "display_name": self.display_name,
            "construction_year": self.construction_year,
            "building_typology": self.building_typology,
            "current_year": self.current_year,
            "heating_system": self.heating_system,
            "ventilation_system": self.ventilation_system,
            "cold_attic": self.cold_attic,
            "window_to_wall_ratio": self.window_to_wall_ratio,
            "infiltration_rate": self.infiltration_rate,
            "construction_set": self.construction_set.to_dict(),
            "renovation_log": [e.to_dict() for e in self.renovation_log],
        }

    def to_consumption_contract(self) -> dict: #instead of regular to dict as in others
        """Export archetype state as a flat, serializable dict for the
        downstream geolocated-building library. No epsm_data objects leak out.
        """
        elements_contract = {}
        for role, element in self.construction_set.elements.items():
            elements_contract[role.value] = {
                "u_value": round(element.u_value, 6),
                "r_total": round(element.r_total, 6),
                "is_long_lived": element.is_long_lived,
                "components": [
                    {
                        "name": comp.name,
                        "shearing_layer": comp.shearing_layer.value,
                        "thickness": comp.thickness,
                        "is_long_lived": comp.is_long_lived,
                        "layers": [
                            {
                                "layer_code": layer.layer_code,
                                "thickness": layer.thickness,
                                "r_value": round(layer.r_value, 6),
                                "is_long_lived": layer.is_long_lived,
                                "materials": [
                                    {
                                        "name": mat.name,
                                        "conductivity": mat.conductivity,
                                        "density": mat.density,
                                        "service_life_years": mat.service_life_years,
                                        "A1_A3_typical": mat.embodied_carbon.A1_A3_typical,
                                        "A1_A3_conservative": mat.embodied_carbon.A1_A3_conservative,
                                    }
                                    for mat, _, _ in layer.materials
                                ],
                            }
                            for layer, _ in comp.layers
                        ],
                    }
                    for comp in element.components
                ],
            }

        return {
            "contract_version": "1.0",
            "archetype_id": self.archetype_id,
            "display_name": self.display_name,
            "construction_year": self.construction_year,
            "building_typology": self.building_typology,
            "current_year": self.current_year,
            "cold_attic": self.cold_attic,
            "window_to_wall_ratio": self.window_to_wall_ratio,
            "infiltration_rate": self.infiltration_rate,
            "heating_system": self.heating_system,
            "ventilation_system": self.ventilation_system,
            "construction_set_version": str(self.construction_set.version_id),
            "elements": elements_contract,
            "renovation_log": [e.to_dict() for e in self.renovation_log],
        }


    