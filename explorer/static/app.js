"use strict";
const $ = (s, root = document) => root.querySelector(s);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const names = {
  single_family: "SF",
  multi_family: "MF",
  office: "Office",
  generic: "Generic",
  internal_wall: "Internal wall",
  ground_floor: "Ground floor",
  external_wall: "External wall",
  roof: "Roof / top",
  window: "Window",
  infiltration: "Infiltration",
  lod1_pending: "LoD1 pending",
  lod1_complete: "LoD1 complete",
  school: "School",
  hospital: "Hospital",
  industrial: "Industrial",
  other: "Other",
  existing: "Existing",
  standard: "Standard renovation",
  advanced: "Advanced renovation",
  wall: "External wall",
  top: "Roof / top",
  ground: "Ground floor",
  glazing: "Windows",
  basement_wall: "Basement wall",
  basement_ceiling: "Basement ceiling",
  intermediate_floor: "Internal floor nominal U",
  weather_shell: "Weather shell",
  dwelling_partition: "Dwelling partition",
  common_partition: "Common partition",
  door: "Door",
  heavy_frame: "Heavy frame",
  light_frame: "Light frame",
  timber_frame: "Timber frame",
  assumed_layers: "Assumed layers",
  remark: "Remark",
  question: "Question",
  issue: "Needs attention",
  S: "S · Natural",
  F: "F · Mechanical exhaust",
  FT: "FT · Supply & exhaust",
  FTX: "FTX · Heat recovery",
};
const label = (v) => names[v] || String(v).replaceAll("_", " ");
const lod2Label = (status) => ({
  complete: "LoD2 complete",
  draft: "LoD2 draft",
  no_recipe: "No LoD2 recipe",
})[status] || "LoD2 status unknown";
const checkNames = {
  construction_builder_supported: "Construction builder supported",
  construction_schema: "Construction schema",
  honeybee_material_references: "Honeybee material references",
  boverket_material_references: "Boverket material references",
  boverket_intervention_scope_references: "Boverket references: intervention scope (retained fill unmapped)",
  captured_targets_unchanged: "Captured LoD1 targets unchanged",
  no_open_blocking_catalogue_caveats: "No blocking catalogue caveats",
  thermal_and_optical_evidence_reviewed: "Thermal and optical evidence reviewed",
  nominal_u_alignment: "Nominal U-value alignment",
  honeybee_nominal_export: "Honeybee nominal export",
  core_nominal_export: "Core nominal export",
  classification_slots_validated: "Classification slots validated",
  selected_replacement_window: "Selected replacement window matches target Uw",
  ground_validation: "Ground validation",
  carbon_assessment: "Carbon assessment",
  simulation: "Simulation",
};
const checkLabel = (key) => checkNames[key] || label(key);
const fmt = (v, digits = 2) => (Number.isFinite(v) ? v.toFixed(digits) : "—");
const eraLabel = (era) => {
  const [a, b] = data.dimensions.eras[era];
  return a === 1 ? `≤ ${b}` : `${a}–${b ?? "present"}`;
};
const packageKey = (id, rev) => `${id}@${rev}`;
let drawingSequence = 0;
let data,
  packages,
  cellsById,
  selected,
  activePackage,
  tab = "overview",
  notes = [],
  editing = null,
  toastTimer,
  busy = false;
