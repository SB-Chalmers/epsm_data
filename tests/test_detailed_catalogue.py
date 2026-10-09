"""Shared authoring registries and explicit, portable caveat management."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from epsm_data import load_calibrated_archetype, load_detailed_catalogue


def save(path, data):
    for name, record in data.items():
        (path / f"{name}.json").write_text(json.dumps(record), encoding="utf-8")


def test_registry_counts_references_and_defensive_export():
    catalogue = load_detailed_catalogue()
    summary = catalogue.summary()
    assert {key: summary[key] for key in ("materials", "assemblies", "archetypes", "states")} == {
        "materials": 207, "assemblies": 1606, "archetypes": 32, "states": 92,
    }
    assert summary["open_caveats"] > 0
    materials = catalogue.materials
    materials["cellular_plastic"]["honeybee_id"] = "changed"
    assert catalogue.materials["cellular_plastic"]["honeybee_id"] == "EPSM_cellular_plastic"
    honeybee = catalogue.honeybee_materials
    honeybee["EPSM_cellular_plastic"]["conductivity"] = 999
    assert catalogue.resolve_material("cellular_plastic")["properties"]["conductivity"] == 0.037
    data = catalogue.to_dict()
    data["archetypes"]["archetypes"]["mf_se02"]["notes"].append("external edit")
    assert "external edit" not in catalogue.archetypes["mf_se02"]["notes"]


@pytest.mark.parametrize("state,expected", [
    ("existing", [0.20021817118979393, 0.41441970429638514, 0.27057641121748016, 3.1091724942987744]),
    ("standard", [0.11674087174636628, 0.2363398801866083, 0.27057641121748016, 3.1091724942987744]),
    ("advanced", [0.0966025415448334, 0.11801333420640135, 0.27057641121748016, 3.1091724942987744]),
])
def test_reviewed_recipes_preserve_expected_calibrated_results(state, expected):
    result = load_calibrated_archetype(renovation_state=state)
    rows = result.report["elements"]
    for prop, value in zip(("roof", "external_wall", "ground_floor", "basement_wall"), expected, strict=True):
        assert rows[prop]["assembly_u"] == pytest.approx(value, rel=1e-12)
    assert rows["internal_wall"]["assembly_u"] == pytest.approx(0.5738830644143139, rel=1e-12)
    assert rows["intermediate_floor"]["assembly_u"] == pytest.approx(1.8217057061790272, rel=1e-12)
    assert result.report["nominal_calibration_complete"]


def test_material_links_do_not_duplicate_source_properties():
    data = load_detailed_catalogue().to_dict()

    def check(record):
        if isinstance(record, dict):
            assert not {"conductivity", "density", "specific_heat", "embodied_carbon", "properties"} & set(record)
            for value in record.values():
                check(value)
        elif isinstance(record, list):
            for value in record:
                check(value)

    # Mapping annotations can name properties, but cannot carry numeric data.
    for record in data["materials"]["materials"].values():
        check(record)
        assert record["honeybee_id"] in data["honeybee"]["materials"]
    check(data["assemblies"])
    check(data["archetypes"])
    for archetype in data["archetypes"]["archetypes"].values():
        for state in ("standard", "advanced"):
            if state not in archetype["states"]:
                continue
            if "operations" in archetype["states"][state]:
                assert archetype["states"][state]["base_state"] == "existing"
                assert all("assembly_id" in op and "layers" not in op
                           for op in archetype["states"][state]["operations"])
            else:
                assert "assemblies" in archetype["states"][state]


def test_one_material_edit_recalculates_every_dependent_state(detailed_copy):
    path, data = detailed_copy
    original = {state: load_calibrated_archetype(renovation_state=state)
                for state in ("existing", "standard", "advanced")}
    data["honeybee"]["materials"]["EPSM_cellular_plastic"]["conductivity"] = 0.038
    save(path, data)
    uuids = set()
    for state in original:
        changed = load_calibrated_archetype(path, renovation_state=state)
        assert changed.report["elements"]["ground_floor"]["assembly_u"] > original[state].report["elements"]["ground_floor"]["assembly_u"]
        assert changed.report["elements"]["roof"]["assembly_u"] == original[state].report["elements"]["roof"]["assembly_u"]
        assert changed.report["elements"]["ground_floor"]["target_u"] == original[state].report["elements"]["ground_floor"]["target_u"]
        assert changed.report["target_drift"] == []
        for element in changed.archetype.construction_set.elements.values():
            if hasattr(element, "components"):
                for component in element.components:
                    for layer in component.layers:
                        for slot in layer.layer.materials:
                            if slot.material.json_id.endswith(":cellular_plastic"):
                                uuids.add(slot.material.uuid)
    assert len(uuids) == 1




def test_annotations_at_layer_assembly_archetype_and_state(detailed_copy):
    path, data = detailed_copy
    assembly = data["assemblies"]["assemblies"][data["archetypes"]["archetypes"]["mf_se02"]["states"]["existing"]["assemblies"]["EXT_WALL"]]
    assembly["components"][0]["layers"][0]["notes"].append("Layer-specific review note.")
    state = data["archetypes"]["archetypes"]["mf_se02"]["states"]["existing"]
    state["caveats"].append({"id": "new_review", "status": "open", "severity": "warning",
                             "topic": "provenance", "note": "Verify drawing variant.", "resolution": None})
    save(path, data)
    report = load_calibrated_archetype(path).report
    assert any(item["owner_type"] == "layer" and "Layer-specific review note." in item["notes"]
               for item in report["record_annotations"])
    assert any(c["owner_type"] == "state" and c["id"] == "new_review" for c in report["open_caveats"])


@pytest.mark.parametrize("mutation", [
    "notes_string", "invalid_status", "invalid_severity", "resolved_without_resolution",
    "duplicate_caveat_id", "dangling_caveat_source", "missing_explanation", "missing_resolution_text",
    "bad_source", "dangling_assembly", "dangling_material", "wrong_role", "compound_state",
    "zero_u", "negative_ach", "bad_target_unit", "bad_target_curve", "missing_property",
])
def test_invalid_registry_or_caveat_rejected(detailed_copy, mutation):
    path, data = detailed_copy
    material = data["materials"]["materials"]["perimeter_xps300"]
    caveat = material["caveats"][0]
    state = data["archetypes"]["archetypes"]["mf_se02"]["states"]["advanced"]
    if mutation == "notes_string":
        material["notes"] = "not a list"
    elif mutation == "invalid_status":
        caveat["status"] = "maybe"
    elif mutation == "invalid_severity":
        caveat["severity"] = "huge"
    elif mutation == "resolved_without_resolution":
        caveat["status"] = "resolved"
        caveat["resolution"] = None
    elif mutation == "duplicate_caveat_id":
        material["caveats"].append(caveat)
    elif mutation == "dangling_caveat_source":
        caveat["source"] = "unknown"
    elif mutation == "missing_explanation":
        caveat["note"] = ""
    elif mutation == "missing_resolution_text":
        caveat["resolution"] = " "
    elif mutation == "bad_source":
        data["materials"]["sources"]["boverket_02_07"] = None
    elif mutation == "dangling_assembly":
        state["assemblies"]["TOP_FLOOR"] = "unknown"
    elif mutation == "dangling_material":
        data["assemblies"]["assemblies"]["mf_se02_advanced_top_floor"]["components"][0]["layers"][0]["material_id"] = "unknown"
    elif mutation == "wrong_role":
        state["assemblies"]["TOP_FLOOR"] = state["assemblies"]["EXT_WALL"]
    elif mutation == "compound_state":
        state["base_state"] = "standard"
    elif mutation == "zero_u":
        state["target_snapshot"]["roof"]["value"] = 0
    elif mutation == "negative_ach":
        state["target_snapshot"]["infiltration"]["value"] = -1
    elif mutation == "bad_target_unit":
        state["target_snapshot"]["roof"]["unit"] = "mm"
    elif mutation == "bad_target_curve":
        state["target_snapshot"]["roof"]["curve"] = "unknown"
    elif mutation == "missing_property":
        del state["target_snapshot"]["roof"]
    save(path, data)
    with pytest.raises(ValueError):
        load_detailed_catalogue(path)


def test_duplicate_json_ids_not_silently_discarded(detailed_copy):
    path, _ = detailed_copy
    file = path / "materials.json"
    file.write_text(file.read_text().replace('"format_version": 2,', '"format_version": 2, "format_version": 2,', 1))
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        load_detailed_catalogue(path)


def test_active_loader_never_reads_evidence_or_archived_definitions(monkeypatch):
    original = Path.open

    def checked_open(path, *args, **kwargs):
        assert "ARCHIVE" not in path.parts and "evidence" not in path.parts
        assert path.name not in {"mf_se02_existing.json", "mf_se02_renovations.json"}
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked_open)
    for state in ("existing", "standard", "advanced"):
        assert not load_calibrated_archetype(renovation_state=state).report["target_drift"]


def test_directory_or_any_registry_file_and_cli(detailed_copy):
    path, _ = detailed_copy
    expected = load_detailed_catalogue(path).to_dict()
    for name in ("materials", "assemblies", "archetypes", "honeybee", "boverket"):
        assert load_detailed_catalogue(path / f"{name}.json").to_dict() == expected
    result = subprocess.run([sys.executable, "-m", "epsm_data.detailed", "--path", str(path),
                             "--check", "--summary"], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["materials"] == 207
    assert not result.stderr
    result = subprocess.run([sys.executable, "-m", "epsm_data.detailed", "--caveats", "--state", "advanced", "--path", "src/epsm_data/datasets/layered"],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == load_detailed_catalogue().caveats(state="advanced")


@pytest.mark.parametrize("mutation", [
    "embedded_properties", "embedded_conductivity", "dangling_honeybee", "dangling_boverket",
    "source_identifier", "duplicate_boverket", "boverket_version", "carbon_unit",
    "duplicate_carbon_module", "invalid_prototype",
])
def test_invalid_material_link_or_source_rejected(detailed_copy, mutation):
    path, data = detailed_copy
    link = data["materials"]["materials"]["cellular_plastic"]
    hb = data["honeybee"]["materials"][link["honeybee_id"]]
    resource = next(r for r in data["boverket"]["Resources"] if str(r["ResourceId"]) == link["boverket_id"])
    if mutation == "embedded_properties":
        link["properties"] = {"conductivity": 0.037}
    elif mutation == "embedded_conductivity":
        link["conductivity"] = 0.037
    elif mutation == "dangling_honeybee":
        link["honeybee_id"] = "not_registered"
    elif mutation == "dangling_boverket":
        link["boverket_id"] = "not_registered"
    elif mutation == "source_identifier":
        hb["identifier"] = "different_id"
    elif mutation == "duplicate_boverket":
        data["boverket"]["Resources"].append(resource)
    elif mutation == "boverket_version":
        resource["SourceVersion"] = "not_the_snapshot_version"
    elif mutation == "carbon_unit":
        resource["DataItems"][0]["PropertyUnitCode"] = "kg CO2 eq./m²"
    elif mutation == "duplicate_carbon_module":
        values = resource["DataItems"][0]["DataValueItems"]
        values.append(values[0])
    elif mutation == "invalid_prototype":
        hb["thickness"] = 0
    save(path, data)
    with pytest.raises(ValueError):
        load_detailed_catalogue(path)


def test_boverket_source_resolves_carbon_without_changing_thermal_properties(detailed_copy):
    path, data = detailed_copy
    original = load_calibrated_archetype(path)
    link = data["materials"]["materials"]["cellular_plastic"]
    resource = next(r for r in data["boverket"]["Resources"] if str(r["ResourceId"]) == link["boverket_id"])
    values = resource["DataItems"][0]["DataValueItems"]
    next(v for v in values if v["DataModuleCode"] == "A1-A3 Conservative")["Value"] = 4.1
    save(path, data)
    catalogue = load_detailed_catalogue(path)
    assert "properties" not in catalogue.materials["cellular_plastic"]
    resolved = catalogue.resolve_material("cellular_plastic")["properties"]
    assert resolved["embodied_carbon"]["A1_A3_conservative"] == 4.1
    assert resolved["embodied_carbon"]["conversion_factor"] is None
    assert resolved["conductivity"] == 0.037
    changed = load_calibrated_archetype(path)
    assert changed.report["revision"] != original.report["revision"]
    for prop in original.report["elements"]:
        assert changed.report["elements"][prop]["assembly_u"] == original.report["elements"][prop]["assembly_u"]
    assert load_calibrated_archetype(path, renovation_state="standard").report["revision"] != load_calibrated_archetype(renovation_state="standard").report["revision"]


def test_candidate_boverket_resource_is_not_an_accepted_mapping():
    catalogue = load_detailed_catalogue()
    link = catalogue.materials["woodfiber_board"]
    assert link["candidate_boverket_id"] in catalogue.boverket_resources
    assert link["mapping_status"] == "reviewed_proxy"
    assert link["boverket_id"] == "6000000216"
    assert link["boverket_id"] != link["candidate_boverket_id"]


def test_lod2_recipe_coverage_is_separate_from_acceptance_and_material_registration():
    catalogue = load_detailed_catalogue()
    report = catalogue.lod2_completeness()
    assert report == catalogue.lod2_completeness()
    assert (report["total_slots"], report["slots_with_layer_recipe"], report["slots_without_layer_recipe"]) == (1080, 1080, 0)
    assert report["lod2_complete_slots"] == 1080
    assert report["lod2_complete_states"] == 90
    variants = {r["archetype_id"]: r for r in report["states"] if r["archetype_id"] in {"mf_1940", "mf_1950"}}
    assert variants["mf_1940"]["slots_with_recipe"] == 12
    assert variants["mf_1950"]["slots_with_recipe"] == 0
    assert variants["mf_1940"]["lod2_complete"]
    assert not variants["mf_1950"]["lod2_complete"]
    assert len(report["detailed_revision"]) == len(report["catalogue_revision"]) == 64
    mf_states = [r for r in report["states"] if r["archetype_id"] == "mf_se02"]
    for row in mf_states:
        assert row["slots_with_recipe"] == 12
        assert row["materials_used"] == row["materials_with_both_references"]
        assert all(row["checks"].values())
        assert row["lod2_complete"]
        assert not row["readiness"]["ground_validation"]
        assert not row["readiness"]["simulation"]
        assert not row["readiness"]["carbon_assessment"]
        assert row["readiness"]["honeybee_nominal_export"]
        assert row["readiness"]["core_nominal_export"]
        assert not row["pending_boverket_references"]
        assert len(row["slot_checks"]) == 12
        assert row["accepted_evidence"]
        if row["state"] != "existing":
            assert not any(c["owner_id"] == "window_existing" for c in row["open_caveats"])




def test_lod2_check_uses_supplied_catalogue_and_in_memory_registries(detailed_copy):
    from epsm_data import load_parametric_catalogue

    path, data = detailed_copy
    data["honeybee"]["materials"]["EPSM_cellular_plastic"]["conductivity"] = 0.038
    save(path, data)
    edited = load_detailed_catalogue(path)
    report = edited.lod2_completeness()
    # Ground conductivity changes nominal ground U without fitting effective targets.
    original = load_calibrated_archetype()
    changed = load_calibrated_archetype(path)
    assert changed.report["elements"]["ground_floor"]["assembly_u"] != original.report["elements"]["ground_floor"]["assembly_u"]
    assert report["detailed_revision"] != load_detailed_catalogue().lod2_completeness()["detailed_revision"]
    parametric = load_parametric_catalogue().with_anchor(
        "multi_family", "internal_wall",
        {"value": 0.65, "era": "SE.02", "state": "existing",
         "source": "cmf_1960_1_internal", "note": "Future evidence replacement"},
    )
    drift = load_detailed_catalogue().lod2_completeness(catalogue=parametric)
    assert all(not r["checks"]["nominal_u_alignment"] for r in drift["states"] if r["archetype_id"] == "mf_se02")
    assert next(r for r in drift["states"] if r["archetype_id"] == "office_se05")["lod2_complete"]


def test_lod2_cli_compact_summary():
    result = subprocess.run([sys.executable, "-m", "epsm_data.detailed", "--lod2", "--summary",
                             "--catalogue", "src/epsm_data/datasets/parametric/catalogue.json", "--path", "src/epsm_data/datasets/layered"],
                            capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report["slots_with_layer_recipe"] == 1080
    assert report["lod2_complete_slots"] == 1080
    assert all("blocking_caveats" not in r and "remaining" in r for r in report["states"])










def test_source_definitions_are_native_honeybee_materials_when_installed():
    dictutil = pytest.importorskip("honeybee_energy.material.dictutil")
    catalogue = load_detailed_catalogue()
    for hid, record in catalogue.honeybee_materials.items():
        material = dictutil.dict_to_material(record)
        assert material.identifier == hid
        if record["type"] == "EnergyMaterial":
            assert material.conductivity == record["conductivity"]
            assert material.thickness == record["thickness"]
        else:
            assert material.u_factor == record["u_factor"]
