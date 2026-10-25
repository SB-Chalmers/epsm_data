"""Forward-only reference checks for representative Swedish LoD2 constructions.

The small packaged benchmark table is an offline extract of retained TABULA
references. This module reports disagreements; it never modifies the catalogue
or derives layer thicknesses from target U-values.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping

from .classification import ERAS, ZONES

_RESIDENTIAL = {"single_family", "multi_family"}
_ENVELOPE = ("EXT_WALL", "GROUND_FLOOR", "BASEMENT_WALL", "THERMAL_TOP", "WINDOW")
_DIRECT = ("EXT_WALL", "THERMAL_TOP", "WINDOW")


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _record(data, section, identifier):
    if not isinstance(identifier, (str, int)):
        return {}
    return _mapping(data.get(section, {}).get(identifier))


def _sequence(value):
    return value if isinstance(value, (list, tuple)) else ()


def _number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def _affected(record, state, zones=ZONES):
    return [f"{record.get('category')}:{record.get('era')}:{z}:{state}" for z in zones]


def _config_elements(data, config):
    return _mapping(_record(data, "construction_sets", config.get("construction_set_id")).get(
        "elements"))


def _role(config, elements, role):
    if role != "THERMAL_TOP":
        return role if role in elements else None
    topology = config.get("roof_topology")
    if topology == "cold_attic" and "TOP_FLOOR" in elements:
        return "TOP_FLOOR"
    if topology == "compact" and "ROOF" in elements:
        return "ROOF"
    return None


def _boundary_comparison(target):
    """Accept only the explicit, source-incompatible ground mapping schema."""
    comparison = _mapping(_mapping(target).get("boundary_comparison"))
    required = {"catalogue_role", "physical_boundary", "physical_role", "status",
                "reason", "source_locators"}
    if set(comparison) != required or comparison.get("status") != "source_incompatible":
        return {}
    if comparison.get("physical_boundary") != "soil" or not isinstance(
        comparison.get("reason"), str
    ) or not comparison["reason"].strip():
        return {}
    locators = comparison.get("source_locators")
    if not isinstance(locators, list) or not locators or not all(
        isinstance(value, str) and value.strip() for value in locators
    ):
        return {}
    return comparison


def _mapped_boundary_role(config, elements, logical_role, target):
    """Resolve only a fixture-evidenced physical role, never a name-based alias."""
    comparison = _boundary_comparison(target)
    expected_roles = {
        "GROUND_FLOOR": ("GROUND_FLOOR", "conditioned_basement_floor"),
        "TABULA_WALL_2": ("BASEMENT_WALL", "conditioned_basement_wall"),
    }
    expected = expected_roles.get(logical_role)
    if not comparison or expected != (
        comparison.get("catalogue_role"), comparison.get("physical_role")
    ):
        return None
    role = comparison["catalogue_role"]
    details = _mapping(_mapping(config.get("boundary_details")).get(role))
    required = {
        "physical_boundary": comparison["physical_boundary"],
        "physical_role": comparison["physical_role"],
        "source_mapping": logical_role,
        "layer_order": "outside_to_inside",
        "value_meaning": "nominal_material_layers_not_effective_ground_u",
    }
    return role if role in elements and all(
        details.get(key) == value for key, value in required.items()
    ) else None


def _u(catalogue, element_id):
    if catalogue is None or not element_id:
        return None
    try:
        value = catalogue.elements[element_id].u_value
    except (KeyError, AttributeError, TypeError, ValueError, ArithmeticError):
        return None
    return value if _number(value) and value > 0 else None


def _stack(data, element_id):
    """Return raw layer occurrences, preserving cross-component order."""
    element = _record(data, "elements", element_id)
    result = []
    for cid in _sequence(element.get("components")):
        component = _record(data, "components", cid)
        slots = _sequence(component.get("layers"))
        try:
            slots = sorted(slots, key=lambda item: item["position"])
        except (TypeError, KeyError, AttributeError):
            return None
        for slot in slots:
            layer = _record(data, "layers", slot.get("layer_id"))
            if not layer:
                return None
            result.append(layer)
    return result or None


def _signature(layer):
    """Compare physical occurrences independently of names and generated IDs."""
    return (
        layer.get("thickness"),
        tuple(sorted(
            ((_mapping(m).get("material_id", ""), _mapping(m).get("area_fraction"),
              _mapping(m).get("thickness")) for m in _sequence(layer.get("materials"))),
            key=repr,
        )),
    )


def _added_layers(baseline, renovated):
    """Match retained occurrences in order; additions can be outside or inside."""
    if not baseline or not renovated:
        return None
    signatures = [_signature(layer) for layer in baseline]
    matched, position = [], 0
    for index, layer in enumerate(renovated):
        if position < len(signatures) and _signature(layer) == signatures[position]:
            matched.append(index)
            position += 1
    if position != len(signatures):
        return None
    added = [index for index in range(len(renovated)) if index not in matched]
    return added, matched


def _insulation_depth(data, layers, policy):
    total = 0.0
    maximum = policy.get("insulation_conductivity_max_w_mk", 0.12)
    minimum_fraction = policy.get("insulation_minimum_area_fraction", 0.5)
    for layer in layers:
        fraction = 0.0
        for material in _sequence(layer.get("materials")):
            material = _mapping(material)
            definition = _record(data, "materials", material.get("material_id"))
            # Low conductivity alone does not turn framing, cladding or an air
            # cavity into the insulation prescribed by a renovation measure.
            if definition.get("material_family") == "timber" or definition.get("non_product") is True:
                continue
            properties = _mapping(definition.get("properties"))
            conductivity = properties.get("conductivity")
            share = material.get("area_fraction")
            if _number(conductivity) and 0 < conductivity <= maximum and _number(share):
                fraction += share
        if fraction >= minimum_fraction and _number(layer.get("thickness")):
            total += layer["thickness"]
    return total


def _physical_role_u(data, catalogue, elements, role):
    """Require a resolved layered definition with the assigned physical role."""
    identifier = elements.get(role)
    element = _record(data, "elements", identifier)
    if element.get("role") != role or not _stack(data, identifier):
        return None
    return _u(catalogue, identifier)


def _ground_project_inputs(data, catalogue, emit, record, aid, state, config, policy):
    """Separate site-dependent ground modelling from catalogue fabric validity."""
    elements = _config_elements(data, config)
    value = _physical_role_u(data, catalogue, elements, "GROUND_FLOOR")
    known = value is not None
    emit("ground.project_inputs" if known else "construction.ground_definition",
         "review" if known else "missing", f"archetypes.{aid}.states.{state}",
         ("Ground heat transfer requires project geometry, soil and a declared simulation boundary method; this is not a missing catalogue construction."
          if known else "A resolved ground-floor assembly and finite forward nominal U-value are required before project ground conditions can be assessed."),
         actual={"element": "GROUND_FLOOR", "element_id": elements.get("GROUND_FLOOR"),
                 "nominal_u_w_m2k": value,
                 "status": "project_inputs_required" if known else "definition_unresolved"},
         expected={"required_project_inputs": _mapping(policy.get("ground_assessment")).get(
             "required_project_inputs", ["ground_contact_geometry_area_perimeter_and_burial_depth",
                                         "soil_properties", "ground_boundary_method_and_assumptions"]),
                   "basement_presence": "Selected by project geometry, not by a reusable basement recipe",
                   "catalogue_ground_factors_added": False,
                   "benchmark_agreement_assessed": False},
         affected=_affected(record, state))


def _check_u_values(data, catalogue, emit, record, aid, state, config, reference, policy):
    elements = _config_elements(data, config)
    path = f"archetypes.{aid}.states.{state}"
    for logical_role in _DIRECT:
        target = _mapping(reference.get("elements")).get(logical_role)
        if not isinstance(target, dict):
            emit("tabula.reference_missing", "missing", path,
                 f"TABULA {logical_role} comparison has no benchmark; not assessed.",
                 actual=None, expected={"element": logical_role}, affected=_affected(record, state))
            continue
        role = _role(config, elements, logical_role)
        if role is None:
            emit("tabula.boundary_not_assessed", "missing", path,
                 f"TABULA {logical_role} needs a matching thermal boundary; not assessed.",
                 actual={"roof_topology": config.get("roof_topology"), "roles": sorted(elements)},
                 expected={"element": logical_role, "cold_attic": "TOP_FLOOR", "compact": "ROOF"},
                 affected=_affected(record, state))
            continue
        if role != "WINDOW" and _mapping(_mapping(config.get("boundary_details")).get(role)).get(
            "layer_order"
        ) != "outside_to_inside":
            emit("tabula.boundary_not_assessed", "missing", path + f".boundary_details.{role}",
                 "TABULA comparison requires an explicit matching side convention; not assessed.",
                 actual=_mapping(config.get("boundary_details")).get(role),
                 expected={"layer_order": "outside_to_inside"}, affected=_affected(record, state))
            continue
        actual = _u(catalogue, elements[role])
        groups = defaultdict(list)
        for zone in ZONES:
            value = _mapping(target.get("values_w_m2k")).get(zone)
            locator = _mapping(target.get("source_locators")).get(zone)
            if not _number(value) or value <= 0 or not locator:
                emit("tabula.reference_missing", "missing", path,
                     f"TABULA {logical_role} target/source locator is missing; not assessed.",
                     actual={"target": value, "source_locator": locator},
                     expected={"positive_u_w_m2k": True, "source_locator": True},
                     affected=_affected(record, state, (zone,)))
            else:
                groups[value].append(zone)
        for target_value, zones in groups.items():
            expected = {"u_value_w_m2k": target_value,
                        "relative_tolerance": policy.get("u_value_relative_tolerance", 0.2),
                        "element": logical_role,
                        "source_locators": {z: target["source_locators"][z] for z in zones},
                        "calculation_convention": policy.get("nominal_comparison_convention")}
            if actual is None:
                emit("tabula.calculation", "missing", path,
                     f"Forward {role} U-value is unavailable; TABULA comparison not assessed.",
                     actual=None, expected=expected, affected=_affected(record, state, zones))
            elif abs(actual - target_value) / target_value > expected["relative_tolerance"] + 1e-12:
                emit("tabula.u_value", "error", f"elements.{elements[role]}",
                     f"{role} U-value is outside the TABULA ±{expected['relative_tolerance']:.0%} acceptance margin.",
                     actual={"u_value_w_m2k": actual,
                             "relative_difference": abs(actual - target_value) / target_value},
                     expected=expected, affected=_affected(record, state, zones))
    # Neither an effective ground U nor TABULA's second wall can safely be
    # substituted with a nominal seven-role assembly merely because names match.
    for logical_role in ("GROUND_FLOOR", "TABULA_WALL_2"):
        if logical_role not in _mapping(reference.get("elements")):
            continue
        target = reference["elements"][logical_role]
        if "boundary_comparison" in target:
            comparison = _boundary_comparison(target)
            role = _mapped_boundary_role(config, elements, logical_role, target)
            nominal_u = _physical_role_u(data, catalogue, elements, role) if role else None
            known = role is not None and nominal_u is not None
            if comparison:
                emit("tabula.source_convention", "review", path,
                     "The retained TABULA ground comparison has incompatible source boundary corrections; it is not a nominal assembly acceptance target.",
                     actual={"element": logical_role, "catalogue_role": role,
                             "nominal_u_w_m2k": nominal_u,
                             "status": "source_incompatible",
                             "mapping_status": "resolved" if known else "not_assessed"},
                     expected={"reason": comparison["reason"],
                               "source_locators": comparison["source_locators"]},
                     affected=_affected(record, state))
            emit("tabula.boundary_not_assessed", "review" if known else "missing", path,
                 ("The physical boundary is mapped, but ground-inclusive BETSI inputs with subsequent TABULA Cellar corrections cannot validate a nominal assembly U-value; this is a reference limitation."
                  if known else "An explicit matching physical boundary, resolved assembly and valid source-comparison descriptor are required; the TABULA comparison is not assessed."),
                 actual={"element": logical_role, "catalogue_role": role,
                         "nominal_u_w_m2k": nominal_u,
                         "status": ("source_incompatible" if known else "boundary_mapping_missing"
                                    if role is None else "physical_definition_unresolved"),
                         "source_issue": comparison.get("reason")},
                 expected={"boundary_comparison": target.get("boundary_comparison"),
                           "values_w_m2k": target.get("values_w_m2k"),
                           "source_locators": target.get("source_locators")},
                 affected=_affected(record, state))
            continue
        role = "GROUND_FLOOR" if logical_role == "GROUND_FLOOR" else None
        nominal_u = _physical_role_u(data, catalogue, elements, role) if role else None
        known = logical_role == "TABULA_WALL_2" or nominal_u is not None
        emit("tabula.boundary_not_assessed", "review" if known else "missing", path,
             ("Effective ground U requires project geometry, soil and matching reference conditions; the nominal construction is defined but no ground benchmark agreement is claimed."
              if nominal_u is not None else
              "The ground-floor definition or forward calculation is unresolved; project ground inputs cannot replace missing catalogue fabric."
              if logical_role == "GROUND_FLOOR" else
              "TABULA wall_2 has no evidenced source-to-envelope mapping; this reference limitation does not imply missing physical fabric or assume a basement-wall alias."),
             actual={"element": logical_role, "catalogue_role": role,
                     "nominal_u_w_m2k": nominal_u,
                     "status": ("reference_mapping_not_assessed" if logical_role == "TABULA_WALL_2"
                                else "project_boundary_required" if known else "definition_unresolved")},
             expected={"values_w_m2k": target.get("values_w_m2k"),
                       "source_locators": target.get("source_locators"),
                       "benchmark_agreement_assessed": False},
             affected=_affected(record, state))


def _check_measure(data, catalogue, emit, record, aid, state, config, baseline,
                   logical_role, measure, policy, boundary_target=None):
    path = f"archetypes.{aid}.states.{state}"
    affected = _affected(record, state)
    elements, base_elements = _config_elements(data, config), _config_elements(data, baseline)
    if boundary_target is not None and "boundary_comparison" in boundary_target:
        role = _mapped_boundary_role(config, elements, logical_role, boundary_target)
        base_role = _mapped_boundary_role(baseline, base_elements, logical_role, boundary_target)
    else:
        role = _role(config, elements, logical_role)
        base_role = _role(baseline, base_elements, logical_role)
    source = {"code": measure.get("code"), "source_locator": measure.get("source_locator"),
              "retained_source_locator": measure.get("retained_source_locator")}
    if measure.get("placement_source_locator"):
        source["placement_source_locator"] = measure["placement_source_locator"]
    if role is None or base_role is None or role != base_role:
        emit("tabula.measure_mapping", "missing", path,
             f"TABULA {logical_role} intervention needs matching baseline and renovated boundaries.",
             actual={"baseline_role": base_role, "renovated_role": role}, expected=source,
             affected=affected)
        return
    if logical_role == "WINDOW":
        target, actual = measure.get("window_u_w_m2k"), _u(catalogue, elements[role])
        if actual is None or not _number(target):
            emit("tabula.measure_window", "missing", path,
                 "TABULA replacement window cannot be assessed without both U-values.",
                 actual=actual, expected=source | {"window_u_w_m2k": target}, affected=affected)
        elif elements[role] == base_elements[role] or abs(actual-target) / target > policy.get(
            "u_value_relative_tolerance", 0.2
        ) + 1e-12:
            emit("tabula.measure_window", "error", path,
                 "Renovation does not implement the TABULA replacement-window performance.",
                 actual={"window_u_w_m2k": actual, "replaced": elements[role] != base_elements[role]},
                 expected=source | {"window_u_w_m2k": target, "relative_tolerance": policy.get(
                     "u_value_relative_tolerance", 0.2)},
                 affected=affected)
        return
    base_stack, stack = _stack(data, base_elements[base_role]), _stack(data, elements[role])
    change = _added_layers(base_stack, stack)
    if change is None:
        emit("tabula.measure_baseline", "error" if base_stack and stack else "missing", path,
             "TABULA addition cannot be verified as an intervention retaining the baseline layer order.",
             actual={"element": role, "baseline_retained": False}, expected=source,
             affected=affected)
        return
    added, matched = change
    added_layers = [stack[index] for index in added]
    actual_depth = _insulation_depth(data, added_layers, policy)
    target = measure.get("nominal_added_insulation_m")
    tolerance = policy.get("nominal_added_thickness_tolerance_m", 0.001)
    if not _number(target):
        emit("tabula.measure_thickness", "missing", path,
             "The retained TABULA measure has no nominal insulation addition; not assessed.",
             actual=actual_depth, expected=source, affected=affected)
    elif abs(actual_depth - target) > tolerance + 1e-12:
        emit("tabula.measure_thickness", "error", path,
             f"{role} added insulation differs from the TABULA nominal measure.",
             actual={"added_insulation_m": actual_depth},
             expected=source | {"added_insulation_m": target, "absolute_tolerance_m": tolerance},
             affected=affected)
    order = _mapping(_mapping(config.get("boundary_details")).get(role)).get("layer_order")
    placement = measure.get("placement")
    if placement == "exterior_or_cold_side":
        if order != "outside_to_inside":
            emit("tabula.measure_placement", "missing", path,
                 "TABULA addition placement requires an explicit side convention.",
                 actual=order, expected=source | {"placement": placement}, affected=affected)
        elif added and any(index > matched[0] for index in added):
            emit("tabula.measure_placement", "error", path,
                 "TABULA exterior/cold-side addition is placed within or inside the retained baseline.",
                 actual={"added_layer_positions": added, "retained_layer_positions": matched},
                 expected=source | {"placement": placement}, affected=affected)
    elif placement == "interior_or_warm_side":
        if order != "outside_to_inside":
            emit("tabula.measure_placement", "missing", path,
                 "TABULA interior addition placement requires an explicit side convention.",
                 actual=order, expected=source | {"placement": placement}, affected=affected)
        elif added and any(index <= matched[-1] for index in added):
            emit("tabula.measure_placement", "error", path,
                 "TABULA interior/warm-side addition must follow all retained baseline layers.",
                 actual={"added_layer_positions": added, "retained_layer_positions": matched},
                 expected=source | {"placement": placement}, affected=affected)
    elif placement == "not_specified_in_retained_measure":
        assessment = _mapping(_mapping(config.get("sanity_assessment")).get(
            "measure_placement")).get(logical_role)
        if not _assessment(assessment):
            emit("tabula.measure_placement", "missing", path,
                 "Retained TABULA measure does not establish ground/secondary-wall placement; an explicit physical assessment is needed.",
                 actual={"element": logical_role, "status": "not_assessed"}, expected=source,
                 affected=affected)
    finish = measure.get("required_finish")
    if finish:
        names = []
        finish_layers = []
        terms = ("wood", "timber", "trä") if finish == "wood_panelling" else ("brick", "tegel")
        for layer in added_layers:
            constituents = _sequence(layer.get("materials"))
            layer_names = [str(_record(data, "materials", _mapping(m).get("material_id")).get(
                "name", "")).casefold() for m in constituents]
            names.extend(layer_names)
            # Framing within an insulation layer is not a new cladding panel.
            # A homogeneous finish proxy can represent panels, but loose wood
            # shavings/fibre do not establish wood panelling from their name.
            finish_layers.append(bool(layer_names) and all(
                any(term in name for term in terms)
                and not any(term in name for term in ("shaving", "fibre", "fiber", "loose"))
                for name in layer_names))
        present = any(finish_layers)
        if not present:
            emit("tabula.measure_finish", "error", path,
                 "TABULA package specifies an accompanying finish that is absent from the intervention.",
                 actual={"added_material_names": names}, expected=source | {"finish": finish},
                 affected=affected)


def _assessment(value):
    return (isinstance(value, dict) and isinstance(value.get("rationale"), str)
            and bool(value["rationale"].strip()) and isinstance(value.get("sources"), list)
            and bool(value["sources"]) and all(isinstance(v, str) and v.strip() for v in value["sources"]))


def _era_assessment(data, emit, aid, record):
    state = "default" if record.get("era") == "SE.07" else "existing"
    config = _mapping(record.get("states")).get(state)
    if not isinstance(config, dict):
        return
    path = f"archetypes.{aid}.states.{state}"
    if not _assessment(_mapping(config.get("sanity_assessment")).get("as_built")):
        emit("era.as_built_assessment", "review", path,
             "Representative original-era construction needs an explicit plausibility rationale and source locators; this is not a verified building.",
             actual={"era": record.get("era"), "construction_year": config.get("construction_year"),
                     "status": "not_assessed"},
             expected={"sanity_assessment.as_built": {"rationale": "nonempty", "sources": ["source locator"]}},
             affected=_affected(record, state))
    year = config.get("construction_year")
    if not _number(year):
        return
    elements = _config_elements(data, config)
    material_ids = set()
    for eid in elements.values():
        element = _record(data, "elements", eid)
        if isinstance(element.get("window_material_id"), str):
            material_ids.add(element["window_material_id"])
        for layer in _stack(data, eid) or []:
            material_ids.update(_mapping(m).get("material_id")
                                for m in _sequence(layer.get("materials"))
                                if isinstance(_mapping(m).get("material_id"), str))
    for mid in sorted(mid for mid in material_ids if isinstance(mid, str)):
        first_use = _record(data, "materials", mid).get("first_use_year")
        if _number(first_use) and first_use > year:
            emit("era.material_anachronism", "error", f"materials.{mid}.first_use_year",
                 "Material's declared first construction use is later than the original-era building; a review note cannot waive this contradiction.",
                 actual={"first_use_year": first_use, "construction_year": year},
                 expected={"first_use_year_max": year}, affected=_affected(record, state))


def _renovation_checks(data, catalogue, emit, aid, record, policy):
    states = _mapping(record.get("states"))
    baseline = states.get("existing")
    if not isinstance(baseline, dict):
        return
    baseline_year = baseline.get("construction_year")
    base_elements = _config_elements(data, baseline)
    epsilon = policy.get("u_value_numeric_tolerance_w_m2k", 1e-6)
    previous, previous_state = baseline, "existing"
    for state in ("standard", "advanced"):
        config = states.get(state)
        if not isinstance(config, dict):
            continue
        path, affected = f"archetypes.{aid}.states.{state}", _affected(record, state)
        if config.get("construction_year") != baseline_year:
            emit("renovation.construction_year", "error", path + ".construction_year",
                 "Renovation must retain the original construction year.",
                 actual=config.get("construction_year"), expected=baseline_year, affected=affected)
        elements, previous_elements = _config_elements(data, config), _config_elements(data, previous)
        improved, known, unknown = False, 0, []
        for logical_role in _ENVELOPE:
            role = _role(config, elements, logical_role)
            base_role = _role(baseline, base_elements, logical_role)
            prior_role = _role(previous, previous_elements, logical_role)
            actual = _u(catalogue, elements.get(role))
            original = _u(catalogue, base_elements.get(base_role))
            prior = _u(catalogue, previous_elements.get(prior_role))
            if actual is None or original is None or prior is None or role != base_role or role != prior_role:
                unknown.append(logical_role)
                continue
            known += 1
            improved = improved or actual < original - epsilon
            if actual > original + epsilon or actual > prior + epsilon:
                emit("renovation.u_value", "error", path,
                     "Renovation worsens an envelope U-value; advanced ≤ standard ≤ original is required.",
                     actual={"element": logical_role, "u_value_w_m2k": actual},
                     expected={"baseline_u_w_m2k": original, f"{previous_state}_u_w_m2k": prior,
                               "numeric_tolerance_w_m2k": epsilon}, affected=affected)
        if unknown:
            emit("renovation.calculation", "missing", path,
                 "Some forward envelope comparisons are unavailable; renovation consistency is not fully assessed.",
                 actual={"unassessed_elements": unknown}, expected={"elements": list(_ENVELOPE)},
                 affected=affected)
        if not improved:
            emit("renovation.improvement", "missing" if unknown else "error", path,
                 "A renovated state must improve at least one envelope U-value relative to its original baseline.",
                 actual={"improved": False, "known_comparisons": known},
                 expected={"at_least_one_envelope_improvement": True}, affected=affected)
        _chronology(data, catalogue, emit, aid, record, state, config, baseline_year, policy)
        previous, previous_state = config, state


def _chronology(data, catalogue, emit, aid, record, state, config, original_year, policy):
    """Context only: later-era resemblance is not an equality constraint."""
    path, affected = f"archetypes.{aid}.states.{state}", _affected(record, state)
    year = config.get("renovation_year")
    assumed_age = policy.get("heuristic_renovation_age_years", 35)
    explicit = year is not None
    if year is None and _number(original_year):
        year = original_year + assumed_age
    if not _number(year) or not _number(original_year):
        emit("renovation.chronology", "review", path,
             "Renovation chronology is not assessed without a construction year.",
             actual={"status": "not_assessed"}, expected={"comparison": "30–40 year advisory context"},
             affected=affected)
        return
    if explicit and year < original_year:
        emit("renovation.chronology", "error", path + ".renovation_year",
             "Explicit renovation year precedes original construction.", actual=year,
             expected={"minimum_year": original_year}, affected=affected)
        return
    era = next((e for e, (start, end) in ERAS.items() if start <= year and (end is None or year <= end)), None)
    candidate = next((r for r in data.get("archetypes", {}).values()
                      if isinstance(r, Mapping) and r.get("category") == record.get("category")
                      and r.get("era") == era), None)
    base = _mapping((candidate or {}).get("states")).get(
        "default" if era == "SE.07" else "existing")
    comparisons = {}
    if isinstance(base, dict):
        here, there = _config_elements(data, config), _config_elements(data, base)
        for logical_role in _DIRECT:
            value = _u(catalogue, here.get(_role(config, here, logical_role)))
            later = _u(catalogue, there.get(_role(base, there, logical_role)))
            if value is not None and later is not None:
                comparisons[logical_role] = {"renovated_u_w_m2k": value, "later_new_u_w_m2k": later,
                                              "ratio": value / later}
    emit("renovation.chronology", "review", path,
         (f"Advisory later-era comparison; the assumed {assumed_age:g}-year intervention is a heuristic, and advanced renovation may outperform later new construction."
          if not explicit else "Advisory later-era comparison at the explicit intervention year; no equality constraint applies.")
         if comparisons else "A matching later-era construction is unavailable; chronology comparison is not assessed.",
         actual={"comparison_year": year, "year_basis": "explicit" if explicit else f"construction_year_plus_{assumed_age:g}_heuristic",
                 "comparison_era": era, "later_representative_construction_year": base.get("construction_year") if isinstance(base, dict) else None,
                 "status": "context_only" if comparisons else "not_assessed", "comparisons": comparisons},
         expected={"comparison_age_years": [30, 40], "hard_equality_required": False,
                   "future_projection": False}, affected=affected)


def check_references(data, catalogue, emit, benchmarks):
    """Append TABULA, era and renovation findings through the shared emitter.

    ``catalogue`` is the successfully loaded domain catalogue, or ``None`` when
    structural validation failed. Missing calculations always remain explicit.
    Benchmark fields are local portable data, never dynamically downloaded.
    """
    benchmarks = benchmarks if isinstance(benchmarks, dict) else {}
    from .sanity_nonresidential import check_nonresidential

    check_nonresidential(data, catalogue, emit, benchmarks)
    policy = _mapping(benchmarks.get("policy"))
    index = {(row.get("category"), row.get("era"), row.get("state")): row
             for row in _sequence(benchmarks.get("u_values")) if isinstance(row, dict)}
    packages = {(row.get("category"), row.get("era"), row.get("state")): row
                for row in _sequence(benchmarks.get("renovation_packages")) if isinstance(row, dict)}
    for aid, record in sorted(data.get("archetypes", {}).items(), key=lambda item: str(item[0])):
        if not isinstance(record, dict):
            continue
        _era_assessment(data, emit, aid, record)
        _renovation_checks(data, catalogue, emit, aid, record, policy)
        for state, config in sorted(_mapping(record.get("states")).items(),
                                    key=lambda item: str(item[0])):
            if not isinstance(config, dict):
                continue
            path = f"archetypes.{aid}.states.{state}"
            _ground_project_inputs(data, catalogue, emit, record, aid, state, config, policy)
            category, era = record.get("category"), record.get("era")
            if category not in _RESIDENTIAL or era not in tuple(ERAS)[:5]:
                emit("era.reference_coverage", "review", path,
                     "Outside retained Swedish residential TABULA coverage; era and intervention plausibility require a separate assessment.",
                     actual={"category": category, "era": era, "status": "not_assessed"},
                     expected={"covered_categories": sorted(_RESIDENTIAL), "covered_eras": list(ERAS)[:5]},
                     affected=_affected(record, state))
                continue
            reference = index.get((category, era, state))
            if reference is None:
                emit("tabula.reference_missing", "missing", path,
                     "Required residential TABULA benchmark is absent; not assessed.",
                     actual=None, expected={"category": category, "era": era, "state": state},
                     affected=_affected(record, state))
                continue
            _check_u_values(data, catalogue, emit, record, aid, state, config, reference, policy)
            if state not in ("standard", "advanced"):
                continue
            package = packages.get((category, era, state))
            if package is None:
                emit("tabula.reference_missing", "missing", path,
                     "Required TABULA renovation package is missing; not assessed.",
                     actual=None, expected={"category": category, "era": era, "state": state},
                     affected=_affected(record, state))
                continue
            baseline = _mapping(record.get("states")).get("existing")
            if not isinstance(baseline, dict):
                emit("tabula.measure_baseline", "missing", path,
                     "Original construction is missing; TABULA intervention cannot be assessed.",
                     actual=None, expected={"state": "existing"}, affected=_affected(record, state))
                continue
            for logical_role, code in _mapping(package.get("measures")).items():
                measure = _mapping(benchmarks.get("measures")).get(code)
                if not isinstance(measure, dict):
                    emit("tabula.reference_missing", "missing", path,
                         "TABULA measure definition is missing; not assessed.", actual=None,
                         expected={"measure_code": code}, affected=_affected(record, state))
                    continue
                override = _mapping(_mapping(package.get("measure_overrides")).get(logical_role))
                if override:
                    allowed = {"placement", "placement_source_locator"}
                    if (set(override) != allowed
                            or override.get("placement") != "interior_or_warm_side"
                            or not isinstance(override.get("placement_source_locator"), str)
                            or not override["placement_source_locator"].strip()):
                        emit("tabula.reference_missing", "missing", path,
                             "The package placement override is unsupported or incomplete; the intervention is not assessed.",
                             actual=dict(override),
                             expected={"allowed_fields": sorted(allowed),
                                       "placement": "interior_or_warm_side",
                                       "placement_source_locator": "nonempty source locator"},
                             affected=_affected(record, state))
                        continue
                    measure = dict(measure) | dict(override)
                boundary_target = _mapping(_mapping(reference.get("elements")).get(logical_role))
                _check_measure(data, catalogue, emit, record, aid, state, config, baseline,
                               logical_role, measure, policy, boundary_target)
