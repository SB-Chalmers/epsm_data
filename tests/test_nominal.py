"""Catalogue acceptance and storage-preserving native handovers."""

import json

import pytest

from epsm_data import (
    load_calibrated_archetype,
    load_detailed_catalogue,
    validate_native_handover,
    validate_nominal_handover,
)


def save(path, data):
    for name, record in data.items():
        (path / f"{name}.json").write_text(json.dumps(record))


@pytest.mark.parametrize("state", ["existing", "standard", "advanced"])
def test_export_conserves_catalogue_resistance_mass_capacity_and_order(state):
    calibrated = load_calibrated_archetype(renovation_state=state)
    bundle = json.loads(json.dumps(calibrated.to_nominal_dict(), allow_nan=False))
    assert validate_nominal_handover(bundle) == {"honeybee": True, "core": True}
    assert bundle["sources"] == calibrated.report["sources"]
    assert bundle["construction_revision"] == calibrated.report["revision"]
    for role, element in calibrated.archetype.construction_set.elements.items():
        name = role.value
        if name == "WINDOW":
            assert bundle["roles"][name]["mass_kg_m2"] is None
            continue
        layers = [slot.layer for component in element.components for slot in component.layers]
        exported = bundle["honeybee"][name]["materials"]
        assert len(layers) == len(exported)
        for layer, material in zip(layers, exported, strict=True):
            density = sum(c.area_fraction * c.material.density for c in layer.materials)
            capacity = sum(
                c.area_fraction * c.material.density * c.material.specific_heat
                for c in layer.materials
            )
            assert material["thickness"] / material["conductivity"] == pytest.approx(layer.r_value)
            assert material["thickness"] == layer.thickness
            assert material["density"] == pytest.approx(density)
            assert material["specific_heat"] * material["density"] == pytest.approx(capacity)
            assert [
                c["source_reference"]["json_id"] for c in material["user_data"]["constituents"]
            ] == [c.material.json_id for c in layer.materials]
            if layer.is_composite:
                assert material["user_data"]["representation"] == "derived_equivalent"
                assert material["user_data"]["carbon_mapping"] == "constituents_only"
                # A simple area-weighted cp would lose storage for unlike densities.
                naive_cp = sum(c.area_fraction * c.material.specific_heat for c in layer.materials)
                assert material["specific_heat"] != pytest.approx(naive_cp)
        metrics = bundle["roles"][name]
        assert metrics["nominal_u_w_m2k"] == pytest.approx(element.u_value)
        assert metrics["mass_kg_m2"] == pytest.approx(
            sum(
                layer.thickness * sum(c.area_fraction * c.material.density for c in layer.materials)
                for layer in layers
            )
        )
        assert metrics["heat_capacity_j_m2k"] == pytest.approx(
            sum(
                layer.thickness
                * sum(
                    c.area_fraction * c.material.density * c.material.specific_heat
                    for c in layer.materials
                )
                for layer in layers
            )
        )
        assert bundle["reciprocal"][name]["honeybee"]["materials"] == list(reversed(exported))
    wall = bundle["roles"]["EXT_WALL"]["boundary_details"]
    assert wall["facade_cavity"]["thickness_m"] == 0.025
    assert "omitted" in wall["facade_cavity"]["nominal_projection"]
    brick_layers = [
        m
        for m in bundle["honeybee"]["EXT_WALL"]["materials"]
        if any(
            c["source_reference"]["registry_id"] == "brick" for c in m["user_data"]["constituents"]
        )
    ]
    assert len(brick_layers) == 1
    assert calibrated.report["lod2_complete"]
    assert not any(
        bundle["readiness"][f] for f in ("ground_validation", "carbon_assessment", "simulation")
    )


@pytest.mark.parametrize("state", ["existing", "standard", "advanced"])
def test_native_constructions_roundtrip_and_installed_core_types(state):
    pytest.importorskip("honeybee_energy")
    pytest.importorskip("epsm_core")
    from honeybee_energy.construction.dictutil import dict_to_construction

    bundle = load_calibrated_archetype(renovation_state=state).to_nominal_dict()
    assert validate_native_handover(bundle) == {"honeybee": True, "core": True}
    for role, record in bundle["honeybee"].items():
        native = dict_to_construction(record)
        assert native.to_dict()["user_data"] == record["user_data"]
        if role != "WINDOW":
            reverse = dict_to_construction(bundle["reciprocal"][role]["honeybee"])
            assert dict_to_construction(reverse.to_dict()) == reverse
            assert list(reverse.materials) == list(reversed(native.materials))


