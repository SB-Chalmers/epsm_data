# Archetype explorer

Local, dependency-free viewer for the Swedish parametric catalogue and detailed
LoD2 completeness report.

## Run

```sh
python -m explorer.server
python -m explorer.server --port 8766 --catalogue /path/to/catalogue.json \
  --notes /path/to/explorer-notes.sqlite
```

Open http://127.0.0.1:8765. The optional catalogue is editable JSON and is loaded
read-only. No workbooks, network connections, or governed database are needed.

## Explore

The 1,080-slot matrix has five categories and six eras. Climate zone, renovation,
and ventilation select a 30-cell slice. Search by category, era, year, or cell ID;
choose any of seven U-value colour metrics. Missing values appear as dashes in
grey cells. Each cell reports its LoD1 and LoD2 completeness.

Overview shows seven effective boundary U-values and infiltration. Evidence
shows anchors, curves, overrides, source notes, and assumptions. Selecting a
School cell also shows its whole-window U-values across all six eras for the
selected renovation state. The school-specific period mapping is documented in
[the evidence note](../evidence/school_window_period_profile.md). The LoD2 tab
shows whether a detailed layer recipe is accepted, draft, or absent. For authored
recipes it shows acceptance checks, remaining limitations, and separate ground,
carbon, and simulation readiness. The actual layer stacks remain in the detailed
catalogue. Zone and ventilation classifications do not scale the values.

Existing bookmarks work where the category and era IDs remain present.
SE.06 is the 2006–present extension. Removed categories and former modern-era
bookmarks have no automatic mapping.

## Remarks

Remarks remain in `data/local/explorer-notes.sqlite`, separately from the
catalogue. Preserve that file when backing up or changing the catalogue.
Export remarks downloads all saved notes, including notes for removed cells.

Historical remarks retain their original release, package, and revision context.
Matching historical cell IDs continue to show their remarks; missing-cell remarks
remain stored and exportable. Editing a remark never changes its review context.
New remarks record deterministic hashes of the catalogue and effective properties.

Drafts survive navigation within the page and warn before leaving. Save a remark
to make it durable. Concurrent edits are rejected rather than silently overwritten.
The app binds to localhost and retains the existing local request guards.

```sh
python -m pytest tests/test_explorer.py -q
node --check explorer/static/app.js
```
