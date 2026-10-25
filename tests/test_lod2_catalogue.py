"""The curated catalogue is a deterministic, reference-linked LoD2 library."""

from __future__ import annotations

import json
from importlib.resources import files
from itertools import product

import pytest

from epsm_data import (
    Archetype,
    ArchetypeKey,
    BuildingElement,
    Catalogue,
    Component,
    ConstructionSet,
    Element,
    EmbodiedCarbon,
    Layer,
    LayerMaterial,
    LayerSlot,
    Material,
    Roughness,
    ShearingLayer,
    WindowElement,
    archetype_from_dict,
    archetype_to_dict,
)

CATEGORIES = ("single_family", "multi_family", "office", "school")
ERAS = tuple(f"SE.{number:02d}" for number in range(1, 8))
ZONES = ("SE.Zone1", "SE.Zone2", "SE.Zone3")
STATES = ("existing", "standard", "advanced")


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture
def catalogue_payload():
    return Catalogue(json.loads(files("epsm_data.datasets.lod2").joinpath("catalogue.json").read_text())).resolved_dict()


def _configurations(catalogue):
    for identifier in catalogue.ids():
        states = (None,) if identifier.endswith("se07") else STATES
        for state in states:
            yield identifier, state


def _load_changed(tmp_path, payload):
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return Catalogue.load(path)


def _references_to_material(payload, material_id):
    """Find configurations that really use a particular shared material."""
    layers = {
        identifier
        for identifier, layer in payload["layers"].items()
        if any(slot["material_id"] == material_id for slot in layer["materials"])
    }
    components = {
        identifier
        for identifier, component in payload["components"].items()
        if any(slot["layer_id"] in layers for slot in component["layers"])
    }
    elements = {
        identifier
        for identifier, element in payload["elements"].items()
        if element.get("window_material_id") == material_id
        or any(component in components for component in element.get("components", ()))
    }
    construction_sets = {
        identifier
        for identifier, construction in payload["construction_sets"].items()
        if any(element in elements for element in construction["elements"].values())
    }
    return [
        (identifier, None if state == "default" else state)
        for identifier, archetype in payload["archetypes"].items()
        for state, configuration in archetype["states"].items()
        if configuration["construction_set_id"] in construction_sets
    ]


def test_matrix_has_exactly_the_requested_families_configurations_and_slots(catalogue):
    assert len(catalogue.ids()) == 28
    assert len(set(_configurations(catalogue))) == 76
    slots = catalogue.search()
    assert len(slots) == 228
    expected = {
        (category, era, zone, state)
        for category, era, zone in product(CATEGORIES, ERAS, ZONES)
        for state in ((None,) if era == "SE.07" else STATES)
    }
    actual = {
        (slot.key.category, slot.key.era, slot.key.climate_zone, slot.key.renovation_state)
        for slot in slots
    }
    assert actual == expected
    assert len({slot.key.id for slot in slots}) == len(slots)
    for category in CATEGORIES:
        assert len(catalogue.ids(category=category)) == 7
    assert catalogue.summary()["slot_count"] == 228


def test_lookup_and_filtering_share_one_physical_configuration(catalogue):
    slots = catalogue.search(
        category="multi_family", era="SE.02", climate_zone="SE.Zone3", state="existing"
    )
    assert len(slots) == 1
    slot = slots[0]
    key = ArchetypeKey("multi_family", "SE.02", "SE.Zone3", "existing")
    assert slot.key == key
    assert catalogue.get_slot(key.id) == slot
    assert "ventilation_system" not in key.to_dict()
    assert (
        catalogue.get(slot.archetype_id, state=slot.state).construction_set
        is (catalogue.construction_sets[slot.construction_set_id])
    )
    assert catalogue.for_year("multi_family", 1965, state="existing") == catalogue.get(
        "mf_se02", state="existing"
    )


def test_se07_has_one_configuration_and_no_renovation_variants(catalogue):
    assert len(catalogue.search(era="SE.07")) == 12
    for identifier in catalogue.ids():
        if identifier.endswith("se07"):
            assert not any(state is not None for state in catalogue.renovation_states(identifier))
            assert catalogue.get(identifier).construction_set is not None
            with pytest.raises((KeyError, ValueError)):
                catalogue.get(identifier, state="existing")
        else:
            assert set(catalogue.renovation_states(identifier)) == set(STATES)
    with pytest.raises(ValueError):
        ArchetypeKey("multi_family", "SE.07", "SE.Zone3", "existing")


@pytest.mark.parametrize(
    "year, identifier",
    [(1960, "mf_se01"), (1961, "mf_se02"), (2021, "mf_se06"), (2022, "mf_se07")],
)
def test_year_lookup_respects_curated_era_boundaries(catalogue, year, identifier):
    assert catalogue.for_year("multi_family", year).archetype_id == identifier


