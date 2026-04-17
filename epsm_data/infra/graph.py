"""Graph visualization of the EPSM domain hierarchy.

Builds a NetworkX directed graph of the full building envelope hierarchy:
  Building -> Element -> Component -> Layer -> OpaqueMaterial -> EmbodiedCarbon

Adapted from Djamila's original Graph.py to work with the current domain
model (LayerSlot, LayerMaterial dataclasses instead of raw tuples).
"""

import networkx as nx
from pyvis.network import Network

from epsm_data.domain.element import Element
from epsm_data.domain.building import BuildingArchetype


def build_graph(
    buildings: list[BuildingArchetype],
    elements: list[Element],
) -> nx.DiGraph:
    """Build a directed graph of the full domain hierarchy."""
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
            type="Element",
            archetype=element.archetype,
            age=element.age,
            element_type=element.application.value,
            u_value=round(element.u_value, 5),
        )

        for component in element.components:
            G.add_node(
                component.name,
                type="Component",
                archetype=component.archetype,
                shearing_layer=component.shearing_layer.value,
                r_sum=round(component.r_sum, 4),
            )
            G.add_edge(element.name, component.name, relationship="contains_component")

            for slot in component.layers:
                layer = slot.layer
                G.add_node(
                    layer.layer_code,
                    type="Layer",
                    thickness=layer.thickness,
                    r_value=round(layer.r_value, 4),
                    is_composite=layer.is_composite,
                )
                G.add_edge(
                    component.name,
                    layer.layer_code,
                    relationship="contains_layer",
                    layer_index=slot.position,
                )

                for lm in layer.materials:
                    material = lm.material
                    G.add_node(
                        material.name,
                        type="OpaqueMaterial",
                        conductivity=material.conductivity,
                        density=material.density,
                    )
                    G.add_edge(
                        layer.layer_code,
                        material.name,
                        relationship="contains_material",
                        area_fraction=lm.area_fraction,
                        thickness=lm.thickness,
                    )

                    ec = material.embodied_carbon
                    G.add_node(
                        ec.resource_id,
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
    """Print node/edge counts by type."""
    from collections import Counter
    type_counts = Counter(data["type"] for _, data in G.nodes(data=True))
    print(f"\nGraph summary:")
    print(f"  Total nodes : {G.number_of_nodes()}")
    print(f"  Total edges : {G.number_of_edges()}")
    print(f"\n  Nodes by type:")
    for t, count in type_counts.items():
        print(f"    {t}: {count}")


def visualise_pyvis(G: nx.DiGraph, output: str = "graph.html") -> None:
    """Render an interactive HTML graph using pyvis.

    Uses hierarchical layout so each Building fans out into its own
    cluster of Elements -> Components -> Layers -> Materials -> EC.
    """
    color_map = {
        "Building":       "#f1c40f",  # gold
        "Element":        "#e74c3c",  # red
        "Component":      "#e67e22",  # orange
        "Layer":          "#3498db",  # blue
        "OpaqueMaterial": "#2ecc71",  # green
        "EmbodiedCarbon": "#9b59b6",  # purple
    }
    # Hierarchical level for top-down layout (0 = top)
    level_map = {
        "Building":       0,
        "Element":        1,
        "Component":      2,
        "Layer":          3,
        "OpaqueMaterial": 4,
        "EmbodiedCarbon": 5,
    }
    base_size_map = {
        "Building":       55,
        "Element":        40,
        "Component":      28,
        "Layer":          18,
        "OpaqueMaterial": 12,
        "EmbodiedCarbon": 8,
    }
    edge_color_map = {
        "contains_element":    "#e74c3c99",  # red tint
        "contains_component":  "#e67e2299",  # orange tint
        "contains_layer":      "#3498db99",  # blue tint
        "contains_material":   "#2ecc7199",  # green tint
        "has_embodied_carbon": "#9b59b699",  # purple tint
    }
    edge_width_map = {
        "contains_element":    4,
        "contains_component":  3,
        "contains_layer":      2,
        "contains_material":   1.5,
        "has_embodied_carbon": 1,
    }
    # Short readable labels for deeper nodes
    label_map = {
        "Building":       lambda n, d: n,
        "Element":        lambda n, d: n,
        "Component":      lambda n, d: d.get("shearing_layer", n.split("_")[-1]),
        "Layer":          lambda n, d: n.split("_")[-1] if "_" in n else n,
        "OpaqueMaterial": lambda n, d: n[:20],
        "EmbodiedCarbon": lambda n, d: "",
    }

    net = Network(height="950px", width="100%", directed=True, notebook=False)

    # Hierarchical top-down layout keeps buildings at top, children below
    net.set_options("""{
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "UD",
          "sortMethod": "directed",
          "levelSeparation": 180,
          "nodeSpacing": 200,
          "treeSpacing": 350,
          "blockShifting": true,
          "edgeMinimization": true,
          "parentCentralization": true
        }
      },
      "physics": {
        "enabled": true,
        "hierarchicalRepulsion": {
          "centralGravity": 0.2,
          "springLength": 150,
          "springConstant": 0.05,
          "nodeDistance": 200,
          "damping": 0.09,
          "avoidOverlap": 0.5
        },
        "solver": "hierarchicalRepulsion",
        "stabilization": {
          "enabled": true,
          "iterations": 300
        }
      },
      "edges": {
        "smooth": { "type": "cubicBezier", "forceDirection": "vertical" },
        "arrows": { "to": { "enabled": true, "scaleFactor": 0.5 } }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "navigationButtons": true,
        "keyboard": true
      },
      "configure": {
        "enabled": true,
        "filter": ["physics", "layout"]
      }
    }""")

    degree = dict(G.degree())

    for node, data in G.nodes(data=True):
        node_type = data.get("type", "Unknown")
        level = level_map.get(node_type, 5)

        label_fn = label_map.get(node_type, lambda n, d: "")
        label = label_fn(node, data)

        base = base_size_map.get(node_type, 10)
        node_degree = degree.get(node, 1)
        size = base + (node_degree * 1.2)

        # Rich tooltip — plain text (pyvis escapes HTML in hierarchical mode)
        tooltip_lines = [
            node,
            f"Type: {node_type}",
            f"Connections: {node_degree}",
        ]
        tooltip_lines.extend(
            f"{k}: {v}" for k, v in data.items() if k != "type"
        )
        tooltip = "\n".join(tooltip_lines)

        font_size = {0: 16, 1: 13, 2: 11, 3: 9, 4: 8}.get(level, 0)

        net.add_node(
            node,
            label=label,
            level=level,
            color={
                "background": color_map.get(node_type, "#95a5a6"),
                "border": "#333",
                "highlight": {"background": "#fff", "border": "#333"},
            },
            size=size,
            title=tooltip,
            shape="dot",
            borderWidth=1.5,
            font={"size": font_size, "color": "#333"} if label else {"size": 0},
        )

    for src, dst, data in G.edges(data=True):
        rel = data.get("relationship", "")
        edge_info = rel.replace("_", " ")
        extra = {k: v for k, v in data.items() if k != "relationship"}
        if extra:
            edge_info += " | " + ", ".join(f"{k}={v}" for k, v in extra.items())

        net.add_edge(
            src, dst,
            title=edge_info,
            color=edge_color_map.get(rel, "#cccccc88"),
            width=edge_width_map.get(rel, 1),
        )

    net.show(output, notebook=False)

    # Inject legend + export panel
    with open(output, "r", encoding="utf-8") as f:
        html = f.read()

    legend_html = _build_legend_html(color_map)
    inject = legend_html + "\n" + _EXPORT_PANEL_HTML
    if "</body>" in html:
        html = html.replace("</body>", inject + "\n</body>")
    else:
        html += inject

    with open(output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Graph saved to {output}")


def _build_legend_html(color_map: dict[str, str]) -> str:
    """Generate an HTML legend panel for node types."""
    items = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0">'
        f'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;'
        f'background:{color};border:1px solid #555"></span>'
        f'<span>{label}</span></div>'
        for label, color in color_map.items()
    )
    return f"""
<div id="legend-panel" style="
  position:fixed; bottom:14px; left:14px; z-index:9999;
  background:#fff; border-radius:8px; padding:12px 16px;
  box-shadow:0 2px 12px rgba(0,0,0,0.15);
  font-family:sans-serif; font-size:13px; color:#333;
">
  <div style="font-weight:700;margin-bottom:6px;border-bottom:1px solid #eee;padding-bottom:4px">
    Legend</div>
  {items}
</div>
"""


def export_gephi(G: nx.DiGraph, output: str = "graph.gexf") -> None:
    """Export the graph in GEXF format for Gephi."""
    G_export = G.copy()
    for node in G_export.nodes:
        G_export.nodes[node].pop("instance", None)
    nx.write_gexf(G_export, output)
    print(f"Exported to {output} — open in Gephi")


# ---------------------------------------------------------------------------
# Export panel HTML/JS injected into the pyvis output
# ---------------------------------------------------------------------------
_EXPORT_PANEL_HTML = """
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
  var sel = document.getElementById('bg-select').value;
  return sel === 'white' ? '#ffffff' : sel === 'black' ? '#000000'
       : sel === 'custom' ? document.getElementById('bg-custom').value : null;
}
function setStatus(msg) {
  document.getElementById('export-status').textContent = msg;
  if (msg) setTimeout(function() { document.getElementById('export-status').textContent = ''; }, 5000);
}
function exportPNG() {
  var scale = parseInt(document.getElementById('scale-select').value);
  var bgColor = getBgColor();
  var btn = document.getElementById('png-btn');
  var visCvs = document.querySelector('#mynetwork canvas');
  if (!visCvs) { setStatus('Canvas not found.'); return; }
  btn.disabled = true; setStatus('Rendering PNG...');
  requestAnimationFrame(function() {
    var w = visCvs.width, h = visCvs.height;
    var out = document.createElement('canvas');
    out.width = w * scale; out.height = h * scale;
    var ctx = out.getContext('2d');
    if (bgColor) { ctx.fillStyle = bgColor; ctx.fillRect(0, 0, out.width, out.height); }
    ctx.imageSmoothingEnabled = false;
    ctx.scale(scale, scale);
    ctx.drawImage(visCvs, 0, 0, w, h);
    out.toBlob(function(blob) {
      var a = document.createElement('a');
      a.download = 'graph_' + scale + 'x.png';
      a.href = URL.createObjectURL(blob); a.click();
      btn.disabled = false;
      setStatus('PNG saved - ' + out.width + 'x' + out.height + 'px');
    }, 'image/png');
  });
}
function exportSVG() {
  var btn = document.getElementById('svg-btn');
  var bgColor = getBgColor() || '#ffffff';
  var net = window.network;
  if (!net) { setStatus('vis.js network not found.'); return; }
  btn.disabled = true; setStatus('Building SVG...');
  requestAnimationFrame(function() {
    try {
      var positions = net.getPositions();
      var allNodes = net.body.data.nodes.get();
      var allEdges = net.body.data.edges.get();
      var xs = Object.values(positions).map(function(p) { return p.x; });
      var ys = Object.values(positions).map(function(p) { return p.y; });
      var pad = 80;
      var W = Math.max.apply(null, xs) - Math.min.apply(null, xs) + pad * 2;
      var H = Math.max.apply(null, ys) - Math.min.apply(null, ys) + pad * 2;
      var minX = Math.min.apply(null, xs), minY = Math.min.apply(null, ys);
      var toX = function(x) { return x - minX + pad; };
      var toY = function(y) { return y - minY + pad; };
      var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '">';
      svg += '<rect width="100%" height="100%" fill="' + bgColor + '"/>';
      allEdges.forEach(function(e) {
        var from = positions[e.from], to = positions[e.to];
        if (!from || !to) return;
        var color = (e.color && e.color.color) ? e.color.color : '#cccccc';
        var mid = 'arr' + Math.random().toString(36).slice(2);
        svg += '<defs><marker id="' + mid + '" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">';
        svg += '<path d="M0,0 L0,6 L8,3 z" fill="' + color + '"/></marker></defs>';
        svg += '<line x1="' + toX(from.x) + '" y1="' + toY(from.y) + '" x2="' + toX(to.x) + '" y2="' + toY(to.y) + '" ';
        svg += 'stroke="' + color + '" stroke-width="' + (e.width || 1) + '" stroke-opacity="0.7" marker-end="url(#' + mid + ')"/>';
      });
      allNodes.forEach(function(n) {
        var pos = positions[n.id]; if (!pos) return;
        var cx = toX(pos.x), cy = toY(pos.y);
        var color = typeof n.color === 'object' ? (n.color.background || n.color.color || '#95a5a6') : (n.color || '#95a5a6');
        var r = n.size || 10;
        svg += '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="' + color + '" stroke="#fff" stroke-width="1.5"/>';
        if (n.label) svg += '<text x="' + cx + '" y="' + (cy - r - 4) + '" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#333">' + n.label + '</text>';
      });
      svg += '</svg>';
      var a = document.createElement('a');
      a.download = 'graph.svg';
      a.href = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
      a.click();
      setStatus('SVG saved — infinitely scalable');
    } catch(err) { setStatus('SVG error: ' + err.message); }
    btn.disabled = false;
  });
}
</script>
"""
