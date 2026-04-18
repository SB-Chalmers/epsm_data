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

import textwrap
from typing import TYPE_CHECKING

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

if TYPE_CHECKING:
    from epsm_data.domain.building import BuildingArchetype
    from epsm_data.domain.element import Element, WindowElement


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
]

_ELEMENT_LABELS = {
    "ROOF": "Roof",
    "TOP_FLOOR": "Top floor",
    "EXT_WALL": "Ext. wall",
    "EXT_WALL_LOW": "Ext. wall (low)",
    "EXT_WALL_MEDIUM": "Ext. wall (med)",
    "EXT_WALL_HIGH": "Ext. wall (high)",
    "INTERMEDIATE_FLOOR": "Intermed. floor",
    "GROUND_FLOOR": "Ground floor",
    "BASEMENT_WALL": "Basement wall",
    "BASEMENT_FLOOR": "Basement floor",
}


# ══════════════════════════════════════════════════════════════════
# DRAWING ENGINE
# ══════════════════════════════════════════════════════════════════

_SECTION_WIDTH = 1.0  # normalised horizontal width for each section
_MM_SCALE = 1000.0  # metres → mm
_MIN_LABEL_MM = 6  # minimum layer mm to put label inside


def _element_total_mm(element: "Element") -> float:
    """Return the total built-up thickness of an element in mm."""
    return sum(
        slot.layer.thickness
        for comp in element.components
        for slot in comp.layers
    ) * _MM_SCALE


def _draw_element(ax: plt.Axes, element: "Element", *, max_total_mm: float) -> None:
    """Draw one element cross section on *ax*."""
    from epsm_data.domain.element import Element

    if not isinstance(element, Element):
        return  # skip WindowElement

    y = 0.0  # bottom of current layer (in mm)

    for comp in element.components:
        for slot in comp.layers:
            layer = slot.layer
            t_mm = layer.thickness * _MM_SCALE

            if layer.is_composite:
                # Draw composite as side-by-side strips
                x_cursor = 0.0
                for lm in layer.materials:
                    w = lm.area_fraction * _SECTION_WIDTH
                    style = _style_for(lm.material.name)
                    rect = mpatches.FancyBboxPatch(
                        (x_cursor, y), w, t_mm,
                        boxstyle="square,pad=0",
                        facecolor=style["facecolor"],
                        edgecolor=style["edgecolor"],
                        hatch=style["hatch"],
                        linewidth=0.8,
                    )
                    ax.add_patch(rect)
                    x_cursor += w
                # Label the composite
                label = "Stud + MW"
                ax.text(
                    _SECTION_WIDTH + 0.08, y + t_mm / 2,
                    f"{label}  {t_mm:.0f}",
                    ha="left", va="center",
                    fontsize=6.5, color="#444444",
                )
                # Dimension line
                ax.plot(
                    [_SECTION_WIDTH + 0.04, _SECTION_WIDTH + 0.04],
                    [y + 1, y + t_mm - 1],
                    color="#999999", linewidth=0.4,
                )
            else:
                # Single material layer
                mat_name = layer.materials[0].material.name
                style = _style_for(mat_name)
                rect = mpatches.FancyBboxPatch(
                    (0, y), _SECTION_WIDTH, t_mm,
                    boxstyle="square,pad=0",
                    facecolor=style["facecolor"],
                    edgecolor=style["edgecolor"],
                    hatch=style["hatch"],
                    linewidth=0.8,
                )
                ax.add_patch(rect)

                short = _short_name(mat_name)
                # Label to the right side for all layers
                ax.text(
                    _SECTION_WIDTH + 0.08, y + t_mm / 2,
                    f"{short}  {t_mm:.0f}",
                    ha="left", va="center",
                    fontsize=6.5, color="#444444",
                )
                # Dimension tick marks
                ax.plot(
                    [_SECTION_WIDTH + 0.04, _SECTION_WIDTH + 0.04],
                    [y + 1, y + t_mm - 1],
                    color="#999999", linewidth=0.4,
                )

            y += t_mm

    # Draw outer boundary with heavier line weight
    total_mm = y
    border = mpatches.FancyBboxPatch(
        (0, 0), _SECTION_WIDTH, total_mm,
        boxstyle="square,pad=0",
        facecolor="none",
        edgecolor="#222222",
        linewidth=1.6,
    )
    ax.add_patch(border)

    # Outside / inside markers
    ax.annotate(
        "EXT", xy=(_SECTION_WIDTH / 2, 0),
        xytext=(_SECTION_WIDTH / 2, -8),
        ha="center", va="top", fontsize=6, color="#666666",
        fontstyle="italic",
        arrowprops=dict(arrowstyle="-", color="#AAAAAA", lw=0.5),
    )
    ax.annotate(
        "INT", xy=(_SECTION_WIDTH / 2, total_mm),
        xytext=(_SECTION_WIDTH / 2, total_mm + 8),
        ha="center", va="bottom", fontsize=6, color="#666666",
        fontstyle="italic",
        arrowprops=dict(arrowstyle="-", color="#AAAAAA", lw=0.5),
    )

    # Use a shared vertical scale across all panels so thickness remains comparable.
    ax.set_xlim(-0.08, _SECTION_WIDTH + 0.80)
    pad = max(max_total_mm * 0.08, 15)
    ax.set_ylim(-pad, max_total_mm + pad)
    ax.axis("off")