const drafts = new Map();
let filters = {
  zone: "SE.Zone3",
  state: "existing",
  system: "F",
  search: "",
  noted: false,
  metric: "wall",
};
async function api(path, options = {}) {
  const r = await fetch(path, {
    cache: "no-store",
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  let result;
  try {
    result = await r.json();
  } catch {
    throw new Error(
      "The app could not read the server response. Please retry.",
    );
  }
  if (!r.ok)
    throw new Error(result.error || "The request failed. Please retry.");
  return result;
}
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("#toast").hidden = true), 3500);
}
function options(values, text) {
  return values
    .map((v) => `<option value="${esc(v)}">${esc(text(v))}</option>`)
    .join("");
}
function saveDraft() {
  const form = $("#note-form");
  if (form && selected) {
    if (!$("#body").value.trim() && !editing) {
      drafts.delete(selected.id);
      return;
    }
    drafts.set(selected.id, {
      body: $("#body").value,
      author: $("#author").value,
      kind: $("#kind").value,
      editing,
      package_id:
        drafts.get(selected.id)?.package_id || packages.get(activePackage)?.id,
      revision:
        drafts.get(selected.id)?.revision ||
        packages.get(activePackage)?.revision,
    });
  }
}
function selectCell(cell) {
  if (busy) return;
  saveDraft();
  selected = cell;
  activePackage = packageKey(cell.package_id, cell.revision);
  editing = null;
  history.replaceState(null, "", `#${encodeURIComponent(cell.id)}`);
  renderMatrix();
  renderDetail();
  if (matchMedia("(max-width:1100px)").matches)
    $(".detail-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}
function visible(cell) {
  if (
    cell.zone !== filters.zone ||
    cell.state !== filters.state ||
    cell.system !== filters.system
  )
    return false;
  if (filters.noted && !notes.some((n) => n.cell_id === cell.id)) return false;
  const q = filters.search.trim().toLowerCase();
  if (!q) return true;
  if (/^\d{4}$/.test(q)) {
    const y = Number(q),
      [a, b] = data.dimensions.eras[cell.era];
    return y >= a && (b == null || y <= b);
  }
  return `${cell.id} ${label(cell.category)} ${eraLabel(cell.era)} ${label(cell.family || "")}`
    .toLowerCase()
    .includes(q);
}
function renderMatrix() {
  const shown = data.cells.filter(visible);
  const index = new Map(shown.map((c) => [`${c.category}|${c.era}`, c]));
  $("#count").textContent = `${shown.length} of ${data.dimensions.categories.length * Object.keys(data.dimensions.eras).length} cells in this slice`;
  $("#slice-context").textContent =
    `${filters.zone.replace("SE.", "")} · TABULA climate zones · ${label(filters.system)} ventilation`;
  const counts = new Map();
  notes.forEach((n) => counts.set(n.cell_id, (counts.get(n.cell_id) || 0) + 1));
  $("#matrix").innerHTML =
    `<thead><tr><th scope="col">Building type <small>Construction era →</small></th>${Object.keys(
      data.dimensions.eras,
    )
      .map(
        (e) =>
          `<th scope="col">${eraLabel(e)}<small>${esc(e.replace("EPSM.", ""))}</small></th>`,
      )
      .join("")}</tr></thead><tbody>${data.dimensions.categories
      .map(
        (cat) =>
          `<tr><th scope="row">${label(cat)}</th>${Object.keys(
            data.dimensions.eras,
          )
            .map((era) => {
              const c = index.get(`${cat}|${era}`);
              if (!c) return '<td class="empty-cell"></td>';
              const v = c.u_values[filters.metric];
              const t = Math.max(0, Math.min(1, (v ?? 0) / 3));
              const bg = Number.isFinite(v) ? `hsl(177 38% ${94 - t * 62}%)` : "#e8eaed";
              const foreground = t > 0.925 ? "#ffffff" : "#000000";
              return `<td><button class="cell ${selected?.id === c.id ? "selected" : ""}" style="background:${bg};color:${foreground}" data-cell="${esc(c.id)}" aria-pressed="${selected?.id === c.id}" aria-label="${esc(`${label(cat)}, ${eraLabel(era)}, ${label(filters.metric)} U-value ${fmt(v)} W per square metre kelvin, ${lod2Label(c.lod2_status)}, ${counts.get(c.id) || 0} remarks`)}">${c.lod2_status === "complete" ? '<span class="lod2-tick" aria-hidden="true">✓</span>' : ""}${counts.has(c.id) ? '<span class="note-dot" aria-hidden="true">●</span>' : ""}<strong>${fmt(v)}</strong><small>${c.lod1_complete ? "LoD1 complete" : `${8 - c.missing.length}/8 properties`}</small><small class="cell-lod2">${lod2Label(c.lod2_status)}</small></button></td>`;
            })
            .join("")}</tr>`,
      )
      .join(
        "",
      )}</tbody>${!shown.length ? `<tfoot><tr><td colspan="${Object.keys(data.dimensions.eras).length + 1}" class="no-results">No archetypes match. Try another search or clear “With remarks”.</td></tr></tfoot>` : ""}`;
  $$("[data-cell]").forEach(
    (b) => (b.onclick = () => selectCell(cellsById.get(b.dataset.cell))),
  );
}
function $$(s, root = document) {
  return [...root.querySelectorAll(s)];
}
function evidence(e, title = "Evidence") {
  if (!e) return "";
  return `<div class="evidence"><strong>${esc(title)}</strong><p>${esc(e.rationale || label(e.evidence_kind || ""))}</p><small>${esc(e.source_id)} · ${esc(e.locator || "")}<br>${esc(label(e.evidence_kind || ""))}${e.confidence ? ` · ${esc(e.confidence)} confidence` : ""}</small></div>`;
}
function facts(entries) {
  return `<dl class="facts">${entries.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>`;
}
function metrics(p) {
  return `<dl class="metrics">${Object.entries(p.properties).map(([role, prop]) =>
    `<div class="metric"><dt>${label(role)}</dt><dd>${fmt(prop.value)} <small>${esc(prop.unit)}</small></dd></div>`
  ).join("")}</dl>`;
}
function schoolWindowProfile(p) {
  if (selected.category !== "school" || !["school.window", "calibrated.school.window", "v1.school.window", "v1_1.school.window"].includes(p.properties.window?.curve)) return "";
  const source = data.sources.find((item) => item.id === p.properties.window.curve_source);
  const rows = Object.keys(data.dimensions.eras).map((era) => {
    const period = data.packages.find((item) => item.id === `parametric:school:${era}:${selected.state}`);
    if (!period) return "";
    return `<tr class="${era === selected.era ? "current" : ""}"><th scope="row">${esc(era)} · ${esc(eraLabel(era))}</th><td>${fmt(period.properties.window?.value, 3)}</td></tr>`;
  }).join("");
  return `<section class="school-window-profile" aria-labelledby="school-window-profile-title"><h3 id="school-window-profile-title">School window profile</h3><p class="muted">Representative whole-window U-values for ${esc(label(selected.state))}. The same construction values apply across climate zones and ventilation classes.</p><table class="profile-table"><caption>Window U-value · W/(m²·K)</caption><thead><tr><th scope="col">Construction era</th><th scope="col">Uw</th></tr></thead><tbody>${rows}</tbody></table><p class="muted">${esc(source?.title || p.properties.window.curve_source)}. ${esc(source?.version || "")}</p></section>`;
}
function lod2Overview(p) {
  const lod2 = p.lod2;
  if (lod2.status === "no_recipe") {
    return "<h3>Catalogue LoD2</h3><p>No layer recipe has been authored for this archetype.</p>";
  }
  const passed = Object.values(lod2.checks).filter(Boolean).length;
  const total = Object.keys(lod2.checks).length;
  return `<h3>Catalogue LoD2</h3><p><strong>${lod2Label(lod2.status)}.</strong> ${passed} of ${total} acceptance checks pass. <a href="#tab-layers" data-open-lod2>Review LoD2 checks</a>.</p>`;
}
function lod2Details(p) {
  const lod2 = p.lod2;
  if (lod2.status === "no_recipe") {
    return "<h3>No LoD2 recipe</h3><p>No detailed layer construction is recorded for this archetype. The LoD1 effective values shown in Overview do not establish a physical layer assembly.</p>";
  }
  const checks = Object.entries(lod2.checks).map(([key, passed]) =>
    `<li class="check ${passed ? "pass" : "fail"}"><span aria-hidden="true">${passed ? "✓" : "×"}</span><span>${esc(checkLabel(key))}</span><strong>${passed ? "Pass" : "Open"}</strong></li>`
  ).join("");
  const readiness = Object.entries(lod2.readiness).map(([key, ready]) =>
    `<li class="check ${ready ? "pass" : "fail"}"><span aria-hidden="true">${ready ? "✓" : "×"}</span><span>${esc(checkLabel(key))}</span><strong>${ready ? "Ready" : "Pending"}</strong></li>`
  ).join("");
  const alternatives = lod2.alternatives?.length
    ? `<h4>Named alternatives</h4><ul>${lod2.alternatives.map((variant) => `<li>${esc(variant.archetype_id)}: ${lod2Label(variant.status)} against the same LoD1 targets; no extra catalogue slots.</li>`).join("")}</ul>`
    : "";
  const role = metricRoles[filters.metric];
  const available = Object.keys(p.construction || {}).length > 0;
  return `<h3>${lod2Label(lod2.status)}</h3><p class="muted">Detailed archetype: ${esc(lod2.archetype_id)}. This is the catalogue acceptance status for its layer recipe.</p>${constructionDetails(p.construction || {}, role)}${available ? '<button type="button" class="button primary" id="open-archetype">Open full archetype</button>' : ""}<h4>Acceptance checks</h4><ul class="check-list">${checks}</ul>${alternatives}<h4>Downstream readiness</h4><p class="muted">Nominal export is separate from validated ground, carbon, and simulation readiness.</p><ul class="check-list">${readiness}</ul>${lod2.blocking_caveats ? `<p><strong>${lod2.blocking_caveats} blocking catalogue caveats</strong> remain open.</p>` : ""}${lod2.pending_boverket_references?.length ? `<p>Pending Boverket references: ${esc(lod2.pending_boverket_references.join(", "))}.</p>` : ""}<details class="source-details"><summary>Remaining limitations (${lod2.remaining.length})</summary><ul>${lod2.remaining.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></details>`;
}
const elementNames = { TOP_FLOOR: "Attic floor", EXT_WALL: "External wall", INTERMEDIATE_FLOOR: "Intermediate floor", GROUND_FLOOR: "Ground floor", BASEMENT_WALL: "Basement wall", BASEMENT_FLOOR: "Basement floor", INT_WALL_LOADBEARING: "Loadbearing internal wall", INT_WALL_NONLOADBEARING: "Internal partition", WINDOW: "Window" };
const metricRoles = { wall: "EXT_WALL", top: "TOP_FLOOR", ground: "GROUND_FLOOR", glazing: "WINDOW", intermediate_floor: "INTERMEDIATE_FLOOR", internal_wall: "INT_WALL_NONLOADBEARING", basement_wall: "BASEMENT_WALL" };
const hatchStyles = [
  ["air gap", "#fff", "#78909c", ""], ["acoustic", "#d5e1e8", "#708a99", "dots"],
  ["linoleum", "#879ba0", "#465d62", ""], ["brick", "#c8785a", "#7a3b20", "cross"],
  ["expanded plastic", "#e8f0ff", "#7090c0", "circles"], ["light insulation", "#fff7d9", "#b59a52", "diagonal"],
  ["under felt", "#404040", "#202020", ""], ["wood-fibre", "#dfcba1", "#927d55", "dots"],
  ["woodfiber", "#dfcba1", "#927d55", "dots"], ["rubber", "#879ba0", "#465d62", ""],
  ["leca", "#d8c6b3", "#8d7258", "circles"], ["lightweight concrete", "#d0d0d0", "#8a8a8a", "dots"],
  ["stone wool", "#fff7d9", "#b59a52", "diagonal"],
  ["eps", "#e8f0ff", "#7090c0", "circles"], ["xps", "#d5e7f5", "#5681a0", "circles"],
  ["mortar", "#e8e0d0", "#968870", ""], ["plaster", "#e8e0d0", "#968870", ""],
  ["mineral wool", "#fff7d9", "#b59a52", "diagonal"], ["stucco", "#e8e0d0", "#968870", ""],
  ["concrete block", "#bcbcbc", "#6b6b6b", "dots"],
  ["concrete floor", "#bcbcbc", "#6b6b6b", "dots"], ["concrete roof", "#bcbcbc", "#6b6b6b", "dots"],
  ["concrete wall", "#bcbcbc", "#6b6b6b", "dots"], ["concrete", "#bcbcbc", "#6b6b6b", "dots"],
  ["gypsum", "#f5f0e8", "#a09880", ""], ["plywood", "#ddb87a", "#8b6914", "wood"],
  ["wood", "#e8c882", "#8b6914", "wood"], ["insulation board", "#e8f0ff", "#7090c0", "circles"],
  ["built-up roofing", "#404040", "#202020", ""], ["roofing", "#404040", "#202020", ""],
];
function hatchStyle(name) {
  const lower = String(name || "").toLowerCase();
  const found = hatchStyles.find(([fragment]) => lower.includes(fragment));
  return found ? found.slice(1) : ["#e0e0e0", "#888", ""];
}
function patternSvg(id, color, edge, hatch) {
  const marks = {
    dots: `<circle cx="10" cy="10" r="1.4" fill="${edge}"/><circle cx="30" cy="30" r="1.4" fill="${edge}"/>`,
    diagonal: `<path d="M-8 32L32-8M8 48L48 8" stroke="${edge}" stroke-width="1.15"/>`,
    cross: `<path d="M-8-8L48 48M48-8L-8 48" stroke="${edge}" stroke-width="1.1"/>`,
    circles: `<circle cx="11" cy="11" r="3" fill="none" stroke="${edge}" stroke-width="1.1"/><circle cx="31" cy="31" r="3" fill="none" stroke="${edge}" stroke-width="1.1"/>`,
    wood: `<path d="M0 12H40M0 32H40" stroke="${edge}" stroke-width="1.1"/>`,
  }[hatch] || "";
  return `<pattern id="${id}" width="40" height="40" patternUnits="userSpaceOnUse"><rect width="40" height="40" fill="${color}"/>${marks}</pattern>`;
}
function roleLayers(assembly) {
  if (assembly?.window) return [];
  const layers = (assembly?.components || []).flatMap((component) => component.layers || []);
  const cavity = assembly?.boundary_details?.facade_cavity;
  if (cavity) layers.splice(cavity.after_layer ?? 1, 0, {
    name: cavity.ventilation === "sealed_existing_cavity_assumption" ? "Sealed existing cavity" : "Drained cavity",
    thickness_mm: cavity.thickness_m * 1000, materials: [], cavity: true,
  });
  return layers;
}
function sectionSvg(role, assembly, prefix) {
  const layers = roleLayers(assembly);
  const total = layers.reduce((sum, layer) => sum + layer.thickness_mm, 0);
  if (!layers.length || !(total > 0)) return "";
  const wall = ["EXT_WALL", "BASEMENT_WALL", "INT_WALL_LOADBEARING", "INT_WALL_NONLOADBEARING"].includes(role);
  const topFirst = ["TOP_FLOOR", "INTERMEDIATE_FLOOR"].includes(role);
  const patterns = new Map();
  let cursor = 0;
  const rects = layers.map((layer, li) => {
    const x = wall ? cursor / total * 100 : 0;
    const y = wall ? 10 : 10 + (topFirst ? cursor : total - cursor - layer.thickness_mm) / total * 76;
    const w = wall ? layer.thickness_mm / total * 100 : 100;
    const h = wall ? 76 : layer.thickness_mm / total * 76;
    const mats = layer.materials?.length ? layer.materials : [{ name: layer.name, area_fraction: 1 }];
    const divisionCount = mats.length > 1 ? 5 : 1;
    const pieces = [];
    for (let div = 0; div < divisionCount; div++) {
      let materialCursor = 0;
      for (const material of mats) {
        const fraction = material.area_fraction ?? 1 / mats.length;
        const share = fraction / divisionCount;
        const [color, edge, hatch] = layer.cavity ? ["#fff", "#78909c", ""] : hatchStyle(material.name);
        const key = `${prefix}-${li}-${patterns.size}`;
        patterns.set(key, patternSvg(key, color, edge, hatch));
        const px = wall ? x : (div / divisionCount + materialCursor / divisionCount) * 100;
        const py = wall ? 10 + (div / divisionCount + materialCursor / divisionCount) * 76 : y;
        const pw = wall ? w : share * 100;
        const ph = wall ? share * 76 : h;
        pieces.push(`<rect x="${px}%" y="${py}%" width="${pw}%" height="${ph}%" fill="url(#${key})" stroke="${edge}" stroke-width="1"><title>${esc(material.name || layer.name)} · ${fmt(layer.thickness_mm, 0)} mm${material.area_fraction != null ? ` · ${fmt(material.area_fraction * 100, 0)}%` : ""}</title></rect>`);
        materialCursor += fraction;
      }
    }
    cursor += layer.thickness_mm;
    return pieces.join("");
  }).join("");
  const edge = wall ? `<text x="0" y="15" font-size="14" fill="#526372">${role.startsWith("INT_") ? "ROOM A" : "OUTSIDE"}</text><text x="1000" y="15" text-anchor="end" font-size="14" fill="#526372">${role.startsWith("INT_") ? "ROOM B" : "ROOM"}</text>` : "";
  return `<svg class="layer-section hatched-section ${wall ? "wall-section" : "floor-section"}" viewBox="0 0 1000 220" role="img" aria-label="Hatched cross-section of ${esc(elementNames[role] || label(role))}, ${layers.length} layers, ${fmt(total, 0)} millimetres"><defs>${[...patterns.values()].join("")}</defs>${edge}${rects}</svg>`;
}
function materialDetails(material) {
  const hb = material.honeybee_properties || {};
  const propertyNames = { roughness: "Roughness", conductivity: "Conductivity λ (W/(m·K))", density: "Density (kg/m³)", specific_heat: "Specific heat (J/(kg·K))", thermal_absorptance: "Thermal absorptance", solar_absorptance: "Solar absorptance", visible_absorptance: "Visible absorptance", u_value: "U-value (W/(m²·K))", shgc: "SHGC", vt: "Visible transmittance" };
  const propertyRows = Object.entries(hb).map(([key, value]) => `<div><dt>${esc(propertyNames[key] || label(key))}</dt><dd>${esc(typeof value === "number" ? fmt(value, 4) : value ?? "Unavailable")}</dd></div>`).join("");
  const gwp = material.gwp;
  const gwpRows = gwp ? [["A1–A3 typical", gwp.A1_A3_typical], ["A1–A3 conservative", gwp.A1_A3_conservative], ["A4 transport", gwp.A4_transport], ["A5 conservative", gwp.A5_conservative]].map(([name, value]) => `<div><dt>${name}</dt><dd>${value == null ? "Unavailable" : `${fmt(value, 5)} ${esc(gwp.unit)}`}</dd></div>`).join("") : "<div><dt>Retrieved values</dt><dd>Unavailable</dd></div>";
  return `<details class="material-facts"><summary>${esc(material.name)} · ${esc(material.honeybee_id || "Honeybee ID unavailable")} · Boverket ${esc(material.boverket_id || "unmatched")}</summary><p class="muted">${esc(material.boverket_name || "No matched Boverket resource")} · ${esc(label(material.mapping_status || "unmatched"))}</p>${propertyRows ? `<h6>HBJSON thermal properties</h6><dl class="material-property-grid">${propertyRows}</dl>` : "<p class=\"muted\">HBJSON properties unavailable.</p>"}<h6>Boverket GWP · retrieved values</h6><dl class="material-property-grid">${gwpRows}</dl></details>`;
}
function wholeWindowDefinition(assembly) {
  const props = assembly.material?.honeybee_properties || {};
  const uValue = assembly.u_value ?? props.u_value;
  return `<div class="whole-window-definition"><strong>Whole-window definition</strong><dl><div><dt>U-value</dt><dd>${uValue == null ? "Unavailable" : `${fmt(uValue, 2)} W/(m²·K)`}</dd></div><div><dt>Solar gain · SHGC</dt><dd>${props.shgc == null ? "Unavailable" : fmt(props.shgc, 2)}</dd></div><div><dt>Visible transmittance · VT</dt><dd>${props.vt == null ? "Unavailable" : fmt(props.vt, 2)}</dd></div></dl><p>Frame dimensions and pane layers are unspecified.</p></div>`;
}
function constructionDetails(construction, role, { full = false } = {}) {
  const entries = full ? Object.entries(construction).sort(([a], [b]) => {
    const order = ["TOP_FLOOR", "EXT_WALL", "INTERMEDIATE_FLOOR", "GROUND_FLOOR", "BASEMENT_WALL", "BASEMENT_FLOOR", "INT_WALL_LOADBEARING", "INT_WALL_NONLOADBEARING", "WINDOW"];
    return order.indexOf(a) - order.indexOf(b);
  }) : (construction[role] ? [[role, construction[role]]] : []);
  if (!entries.length) return `<h4>${full ? "Full archetype" : "Selected construction"}</h4><p class="muted">${full ? "No detailed layer recipe is available." : `No layer recipe is available for ${esc(elementNames[role] || label(role))}.`}</p>`;
  return `<section class="construction-details ${full ? "full-construction" : "selected-construction"}">${full ? "" : `<h3>${esc(elementNames[role] || label(role))} composition</h3>`}${entries.map(([entryRole, assembly]) => {
    const layers = roleLayers(assembly), total = layers.reduce((sum, layer) => sum + layer.thickness_mm, 0);
    const componentLists = assembly.components || [];
    const list = componentLists.map((component) => `<div class="component-block"><h5>${esc(component.name)}${component.shearing_layer ? ` · ${esc(label(component.shearing_layer))}` : ""}</h5><ol class="layer-list">${component.layers.map((layer) => `<li><span><strong>${esc(layer.name)}</strong><small>${fmt(layer.thickness_mm, 0)} mm</small>${layer.materials.map((material) => `<span class="material-share">${esc(material.name)}${material.area_fraction != null && layer.materials.length > 1 ? ` · ${fmt(material.area_fraction * 100, 0)}% area` : ""}</span>${materialDetails(material)}`).join("")}</span></li>`).join("")}</ol></div>`).join("");
    const cavity = assembly.boundary_details?.facade_cavity;
    const cavityDetails = cavity ? `<p class="muted cavity-note">${cavity.ventilation === "sealed_existing_cavity_assumption" ? "Sealed existing cavity" : "Drained facade cavity"} · ${fmt(cavity.thickness_m * 1000, 0)} mm · section depth shown; no separate material record.</p>` : "";
    const windowMaterial = assembly.window ? materialDetails(assembly.material) : "";
    return `<article class="construction-card"><h4>${esc(elementNames[entryRole] || label(entryRole))}${assembly.u_value != null ? ` <small>· U ${fmt(assembly.u_value, 3)} W/(m²·K)</small>` : ""}</h4><p class="muted">${esc(assembly.name)}${total ? ` · ${fmt(total, 0)} mm total` : ""}</p>${assembly.window ? `${wholeWindowDefinition(assembly)}${windowMaterial}` : `${sectionSvg(entryRole, assembly, `draw-${++drawingSequence}`)}<p class="muted layer-order-note">${["EXT_WALL", "BASEMENT_WALL", "INT_WALL_LOADBEARING", "INT_WALL_NONLOADBEARING"].includes(entryRole) ? "Layer order: left to right · composites repeat five divisions." : "Layer order: from top to bottom · composites repeat five divisions."}</p>${cavityDetails}${list}`}</article>`;
  }).join("")}</section>`;
}
function closeArchetypeDialog() {
  const dialog = $("#archetype-dialog");
  if (typeof dialog.close === "function" && dialog.open) dialog.close();
  else dialog.removeAttribute("open");
  document.body.classList.remove("dialog-open");
  $("#app").inert = false;
  dialog._returnFocus?.focus();
  dialog._returnFocus = null;
}
function openArchetypeDialog(dialog, trigger, p) {
  $("#archetype-dialog-title").textContent = `${label(selected.category)} · ${eraLabel(selected.era)} · ${label(selected.state)} archetype`;
  $("#archetype-dialog-subtitle").textContent = `${p.lod2.archetype_id} · ${selected.zone.replace("SE.", "")} · ${label(selected.system)}`;
  $("#archetype-dialog-content").innerHTML = constructionDetails(p.construction || {}, null, { full: true });
  dialog._returnFocus = trigger;
  $("#app").inert = true;
  document.body.classList.add("dialog-open");
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
  $("#close-archetype").focus();
}
function floorReview(p) {
  if (!p.floor_review) return "";
  const f = p.floor_review;
  return `<h3>Representative internal floor</h3><p>${esc(f.family)}.</p><p class="muted">Upper room to lower room. Nominal U describes the internal assembly, not outdoor heat loss. Material heat capacity: ${fmt(f.thermal_mass_kj_m2k, 1)} kJ/(m²·K). Applied only where geometry has an intermediate floor.</p>${f.fill_depth_m ? `<p>Joist depth: ${fmt(f.joist_depth_m * 1000, 0)} mm; fill: ${fmt(f.fill_depth_m * 1000, 0)} mm; air cavity: ${fmt(f.cavity_depth_m * 1000, 0)} mm. Fixed cavity resistance: ${fmt(f.cavity_nominal_r_m2k_w, 2)} m²·K/W.</p><p class="muted">${esc(f.evidence_limit)}</p>` : ""}${p.generic_donor ? `<p><strong>Generic fallback:</strong> complete ${esc(p.generic_donor)} construction set. This is an MF-based assumption, not a national stock average.</p>` : ""}`;
}
function renderDetail() {
  if (!selected) return;
  const p = packages.get(activePackage);
  const count = notes.filter((n) => n.cell_id === selected.id).length;
  $("#detail").innerHTML = `<div class="detail-header"><p class="eyebrow">SELECTED ARCHETYPE</p><h2>${label(selected.category)} <span style="font-weight:400">· ${eraLabel(selected.era)}</span></h2><p class="detail-subtitle">${selected.zone.replace("SE.", "")} / ${label(selected.state)} / ${selected.system}</p><span class="badge ${p.lod1_complete ? "" : "amber"}">${label(p.status)}</span> <span class="badge lod2-${p.lod2.status}">${lod2Label(p.lod2.status)}</span><p class="id-line">${esc(selected.id)}</p></div><div class="tabs" role="tablist" aria-label="Archetype details">${[
    ["overview", "Overview"], ["layers", "LoD2"], ["evidence", "Evidence"],
    ["notes", `Remarks${count ? ` (${count})` : ""}`],
  ].map(([key, title]) => `<button class="tab" role="tab" id="tab-${key}" aria-controls="detail-content" tabindex="${key === tab ? "0" : "-1"}" aria-selected="${key === tab}" data-tab="${key}">${title}</button>`).join("")}</div><div class="detail-body" id="detail-content" role="tabpanel" tabindex="0" aria-labelledby="tab-${tab}"></div>`;
  $$("[data-tab]").forEach((b, i, buttons) => {
    b.onclick = () => {
      if (busy) return;
      saveDraft();
      tab = b.dataset.tab;
      renderDetail();
      $(`[data-tab="${tab}"]`).focus();
    };
    b.onkeydown = (e) => {
      let next;
      if (e.key === "ArrowRight") next = (i + 1) % buttons.length;
      if (e.key === "ArrowLeft") next = (i + buttons.length - 1) % buttons.length;
      if (e.key === "Home") next = 0;
      if (e.key === "End") next = buttons.length - 1;
      if (next !== undefined) { e.preventDefault(); buttons[next].click(); }
    };
  });
  const body = $("#detail-content");
  if (tab === "notes") { renderNotes(body); return; }
  body.innerHTML = `<p class="id-line">Construction set: ${esc(p.id)}<br>Revision: ${esc(p.revision)}</p>`;
  if (tab === "overview") {
    body.insertAdjacentHTML("beforeend", `${metrics(p)}${floorReview(p)}${schoolWindowProfile(p)}<h3>LoD1 completeness</h3><p>${8 - p.missing.length} of 8 required properties available.</p>${p.missing.length ? `<p class="muted">Pending: ${p.missing.map(label).join(", ")}.</p>` : "<p>LoD1 complete.</p>"}${lod2Overview(p)}<p class="muted">Above-ground U-values describe nominal assemblies. Internal floors are not exterior heat-loss boundaries. Roof is the top thermal boundary. Ground and basement values retain their source boundary meaning.</p><p class="muted">Climate zones and ventilation types are classifications. Construction values and effective infiltration are shared across those choices; mechanical airflow and recovery are supplied downstream.</p>`);
    $("[data-open-lod2]")?.addEventListener("click", (event) => { event.preventDefault(); tab = "layers"; renderDetail(); });
  }
  if (tab === "layers") {
    body.insertAdjacentHTML("beforeend", lod2Details(p) + `<h3>Available constructions</h3><p>${(p.construction_availability || []).map(esc).join(", ")}</p><p class="muted">Availability does not imply presence. Geometry selects basement and other elements. Nominal ground-layer U is separate from the retained effective ground reference. Completeness does not imply empirical validation.</p>`);
    $("#open-archetype")?.addEventListener("click", (event) => {
      openArchetypeDialog($("#archetype-dialog"), event.currentTarget, p);
    });
  }
  if (tab === "evidence") {
    body.insertAdjacentHTML("beforeend", `<h3>References and scaling</h3>${Object.entries(p.properties).map(([role, prop]) => {
      const source = data.sources.find((s) => s.id === prop.source);
      const curveSource = data.sources.find((s) => s.id === prop.curve_source);
      const ref = prop.override || prop.anchor;
      return `<div class="evidence"><strong>${label(role)}</strong>${facts([
        ["Value", `${fmt(prop.value, 4)} ${prop.unit}`],
        ["Resolution", prop.mode],
        ["Evidence class", label(prop.evidence?.classification || "unclassified")],
        ["Construction basis", label(prop.evidence?.construction_basis || "unclassified")],
        ["Value meaning", label(prop.evidence?.value_kind || prop.boundary)],
        ...(prop.evidence?.nominal_u_value != null ? [["Nominal construction U", `${fmt(prop.evidence.nominal_u_value, 4)} W/(m²K)`]] : []),
        ["Evidence limits", prop.evidence?.limitations || prop.evidence?.decision || "See source record"],
        ["Boundary", label(prop.boundary)],
        ["Reference", ref ? `${ref.category || selected.category} · ${ref.era} · ${ref.state}: ${fmt(ref.value, 4)} ${prop.unit}` : "Pending reference"],
        ["Curve", prop.curve],
        ["Scaling factor", prop.scaling_factor == null ? "Not applied" : `${fmt(prop.scaling_factor, 6)} × reference`],
        ["Unclipped value", prop.unclipped_value == null ? "Pending" : `${fmt(prop.unclipped_value, 4)} ${prop.unit}`],
        ...(prop.guardrail ? [
          ["Guardrail", prop.guardrail.applied ? "Adjusted" : prop.guardrail.protected ? "Protected evidence" : "Not adjusted"],
          ["Nominal lower bound", `${fmt(prop.guardrail.lower_bound, 4)} ${prop.unit} (${fmt(prop.guardrail.margin_percent, 1)}% margin)`],
          ["Effective lower bound", `${fmt(prop.guardrail.effective_lower_bound, 4)} ${prop.unit}`],
          ["Below nominal limit", prop.guardrail.below_nominal_limit ? "Yes — retained exception" : "No"],
          ["Adjustment reason", prop.guardrail.reason],
          ["Guardrail source", data.sources.find((s) => s.id === prop.guardrail.source)?.title || prop.guardrail.source],
        ] : []),
        ["Source", source?.title || prop.source || "Pending"],
        ["Curve source", curveSource?.title || prop.curve_source],
        ["Status", prop.assumed ? "Provisional assumption" : prop.value == null ? "Pending" : "Source reference"],
      ])}<small>${esc(ref?.locator || ref?.note || "")}</small>${curveSource?.note ? `<p class="muted">${esc(curveSource.note)}</p>` : ""}</div>`;
    }).join("")}<details class="source-details"><summary>Source register</summary>${data.sources.map((s) => `<p><strong>${esc(s.title)}</strong><br>${esc(s.version || "")}<br>${esc(s.note || s.url || "")}</p>`).join("")}</details><details class="source-details"><summary>Full construction record</summary><pre>${esc(JSON.stringify(p, null, 2))}</pre></details>`);
  }
}
function renderNotes(root) {
  const draft = drafts.get(selected.id) || {
    body: "",
    author: "",
    kind: "remark",
    editing: null,
  };
  editing = draft.editing;
  const own = notes
    .filter((n) => n.cell_id === selected.id)
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  root.innerHTML = `<h3>${editing ? "Edit remark" : "Leave a remark"}</h3><p class="muted" style="margin-bottom:15px">Remarks belong to this exact matrix cell. Each records the construction set and catalogue release being reviewed.</p><p class="id-line" style="margin-bottom:16px">Construction set: ${esc(draft.package_id || packages.get(activePackage)?.id)}<br>Revision: ${esc(draft.revision || packages.get(activePackage)?.revision)}</p><form id="note-form" class="note-form"><label for="body">Remark<textarea id="body" maxlength="20000" required placeholder="What should we verify, improve, or discuss?">${esc(draft.body)}</textarea></label><div class="form-row"><label>Your name (optional)<input id="author" maxlength="100" value="${esc(draft.author)}" placeholder="Name"></label><label>Type<select id="kind">${options(["remark", "question", "issue"], label)}</select></label></div><p id="save-error" class="inline-error" role="alert" hidden></p><div class="form-actions"><small id="storage-label">Saved on the app server</small><div>${editing ? '<button type="button" id="cancel-edit" class="button text-button">Cancel</button>' : ""}<button id="save" class="button primary" type="submit">${editing ? "Save changes" : "Save remark"}</button></div></div></form><h3>${own.length} saved ${own.length === 1 ? "remark" : "remarks"}</h3>${own.length ? own.map((n) => `<article class="note-card"><div class="note-meta"><span class="badge ${n.kind === "issue" ? "amber" : ""}">${label(n.kind)}</span><strong>${esc(n.author || "Anonymous")}</strong><time datetime="${esc(n.created_at)}">${esc(new Date(n.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }))}</time>${n.updated_at !== n.created_at ? "<span>edited</span>" : ""}</div><p class="note-text">${esc(n.body)}</p><details class="source-details"><summary>Review context</summary><p>${esc(n.release_id)}<br>${esc(n.package_id)}<br>Revision ${esc(n.revision)}</p></details><div class="note-actions"><button data-edit="${esc(n.id)}">Edit</button><button class="delete" data-delete="${esc(n.id)}">Delete</button></div></article>`).join("") : '<p class="muted">No remarks yet for this cell.</p>'}`;
  $("#kind").value = draft.kind;
  $("#note-form").oninput = saveDraft;
  $("#note-form").onsubmit = async (e) => {
    e.preventDefault();
    if (busy) return;
    saveDraft();
    const d = drafts.get(selected.id);
    if (!d.body.trim()) {
      $("#save-error").textContent = "Write a remark before saving.";
      $("#save-error").hidden = false;
      return;
    }
    const cell = selected,
      p = packages.get(activePackage),
      existing = notes.find((n) => n.id === editing);
    const payload = {
      cell_id: cell.id,
      body: d.body.trim(),
      author: d.author.trim(),
      kind: d.kind,
      package_id: existing?.package_id || d.package_id || p?.id,
      revision: existing?.revision || d.revision || p?.revision,
      release_id: existing?.release_id || data.manifest.release_id,
    };
    setBusy(true);
    try {
      const result = await api(
        editing ? `/api/notes/${editing}` : "/api/notes",
        {
          method: editing ? "PUT" : "POST",
          body: JSON.stringify({
            ...payload,
            updated_at: existing?.updated_at,
          }),
        },
      );
      notes = notes.filter((n) => n.id !== result.id);
      notes.push(result);
      drafts.delete(cell.id);
      editing = null;
      renderMatrix();
      renderDetail();
      toast("Remark saved");
    } catch (error) {
      $("#save-error").textContent = error.message;
      $("#save-error").hidden = false;
    } finally {
      setBusy(false);
    }
  };
  if (editing)
    $("#cancel-edit").onclick = () => {
      drafts.delete(selected.id);
      editing = null;
      renderDetail();
    };
  $$("[data-edit]").forEach(
    (b) =>
      (b.onclick = () => {
        if (busy) return;
        const n = notes.find((n) => n.id === b.dataset.edit);
        drafts.set(selected.id, {
          body: n.body,
          author: n.author,
          kind: n.kind,
          editing: n.id,
          package_id: n.package_id,
          revision: n.revision,
        });
        renderDetail();
        $("#body").focus();
      }),
  );
  $$("[data-delete]").forEach(
    (b) =>
      (b.onclick = async () => {
        if (busy || !confirm("Delete this remark? This cannot be undone."))
          return;
        setBusy(true);
        try {
          const n = notes.find((n) => n.id === b.dataset.delete);
          await api(`/api/notes/${n.id}`, {
            method: "DELETE",
            body: JSON.stringify({ updated_at: n.updated_at }),
          });
          notes = notes.filter((x) => x.id !== n.id);
          if (editing === n.id) {
            drafts.delete(selected.id);
            editing = null;
          } else saveDraft();
          renderMatrix();
          renderDetail();
          toast("Remark deleted");
        } catch (error) {
          toast(error.message);
        } finally {
          setBusy(false);
        }
      }),
  );
}
function setBusy(value) {
  busy = value;
  $$("button,select,input,textarea").forEach((e) => (e.disabled = value));
}
async function init() {
  try {
    [data, notes] = await Promise.all([
      api("/api/catalogue"),
      api("/api/notes"),
    ]);
    packages = new Map(
      data.packages.map((p) => [packageKey(p.id, p.revision), p]),
    );
    cellsById = new Map(data.cells.map((c) => [c.id, c]));
    $("#zone").innerHTML = options(data.dimensions.zones, (v) =>
      v.replace("SE.", ""),
    );
    $("#state").innerHTML = options(data.dimensions.states, label);
    $("#system").innerHTML = options(data.dimensions.systems, label);
    let hash;
    try {
      hash = decodeURIComponent(location.hash.slice(1));
    } catch {}
    selected =
      cellsById.get(hash) ||
      cellsById.get("multi_family:SE.02:SE.Zone3:existing:F") ||
      data.cells[0];
    for (const k of ["zone", "state", "system"]) filters[k] = selected[k];
    activePackage = packageKey(selected.package_id, selected.revision);
    for (const k of Object.keys(filters)) {
      const el = $("#" + k);
      if (k === "noted") el.checked = filters[k];
      else el.value = filters[k];
      el.addEventListener(k === "search" ? "input" : "change", () => {
        if (busy) return;
        saveDraft();
        filters[k] = k === "noted" ? el.checked : el.value;
        if (["zone", "state", "system"].includes(k)) {
          selected = cellsById.get(
            [
              selected.category,
              selected.era,
              filters.zone,
              filters.state,
              filters.system,
            ].join(":"),
          );
          activePackage = packageKey(selected.package_id, selected.revision);
          history.replaceState(null, "", `#${encodeURIComponent(selected.id)}`);
          renderDetail();
        }
        renderMatrix();
        if (k === "metric") renderDetail();
      });
    }
    $("#reset").onclick = () => {
      saveDraft();
      filters = {
        zone: "SE.Zone3",
        state: "existing",
        system: "F",
        search: "",
        noted: false,
        metric: "wall",
      };
      for (const [k, v] of Object.entries(filters)) {
        if (k === "noted") $("#" + k).checked = v;
        else $("#" + k).value = v;
      }
      selectCell(cellsById.get("multi_family:SE.02:SE.Zone3:existing:F"));
    };
    $("#export").onclick = async () => {
      try {
        const fresh = await api("/api/notes");
        const blob = new Blob(
          [
            JSON.stringify(
              {
                schema_version: 1,
                exported_at: new Date().toISOString(),
                notes: fresh,
              },
              null,
              2,
            ),
          ],
          { type: "application/json" },
        );
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `epsm-remarks-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        toast(`${fresh.length} remarks exported`);
      } catch (e) {
        toast(e.message);
      }
    };
    $("#total").textContent = data.cells.length.toLocaleString();
    $("#close-archetype").addEventListener("click", closeArchetypeDialog);
    $("#archetype-dialog").addEventListener("close", (event) => {
      document.body.classList.remove("dialog-open");
      $("#app").inert = false;
      event.currentTarget._returnFocus?.focus();
      event.currentTarget._returnFocus = null;
    });
    $("#archetype-dialog").addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeArchetypeDialog();
      } else if (event.key === "Tab") {
        const focusable = $$("button:not(:disabled), summary, a[href], [tabindex]:not([tabindex='-1'])", event.currentTarget);
        if (!focusable.length) { event.preventDefault(); return; }
        const first = focusable[0], last = focusable.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    });
    $("#release").textContent =
      `${data.summary.lod1_complete} LoD1 complete · ${data.summary.lod1_pending} pending`;
    $("#lod2-total").textContent =
      `${data.lod2_summary.lod2_complete_slots} LoD2 complete · ${data.lod2_summary.slots_with_layer_recipe} with recipes`;
    $("#footer-release").textContent = data.manifest.release_id;
    $("#loading").hidden = true;
    $("#app").hidden = false;
    renderMatrix();
    renderDetail();
  } catch (error) {
    $("#loading").hidden = true;
    $("#error").textContent =
      `Could not load the explorer. ${error.message} Reload to retry.`;
    $("#error").hidden = false;
  }
}
window.addEventListener("beforeunload", (e) => {
  saveDraft();
  if ([...drafts.values()].some((d) => d.body.trim())) {
    e.preventDefault();
    e.returnValue = "";
  }
});
init();
