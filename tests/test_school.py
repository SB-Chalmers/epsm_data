"""Fridhemsskolan published depths, inferred layers and honest draft readiness."""

import json
from pathlib import Path

import pytest

from epsm_data import (
    archetype_from_dict,
    archetype_to_dict,
    load_detailed_catalogue,
    load_school_reference,
    validate_native_handover,
    validate_nominal_handover,
)
from epsm_data.domain import BuildingElement


def save(path, data):
    for name, record in data.items():
        (path / f"{name}.json").write_text(json.dumps(record), encoding="utf-8")


def test_reported_depths_are_preserved_with_provisional_cladding_separate():
    result = load_school_reference()
    wall = result.report["assembly_evidence"]["EXT_WALL"]
    layers = wall["components"][0]["layers"]
    assert [row["thickness"] for row in layers] == [0.023, 0.034, 0.0095, 0.190, 0.025]
    assert layers[0]["evidence_status"] == "provisional"
    assert all(row["evidence_status"] == "source_reported" for row in layers[1:])
    assert wall["boundary_details"]["source_order"] == "inside_to_outside_confirmed_in_figure_8_11"
    roof = result.report["assembly_evidence"]["ROOF"]
    assert [row["thickness"] for row in roof["components"][0]["layers"]] == [
        0.023,
        0.045,
        0.0032,
        0.220,
        0.0125,
        0.028,
    ]
    assert roof["boundary_details"]["table_appendix_order_conflict"]
    ground = result.report["assembly_evidence"]["GROUND_FLOOR"]
    assert [row["thickness"] for row in ground["components"][0]["layers"]] == [0.150, 0.080, 0.100]
    assert result.report["source_u_values"] == {
        "EXT_WALL": 0.17,
        "ROOF": 0.15,
        "GROUND_FLOOR": 0.31,
        "WINDOW": 1.9,
    }


def test_source_identity_and_single_window_do_not_confuse_solar_and_visible_transmittance():
    result = load_school_reference()
    source = result.report["sources"]["fridhemsskolan_2017"]
    assert source["publication_id"] == "PUB-611"
    assert source["publication_type"] == "student_thesis"
    assert source["doi"] is None
    assert "10.3390/en13092325" in result.report["sources"]["steen_englund_2020_school"]["version"]
    assert result.archetype.window.u_value == 1.9
    assert result.archetype.window.shgc == 0.68
    assert result.archetype.window.vt == 0.65
    assert result.report["window"]["vt_status"] == "provisional"
    assert result.report["boundary_details"]["WINDOW"]["source_solar_transmittance"] == 0.6
    assert (
        sum(role == BuildingElement.WINDOW for role in result.archetype.construction_set.elements)
        == 1
    )
    assert not any(
        role.is_ext_wall and role != BuildingElement.EXT_WALL
        for role in result.archetype.construction_set.elements
    )
    panes = result.report["boundary_details"]["WINDOW"]["provisional_glazing_layers"]
    assert [row["thickness_mm"] for row in panes] == [4, 16, 4, 16, 4]
    assert all(row["evidence_status"] == "provisional" for row in panes)


def test_internal_hypotheses_and_inactive_basement_are_labelled_provisional():
    result = load_school_reference()
    for role in ("INT_WALL_NONLOADBEARING", "INTERMEDIATE_FLOOR"):
        assembly = result.report["assembly_evidence"][role]
        assert assembly["evidence_status"] == "provisional"
        assert all(
            row["evidence_status"] == "provisional"
            for c in assembly["components"]
            for row in c["layers"]
        )
    assert BuildingElement.BASEMENT_WALL not in result.archetype.construction_set.elements
    basement = result.report["provisional_hypotheses"]["hus2_basement_wall"]
    assert basement["evidence_status"] == "provisional" and not basement["active"]
    hus2 = result.report["source_block_variations"]["hus2"]
    assert not hus2["active"] and hus2["roof_wool_mm"] == 270
    assert hus2["roof_framing_zones_mm"] == [28, 45]


def test_fridhem_draft_is_retained_as_an_alternative_to_complete_school_states():
    result = load_school_reference()
    assert not result.report["lod2_complete"]
    assert not result.report["lod2_checks"]["nominal_u_alignment"]
    assert result.report["elements"]["EXT_WALL"]["lod1_target_u"] == pytest.approx(0.45980677760922356)
    assert result.report["elements"]["WINDOW"]["lod1_target_u"] == 2.7
    assert result.report["elements"]["GROUND_FLOOR"]["lod1_target_u"] == 0.22
    assert result.report["target_drift"]  # Historical source study differs from current baseline.
    report = load_detailed_catalogue().lod2_completeness()
    assert report["slots_with_layer_recipe"] == 1140
    assert report["lod2_complete_slots"] == 1140
    row = next(row for row in report["states"] if row["archetype_id"] == "school_fridhem")
    assert row["slots_with_recipe"] == 0
    assert len(row["slot_checks"]) == 12
    assert not any(slot["nominal_u_alignment"] for slot in row["slot_checks"])
    assert not row["lod2_complete"]
    assert not any(
        row["readiness"][field]
        for field in ("ground_validation", "carbon_assessment", "simulation")
    )


