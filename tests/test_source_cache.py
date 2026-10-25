"""Pinned source snapshots load offline and explicit checks never change them."""

import json
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from http.client import IncompleteRead

import pytest

from epsm_data import source_cache
from epsm_data.source_cache import SourceCache

_PYPI = {
    "kind": "pypi",
    "url": "https://pypi.org/pypi/honeybee-standards/json",
}
_BOVERKET = {
    "kind": "boverket_page",
    "url": "https://www.boverket.se/sv/om-boverket/oppna-data/boverkets-klimatdatabas/",
}


def _write_cache(tmp_path, *, records=None, source=None, raw=None):
    records = records if records is not None else {"Example": {"identifier": "Example", "density": 100}}
    raw = json.dumps(records).encode() if raw is None else raw
    (tmp_path / "records.json").write_bytes(raw)
    definition = {
        "release": "2.0.7", "records_path": "records.json",
        "sha256": sha256(raw).hexdigest(), "kind": "honeybee",
    }
    definition.update(source or {})
    manifest = {"schema_version": 1, "sources": {"example": definition}}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, manifest


def _rewrite_manifest(path, manifest):
    path.write_text(json.dumps(manifest))


def _responses(monkeypatch, payload, *, url=None):
    calls = []

    @contextmanager
    def opened(request, timeout):
        calls.append((request.full_url, timeout))

        class Response:
            def geturl(self):
                return request.full_url if url is None else url

            def read(self, limit):
                return payload[:limit]

        yield Response()

    monkeypatch.setattr(source_cache, "urlopen", opened)
    return calls


def test_packaged_sources_are_pinned_and_load_without_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline loading attempted network I/O")

    monkeypatch.setattr(source_cache, "urlopen", forbidden)
    cache = SourceCache.load()
    counts = {key: len(cache.records(key)) for key in cache.manifest["sources"]}
    assert counts == {
        "epsm-custom": 52, "honeybee-standards": 16,
        "honeybee-energy-standards-opaque": 171, "honeybee-energy-standards-window": 322,
        "boverket": 230,
        "epd-ies-0005222": 1, "epd-ies-0013025": 1,
    }
    assert {r["Version"] for r in cache.records("boverket").values()} == {"02.07.000"}
    report = cache.check_versions()
    assert report["status"] == "verified"
    assert all(row["status"] == "local_verified" for row in report["sources"].values())
    assert all(row["remote_release"] is None for row in report["sources"].values())


def test_explicit_file_or_directory_and_detached_outputs(tmp_path):
    path, original = _write_cache(tmp_path)
    cache = SourceCache.load(path)
    assert SourceCache.load(tmp_path).identity == sha256(path.read_bytes()).hexdigest()
    records = cache.records("example")
    records["Example"]["density"] = 1
    manifest = cache.manifest
    manifest["sources"]["example"]["release"] = "bad"
    assert cache.records("example")["Example"]["density"] == 100
    assert cache.manifest == original
    with pytest.raises(KeyError):
        cache.records("unknown")


def test_original_boverket_database_retains_exact_detached_resource_records(tmp_path):
    resource = {
        "ResourceId": 6000000000, "Version": "02.07.000", "SourceVersion": "02.07.000",
        "Name": "Original source name", "DataItems": [{"value": 1.25, "note": None}],
        "Conversions": [], "UnusedSourceField": {"locale": "sv-SE"},
    }
    original = {
        "Version": "02.07.000", "Publisher": "Boverket", "Categories": [],
        "Resources": [resource],
    }
    raw = (json.dumps(original, ensure_ascii=False, indent=3) + "\n").encode()
    path, _ = _write_cache(tmp_path, raw=raw, source={
        "format": "boverket_database", "kind": "boverket", "release": "02.07.000",
    })
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    cache = SourceCache.load(path)
    assert cache.records("example") == {"6000000000": resource}
    detached = cache.records("example")
    detached["6000000000"]["DataItems"][0]["value"] = 9
    assert cache.records("example")["6000000000"] == resource
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("location", ["root", "Version", "SourceVersion"])
def test_original_boverket_database_rejects_actual_release_mismatches(tmp_path, location):
    resource = {"ResourceId": 6000000000, "Version": "02.07.000", "SourceVersion": "02.07.000"}
    original = {"Version": "02.07.000", "Resources": [resource]}
    if location == "root":
        original["Version"] = "02.06.000"
    else:
        resource[location] = "02.06.000"
    path, _ = _write_cache(tmp_path, records=original, source={
        "format": "boverket_database", "kind": "boverket", "release": "02.07.000",
    })
    with pytest.raises(ValueError, match="release mismatch"):
        SourceCache.load(path)


