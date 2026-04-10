"""Renovation domain model.

─────────────────────────────────────────────────────────────────────
MEASURE DEFINITION
─────────────────────────────────────────────────────────────────────
A RenovationMeasure is a *template* — it describes what CAN be done.
A RenovationEvent (on the Building) records what WAS done.

class RenovationMeasure:
    measure_id: str               # canonical key, e.g. "ventilation.install_ftx"
    category: MeasureCategory     # enum: OPERATIONAL, SYSTEMS, ENVELOPE, RENEWABLES
    target_scope: str             # what part of the building it touches
    sv_label: str                 # Swedish display name
    description: str
    required_params: dict         # parameter schema for application
    typical_cost_sek_per_unit: float | None
    typical_embodied_carbon: float | None
    expected_service_life_years: int | None
    applicability_rules: list     # conditions under which this measure applies


class MeasureCategory(Enum):
    OPERATIONAL = "operational"    # controls, schedules, setpoints
    SYSTEMS = "systems"           # ventilation, heating, DHW
    ENVELOPE = "envelope"         # insulation, windows, airtightness
    RENEWABLES = "renewables"     # PV, solar thermal, storage


─────────────────────────────────────────────────────────────────────
APPLICATION RECORD
─────────────────────────────────────────────────────────────────────
class RenovationEvent:
    event_id: UUID
    measure_id: str                        # links to catalog
    applied_year: int
    trigger: RenovationTrigger             # why it happened
    target_element_role: BuildingElement    # which element slot was affected
    removed_components: list[str]          # component IDs taken out
    added_components: list[str]            # component IDs installed
    parameters: dict                       # thickness, material_id, etc.
    construction_set_before: UUID          # snapshot reference
    construction_set_after: UUID           # snapshot reference
    cost_sek: float | None
    embodied_carbon_delta_kg: float | None
    notes: str | None


class RenovationTrigger(Enum):
    END_OF_LIFE = "end_of_life"            # component exceeded service life
    POLICY = "policy"                       # regulatory requirement
    PIGGYBACK = "piggyback"                # done alongside another triggered work
    USER_CHOICE = "user_choice"            # manual scenario decision
    AGING_ENGINE = "aging_engine"          # auto-triggered by simulation


─────────────────────────────────────────────────────────────────────
LINEAGE
─────────────────────────────────────────────────────────────────────
Each RenovationEvent links a before/after ConstructionSet UUID.
This forms a directed chain:

  baseline_v0 ──[event_1]──> v1 ──[event_2]──> v2 ...

Scenarios can branch from any version.
"""


def define_renovation_model() -> None:
    """Implement renovation entities and lineage structures per guidance above."""
    raise NotImplementedError("Define renovation entities in domain/renovation.py")
