"""Portable external carbon sources preserve undeclared lifecycle modules."""

import copy
import json
from dataclasses import FrozenInstanceError

import pytest

from epsm_data import (
    CarbonReference,
    EnvironmentalFactor,
    Material,
    Roughness,
    WindowElement,
    WindowMaterial,
    archetype_from_dict,
    archetype_to_dict,
    build_archetype,
    export_nominal_constructions,
)
from epsm_data.serialization import element_from_dict, element_to_dict


def reference(**changes):
    return CarbonReference(**{
        "identifier": "EPD-IES-0005222:003",
        "name": "Tagene crushed aggregate",
        "url": "https://www.environdec.com/library/epd5222",
        "method": "EN 15804+A2 GWP-GHG",
        "unit": "kg",
        "modules": {"A1A3": 0.002, "A4": None, "A5": None},
        "proxy_for": "Retained dry sand fill",
        "declared_unit": "1 tonne (1000 kg)",
        "notes": ["Crushed aggregate proxy; transport and installation undeclared."],
        **changes,
    })


def material(**changes):
    return Material(**{
        "name": "Dry sand fill", "json_id": "sand", "boverket_id": None,
        "material_type": "EnergyMaterial", "roughness": Roughness.MEDIUM_ROUGH,
        "density": 1600, "specific_heat": 800, "thermal_absorptance": 0.9,
        "solar_absorptance": 0.7, "visible_absorptance": 0.7, "conductivity": 0.4,
        "carbon_reference": reference(), **changes,
    })


def archetype():
    return build_archetype({
        "archetype_id": "authored", "display_name": "Authored",
        "elements": {"EXT_WALL": {"components": [{
            "shearing_layer": "Structure",
            "layers": [{"material_id": "sand", "thickness": 0.1}],
        }]}},
    }, materials={"sand": material()})


def test_reference_freezes_inputs_and_roundtrips_nulls_without_source_lookup():
    modules = {"A1A3": 0.002, "A4": None, "A5": None}
    notes = ["A4 and A5 are not declared."]
    source = reference(modules=modules, notes=notes)
    modules["A4"] = 99
    notes.append("Changed outside the record")
    assert source.modules["A4"] is None
    assert source.notes == ("A4 and A5 are not declared.",)
    with pytest.raises(TypeError):
        source.modules["A4"] = 0
    with pytest.raises(FrozenInstanceError):
        source.method = "Boverket AR4"
    payload = json.loads(json.dumps(source.to_dict(), allow_nan=False))
    assert CarbonReference.from_dict(payload) == source
    assert copy.deepcopy(source) is source
    assert hash(source) == hash(CarbonReference.from_dict(source.to_dict()))
    assert isinstance(hash(material()), int)
    payload["modules"]["A4"] = 5
    assert source.modules["A4"] is None


def test_known_factors_preserve_the_declared_indicator_and_unknowns_are_omitted():
    source = reference()
    factors = source.factors()
    assert set(factors) == {"A1A3"}
    factor = factors["A1A3"]
    assert isinstance(factor, EnvironmentalFactor)
    assert factor.value == 0.002 and factor.unit == "kg" and factor.module == "A1A3"
    for label in (source.identifier, source.method, source.url, source.proxy_for):
        assert label in factor.source
    assert "AR4" not in factor.source
    assert reference(modules={"A1A3": None, "A4": None}).factors() == {}
    assert reference(modules={"A1A3": 0, "D": -0.001}).factors()["D"].value == -0.001


@pytest.mark.parametrize("changes", [
    {"identifier": ""}, {"name": None}, {"method": " "}, {"url": "file:///tmp/epd"},
    {"url": "https://"}, {"url": "https://example.com/a b"}, {"unit": "tonne"},
    {"unit": []},
    {"modules": {}}, {"modules": []}, {"modules": {"A1-A3": 0.002}},
    {"modules": {"C7": None}}, {"modules": {1: 2}},
    {"modules": {"A4": True}}, {"modules": {"A4": float("nan")}},
    {"modules": {"A4": float("inf")}}, {"modules": {"A4": "unknown"}},
    {"notes": "one note"}, {"notes": [None]}, {"notes": None}, {"notes": {"label": "note"}},
    {"proxy_for": ""}, {"declared_unit": 1000},
])
def test_malformed_source_identity_units_and_module_values_are_rejected(changes):
    with pytest.raises(ValueError):
        reference(**changes)


