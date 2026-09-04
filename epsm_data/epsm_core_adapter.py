"""Optional one-way conversion of epsm_data physical objects into epsm_core specs.

Imports epsm_core only when an adapter is called. No registry discovery or I/O.
The caller selects roles and their outside-to-inside component order explicitly.
"""


def construction_to_core(element, *, surface_resistance_m2k_w=0.17):
    from epsm_core import ConstructionSpec, LayerSpec, MaterialSpec

    result = []
    for component in element.components:
        for slot in sorted(component.layers, key=lambda s: s.position):
            layer = slot.layer
            materials = layer.materials
            # Parallel composites become a declared equivalent homogeneous layer.
            conductivity = layer.thickness / layer.r_value
            density = sum(m.area_fraction * m.material.density for m in materials)
            capacity = (
                sum(
                    m.area_fraction * m.material.density * m.material.specific_heat
                    for m in materials
                )
                / density
            )

            def weighted(name):
                return sum(m.area_fraction * getattr(m.material, name) for m in materials)

            first = materials[0].material
            roughness = getattr(first.roughness, "value", first.roughness)
            material = MaterialSpec(
                name=layer.name,
                conductivity_w_mk=conductivity,
                density_kg_m3=density,
                specific_heat_j_kgk=capacity,
                roughness=roughness,
                thermal_absorptance=weighted("thermal_absorptance"),
                solar_absorptance=weighted("solar_absorptance"),
                visible_absorptance=weighted("visible_absorptance"),
            )
            result.append(LayerSpec(material=material, thickness_m=layer.thickness))
    return ConstructionSpec(layers=tuple(result), surface_resistance_m2k_w=surface_resistance_m2k_w)


def envelope_to_core(
    construction_set, *, role_map, roof_topology, thermal_bridge_uplift_fraction=0
):
    """role_map maps core role names to caller-selected epsm_data BuildingElement keys."""
    from epsm_core import EnvelopeSpec

    roles = ("wall", "top", "ground", "intermediate_floor", "weather_shell", "basement_wall")
    absent = set(roles) - role_map.keys()
    if absent:
        raise ValueError(f"Explicit construction roles required: {sorted(absent)}")
    return EnvelopeSpec(
        **{
            role: construction_to_core(
                construction_set.elements[role_map[role]],
                surface_resistance_m2k_w=0.14 if role == "top" else 0.17,
            )
            for role in roles
        },
        roof_topology=roof_topology,
        thermal_bridge_uplift_fraction=thermal_bridge_uplift_fraction,
    )


def glazing_to_core(window):
    from epsm_core import GlazingSpec

    return GlazingSpec(
        u_value_w_m2k=window.u_value,
        solar_heat_gain_coefficient=window.shgc,
        visible_transmittance=window.vt,
    )


def renovation_to_core(kind, **resolved_parameters):
    """Convert a catalogue selection with resolved physics into a typed core measure."""
    from epsm_core import AddInsulation, ReplaceGlazing, ChangeAirflow, InstallFVP, InstallPV

    models = {
        "add_insulation": AddInsulation,
        "replace_glazing": ReplaceGlazing,
        "change_airflow": ChangeAirflow,
        "install_fvp": InstallFVP,
        "install_pv": InstallPV,
    }
    if kind not in models:
        raise ValueError(f"Unsupported simulation measure: {kind}")
    return models[kind].model_validate(resolved_parameters)
