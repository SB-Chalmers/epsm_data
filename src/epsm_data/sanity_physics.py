"""Read-only screening of raw catalogue definitions.

Ranges below are deliberately broad project screening policies, not Swedish
regulatory limits or structural, fire and moisture certification. Source links
and dimensional correctness are checked independently of heuristic plausibility.
"""

import json
import math
import re
from collections.abc import Mapping
from urllib.parse import urlsplit

from .carbon_scope import retained_stock_assessments
from .domain.enums import BuildingElement
from .sources import OPAQUE_FIELDS, WINDOW_FIELDS

ROLES = {role.value for role in BuildingElement}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _choice(value, choices):
    return isinstance(value, str) and value in choices


def _items(value):
    return value if isinstance(value, (list, tuple)) else ()


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _label(value):
    return re.sub(r"[\s_-]+", " ", str(value or "").casefold()).strip()


def _family(record, rules):
    """Return (family, inferred); ambiguous descriptive names remain unclassified."""
    explicit = record.get("material_family")
    if explicit is not None:
        return explicit if isinstance(explicit, str) else None, False
    name = _label(record.get("name", record.get("Name")))
    return next(((item["family"], True) for item in rules["family_name_patterns"]
                 if re.search(item["pattern"], name)), (None, False))


def _subtype(record, rules):
    name = _label(record.get("name", record.get("Name")))
    for item in rules["subtype_name_patterns"]:
        if re.search(item["pattern"], name):
            return item["subtype"]
    return None


def _signature(section, record):
    """Match the catalogue's physical signatures, excluding labels and notes."""
    if section == "materials":
        return {key: record.get(key) for key in
                ("kind", "properties", "boverket_id", "carbon_reference_id")}
    if section == "layers":
        if record.get("thickness") is None or not record.get("materials"):
            return None
        return {key: record.get(key, False if key == "is_composite" else None)
                for key in ("thickness", "materials", "is_composite")}
    if section == "components":
        if any(record.get(key) is None for key in ("application", "shearing_layer", "layers")):
            return None
        slots = list(_items(record.get("layers")))
        if any(not isinstance(slot, Mapping) for slot in slots):
            return None
        slots.sort(key=lambda slot: (not _number(slot.get("position")),
                                     slot.get("position") if _number(slot.get("position")) else 0))
        return {"application": record["application"],
                "shearing_layer": record["shearing_layer"],
                "layers": [{key: value for key, value in slot.items()
                            if key != "layer_function"} for slot in slots]}
    if section == "elements":
        if not record.get("role"):
            return None
        return {key: record.get(key) for key in ("role", "components", "window_material_id")}
    if section == "construction_sets":
        return record.get("elements") or None
    return None


