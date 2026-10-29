"""Explicit illustrative reference construction, independent of catalogue I/O.

These supplied demonstration values are not a calibrated national archetype.
Carbon factors are intentionally unknown. Applications may replace this preset
with a catalogue archetype or project-specific measured construction.
"""

from uuid import NAMESPACE_URL, uuid5

from ..domain import (
    BuildingElement,
    Component,
    ConstructionSet,
    Element,
    Layer,
    LayerMaterial,
    LayerSlot,
    Material,
    Roughness,
    ShearingLayer,
    WindowElement,
)


def reference_construction_set() -> ConstructionSet:
    """Return a complete, inspectable illustrative reference; no files are read."""
    concrete = Material(
        name="Illustrative concrete", json_id="reference.concrete", boverket_id=None,
        material_type="illustrative", roughness=Roughness.MEDIUM_ROUGH,
        density=2200, specific_heat=900, conductivity=1.4,
        thermal_absorptance=.9, solar_absorptance=.6, visible_absorptance=.6,
        uuid=uuid5(NAMESPACE_URL, "epsm:reference:concrete"),
    )
    insulation = Material(
        name="Illustrative insulation", json_id="reference.insulation", boverket_id=None,
        material_type="illustrative", roughness=Roughness.MEDIUM_ROUGH,
        density=35, specific_heat=840, conductivity=.04,
        thermal_absorptance=.9, solar_absorptance=.6, visible_absorptance=.6,
        uuid=uuid5(NAMESPACE_URL, "epsm:reference:insulation"),
    )
    elements = {}
    roles = {BuildingElement.EXT_WALL: .15, BuildingElement.TOP_FLOOR: .25,
             BuildingElement.ROOF: .25, BuildingElement.GROUND_FLOOR: .15,
             BuildingElement.BASEMENT_WALL: .10, BuildingElement.INTERMEDIATE_FLOOR: None,
             BuildingElement.INT_WALL_LOADBEARING: None,
             BuildingElement.INT_WALL_NONLOADBEARING: None}
    for role, insulation_depth in roles.items():
        layers = []
        for material, depth in [(insulation, insulation_depth), (concrete, .15)]:
            if depth is None:
                continue
            name = f"reference.{role.value}.{material.json_id}"
            layer = Layer(name, name, depth, (LayerMaterial(material, 1, depth),))
            layers.append(LayerSlot(layer, len(layers)))
        component = Component(f"reference.{role.value}", "illustrative_reference", role,
                              tuple(layers), ShearingLayer.STRUCTURE)
        elements[role] = Element(f"reference.{role.value}", "illustrative_reference", 2000,
                                 (component,), role)
    elements[BuildingElement.WINDOW] = WindowElement(
        "reference.WINDOW", "illustrative_reference", u_value=1.6, shgc=.6, vt=.65,
    )
    return ConstructionSet(
        version_id=uuid5(NAMESPACE_URL, "epsm:illustrative_reference:construction"),
        elements=elements,
    )


def reference_hvac_template():
    """Explicit illustrative FTX and district-heat inputs, not measured stock values."""
    from ..profiles import HVACTemplate

    return HVACTemplate(
        template_id="illustrative_reference_ftx",
        values={
            "airflow": {"envelope_infiltration_ach": .2,
                        "topology": "FTX", "mechanical_vent_l_s_m2": .35,
                        "sensible_recovery_effectiveness": .7},
            "delivery": {"heating": {"carrier": "district_heat", "efficiency": 1.0,
                                     "source": "epsm_data:illustrative-reference",
                                     "specific_fan_power_w_per_l_s": 1.5}},
            "equipment": [{"identifier": "ventilation", "product_id": "reference.ftx",
                           "count": 1, "description": "Illustrative FTX system", "factor_refs": {}},
                          {"identifier": "heating", "product_id": "reference.district_heat_substation",
                           "count": 1, "description": "Illustrative district heating substation", "factor_refs": {}}],
        },
        source_references=("epsm:modelling-assumptions:illustrative-reference",),
        notes=("Illustrative inspectable preset. Supply project evidence and environmental factors before assessment.",),
    )
