"""Explicit, broad school/office construction screens, never fitted benchmarks.

These checks use the captured project-policy fixture. Passing a range does not
establish a typical Swedish building, building compliance or source agreement.
"""

from collections.abc import Mapping

from .classification import ERAS
from .sanity_physics import _family
from .sanity_reference import (
    _added_layers,
    _affected,
    _assessment,
    _config_elements,
    _insulation_depth,
    _mapping,
    _number,
    _record,
    _role,
    _sequence,
    _stack,
    _u,
)

_CATEGORIES = {"office", "school"}


def validate_nonresidential_fixture(value):
    """Reject malformed policy rather than silently broadening a screen."""
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("Invalid sanity fixture nonresidential_construction schema")
    if value.get("categories") != ["office", "school"]:
        raise ValueError("Invalid sanity fixture nonresidential categories")
    if not isinstance(value.get("basis"), str) or not value["basis"].strip():
        raise ValueError("Missing sanity fixture nonresidential policy basis")
    if not _assessment(value.get("provenance")):
        raise ValueError("Missing sanity fixture nonresidential policy provenance")
    rows = value.get("period_screens")
    if not isinstance(rows, list) or len(rows) != len(ERAS):
        raise ValueError("Sanity fixture nonresidential period coverage must include seven eras")
    if (any(not isinstance(row, dict) or not isinstance(row.get("era"), str) for row in rows)
            or {row["era"] for row in rows} != set(ERAS)):
        raise ValueError("Invalid sanity fixture nonresidential period identities")
    fields = ("wall_insulation_m", "top_insulation_m", "wall_u_w_m2k", "top_u_w_m2k",
              "window_u_w_m2k")
    for row in rows:
        if not isinstance(row, dict) or not _assessment(row.get("provenance")):
            raise ValueError("Missing sanity fixture nonresidential period provenance")
        for field in fields:
            _bounds(row.get(field), field)
        for field in ("wall_capacity_kj_m2k", "intermediate_capacity_kj_m2k"):
            if not isinstance(row.get(field), dict) or set(row[field]) != _CATEGORIES:
                raise ValueError("Invalid sanity fixture nonresidential construction-family ranges")
            for bounds in row[field].values():
                _bounds(bounds, field)
    for field in ("shgc", "visible_transmittance", "soil_concrete_depth_m",
                  "renovation_added_insulation_m"):
        _bounds(value.get(field), field)
    if value.get("unheated_basement_eras") != ["SE.01"]:
        raise ValueError("Invalid sanity fixture nonresidential basement-family coverage")
    if any(not 0 <= bound <= 1 for field in ("shgc", "visible_transmittance")
           for bound in value[field]):
        raise ValueError("Invalid sanity fixture nonresidential optical range")


def _bounds(value, field):
    if (not isinstance(value, list) or len(value) != 2
            or not all(_number(v) for v in value) or not 0 <= value[0] < value[1]):
        raise ValueError(f"Invalid sanity fixture nonresidential range: {field}")


def _metrics(data, element_id, rules):
    """Full material capacity and family depths from stored parallel shares."""
    stack = _stack(data, element_id)
    if not stack:
        return None
    capacity, mass, family_depths = 0.0, 0.0, {}
    for layer in stack:
        shares = _sequence(layer.get("materials"))
        if not shares:
            return None
        for share in shares:
            share = _mapping(share)
            material = _record(data, "materials", share.get("material_id"))
            props = _mapping(material.get("properties"))
            fraction, depth = share.get("area_fraction"), share.get("thickness")
            density, heat_capacity = props.get("density"), props.get("specific_heat")
            if (not all(_number(v) for v in (fraction, depth, density, heat_capacity))
                    or not 0 < fraction <= 1 or min(depth, density, heat_capacity) <= 0):
                return None
            contribution = fraction * depth * density
            mass += contribution
            capacity += contribution * heat_capacity / 1000
            family, _ = _family(material, rules)
            if family:
                family_depths[family] = family_depths.get(family, 0.0) + fraction * depth
    return {"capacity_kj_m2k": capacity, "mass_kg_m2": mass,
            "family_depths_m": family_depths}