def check_physics(data, emit, fixture=None):
    """Emit non-mutating material and assembly findings from even invalid raw data."""
    if fixture is None:
        from .sanity import load_sanity_fixture

        fixture = load_sanity_fixture()
    rules, policy = fixture["construction_rules"], fixture["policy"]
    if not isinstance(data, Mapping):
        emit("definition.structure", "error", "", "Catalogue must be an object.")
        return
    sections = {}
    for section in ("materials", "honeybee", "boverket", "carbon_references", "layers",
                    "components", "elements", "construction_sets", "archetypes"):
        raw = data.get(section, {})
        if not isinstance(raw, Mapping):
            emit("definition.structure", "error", section, "Definitions must be an ID mapping.",
                 actual=raw)
            raw = {}
        sections[section] = {}
        for identifier, record in raw.items():
            if not isinstance(record, Mapping):
                emit("definition.structure", "error", f"{section}.{identifier}",
                     "Definition must be an object.", actual=record)
            else:
                sections[section][identifier] = record

    def reference(section, identifier, path, *, optional=False):
        if identifier is None or identifier == "":
            if not optional:
                emit("reference.missing", "missing", path, "Required reference is missing.",
                     expected=section)
            return None
        key = str(identifier) if section == "boverket" and isinstance(identifier, int) else identifier
        if not isinstance(key, str) or key not in sections[section]:
            emit("reference.dangling", "error", path, "Reference does not resolve.",
                 actual=identifier, expected=section)
            return None
        return sections[section][key]

    for section in ("materials", "layers", "components", "elements", "construction_sets"):
        signatures = {}
        for identifier, record in sections[section].items():
            signature = _signature(section, record)
            if signature is None:
                continue
            key = json.dumps(signature, sort_keys=True, default=str)
            if key in signatures:
                emit("definition.duplicate", "error", f"{section}.{identifier}",
                     "Identical physical definitions must reuse one shared ID.",
                     actual=identifier, expected=signatures[key],
                     related_paths=[f"{section}.{signatures[key]}"])
            else:
                signatures[key] = identifier

    stock_assessments = retained_stock_assessments(data)
    names = {}
    for mid, record in sections["materials"].items():
        path = f"materials.{mid}"
        name = record.get("name")
        if not isinstance(name, str) or not name.strip():
            emit("material.name", "error", path + ".name", "Material requires an identifiable name.",
                 actual=name)
        else:
            if name != name.strip():
                emit("material.name", "review", path + ".name", "Trim material name whitespace.",
                     actual=name, expected=name.strip())
            label = _label(name)
            if label in names:
                other = names[label]
                if _signature("materials", record) != _signature("materials", sections["materials"][other]):
                    emit("material.name_ambiguous", "review", path + ".name",
                         "Different material definitions share the same name; add a physical qualifier.",
                         actual=name, expected="Distinct material family and variant",
                         related_paths=[f"materials.{other}"])
            else:
                names[label] = mid
            if re.fullmatch(r"(?:material|unknown|unnamed|generic|test|new material)(?: \d+)?", label):
                emit("material.name_ambiguous", "review", path + ".name",
                     "Name does not identify a material family or variant.", actual=name)
            if re.search(r"used in|archetype|\b(?:sf|mf|se)[ ._-]?0?[1-7]\b|\boffice_|\bschool_", name,
                         re.IGNORECASE):
                emit("material.name_usage", "review", path + ".name",
                     "Shared material name describes usage rather than physical identity.", actual=name)
        family, _ = _family(record, rules)
        if record.get("material_family") is not None and family not in rules["material_families"]:
            emit("material.family", "review", path + ".material_family",
                 "Unknown material family; thickness and mapping screening cannot use it.",
                 actual=record.get("material_family"), expected=sorted(rules["material_families"]))
        _check_thermal(record, path, reference, emit, rules)
        bov = reference("boverket", record.get("boverket_id"), path + ".boverket_id", optional=True)
        external = reference("carbon_references", record.get("carbon_reference_id"),
                             path + ".carbon_reference_id", optional=True)
        _check_material_carbon(record, path, bov, external, emit, rules,
                               stock_assessments.get(mid))
        _check_density(record, path, bov, emit, rules, policy, external=external)

    for identifier, record in sections["honeybee"].items():
        if record.get("identifier") != identifier:
            emit("thermal.identity", "error", f"honeybee.{identifier}.identifier",
                 "Thermal source identifier disagrees with its catalogue key.",
                 actual=record.get("identifier"), expected=identifier)
    for identifier, record in sections["boverket"].items():
        if str(record.get("ResourceId")) != str(identifier):
            emit("carbon.identity", "error", f"boverket.{identifier}.ResourceId",
                 "Boverket ResourceId disagrees with its catalogue key.",
                 actual=record.get("ResourceId"), expected=identifier)
        _check_boverket_modules(record, f"boverket.{identifier}", emit)
    for identifier, record in sections["carbon_references"].items():
        _check_external_carbon(identifier, record, f"carbon_references.{identifier}", emit)

    for lid, record in sections["layers"].items():
        path = f"layers.{lid}"
        _check_layer(record, path, reference, emit, rules, policy)
    for cid, record in sections["components"].items():
        path = f"components.{cid}"
        role = record.get("application")
        if not _choice(role, ROLES):
            emit("component.role", "error", path + ".application", "Unknown component application.",
                 actual=role, expected=sorted(ROLES))
        if not _choice(record.get("shearing_layer"), {"Skin", "Structure", "Services", "Space", "Stuff"}):
            emit("component.role", "error", path + ".shearing_layer", "Unknown shearing-layer group.",
                 actual=record.get("shearing_layer"))
        positions = []
        slots = record.get("layers")
        if not isinstance(slots, (list, tuple)) or not slots:
            emit("component.positions", "missing", path + ".layers", "Component needs ordered layers.")
        for index, slot in enumerate(_items(slots)):
            base = f"{path}.layers.{index}"
            if not isinstance(slot, Mapping):
                emit("component.positions", "error", base, "Layer slot must be an object.")
                continue
            reference("layers", slot.get("layer_id"), base + ".layer_id")
            if "layer_function" in slot and not _choice(
                slot["layer_function"], rules["assembly"]["layer_functions"]
            ):
                emit("assembly.metadata", "error", base + ".layer_function",
                     "Unknown component layer-slot function.", actual=slot["layer_function"],
                     expected=rules["assembly"]["layer_functions"])
            position = slot.get("position")
            if position is None:
                emit("component.positions", "missing", base + ".position", "Layer position is missing.")
            elif isinstance(position, bool) or not isinstance(position, int) or position < 0:
                emit("component.positions", "error", base + ".position",
                     "Layer positions must be nonnegative integers.", actual=position)
            else:
                positions.append(position)
        if len(positions) != len(set(positions)):
            emit("component.positions", "error", path + ".layers", "Layer positions must be unique.",
                 actual=positions)
        _check_assembly_metadata(record, path, emit, rules, required=False)

    for eid, record in sections["elements"].items():
        path, role = f"elements.{eid}", record.get("role")
        if not _choice(role, ROLES):
            emit("assembly.role", "error", path + ".role", "Unknown element role.", actual=role)
        if role == "WINDOW":
            material = reference("materials", record.get("window_material_id"),
                                 path + ".window_material_id")
            if material is not None and material.get("kind") != "window":
                emit("assembly.role", "error", path + ".window_material_id",
                     "Window element must reference a whole-window material.")
            if record.get("components"):
                emit("assembly.role", "error", path + ".components",
                     "Whole-window element cannot also contain opaque components.")
            continue
        components = []
        if not isinstance(record.get("components"), (list, tuple)) or not record.get("components"):
            emit("assembly.role", "missing", path + ".components", "Opaque element needs components.")
        for index, cid in enumerate(_items(record.get("components"))):
            component = reference("components", cid, f"{path}.components.{index}")
            if component is not None:
                components.append(component)
                if not _same_role(component.get("application"), role):
                    emit("assembly.role", "error", f"{path}.components.{index}",
                         "Component application contradicts its parent element role.",
                         actual=component.get("application"), expected=role)
                for field in ("side_convention", "assembly_family"):
                    if record.get(field) and component.get(field) and record[field] != component[field]:
                        emit("assembly.role", "error", f"{path}.components.{index}",
                             "Component assembly metadata contradicts its parent element.",
                             actual={field: component[field]}, expected={field: record[field]})
        _check_assembly_metadata(record, path, emit, rules, required=True)
        _check_assembly_order(record, components, sections["layers"], path, emit, rules)

    for sid, record in sections["construction_sets"].items():
        path = f"construction_sets.{sid}.elements"
        if not isinstance(record.get("elements"), Mapping):
            emit("assembly.role", "missing", path, "Construction set needs element assignments.")
        for role, eid in _mapping(record.get("elements")).items():
            element = reference("elements", eid, f"{path}.{role}")
            if not _choice(role, ROLES):
                emit("assembly.role", "error", f"{path}.{role}", "Unknown construction-set role.",
                     actual=role)
            if element is not None and not _same_role(element.get("role"), role):
                emit("assembly.role", "error", f"{path}.{role}",
                     "Assigned element role contradicts construction-set role.",
                     actual=element.get("role"), expected=role)
    for aid, record in sections["archetypes"].items():
        for state, config in _mapping(record.get("states")).items():
            path = f"archetypes.{aid}.states.{state}"
            if not isinstance(config, Mapping):
                emit("definition.structure", "error", path, "Archetype configuration must be an object.")
                continue
            reference("construction_sets", config.get("construction_set_id"),
                      path + ".construction_set_id")
            reference("elements", config.get("weather_shell_element_id"),
                      path + ".weather_shell_element_id", optional=True)
    for section, aliases in _mapping(data.get("aliases")).items():
        if section in sections:
            for alias, target in _mapping(aliases).items():
                reference(section, target, f"aliases.{section}.{alias}")


