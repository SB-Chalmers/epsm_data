# graph.py
import networkx as nx
from pyvis.network import Network
from epsm_data.domain.element import Elements
from epsm_data.domain.building import BuildingArchetype

EXCEL_PATH = "data/Material_Database.xlsx"
JSON_PATH = "data/opaque_material.json"


def build_graph(buildings: list[BuildingArchetype], elements: list[Elements]) -> nx.DiGraph:
    """
    Building -> Element -> Components -> Layer -> OpaqueMaterial -> EmbodiedCarbon
    """
    G = nx.DiGraph()

    for building in buildings:
        G.add_node(
            building.archetype_id,
            type="Building",
            age=building.construction_year,
        )
        for role, element in building.construction_set.elements.items():
            G.add_edge(
                building.archetype_id,
                element.name,
                relationship="contains_element",
                element_type=role.value,
            )

    for element in elements:
        G.add_node(
            element.name,
            instance=element,
            type="Element",
            archetype=element.archetype,
            age=element.age,
            element_type=element.application.value,
            u_value=round(element.u_value, 5),
        )

        for component in element.components:
            G.add_node(
                component.name,
                instance=component,
                type="Components",
                archetype=component.archetype,
                shearing_layer=component.shearing_layer.value,
                r_sum=round(component.r_sum, 4),
            )
            G.add_edge(element.name, component.name, relationship="contains_component")

            for layer, layer_index in component.layers:
                G.add_node(
                    layer.layer_code,
                    instance=layer,
                    type="Layer",
                    thickness=layer.thickness,
                    r_value=round(layer.r_value, 4),
                    is_composite=layer.is_composite,
                )
                G.add_edge(
                    component.name,
                    layer.layer_code,
                    relationship="contains_layer",
                    layer_index=layer_index,
                )

                for material, frac, thickness in layer.materials:
                    G.add_node(
                        material.name,
                        instance=material,
                        type="OpaqueMaterial",
                        conductivity=material.conductivity,
                        density=material.density,
                    )
                    G.add_edge(
                        layer.layer_code,
                        material.name,
                        relationship="contains_material",
                        area_fraction=frac,
                        thickness=thickness,
                    )

                    ec = material.embodied_carbon
                    G.add_node(
                        ec.resource_id,
                        instance=ec,
                        type="EmbodiedCarbon",
                        boverket_name=ec.boverket_name,
                        A1_A3_conservative=ec.A1_A3_conservative,
                        A1_A3_typical=ec.A1_A3_typical,
                    )
                    G.add_edge(
                        material.name,
                        ec.resource_id,
                        relationship="has_embodied_carbon",
                    )

    return G


def print_graph_summary(G: nx.DiGraph) -> None:
    from collections import Counter
    type_counts = Counter(data["type"] for _, data in G.nodes(data=True))
    print(f"\nGraph summary:")
    print(f"  Total nodes : {G.number_of_nodes()}")
    print(f"  Total edges : {G.number_of_edges()}")
    print(f"\n  Nodes by type:")
    for t, count in type_counts.items():
        print(f"    {t}: {count}")


