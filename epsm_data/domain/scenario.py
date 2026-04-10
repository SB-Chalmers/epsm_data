"""Scenario and timeline model.

─────────────────────────────────────────────────────────────────────
SCENARIO
─────────────────────────────────────────────────────────────────────
A Scenario defines the assumptions under which a simulation runs.
Multiple scenarios can share the same baseline building but apply
different measure sequences, policies, or timing.

class Scenario:
    scenario_id: UUID
    name: str                             # e.g. "baseline", "deep_renovation", "systems_only"
    description: str
    baseline_building_name: str           # starting archetype
    start_year: int                       # simulation start
    end_year: int                         # simulation end
    time_step_years: int                  # e.g. 1, 5, 10
    seed: int | None                      # for stochastic runs

    # ── policy assumptions ──
    measure_sequence: list[str]           # ordered measure_ids to apply
    trigger_policy: TriggerPolicy         # when measures fire
    replacement_lag_years: dict[str, int] # component_type -> typical delay beyond service life
    degradation_model: str                # "linear" | "stepped" | "custom"

    # ── outputs ──
    results: list[ScenarioStepResult]     # populated after simulation


class TriggerPolicy:
    '''Rules for when measures are applied.

    Examples:
    - "apply all at year X"
    - "apply when component age > service_life + lag"
    - "apply when policy mandates by BBR threshold"
    '''
    ...


class ScenarioStepResult:
    '''Snapshot of building state at one simulation timestep.

    year: int
    construction_set_version: UUID
    envelope_u_values: dict[str, float]
    total_energy_demand_kwh_m2: float | None
    cumulative_cost_sek: float
    cumulative_embodied_carbon_kg: float
    events_this_step: list[RenovationEvent]
    '''
    ...

─────────────────────────────────────────────────────────────────────
KEY RULES
─────────────────────────────────────────────────────────────────────
1. Scenarios are configuration, not domain mutations.
2. Building state branches per scenario — the baseline is never altered.
3. Results are append-only per timestep.
4. Comparison across scenarios uses matched ScenarioStepResults.
"""


def define_scenario_model() -> None:
    """Implement simulation scenario model per guidance above."""
    raise NotImplementedError("Define scenario entities in domain/scenario.py")
