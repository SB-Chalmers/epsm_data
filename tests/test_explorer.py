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


def test_matrix_uses_only_lod2_and_forward_construction_values(catalogue):
    from epsm_data import BuildingElement, Catalogue

    library = Catalogue.load()
    assert len(catalogue["cells"]) == len({c["id"] for c in catalogue["cells"]}) == 228
    assert len(catalogue["packages"]) == 76
    assert set(catalogue["dimensions"]["categories"]) == {
        "single_family",
        "multi_family",
        "office",
        "school",
    }
    assert "systems" not in catalogue["dimensions"]
    assert all("system" not in cell and "lod1_complete" not in cell for cell in catalogue["cells"])
    assert all(package["lod"] == 2 for package in catalogue["packages"])
    cell = next(c for c in catalogue["cells"] if c["id"] == "multi_family:SE.02:SE.Zone3:existing")
    archetype = library.get("mf_se02", state="existing")
    assert (
        cell["u_values"]["wall"]
        == archetype.construction_set.elements[BuildingElement.EXT_WALL].u_value
    )
    assert cell["u_values"]["glazing"] == archetype.window.u_value
    assert all(
        sum(cell["zone"] == zone and cell["state"] == state for cell in catalogue["cells"])
        == (4 if state == "default" else 24)
        for zone in catalogue["dimensions"]["zones"]
        for state in catalogue["dimensions"]["states"]
    )


def test_completeness_matches_public_fabric_report(catalogue):
    from epsm_data import Catalogue

    library = Catalogue.load()
    packages = {package["id"]: package for package in catalogue["packages"]}
    for cell in catalogue["cells"]:
        slot = library.get_slot(cell["id"])
        report = library.completeness(slot.archetype_id, state=slot.state)
        package = packages[cell["package_id"]]
        assert cell["missing"] == list(report["missing_values"])
        assert cell["lod2_status"] == ("complete" if report["complete"] else "incomplete")
        assert package["lod2"]["archetype_id"] == slot.archetype_id
        assert package["construction_set_id"] == slot.construction_set_id
    assert (
        sum(cell["status"] == "incomplete" for cell in catalogue["cells"])
        == catalogue["summary"]["incomplete_slots"]
    )


@pytest.mark.parametrize("category", ["office", "school"])
@pytest.mark.parametrize("state", ["existing", "standard", "advanced"])
def test_basement_ceiling_is_not_displayed_as_soil_slab(catalogue, category, state):
    package = next(p for p in catalogue["packages"] if p["id"] == f"lod2:{category}_se01:{state}")
    slab = package["construction"]["BASEMENT_FLOOR"]
    ceiling = package["construction"]["GROUND_FLOOR"]
    assert package["u_values"]["ground"] == slab["u_value"]
    assert package["u_values"]["basement_ceiling"] == ceiling["u_value"]
    assert package["properties"]["ground_floor"]["value"] != package["properties"]["basement_ceiling"]["value"]
    layers = [layer for component in slab["components"] for layer in component["layers"]]
    assert len(layers) == 1 and layers[0]["thickness_mm"] == 100


def test_construction_payload_retains_material_properties_and_composites(catalogue):
    package = next(p for p in catalogue["packages"] if p["id"] == "lod2:mf_se02:existing")
    wall = package["construction"]["EXT_WALL"]
    assert wall["u_value"] is not None
    assert wall["components"]
    layers = [layer for component in wall["components"] for layer in component["layers"]]
    composite = next(layer for layer in layers if len(layer["materials"]) > 1)
    assert sum(material["area_fraction"] for material in composite["materials"]) == pytest.approx(1)
    material = composite["materials"][0]
    assert material["thermal_id"]
    assert material["thermal_properties"]["conductivity"] > 0
    assert material["thermal_properties"]["density"] > 0
    assert material["thermal_properties"]["specific_heat"] > 0
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
        if material["mapping_status"] == "non_product"
    )
    assert unmatched["gwp"] is None
    window = package["construction"]["WINDOW"]
    assert window["window"] and window["material"]["thermal_id"]


