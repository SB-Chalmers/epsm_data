"""Read-only, forward checks of the curated LoD2 catalogue.

These project policies report invalid inputs, missing information and matters
requiring construction judgement separately. They neither repair definitions
nor certify structural, fire or moisture compliance.
"""

import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
from math import isfinite
from pathlib import Path

from .classification import CATEGORIES, ERAS, STATES, ZONES

SECTIONS = (
    "materials", "thermal", "boverket", "carbon_references", "layers",
    "components", "elements", "construction_sets", "archetypes",
)
GENERIC_LABEL = "Unknown building type — multifamily assumption"
FIXTURE_FILES = ("policy.json", "construction_rules.json", "tabula_u_values.json",
                 "tabula_renovations.json", "nonresidential_construction.json")


def load_sanity_fixture(path=None):
    """Load the fixed, documented fixture layout, never discover evidence files.

    The packaged ``epsm_data.datasets.sanity`` bundle is the maintained fixture.
    An alternative fixture directory must be selected explicitly by the caller.
    """
    from .library import _object

    folder = files("epsm_data.datasets.sanity") if path is None else Path(path)
    tables = {}
    for name in FIXTURE_FILES:
        try:
            source = folder.joinpath(name).read_text(encoding="utf-8")
        except FileNotFoundError:
            # Explicit older four-file bundles remain valid. Do not import new
            # ranges from somewhere else; the report marks them not assessed.
            if path is not None and name == "nonresidential_construction.json":
                continue
            raise
        record = json.loads(source, object_pairs_hook=_object)
        if not isinstance(record, dict) or record.get("schema_version") != 1:
            raise ValueError(f"Unsupported sanity fixture schema: {name}")
        tables[name] = record
    fixture = {
        "schema_version": 1,
        "fixture_id": tables["policy.json"].get("fixture_id"),
        "policy": tables["policy.json"].get("policy"),
        "construction_rules": tables["construction_rules.json"],
        "u_values": tables["tabula_u_values.json"].get("u_values"),
        "measures": tables["tabula_renovations.json"].get("measures"),
        "renovation_packages": tables["tabula_renovations.json"].get("renovation_packages"),
        "sources": {
            "tabula_u_values": tables["tabula_u_values.json"].get("sources"),
            "tabula_renovations": tables["tabula_renovations.json"].get("sources"),
        },
    }
    if "nonresidential_construction.json" in tables:
        fixture["nonresidential_construction"] = tables["nonresidential_construction.json"]
    _validate_fixture(fixture)
    return fixture


