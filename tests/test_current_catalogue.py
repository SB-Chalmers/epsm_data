"""Shared physical graph, safe editing, renovation and source input boundaries."""

import json

import pytest

from epsm_data import (
    Catalogue,
    construction_set_to_dict,
)


def test_catalogue_year_assignment_and_se07_independent_recipes(detailed_copy):
    cat = Catalogue.load()
    assert len(cat.ids()) == 35
    assert cat.for_year("multi_family",2021).archetype_id == "MF_SE06_EXISTING"
    modern = cat.for_year("multi_family",2022)
    assert modern.archetype_id == "MF_SE07"
    assert cat.renovation_states("mf_se07") == ()
    assert len(modern.construction_set.elements) == 7
    with pytest.raises(ValueError, match="no renovation states"):
        cat.get("mf_se07",state="advanced")
    path, records = detailed_copy
    old = records["archetypes"]["archetypes"]["mf_se06"]["states"]["advanced"]
    new = records["archetypes"]["archetypes"]["mf_se07"]["configuration"]
    assert set(old["assemblies"].values()).isdisjoint(new["assemblies"].values())
    assembly = records["assemblies"]["assemblies"][old["assemblies"]["EXT_WALL"]]
    layer = assembly["components"][0]["layers"][0]
    material_id = layer["material_id"]
    material_id = material_id[0] if isinstance(material_id,list) else material_id
    hid = records["materials"]["materials"][material_id]["honeybee_id"]
    records["honeybee"]["materials"][hid]["density"] *= 1.01
    for name, payload in records.items():
        (path / f"{name}.json").write_text(json.dumps(payload))
    after = Catalogue.load(detailed_path=path).for_year("multi_family",2022)
    assert construction_set_to_dict(after.construction_set) == construction_set_to_dict(modern.construction_set)