def test_original_boverket_database_rejects_duplicate_resource_ids(tmp_path):
    resource = {"ResourceId": 6000000000, "Version": "02.07.000", "SourceVersion": "02.07.000"}
    original = {"Version": "02.07.000", "Resources": [resource, deepcopy(resource)]}
    path, _ = _write_cache(tmp_path, records=original, source={
        "format": "boverket_database", "kind": "boverket", "release": "02.07.000",
    })
    with pytest.raises(ValueError, match="Duplicate source record identifier"):
        SourceCache.load(path)


def test_original_honeybee_defaults_retains_all_material_types_without_injected_fields(tmp_path):
    materials = [
        {"type": "EnergyMaterial", "identifier": "Roof membrane", "density": 1120.0},
        {"type": "EnergyWindowMaterialGas", "identifier": "Air gap", "gas_type": "Air"},
        {"type": "EnergyWindowMaterialGlazing", "identifier": "Clear glass",
         "solar_transmittance": 0.8, "user_data": {"note": "Original"}},
    ]
    original = {"type": "ModelEnergyProperties", "materials": materials,
                "constructions": [{"identifier": "Unused construction"}], "schedules": []}
    path, _ = _write_cache(tmp_path, records=original, source={"format": "honeybee_defaults"})
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    cache = SourceCache.load(path)
    expected = {record["identifier"]: record for record in materials}
    assert cache.records("example") == expected
    detached = cache.records("example")
    detached["Clear glass"]["user_data"]["note"] = "Changed"
    assert cache.records("example") == expected
    assert "roughness" not in cache.records("example")["Roof membrane"]
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_original_honeybee_defaults_rejects_duplicate_material_ids(tmp_path):
    original = {"type": "ModelEnergyProperties", "materials": [
        {"identifier": "Same", "density": 100}, {"identifier": "Same", "density": 200},
    ]}
    path, _ = _write_cache(tmp_path, records=original, source={"format": "honeybee_defaults"})
    with pytest.raises(ValueError, match="Duplicate source record identifier"):
        SourceCache.load(path)


@pytest.mark.parametrize("source, payload", [
    ({"format": "unknown"}, {"A": {"identifier": "A"}}),
    ({"format": None}, {"A": {"identifier": "A"}}),
    ({"format": "honeybee_defaults"}, {"type": "Other", "materials": [{"identifier": "A"}]}),
    ({"format": "honeybee_defaults"}, {"type": "ModelEnergyProperties", "materials": {"A": {}}}),
    ({"format": "honeybee_defaults"}, {"type": "ModelEnergyProperties", "materials": []}),
    ({"format": "honeybee_defaults"}, {"type": "ModelEnergyProperties", "materials": [None]}),
    ({"format": "boverket_database"}, {"Version": "2.0.7", "Resources": [{"ResourceId": 1}]}),
    ({"format": "boverket_database", "kind": "boverket"}, []),
    ({"format": "boverket_database", "kind": "boverket"}, {"Resources": [{"ResourceId": 1}]}),
    ({"format": "boverket_database", "kind": "boverket"}, {"Version": "2.0.7", "Resources": []}),
    ({"format": "boverket_database", "kind": "boverket"}, {"Version": "2.0.7", "Resources": {"1": {}}}),
    ({"format": "boverket_database", "kind": "boverket"}, {"Version": "2.0.7", "Resources": [None]}),
])
def test_declared_raw_formats_reject_incompatible_or_malformed_source_shapes(tmp_path, source, payload):
    path, _ = _write_cache(tmp_path, records=payload, source=source)
    with pytest.raises(ValueError):
        SourceCache.load(path)


def test_record_change_without_manifest_hash_change_is_rejected(tmp_path):
    path, _ = _write_cache(tmp_path)
    (tmp_path / "records.json").write_text('{"Example":{"identifier":"Example","density":1}}')
    with pytest.raises(ValueError, match="checksum mismatch"):
        SourceCache.load(path)


@pytest.mark.parametrize("field", ["Version", "SourceVersion"])
def test_boverket_record_versions_must_match_the_pin(tmp_path, field):
    record = {"ResourceId": 6000000000, "Version": "02.07.000", "SourceVersion": "02.07.000"}
    record[field] = "02.06.000"
    path, _ = _write_cache(
        tmp_path, records={"6000000000": record},
        source={"kind": "boverket", "release": "02.07.000", "record_version_fields": []},
    )
    with pytest.raises(ValueError, match="release mismatch"):
        SourceCache.load(path)


def test_carbon_reference_revision_must_match_the_pin(tmp_path):
    path, _ = _write_cache(
        tmp_path, records={"EPD-IES-0005222:003": {"identifier": "EPD-IES-0005222:003"}},
        source={"kind": "carbon_reference", "release": "002"},
    )
    with pytest.raises(ValueError, match="revision mismatch"):
        SourceCache.load(path)