def test_external_sand_carbon_proxy_and_missing_modules_are_visible(catalogue):
    sand_uses = [
        (package, material)
        for package in catalogue["packages"]
        for assembly in package["construction"].values()
        for component in assembly.get("components", [])
        for layer in component["layers"]
        for material in layer["materials"]
        if material["id"] == "material:4857e866ed223064"
    ]
    assert len(sand_uses) == 6
    for package, material in sand_uses:
        assert material["mapping_status"] == "external"
        assert material["boverket_id"] is None
        reference = material["carbon_reference"]
        assert reference["identifier"] == "EPD-IES-0005222:003"
        assert reference["url"] == "https://www.environdec.com/library/epd5222"
        assert reference["proxy_for"]
        assert reference["modules"] == {"A1A3": 0.002, "A4": None, "A5": None}
        assert material["gwp"]["modules"] == reference["modules"]
        assert material["gwp"]["method"] == reference["method"]
        assert package["missing"] == []
        assert material["thermal_properties"]["conductivity"] == 0.4
        assert material["thermal_properties"]["density"] == 1600


@pytest.mark.parametrize("unit", ["m2", "m3", "item"])
def test_external_carbon_projection_preserves_quantity_unit(tmp_path, unit):
    from epsm_data import Catalogue

    config = Catalogue.load().resolved_dict()
    reference = config["carbon_references"]["EPD-IES-0005222:003"]
    reference["unit"] = unit
    reference["declared_unit"] = f"1 {unit}"
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    projected = load_data(path)
    material = next(
        material
        for package in projected["packages"]
        for assembly in package["construction"].values()
        for component in assembly.get("components", [])
        for layer in component["layers"]
        for material in layer["materials"]
        if material["id"] == "material:4857e866ed223064"
    )
    assert material["gwp"]["unit"] == f"kg CO2 eq./{unit}"
    assert material["carbon_reference"]["unit"] == unit
    assert material["gwp"]["modules"]["A1A3"] == 0.002


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
    from epsm_data import Catalogue

    path = tmp_path / "catalogue.json"
    config = Catalogue.load().to_dict()
    path.write_text(json.dumps(dict(reversed(list(config.items())))), encoding="utf-8")
    assert load_data(path) == catalogue
    material_users = {}
    for package in catalogue["packages"]:
        for assembly in package["construction"].values():
            for component in assembly.get("components", []):
                for layer in component["layers"]:
                    for material in layer["materials"]:
                        material_users.setdefault(material["id"], set()).add(package["id"])
    # Exercise both shared propagation and unaffected packages. The first
    # material may legitimately be concrete used by every configuration.
    material_id = next(
        identifier for identifier in sorted(material_users)
        if 1 < len(material_users[identifier]) < len(catalogue["packages"])
    )
    config["materials"][material_id]["epsm_material_name"] += " reviewed"
    path.write_text(json.dumps(config), encoding="utf-8")
    changed = load_data(path)
    assert changed["manifest"]["release_id"] != catalogue["manifest"]["release_id"]
    changed_packages = {package["id"]: package for package in changed["packages"]}
    affected = 0
    for before in catalogue["packages"]:
        uses_material = any(
            item["id"] == material_id
            for assembly in before["construction"].values()
            for component in assembly.get("components", [])
            for layer in component["layers"]
            for item in layer["materials"]
        )
        assert (before["revision"] != changed_packages[before["id"]]["revision"]) == uses_material
        affected += uses_material
    assert affected == len(material_users[material_id])
    assert 1 < affected < len(catalogue["packages"])


