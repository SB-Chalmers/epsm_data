"""Renovation catalogue: candidates, cost estimates and readiness, independent of archetype states."""

import json
from dataclasses import replace

import pytest

from epsm_data import (
    MEASURE_TYPES,
    BuildingElement,
    Catalogue,
    CostEstimate,
    CostItem,
    LayerAddition,
    RenovationCatalogue,
    SystemSwap,
    WindowSwap,
)


@pytest.fixture(scope="module")
def library():
    return Catalogue.load()


@pytest.fixture(scope="module")
def renovations(library):
    return RenovationCatalogue.load(library)


def estimate(**changes):
    values = {"currency": "SEK", "price_year": 2026,
              "items": [{"category": "material", "rate": 10.0, "driver": "element_area_m2"}]}
    return values | changes


def test_every_measure_type_has_resolved_candidates(renovations):
    assert {c.measure_type for c in renovations} == set(MEASURE_TYPES)
    for candidate in renovations:
        payload = candidate.payload
        assert isinstance(payload, candidate.kind.payload)
        if isinstance(payload, LayerAddition):
            assert len(payload.components) == len(payload.component_ids)
            assert all(c.application == candidate.role for c in payload.components)
        elif isinstance(payload, WindowSwap):
            assert payload.window is not None
        elif isinstance(payload, SystemSwap):
            template = payload.operation(candidate.candidate_id).template
            assert template.values["airflow"]["topology"] in payload.template_id


def test_catalogue_is_independent_of_archetype_renovation_states(renovations):
    """Standard and Advanced are past renovations of the stock, not catalogue outcomes."""
    assert not hasattr(renovations, "packages")
    readiness = renovations.readiness(Catalogue.load())
    assert readiness["ready"], readiness
    assert readiness["archetypes"] == 28
    assert all(not t["uncovered"] for t in readiness["measure_types"].values())


def test_placement_follows_measure_type(library, renovations):
    construction = library.get("mf_se02", state="existing").construction_set
    for candidate_id, role in (("insulate_wall.stone_wool_200", BuildingElement.EXT_WALL),
                               ("insulate_basement.floor_eps_45_screed_50",
                                BuildingElement.GROUND_FLOOR)):
        candidate = renovations.get(candidate_id)
        before = construction.elements[role]
        changed = construction
        for operation in candidate.payload.operations_for(before):
            changed = operation.apply(changed)
        after = changed.elements[role].components
        components = candidate.payload.components
        added = len(components)
        if candidate.payload.side == "exterior":
            assert after[:added] == components and after[added:] == before.components
        else:
            assert after[:-added] == before.components and after[-added:] == components
        assert changed.elements[role].u_value < before.u_value


def test_cost_overlay_prefers_the_most_specific_key(library):
    overlay = {"insulate_roof": estimate(),
               "insulate_roof/ROOF": estimate(price_year=2025),
               "insulate_roof.roof_stone_wool_board_150": estimate(price_year=2024)}
    renovations = RenovationCatalogue.load(library, costs=overlay)
    years = {c.candidate_id: c.cost.price_year for c in renovations.filter("insulate_roof")}
    assert years["insulate_roof.roof_stone_wool_board_150"] == 2024
    assert years["insulate_roof.roof_stone_wool_board_250"] == 2025
    assert years["insulate_roof.attic_loose_glass_wool_200"] == 2026
    assert renovations.readiness(library)["measure_types"]["insulate_roof"]["fully_priced"] == len(
        renovations.filter("insulate_roof"))


def test_cost_estimates_are_explicit_about_scope_and_round_trip():
    partial = CostEstimate.from_dict(estimate(coverage="partial", missing_scope=["ductwork"]))
    assert CostEstimate.from_dict(json.loads(json.dumps(partial.to_dict()))) == partial
    with pytest.raises(ValueError, match="missing scope"):
        CostEstimate.from_dict(estimate(coverage="partial"))
    with pytest.raises(ValueError, match="driver"):
        CostItem("material", 1.0, "per_apartment")
    with pytest.raises(ValueError, match="category"):
        CostItem("profit", 1.0, "building")
    with pytest.raises(ValueError, match="Currency"):
        CostEstimate.from_dict(estimate(currency="sek"))


