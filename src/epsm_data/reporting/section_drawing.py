"""Architectural section drawings for building archetypes.

Produces wall-section-style cross sections with material-specific
colours, hatching patterns, and annotations — one subplot per element.

Usage:
    from epsm_data.reporting.section_drawing import plot_sections

    fig = plot_sections(archetype)          # returns matplotlib Figure
    fig.savefig("sections.pdf", dpi=150)

    # or via the convenience method (available after importing this module):
    archetype.plot()
"""

from __future__ import annotations

from math import ceil, isfinite
from typing import TYPE_CHECKING

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

if TYPE_CHECKING:
    from epsm_data.domain.building import BuildingArchetype
    from epsm_data.domain.element import Element


# ══════════════════════════════════════════════════════════════════
# MATERIAL VISUAL STYLES
# ══════════════════════════════════════════════════════════════════
# Architectural convention:
#   Concrete — dots/stipple    Brick — diagonal 45° crosshatch
#   Insulation — wavy/light    Wood — horizontal grain lines
#   Gypsum/Plaster — plain     EPS — circles
#   Membrane/felt — solid dark
# ══════════════════════════════════════════════════════════════════

_STYLE_TABLE: dict[str, dict] = {
    "air_gap": {
        "facecolor": "#FFFFFF",
        "hatch": "",
        "edgecolor": "#78909C",
        "label": "Air gap",
    },
    "acoustic": {
        "facecolor": "#D5E1E8",
        "hatch": "..",
        "edgecolor": "#708A99",
        "label": "Acoustic tile",
    },
    "linoleum": {
        "facecolor": "#879BA0",
        "hatch": "",
        "edgecolor": "#465D62",
        "label": "Linoleum",
    },
    # ── Masonry / stone ──────────────────────────────────────
    "brick": {
        "facecolor": "#C8785A",
        "hatch": "xx",
        "edgecolor": "#7A3B20",
        "label": "Brick",
    },
    # ── Concrete variants ────────────────────────────────────
    "concrete": {
        "facecolor": "#BCBCBC",
        "hatch": "...",
        "edgecolor": "#6B6B6B",
        "label": "Concrete",
    },
    "concrete_light": {
        "facecolor": "#D0D0D0",
        "hatch": "..",
        "edgecolor": "#8A8A8A",
        "label": "Lightweight concrete",
    },
    # ── Insulation ───────────────────────────────────────────
    "mineral_wool": {
        "facecolor": "#FFF2B0",
        "hatch": "//",
        "edgecolor": "#C8A832",
        "label": "Mineral wool",
    },
    "eps": {
        "facecolor": "#E8F0FF",
        "hatch": "oo",
        "edgecolor": "#7090C0",
        "label": "EPS",
    },
    "xps": {
        "facecolor": "#D5E7F5",
        "hatch": "oo",
        "edgecolor": "#5681A0",
        "label": "XPS",
    },
    "leca": {
        "facecolor": "#D8C6B3",
        "hatch": "OO",
        "edgecolor": "#8D7258",
        "label": "LECA",
    },
    "rubber": {
        "facecolor": "#879BA0",
        "hatch": "",
        "edgecolor": "#465D62",
        "label": "Rubber finish",
    },
    "wood_fibre": {
        "facecolor": "#DFCBA1",
        "hatch": "..",
        "edgecolor": "#927D55",
        "label": "Wood-fibre board",
    },
    # ── Wood ─────────────────────────────────────────────────
    "wood": {
        "facecolor": "#E8C882",
        "hatch": "---",
        "edgecolor": "#8B6914",
        "label": "Wood",
    },
    "plywood": {
        "facecolor": "#DDB87A",
        "hatch": "--",
        "edgecolor": "#8B6914",
        "label": "Plywood",
    },
    # ── Board / finish ───────────────────────────────────────
    "gypsum": {
        "facecolor": "#F5F0E8",
        "hatch": "",
        "edgecolor": "#A09880",
        "label": "Gypsum board",
    },
    "plaster": {
        "facecolor": "#E8E0D0",
        "hatch": "",
        "edgecolor": "#968870",
        "label": "Plaster / render",
    },
    # ── Membrane ─────────────────────────────────────────────
    "membrane": {
        "facecolor": "#404040",
        "hatch": "",
        "edgecolor": "#202020",
        "label": "Roof membrane",
    },
    # ── Composite (stud+insulation) ──────────────────────────
    "composite": {
        "facecolor": "#F0E4A8",
        "hatch": "||//",
        "edgecolor": "#9A8428",
        "label": "Stud + insulation",
    },
    # ── Fallback ─────────────────────────────────────────────
    "_default": {
        "facecolor": "#E0E0E0",
        "hatch": "",
        "edgecolor": "#888888",
        "label": "Other",
    },
}

