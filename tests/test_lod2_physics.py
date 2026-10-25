"""Reviewed physical regression values for the accepted catalogue."""

import hashlib
import json
from pathlib import Path

from epsm_data import Catalogue, WindowElement


def _physical(element):
    if isinstance(element, WindowElement):
        return {
            "u_value": element.u_value,
            "shgc": element.shgc,
            "vt": element.vt,
            "boverket_id": str(element.boverket_id) if element.boverket_id is not None else None,
        }
    return [
        {
            "shearing_layer": component.shearing_layer.value,
            "layers": [
                {
                    "position": slot.position,
                    "thickness": slot.layer.thickness,
                    "is_composite": slot.layer.is_composite,
                    "materials": [
                        {
                            "area_fraction": share.area_fraction,
                            "thickness": share.thickness,
                            "properties": {
                                key: value
                                for key, value in share.material.to_dict().items()
                                if key
                                not in {
                                    "uuid",
                                    "json_id",
                                    "name",
                                    "material_type",
                                    "embodied_carbon",
                                    "carbon_reference",
                                }
                            },
                        }
                        for share in slot.layer.materials
                    ],
                }
                for slot in component.layers
            ],
        }
        for component in element.components
    ]


def test_all_76_frozen_configurations_preserve_their_accepted_physical_values():
    expected = json.loads((Path(__file__).parent / "fixtures/lod2-physics.json").read_text())
    catalogue = Catalogue.load()
    checked = 0
    for key, roles in expected.items():
        identifier, state = key.split(":")
        archetype = catalogue.get(identifier, state=None if state == "default" else state)
        assert set(roles) == {role.value for role in archetype.construction_set.elements}
        for role, element in archetype.construction_set.elements.items():
            actual = hashlib.sha256(
                json.dumps(
                    _physical(element), sort_keys=True, ensure_ascii=False, allow_nan=False
                ).encode()
            ).hexdigest()
            assert element.u_value == roles[role.value]["u_value"], (key, role)
            assert actual == roles[role.value]["physics"], (key, role)
        checked += 1
    assert checked == 76


def test_original_retained_source_evidence_is_unchanged():
    root = Path(__file__).resolve().parents[1]
    index = json.loads((root / "evidence/source-index.json").read_text())
    for record in index["files"]:
        assert (
            hashlib.sha256((root / record["retained_path"]).read_bytes()).hexdigest()
            == record["sha256"]
        )