def test_bundled_dataset_carries_only_public_prices_and_products_resolve(renovations):
    priced = {c.candidate_id for c in renovations if c.cost is not None}
    assert priced == {"install_pv.roof_south_15", "reduce_dhw.low_flow_fittings"}
    assert not any("Wikells" in ref for c in renovations if c.cost
                   for ref in c.cost.source_references)
    referenced = {p.boverket_id for c in renovations for p in c.products if p.boverket_id}
    assert referenced == set(renovations.boverket_resources)


def test_sealing_is_a_dependent_measure_named_by_its_hosts(renovations):
    sealing = renovations.get("seal_envelope.renovated_joints")
    assert not sealing.kind.standalone and sealing.kind.priced_with_host
    assert set(sealing.kind.hosts) == {"replace_window", "insulate_wall"}
    assert not sealing.products and sealing.cost is None
    for candidate in (*renovations.filter("replace_window"), *renovations.filter("insulate_wall")):
        assert candidate.companion_candidates == (sealing,)
    assert not renovations.get("upgrade_window.insulating_glass_inner_sash").companions
    assert sealing.payload.operation(0.5).fraction == pytest.approx(
        0.5 * sealing.payload.nominal_reduction)
    roof = renovations.get("insulate_roof.roof_stone_wool_board_150")
    with pytest.raises(ValueError, match="cannot host"):
        replace(roof, companions=(sealing.candidate_id,))


def test_new_envelope_options_use_their_own_side_and_boundaries(library, renovations):
    interior = renovations.get("insulate_wall.interior_wood_fibre_70")
    ceiling = renovations.get("insulate_basement.ceiling_stone_wool_100")
    attic = renovations.get("insulate_roof.attic_cellulose_300")
    assert (interior.payload.side, ceiling.payload.side) == ("interior", "exterior")
    assert ceiling.payload.target_boundaries == ("Internal",)
    assert "Internal" in attic.payload.target_boundaries
    material = attic.payload.components[0].layers[0].layer.materials[0].material
    assert material.boverket_id == "6000000137" and material.embodied_carbon is not None
    assert "renovation:material:cellulose_loose_fill" not in library.materials


def test_pv_and_dhw_candidates_and_carbon_references(renovations):
    from epsm_data import CarbonReference, Product

    pv = renovations.get("install_pv.roof_south_15")
    array = pv.payload
    assert (array.tilt_deg, array.azimuth_deg, array.module_w_m2, array.system_losses_pct) == (
        15, 180, 130, 12)
    assert (array.flat_roof_share, array.pitched_roof_share) == (0.8, 0.3)
    dhw = renovations.get("reduce_dhw.low_flow_fittings")
    assert 0 < dhw.payload.fraction < 1 and dhw.cost.items[0].driver == "floor_area_m2"
    fittings = dhw.products[0].carbon_reference
    assert isinstance(fittings, CarbonReference) and fittings.unit == "m2"
    assert fittings.modules["A1A3"] == 0.2 and fittings.modules["A4"] is None
    reference = fittings.to_dict()
    with pytest.raises(ValueError, match="per m2, the product per m"):
        Product("x", "x", "building", "m", carbon_reference=reference)
    with pytest.raises(ValueError, match="not both"):
        Product("x", "x", "building", "m2", boverket_id="1", carbon_reference=reference)


def test_payloads_round_trip_and_the_contract_names_every_driver(renovations):
    from epsm_data import Payload, QuantityDriver, RenovationCandidate, boundary_name

    for candidate in renovations:
        data = json.loads(json.dumps(candidate.to_dict()))
        restored = RenovationCandidate(**{**data, "payload": Payload.from_dict(data["payload"])})
        assert restored.payload == candidate.payload
        assert all(isinstance(p.driver, QuantityDriver) for p in candidate.products)
    with pytest.raises(ValueError, match="takes a window_swap payload"):
        RenovationCandidate("x", "replace_window", "x",
                            {"kind": "dhw_reduction", "fraction": 0.2})
    assert boundary_name(["fans", "space_heating"]) == "space_heating_and_fans"