@pytest.mark.parametrize("mutation", ["storage", "order", "films", "window", "role"])
def test_corrupt_nominal_handover_is_rejected(mutation):
    bundle = load_calibrated_archetype().to_nominal_dict()
    if mutation == "storage":
        bundle["core"]["EXT_WALL"]["layers"][0]["material"]["specific_heat_j_kgk"] += 1
    elif mutation == "order":
        bundle["reciprocal"]["EXT_WALL"]["core"]["layers"].reverse()
    elif mutation == "films":
        bundle["core"]["TOP_FLOOR"]["surface_resistance_m2k_w"] += 0.1
    elif mutation == "window":
        bundle["core"]["WINDOW"]["visible_transmittance"] = 0.5
    else:
        del bundle["honeybee"]["GROUND_FLOOR"]
    with pytest.raises(ValueError):
        validate_nominal_handover(bundle)


@pytest.mark.parametrize(
    "status,accepted", [("open", False), ("accepted_assumption", True), ("resolved", True)]
)
def test_catalogue_caveats_block_acceptance_until_explicitly_reviewed(
    detailed_copy, status, accepted
):
    path, data = detailed_copy
    data["materials"]["materials"]["woodfiber_board"]["caveats"].append(
        {
            "id": "additional_review",
            "status": status,
            "severity": "blocking",
            "topic": "thermal",
            "scope": "catalogue",
            "source": "lod2_review",
            "note": "Additional thermal review required.",
            "resolution": None
            if status == "open"
            else "Representative assumption reviewed; no measurement claimed.",
        }
    )
    save(path, data)
    result = load_calibrated_archetype(path)
    assert result.report["lod2_complete"] is accepted
    assert any(c["id"] == "additional_review" for c in result.report["caveats"])
    # Reviewed v1.3 states are independent full recipes.
    assert load_calibrated_archetype(path, renovation_state="standard").report["lod2_complete"] is accepted


def test_rejected_mapping_candidate_and_missing_official_values_remain_unknown():
    catalogue = load_detailed_catalogue()
    board = catalogue.resolve_material("woodfiber_board")
    assert board["boverket_id"] == "6000000216"
    assert board["candidate_boverket_id"] == "6000000136"
    rubber = catalogue.resolve_material("rubber_floor_finish")["properties"]["embodied_carbon"]
    assert rubber["biogenic_carbon"] is None
    assert rubber["conversion_factor"] is None
    for legacy in ("linoleum", "asphalt_board", "cardboard"):
        assert catalogue.materials[legacy]["mapping_status"] == "pending"
        assert legacy not in catalogue.active_material_ids()


@pytest.mark.parametrize("state", ["existing", "standard", "advanced"])
@pytest.mark.parametrize("tolerance", [3, 6])
def test_nominal_rule_rejects_unsupported_tolerances(detailed_copy, state, tolerance):
    path, data = detailed_copy
    data["archetypes"]["archetypes"]["mf_se02"]["states"][state]["tolerance_percent"] = tolerance
    save(path, data)
    with pytest.raises(ValueError, match="2% or 5%"):
        load_calibrated_archetype(path, renovation_state=state)


def test_pending_active_mapping_blocks_existing_acceptance(detailed_copy):
    path, data = detailed_copy
    link = data["materials"]["materials"]["woodfiber_board"]
    link.update(mapping_status="pending", boverket_id=None)
    save(path, data)
    result = load_calibrated_archetype(path)
    assert not result.report["lod2_complete"]
    assert not result.report["lod2_checks"]["boverket_material_references"]
    assert result.report["pending_carbon_mappings"] == ["woodfiber_board"]


def test_all_36_classification_slots_are_checked_with_one_construction_per_state():
    report = load_detailed_catalogue().lod2_completeness()
    rows = [row for row in report["states"] if row["archetype_id"] == "mf_se02"]
    slots = [s for row in rows for s in row["slot_checks"]]
    assert len(slots) == len({s["slot_id"] for s in slots}) == 36
    for row in rows:
        assert len({s["construction_revision"] for s in row["slot_checks"]}) == 1
        assert all(
            s["identical_state_targets"] and s["nominal_u_alignment"] for s in row["slot_checks"]
        )


def test_bounded_search_is_read_only_and_reports_feasibility():
    from tools.recalibrate_mf_se02 import search

    catalogue = load_detailed_catalogue()
    before = catalogue.to_dict()
    selections = search(catalogue)
    assert catalogue.to_dict() == before
    assert set(selections) == {"roof", "external_wall", "intermediate_floor", "internal_wall"}
    for row in selections.values():
        assert row["searched_candidates"] > 0
        assert all(v["field"] == "thickness" or isinstance(v["field"], int)
                   for v in row["variables"])
        if row["feasible_candidates"] == 0:
            assert row["selected"] is None
        else:
            selected = row["selected"]
            for variable, value in zip(row["variables"], selected["choices"], strict=True):
                assert value in variable["choices"]
            assert all(u > 0 for u in selected["u_values"])
    # Historic bounds need not admit the reviewed v1.3 envelope targets.
    assert selections["roof"]["selected"] is None
    assert selections["external_wall"]["feasible_candidates"] > 0
    assert selections["internal_wall"]["feasible_candidates"] > 0
    assert selections["intermediate_floor"]["feasible_candidates"] > 0
