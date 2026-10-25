"""Reference-only material authoring resolves checked cached records into physics."""

import hashlib
import json
from importlib.resources import files

import pytest

from epsm_data import (
    BuildingElement,
    Catalogue,
    SourceCache,
    archetype_from_dict,
    archetype_to_dict,
)


def test_catalogue_stores_names_and_references_instead_of_copied_properties():
    catalogue = Catalogue.load()
    raw = catalogue.to_dict()
    assert raw["schema_version"] == 2
    assert not {"honeybee", "boverket", "carbon_references"} & raw.keys()
    for identifier, mapping in catalogue.material_mappings.items():
        assert mapping["epsm_material_name"] == catalogue.material_records[identifier]["name"]
        assert not {"properties", "name", "honeybee_id", "boverket_id"} & mapping.keys()
        assert mapping["thermal_ref"]["source"] in catalogue.source_versions
    assert Catalogue(raw).resolved_dict() == catalogue.resolved_dict()


def test_linked_views_keep_exact_cached_thermal_records():
    catalogue, cache = Catalogue.load(), SourceCache.load()
    linked_records = catalogue.resolved_dict()["honeybee"]
    refs = [material["thermal_ref"] for material in catalogue.material_mappings.values()]
    assert {ref["source"] for ref in refs} == {"epsm-custom"}
    for ref in refs:
        # Inspection links retain exact source records instead of rebuilding fields.
        assert linked_records[ref["identifier"]] == cache.records(ref["source"])[ref["identifier"]]
    assert {ref["identifier"] for ref in refs} == set(cache.records("epsm-custom"))
    assert len(catalogue.boverket_resources) == 22
    assert len(cache.records("boverket")) == 230


def test_complete_upstream_files_retain_their_original_bytes():
    source_dir = files("epsm_data.datasets.sources")
    # Anchored to the complete official versioned Boverket response.
    assert hashlib.sha256(source_dir.joinpath("boverket.json").read_bytes()).hexdigest() == (
        "8894acdfc1c4a45730b77af7f65caacdb8f75a9b851c4af6e74f4583ea030d2c")


def test_thermal_sources_carry_no_external_simulation_library():
    cache = SourceCache.load()
    assert {source["kind"] for source in cache.manifest["sources"].values()} == {
        "boverket", "epsm_authored", "carbon_reference"}
    assert not any(name.startswith(("honeybee", "LICENSE-honeybee"))
                   for name in (p.name for p in files("epsm_data.datasets.sources").iterdir()))
    for record in cache.records("epsm-custom").values():
        assert record["user_data"]["provenance"]["sources"], record["identifier"]


def test_incompatible_source_pin_and_duplicate_properties_are_rejected():
    raw = Catalogue.load().to_dict()
    raw["source_versions"]["boverket"] = "00.00.000"
    with pytest.raises(ValueError, match="Source release mismatch"):
        Catalogue(raw)
    raw = Catalogue.load().to_dict()
    next(iter(raw["materials"].values()))["properties"] = {"conductivity": 1}
    with pytest.raises(ValueError, match="without copied properties"):
        Catalogue(raw)


def test_custom_cache_changes_resolved_physics_without_repeating_properties(tmp_path):
    baseline = Catalogue.load()
    raw, cache = baseline.to_dict(), SourceCache.load()
    manifest = cache.manifest
    material_id = next(mid for mid, item in raw["materials"].items()
                       if item["thermal_ref"]["identifier"] == "EPSM_tabula_facing_brick_lambda060")
    source_id = raw["materials"][material_id]["thermal_ref"]["source"]
    record_id = raw["materials"][material_id]["thermal_ref"]["identifier"]
    expected = baseline.materials[material_id].conductivity * 1.1
    for sid, source in manifest["sources"].items():
        # Preserve each source's original container, including root metadata/lists.
        records = json.loads(files("epsm_data.datasets.sources").joinpath(
            source["records_path"]).read_text())
        if sid == source_id:
            source["release"] = "custom-thermal-v1"
            raw["source_versions"][sid] = source["release"]
            assert source.get("format", "id_map") == "id_map"
            records[record_id]["conductivity"] = expected
        path = tmp_path / source["records_path"]
        path.write_text(json.dumps(records))
        source["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "catalogue.json").write_text(json.dumps(raw))
    custom = Catalogue.load(tmp_path / "catalogue.json", source_cache=tmp_path)
    assert custom.materials[material_id].name == baseline.materials[material_id].name
    assert custom.materials[material_id].conductivity == expected
    def wall(catalogue):
        return catalogue.get("office_se01").construction_set.elements[BuildingElement.EXT_WALL].u_value

    assert wall(custom) > wall(baseline)
    assert Catalogue.load().materials[material_id].conductivity != expected


def test_saved_archetype_restores_without_a_source_cache(monkeypatch):
    original = Catalogue.load().get("office_se01")
    saved = json.loads(json.dumps(archetype_to_dict(original)))

    def denied(*args, **kwargs):
        pytest.fail("A saved resolved archetype must not fetch its source cache")

    monkeypatch.setattr(SourceCache, "load", denied)
    assert archetype_from_dict(saved) == original


def test_source_cli_checks_offline_and_reports_upstream_updates(monkeypatch, capsys):
    from epsm_data import source_cache
    from epsm_data.cli import main

    def denied(*args, **kwargs):
        pytest.fail("Default source verification must remain offline")

    monkeypatch.setattr(source_cache, "_fetch_upstream", denied)
    assert main(["--check-sources", "--check"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "verified"
    monkeypatch.setattr(source_cache, "_fetch_upstream", lambda *args: "99.0.0")
    assert main(["--check-sources", "--online", "--check"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "updates_available"
    assert report["sources"]["boverket"]["pinned_release"] == "02.07.000"
    assert Catalogue.load().source_versions["boverket"] == "02.07.000"
