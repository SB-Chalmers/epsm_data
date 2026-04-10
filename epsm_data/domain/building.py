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

5. The consumption contract is the ONLY coupling point between
   epsm_data and the downstream geolocated-building library.
   Keep it stable and versioned.
"""


def define_building_archetype_model() -> None:
    """Implement BuildingArchetype model per guidance above."""
    raise NotImplementedError("Define BuildingArchetype in domain/building.py")