def test_loaded_definitions_use_shared_objects_and_are_immutable(catalogue):
    assert catalogue.materials and catalogue.layers and catalogue.components and catalogue.elements
    all_elements = {
        id(element) for element in (*catalogue.elements.values(), *catalogue.windows.values())
    }
    all_materials = {id(material) for material in catalogue.materials.values()}
    usages = []
    for identifier, state in _configurations(catalogue):
        archetype = catalogue.get(identifier, state=state)
        assert archetype.construction_set is not None
        for element in archetype.construction_set.elements.values():
            assert id(element) in all_elements
            usages.append(id(element))
            if isinstance(element, Element):
                assert isinstance(element.components, tuple)
                for component in element.components:
                    assert isinstance(component.layers, tuple)
                    for slot in component.layers:
                        assert isinstance(slot.layer.materials, tuple)
                        for material_slot in slot.layer.materials:
                            assert id(material_slot.material) in all_materials
    assert len(set(usages)) < len(usages), "Identical definitions should be shared across uses"
    for index in (
        catalogue.materials,
        catalogue.layers,
        catalogue.components,
        catalogue.elements,
        catalogue.construction_sets,
        catalogue.dimensions,
    ):
        with pytest.raises(TypeError):
            index["new"] = object()
    with pytest.raises(TypeError):
        catalogue.get("mf_se02").construction_set.elements[BuildingElement.ROOF] = object()


def test_catalogue_contains_one_definition_per_physical_composition(catalogue_payload):
    fields_by_index = {
        "materials": ("kind", "properties", "boverket_id"),
        "layers": ("thickness", "materials", "is_composite"),
        "components": ("shearing_layer", "application", "layers"),
        "elements": ("role", "components", "window_material_id"),
        "construction_sets": ("elements",),
    }
    for index, fields in fields_by_index.items():
        signatures = {}
        for identifier, record in catalogue_payload[index].items():
            signature = json.dumps(
                {field: record.get(field) for field in fields}, sort_keys=True, allow_nan=False
            )
            assert signature not in signatures, (
                f"{index}: {identifier} duplicates the physical definition {signatures.get(signature)}"
            )
            signatures[signature] = identifier


def test_all_resolved_archetypes_are_deterministic_and_portable(catalogue):
    independent = Catalogue.load()
    for identifier, state in _configurations(catalogue):
        actual = catalogue.get(identifier, state=state)
        payload = archetype_to_dict(actual)
        serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        assert serialized == json.dumps(
            archetype_to_dict(independent.get(identifier, state=state)),
            ensure_ascii=False,
            allow_nan=False,
        )
        assert archetype_from_dict(json.loads(serialized)) == actual
    exported = catalogue.to_dict()
    exported["dataset_id"] = "caller-owned-copy"
    assert catalogue.dataset_id != "caller-owned-copy"


def test_completeness_reports_fabric_gaps_without_requiring_model_setup(catalogue):
    for identifier, state in _configurations(catalogue):
        report = catalogue.completeness(identifier, state=state)
        assert isinstance(report["complete"], bool)
        assert report["complete"] == (not report["missing_values"])
        assert all(isinstance(path, str) and path for path in report["missing_values"])
        assert not any(
            term in path.lower()
            for path in report["missing_values"]
            for term in ("hvac", "operating_profile", "geometry", "ventilation_system")
        )
    for slot in catalogue.search():
        report = catalogue.completeness(slot.archetype_id, state=slot.state)
        assert slot.complete == report["complete"]
        assert tuple(slot.missing_values) == tuple(report["missing_values"])


@pytest.mark.parametrize("mapping", ["boverket_id", "thermal_id"])
def test_absent_external_mapping_is_inspectable_and_marks_its_users_incomplete(
    tmp_path, catalogue_payload, mapping
):
    material_id = next(
        identifier
        for identifier, material in catalogue_payload["materials"].items()
        if material["kind"] == "opaque"
        and material.get(mapping)
        and _references_to_material(catalogue_payload, identifier)
    )
    affected = _references_to_material(catalogue_payload, material_id)
    catalogue_payload["materials"][material_id][mapping] = None
    changed = _load_changed(tmp_path, catalogue_payload)
    assert changed.material_records[material_id][mapping] is None
    for identifier, state in affected:
        report = changed.completeness(identifier, state=state)
        assert report["complete"] is False
        assert any(mapping in path.lower() for path in report["missing_values"])
        assert changed.get(identifier, state=state).construction_set is not None


