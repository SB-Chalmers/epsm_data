# Release 0.6.0 — 15 October 2026

Shared complete or partial archetype authoring, immutable editing, sourced operating profiles and format-4 exchange now use the same definitions as catalogue selections. All shipped catalogue types and source variants retain their physical recipes and source evidence.

This minor release removes migrated selection loaders, summary-only exchange and Data-to-EPSM forwarding APIs. Follow [the migration guide](docs/archetype-api-migration.md). Saved formats 1–3 remain readable. Data still imports and runs its authoring examples independently of Core and EPSM.

The coordinated application combination uses Data 0.6.0, Core 0.4.0, EPSM 0.3.0 and optional Database 0.3.0. Integration checks use exact source revisions; version labels alone do not establish a tested combination.

# Release 0.5.0 — 15 October 2026

Catalogue loading, selection, construction and renovation resolution, validation and exports; explicit standalone setup remains supported. Includes the reviewed operating-profile consolidation already on dev.

Libraries emit through Python's standard logging without configuring output.
Instrumented operations accept optional keyword-only `log_context`; identifiers
stay separate from scientific inputs, saved models and cache keys. INFO shows
major stages; DEBUG adds decisions and timing. Standalone commands support
`--log-level`, including `OFF`, where the package provides a command.

The EPSM application configures the combined stderr and optional DEBUG JSONL
output with `configure_logging`; `enabled=False` disables both destinations.
Existing callers and supported older collaborator signatures remain supported.
No new mandatory dependency is introduced by the logging implementation.

The coordinated release was requested for manual review and local validation
because GitHub refused to start several hosted jobs due to account billing.
Hosted checks that did not run are not counted as passes. See the
[coordinated verification record](https://github.com/SB-Chalmers/epsm_development/blob/main/docs/logging-verification.md)
for exact tested revisions, executed checks and remaining limitations.