def _check_thermal(record, path, reference, emit, rules):
    kind, properties = record.get("kind"), _mapping(record.get("properties"))
    if not _choice(kind, {"opaque", "window"}):
        emit("thermal.properties", "error", path + ".kind", "Unknown material kind.", actual=kind)
        return
    fields = OPAQUE_FIELDS if kind == "opaque" else WINDOW_FIELDS
    for field in fields:
        value = properties.get(field)
        base = f"{path}.properties.{field}"
        if value is None:
            emit("thermal.properties", "missing", base, "Thermal property is missing.")
        elif field == "roughness":
            if not _choice(value, {"VerySmooth", "Smooth", "MediumSmooth", "MediumRough", "Rough", "VeryRough"}):
                emit("thermal.properties", "error", base, "Unknown EnergyPlus roughness.", actual=value)
        elif not _number(value) or (value <= 0 if field in
                {"conductivity", "density", "specific_heat", "u_value"} else not 0 <= value <= 1):
            emit("thermal.properties", "error", base, "Thermal value is outside its physical domain.",
                 actual=value, expected="positive finite SI value" if field in
                 {"conductivity", "density", "specific_heat", "u_value"} else "finite fraction in [0,1]")
    source = reference("honeybee", record.get("honeybee_id"), path + ".honeybee_id")
    if source is not None:
        expected_type = "EnergyMaterial" if kind == "opaque" else "EnergyWindowMaterialSimpleGlazSys"
        if source.get("type") != expected_type:
            emit("thermal.source", "error", path + ".honeybee_id", "Thermal source has wrong type.",
                 actual=source.get("type"), expected=expected_type)
        for field in fields:
            source_field = "u_factor" if field == "u_value" else field
            expected, actual = source.get(source_field), properties.get(field)
            if expected is None:
                emit("thermal.source", "missing", path + ".honeybee_id",
                     "Linked thermal source lacks a required property.", actual=source_field)
            elif actual is not None and not (_number(actual) and _number(expected) and
                    math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)) and actual != expected:
                emit("thermal.source", "error", f"{path}.properties.{field}",
                     "Stored thermal property contradicts linked source.", actual=actual, expected=expected)
    for owner, base in ((record, path), (source, path + ".honeybee_id")):
        if owner is None:
            continue
        units = owner.get("property_units", owner.get("units"))
        if units is None:
            continue  # Honeybee properties use their documented SI convention.
        if not isinstance(units, Mapping):
            emit("thermal.units", "error", base + ".units", "Thermal units must identify each property.")
            continue
        for field, unit in units.items():
            expected = rules["thermal_units"].get(field)
            if expected and not _choice(unit, expected["accepted"]):
                emit("thermal.units", "error", f"{base}.units.{field}",
                     "Thermal unit contradicts the catalogue SI convention.", actual=unit, expected=expected["canonical"])


