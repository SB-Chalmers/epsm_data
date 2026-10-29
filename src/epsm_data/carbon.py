"""Narrow missing-carbon scope for provably retained catalogue stock.

This authoring assessment never supplies factors or changes LCA accounting.
Only complete, shared baseline component occurrences qualify. Additions,
relocation and changes to a containing component require an actual carbon source.
"""

from collections.abc import Mapping

STATUS = "retained_existing_unmapped"


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _configuration(data, config, material_id):
    """Read component identities per role; unresolved definitions cannot qualify."""
    assignments = dict(data["construction_sets"][config["construction_set_id"]]["elements"])
    if not assignments:
        raise ValueError("Construction-set assignments are unavailable")
    if config.get("weather_shell_element_id") is not None:
        assignments["WEATHER_SHELL"] = config["weather_shell_element_id"]
    components, occurrences = {}, {}
    for role, element_id in assignments.items():
        element = data["elements"][element_id]
        if element.get("role") == "WINDOW":
            if element.get("window_material_id") == material_id:
                raise ValueError("Whole-window stock exemptions are unsupported")
            continue
        children = element["components"]
        if not isinstance(children, (list, tuple)) or not children:
            raise ValueError("An opaque element has no ordered component definitions")
        hits = []
        for cid in children:
            slots = data["components"][cid]["layers"]
            if not slots:
                raise ValueError("A component has no material layers")
            if any(share["material_id"] == material_id
                   for slot in slots
                   for share in data["layers"][slot["layer_id"]]["materials"]):
                hits.append(cid)
        components[role] = tuple(children)
        if hits:
            occurrences[role] = tuple(hits)
    return components, occurrences


def _subsequence(baseline, current):
    position = 0
    for identifier in current:
        if position < len(baseline) and baseline[position] == identifier:
            position += 1
    return position == len(baseline)


def retained_stock_assessments(data):
    """Assess declarations defensively; an unproven claim never waives a source.

    Reusing the same ordered baseline component records proves unchanged layer
    depths, fractions and materials within one catalogue. Other baseline
    components must remain in sequence around them; insertions of sourced new
    products are allowed. Every family/state using the material is checked,
    including the separate weather shell. Unused definitions do not qualify.
    """
    data = _mapping(data)
    results = {}
    for mid, material in _mapping(data.get("materials")).items():
        material = _mapping(material)
        if "carbon_assessment" not in material:
            continue
        declaration = _mapping(material.get("carbon_assessment"))
        reason = declaration.get("reason")
        result = {"eligible": False, "reason": reason, "issue": None, "archetypes": ()}
        results[mid] = result
        if declaration.get("status") != STATUS or not isinstance(reason, str) or not reason.strip():
            result["issue"] = "Retained-stock assessment requires its supported status and a nonempty reason"
            continue
        if (material.get("kind") != "opaque" or material.get("non_product") is True
                or any(material.get(field) is not None for field in
                       ("boverket_id", "carbon_reference_id", "embodied_carbon"))):
            result["issue"] = "Retained unmapped stock must be an opaque product without assigned carbon factors or another exemption"
            continue
        users = []
        try:
            archetypes = _mapping(data.get("archetypes"))
            if not archetypes:
                raise ValueError("No authored baseline configurations prove retained stock")
            for aid, archetype in archetypes.items():
                states = _mapping(_mapping(archetype).get("states"))
                inspected = {state: _configuration(data, config, mid)
                             for state, config in states.items()}
                if not any(hits for _, hits in inspected.values()):
                    continue
                base = "existing" if "existing" in states else "default"
                if base not in states or (base == "default" and set(states) != {"default"}):
                    raise ValueError(f"{aid}: material use has no unambiguous original baseline")
                baseline, original_hits = inspected[base]
                if not original_hits:
                    raise ValueError(f"{aid}: material is newly introduced after the baseline")
                for state, (components, hits) in inspected.items():
                    if hits != original_hits:
                        raise ValueError(f"{aid}/{state}: material roles, amounts or containing components changed")
                    for role in original_hits:
                        if not _subsequence(baseline[role], components.get(role, ())):
                            raise ValueError(f"{aid}/{state}: baseline components were changed or relocated")
                users.append(aid)
            if not users:
                raise ValueError("Unused material has no verified existing-stock occurrences")
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            result["issue"] = str(exc)
            continue
        result.update(eligible=True, archetypes=tuple(sorted(users)))
    return results
