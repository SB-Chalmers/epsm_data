"""Pinned local source records with explicit, read-only upstream version checks.

Loading verifies the packaged or caller-selected cache without using the network.
Online checks report upstream releases; they never replace cached records.
"""

import json
import math
import re
from copy import deepcopy
from hashlib import sha256
from html import unescape
from http.client import HTTPException
from importlib.resources import files
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

_KINDS = {"boverket", "epsm_authored", "carbon_reference"}
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_MAX_TIMEOUT_SECONDS = 30
_BOVERKET_VERSION_URL = (
    "https://www.boverket.se/sv/om-boverket/oppna-data/boverkets-klimatdatabas/"
)


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{label} requires nonempty text without surrounding whitespace")
    return value


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(raw):
    def nonfinite(value):
        raise ValueError(f"Nonfinite JSON value: {value}")

    value = json.loads(raw, object_pairs_hook=_object, parse_constant=nonfinite)
    # Also catches numeric overflow such as 1e999, which parse_constant misses.
    json.dumps(value, allow_nan=False)
    return value


def _relative_path(value):
    value = _text(value, "records_path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or "\\" in value
        or ":" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("records_path must stay within the cache directory")
    return path.parts


def _read_record_file(root, relative):
    parts = _relative_path(relative)
    target = root.joinpath(*parts)
    if isinstance(root, Path) and not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("records_path resolves outside the cache directory")
    return target.read_bytes()


def _validate_upstream(upstream):
    if upstream is None:
        return
    if not isinstance(upstream, dict):
        raise ValueError("upstream must be a mapping")
    kind = upstream.get("kind")
    url = upstream.get("url")
    if kind == "boverket_page":
        if url != _BOVERKET_VERSION_URL:
            raise ValueError("Boverket version checks require the official current-version page")
    else:
        raise ValueError(f"Unsupported upstream version check: {kind!r}")


def _index_records(source_id, records, identifier_field):
    """Index an original source array without changing any source record."""
    if not isinstance(records, list) or not records:
        raise ValueError(f"Source {source_id!r} requires a nonempty source record array")
    indexed = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"Source record {source_id!r} must be a mapping")
        identifier = record.get(identifier_field)
        if identifier_field == "ResourceId":
            if type(identifier) is not int or identifier <= 0:
                raise ValueError("Boverket ResourceId must be a positive integer")
        else:
            _text(identifier, "source record identifier")
        key = str(identifier)
        if key in indexed:
            raise ValueError(f"Duplicate source record identifier: {source_id}/{key}")
        indexed[key] = record
    return indexed


def _record_mapping(source_id, source, payload):
    """Read explicitly declared upstream layouts; source bytes remain intact."""
    format_name = source.get("format", "id_map")
    if format_name == "id_map":
        return payload
    if format_name == "boverket_database":
        if source["kind"] != "boverket" or not isinstance(payload, dict):
            raise ValueError("boverket_database requires a Boverket root object")
        if payload.get("Version") != source["release"]:
            raise ValueError(f"Source root release mismatch: {source_id}.Version")
        return _index_records(source_id, payload.get("Resources"), "ResourceId")
    raise ValueError(f"Unsupported source record format: {format_name!r}")


def _validate_records(source_id, source, records):
    if not isinstance(records, dict) or not records:
        raise ValueError(f"Source {source_id!r} requires a nonempty ID-to-record mapping")
    kind = source["kind"]
    version_fields = source.get("record_version_fields", [])
    if not isinstance(version_fields, list) or any(
        not isinstance(field, str) or not field for field in version_fields
    ) or len(set(version_fields)) != len(version_fields):
        raise ValueError("record_version_fields must contain distinct field names")
    if kind == "boverket":
        version_fields = list(dict.fromkeys(["Version", "SourceVersion", *version_fields]))
    for identifier, record in records.items():
        _text(identifier, "record identifier")
        if not isinstance(record, dict):
            raise ValueError(f"Source record {source_id}/{identifier} must be a mapping")
        actual_id = record.get("ResourceId" if kind == "boverket" else "identifier")
        if kind == "boverket" and (type(actual_id) is not int or actual_id <= 0):
            raise ValueError("Boverket ResourceId must be a positive integer")
        if kind != "boverket":
            _text(actual_id, "source record identifier")
        if str(actual_id) != identifier:
            raise ValueError(f"Source record identifier mismatch: {source_id}/{identifier}")
        for field in version_fields:
            if record.get(field) != source["release"]:
                raise ValueError(f"Source release mismatch: {source_id}/{identifier}.{field}")
        if kind == "carbon_reference" and identifier.rsplit(":", 1)[-1] != source["release"]:
            raise ValueError(f"Carbon reference revision mismatch: {source_id}/{identifier}")


