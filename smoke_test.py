"""End-to-end smoke test for epsm_data pipeline."""

from pathlib import Path

from epsm_data import setup_logging, run_build_baseline, export_json, export_construction_sets

DATA = Path("Data")
EXCEL = DATA / "Material_Database.xlsx"
JSON = DATA / "opaque_material.json"
OUT = Path("output") / "smoke_test"

print("=" * 60)
print("EPSM_DATA END-TO-END SMOKE TEST")
print("=" * 60)

setup_logging(log_file=Path("logs/smoke_test.log"))

# Run the full pipeline
result = run_build_baseline(EXCEL, JSON)

# Export
export_json(result.archetypes, OUT)
export_construction_sets(result.archetypes, OUT)

print(f"\nExported to {OUT}/")
print("SMOKE TEST PASSED")