# Keyword mapping: honeybee name fragments → style key
_NAME_MAP: list[tuple[str, str]] = [
    ("air gap", "air_gap"),
    ("acoustic", "acoustic"),
    ("linoleum", "linoleum"),
    ("expanded plastic", "eps"),
    ("light insulation", "mineral_wool"),
    ("under felt", "membrane"),
    ("wood-fibre", "wood_fibre"),
    ("woodfiber", "wood_fibre"),
    ("rubber", "rubber"),
    ("leca", "leca"),
    ("lightweight concrete", "concrete_light"),
    ("stone wool", "mineral_wool"),
    ("eps", "eps"),
    ("xps", "xps"),
    ("mortar", "plaster"),
    ("plaster", "plaster"),
    ("mineral wool", "mineral_wool"),
    ("brick", "brick"),
    ("stucco", "plaster"),
    ("concrete block", "concrete"),
    ("concrete floor", "concrete"),
    ("concrete roof", "concrete"),
    ("concrete wall", "concrete"),
    ("concrete", "concrete"),
    ("lightweight concrete", "concrete_light"),
    ("gypsum", "gypsum"),
    ("plywood", "plywood"),
    ("wood", "wood"),
    ("insulation board", "eps"),
    ("built-up roofing", "membrane"),
    ("roofing", "membrane"),
]


def _classify_material(name: str) -> str:
    """Map a honeybee material name to a style key."""
    low = name.lower()
    for fragment, style_key in _NAME_MAP:
        if fragment in low:
            return style_key
    return "_default"


def _style_for(name: str, is_composite: bool = False) -> dict:
    """Return drawing style dict for a material/layer name."""
    if is_composite:
        return _STYLE_TABLE["composite"]
    key = _classify_material(name)
    return _STYLE_TABLE[key]


def _short_name(name: str) -> str:
    """Abbreviate honeybee material names for annotation."""
    replacements = [
        ("Attic loose stone wool", "Loose stone wool"),
        ("Facade stone wool board", "Facade stone wool"),
        ("Perimeter XPS 300", "XPS 300"),
        ("gypsum_board", "Gypsum"),
        ("plaster_board", "Gypsum"),
        ("gypsum_wind_sheathing", "Wind gypsum"),
        ("plywood_separator", "Plywood"),
        ("rubber_floor_finish", "Rubber finish"),
        ("wooden_stud", "Timber"),
        ("Stone wool batts — representative", "Stone wool"),
        ("Soft wood-fibre board — representative", "Soft fibreboard"),
        ("EPS 100 — representative", "EPS 100"),
        ("Stone wool, blowing wool, attic floor — representative", "Loose stone wool"),
        ("Mineral Wool Old (created)", "MW-old"),
        ("Mineral Wool New (created)", "MW-new"),
        ("M01 100mm brick", "Brick"),
        ("25mm Stucco", "Plaster"),
        ("G01 13mm gypsum board", "Gypsum"),
        ("G05 25mm wood", "Wood"),
        ("5/8 in. Plywood", "Plywood"),
        ("I02 50mm insulation board", "EPS"),
        ("Built-up Roofing", "Felt"),
        ("4 in. Normalweight Concrete Wall", "Concrete"),
        ("100mm Normalweight concrete floor", "Concrete"),
        ("6 in. Heavyweight Concrete Roof", "Concrete"),
        ("8 in. Concrete Block Basement Wall", "Conc. block"),
        ("M11 100mm lightweight concrete", "LW concrete"),
    ]
    for long, short in replacements:
        if long.lower() == name.lower():
            return short
    # generic shortening
    if len(name) > 16:
        return name[:14] + "…"
    return name


# ══════════════════════════════════════════════════════════════════
# ELEMENT DISPLAY ORDER AND LABELS
# ══════════════════════════════════════════════════════════════════

