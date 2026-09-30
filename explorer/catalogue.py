"""Read-only explorer adapter for the compact parametric catalogue."""

from epsm_data import load_detailed_catalogue, load_parametric_catalogue
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


def load_data(path=None):
    catalogue = load_parametric_catalogue(path)
    registry = load_detailed_catalogue(catalogue=catalogue)
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
    for slot in catalogue.slots:
        key = slot.key
        package_id = f"parametric:{key.category}:{key.era}:{key.renovation_state}"
        if package_id not in packages:
            properties = {role: prop.to_dict() for role, prop in slot.properties.items()}
            revision = content_hash(properties)
            detailed = detailed_states.get((key.category, key.era, key.renovation_state))
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
                state=key.renovation_state,
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
            states=list(dims["states"]),
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