def _fetch_upstream(upstream, timeout):
    request = Request(
        upstream["url"],
        headers={"User-Agent": "epsm-data-source-check/1", "Accept": "application/json,text/html"},
    )
    with urlopen(request, timeout=timeout) as response:
        # Redirects must retain the explicitly approved official endpoint host.
        actual = urlsplit(response.geturl())
        if actual.scheme != "https" or actual.netloc != urlsplit(upstream["url"]).netloc:
            raise ValueError("Version endpoint redirected to another host")
        raw = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise ValueError("Version endpoint response exceeds the size limit")
    plain = unescape(re.sub(r"<[^>]*>", " ", raw.decode("utf-8")))
    match = re.search(
        r"Klimatdatabas\s+gällande\s+version.{0,2000}?\bversion\s+(\d{2}\.\d{2}\.\d{3})\b",
        plain,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise ValueError("Boverket page lacks the labelled current-version section")
    return match.group(1)


def _release_status(pinned, remote):
    if pinned == remote:
        return "current"
    if re.fullmatch(r"\d+(?:\.\d+)*", pinned) and re.fullmatch(r"\d+(?:\.\d+)*", remote):
        if tuple(map(int, remote.split("."))) > tuple(map(int, pinned.split("."))):
            return "update_available"
    return "different_release"


class SourceCache:
    """Verified snapshots of source records and their pinned release identities."""

    def __init__(self, manifest, records, identity):
        self._manifest = deepcopy(manifest)
        self._records = deepcopy(records)
        self._identity = identity

    @classmethod
    def load(cls, path=None):
        """Verify a manifest and all referenced local files, without network I/O.

        ``path`` may name a manifest JSON file or its containing directory.
        The default is ``epsm_data.datasets.sources/manifest.json``.
        """
        if path is None:
            root = files("epsm_data.datasets.sources")
            manifest_file = root.joinpath("manifest.json")
        else:
            manifest_file = Path(path)
            if manifest_file.is_dir():
                manifest_file /= "manifest.json"
            root = manifest_file.parent
        raw = manifest_file.read_bytes()
        manifest = _json(raw)
        if (
            not isinstance(manifest, dict)
            or type(manifest.get("schema_version")) is not int
            or manifest["schema_version"] != 1
            or not isinstance(manifest.get("sources"), dict)
            or not manifest["sources"]
        ):
            raise ValueError("Unsupported source cache manifest")
        captured = {}
        used_paths = set()
        for source_id, source in manifest["sources"].items():
            _text(source_id, "source ID")
            if not isinstance(source, dict) or source.get("kind") not in _KINDS:
                raise ValueError(f"Unsupported source kind: {source_id}")
            _text(source.get("release"), "source release")
            parts = _relative_path(source.get("records_path"))
            if parts in used_paths:
                raise ValueError("Source record files must be distinct")
            used_paths.add(parts)
            digest = source.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Source records require a lowercase SHA-256 digest")
            _validate_upstream(source.get("upstream"))
            record_bytes = _read_record_file(root, source["records_path"])
            if sha256(record_bytes).hexdigest() != digest:
                raise ValueError(f"Source cache checksum mismatch: {source_id}")
            records = _record_mapping(source_id, source, _json(record_bytes))
            _validate_records(source_id, source, records)
            captured[source_id] = records
        return cls(manifest, captured, sha256(raw).hexdigest())

    @property
    def manifest(self):
        """Detached manifest, including pinned releases and file checksums."""
        return deepcopy(self._manifest)

    @property
    def identity(self):
        """SHA-256 of the exact verified manifest bytes."""
        return self._identity

    def records(self, source_id):
        """Return detached records from one verified source namespace."""
        return deepcopy(self._records[source_id])

    def check_versions(self, *, online=False, timeout=3):
        """Report local pins and optionally query official upstream release metadata.

        ``timeout`` is the per-request network timeout in seconds (0–30, exclusive
        of zero). Errors are reported per source. Cache files are never written.
        """
        if type(online) is not bool:
            raise ValueError("online must be a boolean")
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or not 0 < timeout <= _MAX_TIMEOUT_SECONDS
        ):
            raise ValueError("timeout must be finite, positive and at most 30 seconds")
        result = {"online": online, "cache_identity": self.identity, "status": "verified", "sources": {}}
        remote_releases = {}
        for source_id, source in self._manifest["sources"].items():
            entry = {
                "pinned_release": source["release"],
                "local_release": source["release"],
                "remote_release": None,
                "local_status": "verified",
                "remote_status": "not_checked" if not online else "not_configured",
                "status": "local_verified" if not online else "not_configured",
                "error": None,
            }
            if online and source.get("upstream") is not None:
                try:
                    upstream = source["upstream"]
                    endpoint = (upstream["kind"], upstream["url"])
                    if endpoint not in remote_releases:
                        remote_releases[endpoint] = _fetch_upstream(upstream, timeout)
                    entry["remote_release"] = remote_releases[endpoint]
                    entry["status"] = _release_status(source["release"], entry["remote_release"])
                    entry["remote_status"] = entry["status"]
                except (OSError, ValueError, UnicodeError, HTTPException) as exc:
                    entry.update(status="error", remote_status="error", error=str(exc))
            result["sources"][source_id] = entry
        statuses = {entry["status"] for entry in result["sources"].values()}
        if "error" in statuses:
            result["status"] = "error"
        elif statuses & {"update_available", "different_release"}:
            result["status"] = "updates_available"
        return result
