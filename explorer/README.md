# LoD2 catalogue explorer

A local, dependency-free viewer for the frozen Swedish LoD2 catalogue. The public
`Catalogue` API supplies 28 families, 76 fabric configurations and 228 climate-zone
assignments. The viewer shows forward U-values, shared material/layer composition,
Honeybee/Boverket links and explicit missing-value paths.

```sh
python -m explorer.server
```

Open the localhost address printed by the server. Choose a climate zone and fabric
alternative, then select a matrix cell. SE.07 has one configuration without a
renovation state. No ventilation matrix, LoD1 targets or calibration checks remain.

An alternate complete LoD2 JSON file can be selected with `--catalogue PATH`.
The catalogue is read-only. Correct canonical database definitions through a PR.

Remarks are stored separately in `data/local/explorer-notes.sqlite`; use
`--notes PATH` to change the location. Export remarks downloads all saved notes,
including historical notes. Each note retains the reviewed cell, definition
content hash and catalogue content hash. These hashes identify remark context;
they do not create a catalogue version workflow. Existing remarks are not moved
when a new database is loaded.

Drafts survive navigation and warn before leaving. Concurrent remark edits are
rejected. The server binds to localhost and keeps its local request guards.

```sh
python -m pytest tests/test_explorer.py -q
node --check explorer/static/app.js
```
