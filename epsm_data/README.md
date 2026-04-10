# epsm_data Scaffold

This folder is the new library namespace for EPSM development.

## Intent
- Provide a stable package layout before implementation starts.
- Keep domain logic, thermal physics, lifecycle simulation, I/O, and reporting separated.
- Avoid refactoring existing code during this scaffold phase.

## Development Rules
- Implement thermal calculations in one source of truth (`thermal/`).
- Keep domain entities in `domain/` free of I/O and SQL dependencies.
- Keep all adapters to Excel/API/DB in `infra/`.
- Use `reporting/` to produce comprehensive run and validation reports.

## Status
Scaffold only. Most functions intentionally raise `NotImplementedError`.
