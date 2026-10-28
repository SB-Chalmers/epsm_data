"""Section drawings compare ordinary physical definitions without catalogue history."""

from uuid import uuid4

import pytest

from epsm_data import Archetype, BuildingElement, Catalogue, archetype_to_dict


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture
def drawing():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    from epsm_data.plotting import plot_sections

    return plt, plot_sections


def example(catalogue, state="existing"):
    archetype = catalogue.get("mf_se02", state=state)
    boundaries = catalogue.nominal_metadata("mf_se02", state=state)["boundary_details"]
    return archetype, boundaries


@pytest.mark.parametrize("state", ["existing", "standard", "advanced"])
def test_sections_have_correct_floor_wall_orientation_and_cavity(state, drawing, catalogue):
    plt, plot_sections = drawing
    archetype, boundaries = example(catalogue, state)
    before = archetype_to_dict(archetype)
    fig = plot_sections(archetype, boundary_details=boundaries, show=False)
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
    # The retained veneer/cavity follow the new brick and wool in renovated walls.
    offset = 0 if state == "existing" else 2
    brick, mortar = wall.patches[offset:offset + 2]
    cavity = wall.patches[offset + 10]
    assert brick.get_x() == mortar.get_x()
    if state == "existing":
        assert brick.get_x() == 0
    else:
        new_brick, added_wool = wall.patches[:2]
        assert new_brick.get_x() == 0
        assert added_wool.get_x() == pytest.approx(new_brick.get_width())
        assert brick.get_x() == pytest.approx(new_brick.get_width() + added_wool.get_width())
        assert new_brick.get_width() / brick.get_width() == pytest.approx(120 / 125)
        added_mm = 50 if state == "standard" else 300
        assert added_wool.get_width() / brick.get_width() == pytest.approx(added_mm / 125)
        assert boundaries["EXT_WALL"]["facade_cavity"]["after_layer"] == 3
    assert cavity.get_x() == pytest.approx(brick.get_x() + brick.get_width())
    assert cavity.get_width() / brick.get_width() == pytest.approx(25 / 125)
    label = "Drained cavity" if state == "existing" else "Sealed existing cavity"
    assert label in " ".join(t.get_text() for t in wall.texts)
    assert wall.patches[-2].get_x() > cavity.get_x()
    # Repeated joints/studs retain the same area shares and full layer depth.
    for axis, first, shares in ((wall, offset, (0.85, 0.15)), (partition, 1, (0.8, 0.2))):
        patches = axis.patches[first:first + 10]
        height = sum(p.get_height() for p in patches)
        for index, patch in enumerate(patches):
            assert patch.get_height() / height == pytest.approx(shares[index % 2] / 5)
            assert patch.get_x() == patches[0].get_x()
            assert patch.get_width() == patches[0].get_width()
            if index:
                previous = patches[index - 1]
                assert patch.get_y() == pytest.approx(previous.get_y() + previous.get_height())
    assert basement.patches[0].get_x() == 0
    assert "XPS" not in " ".join(t.get_text() for t in basement.texts)
    assert {t.get_text() for t in partition.texts} >= {"ROOM A", "ROOM B"}
    assert not {"EXT", "INT"} & {t.get_text() for t in partition.texts}
    assert before == archetype_to_dict(archetype)
    plt.close(fig)


def test_default_plot_remains_a_nominal_layer_drawing_without_cavity(drawing, catalogue):
    plt, plot_sections = drawing
    archetype, _ = example(catalogue)
    fig = plot_sections(archetype, show=False)
    assert "Drained cavity" not in " ".join(t.get_text() for t in fig.axes[1].texts)
    plt.close(fig)


def test_shared_overview_scales_preserve_pixel_thickness_and_window_properties(drawing, catalogue):
    plt, plot_sections = drawing
    from epsm_data.plotting import section_scales

    examples = [example(catalogue, state) for state in ("existing", "standard", "advanced")]
    scales = section_scales([a for a, _ in examples], [b for _, b in examples])
    widths, heights = [], []
    for index, (archetype, boundaries) in enumerate(examples):
        fig = plot_sections(archetype, scales=scales, boundary_details=boundaries, show=False)
        fig.canvas.draw()
        brick_index = 0 if index == 0 else 2
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


