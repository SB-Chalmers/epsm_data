from sqlalchemy import (
    create_engine, Column, String, Float, Integer,
    Boolean, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class DBEmbodiedCarbon(Base):
    __tablename__ = "embodied_carbon"
    resource_id            = Column(String, primary_key=True)
    name                   = Column(String, nullable=False)
    boverket_name          = Column(String)
    A1_A3_conservative     = Column(Float)
    A1_A3_typical          = Column(Float)
    A4_transport           = Column(Float)
    A5_conservative        = Column(Float)
    conservative_factor    = Column(Float)
    conversion_factor      = Column(Float)
    technical_service_life = Column(String)
    biogenic_carbon        = Column(Float)

    materials = relationship("DBOpaqueMaterial", back_populates="embodied_carbon")


class DBOpaqueMaterial(Base):
    __tablename__ = "opaque_material"
    name                = Column(String, primary_key=True)
    uuid                = Column(String)
    json_id             = Column(String)
    boverket_id         = Column(String)
    material_type       = Column(String)
    roughness           = Column(String)
    density             = Column(Float)
    specific_heat       = Column(Float)
    thermal_absorptance = Column(Float)
    solar_absorptance   = Column(Float)
    visible_absorptance = Column(Float)
    conductivity        = Column(Float)
    embodied_carbon_id  = Column(String, ForeignKey("embodied_carbon.resource_id"))

    embodied_carbon = relationship("DBEmbodiedCarbon", back_populates="materials")
    layer_materials = relationship("DBLayerMaterial", back_populates="material")


class DBLayer(Base):
    __tablename__ = "layer"
    layer_code   = Column(String, primary_key=True)
    name         = Column(String)
    thickness    = Column(Float)
    is_composite = Column(Boolean)
    r_value      = Column(Float)

    materials        = relationship("DBLayerMaterial", back_populates="layer")
    component_layers = relationship("DBComponentLayer", back_populates="layer")


class DBLayerMaterial(Base):
    __tablename__ = "layer_material"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    layer_code    = Column(String, ForeignKey("layer.layer_code"))
    material_name = Column(String, ForeignKey("opaque_material.name"))
    area_fraction = Column(Float)
    thickness     = Column(Float)

    layer    = relationship("DBLayer", back_populates="materials")
    material = relationship("DBOpaqueMaterial", back_populates="layer_materials")


class DBComponent(Base):
    __tablename__  = "component"
    name           = Column(String, primary_key=True)
    archetype      = Column(String)
    application    = Column(String)
    shearing_layer = Column(String)
    r_sum          = Column(Float)

    layers   = relationship("DBComponentLayer", back_populates="component")
    elements = relationship("DBElementComponent", back_populates="component")


class DBComponentLayer(Base):
    __tablename__ = "component_layer"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    component_id = Column(String, ForeignKey("component.name"))
    layer_code   = Column(String, ForeignKey("layer.layer_code"))
    layer_index  = Column(Integer)

    component = relationship("DBComponent", back_populates="layers")
    layer     = relationship("DBLayer", back_populates="component_layers")


class DBElement(Base):
    __tablename__ = "element"
    name           = Column(String, primary_key=True)
    archetype      = Column(String)
    age            = Column(Integer)
    element_type   = Column(String)
    u_value        = Column(Float)
    r_total        = Column(Float)
    tabula_u_value = Column(Float, nullable=True)
    tabula_warning = Column(String, nullable=True)

    components = relationship("DBElementComponent", back_populates="element")
    buildings  = relationship("DBBuildingElement", back_populates="element")


class DBElementComponent(Base):
    __tablename__ = "element_component"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    element_name = Column(String, ForeignKey("element.name"))
    component_id = Column(String, ForeignKey("component.name"))

    element   = relationship("DBElement", back_populates="components")
    component = relationship("DBComponent", back_populates="elements")


class DBBuilding(Base):
    __tablename__      = "building"
    archetype_id       = Column(String, primary_key=True)
    display_name       = Column(String)
    construction_year  = Column(Integer)
    building_typology  = Column(String)
    heating_system     = Column(String, nullable=True)
    ventilation_system = Column(String, nullable=True)
    cold_attic         = Column(Boolean, default=False)
    window_to_wall_ratio = Column(Float, default=0.2)
    infiltration_rate  = Column(Float, default=0.5)
    construction_set_version = Column(String)  # UUID of current ConstructionSet

    elements = relationship("DBBuildingElement", back_populates="building")


class DBBuildingElement(Base):
    __tablename__ = "building_element"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    building_name = Column(String, ForeignKey("building.archetype_id"))
    element_name  = Column(String, ForeignKey("element.name"))
    element_type  = Column(String)

    building = relationship("DBBuilding", back_populates="elements")
    element  = relationship("DBElement", back_populates="buildings")


def init_db(path: str = "epsm.db"):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return engine