def _draw_window(ax: plt.Axes, window: "WindowElement", *, max_total_mm: float) -> None:
    """Draw a simplified window cross section.

    The window panel is schematic rather than thickness-accurate.
    """
    from epsm_data.domain.element import WindowElement

    if not isinstance(window, WindowElement):
        return

    total_h = min(max(max_total_mm * 0.82, 160), max_total_mm)
    glass_w = _SECTION_WIDTH * 0.6
    frame_w = _SECTION_WIDTH * 0.2

    # Frame left
    frame_l = mpatches.FancyBboxPatch(
        (0, 0), frame_w, total_h,
        boxstyle="square,pad=0",
        facecolor="#E8C882", edgecolor="#8B6914",
        hatch="---", linewidth=0.8,
    )
    ax.add_patch(frame_l)

    # Glass
    glass = mpatches.FancyBboxPatch(
        (frame_w, total_h * 0.05), glass_w, total_h * 0.9,
        boxstyle="square,pad=0",
        facecolor="#C8E0F4", edgecolor="#5080A0",
        linewidth=0.6, alpha=0.8,
    )
    ax.add_patch(glass)

    # Frame right
    frame_r = mpatches.FancyBboxPatch(
        (frame_w + glass_w, 0), frame_w, total_h,
        boxstyle="square,pad=0",
        facecolor="#E8C882", edgecolor="#8B6914",
        hatch="---", linewidth=0.8,
    )
    ax.add_patch(frame_r)

    # Border
    border = mpatches.FancyBboxPatch(
        (0, 0), _SECTION_WIDTH, total_h,
        boxstyle="square,pad=0",
        facecolor="none", edgecolor="#222222",
        linewidth=1.6,
    )
    ax.add_patch(border)

    # Annotations
    ax.text(
        _SECTION_WIDTH / 2, total_h * 0.55,
        f"U = {window.u_value:.2f}",
        ha="center", va="center",
        fontsize=8, fontweight="bold", color="#2050A0",
    )
    ax.text(
        _SECTION_WIDTH / 2, total_h * 0.40,
        f"SHGC = {window.shgc:.2f}",
        ha="center", va="center",
        fontsize=7, color="#2050A0",
    )
    ax.text(
        _SECTION_WIDTH / 2, total_h * 0.06,
        "schematic",
        ha="center", va="bottom",
        fontsize=6, color="#6A6A6A", fontstyle="italic",
    )

    ax.set_xlim(-0.08, _SECTION_WIDTH + 0.80)
    pad = max(max_total_mm * 0.08, 15)
    ax.set_ylim(-pad, max_total_mm + pad)
    ax.axis("off")


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════


