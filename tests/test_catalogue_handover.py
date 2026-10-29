"""Frozen LoD2 handovers conserve physics without catalogue-building machinery."""

import json
from copy import deepcopy

import pytest

from epsm_data import (
    Archetype,
    Material,
    Roughness,
    build_archetype,
    export_nominal_constructions,
    validate_nominal_handover,
)


def make_material(identifier, conductivity, density, specific_heat):
    return Material(
        name=identifier,
        json_id=identifier,
        boverket_id=f"carbon:{identifier}",
        material_type="EnergyMaterial",
        roughness=Roughness.MEDIUM_ROUGH,
        density=density,
        specific_heat=specific_heat,
        thermal_absorptance=0.9,
        solar_absorptance=0.6,
        visible_absorptance=0.6,
        conductivity=conductivity,
    )


def make_archetype():
    materials = {
        "insulation": make_material("insulation", 0.04, 30, 1400),
        "timber": make_material("timber", 0.12, 500, 1600),
        "board": make_material("board", 0.1, 400, 1200),
    }
    construction = {
        "components": [{
            "shearing_layer": "Structure",
            "layers": [
                {"material_id": ["insulation", "timber"], "thickness": 0.2,
                 "area_fraction": [0.8, 0.2]},
                {"material_id": "board", "thickness": 0.02},
            ],
        }],
    }
    return build_archetype({
        "archetype_id": "authored",
        "display_name": "Authored physical construction",
        "elements": {
            "EXT_WALL": construction,
            "INT_WALL_NONLOADBEARING": construction,
            "WINDOW": {"u_value": 1.5, "shgc": 0.5, "vt": 0.65,
                       "boverket_id": 6000000010},
        },
    }, materials=materials)


def test_parallel_layer_export_preserves_resistance_mass_storage_and_films():
    archetype = make_archetype()
    bundle = export_nominal_constructions(archetype)
    assert validate_nominal_handover(bundle) == {"honeybee": True, "core": True}
    resistance = 0.2 / (0.8 * 0.04 + 0.2 * 0.12) + 0.02 / 0.1
    for role, films in (("EXT_WALL", 0.17), ("INT_WALL_NONLOADBEARING", 0.26)):
        metrics = bundle["roles"][role]
        assert metrics["resistance_m2k_w"] == pytest.approx(resistance)
        assert metrics["thickness_m"] == pytest.approx(0.22)
        assert metrics["mass_kg_m2"] == pytest.approx(32.8)
        assert metrics["heat_capacity_j_m2k"] == pytest.approx(48320)
        assert metrics["nominal_u_w_m2k"] == pytest.approx(1 / (resistance + films))
        assert bundle["core"][role]["surface_resistance_m2k_w"] == pytest.approx(films)
        first = bundle["honeybee"][role]["materials"][0]
        assert first["conductivity"] == pytest.approx(0.056)
        assert first["specific_heat"] == pytest.approx(193600 / 124)
        assert first["specific_heat"] != pytest.approx(0.8 * 1400 + 0.2 * 1600)
        assert first["user_data"]["carbon_mapping"] == "constituents_only"
        constituent_ids = [
            entry["source_reference"]["boverket_id"]
            for entry in first["user_data"]["constituents"]
        ]
        assert constituent_ids == ["carbon:insulation", "carbon:timber"]
        assert bundle["reciprocal"][role]["honeybee"]["materials"] == list(
            reversed(bundle["honeybee"][role]["materials"])
        )
    assert bundle["core"]["WINDOW"] == {
        "u_value_w_m2k": 1.5,
        "solar_heat_gain_coefficient": 0.5,
        "visible_transmittance": 0.65,
    }
    assert bundle["roles"]["WINDOW"]["window_reference"]["boverket_id"] == 6000000010
    assert bundle["roles"]["WINDOW"]["mass_kg_m2"] is None


def test_export_is_deterministic_across_recreated_authored_objects_and_portable():
    first, second = make_archetype(), make_archetype()
    assert first.construction_set.version_id != second.construction_set.version_id
    first_bundle = export_nominal_constructions(first)
    second_bundle = export_nominal_constructions(second)
    assert first_bundle == second_bundle
    assert json.loads(json.dumps(first_bundle, allow_nan=False)) == first_bundle
    assert "revision" not in first_bundle
    assert "readiness" not in first_bundle


