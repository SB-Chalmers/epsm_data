# graph.py
import networkx as nx
from pyvis.network import Network
from Classes import Element2

# Build Graph
def build_graph(elements: list[Element2]) -> nx.DiGraph:
    """
    Build a directed graph of all relationships in the data hierarchy.
    Element2 → Components2 → Layer2 → OpaqueMaterial2 ( → EmbodiedCarbon2)
    """
    G = nx.DiGraph()

    for element in elements:
        G.add_node(
            element.name,
            instance=element,
            type="Element",
            archetype=element.archetype,
            age=element.age,
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
                    archetype=layer.archetype,
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

# Summary
def print_graph_summary(G: nx.DiGraph) -> None:
    from collections import Counter
    type_counts = Counter(data["type"] for _, data in G.nodes(data=True))
    print(f"\nGraph summary:")
    print(f"  Total nodes : {G.number_of_nodes()}")
    print(f"  Total edges : {G.number_of_edges()}")
    print(f"\n  Nodes by type:")
    for t, count in type_counts.items():
        print(f"    {t}: {count}")

# Pyvis Visualisation
def visualise_pyvis(G: nx.DiGraph, output: str = "graph.html") -> None:
    color_map = {
        "Element":       "#ff1900",  # red
        "Components":    "#e67e22",  # orange
        "Layer":         "#3498db",  # blue
        "OpaqueMaterial":"#2ecc71",  # green
        "EmbodiedCarbon":"#9b59b6",  # purple
    }
    size_map = {
        "Element":       40,
        "Components":    30,
        "Layer":         20,
        "OpaqueMaterial":15,
        "EmbodiedCarbon":10, #Maybe reverse?
    }

    net = Network(height="900px", width="100%", directed=True, notebook=False)
    net.barnes_hut(spring_length=120, spring_strength=0.02, damping=0.9)

    for node, data in G.nodes(data=True):
        node_type = data.get("type", "Unknown")

        # Build hover tooltip from node attributes
        tooltip = f"<b>{node}</b><br>Type: {node_type}<br>" + "<br>".join(
            f"{k}: {v}"
            for k, v in data.items()
            if k not in ("instance", "type")
        )

        net.add_node(
            node,
            label=node,
            color=color_map.get(node_type, "#95a5a6"),
            size=size_map.get(node_type, 15),
            title=tooltip,
        )

    for src, dst, data in G.edges(data=True):
        net.add_edge(
            src, dst,
            label=data.get("relationship", ""),
            title=data.get("relationship", ""),
            arrows="to",
            color="#cccccc",
        )

    net.show(output, notebook=False)
    print(f"Graph saved to {output} — opening in browser.")

# Gephi Export
def export_gephi(G: nx.DiGraph, output: str = "graph.gexf") -> None:
    G_export = G.copy()
    for node in G_export.nodes:
        G_export.nodes[node].pop("instance", None)
    nx.write_gexf(G_export, output)
    print(f"Exported to {output} — open in Gephi")

# Example Query
def query_element_materials(G: nx.DiGraph, element_name: str) -> list[str]:
    """Get all material names reachable from an element."""
    return [
        node for node, data in G.nodes(data=True)
        if data.get("type") == "OpaqueMaterial2"
        and nx.has_path(G, element_name, node)
    ]

# Run
if __name__ == "__main__":
    from InstanceLoader import (
    load_opaque_materials, load_layers,
    load_components, load_elements
)

    opaque_materials = load_opaque_materials()
    opaque_lookup = {mat.name: mat for mat in opaque_materials}

    layers = load_layers(opaque_lookup)
    layer_lookup = {layer.layer_code: layer for layer in layers}

    components = load_components(layer_lookup)
    components_lookup = {comp.name: comp for comp in components}

    elements = load_elements(components_lookup)

    G = build_graph(elements)
    print_graph_summary(G)

    # Example condition
    if elements:
        example = elements[0].name
        print(f"\nMaterials in '{example}':")
        for mat in query_element_materials(G, example):
            print(f"  {mat}")

    visualise_pyvis(G)
    export_gephi(G)
