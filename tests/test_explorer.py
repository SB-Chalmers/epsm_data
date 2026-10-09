"""Explorer integration checks: catalogue identity and durable review notes."""

import json
import shutil
import subprocess
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

from explorer.catalogue import load_data
from explorer.server import NotesStore, make_server


@pytest.fixture(scope="module")
def catalogue():
    return load_data()


def test_matrix_uses_parametric_catalogue_and_effective_values(catalogue):
    from epsm_data import load_parametric_catalogue

    assert len(catalogue["cells"]) == len({c["id"] for c in catalogue["cells"]}) == 1080
    assert all(c["package_id"] for c in catalogue["cells"])
    office_cells = [c for c in catalogue["cells"] if c["category"] == "office"]
    assert len(office_cells) == 216
    assert all(c["lod1_complete"] and not c["missing"] for c in office_cells)
    school_cells = [c for c in catalogue["cells"] if c["category"] == "school"]
    assert len(school_cells) == 216
    assert all(c["lod1_complete"] and not c["missing"] for c in school_cells)
    school_se04 = next(
        c for c in school_cells if c["id"] == "school:SE.04:SE.Zone3:existing:F"
    )
    assert school_se04["u_values"]["glazing"] == 1.9
    school_package = next(
        p for p in catalogue["packages"] if p["id"] == school_se04["package_id"]
    )
    assert school_package["properties"]["window"]["curve"] == "v1_1.school.window"
    cell = next(
        c for c in catalogue["cells"] if c["id"] == "multi_family:SE.02:SE.Zone3:existing:F"
    )
    slot = load_parametric_catalogue().get_slot(cell["id"])
    assert cell["u_values"]["wall"] == slot.properties["external_wall"].value
    assert cell["u_values"]["internal_wall"] == slot.properties["internal_wall"].value
    assert cell["u_values"]["intermediate_floor"] == slot.properties["intermediate_floor"].value
    mf_cells = [c for c in catalogue["cells"] if c["category"] == "multi_family"]
    assert len(mf_cells) == 216
    assert all(c["lod1_complete"] and not c["missing"] for c in mf_cells)
    sf_cells = [c for c in catalogue["cells"] if c["category"] == "single_family"]
    assert len(sf_cells) == 216
    assert all(c["u_values"]["basement_wall"] is not None for c in sf_cells)
    assert all(c["lod1_complete"] and not c["missing"] for c in sf_cells)
    sf_modern = next(c for c in sf_cells if c["id"] == "single_family:SE.06:SE.Zone1:existing:S")
    assert sf_modern["u_values"]["internal_wall"] == pytest.approx(0.5366837272668065)
    assert sf_modern["u_values"]["intermediate_floor"] == pytest.approx(
        load_parametric_catalogue().resolve_construction("single_family", "SE.06", "existing").u_values["intermediate_floor"])
    generic_cells = [c for c in catalogue["cells"] if c["category"] == "generic"]
    assert len(generic_cells) == 216
    assert all(c["lod1_complete"] and not c["missing"] for c in generic_cells)
    construction = next(p for p in catalogue["packages"] if p["id"] == cell["package_id"])
    assert len(construction["properties"]) == 8
    assert construction["properties"]["infiltration"]["unit"] == "1/h"
    assert all(
        sum(
            c["zone"] == zone and c["state"] == state and c["system"] == system
            for c in catalogue["cells"]
        )
        == 30
        for zone in catalogue["dimensions"]["zones"]
        for state in catalogue["dimensions"]["states"]
        for system in catalogue["dimensions"]["systems"]
    )


def test_lod2_completeness_comes_from_detailed_catalogue(catalogue):
    assert catalogue["lod2_summary"]["lod2_complete_slots"] > 0
    assert catalogue["lod2_summary"]["slots_with_layer_recipe"] == 1080
    assert catalogue["lod2_summary"]["slots_without_layer_recipe"] == 0
    counts = {status: sum(c["lod2_status"] == status for c in catalogue["cells"])
              for status in ("complete", "draft", "no_recipe")}
    assert counts == {"complete": catalogue["lod2_summary"]["lod2_complete_slots"],
                      "draft": 1080 - catalogue["lod2_summary"]["lod2_complete_slots"], "no_recipe": 0}
    packages = {p["id"]: p for p in catalogue["packages"]}
    se01 = packages["parametric:multi_family:SE.01:existing"]["lod2"]
    assert se01["archetype_id"] == "mf_1940"
    assert se01["alternatives"][0]["archetype_id"] == "mf_1950"
    assert se01["alternatives"][0]["status"] == "draft"
    assert packages["parametric:multi_family:SE.02:existing"]["lod2"]["checks"]["nominal_u_alignment"]
    school = packages["parametric:school:SE.02:existing"]["lod2"]
    assert school["status"] == "complete"
    assert school["checks"]["nominal_u_alignment"] is True
    assert school["alternatives"][0]["archetype_id"] == "school_fridhem"
    assert school["alternatives"][0]["status"] == "draft"
    assert packages["parametric:school:SE.04:existing"]["lod2"]["status"] == "complete"