@pytest.mark.parametrize("records", [
    {"A": {"identifier": "B"}},
    {"None": {}},
    {"3": {"identifier": 3}},
    {"": {"identifier": ""}},
    {"A": []},
    [],
    {},
])
def test_invalid_record_identity_or_shape_is_rejected(tmp_path, records):
    path, _ = _write_cache(tmp_path, records=records)
    with pytest.raises(ValueError):
        SourceCache.load(path)


@pytest.mark.parametrize("identifier", [True, "6000000000", 0])
def test_boverket_resource_id_requires_positive_integer(tmp_path, identifier):
    path, _ = _write_cache(
        tmp_path, records={str(identifier): {"ResourceId": identifier}}, source={"kind": "boverket"},
    )
    with pytest.raises(ValueError, match="positive integer"):
        SourceCache.load(path)


@pytest.mark.parametrize("relative", ["../records.json", "/tmp/records.json", "a/../records.json",
    "./records.json", "a//records.json", "a\\records.json", "C:/records.json", ""])
def test_record_paths_cannot_escape_or_hide_dot_segments(tmp_path, relative):
    path, manifest = _write_cache(tmp_path)
    manifest["sources"]["example"]["records_path"] = relative
    _rewrite_manifest(path, manifest)
    with pytest.raises(ValueError):
        SourceCache.load(path)


def test_symlink_outside_cache_is_rejected(tmp_path):
    root = tmp_path / "cache"
    root.mkdir()
    path, manifest = _write_cache(root)
    outside = tmp_path / "outside.json"
    outside.write_bytes((root / "records.json").read_bytes())
    (root / "link.json").symlink_to(outside)
    manifest["sources"]["example"]["records_path"] = "link.json"
    _rewrite_manifest(path, manifest)
    with pytest.raises(ValueError, match="outside"):
        SourceCache.load(path)


@pytest.mark.parametrize("raw", [
    b'{"Example":{"identifier":"Example"},"Example":{"identifier":"Example"}}',
    b'{"Example":{"identifier":"Example","density":NaN}}',
    b'{"Example":{"identifier":"Example","density":Infinity}}',
    b'{"Example":{"identifier":"Example","density":1e999}}',
])
def test_duplicate_record_keys_and_nonfinite_json_are_rejected(tmp_path, raw):
    path, _ = _write_cache(tmp_path, raw=raw)
    with pytest.raises(ValueError):
        SourceCache.load(path)


def test_duplicate_manifest_source_id_is_rejected(tmp_path):
    path, manifest = _write_cache(tmp_path)
    source = json.dumps(manifest["sources"]["example"])
    path.write_text('{"schema_version":1,"sources":{"example":' + source + ',"example":' + source + '}}')
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        SourceCache.load(path)


@pytest.mark.parametrize("updates", [
    {"release": ""}, {"sha256": "0"}, {"kind": "other"},
    {"record_version_fields": ["Version", "Version"]},
    {"record_version_fields": "Version"},
    {"upstream": {"kind": "pypi", "url": "https://example.com/json"}},
    {"upstream": {"kind": "pypi", "url": "http://pypi.org/pypi/a/json"}},
    {"upstream": {"kind": "boverket_page", "url": "https://example.com"}},
    {"upstream": {"kind": "guess", "url": "https://example.com"}},
])
def test_invalid_manifest_source_contract_is_rejected(tmp_path, updates):
    path, _ = _write_cache(tmp_path, source=updates)
    with pytest.raises(ValueError):
        SourceCache.load(path)


def test_duplicate_source_files_are_rejected(tmp_path):
    path, manifest = _write_cache(tmp_path)
    manifest["sources"]["other"] = deepcopy(manifest["sources"]["example"])
    _rewrite_manifest(path, manifest)
    with pytest.raises(ValueError, match="distinct"):
        SourceCache.load(path)


@pytest.mark.parametrize("remote,status", [("2.0.7", "current"), ("2.0.8", "update_available"),
    ("2.0.6", "different_release"), ("3.0.0rc1", "different_release")])
