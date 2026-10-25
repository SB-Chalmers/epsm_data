"""Reviewed SF SE.02 assembly metadata and contextual shared-layer functions."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from epsm_data import Catalogue, load_sanity_fixture
from epsm_data.sanity_physics import check_physics

FIXTURE = Path(__file__).parent / "fixtures/catalogue_sanity"
CASE = json.loads((FIXTURE / "cases/sf_se02_assembly_metadata.json").read_text())


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture(scope="module")
def payload(catalogue):
    return catalogue.resolved_dict()


@pytest.fixture(scope="module")
def report(catalogue):
    return catalogue.sanity_report(fixture=FIXTURE)


def _raw_findings(payload):
    findings = []

    def emit(rule_id, severity, path, message, **details):
        findings.append(dict(rule_id=rule_id, severity=severity, path=path,
                             message=message, **details))

    check_physics(payload, emit, load_sanity_fixture(FIXTURE))
    return findings


def _physical(section, record):
    if section == "layers":
        return {key: record.get(key, False if key == "is_composite" else None)
                for key in ("thickness", "materials", "is_composite")}
    if section == "components":
        return {
            "application": record["application"], "shearing_layer": record["shearing_layer"],
            "layers": sorted([
                {key: value for key, value in slot.items() if key != "layer_function"}
                for slot in record["layers"]
            ], key=lambda slot: slot["position"]),
        }
    return {key: record.get(key) for key in ("role", "components", "window_material_id")}


def _users(rows):
    return {(row["archetype_id"], row["state"], tuple(row["climate_zones"])) for row in rows}


def test_reviewed_global_and_occurrence_functions_are_explicit_and_supported(payload):
    choices = load_sanity_fixture(FIXTURE)["construction_rules"]["assembly"]
    for lid, function in CASE["global_layer_functions"].items():
        assert function in choices["layer_functions"]
        assert payload["layers"][lid]["layer_function"] == function
    for expected in CASE["slot_functions"]:
        slot = payload["components"][expected["component_id"]]["layers"][expected["slot_index"]]
        assert slot["layer_id"] == expected["layer_id"]
        assert slot["layer_function"] == expected["layer_function"]
        assert slot["layer_function"] in choices["layer_functions"]
    assert payload["layers"][CASE["shared_layer_without_global_function"]].get("layer_function") is None
    for eid, expected in CASE["element_metadata"].items():
        actual = payload["elements"][eid]
        for key, value in expected.items():
            assert actual[key] == value
        assert actual["side_convention_note"] == CASE["side_convention_notes"][eid]


@pytest.mark.parametrize("state", ("existing", "standard", "advanced"))
def test_all_represented_sf02_opaque_stacks_have_functions_without_assembly_contradictions(
    payload, report, state,
):
    config = payload["archetypes"]["sf_se02"]["states"][state]
    elements = payload["construction_sets"][config["construction_set_id"]]["elements"]
    ids = [elements[role] for role in CASE["sf02_opaque_roles"]]
    ids.append(config["weather_shell_element_id"])
    for eid in ids:
        element = payload["elements"][eid]
        assert element.get("assembly_family") and element.get("side_convention")
        for cid in element["components"]:
            for slot in payload["components"][cid]["layers"]:
                function = slot.get("layer_function", payload["layers"][slot["layer_id"]].get("layer_function"))
                assert function is not None
    affected = [row for row in report["findings"] if any(
        user["archetype_id"] == "sf_se02" and user["state"] == state
        for user in row["affected_archetypes"]
    )]
    assert not [row for row in affected if row["rule_id"].startswith("assembly.")]


def test_metadata_assignments_preserve_shared_physical_definitions(payload):
    for section, records in CASE["physical_guards"].items():
        for identifier, expected in records.items():
            assert _physical(section, payload[section][identifier]) == expected


@pytest.mark.parametrize("probe", CASE["propagation_cases"], ids=lambda row: row["identifier"])
def test_shared_metadata_findings_identify_every_affected_archetype(payload, probe):
    raw = deepcopy(payload)
    record = raw[probe["section"]][probe["identifier"]]
    keys = probe["field_path"].split(".")
    target = record
    for key in keys[:-1]:
        target = target[int(key)] if isinstance(target, list) else target[key]
    if probe["mutation"] == "remove":
        del target[keys[-1]]
    else:
        target[keys[-1]] = "unknown_function_for_regression"
    changed = Catalogue(raw).sanity_report(fixture=FIXTURE)
    path = f"{probe['section']}.{probe['identifier']}"
    if probe["mutation"] != "remove":
        path += "." + probe["field_path"]
    finding = next(row for row in changed["findings"] if row["rule_id"] == probe["rule_id"]
                   and row["path"] == path)
    assert finding["severity"] == probe["severity"]
    assert _users(finding["affected_archetypes"]) == _users(probe["expected_affected_archetypes"])
    assert finding["generic_fallback_affected"] == probe["generic_fallback_affected"]


def test_occurrence_functions_complete_an_unlabelled_shared_layer_without_mutating_it():
    raw = deepcopy(CASE["slot_override_unit_assembly"])
    del raw["layers"]["board"]["layer_function"]
    raw["components"]["panel"]["layers"][0]["layer_function"] = "weather_protection"
    raw["components"]["panel"]["layers"][1]["layer_function"] = "lining"
    before = deepcopy(raw)
    findings = _raw_findings(raw)
    assert not [row for row in findings if row["rule_id"].startswith("assembly.")]
    assert raw == before


@pytest.mark.parametrize("invalid", (None, "unknown", [], {"function": "lining"}))
def test_invalid_slot_functions_are_errors_even_with_a_valid_global_default(invalid):
    raw = deepcopy(CASE["slot_override_unit_assembly"])
    raw["components"]["panel"]["layers"][1]["layer_function"] = invalid
    finding = next(row for row in _raw_findings(raw)
                   if row["rule_id"] == "assembly.metadata"
                   and row["path"] == "components.panel.layers.1.layer_function")
    assert finding["severity"] == "error"
    assert finding["actual"] == invalid


def test_occurrence_functions_take_precedence_and_order_checks_cross_component_interfaces():
    raw = deepcopy(CASE["slot_override_unit_assembly"])
    raw["layers"]["board"]["layer_function"] = "lining"
    raw["components"]["panel"]["layers"] = [
        {"layer_id": "board", "position": 0, "layer_function": "weather_protection"},
    ]
    raw["components"]["inner"] = {
        "name": "Inner lining", "application": "EXT_WALL", "shearing_layer": "Space",
        "layers": [{"layer_id": "board", "position": 0, "layer_function": "lining"}],
    }
    raw["elements"]["wall"]["components"].append("inner")
    assert not [row for row in _raw_findings(raw) if row["rule_id"] == "assembly.order"]
    raw["components"]["panel"]["layers"][0]["layer_function"] = "lining"
    raw["components"]["inner"]["layers"][0]["layer_function"] = "weather_protection"
    finding = next(row for row in _raw_findings(raw) if row["rule_id"] == "assembly.order")
    assert finding["actual"] == ["lining", "weather_protection"]
    raw["elements"]["wall"]["side_convention"] = "inside_to_outside"
    assert not [row for row in _raw_findings(raw) if row["rule_id"] == "assembly.order"]


def test_slot_functions_cannot_hide_duplicate_physical_components(payload):
    raw = deepcopy(CASE["slot_override_unit_assembly"])
    raw["components"]["duplicate"] = deepcopy(raw["components"]["panel"])
    raw["components"]["duplicate"]["layers"].reverse()
    raw["components"]["duplicate"]["layers"][0]["layer_function"] = "weather_protection"
    assert any(row["rule_id"] == "definition.duplicate" and row["path"] == "components.duplicate"
               for row in _raw_findings(raw))
    actual = deepcopy(payload)
    cid = CASE["slot_functions"][0]["component_id"]
    actual["components"]["component:metadata_only_duplicate"] = deepcopy(actual["components"][cid])
    actual["components"]["component:metadata_only_duplicate"]["layers"][0]["layer_function"] = "weather_protection"
    with pytest.raises(ValueError, match="Duplicate component definitions"):
        Catalogue(actual)


def test_only_layer_function_is_excluded_from_component_physical_identity():
    raw = deepcopy(CASE["slot_override_unit_assembly"])
    raw["components"]["panel"]["layers"][0]["physical_offset_m"] = 0.01
    raw["components"]["other"] = deepcopy(raw["components"]["panel"])
    raw["components"]["other"]["layers"][0]["physical_offset_m"] = 0.02
    raw["components"]["other"]["layers"][0]["layer_function"] = "lining"
    assert not [row for row in _raw_findings(raw) if row["rule_id"] == "definition.duplicate"]