def _validate_fixture(fixture):
    if not isinstance(fixture, dict) or fixture.get("schema_version") != 1:
        raise ValueError("Sanity fixture requires schema_version 1")
    if not isinstance(fixture.get("fixture_id"), str) or not fixture["fixture_id"].strip():
        raise ValueError("Sanity fixture requires a stable fixture_id")
    for name, kind in (("policy", dict), ("construction_rules", dict), ("u_values", list),
                       ("measures", dict), ("renovation_packages", list)):
        if not isinstance(fixture.get(name), kind):
            raise ValueError(f"Invalid sanity fixture table: {name}")
    policy = fixture["policy"]
    numeric = ("u_value_relative_tolerance", "density_review_relative_difference",
               "density_prominent_relative_difference", "area_fraction_tolerance",
               "nominal_added_thickness_tolerance_m", "u_value_numeric_tolerance_w_m2k",
               "insulation_conductivity_max_w_mk", "insulation_minimum_area_fraction",
               "heuristic_renovation_age_years")
    for name in numeric:
        value = policy.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
            raise ValueError(f"Sanity fixture policy must be finite and nonnegative: {name}")
    if policy["density_review_relative_difference"] > policy["density_prominent_relative_difference"]:
        raise ValueError("Sanity fixture density warning thresholds are reversed")
    if policy["insulation_minimum_area_fraction"] > 1 or policy["area_fraction_tolerance"] >= 1:
        raise ValueError("Sanity fixture fractions must lie within their valid ranges")
    if "nonresidential_construction" in fixture:
        from .sanity_nonresidential import validate_nonresidential_fixture

        validate_nonresidential_fixture(fixture["nonresidential_construction"])
    expected_generic = {
        "requested_category": "generic", "donor_category": "multi_family",
        "assumption_label": GENERIC_LABEL, "is_average": False,
    }
    if policy.get("generic_fallback") != expected_generic:
        raise ValueError("Sanity fixture generic_fallback must declare the agreed labelled MF reference")
    rules = fixture["construction_rules"]
    required_tables = {
        "material_families": dict, "family_name_patterns": list, "subtype_name_patterns": list,
        "thermal_units": dict, "density_units": list, "nominal_precision": dict,
        "geometry": dict, "assembly": dict,
    }
    for name, kind in required_tables.items():
        if not isinstance(rules.get(name), kind) or not rules[name]:
            raise ValueError(f"Sanity fixture construction_rules table is missing or invalid: {name}")
    for family, bounds in rules["material_families"].items():
        if not isinstance(bounds, dict):
            raise ValueError(f"Invalid material family bounds: {family}")
        low, high = bounds.get("minimum_m"), bounds.get("maximum_m")
        if any(isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value)
               for value in (low, high)) or not 0 < low <= high:
            raise ValueError(f"Invalid material family thickness range: {family}")
    for table in ("family_name_patterns", "subtype_name_patterns"):
        for row in rules[table]:
            if not isinstance(row, dict) or not isinstance(row.get("pattern"), str):
                raise ValueError(f"Invalid construction_rules pattern: {table}")
            field = "family" if table == "family_name_patterns" else "subtype"
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"Invalid construction_rules pattern identity: {table}")
            if field == "family" and row[field] not in rules["material_families"]:
                raise ValueError("Construction pattern references an unknown material family")
            try:
                re.compile(row["pattern"])
            except re.error as exc:
                raise ValueError(f"Invalid construction_rules pattern: {table}") from exc
    for key in ("families", "side_conventions", "layer_functions"):
        if not isinstance(rules["assembly"].get(key), list) or not rules["assembly"][key]:
            raise ValueError(f"Missing construction_rules assembly definitions: {key}")
    for key in ("parallel_depth_relative_tolerance", "parallel_depth_absolute_tolerance"):
        value = rules["geometry"].get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
            raise ValueError(f"Invalid construction_rules geometry tolerance: {key}")
    for field in ("conductivity", "density", "specific_heat", "u_value", "u_factor", "shgc", "vt",
                  "thermal_absorptance", "solar_absorptance", "visible_absorptance"):
        unit = rules["thermal_units"].get(field)
        if not isinstance(unit, dict) or not isinstance(unit.get("canonical"), str) or not isinstance(unit.get("accepted"), list) or not unit["accepted"]:
            raise ValueError(f"Invalid construction_rules thermal units: {field}")
    window_pattern = rules.get("window_product_name_pattern")
    if not isinstance(window_pattern, str) or not window_pattern:
        raise ValueError("Missing construction_rules window product pattern")
    try:
        re.compile(window_pattern)
    except re.error as exc:
        raise ValueError("Invalid construction_rules window product pattern") from exc
    increment = rules["nominal_precision"].get("increment_mm")
    if isinstance(increment, bool) or not isinstance(increment, (int, float)) or not isfinite(increment) or increment <= 0:
        raise ValueError("Invalid construction_rules nominal precision increment")
    json.dumps(fixture, allow_nan=False)