def test_online_pypi_check_reports_release_without_upgrading(tmp_path, monkeypatch, remote, status):
    path, _ = _write_cache(tmp_path, source={"upstream": _PYPI})
    cache = SourceCache.load(path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    calls = _responses(monkeypatch, json.dumps({"info": {"name": "honeybee_standards", "version": remote}}).encode())
    row = cache.check_versions(online=True, timeout=1.5)["sources"]["example"]
    assert row["status"] == status
    assert row["local_release"] == "2.0.7"
    assert row["remote_release"] == remote
    assert calls == [(_PYPI["url"], 1.5)]
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    assert cache.records("example")["Example"]["density"] == 100


def test_namespaces_share_one_successful_upstream_probe_but_compare_their_own_pins(tmp_path, monkeypatch):
    path, manifest = _write_cache(tmp_path, source={"upstream": _PYPI})
    (tmp_path / "second.json").write_bytes((tmp_path / "records.json").read_bytes())
    manifest["sources"]["second"] = {
        **manifest["sources"]["example"], "records_path": "second.json", "release": "2.0.6",
    }
    _rewrite_manifest(path, manifest)
    cache = SourceCache.load(path)
    calls = _responses(monkeypatch, json.dumps({
        "info": {"name": "honeybee_standards", "version": "2.0.7"},
    }).encode())
    report = cache.check_versions(online=True)
    assert calls == [(_PYPI["url"], 3)]
    assert report["sources"]["example"]["status"] == "current"
    assert report["sources"]["second"]["status"] == "update_available"
    # Memoization belongs to one explicit check; a later request checks again.
    cache.check_versions(online=True)
    assert len(calls) == 2


def test_boverket_probe_uses_labelled_current_version_not_oldest_page_link(tmp_path, monkeypatch):
    path, _ = _write_cache(tmp_path, source={"release": "02.07.000", "upstream": _BOVERKET})
    html = b'<a>version 02.01.000</a><p>Klimatdatabas g&#228;llande version</p><ul><li>Climate database version 02.08.000</li></ul><p>version 02.07.000</p>'
    _responses(monkeypatch, html)
    row = SourceCache.load(path).check_versions(online=True)["sources"]["example"]
    assert row["status"] == "update_available"
    assert row["remote_release"] == "02.08.000"


@pytest.mark.parametrize("payload", [b'{}', b'{"info":{"name":"different","version":"2.0.7"}}', b'not JSON'])
def test_invalid_remote_response_is_reported_per_source(tmp_path, monkeypatch, payload):
    path, _ = _write_cache(tmp_path, source={"upstream": _PYPI})
    _responses(monkeypatch, payload)
    report = SourceCache.load(path).check_versions(online=True)
    row = report["sources"]["example"]
    assert report["status"] == "error"
    assert row["status"] == "error" and row["error"]
    assert row["local_status"] == "verified"


def test_network_timeout_is_reported_without_invalidating_local_cache(tmp_path, monkeypatch):
    path, _ = _write_cache(tmp_path, source={"upstream": _PYPI})

    def timeout(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(source_cache, "urlopen", timeout)
    row = SourceCache.load(path).check_versions(online=True)["sources"]["example"]
    assert row["status"] == "error"
    assert row["error"] == "timed out"
    assert row["local_status"] == "verified"


def test_oversize_or_redirected_response_is_reported(tmp_path, monkeypatch):
    path, _ = _write_cache(tmp_path, source={"upstream": _PYPI})
    cache = SourceCache.load(path)
    _responses(monkeypatch, b"x" * (source_cache._MAX_RESPONSE_BYTES + 1))
    assert "size limit" in cache.check_versions(online=True)["sources"]["example"]["error"]
    _responses(monkeypatch, b"{}", url="https://other.example/data")
    assert "redirected" in cache.check_versions(online=True)["sources"]["example"]["error"]


def test_unconfigured_authored_and_epd_probes_are_not_falsely_verified(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Not-configured sources attempted network I/O")

    cache = SourceCache.load()
    for source in cache._manifest["sources"].values():
        source.pop("upstream", None)
    monkeypatch.setattr(source_cache, "urlopen", forbidden)
    report = cache.check_versions(online=True)
    assert report["status"] == "verified"
    assert all(row["remote_status"] == "not_configured" for row in report["sources"].values())
    assert all(row["remote_release"] is None for row in report["sources"].values())


@pytest.mark.parametrize("timeout", [0, -1, 31, float("nan"), float("inf"), True, None])
def test_network_timeout_is_bounded_even_for_explicit_requests(timeout):
    with pytest.raises(ValueError, match="timeout"):
        SourceCache.load().check_versions(online=True, timeout=timeout)


def test_incomplete_remote_response_is_reported_as_a_source_error(tmp_path, monkeypatch):
    path, _ = _write_cache(tmp_path, source={"upstream": _PYPI})

    def incomplete(*args, **kwargs):
        raise IncompleteRead(b"{", 20)

    monkeypatch.setattr(source_cache, "urlopen", incomplete)
    report = SourceCache.load(path).check_versions(online=True)
    assert report["status"] == "error"
    assert report["sources"]["example"]["local_status"] == "verified"
