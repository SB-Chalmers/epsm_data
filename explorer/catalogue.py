"""Read-only explorer adapter for the compact parametric catalogue."""

from epsm_data import Catalogue
from epsm_data.parametric import content_hash

# Preserve the explorer's package/revision fields for existing remarks.
_ROLES = {
    "ground_floor": "ground",
    "intermediate_floor": "intermediate_floor",
    "external_wall": "wall",
    "internal_wall": "internal_wall",
    "roof": "top",
    "basement_wall": "basement_wall",
    "window": "glazing",
}
_VALUE_ROLES = {
    "TOP_FLOOR": "roof", "EXT_WALL": "external_wall", "INTERMEDIATE_FLOOR": "intermediate_floor",
    "GROUND_FLOOR": "ground_floor", "BASEMENT_WALL": "basement_wall",
    "BASEMENT_FLOOR": "ground_floor", "INT_WALL_LOADBEARING": "internal_wall",
    "INT_WALL_NONLOADBEARING": "internal_wall", "WINDOW": "window",
}


def _material_view(registry, material_id):
    record = registry.resolve_material(material_id)
    props = record.get("properties", {})
    carbon = props.get("embodied_carbon")
    return {
        "id": material_id,
        "name": props.get("name", material_id),
        "honeybee_id": record.get("honeybee_id"),
        "honeybee_type": record.get("honeybee_type"),
        "honeybee_properties": {
            key: props.get(key) for key in (
                "roughness", "conductivity", "density", "specific_heat",
                "thermal_absorptance", "solar_absorptance", "visible_absorptance",
                "u_value", "shgc", "vt",
            ) if key in props
        },
        "boverket_id": record.get("boverket_id"),
        "boverket_name": carbon.get("boverket_name") if carbon else None,
        "mapping_status": record.get("mapping_status", "unmatched"),
        "gwp": ({
            "unit": "kg CO2 eq./kg",
            "A1_A3_typical": carbon.get("A1_A3_typical"),
            "A1_A3_conservative": carbon.get("A1_A3_conservative"),
            "A4_transport": carbon.get("A4_transport"),
            "A5_conservative": carbon.get("A5_conservative"),
        } if carbon else None),
    }