def test_physical_annotations_and_window_comparison(drawing, catalogue):
    plt, _ = drawing
    from epsm_data.plotting import (
        plot_section_comparison,
        renovation_annotations,
    )

    examples = [example(catalogue, state) for state in ("existing", "standard", "advanced")]
    baseline, baseline_boundaries = examples[0]
    baseline_tags, _ = renovation_annotations(
        baseline, baseline, boundary_details=baseline_boundaries
    )
    assert {tag for tags in baseline_tags.values() for tag in tags} == {"E"}
    for state, (archetype, boundaries) in zip(
        ("standard", "advanced"), examples[1:], strict=True,
    ):
        tags, _ = renovation_annotations(
            archetype, baseline, boundary_details=boundaries,
            baseline_boundary_details=baseline_boundaries,
        )
        # New brick and wool, retained veneer, then changed cavity ventilation metadata.
        assert tags["EXT_WALL"][:4] == ["A", "A", "K", "A"]
        assert tags["GROUND_FLOOR"] == ["K", "K", "K", "A", "A"]
        assert tags["BASEMENT_WALL"] == (["K", "K"] if state == "standard"
                                         else ["K", "K", "A", "A"])
        floor = archetype.construction_set.elements[BuildingElement.GROUND_FLOOR]
        layers = [slot.layer for component in floor.components for slot in component.layers]
        # The top course is the added mineral finish, above the added EPS.
        assert len(layers) == 5 and layers[-1].thickness == 0.05
    labels = ["Existing", "Standard", "Advanced"]
    fig = plot_section_comparison(
        [a for a, _ in examples], "WINDOW", labels=labels,
        boundary_details=[b for _, b in examples], show=False,
    )
    assert len(fig.axes) == 3
    assert [ax.get_title(loc="left").split("\n")[0] for ax in fig.axes] == labels
    assert all(len(ax.patches) == 1 for ax in fig.axes)
    assert "depth scale" not in " ".join(t.get_text() for t in fig.texts)
    assert fig._suptitle.get_text() == "Window"
    plt.close(fig)


def test_comparison_ignores_authoring_names_and_material_instance_ids(drawing, catalogue):
    from epsm_data.domain import BuildingElement
    from epsm_data.plotting import renovation_annotations

    baseline, _ = example(catalogue)
    role = BuildingElement.EXT_WALL
    wall = baseline.construction_set.elements[role]
    components = []
    for index, component in enumerate(wall.components):
        slots = []
        for slot in component.layers:
            layer = slot.layer.with_changes(
                name="Renamed layer", layer_code=str(uuid4()),
                materials=tuple(c.with_changes(material=c.material.with_changes(
                    name="Renamed material", json_id=str(uuid4()), uuid=uuid4()
                )) for c in slot.layer.materials),
            )
            slots.append(slot.with_changes(layer=layer))
        components.append(component.with_changes(name=f"Renamed {index}", layers=tuple(slots)))
    wall = wall.with_changes(name="Renamed wall", components=tuple(components))
    authored = baseline.with_changes(
        archetype_id="custom", display_name="Custom authored building",
        construction_set=baseline.construction_set.with_element(role, wall),
    )
    tags, _ = renovation_annotations(authored, baseline)
    assert set(tags["EXT_WALL"]) == {"K"}


def test_comparison_supports_custom_archetypes_and_missing_baseline_roles(drawing, catalogue):
    plt, _ = drawing
    from epsm_data.plotting import (
        plot_section_comparison,
        renovation_annotations,
    )

    archetype, boundaries = example(catalogue)
    empty = Archetype("empty", "Empty authoring baseline")
    tags, notes = renovation_annotations(archetype, empty, boundary_details=boundaries)
    assert {tag for marks in tags.values() for tag in marks} == {"A"}
    assert notes["WINDOW"] == "Added whole-window specification"
    fig = plot_section_comparison(
        [archetype], "EXT_WALL", baseline=empty,
        boundary_details=[boundaries], title="Custom wall comparison", show=False,
    )
    assert fig._suptitle.get_text() == "Custom wall comparison"
    assert fig.axes[0].get_title(loc="left").startswith(archetype.display_name)
    plt.close(fig)


def test_comparison_validates_labels_boundaries_and_missing_roles(drawing, catalogue):
    from epsm_data.plotting import plot_section_comparison

    archetype, _ = example(catalogue)
    with pytest.raises(ValueError, match="At least one archetype"):
        plot_section_comparison([], "EXT_WALL", show=False)
    with pytest.raises(ValueError, match="boundary metadata"):
        plot_section_comparison([archetype], "EXT_WALL", boundary_details=[], show=False)
    with pytest.raises(ValueError, match="nonempty label"):
        plot_section_comparison([archetype], "EXT_WALL", labels=[], show=False)
    with pytest.raises(ValueError, match="must supply EXT_WALL"):
        plot_section_comparison([Archetype("empty", "Empty")], "EXT_WALL", show=False)
