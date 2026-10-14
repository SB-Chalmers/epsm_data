"""Build and serialize an illustrative wall/window archetype entirely offline."""

import json

from epsm_data import (
    EmbodiedCarbon,
    Material,
    Roughness,
    archetype_from_dict,
    archetype_to_dict,
    build_archetype,
)


def make_example():
    """Return an illustrative archetype with explicitly synthetic material data."""
    carbon = EmbodiedCarbon(
        name="Synthetic carbon example",
        resource_id="example:carbon",
        boverket_name="Synthetic example, not a Boverket resource",
        A1_A3_conservative=0.2,
        A1_A3_typical=0.15,
        A4_transport=0.01,
        A5_conservative=0.01,
        conservative_factor=1.3,
        conversion_factor=400,
        technical_service_life="50",
        biogenic_carbon=0,
    )
    board = Material(
        name="Example board",
        json_id="example:board",
        boverket_id="",
        material_type="EnergyMaterial",
        roughness=Roughness.MEDIUM_ROUGH,
        density=400,
        specific_heat=1200,
        thermal_absorptance=0.9,
        solar_absorptance=0.6,
        visible_absorptance=0.6,
        conductivity=0.1,
        embodied_carbon=carbon,
    )
    return build_archetype(
        {
            "archetype_id": "EXAMPLE_1960",
            "display_name": "Illustrative reference",
            "construction_year": 1960,
            "building_typology": "multi_family",
            "elements": {
                "EXT_WALL": {
                    "components": [
                        {
                            "shearing_layer": "Skin",
                            "layers": [
                                {"material_id": "board", "thickness": 0.2},
                            ],
                        }
                    ]
                },
                "WINDOW": {"u_value": 2.5, "shgc": 0.7},
            },
        },
        materials={"board": board},
    )


def main():
    arch = make_example()
    encoded = json.dumps(archetype_to_dict(arch), indent=2)
    restored = archetype_from_dict(json.loads(encoded))
    assert restored == arch
    print(f"{restored.archetype_id}: {restored.envelope_u_values}")
    print(encoded)


if __name__ == "__main__":
    main()