def test_construction_payload_retains_material_properties_and_composites(catalogue):
    package = next(
        p for p in catalogue["packages"]
        if p["id"] == "parametric:multi_family:SE.02:existing"
    )
    wall = package["construction"]["EXT_WALL"]
    assert wall["u_value"] is not None
    assert wall["components"]
    layers = [layer for component in wall["components"] for layer in component["layers"]]
    composite = next(layer for layer in layers if len(layer["materials"]) > 1)
    assert sum(material["area_fraction"] for material in composite["materials"]) == pytest.approx(1)
    material = composite["materials"][0]
    assert material["honeybee_id"]
    assert material["honeybee_properties"]["conductivity"] > 0
    assert material["honeybee_properties"]["density"] > 0
    assert material["honeybee_properties"]["specific_heat"] > 0
    assert material["boverket_id"]
    assert material["gwp"]["unit"] == "kg CO2 eq./kg"
    assert material["gwp"]["A1_A3_typical"] is not None
    assert material["gwp"]["A1_A3_conservative"] is not None
    assert material["gwp"]["A4_transport"] is not None
    assert material["gwp"]["A5_conservative"] is not None
    unmatched = next(
        material
        for p in catalogue["packages"]
        for assembly in p["construction"].values()
        for component in assembly.get("components", [])
        for layer in component["layers"]
        for material in layer["materials"]
        if material["boverket_id"] is None
    )
    assert unmatched["gwp"] is None
    window = package["construction"]["WINDOW"]
    assert window["window"] and window["material"]["honeybee_id"]


@pytest.fixture
def server(tmp_path, catalogue, monkeypatch):
    monkeypatch.setattr("explorer.server.load_data", lambda path: catalogue)
    app = make_server(port=0, notes_path=tmp_path / "notes.sqlite")
    thread = threading.Thread(target=app.serve_forever, daemon=True)
    thread.start()
    yield app, tmp_path / "notes.sqlite"
    app.shutdown()
    app.server_close()
    thread.join()


