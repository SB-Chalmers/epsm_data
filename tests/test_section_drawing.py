"""Physical orientation is presentation only; nominal constructions stay fixed."""


import pytest

from epsm_data import load_calibrated_archetype as _load


def load_calibrated_archetype(**kwargs):
    return _load(**kwargs)

@pytest.fixture
def drawing():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    from epsm_data.reporting.section_drawing import plot_sections

    return plt, plot_sections


@pytest.mark.parametrize("state", ["existing", "standard", "advanced"])
def test_sections_have_correct_floor_wall_orientation_and_cavity(state, drawing):
    plt, plot_sections = drawing
    result = load_calibrated_archetype(renovation_state=state)
    before = result.to_dict()
    fig = plot_sections(
        result.archetype, boundary_details=result.report["boundary_details"], show=False
    )
    assert len(fig.axes) == 7
    roof, wall, intermediate, ground, basement, partition, _ = fig.axes
    # Roof/attic order is above-to-below; concrete must be below all insulation.
    roof_solids = roof.patches[:-1]
    assert roof_solids[-1].get_y() == 0
    assert roof_solids[0].get_y() > roof_solids[-1].get_y()
    # Upper-floor finish lies above concrete; ceiling plaster is at the bottom.
    assert intermediate.patches[0].get_y() > intermediate.patches[2].get_y()
    assert intermediate.patches[3].get_y() == 0
    # Ground assemblies retain bottom-to-top order: aggregate below finish.
    assert ground.patches[0].get_y() == 0
    assert ground.patches[-2].get_y() > ground.patches[0].get_y()
    # A single veneer, then cavity, then wool and lining, left to right.
    offset = 0 if state == "existing" else 1
    brick, mortar = wall.patches[offset:offset + 2]
    cavity = wall.patches[offset + 10]
    assert brick.get_x() == mortar.get_x()
    assert brick.get_x() == (0 if state == "existing" else wall.patches[0].get_width())
    assert cavity.get_x() == pytest.approx(brick.get_x() + brick.get_width())
    assert cavity.get_width() / brick.get_width() == pytest.approx(25 / 125)
    assert ("Drained cavity" if state == "existing" else "Sealed existing cavity") in " ".join(t.get_text() for t in wall.texts)
    assert wall.patches[-2].get_x() > cavity.get_x()
    # Repeated joints/studs retain the same area shares and full layer depth.
    for axis, first, shares in ((wall, offset, (0.85, 0.15)), (partition, 1, (0.8, 0.2))):
        patches = axis.patches[first : first + 10]
        height = sum(p.get_height() for p in patches)
        for index, patch in enumerate(patches):
            assert patch.get_height() / height == pytest.approx(shares[index % 2] / 5)
            assert patch.get_x() == patches[0].get_x()
            assert patch.get_width() == patches[0].get_width()
            if index:
                previous = patches[index - 1]
                assert patch.get_y() == pytest.approx(previous.get_y() + previous.get_height())
    # The current packages retain basement fabric; no unsupported XPS addition.
    assert basement.patches[0].get_x() == 0
    assert "XPS" not in " ".join(t.get_text() for t in basement.texts)
    assert {t.get_text() for t in partition.texts} >= {"ROOM A", "ROOM B"}
    assert not {"EXT", "INT"} & {t.get_text() for t in partition.texts}
    assert before == result.to_dict()
    plt.close(fig)


def test_default_plot_remains_a_nominal_layer_drawing_without_cavity(drawing):
    plt, plot_sections = drawing
    result = load_calibrated_archetype()
    fig = plot_sections(result.archetype, show=False)
    assert "Drained cavity" not in " ".join(t.get_text() for t in fig.axes[1].texts)
    plt.close(fig)


def test_shared_overview_scales_preserve_pixel_thickness_and_window_properties(drawing):
    plt, plot_sections = drawing
    from epsm_data.reporting.section_drawing import section_scales

    states = [
        load_calibrated_archetype(renovation_state=s) for s in ("existing", "standard", "advanced")
    ]
    scales = section_scales(
        [s.archetype for s in states], [s.report["boundary_details"] for s in states]
    )
    widths, heights = [], []
    for state in states:
        fig = plot_sections(
            state.archetype,
            scales=scales,
            boundary_details=state.report["boundary_details"],
            show=False,
        )
        fig.canvas.draw()
        brick_index = 0 if state.report["key"]["renovation_state"] == "existing" else 1
        widths.append(fig.axes[1].patches[brick_index].get_window_extent().width)
        # The retained attic concrete is 140 mm in every state.
        heights.append(fig.axes[0].patches[-2].get_window_extent().height)
        window = fig.axes[-1]
        assert len(window.patches) == 1
        assert not window.patches[0].get_hatch()
        labels = " ".join(t.get_text() for t in window.texts)
        assert "Frame dimensions and pane layers are unspecified" in labels
        assert "Visible transmittance" in labels
        assert "SHGC" in labels
        plt.close(fig)
    assert widths == pytest.approx([widths[0]] * 3)
    assert heights == pytest.approx([heights[0]] * 3)


def test_renovation_markers_and_window_comparison(drawing):
    plt, _ = drawing
    from epsm_data.reporting.section_drawing import (
        plot_section_comparison,
        renovation_annotations,
    )

    states = [
        load_calibrated_archetype(renovation_state=s) for s in ("existing", "standard", "advanced")
    ]
    existing_tags, _ = renovation_annotations(states[0], states[0])
    assert {tag for tags in existing_tags.values() for tag in tags} == {"E"}
    for state in states[1:]:
        tags, _ = renovation_annotations(state, states[0])
        assert tags["EXT_WALL"][:3] == ["A", "K", "K"]
        assert "A" in tags["EXT_WALL"]
        assert "K" in tags["EXT_WALL"]
        assert set(tags["GROUND_FLOOR"]) == {"K"}
        assert set(tags["BASEMENT_WALL"]) == {"K"}
    fig = plot_section_comparison(states, "WINDOW", show=False)
    assert len(fig.axes) == 3
    assert [ax.get_title(loc="left").split("\n")[0] for ax in fig.axes] == [
        "Existing",
        "Standard",
        "Advanced",
    ]
    assert all(len(ax.patches) == 1 for ax in fig.axes)
    assert "depth scale" not in " ".join(t.get_text() for t in fig.texts)
    plt.close(fig)