def test_material_cannot_silently_replace_a_boverket_source_with_an_epd():
    with pytest.raises(ValueError, match="Boverket"):
        material(boverket_id="6000000084")
    with pytest.raises(ValueError, match="CarbonReference"):
        material(carbon_reference=reference().to_dict())
    with pytest.raises(ValueError, match="Boverket"):
        WindowElement("window", "", 1.5, 0.5, boverket_id=123,
                      carbon_reference=reference(unit="m2"))


def test_opaque_archetype_roundtrip_preserves_full_external_record_and_legacy_input():
    authored = archetype()
    payload = archetype_to_dict(authored)
    assert payload["format_version"] == 4
    restored = archetype_from_dict(json.loads(json.dumps(payload, allow_nan=False)))
    assert restored == authored
    slot = restored.construction_set.elements[next(iter(restored.construction_set.elements))]
    restored_material = slot.components[0].layers[0].layer.materials[0].material
    assert restored_material.carbon_reference == reference()
    assert restored_material.embodied_carbon is None
    assert restored_material.to_dict()["carbon_reference"]["modules"]["A4"] is None
    legacy = copy.deepcopy(payload)
    raw_material = legacy["archetype"]["construction_set"]["elements"]["EXT_WALL"][
        "components"][0]["layers"][0]["layer"]["materials"][0]["material"]
    del raw_material["carbon_reference"]
    assert archetype_from_dict(legacy).construction_set is not None


def test_window_portable_roundtrip_and_material_summary_preserve_external_reference():
    source = reference(unit="m2", proxy_for="Window")
    window = WindowElement("window", "", 1.5, 0.5, carbon_reference=source)
    restored = element_from_dict(json.loads(json.dumps(element_to_dict(window))))
    assert restored == window
    assert restored.to_dict()["carbon_reference"] == source.to_dict()
    glazing = WindowMaterial("glazing", "glazing", None, "EnergyWindowMaterialGlazing",
                             1.0, 0.7, 0.1, 0.1, 0.84, 1.0, False,
                             carbon_reference=source)
    assert glazing.to_dict()["carbon_reference"] == source.to_dict()


@pytest.mark.parametrize("metadata", [None, {"material_references": {
    "sand": {"json_id": "sand", "boverket_id": None, "honeybee_id": "hb:sand"},
}}])
def test_export_attaches_full_source_to_fallback_and_supplied_reference(metadata):
    bundle = export_nominal_constructions(archetype(), metadata=metadata)
    ref = bundle["material_references"]["sand"]
    assert ref["carbon_reference_id"] == reference().identifier
    assert ref["carbon_reference"] == reference().to_dict()
    constituent = bundle["honeybee"]["EXT_WALL"]["materials"][0]["user_data"][
        "constituents"][0]["source_reference"]
    assert constituent == ref
    assert constituent["carbon_reference"]["modules"]["A5"] is None


@pytest.mark.parametrize("change", [
    {"carbon_reference_id": "another EPD"},
    {"carbon_reference": reference(modules={"A1A3": 5}).to_dict()},
    {"carbon_reference": None},
])
def test_export_rejects_metadata_that_relabels_attached_carbon_source(change):
    metadata = {"material_references": {"sand": {
        "json_id": "sand", "boverket_id": None, **change,
    }}}
    with pytest.raises(ValueError, match="external carbon reference"):
        export_nominal_constructions(archetype(), metadata=metadata)


def test_window_export_preserves_reference_and_rejects_conflicting_source():
    source = reference(unit="m2", proxy_for="Window")
    authored = build_archetype({
        "archetype_id": "window", "display_name": "Window",
        "elements": {"WINDOW": {"u_value": 1.5, "shgc": 0.5}},
    }, materials={})
    construction = authored.construction_set
    window = construction.elements[next(iter(construction.elements))].with_changes(
        carbon_reference=source)
    authored = authored.with_changes(construction_set=construction.with_changes(
        elements={window.application: window}))
    for metadata in (None, {"material_references": {"window:source": {
        "kind": "window", "boverket_id": None, "carbon_reference_id": source.identifier,
    }}}):
        bundle = export_nominal_constructions(authored, metadata=metadata)
        ref = bundle["roles"]["WINDOW"]["window_reference"]
        assert ref["carbon_reference"] == source.to_dict()
        assert any(r.get("carbon_reference") == source.to_dict()
                   for r in bundle["material_references"].values())
    with pytest.raises(ValueError, match="external carbon reference"):
        export_nominal_constructions(authored, metadata={"material_references": {
            "window:source": {"kind": "window", "boverket_id": None,
                              "carbon_reference_id": "wrong"},
        }})