def request(server, method, path, payload=None, headers=None):
    connection = HTTPConnection("127.0.0.1", server[0].server_port, timeout=10)
    connection.request(
        method,
        path,
        body=json.dumps(payload) if payload is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    response = connection.getresponse()
    raw = response.read()
    result = (
        json.loads(raw) if response.headers["Content-Type"].startswith("application/json") else raw
    )
    connection.close()
    return response.status, result


def payload(catalogue):
    cell = catalogue["cells"][0]
    return dict(
        cell_id=cell["id"],
        package_id=cell["package_id"],
        revision=cell["revision"],
        release_id=catalogue["manifest"]["release_id"],
        body="Review insulation — åäö",
        kind="question",
        author="Reviewer",
    )


def test_notes_persist_update_conflicts_and_delete(server, catalogue):
    status, note = request(server, "POST", "/api/notes", payload(catalogue))
    assert status == 201
    assert NotesStore(server[1]).all() == [note]
    update = {**note, "body": "Reviewed construction"}
    status, revised = request(server, "PUT", "/api/notes/" + note["id"], update)
    assert status == 200 and revised["body"] == update["body"]
    assert revised["created_at"] == note["created_at"]
    assert request(server, "PUT", "/api/notes/" + note["id"], update)[0] == 409
    assert request(server, "DELETE", "/api/notes/" + note["id"], note)[0] == 409
    assert request(server, "GET", "/api/notes")[1] == [revised]
    assert request(server, "DELETE", "/api/notes/" + note["id"], revised)[0] == 200
    assert NotesStore(server[1]).all() == []


def test_invalid_context_input_and_cross_origin_are_rejected(server, catalogue):
    note = payload(catalogue)
    for bad in [
        {**note, "body": " "},
        {**note, "cell_id": "unknown"},
        {**note, "kind": "published"},
        {**note, "body": "a" * 20001},
        {**note, "package_id": "unassigned"},
        {**note, "release_id": "stale"},
        [],
    ]:
        assert request(server, "POST", "/api/notes", bad)[0] == 400
    assert (
        request(server, "POST", "/api/notes", note, {"Origin": "https://untrusted.example"})[0]
        == 403
    )
    assert request(server, "GET", "/api/notes", headers={"Host": "untrusted.example"})[0] == 403
    assert request(server, "POST", "/api/notes", note, {"Content-Type": "text/plain"})[0] == 415
    assert request(server, "GET", "/../../README.md")[0] == 404
    assert NotesStore(server[1]).all() == []


def test_notes_are_isolated_per_cell_and_context_cannot_move(server, catalogue):
    first = payload(catalogue)
    _, note = request(server, "POST", "/api/notes", first)
    second = catalogue["cells"][1]
    other = {
        **first,
        "cell_id": second["id"],
        "package_id": second["package_id"],
        "revision": second["revision"],
        "body": "<script>alert(1)</script>",
    }
    _, other_note = request(server, "POST", "/api/notes", other)
    assert other_note["cell_id"] != note["cell_id"]
    assert other_note["body"] == other["body"]  # UI escapes all remark text.
    assert (
        request(
            server, "PUT", "/api/notes/" + note["id"], {**note, "cell_id": other_note["cell_id"]}
        )[0]
        == 400
    )
    assert len(request(server, "GET", "/api/notes")[1]) == 2


def test_catalogue_cannot_be_used_as_notes_store(tmp_path):
    path = tmp_path / "source.sqlite"
    path.write_bytes(b"unchanged source")
    with pytest.raises(ValueError, match="separate"):
        make_server(notes_path=path, catalogue_path=path)
    assert path.read_bytes() == b"unchanged source"


def test_historical_notes_remain_exportable_without_reassignment(server, catalogue):
    store = NotesStore(server[1])
    originals = []
    for cell_id in (
        "multi_family:SE.02:SE.Zone3:existing:F",
        "commercial:SE.07:SE.Zone1:existing:S",
    ):
        historical = {
            **payload(catalogue),
            "cell_id": cell_id,
            "package_id": "old-physical-set",
            "revision": "old-revision",
            "release_id": "old-release",
        }
        originals.append(store.save(historical))
    assert request(server, "GET", "/api/notes")[1] == originals
    for original in originals:
        status, edited = request(
            server,
            "PUT",
            "/api/notes/" + original["id"],
            {**original, "body": "Retained historical review"},
        )
        assert status == 200
        for key in ("cell_id", "package_id", "revision", "release_id", "created_at"):
            assert edited[key] == original[key]
    assert not any(c["id"] == originals[1]["cell_id"] for c in catalogue["cells"])


def test_json_input_and_deterministic_review_hashes(tmp_path, catalogue):
    from epsm_data import load_parametric_catalogue

    path = tmp_path / "catalogue.json"
    config = load_parametric_catalogue().to_dict()
    path.write_text(json.dumps(dict(reversed(list(config.items())))), encoding="utf-8")
    assert load_data(path) == catalogue
    config["categories"]["office"]["anchors"]["roof"] = dict(
        value=0.2, era="SE.03", state="existing", source="proxy", note="Supplied reference"
    )
    path.write_text(json.dumps(config), encoding="utf-8")
    changed = load_data(path)
    assert changed["manifest"]["release_id"] != catalogue["manifest"]["release_id"]
    for before, after in zip(catalogue["cells"], changed["cells"], strict=True):
        assert (before["revision"] != after["revision"]) == (before["category"] == "office")


def test_static_app_assets_and_catalogue_endpoint(server, catalogue):
    assert request(server, "GET", "/api/catalogue")[1] == json.loads(json.dumps(catalogue))
    html = request(server, "GET", "/")[1].decode()
    assert "internal_wall" in html and "intermediate_floor" in html and "basement_wall" in html
    script = request(server, "GET", "/app.js")[1].decode()
    assert "LoD2 complete" in script
    assert "lod1_complete" in script
    assert '$("#export")' in script


def test_client_rendering_filters_bookmarks_and_remarks_export(catalogue):
    """Execute the actual client against a small DOM double, without browser dependencies."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed for the optional client rendering check")
    script = r"""
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const elements = new Map();
class Element {
  constructor() { this.dataset = {}; this.listeners = {}; this.value = ""; this.hidden = true; }
  set innerHTML(html) {
    for (const match of (this.html || "").matchAll(/id="([^"]+)"/g)) elements.delete(match[1]);
    this.html = html;
    for (const match of html.matchAll(/id="([^"]+)"/g)) elements.set(match[1], new Element());
  }
  get innerHTML() { return this.html || ""; }
  insertAdjacentHTML(position, html) { this.innerHTML = this.innerHTML + html; }
  addEventListener(event, callback) { this.listeners[event] = callback; }
  click() { return this.onclick?.(); }
  focus() {}
  querySelectorAll(selector) { return document.querySelectorAll(selector); }
}
for (const match of input.html.matchAll(/id="([^"]+)"/g)) elements.set(match[1], new Element());
const document = {
  querySelector(selector) {
    if (selector.startsWith("#")) return elements.get(selector.slice(1)) || null;
    const tab = selector.match(/\[data-tab="([^"]+)"\]/);
    return tab ? this.querySelectorAll("[data-tab]").find(e => e.dataset.tab === tab[1]) : null;
  },
  querySelectorAll(selector) {
    const field = selector === "[data-cell]" ? "cell" : selector === "[data-tab]" ? "tab" : null;
    if (!field) return [];
    const html = elements.get(field === "cell" ? "matrix" : "detail").innerHTML;
    return [...html.matchAll(new RegExp(`data-${field}="([^"]+)"`, "g"))].map(m => {
      const e = new Element(); e.dataset[field] = m[1]; return e;
    });
  },
  createElement() { const e = new Element(); e.click = () => downloads.push(e.download); return e; },
};
const historical = {id: "old-note", cell_id: "office:SE.07:SE.Zone1:existing:S", body: "Orphan retained"};
const stored = [historical], downloads = [], blobs = [];
const context = vm.createContext({
  document, console, Blob, URL: {createObjectURL(blob) {blobs.push(blob); return "blob:test";}, revokeObjectURL() {}},
  location: {hash: "#school%3ASE.06%3ASE.Zone2%3Aadvanced%3AFTX"},
  history: {replaceState(a, b, hash) {context.location.hash = hash;}},
  window: {addEventListener() {}}, matchMedia: () => ({matches: false}),
  setTimeout: () => 1, clearTimeout() {}, confirm: () => true,
  fetch: async (path, options) => {
    if (options?.method === "POST") stored.push({id: "new-note", ...JSON.parse(options.body)});
    return {ok: true, json: async () => path === "/api/catalogue" ? input.catalogue :
      options?.method === "POST" ? stored.at(-1) : stored};
  },
});
vm.runInContext(input.script, context);
const flush = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  await flush();
  assert.equal(elements.get("error").textContent, undefined, "Client initialization failed");
  assert.equal(elements.get("app").hidden, false);
  assert.match(elements.get("lod2-total").textContent, new RegExp(`${input.catalogue.lod2_summary.lod2_complete_slots} LoD2 complete · 1080 with recipes`));
  assert.ok((elements.get("matrix").innerHTML.match(/class="lod2-tick"/g) || []).length > 0);
  assert.match(elements.get("count").textContent, /^30 of 30/);
  assert.equal((elements.get("matrix").innerHTML.match(/data-cell=/g) || []).length, 30);
  assert.doesNotMatch(elements.get("matrix").innerHTML, /No LoD2 recipe/);
  assert.match(elements.get("detail").innerHTML, /School.*2006–present/);
  assert.equal((elements.get("detail-content").innerHTML.match(/class="metric"/g) || []).length, 8);
  assert.match(elements.get("detail-content").innerHTML, /School window profile/);
  assert.match(elements.get("detail-content").innerHTML, /SE\.06 · 2006–present<\/th><td>0\.9/);
  assert.equal((elements.get("detail-content").innerHTML.match(/<tr class=/g) || []).length, 6);
  assert.doesNotMatch(elements.get("detail-content").innerHTML, /Pending: Ground floor/);
  elements.get("metric").value = "internal_wall";
  elements.get("metric").listeners.change();
  assert.equal((elements.get("matrix").innerHTML.match(/<strong>—<\/strong>/g) || []).length, 0);
  assert.equal((elements.get("matrix").innerHTML.match(/background:#e8eaed/g) || []).length, 0);
  // Partial caller-supplied catalogues must still show missing values clearly.
  vm.runInContext(`
    globalThis.pendingCell = data.cells.find(c => c.category === "generic" && visible(c));
    globalThis.savedValue = pendingCell.u_values.internal_wall;
    pendingCell.u_values.internal_wall = null;
    renderMatrix();
  `, context);
  assert.equal((elements.get("matrix").innerHTML.match(/<strong>—<\/strong>/g) || []).length, 1);
  assert.equal((elements.get("matrix").innerHTML.match(/background:#e8eaed/g) || []).length, 1);
  vm.runInContext('pendingCell.u_values.internal_wall = savedValue; renderMatrix();', context);
  elements.get("search").value = "2030"; elements.get("search").listeners.input();
  assert.match(elements.get("count").textContent, /^5 of 30/);
  elements.get("search").value = "not-a-category"; elements.get("search").listeners.input();
  assert.match(elements.get("matrix").innerHTML, /colspan="7"/);
  elements.get("reset").click();
  assert.match(context.location.hash, /multi_family/);
  assert.doesNotMatch(elements.get("detail-content").innerHTML, /Pending:/);
  vm.runInContext('tab = "layers"; renderDetail();', context);
  assert.match(elements.get("detail-content").innerHTML, /LoD2 complete/);
  assert.match(elements.get("detail-content").innerHTML, /Nominal U-value alignment/);
  assert.match(elements.get("detail-content").innerHTML, /Ground validation/);
  vm.runInContext('selectCell(cellsById.get("multi_family:SE.01:SE.Zone3:existing:F"));', context);
  vm.runInContext('tab = "layers"; renderDetail();', context);
  assert.match(elements.get("detail-content").innerHTML, /mf_1940/);
  assert.match(elements.get("detail-content").innerHTML, /mf_1950: LoD2 draft/);
  vm.runInContext('selectCell(cellsById.get("school:SE.02:SE.Zone3:existing:F"));', context);
  assert.match(elements.get("detail-content").innerHTML, /LoD2 complete/);
  assert.match(elements.get("detail-content").innerHTML, /school_fridhem: LoD2 draft/);
  vm.runInContext('selectCell(cellsById.get("school:SE.04:SE.Zone3:existing:F"));', context);
  assert.match(elements.get("detail-content").innerHTML, /LoD2 complete/);
  vm.runInContext('selectCell(cellsById.get("multi_family:SE.02:SE.Zone3:existing:F"));', context);
  vm.runInContext('tab = "evidence"; renderDetail();', context);
  assert.match(elements.get("detail-content").innerHTML, /Scaling factor/);
  assert.match(elements.get("detail-content").innerHTML, /Unclipped value/);
  assert.doesNotMatch(elements.get("detail-content").innerHTML, /Nominal lower bound/);
  assert.doesNotMatch(elements.get("detail-content").innerHTML, /Guardrail source/);
  vm.runInContext('tab = "notes"; renderDetail();', context);
  elements.get("body").value = "Review <script> safely";
  elements.get("author").value = "Tester"; elements.get("kind").value = "question";
  await elements.get("note-form").onsubmit({preventDefault() {}});
  assert.equal(stored.length, 2);
  assert.equal(stored[1].cell_id, "multi_family:SE.02:SE.Zone3:existing:F");
  assert.equal(stored[1].release_id, input.catalogue.manifest.release_id);
  assert.match(elements.get("detail-content").innerHTML, /Review &lt;script&gt; safely/);
  await elements.get("export").click();
  assert.match(downloads[0], /^epsm-remarks-/);
  const exported = JSON.parse(await blobs[0].text());
  assert.equal(exported.notes[0].cell_id, historical.cell_id);
  assert.equal(exported.notes.length, 2);
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    static = Path(__file__).resolve().parents[1] / "explorer" / "static"
    result = subprocess.run(
        [node, "-e", script],
        input=json.dumps(
            dict(
                catalogue=catalogue,
                html=(static / "index.html").read_text(),
                script=(static / "app.js").read_text(),
            )
        ),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