def plot_sections(
    archetype: "BuildingArchetype",
    *,
    figsize: tuple[float, float] | None = None,
    dpi: int = 150,
    title: str | None = None,
    show: bool = True,
) -> Figure:
    """Draw architectural cross sections for every element in *archetype*.

    Parameters
    ----------
    archetype : BuildingArchetype
        The archetype to visualize.
    figsize : tuple, optional
        Figure size (width, height) in inches. Auto-calculated if None.
    dpi : int
        Resolution.
    title : str, optional
        Override the figure suptitle.
    show : bool
        Call ``plt.show()`` after drawing. Set False for non-interactive use.

    Returns
    -------
    matplotlib.figure.Figure
    """
    from epsm_data.domain.building import BuildingArchetype
    from epsm_data.domain.element import Element, WindowElement
    from epsm_data.domain.enums import BuildingElement

    elements = archetype.construction_set.elements

    # Sort elements by architectural order
    ordered: list[tuple[str, object]] = []
    for role_name in _ELEMENT_ORDER:
        role = BuildingElement[role_name]
        if role in elements:
            ordered.append((role_name, elements[role]))

    # Add any wall variants not in the standard order
    for role, elem in elements.items():
        if role.is_ext_wall and role.value not in [r for r, _ in ordered]:
            ordered.append((role.value, elem))

    # Window last
    if BuildingElement.WINDOW in elements:
        ordered.append(("WINDOW", elements[BuildingElement.WINDOW]))

    n = len(ordered)
    if n == 0:
        raise ValueError("Archetype has no elements to plot.")

    if figsize is None:
        figsize = (min(n * 2.8, 24), 8)

    fig, axes = plt.subplots(1, n, figsize=figsize, dpi=dpi)
    if n == 1:
        axes = [axes]

    fig.patch.set_facecolor("white")

    max_total_mm = max(
        (_element_total_mm(elem) for _, elem in ordered if isinstance(elem, Element)),
        default=200.0,
    )

    for ax, (role_name, elem) in zip(axes, ordered):
        label = _ELEMENT_LABELS.get(role_name, role_name)
        if isinstance(elem, WindowElement):
            _draw_window(ax, elem, max_total_mm=max_total_mm)
            sub = f"U = {elem.u_value:.2f}"
        elif isinstance(elem, Element):
            _draw_element(ax, elem, max_total_mm=max_total_mm)
            total_mm = _element_total_mm(elem)
            sub = f"U = {elem.u_value:.2f}  |  {total_mm:.0f} mm"
        else:
            continue

        ax.set_title(
            f"{label}\n{sub}",
            fontsize=8, fontweight="bold", pad=6,
            loc="left",
        )

    # Suptitle
    if title is None:
        title = f"{archetype.display_name}  ({archetype.construction_year})"
    fig.suptitle(title, fontsize=12, fontweight="bold", y=0.98)

    # Legend
    seen: dict[str, dict] = {}
    for role_name, elem in ordered:
        if not isinstance(elem, Element):
            continue
        for comp in elem.components:
            for slot in comp.layers:
                layer = slot.layer
                if layer.is_composite:
                    key = "composite"
                    seen.setdefault(key, _STYLE_TABLE["composite"])
                    for lm in layer.materials:
                        mk = _classify_material(lm.material.name)
                        seen.setdefault(mk, _STYLE_TABLE.get(mk, _STYLE_TABLE["_default"]))
                else:
                    mk = _classify_material(layer.materials[0].material.name)
                    seen.setdefault(mk, _STYLE_TABLE.get(mk, _STYLE_TABLE["_default"]))

    legend_handles = []
    for key, style in seen.items():
        patch = mpatches.Patch(
            facecolor=style["facecolor"],
            edgecolor=style["edgecolor"],
            hatch=style["hatch"],
            label=style["label"],
            linewidth=0.8,
        )
        legend_handles.append(patch)

    if legend_handles:
        fig.legend(
            handles=legend_handles,
            loc="lower center",
            ncol=min(len(legend_handles), 8),
            fontsize=7,
            frameon=True,
            fancybox=True,
            edgecolor="#CCCCCC",
            bbox_to_anchor=(0.5, 0.01),
        )

    fig.subplots_adjust(
        left=0.02, right=0.98, top=0.85, bottom=0.10,
        wspace=0.25,
    )

    if show:
        plt.show()

    return fig
