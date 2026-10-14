"""Shared physical graph, safe editing, renovation and source input boundaries."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from epsm_data import (
    Archetype,
    BuildingArchetype,
    BuildingElement,
    Component,
    ConstructionOperation,
    ConstructionSet,
    EnvironmentalFactor,
    Layer,
    LayerMaterial,
    LayerSlot,
    Material,
    OpaqueMaterial,
    RenovationCatalogue,
    RenovationMeasure,
    ShearingLayer,
    SystemOperation,
    construction_set_from_dict,
    construction_set_to_dict,
    reference_construction_set,
    reference_hvac_template,
)


def test_shared_names_are_the_same_types():
    assert Material is OpaqueMaterial
    assert Archetype is BuildingArchetype


def test_reference_is_deterministic_and_roundtrips_without_carbon():
    source = reference_construction_set()
    assert source == reference_construction_set()
    payload = construction_set_to_dict(source)
    restored = construction_set_from_dict(json.loads(json.dumps(payload)))
    assert restored == source
    assert restored.valid_from_year is None
    assert all(slot.material.embodied_carbon is None for element in source.elements.values()
               if hasattr(element, "components") for component in element.components
               for layer in component.layers for slot in layer.layer.materials)
    assert deepcopy(source) == source


def test_nested_collections_are_read_only_and_constructor_does_not_alias():
    source = reference_construction_set()
    elements = dict(source.elements)
    copied = ConstructionSet(elements=elements)
    elements.clear()
    assert copied.elements
    with pytest.raises(TypeError):
        copied.elements[BuildingElement.EXT_WALL] = None
    wall = copied.elements[BuildingElement.EXT_WALL]
    with pytest.raises(FrozenInstanceError):
        wall.name = "changed"
    updated = wall.with_changes(name="project wall")
    assert wall.name != updated.name
    with pytest.raises(ValueError):
        wall.with_changes(components=())


def test_parallel_materials_and_explicit_layer_order():
    wall = reference_construction_set().elements[BuildingElement.EXT_WALL]
    a, b = (s.layer.materials[0].material for s in wall.components[0].layers)
    layer = Layer("parallel","parallel",.1,(LayerMaterial(a,.8,.1),LayerMaterial(b,.2,.1)),True)
    component = Component("parallel","example",wall.application,
                          (LayerSlot(layer,1),LayerSlot(wall.components[0].layers[0].layer,0)),
                          ShearingLayer.STRUCTURE)
    assert [slot.position for slot in component.layers] == [0,1]
    assert layer.r_value == pytest.approx(.1 / (.8*a.conductivity+.2*b.conductivity))
    with pytest.raises(ValueError, match="share"):
        layer.with_changes(thickness=.2)
    with pytest.raises(ValueError, match="unique"):
        component.with_changes(layers=(LayerSlot(layer,0),LayerSlot(layer,0)))


def test_ordered_renovation_operations_roundtrip_without_dates():
    before = reference_construction_set()
    wall = before.elements[BuildingElement.EXT_WALL]
    added = wall.components[0].with_changes(name="added exterior component")
    add = ConstructionOperation("add_component",wall.application,component=added,position=0)
    remove = ConstructionOperation("remove_component",wall.application,target_component=added.name)
    measure = RenovationMeasure("test.add","fabric","Add insulation","Synthetic operation",
                                "wall",operations=(add,),target_element_ids=("wall.north",))
    restored = RenovationMeasure.from_dict(json.loads(json.dumps(measure.to_dict())))
    after = restored.apply(before)
    assert after.elements[wall.application].components[0] == added
    assert before.elements[wall.application] == wall
    restored_geometry = remove.apply(after)
    assert restored_geometry.elements == before.elements
    assert restored_geometry.version_id != before.version_id
    catalogue = RenovationCatalogue.from_dict(RenovationCatalogue((measure,)).to_dict())
    assert catalogue.applicable(before) == (measure,)
    with pytest.raises(ValueError, match="one component"):
        remove.apply(before)
    with pytest.raises(ValueError, match="position"):
        ConstructionOperation("add_component",wall.application,component=added,position=99).apply(before)


def test_hvac_operations_preserve_data_definitions_and_need_core_to_apply():
    template = reference_hvac_template()
    operation = SystemOperation("replace_hvac",template)
    measure = RenovationMeasure("test.ftx","systems","FTX","Illustrative replacement","hvac",
                                operations=(operation,))
    assert RenovationMeasure.from_dict(json.loads(json.dumps(measure.to_dict()))) == measure
    assert {x["identifier"] for x in template.values["equipment"]} == {"heating","ventilation"}
    with pytest.raises(ValueError, match="Core Building"):
        measure.apply(reference_construction_set())
    assert RenovationCatalogue((measure,)).applicable(reference_construction_set()) == (measure,)


def test_sourced_factor_units_and_unknown_carbon_are_independent():
    factor = EnvironmentalFactor(-.5,"kg","A1A3","synthetic example")
    assert EnvironmentalFactor.from_dict(factor.to_dict()) == factor
    with pytest.raises(ValueError):
        factor.with_changes(unit="unknown")
    with pytest.raises(ValueError):
        factor.with_changes(value=float("nan"))



def test_measure_prerequisites_and_incompatibilities_are_executable():
    before = reference_construction_set()
    window = before.elements[BuildingElement.WINDOW]
    operation = ConstructionOperation("replace_element",BuildingElement.WINDOW,element=window)
    measure = RenovationMeasure("windows","fabric","Windows","Example","window",
                                operations=(operation,),requires_measure_ids=("survey",),
                                incompatible_measure_ids=("keep_windows",))
    catalogue = RenovationCatalogue((measure,))
    assert catalogue.applicable(before) == ()
    assert catalogue.applicable(before,applied_measure_ids=("survey",)) == (measure,)
    assert catalogue.applicable(before,applied_measure_ids=("survey","keep_windows")) == ()
    assert RenovationMeasure.from_dict(measure.to_dict()) == measure
    with pytest.raises(ValueError):
        RenovationMeasure("bad","fabric","Bad","Example","wall",requires_measure_ids=("bad",))
    with pytest.raises(ValueError):
        RenovationMeasure("bad","fabric","Bad","Example","wall",
                          requires_measure_ids=("same",),incompatible_measure_ids=("same",))
