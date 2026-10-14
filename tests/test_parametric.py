"""Current explicit properties, independent editing and construction periods."""

import json

import pytest

from epsm_data import ArchetypeKey, ParametricCatalogue, load_parametric_catalogue
from epsm_data.parametric import CATEGORIES, ERAS, PROPERTIES, era_for_year, main, states_for_era


def test_current_dimensions_and_roundtrip():
    catalogue = load_parametric_catalogue()
    assert len(catalogue.slots) == len({slot.slot_id for slot in catalogue.slots}) == 1140
    assert catalogue.summary()["lod1_complete"] == 1140
    assert dict(catalogue.dimensions["eras"]) == ERAS
    assert len(catalogue.search(category="school")) == 228
    assert len(catalogue.search(renovation_state="advanced")) == 360
    assert len(catalogue.search(era="SE.07")) == 60
    assert len(catalogue.search(era="SE.07", renovation_state="advanced")) == 0
    assert ParametricCatalogue(json.loads(json.dumps(catalogue.to_dict()))).release_id == catalogue.release_id


@pytest.mark.parametrize("year,era", [(1960,"SE.01"),(1961,"SE.02"),(2005,"SE.05"),
                                    (2006,"SE.06"),(2021,"SE.06"),(2022,"SE.07"),(2050,"SE.07")])
def test_year_boundaries(year, era):
    assert era_for_year(year) == era


@pytest.mark.parametrize("year", [0,-1,True,2021.5,"2022",None])
def test_invalid_year(year):
    with pytest.raises(ValueError):
        era_for_year(year)


@pytest.mark.parametrize("state", ["existing","standard","advanced"])
def test_se07_has_no_renovation_state(state):
    with pytest.raises(ValueError, match="no renovation states"):
        ArchetypeKey("multi_family","SE.07","SE.Zone1",state,"FTX")


def test_single_configuration_identifier():
    cat = load_parametric_catalogue()
    key = ArchetypeKey("multi_family","SE.07","SE.Zone1",None,"FTX")
    assert cat.get_slot(key.id).key == key
    assert key.to_dict()["renovation_state"] is None
    assert states_for_era("SE.07") == (None,)


def test_current_properties_match_copied_se06_advanced():
    cat = load_parametric_catalogue()
    for category in CATEGORIES:
        old = cat.get_slot(ArchetypeKey(category,"SE.06","SE.Zone1","advanced","S"))
        new = cat.get_slot(ArchetypeKey(category,"SE.07","SE.Zone1",None,"S"))
        for prop in PROPERTIES:
            assert new.properties[prop].value == old.properties[prop].value
            assert new.properties[prop].source == old.properties[prop].source
            assert new.properties[prop].evidence["copied_from"] == f"{category}:SE.06:advanced"


def test_explicit_edit_is_local_and_never_updates_se07():
    cat = load_parametric_catalogue()
    before = cat.to_dict()
    updated = cat.with_property("multi_family","SE.06","advanced","external_wall",
                                {"value":.42,"source":"proxy","note":"Synthetic caller edit"})
    assert cat.to_dict() == before
    actual = updated.to_dict()
    changed = [(key, role) for key, properties in before["resolved"].items()
               for role, record in properties.items() if record != actual["resolved"][key][role]]
    assert changed == [("multi_family:SE.06:advanced","external_wall")]
    evidence = actual["resolved"]["multi_family:SE.06:advanced"]["external_wall"]["evidence"]
    assert evidence["basis_stale"]


def test_legacy_edit_names_replace_one_current_value_without_propagation():
    cat = load_parametric_catalogue()
    reference = {"era":"SE.02","state":"existing","value":.5,"source":"proxy","note":"test"}
    a = cat.with_anchor("office","roof",reference)
    b = cat.with_override("office","roof",reference)
    assert a.to_dict() == b.to_dict()
    assert a.resolve_construction("office","SE.02","advanced") == cat.resolve_construction("office","SE.02","advanced")


@pytest.mark.parametrize("value", [-1,0,True,float("nan"),float("inf")])
def test_invalid_current_thermal_value(value):
    cat = load_parametric_catalogue()
    with pytest.raises(ValueError):
        cat.with_property("office","SE.02","existing","roof",{"value":value,"source":"proxy","note":"test"})


def test_unknown_value_is_not_zero_and_mapping_is_defensive():
    cat = load_parametric_catalogue().with_property("office","SE.02","existing","roof",{"value":None})
    slot = cat.get_slot("office:SE.02:SE.Zone1:existing:S")
    assert slot.missing_properties == ("roof",)
    copy = cat.to_dict()
    copy["resolved"]["office:SE.02:existing"]["roof"]["value"] = 10
    assert cat.get_slot(slot.key).properties["roof"].value is None


@pytest.mark.parametrize("mutation", [
    lambda d: d["resolved"].pop("office:SE.07:default"),
    lambda d: d["resolved"]["office:SE.07:default"].pop("roof"),
    lambda d: d["resolved"]["office:SE.07:default"]["roof"].update(unit="unknown"),
    lambda d: d["resolved"]["office:SE.07:default"]["roof"].update(source="absent"),
    lambda d: d["dimensions"]["eras"].update({"SE.06":[2006,None]}),
    lambda d: d.update(categories={}),
    lambda d: d.update(schema_version=True),
])
def test_invalid_current_catalogue(mutation):
    data = load_parametric_catalogue().to_dict()
    mutation(data)
    with pytest.raises(ValueError):
        ParametricCatalogue(data)


def test_cli_current_summary(capsys):
    assert main(["--check","--summary"]) == 0
    assert json.loads(capsys.readouterr().out)["slot_count"] == 1140