_ELEMENT_ORDER = [
    "ROOF",
    "TOP_FLOOR",
    "EXT_WALL",
    "INTERMEDIATE_FLOOR",
    "GROUND_FLOOR",
    "BASEMENT_WALL",
    "BASEMENT_FLOOR",
    "INT_WALL_LOADBEARING",
    "INT_WALL_NONLOADBEARING",
]

_ELEMENT_LABELS = {
    "ROOF": "Roof",
    "TOP_FLOOR": "Attic floor",
    "EXT_WALL": "External wall",
    "EXT_WALL_LOW": "Ext. wall (low)",
    "EXT_WALL_MEDIUM": "Ext. wall (med)",
    "EXT_WALL_HIGH": "Ext. wall (high)",
    "INTERMEDIATE_FLOOR": "Intermediate floor",
    "GROUND_FLOOR": "Ground floor",
    "BASEMENT_WALL": "Basement wall",
    "BASEMENT_FLOOR": "Basement floor",
    "INT_WALL_LOADBEARING": "Internal wall (loadbearing)",
    "INT_WALL_NONLOADBEARING": "Internal partition",
}


# ══════════════════════════════════════════════════════════════════
# DRAWING ENGINE
# ══════════════════════════════════════════════════════════════════

_SECTION_WIDTH = 1.0  # normalised horizontal width for each section
_COMPOSITE_DIVISIONS = 5  # repeat constituent shares evenly along the section
_MM_SCALE = 1000.0  # metres → mm
_MIN_LABEL_MM = 6  # minimum layer mm to put label inside


def _element_total_mm(element: "Element") -> float:
    """Return the total built-up thickness of an element in mm."""
    return (
        sum(slot.layer.thickness for comp in element.components for slot in comp.layers) * _MM_SCALE
    )


def _drawing_layers(element, boundary_details=None):
    """Return drawing-only geometry, retaining the original material objects."""
    layers = [
        (slot.layer.thickness * _MM_SCALE, slot.layer.materials)
        for component in element.components
        for slot in component.layers
    ]
    cavity = (boundary_details or {}).get("facade_cavity")
    if cavity:
        if cavity.get("position") != "behind_single_brick_veneer":
            raise ValueError("Unsupported facade cavity position for section drawing")
        thickness = cavity["thickness_m"] * _MM_SCALE
        if thickness <= 0:
            raise ValueError("Facade cavity must have positive depth")
        layers.insert(cavity.get("after_layer", 1), (thickness, ()))
    return layers