def visualise_pyvis(G: nx.DiGraph, output: str = "graph.html") -> None:
    color_map = {
        "Building":       "#fffb00",
        "Element":        "#ff1900",
        "Components":     "#e67e22",
        "Layer":          "#3498db",
        "OpaqueMaterial": "#2ecc71",
        "EmbodiedCarbon": "#9b59b6",
    }
    base_size_map = {
        "Building":       60,
        "Element":        45,
        "Components":     30,
        "Layer":          20,
        "OpaqueMaterial": 12,
        "EmbodiedCarbon": 8,
    }
    edge_width_map = {
        "contains_element":    3,
        "contains_component":  2,
        "contains_layer":      1.5,
        "contains_material":   1,
        "has_embodied_carbon": 0.5,
    }

    net = Network(height="900px", width="100%", directed=True, notebook=False)
    net.force_atlas_2based(
        gravity=-80,
        central_gravity=0.005,
        spring_length=150,
        spring_strength=0.1,
        damping=0.9,
        overlap=1,
    )
    net.show_buttons(filter_=['physics'])

    degree = dict(G.degree())

    for node, data in G.nodes(data=True):
        node_type = data.get("type", "Unknown")
        label = node if node_type in ("Building", "Element") else ""

        base = base_size_map.get(node_type, 15)
        node_degree = degree.get(node, 1)
        size = base + (node_degree * 1.5)

        tooltip = f"<b>{node}</b><br>Type: {node_type}<br>Connections: {node_degree}<br>" + "<br>".join(
            f"{k}: {v}"
            for k, v in data.items()
            if k not in ("instance", "type")
        )
        net.add_node(
            node,
            label=label,
            color=color_map.get(node_type, "#95a5a6"),
            size=size,
            title=tooltip,
            font={"size": 14, "color": "#333333"} if label else {"size": 0},
        )

    for src, dst, data in G.edges(data=True):
        rel = data.get("relationship", "")
        net.add_edge(
            src, dst,
            label="",
            title=rel,
            arrows="to",
            color={"color": "#cccccc", "opacity": 0.6},
            width=edge_width_map.get(rel, 1),
        )

    net.show(output, notebook=False)

    with open(output, "r", encoding="utf-8") as f:
        html = f.read()

    export_script = """
<style>
  #export-panel {
    position: fixed; top: 14px; right: 14px; z-index: 9999;
    background: #fff; border-radius: 8px; padding: 14px 16px;
    box-shadow: 0 2px 14px rgba(0,0,0,0.2);
    font-family: sans-serif; font-size: 13px; color: #333;
    display: flex; flex-direction: column; gap: 10px; min-width: 210px;
  }
  #export-panel .panel-title {
    font-weight: 700; font-size: 14px; border-bottom: 1px solid #eee;
    padding-bottom: 6px; margin-bottom: 2px;
  }
  #export-panel .row-label { margin-bottom: 3px; color: #555; }
  #export-panel select, #export-panel input[type=color] {
    width: 100%; padding: 4px 6px; border-radius: 4px;
    border: 1px solid #ccc; font-size: 13px; box-sizing: border-box;
  }
  .btn-row { display: flex; gap: 8px; }
  .export-btn {
    flex: 1; padding: 8px 4px; color: #fff;
    border: none; border-radius: 5px; font-size: 13px;
    cursor: pointer; font-weight: 600;
  }
  #png-btn  { background: #2c3e50; }
  #png-btn:hover  { background: #1a252f; }
  #svg-btn  { background: #27ae60; }
  #svg-btn:hover  { background: #1e8449; }
  .export-btn:disabled { background: #aaa !important; cursor: default; }
  #export-status { font-size: 11px; color: #888; min-height: 14px; }
</style>

<div id="export-panel">
  <div class="panel-title">Export Graph</div>
  <div>
    <div class="row-label">PNG resolution</div>
    <select id="scale-select">
      <option value="2">2x - 2K (fast)</option>
      <option value="4" selected>4x - 4K (recommended)</option>
      <option value="6">6x - 6K</option>
      <option value="8">8x - 8K (ultra)</option>
    </select>
  </div>
  <div>
    <div class="row-label">Background</div>
    <select id="bg-select">
      <option value="white" selected>White</option>
      <option value="transparent">Transparent</option>
      <option value="black">Black</option>
      <option value="custom">Custom colour...</option>
    </select>
    <input type="color" id="bg-custom" value="#ffffff"
           style="display:none; margin-top:5px;">
  </div>
  <div class="btn-row">
    <button id="png-btn" class="export-btn" onclick="exportPNG()">PNG</button>
    <button id="svg-btn" class="export-btn" onclick="exportSVG()">SVG</button>
  </div>
  <div id="export-status"></div>
</div>

<script>
document.getElementById('bg-select').addEventListener('change', function() {
  document.getElementById('bg-custom').style.display =
    this.value === 'custom' ? 'block' : 'none';
});
function getBgColor() {
  const sel = document.getElementById('bg-select').value;
  return sel === 'white' ? '#ffffff' : sel === 'black' ? '#000000'
       : sel === 'custom' ? document.getElementById('bg-custom').value : null;
}
function setStatus(msg) {
  document.getElementById('export-status').textContent = msg;
  if (msg) setTimeout(() => document.getElementById('export-status').textContent = '', 5000);
}
function exportPNG() {
  const scale = parseInt(document.getElementById('scale-select').value);
  const bgColor = getBgColor();
  const btn = document.getElementById('png-btn');
  const visCvs = document.querySelector('#mynetwork canvas');
  if (!visCvs) { setStatus('Canvas not found.'); return; }
  btn.disabled = true; setStatus('Rendering PNG...');
  requestAnimationFrame(() => {
    const w = visCvs.width, h = visCvs.height;
    const out = document.createElement('canvas');
    out.width = w * scale; out.height = h * scale;
    const ctx = out.getContext('2d');
    if (bgColor) { ctx.fillStyle = bgColor; ctx.fillRect(0, 0, out.width, out.height); }
    ctx.imageSmoothingEnabled = false;
    ctx.scale(scale, scale);
    ctx.drawImage(visCvs, 0, 0, w, h);
    out.toBlob(blob => {
      const a = document.createElement('a');
      a.download = `graph_${scale}x.png`;
      a.href = URL.createObjectURL(blob); a.click();
      btn.disabled = false;
      setStatus(`PNG saved - ${out.width}x${out.height}px`);
    }, 'image/png');
  });
}
function exportSVG() {
  const btn = document.getElementById('svg-btn');
  const bgColor = getBgColor() || '#ffffff';
  const net = window.network;
  if (!net) { setStatus('vis.js network not found.'); return; }
  btn.disabled = true; setStatus('Building SVG...');
  requestAnimationFrame(() => {
    try {
      const positions = net.getPositions();
      const allNodes = net.body.data.nodes.get();
      const allEdges = net.body.data.edges.get();
      const xs = Object.values(positions).map(p => p.x);
      const ys = Object.values(positions).map(p => p.y);
      const pad = 80;
      const W = Math.max(...xs) - Math.min(...xs) + pad * 2;
      const H = Math.max(...ys) - Math.min(...ys) + pad * 2;
      const minX = Math.min(...xs), minY = Math.min(...ys);
      const toX = x => x - minX + pad;
      const toY = y => y - minY + pad;
      let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">\n`;
      svg += `<rect width="100%" height="100%" fill="${bgColor}"/>\n`;
      allEdges.forEach(e => {
        const from = positions[e.from], to = positions[e.to];
        if (!from || !to) return;
        const color = (e.color && e.color.color) ? e.color.color : '#cccccc';
        const mid = 'arr' + Math.random().toString(36).slice(2);
        svg += `<defs><marker id="${mid}" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">`;
        svg += `<path d="M0,0 L0,6 L8,3 z" fill="${color}"/></marker></defs>\n`;
        svg += `<line x1="${toX(from.x)}" y1="${toY(from.y)}" x2="${toX(to.x)}" y2="${toY(to.y)}" `;
        svg += `stroke="${color}" stroke-width="${e.width || 1}" stroke-opacity="0.7" marker-end="url(#${mid})"/>\n`;
      });
      allNodes.forEach(n => {
        const pos = positions[n.id]; if (!pos) return;
        const cx = toX(pos.x), cy = toY(pos.y);
        const color = typeof n.color === 'object' ? (n.color.background || n.color.color || '#95a5a6') : (n.color || '#95a5a6');
        const r = n.size || 10;
        svg += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${color}" stroke="#fff" stroke-width="1.5"/>\n`;
        if (n.label) svg += `<text x="${cx}" y="${cy - r - 4}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#333">${n.label}</text>\n`;
      });
      svg += `</svg>`;
      const a = document.createElement('a');
      a.download = 'graph.svg';
      a.href = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
      a.click();
      setStatus('SVG saved - infinitely scalable');
    } catch(err) { setStatus('SVG error: ' + err.message); }
    btn.disabled = false;
  });
}
</script>
"""

    if "</body>" in html:
        html = html.replace("</body>", export_script + "\n</body>")
    else:
        html += export_script

    with open(output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Graph saved to {output}")


def export_gephi(G: nx.DiGraph, output: str = "graph.gexf") -> None:
    G_export = G.copy()
    for node in G_export.nodes:
        G_export.nodes[node].pop("instance", None)
    nx.write_gexf(G_export, output)
    print(f"Exported to {output} - open in Gephi")


if __name__ == "__main__":
    from epsm_data.infra.loaders.loader import (
        load_opaque_materials, load_layers,
        load_components, load_elements, load_buildings,
    )

    materials = load_opaque_materials(EXCEL_PATH, JSON_PATH)
    opaque_lookup = {mat.name: mat for mat in materials}

    layers = load_layers(EXCEL_PATH, opaque_lookup)
    layer_lookup = {layer.layer_code: layer for layer in layers}

    components = load_components(EXCEL_PATH, layer_lookup)
    components_lookup = {comp.name: comp for comp in components}

    elements = load_elements(EXCEL_PATH, components_lookup)
    elements_lookup = {el.name: el for el in elements}

    buildings = load_buildings(EXCEL_PATH, elements_lookup)

    G = build_graph(buildings, elements)
    print_graph_summary(G)
    visualise_pyvis(G)
    export_gephi(G)