def _range(emit, path, affected, name, actual, bounds, source, **details):
    if not _number(actual):
        emit("nonres.calculation", "review", path,
             "A forward school/office construction screen is unavailable; it is not a pass.",
             actual={"quantity": name, "status": "not_assessed"}, affected=affected,
             expected={"project_screen_range": bounds, "source": source})
    elif not bounds[0] <= actual <= bounds[1]:
        emit("nonres.period_range", "review", path,
             "Forward value lies outside a broad school/office project screen; explain the representative construction rather than fit layers to the range.",
             actual={name: actual, **details},
             expected={"quantity": name, "project_screen_range": bounds,
                       "source": source, "independent_validation": False}, affected=affected)


def _boundaries(data, emit, record, aid, state, config, elements, fixture, rules):
    path, affected = f"archetypes.{aid}.states.{state}", _affected(record, state)
    details = _mapping(config.get("boundary_details"))
    top = _role(config, elements, "THERMAL_TOP")
    if config.get("roof_topology") == "cold_attic" and top:
        declared = _mapping(details.get(top))
        expected = {"physical_role": "attic_ceiling",
                    "physical_boundary": "conditioned_to_unconditioned"}
        if any(declared.get(k) is not None and declared[k] != v for k, v in expected.items()):
            emit("construction.nonres_boundary", "error", path + f".boundary_details.{top}",
                 "A cold attic thermal top must be the conditioned ceiling, distinct from the weather roof.",
                 actual=declared, expected=expected, affected=affected)
        elif any(declared.get(k) is None for k in expected):
            emit("construction.nonres_boundary", "review", path + f".boundary_details.{top}",
                 "Declare the cold-attic ceiling's physical boundary; a role label alone does not establish it.",
                 actual=declared, expected=expected, affected=affected)
    for role, element_id in elements.items():
        if role == "WINDOW":
            continue
        element = _record(data, "elements", element_id)
        declared = _mapping(details.get(role))
        order, side = declared.get("layer_order"), element.get("side_convention")
        equivalents = {"outside_to_inside": {"outside_to_inside", "ground_to_inside"},
                       "inside_to_outside": {"inside_to_outside", "inside_to_ground"},
                       "upper_room_to_lower_room": {"top_to_bottom"},
                       "lower_room_to_upper_room": {"bottom_to_top"}}
        if order is not None and (not isinstance(order, str) or order not in equivalents):
            emit("construction.nonres_side", "error", path + f".boundary_details.{role}.layer_order",
                 "Unknown school/office physical side convention.", actual=order,
                 expected=sorted(equivalents), affected=affected)
        elif side is not None and order is not None and (
            not isinstance(side, str) or side not in equivalents[order]
        ):
            emit("construction.nonres_side", "error", path + f".boundary_details.{role}",
                 "Physical boundary order contradicts the assembly's stored side convention.",
                 actual={"layer_order": order, "side_convention": side},
                 expected={"compatible_side_conventions": sorted(equivalents[order])}, affected=affected)
        if role == "INTERMEDIATE_FLOOR" and (not isinstance(order, str) or order not in {
            "upper_room_to_lower_room", "lower_room_to_upper_room"
        }):
            emit("construction.nonres_side", "review", path + f".boundary_details.{role}",
                 "An intermediate floor needs explicit upper/lower room semantics, independent of an exterior wall convention.",
                 actual=declared, affected=affected)
    needs_basement = record.get("era") in fixture["unheated_basement_eras"]
    context = config.get("foundation_context")
    if needs_basement and context != "unheated_basement":
        emit("construction.nonres_boundary", "error" if context is not None else "review",
             path + ".foundation_context",
             "The retained early-period recipe represents an unheated basement, not a timber soil slab; declare a different evidenced foundation explicitly.",
             actual=context, expected="unheated_basement", affected=affected)
    if not needs_basement and context != "unheated_basement":
        return
    expected_roles = {"GROUND_FLOOR": {"physical_role": "basement_ceiling",
                                     "physical_boundary": "conditioned_to_unconditioned"},
                      "BASEMENT_FLOOR": {"physical_role": "basement_floor", "physical_boundary": "soil"}}
    for role, expected in expected_roles.items():
        declared = _mapping(details.get(role))
        if not elements.get(role):
            emit("construction.nonres_boundary", "missing", path + ".construction_set_id",
                 "An unheated-basement family needs separate soil floor and suspended ceiling definitions.",
                 actual={"missing_role": role}, expected=expected_roles, affected=affected)
        elif any(declared.get(k) != v for k, v in expected.items()):
            contradictory = any(declared.get(k) is not None and declared[k] != v for k, v in expected.items())
            emit("construction.nonres_boundary", "error" if contradictory else "review",
                 path + f".boundary_details.{role}",
                 "Separate the basement soil floor from the conditioned-to-unconditioned suspended ceiling.",
                 actual=declared, expected=expected, affected=affected)
    if elements.get("GROUND_FLOOR") == elements.get("BASEMENT_FLOOR") and elements.get("GROUND_FLOOR"):
        emit("construction.nonres_boundary", "error", path + ".construction_set_id",
             "The declared suspended ceiling and soil slab cannot share one physical element definition.",
             actual=elements.get("GROUND_FLOOR"), affected=affected)
    soil = _metrics(data, elements.get("BASEMENT_FLOOR"), rules)
    if soil:
        depth = soil["family_depths_m"].get("concrete", 0.0)
        if depth == 0 and any(soil["family_depths_m"].get(f, 0) > 0 for f in ("timber", "loose_fill")):
            emit("construction.nonres_boundary", "error", path + ".construction_set_id",
                 "A timber/shavings suspended ceiling is not the declared concrete basement soil slab.",
                 actual=soil, expected={"soil_floor_family": "concrete"}, affected=affected)
        else:
            _range(emit, path, affected, "soil_concrete_depth_m", depth,
                   fixture["soil_concrete_depth_m"], fixture["provenance"])