def _check_material_carbon(record, path, bov, external, emit, rules, stock=None):
    if stock is not None:
        if stock["eligible"]:
            emit("carbon.existing_stock", "review", path,
                 "Unmapped carbon belongs only to verified retained original stock. "
                 "Production is outside this assessment; new, replacement, removal or "
                 "baseline-inclusive LCA still requires factors.",
                 actual={"status": "retained_existing_unmapped", "reason": stock["reason"]},
                 expected="Retained stock only; unknown carbon remains unquantified")
            return
        emit("carbon.existing_stock_invalid", "error", path + ".carbon_assessment",
             "The retained-stock declaration is invalid or its scope cannot be proved.",
             actual=record.get("carbon_assessment"), expected=stock["issue"])
    non_product = record.get("non_product") is True and stock is None
    family, _ = _family(record, rules)
    if non_product and family != "air_cavity":
        emit("carbon.mapping", "review", path + ".non_product",
             "Non-product exemption needs an air-layer or other explicit non-product explanation.",
             actual=record.get("name"))
    if record.get("boverket_id") is not None and record.get("carbon_reference_id") is not None:
        emit("carbon.source", "error", path, "Choose one Boverket or external carbon source.")
    if bov is None and external is None:
        if not non_product:
            emit("carbon.source", "missing", path, "Product has no resolved carbon source.",
                 expected="Boverket resource or external EPD")
        return
    if non_product:
        emit("carbon.source", "error", path,
             "Non-product exemption contradicts an assigned product-carbon source.")
    source = bov if bov is not None else external
    source_family, _ = _family(source, rules)
    source_name = _label(source.get("Name", source.get("name")))
    source_is_window = bool(re.search(rules["window_product_name_pattern"], source_name))
    if (record.get("kind") == "window") != source_is_window and (
            record.get("kind") == "window" or source_is_window):
        emit("carbon.mapping", "review", path,
             "Whole-window carbon and opaque-product carbon describe different product scopes.",
             actual={"material_kind": record.get("kind"), "source": source_name},
             expected="Matching whole-window or opaque-product scope")
    notes = " ".join(str(note) for note in _items(record.get("notes")))
    qualified = bool(external and external.get("proxy_for")) or bool(re.search(r"proxy", notes, re.I))
    material_subtype, source_subtype = _subtype(record, rules), _subtype(source, rules)
    mismatch = bool(family and source_family and family != source_family) or bool(
        material_subtype and source_subtype and material_subtype != source_subtype)
    if mismatch:
        emit("carbon.mapping", "review", path,
             "Carbon source describes a different product family or subtype; review proxy suitability.",
             actual={"material": record.get("name"), "source": source.get("Name", source.get("name")),
                     "proxy_qualified": qualified},
             expected="Comparable product family or explicitly justified proxy", proxy=qualified)
    elif qualified:
        emit("carbon.mapping", "review", path,
             "Carbon mapping is an explicitly declared proxy, not a verified product match.",
             actual=external.get("proxy_for") if external else notes, proxy=True)
    elif not (family and source_family) and record.get("kind") != "window":
        emit("carbon.mapping", "review", path,
             "Product-family suitability cannot be assessed from source and material descriptions.",
             assessment="not_assessed")


