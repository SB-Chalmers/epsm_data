"""Archived evidence is hash-pinned and historical proposals cannot change export."""

import hashlib
import json

import pytest

from epsm_data.extraction_audit import reconcile_extraction


def test_hash_guard_and_historical_current_value(tmp_path):
    raw = tmp_path / "raw.json"
    raw.write_text("[{}]")

    def save(name, value):
        (tmp_path / name).write_text(json.dumps(value))

    save(
        "review_decisions.json",
        {
            "input_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
            "groups": [{"id": "same_case", "records": [1]}],
        },
    )
    save(
        "records.json",
        [
            {
                "record_number": 1,
                "json_pointer": "/0",
                "record_id": "R001",
                "case_family": "same_case",
                "state": "existing_as_reported",
            }
        ],
    )
    save(
        "comparisons.json",
        [
            {
                "category": "multi_family",
                "era": "SE.02",
                "state": "existing",
                "element": "window",
                "effective_proposed_value": 2.2,
                "evidence": {"record_ids": ["R001"], "independent_blocks": 1},
            }
        ],
    )
    save(
        "calibration.json",
        {
            "calibration_id": "v1.3",
            "entries": {"multi_family:SE.02:existing:window": {"final_value": 2.8}},
        },
    )
    result = reconcile_extraction(raw, tmp_path, calibration=tmp_path / "calibration.json")
    cell = result["cells"][0]
    assert cell["current_calibration"]["final_value"] == 2.8
    assert cell["archived_review"]["effective_proposed_value"] == 2.2
    assert cell["independent_blocks"] == 1
    assert result["catalogue_changed"] is False
    assert result["measured_annual_targets"] is False
    raw.write_text("[{},{}]")
    with pytest.raises(ValueError, match="hash"):
        reconcile_extraction(raw, tmp_path)