def _draw_element(
    ax, element, *, max_total_mm, max_wall_mm, boundary_details=None, layer_tags=None
):
    """Draw horizontal floor layers and vertical wall layers in physical order."""
    role = element.application
    layers = _drawing_layers(element, boundary_details)
    total_mm = sum(depth for depth, _ in layers)
    wall = role.is_ext_wall or role.is_int_wall or role.value == "BASEMENT_WALL"
    top_first = role.value in {"ROOF", "TOP_FLOOR", "INTERMEDIATE_FLOOR"}
    wall_bottom, wall_height = max_total_mm * 0.35, max_total_mm * 0.40
    cursor, annotations = 0.0, []
    if layer_tags is not None and len(layer_tags) != len(layers):
        raise ValueError("Layer status annotations must match drawing layers")
    for layer_index, (depth, constituents) in enumerate(layers):
        start = total_mm - cursor - depth if top_first else cursor
        label = (
            ("Sealed existing cavity" if (boundary_details or {}).get("facade_cavity", {}).get("ventilation") == "sealed_existing_cavity_assumption" else "Drained cavity")
            if not constituents
            else " / ".join(_short_name(c.material.name) for c in constituents)
        )
        label = (
            (boundary_details or {}).get("layer_label_overrides", {}).get(str(layer_index), label)
        )
        if len(constituents) > 1:
            shares = "/".join(f"{100 * c.area_fraction:g}" for c in constituents)
            label += f" ({shares}%)"
        label += f"  {depth:g} mm"
        if layer_tags:
            label += f"  [{layer_tags[layer_index]}]"
        drawing_parts = [(c.area_fraction, _style_for(c.material.name)) for c in constituents]
        if not constituents:
            drawing_parts = [(1.0, {"facecolor": "white", "edgecolor": "#78909C", "hatch": ""})]
        divisions = _COMPOSITE_DIVISIONS if len(constituents) > 1 else 1
        for division in range(divisions):
            fraction_cursor = division / divisions
            for fraction, style in drawing_parts:
                share = fraction / divisions
                if wall:
                    xy = (cursor / max_wall_mm, wall_bottom + fraction_cursor * wall_height)
                    width, height = depth / max_wall_mm, share * wall_height
                else:
                    xy = (fraction_cursor, start)
                    width, height = share, depth
                ax.add_patch(
                    mpatches.Rectangle(
                        xy,
                        width,
                        height,
                        facecolor=style["facecolor"],
                        edgecolor=style["edgecolor"],
                        hatch=style["hatch"],
                        linewidth=0.8,
                    )
                )
                fraction_cursor += share
        annotations.append((start + depth / 2, label))
        cursor += depth
    if wall:
        width = total_mm / max_wall_mm
        ax.add_patch(
            mpatches.Rectangle(
                (0, wall_bottom),
                width,
                wall_height,
                facecolor="none",
                edgecolor="#222222",
                linewidth=1.6,
            )
        )
        left, right = (
            ("ROOM A", "ROOM B")
            if role.is_int_wall
            else ("GROUND" if role.value == "BASEMENT_WALL" else "OUTSIDE", "ROOM")
        )
        ax.text(
            -0.02,
            wall_bottom + wall_height + 0.03 * max_total_mm,
            left,
            ha="right",
            fontsize=8,
            color="#666666",
        )
        ax.text(
            width + 0.02,
            wall_bottom + wall_height + 0.03 * max_total_mm,
            right,
            ha="left",
            fontsize=8,
            color="#666666",
        )
        # Ordered list avoids misleading leader lines through thin wall layers.
        for index, (_, label) in enumerate(annotations):
            ax.text(
                0,
                max_total_mm * (0.24 - 0.10 * index),
                f"{index + 1}. {label}",
                fontsize=9,
                color="#444444",
                va="top",
            )
    else:
        ax.add_patch(
            mpatches.Rectangle(
                (0, 0),
                _SECTION_WIDTH,
                total_mm,
                facecolor="none",
                edgecolor="#222222",
                linewidth=1.6,
            )
        )
        annotations.sort()
        gap = max(max_total_mm * 0.065, 8)
        positions = []
        for depth, _ in annotations:
            positions.append(max(depth, positions[-1] + gap if positions else depth))
        for (depth, label), position in zip(annotations, positions):
            ax.annotate(
                label,
                xy=(_SECTION_WIDTH, depth),
                xytext=(_SECTION_WIDTH + 0.16, position),
                ha="left",
                va="center",
                fontsize=9,
                color="#444444",
                arrowprops=dict(arrowstyle="-", color="#999999", lw=0.5),
            )
        below, above = ("ROOM", "ATTIC / OUTSIDE") if top_first else ("GROUND", "ROOM")
        if role.value == "ROOF":
            above = "OUTSIDE"
        if role.value == "INTERMEDIATE_FLOOR":
            below, above = "LOWER ROOM", "UPPER ROOM"
        ax.text(
            0.5, -0.035 * max_total_mm, below, ha="center", va="top", fontsize=8, color="#666666"
        )
        ax.text(
            0.5,
            total_mm + 0.025 * max_total_mm,
            above,
            ha="center",
            va="bottom",
            fontsize=8,
            color="#666666",
        )
    ax.set_xlim(-0.20, 2.15)
    # Wall lists need space below the section; floors only need a boundary label.
    # Keep these limits independent of each state's depth to preserve comparison scales.
    ax.set_ylim(
        (-max_total_mm * 0.56, max_total_mm * 0.88)
        if wall
        else (-max_total_mm * 0.12, max_total_mm * 1.15)
    )
    ax.axis("off")