def test_static_app_assets_and_catalogue_endpoint(server, catalogue):
    assert request(server, "GET", "/api/catalogue")[1] == json.loads(json.dumps(catalogue))
    html = request(server, "GET", "/")[1].decode()
    assert "internal_wall" in html and "intermediate_floor" in html and "basement_wall" in html
    script = request(server, "GET", "/app.js")[1].decode()
    assert "LoD2 complete" in script
    assert "lod1_complete" not in script
    assert 'id="system"' not in html
    assert "Missing values" in script
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
  location: {hash: "#school%3ASE.06%3ASE.Zone2%3Aadvanced"},
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
  // SE.07 has no states; both filter directions must choose an actual cell.
  elements.get("state").value = "default"; elements.get("state").listeners.change();
  assert.match(context.location.hash, /school%3ASE.07%3ASE.Zone2%3Adefault/);
  assert.match(elements.get("count").textContent, /^4 of 28/);
  elements.get("zone").value = "SE.Zone1"; elements.get("zone").listeners.change();
  assert.match(context.location.hash, /SE.07%3ASE.Zone1%3Adefault/);
  elements.get("zone").value = "SE.Zone2"; elements.get("zone").listeners.change();
  elements.get("state").value = "advanced"; elements.get("state").listeners.change();
  assert.match(context.location.hash, /school%3ASE.06%3ASE.Zone2%3Aadvanced/);
  assert.match(elements.get("lod2-total").textContent, new RegExp(`${input.catalogue.summary.complete_slots} complete · ${input.catalogue.summary.incomplete_slots} incomplete assignments`));
  assert.ok((elements.get("matrix").innerHTML.match(/class="lod2-tick"/g) || []).length > 0);
  assert.match(elements.get("count").textContent, /^28 of 28/);
  assert.equal((elements.get("matrix").innerHTML.match(/data-cell=/g) || []).length, 28);
  assert.doesNotMatch(elements.get("matrix").innerHTML, /No LoD2 recipe/);
  assert.match(elements.get("detail").innerHTML, /School.*2006–2021/);
  assert.equal((elements.get("detail-content").innerHTML.match(/class="metric"/g) || []).length, 7);
  assert.match(elements.get("detail-content").innerHTML, /calculated forward/);
  elements.get("metric").value = "internal_wall";
  elements.get("metric").listeners.change();
  assert.equal((elements.get("matrix").innerHTML.match(/<strong>—<\/strong>/g) || []).length, 0);
  assert.equal((elements.get("matrix").innerHTML.match(/background:#e8eaed/g) || []).length, 0);
  // Partial caller-supplied catalogues must still show missing values clearly.
  vm.runInContext(`
    globalThis.pendingCell = data.cells.find(c => c.category === "single_family" && visible(c));
    globalThis.savedValue = pendingCell.u_values.internal_wall;
    pendingCell.u_values.internal_wall = null;
    renderMatrix();
  `, context);
  assert.equal((elements.get("matrix").innerHTML.match(/<strong>—<\/strong>/g) || []).length, 1);
  assert.equal((elements.get("matrix").innerHTML.match(/background:#e8eaed/g) || []).length, 1);
  vm.runInContext('pendingCell.u_values.internal_wall = savedValue; renderMatrix();', context);
  elements.get("search").value = "2030"; elements.get("search").listeners.input();
  assert.match(elements.get("count").textContent, /^4 of 28/);
  elements.get("search").value = "not-a-category"; elements.get("search").listeners.input();
  assert.match(elements.get("matrix").innerHTML, /colspan="8"/);
  elements.get("reset").click();
  assert.match(context.location.hash, /multi_family/);
  assert.doesNotMatch(elements.get("detail-content").innerHTML, /Pending:/);
  vm.runInContext('tab = "layers"; renderDetail();', context);
  assert.match(elements.get("detail-content").innerHTML, /LoD2 complete/);
  assert.match(elements.get("detail-content").innerHTML, /Missing values/);
  assert.match(elements.get("detail-content").innerHTML, /Honeybee ID|HBJSON thermal properties/);
  vm.runInContext('selectCell(cellsById.get("office:SE.05:SE.Zone3:existing"));', context);
  elements.get("metric").value = "top"; elements.get("metric").listeners.change();
  assert.match(elements.get("detail-content").innerHTML, /Roof composition/);
  assert.doesNotMatch(elements.get("detail-content").innerHTML, /No layer recipe/);
  vm.runInContext('selectCell(cellsById.get("office:SE.01:SE.Zone3:existing"));', context);
  assert.match(elements.get("detail-content").innerHTML, /LoD2 complete/);
  elements.get("metric").value = "intermediate_floor"; elements.get("metric").listeners.change();
  assert.match(elements.get("detail-content").innerHTML, /Layer order: bottom to top/);
  vm.runInContext(`globalThis.floorDrawing = sectionSvg("INTERMEDIATE_FLOOR", packages.get(activePackage).construction.INTERMEDIATE_FLOOR, "room-side-test");`, context);
  const finish = [...context.floorDrawing.matchAll(/<rect[^>]+y="([^"]+)%"[^>]*><title>([^<]+)<\/title>/g)].find(m => /linoleum/i.test(m[2]));
  const lining = [...context.floorDrawing.matchAll(/<rect[^>]+y="([^"]+)%"[^>]*><title>([^<]+)<\/title>/g)].find(m => /plaster/i.test(m[2]));
  assert.ok(finish && lining, "Real office floor needs upper finish and lower lining");
  assert.ok(Number(finish[1]) < Number(lining[1]), "Floor finish must be drawn above ceiling lining");
  assert.match(elements.get("detail-content").innerHTML, /Carbon proxy:/);
  assert.match(elements.get("detail-content").innerHTML, /External carbon · EPD-IES-0005222:003/);
  assert.match(elements.get("detail-content").innerHTML, /href="https:\/\/www.environdec.com\/library\/epd5222"/);
  assert.match(elements.get("detail-content").innerHTML, /Method: GWP-GHG/);
  assert.match(elements.get("detail-content").innerHTML, /0.00200 kg CO2 eq.\/kg/);
  assert.match(elements.get("detail-content").innerHTML, /A4 transport<\/dt><dd>Not declared/);
  assert.match(elements.get("detail-content").innerHTML, /A5 installation<\/dt><dd>Not declared/);
  assert.match(elements.get("detail-content").innerHTML, /A4 and A5 are not declared/);
  assert.doesNotMatch(elements.get("detail-content").innerHTML, /Boverket unmatched|No matched Boverket resource/);
  // Omitted required modules remain visible, alongside additional supplied modules.
  vm.runInContext(`
    globalThis.sandRecord = packages.get(activePackage).construction.INTERMEDIATE_FLOOR.components
      .flatMap(c => c.layers).flatMap(l => l.materials)
      .find(m => m.id === "material:4857e866ed223064");
    globalThis.savedModules = sandRecord.carbon_reference.modules;
    sandRecord.carbon_reference.modules = {A1A3: 0.002, D: -0.001};
    renderDetail();
  `, context);
  assert.match(elements.get("detail-content").innerHTML, /A4 transport<\/dt><dd>Not declared/);
  assert.match(elements.get("detail-content").innerHTML, /A5 installation<\/dt><dd>Not declared/);
  assert.match(elements.get("detail-content").innerHTML, /<dt>D<\/dt><dd>-0.00100 kg CO2 eq.\/kg/);
  vm.runInContext('sandRecord.carbon_reference.modules = savedModules; renderDetail();', context);
  vm.runInContext('selectCell(cellsById.get("multi_family:SE.02:SE.Zone3:existing"));', context);
  vm.runInContext('tab = "record"; renderDetail();', context);
  assert.match(elements.get("detail-content").innerHTML, /Resolved construction record/);
  assert.doesNotMatch(elements.get("detail-content").innerHTML, /Scaling factor|Nominal U-value alignment/);
  vm.runInContext('tab = "notes"; renderDetail();', context);
  elements.get("body").value = "Review <script> safely";
  elements.get("author").value = "Tester"; elements.get("kind").value = "question";
  await elements.get("note-form").onsubmit({preventDefault() {}});
  assert.equal(stored.length, 2);
  assert.equal(stored[1].cell_id, "multi_family:SE.02:SE.Zone3:existing");
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