def test_all_school_periods_and_states_are_complete_with_named_windows():
    catalogue = load_detailed_catalogue()
    report = catalogue.lod2_completeness()
    school = [
        row
        for row in report["states"]
        if row["category"] == "school" and row["archetype_id"] != "school_fridhem"
    ]
    assert len(school) == 19
    assert sum(row["slots_with_recipe"] for row in school) == 228
    assert all(row["lod2_complete"] and len(row["slot_checks"]) == 12 for row in school)
    for era in (f"se0{i}" for i in range(1, 7)):
        archetype = catalogue.archetypes[f"school_{era}"]
        for state in ("standard", "advanced"):
            window = catalogue.assemblies[archetype["states"][state]["assemblies"]["WINDOW"]]
            product = catalogue.materials[window["material_id"]]["selected_product"]
            target = archetype["states"][state]["target_snapshot"]["window"]["value"]
            assert abs(product["declared_uw"] / target - 1) <= .02






def test_portable_and_native_handover_preserve_labels_metrics_and_reversal():
    result = load_school_reference()
    portable = json.loads(json.dumps(result.to_dict(), allow_nan=False))
    assert (
        archetype_to_dict(archetype_from_dict(portable["construction"])) == portable["construction"]
    )
    assert portable["evidence"]["window"]["detailed_layers_status"] == "provisional"
    nominal = result.to_nominal_dict()
    assert validate_nominal_handover(nominal) == {"honeybee": True, "core": True}
    assert sum(row["type"] == "WindowConstruction" for row in nominal["honeybee"].values()) == 1
    for role, row in nominal["honeybee"].items():
        assert row["user_data"]["acceptance"] == "draft_not_lod2_accepted"
        if role == "WINDOW":
            continue
        layers = row["materials"]
        assert nominal["reciprocal"][role]["honeybee"]["materials"] == list(reversed(layers))
        metrics = nominal["roles"][role]
        assert sum(layer["thickness"] / layer["conductivity"] for layer in layers) == pytest.approx(
            metrics["resistance_m2k_w"]
        )
        assert sum(layer["thickness"] * layer["density"] for layer in layers) == pytest.approx(
            metrics["mass_kg_m2"]
        )
        assert sum(
            layer["thickness"] * layer["density"] * layer["specific_heat"] for layer in layers
        ) == pytest.approx(metrics["heat_capacity_j_m2k"])
        assert all(
            layer["user_data"]["density_heat_capacity_surfaces"] == "provisional"
            for layer in layers
        )
    pytest.importorskip("honeybee_energy")
    pytest.importorskip("epsm_core")
    assert validate_native_handover(nominal) == {"honeybee": True, "core": True}


@pytest.mark.parametrize(
    "mutation",
    [
        "depth_label",
        "internal_promoted",
        "glazing_promoted",
        "basement_active",
        "extra_window",
        "source_u",
        "density",
    ],
)
def test_missing_or_misleading_school_evidence_is_rejected(detailed_copy, mutation):
    path, data = detailed_copy
    state = data["archetypes"]["archetypes"]["school_fridhem"]["states"]["existing"]
    assembly = data["assemblies"]["assemblies"]
    if mutation == "depth_label":
        del assembly[state["assemblies"]["ROOF"]]["components"][0]["layers"][0]["evidence_status"]
    elif mutation == "internal_promoted":
        assembly[state["assemblies"]["INTERMEDIATE_FLOOR"]]["components"][0]["layers"][0][
            "evidence_status"
        ] = "source_reported"
    elif mutation == "glazing_promoted":
        assembly[state["assemblies"]["WINDOW"]]["boundary_details"]["provisional_glazing_layers"][
            0
        ]["evidence_status"] = "source_reported"
    elif mutation == "basement_active":
        state["provisional_hypotheses"]["hus2_basement_wall"]["active"] = True
    elif mutation == "extra_window":
        state["assemblies"]["WINDOW_HUS3"] = state["assemblies"]["WINDOW"]
    elif mutation == "source_u":
        state["source_u_values"]["ROOF"] = 0
    else:
        data["honeybee"]["materials"]["EPSM_school_wood"]["density"] = -1
    save(path, data)
    with pytest.raises(ValueError):
        load_school_reference(path)


def test_live_shared_edit_changes_school_without_retuning_source_depth(detailed_copy):
    path, data = detailed_copy
    before = load_school_reference(path)
    data["honeybee"]["materials"]["EPSM_school_eps"]["conductivity"] = 0.04
    save(path, data)
    after = load_school_reference(path)
    assert after.report["revision"] != before.report["revision"]
    assert (
        after.report["elements"]["GROUND_FLOOR"]["assembly_u"]
        > before.report["elements"]["GROUND_FLOOR"]["assembly_u"]
    )
    assert after.report["elements"]["GROUND_FLOOR"]["source_u"] == 0.31
    assert (
        after.report["assembly_evidence"]["GROUND_FLOOR"]["components"][0]["layers"][1]["thickness"]
        == 0.08
    )
    assert not after.report["lod2_complete"]


def test_school_offline_loader_preserves_lod1_without_reading_archive(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "src/epsm_data/datasets/parametric/catalogue.json"
    before = path.read_bytes()
    original = Path.open

    def no_archive(path, *args, **kwargs):
        assert "ARCHIVE" not in path.parts
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", no_archive)
    assert load_school_reference().report["status"] == "source_and_provisional_draft"
    assert path.read_bytes() == before