def _draw_window(ax, window, *, status=None, evidence_note=None):
    """Show whole-window properties without inventing frame or pane geometry."""
    ax.axis("off")
    card = mpatches.FancyBboxPatch(
        (0.03, 0.30),
        0.91,
        0.57,
        boxstyle="round,pad=0.02,rounding_size=0.025",
        transform=ax.transAxes,
        facecolor="#F1F6FA",
        edgecolor="#CBD8E2",
        linewidth=1,
    )
    ax.add_patch(card)
    ax.text(
        0.09,
        0.79,
        "WHOLE-WINDOW DEFINITION",
        transform=ax.transAxes,
        fontsize=9,
        color="#426279",
        weight="bold",
    )
    for y, label, value in (
        (0.66, "U-value", f"{window.u_value:.2f} W/(m² K)"),
        (0.54, "Solar gain · SHGC", f"{window.shgc:.2f}"),
        (0.42, "Visible transmittance · VT", f"{window.vt:.2f}"),
    ):
        ax.text(0.09, y, label, transform=ax.transAxes, fontsize=10, color="#456072")
        ax.text(
            0.88,
            y,
            value,
            transform=ax.transAxes,
            fontsize=11,
            weight="bold",
            color="#193F59",
            ha="right",
        )
    ax.text(
        0.09,
        0.13,
        evidence_note or "Frame dimensions and pane layers are unspecified.\nSHGC and VT are representative assumptions.",
        transform=ax.transAxes,
        fontsize=9,
        color="#596A76",
        linespacing=1.6,
    )
    if status:
        ax.text(0.09, 0.03, status, transform=ax.transAxes, fontsize=9, color="#193F59")


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════


def section_scales(archetypes, boundary_details=None):
    """Return shared (vertical depth, wall depth) limits in mm for a set of figures."""
    from epsm_data.domain.element import Element

    archetypes = list(archetypes)
    boundaries = (
        list(boundary_details) if boundary_details is not None else [{} for _ in archetypes]
    )
    if len(boundaries) != len(archetypes):
        raise ValueError("One boundary metadata dictionary is required per archetype")
    depths, wall_depths = [], []
    for archetype, metadata in zip(archetypes, boundaries, strict=True):
        for role, element in archetype.construction_set.elements.items():
            if isinstance(element, Element):
                depth = sum(d for d, _ in _drawing_layers(element, metadata.get(role.value)))
                depths.append(depth)
                if role.is_ext_wall or role.is_int_wall or role.value == "BASEMENT_WALL":
                    wall_depths.append(depth)
    return max(depths, default=200.0), max(wall_depths, default=200.0)


def renovation_annotations(calibrated, existing):
    """Derive drawing annotations from independent Existing-based operations."""
    tags, notes = {}, {}
    operations = {op["role"]: op for op in calibrated.report.get("operations", [])}
    renovated = calibrated.report["key"]["renovation_state"] != "existing"
    for role, element in calibrated.archetype.construction_set.elements.items():
        op = operations.get(role.value)
        if role.value == "WINDOW":
            notes[role.value] = (
                "Replacement whole-window specification"
                if op or any(getattr(element, k) != getattr(existing.archetype.construction_set.elements[role], k)
                             for k in ("u_value", "shgc", "vt"))
                else "Retained whole-window specification" if renovated else "Existing whole-window specification"
            )
            continue
        original = existing.archetype.construction_set.elements[role]
        marks = []
        for component in element.components:
            retained = any(component.layers == c.layers and component.shearing_layer == c.shearing_layer
                           for c in original.components)
            for li, _ in enumerate(component.layers):
                mark = "E" if not renovated else ("K" if retained else "A")
                if op and op["action"] == "replace_exterior" and not retained and li == 0:
                    mark = "R"
                if (
                    op
                    and op.get("position") == "before_inside_finish"
                    and component == original.components[-1]
                ):
                    mark = "S"
                marks.append(mark)
        if calibrated.report["boundary_details"].get(role.value, {}).get("facade_cavity"):
            marks.insert(
                calibrated.report["boundary_details"][role.value]["facade_cavity"].get("after_layer", 1),
                "R" if op and op["action"] == "replace_exterior" else ("K" if renovated else "E"),
            )
        tags[role.value] = marks
        if op and op["action"] == "replace_exterior":
            notes[role.value] = "Old veneer removed; one new veneer and cavity."
        elif op and op.get("position") == "before_inside_finish":
            notes[role.value] = "Insulation added below reinstated floor finish."
        elif op:
            notes[role.value] = "Insulation added to retained construction."
        else:
            notes[role.value] = (
                "Retained from Existing." if renovated else "Existing representative recipe."
            )
    return tags, notes


