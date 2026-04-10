"""Renovation measure catalog.

Ordered by typical Swedish cost-effectiveness (best ROI first).
Envelope measures are low priority unless piggyback-triggered.

─────────────────────────────────────────────────────────────────────
CATALOG STRUCTURE
─────────────────────────────────────────────────────────────────────
Each entry is a measure template. The key is the canonical measure_id.
Categories reflect priority tiers, not just building subsystems.

MEASURE_CATALOG = {

    # ── TIER 1: OPERATIONAL (lowest cost, fastest payback) ──────────

    "operational.optimize_controls": {
        "category": "OPERATIONAL",
        "sv_label": "Driftoptimering och styrning",
        "description": "Adjust heating curves, schedules, setpoints, "
                       "and night setback. No physical intervention.",
        "target_scope": "controls",
        "required_params": {},
        "typical_cost_sek_per_m2": 5,
        "expected_service_life_years": None,  # ongoing
        "piggyback_trigger": False,
    },

    "operational.balance_radiators": {
        "category": "OPERATIONAL",
        "sv_label": "Injustering av radiatorsystem",
        "description": "Hydronic balancing of distribution system.",
        "target_scope": "heating_distribution",
        "required_params": {},
        "typical_cost_sek_per_m2": 15,
        "expected_service_life_years": None,
        "piggyback_trigger": False,
    },

    # ── TIER 2: SYSTEMS (moderate cost, significant savings) ────────

    "ventilation.install_ftx": {
        "category": "SYSTEMS",
        "sv_label": "Installera FTX (frånluft-tilluft med värmeåtervinning)",
        "description": "Install balanced ventilation with heat recovery.",
        "target_scope": "ventilation",
        "required_params": {"heat_recovery_efficiency": float},
        "typical_cost_sek_per_m2": 400,
        "expected_service_life_years": 25,
        "piggyback_trigger": False,
    },

    "ventilation.upgrade_sfp": {
        "category": "SYSTEMS",
        "sv_label": "Uppgradera fläktar (lägre SFP)",
        "description": "Replace fans with lower specific fan power.",
        "target_scope": "ventilation",
        "required_params": {"target_sfp": float},
        "typical_cost_sek_per_m2": 80,
        "expected_service_life_years": 20,
        "piggyback_trigger": False,
    },

    "heating.replace_heat_pump": {
        "category": "SYSTEMS",
        "sv_label": "Byt värmekälla till värmepump",
        "description": "Replace heating source with ground/air heat pump.",
        "target_scope": "heating_generation",
        "required_params": {"cop_target": float, "pump_type": str},
        "typical_cost_sek_per_m2": 300,
        "expected_service_life_years": 20,
        "piggyback_trigger": False,
    },

    "heating.replace_distribution": {
        "category": "SYSTEMS",
        "sv_label": "Byt distributionssystem",
        "description": "Upgrade pipes and radiators / install underfloor.",
        "target_scope": "heating_distribution",
        "required_params": {"system_type": str},
        "typical_cost_sek_per_m2": 250,
        "expected_service_life_years": 40,
        "piggyback_trigger": False,
    },

    "dhw.upgrade_system": {
        "category": "SYSTEMS",
        "sv_label": "Uppgradera tappvarmvatten",
        "description": "Insulate pipes, low-flow fixtures, solar preheat.",
        "target_scope": "dhw",
        "required_params": {},
        "typical_cost_sek_per_m2": 50,
        "expected_service_life_years": 25,
        "piggyback_trigger": False,
    },

    # ── TIER 3: ENVELOPE (high cost, usually piggyback-triggered) ───
    # These are rarely done for energy reasons alone.
    # They are triggered by end-of-life, moisture damage, or policy.

    "envelope.airtightness_improve": {
        "category": "ENVELOPE",
        "sv_label": "Tätning av klimatskal",
        "description": "Seal joints, penetrations, and window frames.",
        "target_scope": "airtightness",
        "required_params": {"target_n50": float},
        "typical_cost_sek_per_m2": 100,
        "expected_service_life_years": 30,
        "piggyback_trigger": True,
    },

    "envelope.window_replacement": {
        "category": "ENVELOPE",
        "sv_label": "Fönsterbyte",
        "description": "Replace windows. Usually triggered by end-of-life "
                       "(~30-40 years), not energy savings alone.",
        "target_scope": "window",
        "required_params": {"u_value_target": float, "g_value": float},
        "typical_cost_sek_per_m2": 4000,
        "expected_service_life_years": 35,
        "piggyback_trigger": True,
    },

    "envelope.roof_insulation_attic": {
        "category": "ENVELOPE",
        "sv_label": "Tilläggsisolering vindbjälklag",
        "description": "Add blown/loose-fill insulation to attic floor. "
                       "Cheapest envelope measure when accessible.",
        "target_scope": "roof",
        "required_params": {"material_id": str, "thickness_m": float},
        "typical_cost_sek_per_m2": 300,
        "expected_service_life_years": 50,
        "piggyback_trigger": False,  # exception: attic insulation IS low-hanging
    },

    "envelope.roof_replacement": {
        "category": "ENVELOPE",
        "sv_label": "Takbyte med tilläggsisolering",
        "description": "Full roof replacement. Insulation added as piggyback.",
        "target_scope": "roof",
        "required_params": {"material_id": str, "thickness_m": float},
        "typical_cost_sek_per_m2": 2000,
        "expected_service_life_years": 50,
        "piggyback_trigger": True,
    },

    "envelope.wall_insulation_internal": {
        "category": "ENVELOPE",
        "sv_label": "Invändig tilläggsisolering",
        "description": "Add insulation from inside. Avoids scaffold but "
                       "reduces floor area and risks moisture problems.",
        "target_scope": "external_wall",
        "required_params": {"material_id": str, "thickness_m": float},
        "typical_cost_sek_per_m2": 800,
        "expected_service_life_years": 40,
        "piggyback_trigger": True,  # usually only with interior renovation
    },

    "envelope.wall_insulation_external": {
        "category": "ENVELOPE",
        "sv_label": "Utvändig tilläggsisolering (ETICS)",
        "description": "Add insulation outside. Best thermal result but "
                       "expensive. Only viable during facade renovation.",
        "target_scope": "external_wall",
        "required_params": {"material_id": str, "thickness_m": float},
        "typical_cost_sek_per_m2": 2500,
        "expected_service_life_years": 40,
        "piggyback_trigger": True,  # almost always piggyback on facade work
    },

    "envelope.wall_replacement_full": {
        "category": "ENVELOPE",
        "sv_label": "Fasadbyte",
        "description": "Full facade replacement. Extremely rare.",
        "target_scope": "external_wall",
        "required_params": {"new_element_id": str},
        "typical_cost_sek_per_m2": 5000,
        "expected_service_life_years": 60,
        "piggyback_trigger": True,
    },

    "envelope.floor_insulation": {
        "category": "ENVELOPE",
        "sv_label": "Golvbjälklagsisolering",
        "description": "Insulate crawl space or basement ceiling.",
        "target_scope": "floor",
        "required_params": {"material_id": str, "thickness_m": float},
        "typical_cost_sek_per_m2": 500,
        "expected_service_life_years": 50,
        "piggyback_trigger": True,
    },

    # ── TIER 4: RENEWABLES / SUPPLY (capital-intensive) ─────────────

    "renewables.pv_roof": {
        "category": "RENEWABLES",
        "sv_label": "Solceller på tak",
        "description": "Install rooftop photovoltaics.",
        "target_scope": "roof",
        "required_params": {"capacity_kwp": float},
        "typical_cost_sek_per_kwp": 12000,
        "expected_service_life_years": 30,
        "piggyback_trigger": False,
    },

    "renewables.solar_thermal": {
        "category": "RENEWABLES",
        "sv_label": "Solvärme",
        "description": "Install solar thermal collectors for DHW/space heating.",
        "target_scope": "roof",
        "required_params": {"area_m2": float},
        "typical_cost_sek_per_m2": 5000,
        "expected_service_life_years": 25,
        "piggyback_trigger": False,
    },
}
"""


def get_measure_catalog() -> dict:
    """Return the full measure catalog dictionary.

    Implementation should return MEASURE_CATALOG defined above.
    Filter by category or piggyback_trigger as needed.
    """
    raise NotImplementedError("Implement measure catalog")


def get_measures_by_category(category: str) -> dict:
    """Return measures filtered by category (OPERATIONAL, SYSTEMS, ENVELOPE, RENEWABLES)."""
    raise NotImplementedError("Implement category filter")


def get_piggyback_measures() -> dict:
    """Return only measures that require a piggyback trigger."""
    raise NotImplementedError("Implement piggyback filter")
