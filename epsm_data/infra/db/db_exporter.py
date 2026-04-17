"""Database exporter.

Serializes domain objects to a SQLite database via SQLAlchemy.
Adapted from Djamila's original to work with the current domain model
which uses LayerSlot, LayerMaterial dataclasses instead of raw tuples.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from epsm_data.domain.building import BuildingArchetype
from epsm_data.domain.component import Component
from epsm_data.domain.element import Element
from epsm_data.domain.layer import Layer
from epsm_data.domain.material import OpaqueMaterial
from epsm_data.infra.db.models import (
    init_db,
    DBEmbodiedCarbon, DBOpaqueMaterial, DBLayer, DBLayerMaterial,
    DBComponent, DBComponentLayer, DBElement, DBElementComponent,
    DBBuilding, DBBuildingElement,
)


def export_to_db(
    materials: list[OpaqueMaterial],
    layers: list[Layer],
    components: list[Component],
    elements: list[Element],
    buildings: list[BuildingArchetype],
    db_path: str = "epsm.db",
) -> None:
    """Export all domain objects to a SQLite database.

    Clears junction tables before each export to avoid duplicates.
    """
    engine = init_db(db_path)

    with Session(engine) as session:
        # Clear junction tables before every export
        session.query(DBBuildingElement).delete()
        session.query(DBElementComponent).delete()
        session.query(DBComponentLayer).delete()
        session.query(DBLayerMaterial).delete()
        session.commit()

        # EmbodiedCarbon — deduplicated by resource_id
        seen_ec: set[str] = set()
        for mat in materials:
            ec = mat.embodied_carbon
            if ec.resource_id not in seen_ec:
                session.merge(DBEmbodiedCarbon(
                    resource_id=ec.resource_id,
                    name=ec.name,
                    boverket_name=ec.boverket_name,
                    A1_A3_conservative=ec.A1_A3_conservative,
                    A1_A3_typical=ec.A1_A3_typical,
                    A4_transport=ec.A4_transport,
                    A5_conservative=ec.A5_conservative,
                    conservative_factor=ec.conservative_factor,
                    conversion_factor=ec.conversion_factor,
                    technical_service_life=ec.technical_service_life,
                    biogenic_carbon=ec.biogenic_carbon,
                ))
                seen_ec.add(ec.resource_id)

        for mat in materials:
            session.merge(DBOpaqueMaterial(
                name=mat.name,
                uuid=str(mat.uuid),
                json_id=mat.json_id,
                boverket_id=mat.boverket_id,
                material_type=mat.material_type,
                roughness=mat.roughness.value,
                density=mat.density,
                specific_heat=mat.specific_heat,
                thermal_absorptance=mat.thermal_absorptance,
                solar_absorptance=mat.solar_absorptance,
                visible_absorptance=mat.visible_absorptance,
                conductivity=mat.conductivity,
                embodied_carbon_id=mat.embodied_carbon.resource_id,
            ))

        for layer in layers:
            session.merge(DBLayer(
                layer_code=layer.layer_code,
                name=layer.name,
                thickness=layer.thickness,
                is_composite=layer.is_composite,
                r_value=round(layer.r_value, 6),
            ))
            for lm in layer.materials:
                session.add(DBLayerMaterial(
                    layer_code=layer.layer_code,
                    material_name=lm.material.name,
                    area_fraction=lm.area_fraction,
                    thickness=lm.thickness,
                ))

        for comp in components:
            session.merge(DBComponent(
                name=comp.name,
                archetype=comp.archetype,
                application=comp.application.value,
                shearing_layer=comp.shearing_layer.value,
                r_sum=round(comp.r_sum, 6),
            ))
            for slot in comp.layers:
                session.add(DBComponentLayer(
                    component_id=comp.name,
                    layer_code=slot.layer.layer_code,
                    layer_index=slot.position,
                ))

        for el in elements:
            session.merge(DBElement(
                name=el.name,
                archetype=el.archetype,
                age=el.age,
                element_type=el.application.value,
                u_value=round(el.u_value, 6),
                r_total=round(el.r_total, 6),
            ))
            for comp in el.components:
                session.add(DBElementComponent(
                    element_name=el.name,
                    component_id=comp.name,
                ))

        for building in buildings:
            session.merge(DBBuilding(
                archetype_id=building.archetype_id,
                display_name=building.display_name,
                construction_year=building.construction_year,
                building_typology=building.building_typology,
                construction_set_version=str(building.construction_set.version_id),
            ))
            for role, element in building.construction_set.elements.items():
                session.add(DBBuildingElement(
                    building_name=building.archetype_id,
                    element_name=element.name,
                    element_type=role.value,
                ))

        session.commit()