def _json_value(value):
    """Keep even malformed input diagnostics finite and JSON portable."""
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, set):
        return [_json_value(item) for item in sorted(value, key=str)]
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, float) and not isfinite(value):
        return repr(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _record(section, identifier):
    item = section.get(identifier, {}) if isinstance(section, Mapping) and isinstance(identifier, (str, int)) else {}
    return item if isinstance(item, Mapping) else {}


def _sequence(value):
    return value if isinstance(value, (list, tuple)) else ()


def _usage_index(data):
    """Walk references defensively; index missing targets as well as valid ones."""
    usages = defaultdict(set)
    families = {}

    def walk(section, identifier, user, seen):
        if not isinstance(identifier, str) or not identifier:
            return
        node = section, identifier
        usages[node].add(user)
        if node in seen:
            return
        seen = seen | {node}
        record = _record(data.get(section), identifier)
        children = []
        if section == "materials":
            for target, field in (("thermal", "thermal_id"), ("boverket", "boverket_id"),
                                  ("carbon_references", "carbon_reference_id")):
                value = record.get(field)
                if value is not None:
                    children.append((target, str(value)))
        elif section == "layers":
            children = [("materials", item.get("material_id"))
                        for item in _sequence(record.get("materials")) if isinstance(item, Mapping)]
        elif section == "components":
            children = [("layers", item.get("layer_id"))
                        for item in _sequence(record.get("layers")) if isinstance(item, Mapping)]
        elif section == "elements":
            children = [("components", item) for item in _sequence(record.get("components"))]
            children.append(("materials", record.get("window_material_id")))
        elif section == "construction_sets":
            elements = record.get("elements")
            children = [("elements", item) for item in elements.values()] if isinstance(elements, Mapping) else []
        for target, child in children:
            walk(target, child, user, seen)

    archetypes = data.get("archetypes", {})
    for aid, record in archetypes.items():
        if not isinstance(record, Mapping):
            continue
        category, era = record.get("category"), record.get("era")
        if isinstance(category, str) and isinstance(era, str):
            families[(category, era)] = aid
        states = record.get("states", {})
        if not isinstance(states, Mapping):
            continue
        for state, config in states.items():
            user = aid, None if state == "default" else state
            usages[("archetypes", aid)].add(user)
            if isinstance(config, Mapping):
                walk("construction_sets", config.get("construction_set_id"), user, set())
                walk("elements", config.get("weather_shell_element_id"), user, set())
    return usages, families


def _collector(data):
    usages, families = _usage_index(data)
    findings = {}

    def users_for_path(path):
        if path in {"catalogue", "archetypes", "benchmarks"}:
            return set().union(*(users for (section, _), users in usages.items() if section == "archetypes"))
        for section in SECTIONS:
            if path == section:
                return set().union(*(users for (target, _), users in usages.items() if target == section))
            if not path.startswith(section + "."):
                continue
            records = data.get(section, {})
            candidates = [key for key in records if isinstance(key, str)
                          and (path == f"{section}.{key}" or path.startswith(f"{section}.{key}."))]
            if candidates:
                identifier = max(candidates, key=len)
                users = usages[(section, identifier)]
                if section == "archetypes":
                    prefix = f"archetypes.{identifier}.states."
                    if path.startswith(prefix):
                        state = path[len(prefix):].split(".", 1)[0]
                        return {(identifier, None if state == "default" else state)}
                return users
        return set()

    def normalize_affected(affected, path, zone):
        selected = defaultdict(set)
        if affected is None:
            for aid, state in users_for_path(path):
                selected[(aid, state)].update((zone,) if zone else ZONES)
        else:
            for item in affected:
                if isinstance(item, str):
                    parts = item.split(":")
                    if len(parts) == 4 and parts[1] in ERAS:
                        category, era, selected_zone, state = parts
                        aid = families.get(("multi_family" if category == "generic" else category, era))
                        if aid is not None:
                            selected[(aid, None if state == "default" else state)].add(selected_zone)
                    else:
                        for aid, state in usages[("archetypes", item)]:
                            selected[(aid, state)].update(ZONES)
                elif isinstance(item, Mapping):
                    aid = item.get("archetype_id")
                    if aid is not None:
                        selected[(aid, item.get("state"))].update(item.get("climate_zones", ZONES))
                elif isinstance(item, (tuple, list)) and len(item) == 2:
                    selected[tuple(item)].update(ZONES)
        return [
            {"archetype_id": aid, "state": state, "climate_zones": sorted(zones)}
            for (aid, state), zones in sorted(selected.items(), key=lambda item: (item[0][0], item[0][1] or ""))
        ]

    def emit(rule_id, severity, path, message, *, actual=None, expected=None, affected=None, **details):
        if severity not in {"error", "missing", "review"}:
            raise ValueError(f"Invalid sanity severity: {severity}")
        if affected is None and details.get("related_paths"):
            combined = set(users_for_path(path))
            for related_path in details["related_paths"]:
                combined.update(users_for_path(related_path))
            affected = sorted(combined, key=lambda item: (item[0], item[1] or ""))
        users = normalize_affected(affected, path, details.get("climate_zone"))
        finding = _json_value({
            "rule_id": rule_id, "severity": severity, "path": path, "message": message,
            "actual": actual, "expected": expected, "affected_archetypes": users,
            "generic_fallback_affected": any(
                _record(data["archetypes"], user["archetype_id"]).get("category") == "multi_family"
                for user in users
            ),
            **details,
        })
        identity = sha256(json.dumps(finding, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        findings[identity] = {"id": identity, **finding}

    return findings, emit


def _classification(data, emit):
    found = defaultdict(list)
    for aid, record in data["archetypes"].items():
        if not isinstance(record, Mapping):
            emit("catalogue.definition", "error", f"archetypes.{aid}", "Archetype must be a mapping.", actual=record)
            continue
        category, era = record.get("category"), record.get("era")
        if not isinstance(category, str) or not isinstance(era, str) or category not in CATEGORIES or era not in ERAS:
            emit("catalogue.classification", "error", f"archetypes.{aid}",
                 "Only the four authored types and seven supported eras belong in the physical catalogue.",
                 actual={"category": category, "era": era}, expected={"categories": CATEGORIES, "eras": tuple(ERAS)})
            continue
        found[(category, era)].append(aid)
        states = record.get("states")
        if not isinstance(states, Mapping):
            emit("catalogue.states", "missing", f"archetypes.{aid}.states", "State definitions are missing.")
            continue
        expected_states = {"default"} if era == "SE.07" else set(STATES)
        rule = "catalogue.se07" if era == "SE.07" else "catalogue.states"
        if set(states) != expected_states:
            emit(rule, "error" if set(states) - expected_states else "missing", f"archetypes.{aid}.states",
                 "SE.07 has one new-construction state; earlier eras have the three declared variants.",
                 actual=sorted(states), expected=sorted(expected_states))
        start, end = ERAS[era]
        for state, config in states.items():
            path = f"archetypes.{aid}.states.{state}"
            if not isinstance(config, Mapping):
                emit("catalogue.definition", "error", path, "State must be a mapping.", actual=config)
                continue
            year = config.get("construction_year")
            if year is None:
                emit("catalogue.construction_year", "missing", path + ".construction_year", "Original construction year is missing.")
            elif isinstance(year, bool) or not isinstance(year, int) or year < start or (end is not None and year > end):
                emit("catalogue.construction_year", "error", path + ".construction_year", "Original construction year must lie within its era.", actual=year, expected=[start, end])
            topology = config.get("roof_topology")
            if not isinstance(topology, str) or topology not in {"cold_attic", "compact"}:
                emit("construction.boundary", "missing" if topology is None else "error", path + ".roof_topology",
                     "The thermal top boundary must have an explicit supported topology.", actual=topology)
            if config.get("weather_shell_element_id") is None or config.get("weather_shell_element_id") == "":
                emit("construction.weather_shell", "missing", path + ".weather_shell_element_id",
                     "The representative weather-shell reference is missing.")
            envelope = config.get("envelope_performance")
            if envelope is not None and not isinstance(envelope, Mapping):
                emit("construction.envelope", "error", path + ".envelope_performance",
                     "Envelope defaults must be a mapping.", actual=envelope)
                envelope = {}
            envelope = envelope or {}
            if envelope.get("infiltration_ach") is None and envelope.get("infiltration_l_s_m2") is None:
                emit("construction.envelope", "missing", path + ".envelope_performance.infiltration",
                     "An explicit infiltration rate and its basis are required.")
            if envelope.get("infiltration_reference_basis") == "tabula_reference_volume" and config.get("reference_height_m") is None:
                emit("construction.envelope", "missing", path + ".reference_height_m",
                     "TABULA source-volume infiltration requires its reference height.")
            construction = _record(data["construction_sets"], config.get("construction_set_id"))
            roles = construction.get("elements", {})
            if not isinstance(roles, Mapping):
                continue
            thermal_id = roles.get("TOP_FLOOR", roles.get("ROOF"))
            shell_id = config.get("weather_shell_element_id")
            if topology == "cold_attic" and shell_id and shell_id == thermal_id:
                emit("construction.boundary", "error", path + ".weather_shell_element_id",
                     "A cold attic cannot use the same element as both thermal boundary and separate weather roof.", actual=shell_id)
            if topology == "cold_attic" and "ROOF" in roles and "TOP_FLOOR" not in roles:
                emit("construction.boundary", "review", path + ".construction_set_id",
                     "Cold-attic top is named ROOF; confirm it represents the conditioned ceiling, not the weather shell.",
                     actual=thermal_id, assessment="not_assessed")
            if topology == "compact" and "TOP_FLOOR" in roles and "ROOF" not in roles:
                emit("construction.boundary", "error", path + ".construction_set_id", "Compact roof has a ceiling-only role without a roof assembly.")
    for category in CATEGORIES:
        for era in ERAS:
            matches = found[(category, era)]
            if len(matches) != 1:
                emit("catalogue.coverage", "missing" if not matches else "error", "archetypes",
                     "Each authored type/era needs exactly one family.", actual=matches, expected={"category": category, "era": era})
    required = {"EXT_WALL", "GROUND_FLOOR", "BASEMENT_WALL", "INTERMEDIATE_FLOOR", "INT_WALL_NONLOADBEARING", "WINDOW"}
    for cid, record in data["construction_sets"].items():
        if not isinstance(record, Mapping) or not isinstance(record.get("elements"), Mapping):
            emit("construction.roles", "missing", f"construction_sets.{cid}.elements", "Construction-set role assignments are missing.")
            continue
        missing = required - set(record["elements"])
        if not ({"ROOF", "TOP_FLOOR"} & set(record["elements"])):
            missing.add("ROOF or TOP_FLOOR")
        if missing:
            emit("construction.roles", "missing", f"construction_sets.{cid}.elements", "Required reusable construction roles are absent.", actual=sorted(record["elements"]), expected=sorted(missing))


def _operation(data, catalogue, emit):
    requirements = []
    if catalogue is None:
        emit("operation.not_assessed", "review", "archetypes", "Operating profiles could not be assessed because the catalogue cannot be hydrated.", assessment="not_assessed")
        return requirements
    for aid, record in data["archetypes"].items():
        if not isinstance(record, Mapping):
            continue
        for raw_state in (record.get("states") or {}):
            state = None if raw_state == "default" else raw_state
            path = f"archetypes.{aid}.states.{raw_state}.operating_profile"
            try:
                archetype = catalogue.get(aid, state=state)
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                emit("operation.not_assessed", "error", path, "Invalid archetype defaults prevent operating-profile assessment.", actual=str(exc), assessment="not_assessed")
                continue
            profile = archetype.operating_profile
            if profile is None:
                emit("operation.profile", "missing", path, "A named normal-use operating profile is required.")
                continue
            values = profile.values
            applicability = values.get("applicability", {})
            types = applicability.get("building_types", ()) if isinstance(applicability, Mapping) else ()
            if not types:
                emit("operation.applicability", "missing", path, "Profile building-type applicability must be explicit.", actual=profile.profile_id)
            elif record.get("category") not in types:
                emit("operation.applicability", "error", path, "Operating profile is incompatible with the authored building type.", actual=profile.profile_id, expected=record.get("category"))
            if not profile.source_references and not values.get("source_uri"):
                emit("operation.source", "missing", path, "Normal-use defaults require a named source.", actual=profile.profile_id)
            if not values.get("area_basis"):
                emit("operation.reference_area", "missing", path, "The profile must explicitly declare its load reference-area basis.", actual=profile.profile_id, expected="Explicit reference area such as Atemp")
            declared = values.get("requirements")
            if not isinstance(declared, (tuple, list)) or "load_reference_area_m2" not in declared:
                emit("operation.requirements", "missing", path, "Declare the required project reference-area input.")
                declared = ()
            if record.get("category") in {"office", "school"} and "calendar" not in declared:
                emit("operation.requirements", "missing", path, "Office and school profiles must declare the project calendar requirement.")
            requirements.append({"archetype_id": aid, "state": state, "profile_id": profile.profile_id,
                                 "project_inputs": list(declared), "area_basis": values.get("area_basis")})
            controls = {}
            for section in ("use", "operation_inputs", "building_assumptions"):
                source = values.get(section)
                if isinstance(source, Mapping):
                    controls.update(source)
            heating, cooling = controls.get("heating_setpoint_c"), controls.get("cooling_setpoint_c")
            if isinstance(heating, (int, float)) and isinstance(cooling, (int, float)) and heating >= cooling:
                emit("operation.setpoints", "error", path, "Heating setpoint must be below cooling setpoint.", actual={"heating_c": heating, "cooling_c": cooling})
            for key, value in controls.items():
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    continue
                if "fraction" in key and not 0 <= value <= 1:
                    emit("operation.fraction", "error", path + "." + key, "Operating fractions must lie between zero and one.", actual=value)
                if any(term in key for term in ("_w_m2", "_l_s_m2", "_kwh_m2", "density_per_m2")) and value < 0:
                    emit("operation.quantity", "error", path + "." + key, "Operating gains and flow intensities cannot be negative.", actual=value)
    return requirements


def _generic(catalogue, emit):
    if catalogue is None:
        return
    from .classification import ArchetypeKey

    for aid in catalogue.ids(category="multi_family"):
        record = catalogue.archetype_records[aid]
        for state in catalogue.renovation_states(aid) or (None,):
            path = f"archetypes.{aid}.states.{state or 'default'}"
            try:
                donor = catalogue.get(aid, state=state)
                fallback = catalogue.for_year("generic", donor.construction_year, state=state)
                metadata = catalogue.nominal_metadata(fallback.archetype_id, state=state)
                selection = metadata.get("selection", {})
                matches = (
                    fallback.construction_set is donor.construction_set
                    and fallback.operating_profile is donor.operating_profile
                    and fallback.display_name == GENERIC_LABEL
                    and selection.get("requested_category") == "generic"
                    and selection.get("donor_category") == "multi_family"
                    and selection.get("donor_archetype_id") == aid
                    and selection.get("assumption_label") == GENERIC_LABEL
                )
                for zone in ZONES:
                    slot = catalogue.get_slot(ArchetypeKey("generic", record["era"], zone, state))
                    matches = matches and slot.archetype_id == aid and slot.key.category == "generic"
                if not matches:
                    emit("generic.fallback", "error", path, "Generic must be a labelled reference to the matching MF fabric and residential operation.", expected=GENERIC_LABEL)
            except (KeyError, ValueError, TypeError, AttributeError) as exc:
                emit("generic.fallback", "error", path, "Generic MF fallback could not be resolved.", actual=str(exc), expected=GENERIC_LABEL)


def check_catalogue(catalogue_or_data, *, fixture=None):
    """Return deterministic JSON findings without changing any input definition.

    Accept an explicitly loaded Catalogue or a raw JSON-compatible mapping. Raw
    mappings allow invalid authoring inputs to be reported before loading. The
    bundled fixture is read only when no explicit fixture is supplied.
    Project calendars, geometry and installed systems remain consumer inputs.
    """
    from .library import Catalogue, legacy_thermal_names
    from .sanity_physics import check_physics
    from .sanity_reference import check_references

    catalogue = catalogue_or_data if isinstance(catalogue_or_data, Catalogue) else None
    raw = catalogue.resolved_dict() if catalogue is not None else legacy_thermal_names(
        deepcopy(catalogue_or_data))
    if not isinstance(raw, Mapping):
        raise TypeError("Sanity checks require a Catalogue or a raw catalogue mapping")
    source_failure = None
    if raw.get("schema_version") == 2:
        try:
            catalogue = Catalogue(raw)
            raw = catalogue.resolved_dict()
        except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            source_failure = str(exc)
    data = dict(raw)
    malformed = []
    for section in SECTIONS:
        if section == "carbon_references" and section not in data:
            data[section] = {}
        if not isinstance(data.get(section), Mapping):
            if source_failure is None:
                malformed.append((section, data.get(section)))
            data[section] = {}
    findings, emit = _collector(data)
    fixture = load_sanity_fixture(fixture) if fixture is None or isinstance(fixture, (str, Path)) else deepcopy(fixture)
    _validate_fixture(fixture)
    for section, value in malformed:
        emit("catalogue.section", "error", section, "Catalogue section must be an ID-to-definition mapping.", actual=value)
    if type(raw.get("schema_version")) is not int or raw["schema_version"] not in (1, 2):
        emit("catalogue.schema", "error", "schema_version", "Unsupported catalogue schema.", actual=raw.get("schema_version"), expected=1)
    if not isinstance(raw.get("dataset_id"), str) or not raw["dataset_id"].strip():
        emit("catalogue.identity", "error", "dataset_id", "A nonempty dataset identity is required.")
    if source_failure is not None:
        emit("catalogue.hydration", "error", "catalogue",
             "Pinned source records could not be resolved; no substitute values or default source versions were used.",
             actual=source_failure, assessment="not_assessed")
        for rule in ("carbon.not_assessed", "operation.not_assessed", "era.not_assessed"):
            emit(rule, "review", "catalogue",
                 "Source resolution failed; dependent checks are not assessed.",
                 assessment="not_assessed")
        project_requirements = []
    else:
        check_physics(data, emit, fixture=fixture)
        _classification(data, emit)
        if catalogue is None:
            try:
                catalogue = Catalogue(raw)
            except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
                emit("catalogue.hydration", "error", "catalogue", "Invalid supplied definitions prevent validated physical calculations.", actual=str(exc), assessment="not_assessed")
        project_requirements = _operation(data, catalogue, emit)
        _generic(catalogue, emit)
        check_references(data, catalogue, emit, fixture)
    ordered = sorted(findings.values(), key=lambda item: (
        {"error": 0, "missing": 1, "review": 2}[item["severity"]], item["rule_id"], item["path"], item["id"]
    ))
    counts = Counter(item["severity"] for item in ordered)
    blocking = counts["error"] + counts["missing"]
    readiness = {}
    groups = {
        "thermal_inputs": ("thermal.", "layer.geometry", "layer.fractions", "layer.depth", "component.", "assembly.role", "construction.", "catalogue.hydration"),
        "carbon_inputs": ("carbon.", "density."),
        "operating_defaults": ("operation.",),
        "reference_agreement": ("tabula.", "renovation.", "era.", "nonres."),
    }
    for group, prefixes in groups.items():
        def belongs(item):
            if item["rule_id"].startswith(prefixes):
                return True
            if item["rule_id"].startswith("reference."):
                carbon = item.get("expected") in {"boverket", "carbon_references"}
                return (group == "carbon_inputs" and carbon) or (group == "thermal_inputs" and not carbon)
            return False

        group_counts = Counter(item["severity"] for item in ordered if belongs(item))
        readiness[group] = {
            "status": "blocked" if group_counts["error"] + group_counts["missing"] else "review" if group_counts["review"] else "pass",
            **{severity + "_count": group_counts[severity] for severity in ("error", "missing", "review")},
        }
    return {
        "dataset_id": _json_value(raw.get("dataset_id")),
        "fixture_id": fixture["fixture_id"],
        "policy": deepcopy(fixture["policy"]),
        "summary": {"status": "blocked" if blocking else "review" if counts["review"] else "pass",
                    "error_count": counts["error"], "missing_count": counts["missing"],
                    "review_count": counts["review"], "blocking_count": blocking,
                    "finding_count": len(ordered)},
        "project_requirements": project_requirements,
        "readiness": readiness,
        "findings": ordered,
    }