def _grade_density(record, source, rules):
    """Read an explicit grade expectation, verified against its retained source.

    Multi-grade sources cannot receive a universal volume conversion. A declared
    grade may instead select the density observation in the maintained fixture;
    its exact source quotation and kg/m³ value must still agree. This never
    changes thermal density or a source's existing volume conversion.
    """
    grade = record.get("carbon_source_grade")
    identifier = record.get("boverket_id") or record.get("carbon_reference_id")
    source_identifier = source.get("ResourceId", source.get("identifier"))
    if not isinstance(grade, str) or str(identifier) != str(source_identifier):
        return None
    references = _mapping(_mapping(rules.get("density_grade_references")).get(str(identifier)))
    reference = _mapping(references.get(grade))
    value, unit = reference.get("value"), reference.get("unit")
    if not _number(value) or value <= 0 or not _choice(unit, rules["density_units"]):
        return None
    if reference.get("basis") != record.get("density_basis", "product_volume"):
        return None
    field = reference.get("source_field")
    if field not in {"TechnologyDescriptionAndIncludedProcesses", "notes"}:
        return None
    text, quote = source.get(field), reference.get("quote")
    if isinstance(text, (list, tuple)) and all(isinstance(item, str) for item in text):
        text = "\n".join(text)
    if not isinstance(text, str) or not isinstance(quote, str) or not quote or quote not in text:
        return None
    quoted = re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)\s*" + re.escape(unit) + r"(?!\w)", quote)
    if len(quoted) != 1 or not math.isclose(float(quoted[0]), value, rel_tol=1e-12):
        return None
    return value


def _check_density(record, path, bov, emit, rules, policy, *, external=None):
    if record.get("kind") != "opaque" or record.get("non_product") is True:
        return
    source = bov if bov is not None else external
    actual = _mapping(record.get("properties")).get("density")
    family, _ = _family(record, rules)
    source_family, _ = _family(source or {}, rules)
    subtype, source_subtype = _subtype(record, rules), _subtype(source or {}, rules)
    density_records = [item for item in _items((source or {}).get("Conversions"))
                       if isinstance(item, Mapping) and item.get("Field") == "Volume"
                       and _choice(item.get("Unit"), rules["density_units"]) and _number(item.get("Value"))
                       and item["Value"] > 0]
    material_basis = record.get("density_basis", "product_volume")
    source_basis = (source or {}).get("DensityBasis", "product_volume")
    if not (source or {}).get("Conversions"):
        density = _grade_density(record, source or {}, rules)
        if density is not None:
            density_records = [{"Value": density}]
    inventory_unit = (source or {}).get("InventoryUnit", (source or {}).get("unit"))
    comparable = (source is not None and inventory_unit == "kg" and family is not None
                  and family == source_family and not (subtype and source_subtype and subtype != source_subtype)
                  and material_basis == source_basis and len(density_records) == 1 and _number(actual))
    if not comparable:
        emit("density.not_assessed", "review", path + ".properties.density",
             "No comparable product density on the same material-volume basis is available.",
             actual=actual, assessment="not_assessed",
             expected="Same product family, kg/m3 conversion and volume basis")
        return
    expected = density_records[0]["Value"]
    difference = abs(actual - expected) / expected
    # Small floating error at exactly 20% or 50% must not change the policy band.
    review_limit = policy["density_review_relative_difference"]
    prominent_limit = policy["density_prominent_relative_difference"]
    if difference > review_limit and not math.isclose(difference, review_limit, abs_tol=1e-12):
        high = difference > prominent_limit and not math.isclose(difference, prominent_limit, abs_tol=1e-12)
        emit("density.agreement", "review", path + ".properties.density",
             "Thermal and carbon-source densities differ beyond the project screening tolerance.",
             actual=actual, expected=expected, relative_difference=difference,
             tolerance=review_limit, prominence="high" if high else "normal", unit="kg/m3")