def _ordered_elements(archetype):
    elements = archetype.construction_set.elements
    lookup = {role.value: element for role, element in elements.items()}
    names = [name for name in _ELEMENT_ORDER if name in lookup]
    names += [role.value for role in elements if role.is_ext_wall and role.value not in names]
    if "WINDOW" in lookup:
        names.append("WINDOW")
    return [(name, lookup[name]) for name in names]


def _plot_panel(
    ax,
    role_name,
    element,
    *,
    scales,
    boundary_details,
    tags=None,
    note=None,
    label=None,
    subtitle_override=None,
):
    from epsm_data.domain.element import WindowElement

    label = label or _ELEMENT_LABELS.get(role_name, role_name.title())
    if isinstance(element, WindowElement):
        _draw_window(ax, element, status=note, evidence_note=(boundary_details or {}).get("window_evidence_note"))
        subtitle = "Thermal and optical properties"
    else:
        _draw_element(
            ax,
            element,
            max_total_mm=scales[0],
            max_wall_mm=scales[1],
            boundary_details=boundary_details,
            layer_tags=tags,
        )
        depth = sum(d for d, _ in _drawing_layers(element, boundary_details))
        u_label = (
            "Assembly U"
            if role_name in {"GROUND_FLOOR", "BASEMENT_FLOOR", "BASEMENT_WALL"}
            else "Nominal U"
        )
        subtitle = f"{u_label} {element.u_value:.3f} W/(m² K)   ·   {depth:g} mm"
        if (
            element.application.is_ext_wall
            or element.application.is_int_wall
            or role_name == "BASEMENT_WALL"
        ):
            subtitle += "\nLayer list: left → right"
        if note:
            ax.text(0, -0.025, note, transform=ax.transAxes, fontsize=9, color="#526372", va="top")
    subtitle = subtitle_override if subtitle_override is not None else subtitle
    ax.set_title(
        f"{label}\n{subtitle}", loc="left", fontsize=11, weight="bold", pad=10, linespacing=1.4
    )


def _figure_key(fig, elements, *, annotated=False, footer_notes=None):
    seen = {}
    for element in elements:
        for component in getattr(element, "components", ()):
            for slot in component.layers:
                for constituent in slot.layer.materials:
                    key = _classify_material(constituent.material.name)
                    seen.setdefault(key, _STYLE_TABLE[key])
    if seen:
        handles = [
            mpatches.Patch(
                facecolor=s["facecolor"],
                edgecolor=s["edgecolor"],
                hatch=s["hatch"],
                label=s["label"],
            )
            for s in seen.values()
        ]
        fig.legend(
            handles=handles,
            loc="lower center",
            ncol=min(len(handles), 6),
            fontsize=9,
            frameon=False,
            bbox_to_anchor=(0.5, 0.014),
        )
    lines = []
    if annotated:
        lines.append(
            "E  Existing   ·   K  Kept   ·   A  Added   ·   R  Replaced   ·   S  Reinstated finish"
        )
    lines += [
        "Five repeated divisions preserve composite area shares; stud spacing and mortar joints are schematic.",
        "Cavities shown contribute depth only; nominal U omits cavity physics. Ground U is assembly-only.",
    ]
    if footer_notes is not None:
        lines = footer_notes
    line_gap = max(0.021, 12 / (72 * fig.get_figheight()))
    for index, line in enumerate(lines):
        fig.text(
            0.5,
            0.073 + (len(lines) - 1 - index) * line_gap,
            line,
            ha="center",
            fontsize=9,
            color="#526372",
        )