def test_missing_required_construction_role_is_visible_without_fabricating_an_element(
    tmp_path, catalogue_payload
):
    configuration = catalogue_payload["archetypes"]["mf_se02"]["states"]["existing"]
    construction = catalogue_payload["construction_sets"][configuration["construction_set_id"]]
    del construction["elements"]["TOP_FLOOR"]
    changed = _load_changed(tmp_path, catalogue_payload)
    actual = changed.get("mf_se02", state="existing")
    assert BuildingElement.TOP_FLOOR not in actual.construction_set.elements
    report = changed.completeness("mf_se02", state="existing")
    assert report["complete"] is False
    assert any("top_floor" in path.lower() for path in report["missing_values"])


@pytest.mark.parametrize("property_name", ["conductivity", "density", "specific_heat"])
def test_missing_numeric_material_value_is_reported_without_a_synthetic_default(
    tmp_path, catalogue_payload, property_name
):
    material_id = next(
        identifier
        for identifier, material in catalogue_payload["materials"].items()
        if material["kind"] == "opaque"
        and property_name in material["properties"]
        and _references_to_material(catalogue_payload, identifier)
    )
    affected = _references_to_material(catalogue_payload, material_id)
    catalogue_payload["materials"][material_id]["properties"][property_name] = None
    changed = _load_changed(tmp_path, catalogue_payload)
    assert changed.material_records[material_id]["properties"][property_name] is None
    assert material_id not in changed.materials
    for identifier, state in affected:
        report = changed.completeness(identifier, state=state)
        assert report["complete"] is False
        assert any(property_name in path for path in report["missing_values"])


@pytest.mark.parametrize(
    "broken_link", ["material", "layer", "component", "element", "construction_set"]
)
def test_dangling_references_fail_at_load(tmp_path, catalogue_payload, broken_link):
    if broken_link == "material":
        next(iter(catalogue_payload["layers"].values()))["materials"][0]["material_id"] = "absent"
    elif broken_link == "layer":
        next(iter(catalogue_payload["components"].values()))["layers"][0]["layer_id"] = "absent"
    elif broken_link == "component":
        element = next(e for e in catalogue_payload["elements"].values() if e.get("components"))
        element["components"][0] = "absent"
    elif broken_link == "element":
        next(iter(catalogue_payload["construction_sets"].values()))["elements"]["ROOF"] = "absent"
    else:
        catalogue_payload["archetypes"]["mf_se02"]["states"]["existing"]["construction_set_id"] = (
            "absent"
        )
    with pytest.raises((ValueError, KeyError), match="absent|reference|Unknown|unknown"):
        _load_changed(tmp_path, catalogue_payload)


def test_custom_authoring_retains_the_complete_linked_hierarchy():
    carbon = EmbodiedCarbon(
        name="Resolved carbon",
        resource_id="BV:masonry",
        boverket_name="Masonry",
        A1_A3_conservative=0,
        A1_A3_typical=0,
        A4_transport=0,
        A5_conservative=0,
        conservative_factor=1,
        conversion_factor=None,
        technical_service_life="50",
        biogenic_carbon=None,
    )
    material = Material(
        name="Authored masonry",
        json_id="HB:masonry",
        boverket_id="BV:masonry",
        material_type="opaque",
        roughness=Roughness.MEDIUM_ROUGH,
        density=1800,
        specific_heat=900,
        thermal_absorptance=0,
        solar_absorptance=0.6,
        visible_absorptance=0.6,
        conductivity=0.8,
        embodied_carbon=carbon,
    )
    layer = Layer("Masonry", "authored-masonry", 0.2, [LayerMaterial(material, 1, 0.2)])
    component = Component(
        "Masonry structure",
        "authored",
        BuildingElement.EXT_WALL,
        [LayerSlot(layer, 0)],
        ShearingLayer.STRUCTURE,
    )
    element = Element("Wall", "authored", None, [component], BuildingElement.EXT_WALL)
    window = WindowElement("Window", "authored", 1.2, 0.5, 0.6, boverket_id=123)
    construction = ConstructionSet(
        elements={BuildingElement.EXT_WALL: element, BuildingElement.WINDOW: window}
    )
    archetype = Archetype("authored", "Authored building", construction_set=construction)
    assert (
        archetype.construction_set.elements[BuildingElement.EXT_WALL]
        .components[0]
        .layers[0]
        .layer.materials[0]
        .material
        is material
    )
    assert archetype.window is window
    assert archetype_from_dict(archetype_to_dict(archetype)) == archetype
    assert material.thermal_absorptance == 0
    assert material.embodied_carbon.A1_A3_typical == 0
    assert material.embodied_carbon.biogenic_carbon is None
    with pytest.raises(ValueError):
        material.with_changes(conductivity=-1)
    with pytest.raises(ValueError):
        layer.with_changes(thickness=0)
    with pytest.raises(ValueError):
        window.with_changes(u_value=0)
    assert Archetype("unfinished", "Unfinished").construction_set is None
