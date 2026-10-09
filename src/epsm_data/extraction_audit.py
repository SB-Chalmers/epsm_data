"""Reconcile archived literature extraction with the current construction matrix.

References: freeze-2026-09-30/evidence/lod1_calibration/{manifest,
review_decisions,comparisons}.json and parametric/calibration.json (LoD2 v1.3).
These are construction/model-input observations, not measured annual heat targets.
Positional case annotations are usable only against their reviewed input hash.
Ground effective reference U and nominal layer U remain distinct physical quantities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def reconcile_extraction(extraction, review_directory, *, calibration=None):
    """Return a read-only evidence register; reject stale review annotations.

    Preserve reviewed source/dependence blocks, state, era uncertainty and boundary
    qualifications instead of pooling correlated cases into a new numerical mean.
    No catalogue value, raw record or earlier proposal is modified or promoted.
    """
    extraction, review = Path(extraction), Path(review_directory)

    def read(path):
        """Decode an explicitly supplied local evidence artifact."""
        return json.loads(Path(path).read_text())

    decisions = read(review / "review_decisions.json")
    digest = hashlib.sha256(extraction.read_bytes()).hexdigest()
    if digest != decisions["input_sha256"]:
        raise ValueError("Extraction hash differs from reviewed positional annotations")
    raw = read(extraction)
    records = read(review / "records.json")
    if not isinstance(raw, list) or len(raw) != len(records):
        raise ValueError("Extraction and reviewed record count differ")
    for number, (_item, record) in enumerate(zip(raw, records), 1):
        # The complete-file hash above is authoritative; keep archived per-record
        # hashes as provenance, without guessing another canonicalization scheme.
        if record["record_number"] != number or record["json_pointer"] != f"/{number - 1}":
            raise ValueError("Reviewed record order differs from extraction")
    if calibration is None:
        calibration = Path(__file__).parent / "datasets/parametric/calibration.json"
    current = read(calibration)
    cells = current["entries"]
    if isinstance(cells, list):
        cells = {f"{c['category']}:{c['era']}:{c['state']}:{c['element']}": c for c in cells}
    comparisons = read(review / "comparisons.json")
    by_id = {r["record_id"]: r for r in records}
    rows = []
    for comparison in comparisons:
        key = ":".join(comparison[k] for k in ("category", "era", "state", "element"))
        evidence = comparison.get("evidence", {})
        ids = evidence.get("record_ids", [])
        contextual = comparison.get("contextual_record_ids", [])
        if any(i not in by_id for i in ids + contextual):
            raise ValueError("Comparison references an unavailable reviewed record")
        rows.append(
            {
                "cell": key,
                "current_calibration": cells.get(key),
                "archived_review": comparison,
                "supporting_records": [by_id[i] for i in ids],
                "contextual_records": [by_id[i] for i in contextual],
                "independent_blocks": evidence.get("independent_blocks"),
                "annual_building_validation": "pending",
                "interpretation": "Archived proposals are historical; current calibration controls export",
            }
        )
    return {
        "schema_version": 1,
        "input_sha256": digest,
        "records": len(records),
        "reviewed_cells": len(rows),
        "current_calibration_id": current.get("calibration_id"),
        "catalogue_changed": False,
        "measured_annual_targets": False,
        "dependence_groups": decisions["groups"],
        "cells": rows,
        "uncompared_current_cells": sorted(set(cells) - {r["cell"] for r in rows}),
    }


def main(argv=None):
    """Export to a new file; preserve the authoritative archive and existing outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--review-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = reconcile_extraction(args.extraction, args.review_directory)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