def load_data(path=None):
    library = Catalogue.load(parametric_path=path)
    catalogue = library.parametric
    registry = library.detailed
    completeness = registry.lod2_completeness(
        catalogue=catalogue
    )
    detailed_states = {
        (row["category"], row["era"], row["state"]): row for row in completeness["states"]
        if row["catalogue_assignment"] == "canonical"
    }
    alternative_states = {}
    for row in completeness["states"]:
        if row["catalogue_assignment"] == "alternative":
            alternative_states.setdefault((row["category"], row["era"], row["state"]), []).append(row)
    packages = {}
    cells = []
    assemblies = registry.assemblies
    for slot in catalogue.slots:
        key = slot.key
        package_id = f"parametric:{key.category}:{key.era}:{key.renovation_state or 'default'}"
        if package_id not in packages:
            properties = {role: prop.to_dict() for role, prop in slot.properties.items()}
            revision = content_hash(properties)
            detailed = detailed_states.get((key.category, key.era, key.renovation_state))
            construction = {}
            if detailed:
                archetype = registry.archetypes[detailed["archetype_id"]]
                state = archetype["states"][key.renovation_state]
                boundary_details = registry.boundary_details(
                    detailed["archetype_id"], key.renovation_state
                )
                base = state if "assemblies" in state else archetype["states"]["existing"]
                resolved = {
                    role: dict(assemblies[aid])
                    for role, aid in base.get("assemblies", {}).items()
                }
                for operation in state.get("operations", []):
                    assembly = dict(assemblies[operation["assembly_id"]])
                    role = operation["role"]
                    if operation["action"] == "replace_window":
                        resolved[role] = assembly
                    else:
                        old = resolved[role]["components"]
                        if operation["action"] == "replace_exterior":
                            old = old[operation["remove_components"]:]
                        added = assembly["components"]
                        resolved[role]["components"] = (
                            added + old if operation["position"] == "outside"
                            else old[:-1] + added + old[-1:]
                        )
                for role, assembly in resolved.items():
                    if role == "WINDOW":
                        window = _material_view(registry, assembly["material_id"])
                        construction[role] = {
                            "window": True, "name": assembly.get("name", "Window"),
                            "material": window,
                            "u_value": slot.construction_set.u_values.get("window"),
                        }
                        continue
                    components = []
                    for component in assembly.get("components", []):
                        component_layers = []
                        for layer in component.get("layers", []):
                            mids = layer["material_id"]
                            mids = [mids] if isinstance(mids, str) else mids
                            materials = [_material_view(registry, mid) for mid in mids]
                            fractions = layer.get("area_fraction", [1.0] if len(mids) == 1 else [])
                            component_layers.append({
                                "name": layer.get("name") or " / ".join(m["name"] for m in materials),
                                "thickness_mm": layer["thickness"] * 1000,
                                "materials": [
                                    {**material, "area_fraction": fractions[i] if i < len(fractions) else None}
                                    for i, material in enumerate(materials)
                                ],
                            })
                        components.append({
                            "name": component.get("name", "Component"),
                            "shearing_layer": component.get("shearing_layer"),
                            "layers": component_layers,
                        })
                    construction[role] = {
                        "name": assembly.get("name", role),
                        "components": components,
                        "boundary_details": boundary_details.get(role, {}),
                        "u_value": slot.construction_set.u_values.get(_VALUE_ROLES.get(role)),
                    }
            lod2 = (
                dict(
                    status="complete" if detailed["lod2_complete"] else "draft",
                    archetype_id=detailed["archetype_id"],
                    checks=detailed["checks"],
                    readiness=detailed["readiness"],
                    remaining=detailed["remaining"],
                    blocking_caveats=len(detailed["blocking_caveats"]),
                    pending_boverket_references=detailed["pending_boverket_references"],
                    alternatives=[
                        dict(archetype_id=variant["archetype_id"],
                             status="complete" if variant["lod2_complete"] else "draft",
                             checks=variant["checks"], remaining=variant["remaining"])
                        for variant in alternative_states.get((key.category, key.era, key.renovation_state), [])
                    ],
                )
                if detailed
                else dict(status="no_recipe")
            )
            packages[package_id] = dict(
                id=package_id,
                revision=revision,
                family=key.category,
                status="lod1_complete" if slot.lod1_complete else "lod1_pending",
                lod=1,
                lod1_complete=slot.lod1_complete,
                missing=list(slot.missing_properties),
                properties=properties,
                lod2=lod2,
                construction=construction,
                construction_availability=(list(registry.archetypes[detailed["archetype_id"]]["states"][key.renovation_state].get("assemblies", {})) if detailed else []),
                element_presence="caller_geometry",
                floor_review=(registry.archetypes[detailed["archetype_id"]]["states"][key.renovation_state].get("v1_review", {}).get("floor_review") if detailed else None),
                generic_donor=(registry.archetypes[detailed["archetype_id"]]["states"][key.renovation_state].get("v1_review", {}).get("generic_donor") if detailed else None),
                u_values={
                    _ROLES[role]: value for role, value in slot.construction_set.u_values.items()
                },
            )
        package = packages[package_id]
        cells.append(
            dict(
                id=slot.slot_id,
                category=key.category,
                era=key.era,
                zone=key.climate_zone,
                state=key.renovation_state or "default",
                system=key.ventilation_system,
                package_id=package_id,
                revision=package["revision"],
                alternatives=[],
                missing=list(slot.missing_properties),
                u_values=package["u_values"],
                family=key.category,
                status=package["status"],
                lod1_complete=slot.lod1_complete,
                lod2_status=package["lod2"]["status"],
            )
        )
    dims = catalogue.dimensions
    return dict(
        manifest=dict(
            release_id=catalogue.release_id, dataset_id=catalogue.dataset_id, schema_version=1
        ),
        cells=cells,
        packages=list(packages.values()),
        sources=[
            dict(id=source_id, **dict(source)) for source_id, source in catalogue.sources.items()
        ],
        dimensions=dict(
            categories=list(dims["categories"]),
            eras=dict(dims["eras"]),
            zones=list(dims["zones"]),
            states=[*dims["states"], "default"],
            systems=list(dims["ventilation"]),
        ),
        summary=catalogue.summary(),
        lod2_summary={
            field: completeness[field]
            for field in (
                "total_slots",
                "slots_with_layer_recipe",
                "slots_without_layer_recipe",
                "lod2_complete_slots",
                "detailed_states",
                "lod2_complete_states",
                "detailed_revision",
                "catalogue_revision",
            )
        },
    )