def plot_sections(
    archetype: "BuildingArchetype",
    *,
    figsize=None,
    dpi=150,
    title=None,
    show=True,
    boundary_details=None,
    scales=None,
    layer_tags=None,
    role_notes=None,
    ncols=4,
    panel_labels=None,
    panel_subtitles=None,
    subtitle=None,
    footer_notes=None,
) -> Figure:
    """Draw all roles in a readable grid with a whole-window property card.

    ``scales`` is the (vertical depth, wall depth) pair from section_scales;
    reuse it across states to keep the same drawing scale. ``boundary_details``
    adds cavity geometry without changing nominal thermal properties. Optional
    layer_tags/role_notes are supplied by renovation_annotations. Composite
    constituents repeat over five divisions, preserving their area shares.
    Label/subtitle/footer overrides allow source reconstructions to distinguish
    diagnostic layer U-values from published applied values and acceptance.
    """
    ordered = _ordered_elements(archetype)
    if not ordered:
        raise ValueError("Archetype has no elements to plot")
    if isinstance(ncols, bool) or not isinstance(ncols, int) or ncols < 1:
        raise ValueError("ncols must be a positive integer")
    boundary_details = boundary_details or {}
    scales = scales or section_scales([archetype], [boundary_details])
    required = section_scales([archetype], [boundary_details])
    if len(scales) != 2 or any(not isfinite(v) or v < r for v, r in zip(scales, required)):
        raise ValueError("Shared section scales must fit every construction")
    columns = min(ncols, len(ordered))
    rows = ceil(len(ordered) / columns)
    fig, grid = plt.subplots(
        rows, columns, squeeze=False, figsize=figsize or (columns * 5.4, rows * 4.5 + 1.5), dpi=dpi
    )
    axes = list(grid.flat)
    for ax in axes[len(ordered) :]:
        fig.delaxes(ax)
    for ax, (role, element) in zip(axes, ordered):
        _plot_panel(
            ax,
            role,
            element,
            scales=scales,
            boundary_details=boundary_details.get(role),
            tags=(layer_tags or {}).get(role),
            note=(role_notes or {}).get(role),
            label=(panel_labels or {}).get(role),
            subtitle_override=(panel_subtitles or {}).get(role),
        )
    fig.patch.set_facecolor("white")
    fig.suptitle(title or archetype.display_name, fontsize=18, weight="bold", y=0.985)
    fig.text(
        0.5,
        0.94,
        subtitle
        or "Construction sections  ·  shared depth scales for floors and walls  ·  representative recipes",
        ha="center",
        fontsize=11,
        color="#526372",
    )
    _figure_key(
        fig,
        [element for _, element in ordered],
        annotated=bool(layer_tags),
        footer_notes=footer_notes,
    )
    fig.subplots_adjust(left=0.025, right=0.985, top=0.84, bottom=0.17, wspace=0.18, hspace=0.40)
    if show:
        plt.show()
    return fig


def plot_section_comparison(calibrated_states, role, *, dpi=180, show=True):
    """Align Existing/Standard/Advanced for one role using the same depth scale."""
    from epsm_data.domain.enums import BuildingElement

    states = list(calibrated_states)
    if not states:
        raise ValueError("At least one calibrated state is required")
    role = BuildingElement(role) if isinstance(role, str) else role
    base = next((s for s in states if s.report["key"]["renovation_state"] == "existing"), None)
    if base is None:
        raise ValueError("Comparisons require Existing as the annotation baseline")
    # Restrict the scale to this role so small assemblies remain readable.
    elements = [s.archetype.construction_set.elements[role] for s in states]
    depths = [
        sum(d for d, _ in _drawing_layers(e, s.report["boundary_details"].get(role.value)))
        for s, e in zip(states, elements)
        if hasattr(e, "components")
    ]
    scale = max(depths, default=200.0)
    window = role.value == "WINDOW"
    fig, axes = plt.subplots(
        1, len(states), squeeze=False, figsize=(len(states) * 5.7, 4.8 if window else 6), dpi=dpi
    )
    for ax, state, element in zip(axes.flat, states, elements):
        tags, notes = renovation_annotations(state, base)
        _plot_panel(
            ax,
            role.value,
            element,
            scales=(scale, scale),
            boundary_details=state.report["boundary_details"].get(role.value),
            tags=tags.get(role.value),
            note=notes.get(role.value),
            label=state.report["key"]["renovation_state"].title(),
        )
    fig.patch.set_facecolor("white")
    fig.suptitle(
        f"MF SE.02 · {_ELEMENT_LABELS.get(role.value, role.value.title())}",
        fontsize=18,
        weight="bold",
        y=0.98,
    )
    fig.text(
        0.5,
        0.90,
        " → ".join(s.report["key"]["renovation_state"].title() for s in states)
        + (
            "  ·  whole-window properties"
            if role.value == "WINDOW"
            else "  ·  identical depth scale in every panel"
        ),
        ha="center",
        fontsize=11,
        color="#526372",
    )
    if role.value != "WINDOW":
        _figure_key(fig, elements, annotated=True)
    fig.subplots_adjust(
        left=0.03, right=0.985, top=0.74, bottom=0.06 if window else 0.23, wspace=0.20
    )
    if show:
        plt.show()
    return fig