def _check_boverket_modules(record, path, emit):
    known = {}
    for index, item in enumerate(_items(record.get("DataItems"))):
        if not isinstance(item, Mapping) or item.get("PropertyCode") != "GWP-GHG AR4":
            continue
        if item.get("PropertyUnitCode") != "kg CO2 eq./kg":
            emit("carbon.units", "error", f"{path}.DataItems.{index}.PropertyUnitCode",
                 "Boverket GWP-GHG AR4 factors require their declared kg basis.",
                 actual=item.get("PropertyUnitCode"), expected="kg CO2 eq./kg")
        for value in _items(item.get("DataValueItems")):
            if not isinstance(value, Mapping):
                continue
            module, factor = value.get("DataModuleCode"), value.get("Value")
            if not isinstance(module, str):
                emit("carbon.modules", "error", path + ".DataItems", "Carbon module label is missing.")
                continue
            if module in known:
                emit("carbon.modules", "error", path + ".DataItems", "Duplicate carbon module factor.",
                     actual=module)
            if factor is not None and not _number(factor):
                emit("carbon.modules", "error", path + ".DataItems", "Carbon factor must be finite or null.",
                     actual={module: factor})
            known[module] = factor
    missing = []
    if not any(_number(known.get(module)) for module in ("A1-A3 Conservative", "A1-A3 Typical")):
        missing.append("A1A3")
    for module in ("A4", "A5"):
        if not _number(known.get(module)):
            missing.append(module)
    if missing:
        emit("carbon.modules", "missing" if "A1A3" in missing else "review", path + ".DataItems",
             "Base production data is required; other lifecycle modules describe source availability, and the consuming assessment selects required modules. A5.1 is waste only, not full A5.",
             actual=known, expected={"required_base_modules": ["A1A3"], "optional_coverage": ["A4", "A5"],
                                     "assessment_scope_owner": "consuming assessment"},
             known_modules={key: value for key, value in known.items() if _number(value)},
             missing_modules=missing, partial_modules=["A5.1"] if "A5.1" in known else [],
             legacy_embodied_carbon_available=all(_number(known.get(key)) for key in (
                 "A1-A3 Conservative", "A1-A3 Typical", "A4", "A5.1")),
             partial_source_handoff="Use the explicit catalogue for published partial factors; absent legacy fields are not filled.")