def check_nonresidential(data, catalogue, emit, benchmarks):
    """Add nonresidential screens without substituting for residential references."""
    fixture = benchmarks.get("nonresidential_construction")
    rules = benchmarks.get("construction_rules", {})
    if not isinstance(fixture, dict) or not rules:
        for aid, record in data.get("archetypes", {}).items():
            if (not isinstance(record, Mapping) or not isinstance(record.get("category"), str)
                    or record["category"] not in _CATEGORIES):
                continue
            for state in _mapping(record.get("states")):
                emit("nonres.reference_not_assessed", "review", f"archetypes.{aid}.states.{state}",
                     "This explicit reference bundle has no school/office project screens; no default ranges were substituted.",
                     actual={"status": "not_assessed"}, affected=_affected(record, state))
        return
    policy = _mapping(benchmarks.get("policy"))
    rows = {row["era"]: row for row in fixture["period_screens"]}
    for aid, record in data.get("archetypes", {}).items():
        if (not isinstance(record, Mapping) or not isinstance(record.get("category"), str)
                or record["category"] not in _CATEGORIES):
            continue
        era = record.get("era")
        period = rows.get(era) if isinstance(era, str) else None
        if period is None:
            continue
        states = _mapping(record.get("states"))
        baseline = _mapping(states.get("existing", states.get("default")))
        base_elements = _config_elements(data, baseline)
        for state, config in states.items():
            if not isinstance(config, Mapping):
                continue
            path, affected = f"archetypes.{aid}.states.{state}", _affected(record, state)
            elements = _config_elements(data, config)
            _boundaries(data, emit, record, aid, state, config, elements, fixture, rules)
            window = _record(data, "elements", elements.get("WINDOW"))
            optical = _mapping(_record(data, "materials", window.get("window_material_id")).get("properties"))
            for field, key in (("shgc", "shgc"), ("vt", "visible_transmittance")):
                _range(emit, path, affected, field, optical.get(field), fixture[key], fixture["provenance"])
            assessment = _mapping(config.get("sanity_assessment"))
            if not _assessment(assessment.get("window_optics")):
                emit("nonres.window_evidence", "review", path + ".sanity_assessment.window_optics",
                     "Representative whole-window U and optical properties need a source or an explicit assumption; period and a carbon product proxy do not establish glazing optics.",
                     actual={"u_w_m2k": optical.get("u_value"), "shgc": optical.get("shgc"),
                             "vt": optical.get("vt"), "status": "not_assessed"}, affected=affected)
            if state in {"existing", "default"}:
                for logical, field in (("EXT_WALL", "wall_insulation_m"), ("THERMAL_TOP", "top_insulation_m")):
                    role = _role(config, elements, logical)
                    stack = _stack(data, elements.get(role))
                    depth = _insulation_depth(data, stack, policy) if stack else None
                    _range(emit, path, affected, field, depth, period[field], period["provenance"])
                for logical, field in (("EXT_WALL", "wall_u_w_m2k"), ("THERMAL_TOP", "top_u_w_m2k")):
                    role = _role(config, elements, logical)
                    _range(emit, path, affected, field, _u(catalogue, elements.get(role)),
                           period[field], period["provenance"], nominal_material_layers=True,
                           surface_films="Rsi .13 + Rse .04 m2K/W; no ground-effective comparison")
                for role, field in (("EXT_WALL", "wall_capacity_kj_m2k"),
                                    ("INTERMEDIATE_FLOOR", "intermediate_capacity_kj_m2k")):
                    metrics = _metrics(data, elements.get(role), rules)
                    _range(emit, path, affected, field, metrics["capacity_kj_m2k"] if metrics else None,
                           period[field][record["category"]], period["provenance"],
                           full_material_capacity=True)
                _range(emit, path, affected, "window_u_w_m2k", _u(catalogue, elements.get("WINDOW")),
                       period["window_u_w_m2k"], period["provenance"])
            else:
                if not _assessment(assessment.get("renovation")):
                    emit("nonres.renovation_rationale", "review", path + ".sanity_assessment.renovation",
                         "Renovation needs a retained-fabric, placement and access/buildability rationale; a lower U-value alone does not establish constructability.",
                         actual={"state": state, "status": "not_assessed"}, affected=affected)
                for logical in ("EXT_WALL", "THERMAL_TOP", "GROUND_FLOOR", "BASEMENT_FLOOR", "BASEMENT_WALL"):
                    role, base_role = _role(config, elements, logical), _role(baseline, base_elements, logical)
                    if not role or not base_role or elements.get(role) == base_elements.get(base_role):
                        continue
                    before, after = _stack(data, base_elements.get(base_role)), _stack(data, elements.get(role))
                    change = _added_layers(before, after)
                    if change is None:
                        emit("nonres.retained_fabric", "review", path,
                             "Changed construction does not retain the original ordered layers; document removal/replacement and its quantities explicitly.",
                             actual={"element": logical, "baseline_retained": False}, affected=affected)
                    else:
                        added, matched = change
                        # Identical adjacent insulation boards have no unique
                        # retained/new matching: the greedy subsequence can
                        # label the outer new board as retained. Only crossing
                        # retained non-insulating fabric establishes placement
                        # within/inside that fabric.
                        crossed_fabric = [index for index in matched
                                          if _insulation_depth(data, [after[index]], policy) == 0]
                        if logical in {"EXT_WALL", "THERMAL_TOP"} and any(
                            original < index for index in added for original in crossed_fabric
                        ):
                            emit("nonres.renovation_placement", "review", path,
                                 "New layers lie within/inside retained fabric; review access, moisture and the representative exterior/cold-side intervention rationale.",
                                 actual={"element": logical, "added_positions": added,
                                         "retained_positions": matched}, affected=affected)
                        _range(emit, path, affected, "renovation_added_insulation_m",
                               _insulation_depth(data, [after[i] for i in added], policy),
                               fixture["renovation_added_insulation_m"], fixture["provenance"])