def test_optional_physical_context_preserves_honeybee_and_boverket_links_without_review():
    metadata = {
        "category": "multi_family", "era": "SE.02", "state": "existing",
        "material_references": {
            "insulation": {"json_id": "insulation", "honeybee_id": "hb:insulation",
                           "boverket_id": "carbon:insulation"},
            "window_current": {"kind": "simple_window", "honeybee_id": "hb:window",
                               "boverket_id": "6000000010"},
        },
        "boundary_details": {
            "EXT_WALL": {"facade_cavity": {"thickness_m": 0.025,
                                           "ventilation": "well_ventilated"}},
        },
        "roof_topology": {"type": "cold_attic"},
    }
    original = deepcopy(metadata)
    bundle = export_nominal_constructions(make_archetype(), metadata=metadata)
    assert metadata == original
    first = bundle["honeybee"]["EXT_WALL"]["materials"][0]
    reference = first["user_data"]["constituents"][0]["source_reference"]
    assert reference["honeybee_id"] == "hb:insulation"
    assert reference["boverket_id"] == "carbon:insulation"
    assert bundle["roles"]["EXT_WALL"]["boundary_details"] == metadata["boundary_details"]["EXT_WALL"]
    assert bundle["roof_topology"] == {"type": "cold_attic"}
    assert bundle["key"] == {"category": "multi_family", "era": "SE.02", "state": "existing"}
    assert bundle["roles"]["WINDOW"]["window_reference"]["honeybee_id"] == "hb:window"
    bundle["roof_topology"]["type"] = "changed"
    reference["honeybee_id"] = "changed"
    assert metadata == original


@pytest.mark.parametrize("mutation", ["storage", "order", "films", "window", "role", "alias"])
def test_corrupt_physical_handover_is_rejected(mutation):
    bundle = export_nominal_constructions(make_archetype())
    if mutation == "storage":
        bundle["core"]["EXT_WALL"]["layers"][0]["material"]["specific_heat_j_kgk"] += 1
    elif mutation == "order":
        for spelling in ("reciprocal", "reciprocal_constructions"):
            bundle[spelling]["EXT_WALL"]["core"]["layers"].reverse()
    elif mutation == "films":
        bundle["core"]["EXT_WALL"]["surface_resistance_m2k_w"] += 0.1
    elif mutation == "window":
        bundle["core"]["WINDOW"]["visible_transmittance"] = 0.5
    elif mutation == "role":
        del bundle["honeybee"]["EXT_WALL"]
    else:
        del bundle["reciprocal"]["EXT_WALL"]
    with pytest.raises(ValueError):
        validate_nominal_handover(bundle)


def test_absent_physical_construction_and_nonportable_metadata_are_rejected():
    with pytest.raises(ValueError, match="physical construction"):
        export_nominal_constructions(Archetype("empty", "Unresolved"))
    with pytest.raises(ValueError, match="finite portable"):
        export_nominal_constructions(make_archetype(), metadata={"value": float("nan")})
    with pytest.raises(TypeError, match="Archetype"):
        export_nominal_constructions(object())
    with pytest.raises(ValueError, match="Malformed"):
        validate_nominal_handover({})


@pytest.mark.parametrize("property_name,value", [
    ("boverket_id", "carbon:another-product"),
    ("properties", {"conductivity": 0.5}),
])
def test_material_context_cannot_relabel_supplied_physics(property_name, value):
    reference = {
        "json_id": "insulation", "honeybee_id": "hb:insulation",
        "boverket_id": "carbon:insulation",
    }
    reference[property_name] = value
    with pytest.raises(ValueError, match="physical properties or Boverket"):
        export_nominal_constructions(
            make_archetype(), metadata={"material_references": {"insulation": reference}},
        )


@pytest.mark.parametrize("properties,boverket_id", [
    ({"u_value": 2.2, "shgc": 0.5, "vt": 0.65}, "6000000010"),
    ({"u_value": 1.5, "shgc": 0.5, "vt": 0.65}, "6000000099"),
])
def test_window_context_cannot_relabel_supplied_window(properties, boverket_id):
    metadata = {"material_references": {
        "window:context": {"kind": "simple_window", "honeybee_id": "hb:window",
                           "boverket_id": boverket_id, "properties": properties},
    }}
    with pytest.raises(ValueError, match="Window.*matching"):
        export_nominal_constructions(make_archetype(), metadata=metadata)


def test_window_reference_selection_matches_actual_physics_and_normalizes_source_ids():
    metadata = {"material_references": {
        "window:other": {"kind": "simple_window", "honeybee_id": "hb:other",
                         "boverket_id": 6000000010,
                         "properties": {"u_value": 2.2, "shgc": 0.5, "vt": 0.65}},
        "window:correct": {"kind": "simple_window", "honeybee_id": "hb:correct",
                           "boverket_id": "6000000010",
                           "properties": {"u_value": 1.5, "shgc": 0.5, "vt": 0.65}},
    }}
    bundle = export_nominal_constructions(make_archetype(), metadata=metadata)
    assert bundle["roles"]["WINDOW"]["window_reference"]["honeybee_id"] == "hb:correct"
    metadata["material_references"]["window:other"]["properties"]["u_value"] = 1.5
    with pytest.raises(ValueError, match="Window.*exactly one"):
        export_nominal_constructions(make_archetype(), metadata=metadata)


def test_stale_catalogue_window_metadata_is_rejected():
    from epsm_data import Catalogue

    catalogue = Catalogue.load()
    with pytest.raises(ValueError, match="Window.*matching"):
        export_nominal_constructions(
            catalogue.get("mf_se02", state="advanced"),
            metadata=catalogue.nominal_metadata("mf_se02", state="existing"),
        )