def _check_external_carbon(identifier, record, path, emit):
    if record.get("identifier") != identifier:
        emit("carbon.identity", "error", path + ".identifier",
             "External carbon identifier disagrees with its catalogue key.",
             actual=record.get("identifier"), expected=identifier)
    for field in ("name", "url", "method"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            emit("carbon.source", "missing", f"{path}.{field}", "External source metadata is missing.")
    url = record.get("url")
    if isinstance(url, str) and url.strip():
        try:
            location = urlsplit(url)
            valid = location.scheme in {"http", "https"} and bool(location.hostname)
        except ValueError:
            valid = False
        if not valid or any(character.isspace() for character in url):
            emit("carbon.source", "error", path + ".url", "External source needs an HTTP(S) URL.",
                 actual=url)
    proxy_for = record.get("proxy_for")
    if proxy_for is not None and (not isinstance(proxy_for, str) or not proxy_for.strip()):
        emit("carbon.mapping", "error", path + ".proxy_for", "A proxy needs a clear material qualification.",
             actual=proxy_for)
    if not _choice(record.get("unit"), {"kg", "m2", "m3", "item"}):
        emit("carbon.units", "error", path + ".unit", "External factor needs an explicit material unit.",
             actual=record.get("unit"), expected=["kg", "m2", "m3", "item"])
    modules = _mapping(record.get("modules"))
    for module, value in modules.items():
        if not isinstance(module, str) or re.fullmatch(
                r"(?:A1A3|A[1-5]|B[1-7]|C[1-4]|D)(?:\.[1-9]\d*)?", module) is None:
            emit("carbon.modules", "error", path + ".modules", "Unknown lifecycle module label.",
                 actual=module)
        if value is not None and not _number(value):
            emit("carbon.modules", "error", path + ".modules", "Factor must be finite or null.",
                 actual={str(module): value})
    missing = [module for module in ("A1A3", "A4", "A5") if not _number(modules.get(module))]
    if missing:
        emit("carbon.modules", "missing" if "A1A3" in missing else "review", path + ".modules",
             "Base production data is required; undeclared transport/installation modules remain unknown, never zero. The consuming assessment selects its required modules.",
             actual=dict(modules), expected={"required_base_modules": ["A1A3"], "optional_coverage": ["A4", "A5"],
                                            "assessment_scope_owner": "consuming assessment"},
             known_modules={key: value for key, value in modules.items() if _number(value)},
             missing_modules=missing, partial_modules=[key for key in modules if str(key).startswith("A5.")])


def _check_layer(record, path, reference, emit, rules, policy):
    thickness = record.get("thickness")
    if thickness is None:
        emit("layer.geometry", "missing", path + ".thickness", "Layer thickness is missing.")
    elif not _number(thickness) or thickness <= 0:
        emit("layer.geometry", "error", path + ".thickness", "Thickness must be positive finite metres.",
             actual=thickness)
    function = record.get("layer_function")
    if function is not None and not _choice(function, rules["assembly"]["layer_functions"]):
        emit("assembly.metadata", "error", path + ".layer_function", "Unknown layer function.",
             actual=function, expected=rules["assembly"]["layer_functions"])
    shares = record.get("materials")
    if not isinstance(shares, (list, tuple)) or not shares:
        emit("layer.fractions", "missing", path + ".materials", "Layer needs material shares.")
        return
    fractions, all_valid = [], True
    for index, share in enumerate(shares):
        base = f"{path}.materials.{index}"
        if not isinstance(share, Mapping):
            emit("layer.fractions", "error", base, "Material share must be an object.")
            all_valid = False
            continue
        material = reference("materials", share.get("material_id"), base + ".material_id")
        if material is not None and material.get("kind") != "opaque":
            emit("layer.geometry", "error", base + ".material_id", "Layers require opaque materials.")
        fraction, depth = share.get("area_fraction"), share.get("thickness")
        if fraction is None:
            emit("layer.fractions", "missing", base + ".area_fraction", "Area fraction is missing.")
            all_valid = False
        elif not _number(fraction) or not 0 < fraction <= 1:
            emit("layer.fractions", "error", base + ".area_fraction",
                 "Area fraction must be finite and in (0,1].", actual=fraction)
            all_valid = False
        else:
            fractions.append(fraction)
        if depth is None:
            emit("layer.geometry", "missing", base + ".thickness", "Constituent thickness is missing.")
        elif not _number(depth) or depth <= 0:
            emit("layer.geometry", "error", base + ".thickness", "Constituent thickness must be positive metres.",
                 actual=depth)
        elif _number(thickness) and not math.isclose(depth, thickness, rel_tol=rules["geometry"]["parallel_depth_relative_tolerance"],
                                                   abs_tol=rules["geometry"]["parallel_depth_absolute_tolerance"]):
            emit("layer.depth", "error", base + ".thickness",
                 "Unequal parallel depths require a supported explicit thermal-equivalence model.",
                 actual=depth, expected=thickness)
        if material is not None and _number(depth) and depth > 0:
            family, inferred = _family(material, rules)
            bounds = rules["material_families"].get(family)
            if bounds is None:
                emit("layer.buildability", "review", base + ".thickness",
                     "Material family is insufficiently identified to assess plausible product depth.",
                     actual=depth, assessment="not_assessed")
            elif not bounds["minimum_m"] <= depth <= bounds["maximum_m"]:
                emit("layer.buildability", "review", base + ".thickness",
                     "Constituent depth is outside the broad project screening range.",
                     actual=depth, expected={key: bounds[key] for key in ("minimum_m", "maximum_m")},
                     material_family=family, family_inferred=inferred)
            if bounds and bounds.get("prefabricated") and not re.search(
                    rules["nominal_precision"]["explanation_pattern"], " ".join(
                        str(note) for note in _items(record.get("notes"))), re.I):
                mm = depth * 1000
                increment = rules["nominal_precision"]["increment_mm"]
                if not math.isclose(mm / increment, round(mm / increment),
                                    abs_tol=rules["nominal_precision"]["comparison_absolute_tolerance"]):
                    emit("layer.precision", "review", base + ".thickness",
                         "Prefabricated product depth has unexplained precision beyond the nominal-dimension policy.",
                         actual=depth, expected="Plausible nominal dimension or explicit explanation",
                         material_family=family, family_inferred=inferred, increment_mm=increment)
            if family == "air_cavity":
                match = re.search(r"equivalent\s+(\d+(?:\.\d+)?)\s*mm", str(material.get("name", "")), re.I)
                if match and not math.isclose(depth, float(match.group(1)) / 1000, abs_tol=1e-9):
                    emit("layer.depth", "error", base + ".thickness",
                         "Depth-specific equivalent air material is used at another cavity depth.",
                         actual=depth, expected=float(match.group(1)) / 1000)
    if all_valid and not math.isclose(sum(fractions), 1, rel_tol=0, abs_tol=policy["area_fraction_tolerance"]):
        emit("layer.fractions", "error", path + ".materials", "Parallel area fractions must sum to one.",
             actual=sum(fractions), expected=1)
    if len(shares) == 1 and record.get("is_composite") is True:
        emit("layer.geometry", "error", path + ".is_composite", "A composite layer needs multiple material shares.")
    if len(shares) > 1 and record.get("is_composite") is not True:
        emit("layer.geometry", "error", path + ".is_composite", "Multiple shares require composite-layer marking.")


def _same_role(left, right):
    return left == right or (isinstance(left, str) and isinstance(right, str)
                             and left.startswith("EXT_WALL") and right.startswith("EXT_WALL"))


def _check_assembly_metadata(record, path, emit, rules, *, required):
    missing = [field for field in ("assembly_family", "side_convention") if not record.get(field)]
    if required and missing:
        emit("assembly.metadata", "review", path, "Assembly-order plausibility is not assessed without explicit metadata.",
             actual={field: record.get(field) for field in missing}, expected=missing,
             assessment="not_assessed")
    for field, choices in (("assembly_family", rules["assembly"]["families"]), ("side_convention", rules["assembly"]["side_conventions"])):
        value = record.get(field)
        if value is not None and not _choice(value, choices):
            emit("assembly.metadata", "error", f"{path}.{field}", "Unknown assembly metadata value.",
                 actual=value, expected=sorted(choices))


def _check_assembly_order(record, components, layers, path, emit, rules):
    if not _choice(record.get("assembly_family"), rules["assembly"]["families"]) or not _choice(record.get("side_convention"), rules["assembly"]["side_conventions"]):
        return
    stack = []
    for component in components:
        slots = [slot for slot in _items(component.get("layers")) if isinstance(slot, Mapping)
                 and _number(slot.get("position"))]
        for slot in sorted(slots, key=lambda item: item["position"]):
            layer = layers.get(slot.get("layer_id"), {}) if isinstance(slot.get("layer_id"), str) else {}
            stack.append(slot.get("layer_function", layer.get("layer_function")))
    if record.get("side_convention") in rules["assembly"]["reverse_conventions"]:
        stack.reverse()
    if not stack or any(function is None for function in stack):
        emit("assembly.metadata", "review", path,
             "Assembly order includes layers without declared functions; review cannot be completed.",
             actual=stack, expected="Declared layer_function for the complete element stack",
             assessment="not_assessed")
    weather = [index for index, function in enumerate(stack) if _choice(function, rules["assembly"]["weather_functions"])]
    linings = [index for index, function in enumerate(stack) if function == "lining"]
    if weather and linings and max(weather) > min(linings):
        emit("assembly.order", "review", path,
             "Weather protection lies inside an internal lining in the declared assembly order.",
             actual=stack, expected="Weather/ground side to occupied side")
    insulation = [index for index, function in enumerate(stack) if function == "insulation"]
    vapour = [index for index, function in enumerate(stack) if function == "vapour_control"]
    if _choice(record.get("assembly_family"), rules["assembly"]["warm_side_vapour_families"]) and insulation and vapour:
        if min(vapour) < max(insulation):
            emit("assembly.order", "review", path,
                 "Vapour-control placement needs moisture review for the declared insulated assembly.",
                 actual=stack, expected="Explain vapour control on the cold side of insulation")
