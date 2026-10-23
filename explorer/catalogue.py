"""Read-only presentation of the public, reference-linked LoD2 catalogue."""

import hashlib
import json

from epsm_data import Catalogue

_VALUE_ROLES = {
    "TOP_FLOOR": "top",
    "ROOF": "top",
    "EXT_WALL": "wall",
    "INTERMEDIATE_FLOOR": "intermediate_floor",
    "GROUND_FLOOR": "ground",
    "BASEMENT_WALL": "basement_wall",
    "BASEMENT_FLOOR": "ground",
    "INT_WALL_LOADBEARING": "internal_wall",
    "INT_WALL_NONLOADBEARING": "internal_wall",
    "WINDOW": "glazing",
}
_PROPERTY_ROLES = {
    "top": "roof",
    "wall": "external_wall",
    "ground": "ground_floor",
    "glazing": "window",
    "intermediate_floor": "intermediate_floor",
    "internal_wall": "internal_wall",
    "basement_wall": "basement_wall",
}


def _content_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def _material_view(library, material_id):
    record = library.material_records[material_id]
    props = dict(record["properties"])
    material = library.materials.get(material_id)
    carbon = material.embodied_carbon if material is not None else None
    resource = library.boverket_resources.get(str(record.get("boverket_id")), {})
    values = {
        item["DataModuleCode"]: item["Value"]
        for group in resource.get("DataItems", ())
        if group.get("PropertyCode") == "GWP-GHG AR4"
        for item in group.get("DataValueItems", ())
    }
    gwp = (
        carbon.to_dict()
        if carbon
        else {
            "A1_A3_typical": values.get("A1-A3 Typical"),
            "A1_A3_conservative": values.get("A1-A3 Conservative"),
            "A4_transport": values.get("A4"),
            "A5_conservative": values.get("A5.1"),
        }
    )
    return {
        "id": material_id,
        "name": record["name"],
        "honeybee_id": record.get("honeybee_id"),
        "honeybee_properties": props,
        "boverket_id": record.get("boverket_id"),
        "boverket_name": resource.get("Name"),
        "mapping_status": "non_product"
        if record.get("non_product")
        else ("mapped" if record.get("boverket_id") else "missing"),
        "gwp": {"unit": "kg CO2 eq./kg", **gwp} if resource else None,
    }


def _construction_view(library, raw, construction_id):
    result = {}
    construction = raw["construction_sets"].get(construction_id, {})
    for role, element_id in construction.get("elements", {}).items():
        record = raw["elements"][element_id]
        element = library.elements.get(element_id)
        value = element.u_value if element is not None else None
        if role == "WINDOW":
            result[role] = {
                "window": True,
                "name": record["name"],
                "u_value": value,
                "material": _material_view(library, record["window_material_id"]),
            }
            continue
        components = []
        for component_id in record.get("components", ()):
            component = raw["components"][component_id]
            layers = []
            for slot in sorted(component["layers"], key=lambda item: item["position"]):
                layer = raw["layers"][slot["layer_id"]]
                layers.append(
                    {
                        "name": layer["name"],
                        "thickness_mm": layer["thickness"] * 1000
                        if layer.get("thickness") is not None
                        else None,
                        "materials": [
                            {
                                **_material_view(library, item["material_id"]),
                                "area_fraction": item.get("area_fraction"),
                            }
                            for item in layer["materials"]
                        ],
                    }
                )
            components.append(
                {
                    "name": component["name"],
                    "layers": layers,
                    "shearing_layer": component["shearing_layer"],
                }
            )
        result[role] = {"name": record["name"], "components": components, "u_value": value}
    return result


def load_data(path=None):
    library = Catalogue.load(path)
    raw = library.to_dict()
    packages, cells = {}, []
    for slot in library.search():
        key = slot.key
        package_id = f"lod2:{slot.archetype_id}:{slot.state or 'default'}"
        if package_id not in packages:
            construction = _construction_view(library, raw, slot.construction_set_id)
            u_values = {
                _VALUE_ROLES[role]: record["u_value"]
                for role, record in construction.items()
                if role in _VALUE_ROLES
            }
            report = library.completeness(slot.archetype_id, state=slot.state)
            status = "complete" if report["complete"] else "incomplete"
            packages[package_id] = {
                "id": package_id,
                "revision": _content_hash(construction),
                "lod": 2,
                "construction_set_id": slot.construction_set_id,
                "family": key.category,
                "status": status,
                "missing": list(report["missing_values"]),
                "u_values": u_values,
                "properties": {
                    _PROPERTY_ROLES[role]: {"value": value, "unit": "W/(m² K)"}
                    for role, value in u_values.items()
                },
                "construction": construction,
                "construction_availability": list(construction),
                "lod2": {
                    "status": status,
                    "archetype_id": slot.archetype_id,
                    "remaining": list(report["missing_values"]),
                },
            }
        package = packages[package_id]
        cells.append(
            {
                "id": slot.key.id,
                "category": key.category,
                "era": key.era,
                "zone": key.climate_zone,
                "state": slot.state or "default",
                "package_id": package_id,
                "revision": package["revision"],
                "alternatives": [],
                "family": key.category,
                "status": package["status"],
                "lod2_status": package["status"],
                "missing": package["missing"],
                "u_values": package["u_values"],
            }
        )
    dimensions = library.dimensions
    return {
        "manifest": {
            "dataset_id": library.dataset_id,
            "release_id": _content_hash(raw),
            "schema_version": 2,
        },
        "cells": cells,
        "packages": list(packages.values()),
        "dimensions": {
            "categories": list(dimensions["categories"]),
            "eras": {era: list(years) for era, years in dimensions["eras"].items()},
            "zones": list(dimensions["zones"]),
            "states": [*dimensions["states"], "default"],
        },
        "summary": library.summary(),
    }
