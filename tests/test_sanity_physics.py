"""Meaningful raw-data mutations for material and construction screening."""

import json
from copy import deepcopy
from importlib.resources import files
from pathlib import Path

import pytest

from epsm_data.sanity import load_sanity_fixture
from epsm_data.sanity_physics import check_physics


@pytest.fixture
def raw():
    props = dict(conductivity=0.13, density=500, specific_heat=1600, roughness="Smooth",
                 thermal_absorptance=0.9, solar_absorptance=0.7, visible_absorptance=0.7)
    return {
        "materials": {"wood": {"name": "Wooden stud", "kind": "opaque", "properties": props,
            "honeybee_id": "hb", "boverket_id": "123"}},
        "honeybee": {"hb": {"identifier": "hb", "type": "EnergyMaterial", **props}},
        "boverket": {"123": {"Name": "Sawn timber", "ResourceId": 123, "InventoryUnit": "kg",
            "Conversions": [{"Field": "Volume", "Unit": "kg/m³", "Value": 500}],
            "DataItems": [{"PropertyCode": "GWP-GHG AR4", "PropertyUnitCode": "kg CO2 eq./kg",
                "DataValueItems": [{"DataModuleCode": module, "Value": value} for module, value in
                    (("A1-A3 Typical", 0.2), ("A4", 0.02), ("A5", 0.03))]}]}},
        "carbon_references": {},
        "layers": {"stud": {"name": "Wooden stud, 100 mm", "thickness": 0.1,
            "is_composite": False, "layer_function": "structure",
            "materials": [{"material_id": "wood", "area_fraction": 1, "thickness": 0.1}]}},
        "components": {"frame": {"name": "Timber frame", "application": "EXT_WALL",
            "shearing_layer": "Structure", "layers": [{"layer_id": "stud", "position": 0}]}},
        "elements": {"wall": {"name": "Timber wall", "role": "EXT_WALL", "components": ["frame"],
            "assembly_family": "timber_frame", "side_convention": "outside_to_inside"}},
        "construction_sets": {"set": {"elements": {"EXT_WALL": "wall"}}},
        "archetypes": {"sf_se01": {"states": {"existing": {"construction_set_id": "set"}}}},
    }


def findings(raw, rule=None):
    result = []

    def emit(rule_id, severity, path, message, **details):
        result.append(dict(rule_id=rule_id, severity=severity, path=path, message=message, **details))

    check_physics(raw, emit)
    return result if rule is None else [item for item in result if item["rule_id"] == rule]


def test_complete_consistent_fixture_is_read_only(raw):
    before = deepcopy(raw)
    assert findings(raw) == []
    assert raw == before


@pytest.mark.parametrize(("name", "rule", "severity"), [
    ("", "material.name", "error"), ("  ", "material.name", "error"),
    (" Wooden stud ", "material.name", "review"),
    ("Material 2", "material.name_ambiguous", "review"),
    ("Wooden stud used in archetype A", "material.name_usage", "review"),
])
def test_material_names(raw, name, rule, severity):
    raw["materials"]["wood"]["name"] = name
    assert any(item["severity"] == severity for item in findings(raw, rule))


def test_distinct_physics_needs_distinct_names(raw):
    raw["materials"]["other"] = deepcopy(raw["materials"]["wood"])
    raw["materials"]["other"]["properties"]["density"] = 600
    result = findings(raw, "material.name_ambiguous")
    assert len(result) == 1
    assert result[0]["related_paths"] == ["materials.wood"]


@pytest.mark.parametrize("section,identifier", [
    ("materials", "wood"), ("layers", "stud"), ("components", "frame"),
    ("elements", "wall"), ("construction_sets", "set"),
])
def test_physical_duplicates_ignore_label_and_notes(raw, section, identifier):
    raw[section]["duplicate"] = deepcopy(raw[section][identifier])
    raw[section]["duplicate"].update(name="A different name", notes=["Curation note"])
    duplicates = findings(raw, "definition.duplicate")
    assert any(item["path"] == f"{section}.duplicate" for item in duplicates)


def test_component_duplicate_signature_sorts_explicit_positions(raw):
    original = raw["components"]["frame"]
    original["layers"].append({"layer_id": "stud", "position": 1})
    raw["components"]["other"] = deepcopy(original)
    raw["components"]["other"]["layers"].reverse()
    assert any(item["path"] == "components.other" for item in findings(raw, "definition.duplicate"))


@pytest.mark.parametrize("section,identifier,field,target", [
    ("materials", "wood", "honeybee_id", "absent"),
    ("materials", "wood", "boverket_id", "absent"),
    ("materials", "wood", "carbon_reference_id", "absent"),
    ("elements", "wall", "components", ["absent"]),
])
def test_broken_source_and_assembly_links_are_collected(raw, section, identifier, field, target):
    raw[section][identifier][field] = target
    assert findings(raw, "reference.dangling")


def test_all_reference_levels_are_checked_even_if_loading_would_fail(raw):
    raw["layers"]["stud"]["materials"][0]["material_id"] = "missing_material"
    raw["components"]["frame"]["layers"][0]["layer_id"] = "missing_layer"
    raw["construction_sets"]["set"]["elements"]["EXT_WALL"] = "missing_element"
    config = raw["archetypes"]["sf_se01"]["states"]["existing"]
    config.update(construction_set_id="missing_set", weather_shell_element_id="missing_roof")
    raw["aliases"] = {"materials": {"old": "missing_alias_target"}}
    assert len(findings(raw, "reference.dangling")) == 6


def test_thermal_source_type_identity_value_and_units_are_independent_errors(raw):
    raw["honeybee"]["hb"].update(identifier="wrong", type="EnergyWindowMaterialSimpleGlazSys",
                                conductivity=0.5, units={"density": "lb/ft3"})
    result = findings(raw)
    assert {item["rule_id"] for item in result if item["severity"] == "error"} >= {
        "thermal.source", "thermal.identity", "thermal.units"}


@pytest.mark.parametrize("field,value", [("density", 0), ("conductivity", -1),
    ("specific_heat", True), ("solar_absorptance", 1.1), ("density", float("inf"))])
def test_invalid_thermal_values(raw, field, value):
    raw["materials"]["wood"]["properties"][field] = value
    assert findings(raw, "thermal.properties")[0]["severity"] == "error"


@pytest.mark.parametrize("density,prominence", [
    (600, None), (600.00001, "normal"), (750, "normal"), (750.00001, "high"),
    (400, None), (399.99, "normal"), (250, "normal"), (249.99, "high"),
])
def test_density_policy_boundaries(raw, density, prominence):
    raw["materials"]["wood"]["properties"]["density"] = density
    result = findings(raw, "density.agreement")
    if prominence is None:
        assert result == []
    else:
        assert result[0]["prominence"] == prominence
        assert result[0]["relative_difference"] == abs(density - 500) / 500
        assert result[0]["expected"] == 500


@pytest.mark.parametrize("source_change", [
    {"Conversions": [{"Field": "Area", "Unit": "kg/m²", "Value": 5}]},
    {"InventoryUnit": "m2"}, {"DensityBasis": "dry_bulk_volume"},
    {"Name": "Lightweight expanded clay clinker"},
])
def test_density_is_not_compared_across_incompatible_bases(raw, source_change):
    raw["boverket"]["123"].update(source_change)
    assert findings(raw, "density.agreement") == []
    assert findings(raw, "density.not_assessed")[0]["assessment"] == "not_assessed"


def test_proxy_is_visible_and_does_not_make_an_unsuitable_family_comparable(raw):
    raw["materials"]["wood"]["notes"] = ["Representative product-family proxy"]
    raw["boverket"]["123"]["Name"] = "Sand lime bricks"
    mapping = findings(raw, "carbon.mapping")
    assert mapping[0]["actual"]["proxy_qualified"] is True
    assert findings(raw, "density.not_assessed")


def test_air_cavity_exemption_is_explicit(raw):
    wood = raw["materials"]["wood"]
    wood["boverket_id"] = None
    assert findings(raw, "carbon.source")
    wood.update(name="Unventilated air gap equivalent 100 mm", non_product=True)
    assert findings(raw, "carbon.source") == []
    assert findings(raw, "density.not_assessed") == []


def test_boverket_a51_does_not_count_as_full_a5(raw):
    values = raw["boverket"]["123"]["DataItems"][0]["DataValueItems"]
    values[-1]["DataModuleCode"] = "A5.1"
    coverage = findings(raw, "carbon.modules")
    assert coverage[0]["severity"] == "review"
    assert coverage[0]["missing_modules"] == ["A5"]
    assert coverage[0]["partial_modules"] == ["A5.1"]


def test_missing_boverket_base_production_still_blocks(raw):
    item = raw["boverket"]["123"]["DataItems"][0]
    item["DataValueItems"] = [row for row in item["DataValueItems"]
                             if not row["DataModuleCode"].startswith("A1-A3")]
    coverage = findings(raw, "carbon.modules")
    assert coverage[0]["severity"] == "missing"
    assert "A1A3" in coverage[0]["missing_modules"]


def test_external_epd_keeps_null_placeholders_and_source_method(raw):
    raw["materials"]["wood"].update(boverket_id=None, carbon_reference_id="EPD-1")
    raw["carbon_references"]["EPD-1"] = {
        "identifier": "EPD-1", "name": "Timber product", "url": "https://example.org/epd",
        "method": "GWP-GHG EN15804+A2", "unit": "kg", "proxy_for": "Historic timber",
        "modules": {"A1A3": 0.002, "A4": None, "A5": None},
    }
    before = deepcopy(raw)
    epd = [item for item in findings(raw, "carbon.modules") if item["path"].startswith("carbon_references")]
    assert epd[0]["missing_modules"] == ["A4", "A5"]
    assert epd[0]["severity"] == "review"
    assert epd[0]["known_modules"]["A1A3"] == 0.002
    assert epd[0]["actual"]["A4"] is None
    assert raw == before
    assert findings(raw, "carbon.mapping")[0]["proxy"] is True


@pytest.mark.parametrize("field,value,rule", [("area_fraction", 0.5, "layer.fractions"),
    ("area_fraction", 0, "layer.fractions"), ("thickness", -0.1, "layer.geometry"),
    ("thickness", 0.05, "layer.depth")])
def test_invalid_layer_shares(raw, field, value, rule):
    raw["layers"]["stud"]["materials"][0][field] = value
    assert findings(raw, rule)[0]["severity"] == "error"


def test_composite_area_fractions_and_depth_are_independent(raw):
    layer = raw["layers"]["stud"]
    layer["materials"] = [{"material_id": "wood", "area_fraction": 0.3, "thickness": 0.1},
                          {"material_id": "wood", "area_fraction": 0.5, "thickness": 0.05}]
    result = findings(raw)
    assert {item["rule_id"] for item in result} >= {"layer.fractions", "layer.depth", "layer.geometry"}


def test_plausible_thickness_policy_is_review_only(raw):
    layer = raw["layers"]["stud"]
    layer["thickness"] = layer["materials"][0]["thickness"] = 0.7
    review = findings(raw, "layer.buildability")[0]
    assert review["severity"] == "review"
    assert review["expected"]["maximum_m"] == load_sanity_fixture()["construction_rules"]["material_families"]["timber"]["maximum_m"]
    assert review["family_inferred"] is True


def test_submillimetre_prefab_precision_needs_explanation(raw):
    layer = raw["layers"]["stud"]
    layer["thickness"] = layer["materials"][0]["thickness"] = 0.028849
    assert findings(raw, "layer.precision")
    layer["notes"] = ["Custom site-cut dimension recorded from representative detail"]
    assert findings(raw, "layer.precision") == []


def test_cast_concrete_can_have_variable_depth_without_prefab_precision_finding(raw):
    wood = raw["materials"]["wood"]
    wood["name"] = "Concrete"
    layer = raw["layers"]["stud"]
    layer["thickness"] = layer["materials"][0]["thickness"] = 0.128849
    assert findings(raw, "layer.precision") == []


def test_depth_specific_effective_air_cannot_be_reused_at_other_depth(raw):
    raw["materials"]["wood"].update(name="Unventilated air gap equivalent 150 mm", non_product=True)
    assert any("Depth-specific" in item["message"] for item in findings(raw, "layer.depth"))


@pytest.mark.parametrize("position", [-1, True, 0.5])
def test_component_positions_are_nonnegative_integers(raw, position):
    raw["components"]["frame"]["layers"][0]["position"] = position
    assert findings(raw, "component.positions")[0]["severity"] == "error"


def test_duplicate_positions_and_roles_are_errors(raw):
    raw["components"]["frame"]["layers"].append({"layer_id": "stud", "position": 0})
    raw["components"]["frame"]["application"] = "GROUND_FLOOR"
    assert findings(raw, "component.positions")
    assert findings(raw, "assembly.role")


def test_missing_assembly_metadata_is_not_a_pass(raw):
    del raw["elements"]["wall"]["assembly_family"]
    assert findings(raw, "assembly.metadata")[0]["assessment"] == "not_assessed"


def test_order_checks_span_component_interfaces(raw):
    layers = raw["layers"]
    layers["lining"] = deepcopy(layers["stud"])
    layers["lining"]["layer_function"] = "lining"
    layers["weather"] = deepcopy(layers["stud"])
    layers["weather"]["layer_function"] = "weather_protection"
    raw["components"]["frame"]["layers"] = [{"layer_id": "lining", "position": 0}]
    raw["components"]["skin"] = {"application": "EXT_WALL", "shearing_layer": "Skin",
                                       "layers": [{"layer_id": "weather", "position": 0}]}
    raw["elements"]["wall"]["components"].append("skin")
    assert findings(raw, "assembly.order")
    raw["elements"]["wall"]["side_convention"] = "inside_to_outside"
    assert findings(raw, "assembly.order") == []


def test_invalid_metadata_is_collected_without_crashing(raw):
    raw["layers"]["stud"]["layer_function"] = ["unknown"]
    raw["elements"]["wall"]["side_convention"] = {"invalid": True}
    raw["components"]["frame"]["application"] = ["GROUND_FLOOR"]
    assert findings(raw, "assembly.metadata")
    assert findings(raw, "component.role")


def test_malformed_raw_records_do_not_prevent_other_findings(raw):
    raw["materials"]["wood"]["kind"] = []
    raw["materials"]["malformed"] = ["not a definition"]
    raw["honeybee"]["hb"]["units"] = {"density": []}
    raw["layers"]["stud"]["materials"].append(None)
    raw["components"]["frame"]["layers"].append("invalid slot")
    raw["elements"]["wall"]["role"] = []
    result = findings(raw)
    assert {item["rule_id"] for item in result} >= {
        "definition.structure", "thermal.properties", "layer.fractions", "component.positions", "assembly.role"}


def test_construction_expectations_match_packaged_fixture():
    expected = Path(__file__).parent / "fixtures" / "catalogue_sanity" / "construction_rules.json"
    packaged = files("epsm_data.datasets.sanity").joinpath("construction_rules.json")
    assert json.loads(expected.read_text()) == json.loads(packaged.read_text())
    assert load_sanity_fixture()["construction_rules"] == json.loads(expected.read_text())


def test_custom_fixture_controls_density_and_buildability(raw):
    fixture = deepcopy(load_sanity_fixture())
    fixture["policy"]["density_review_relative_difference"] = 0.01
    fixture["construction_rules"]["material_families"]["timber"]["maximum_m"] = 0.05
    raw["materials"]["wood"]["properties"]["density"] = 510
    emitted = []
    check_physics(raw, lambda *args, **kwargs: emitted.append((args, kwargs)), fixture=fixture)
    assert any(args[0] == "density.agreement" for args, _ in emitted)
    assert any(args[0] == "layer.buildability" for args, _ in emitted)


def test_composite_marking_requires_multiple_constituents(raw):
    raw["layers"]["stud"]["is_composite"] = True
    assert findings(raw, "layer.geometry")[0]["severity"] == "error"


def test_window_carbon_cannot_silently_use_an_opaque_product(raw):
    material = raw["materials"]["wood"]
    material.update(kind="window", name="Whole window", properties={"u_value": 1.3, "shgc": 0.5, "vt": 0.6})
    assert any("product scopes" in item["message"] for item in findings(raw, "carbon.mapping"))


def _custom(raw, provenance=None):
    raw["honeybee"]["EPSM_wood"] = {**raw["honeybee"].pop("hb"), "identifier": "EPSM_wood"}
    raw["materials"]["wood"]["honeybee_id"] = "EPSM_wood"
    if provenance is not None:
        raw["honeybee"]["EPSM_wood"]["user_data"] = {"provenance": provenance}
    return raw


def test_upstream_thermal_records_need_no_epsm_provenance(raw):
    assert findings(raw, "thermal.provenance") == []


@pytest.mark.parametrize("state, severity", [("existing", "review"), ("advanced", "missing")])
def test_custom_thermal_without_provenance_blocks_only_renovation_use(raw, state, severity):
    raw["archetypes"]["sf_se01"]["states"] = {state: {"construction_set_id": "set"}}
    [finding] = findings(_custom(raw), "thermal.provenance")
    assert finding["severity"] == severity
    assert finding["actual"] == "EPSM_wood"


def test_custom_thermal_with_sourced_provenance_passes(raw):
    provenance = {"tier": "standard", "basis": "Softwood design value.",
                  "sources": [{"reference": "EN ISO 10456"}]}
    assert findings(_custom(raw, provenance), "thermal.provenance") == []


@pytest.mark.parametrize("provenance", [
    {"tier": "guess", "basis": "x", "sources": [{"reference": "y"}]},
    {"tier": "product", "basis": " ", "sources": [{"reference": "y"}]},
    {"tier": "product", "basis": "x", "sources": []},
    {"tier": "product", "basis": "x", "sources": [{"url": "https://example.org"}]},
])
def test_malformed_provenance_is_an_error(raw, provenance):
    [finding] = findings(_custom(raw, provenance), "thermal.provenance")
    assert finding["severity"] == "error"


def test_assumed_custom_thermal_values_stay_visible_for_review(raw):
    provenance = {"tier": "assumption", "basis": "Generic grade.", "sources": [{"reference": "note"}]}
    [finding] = findings(_custom(raw, provenance), "thermal.provenance")
    assert finding["severity"] == "review"


def test_packaged_custom_records_all_declare_provenance():
    from epsm_data import Catalogue, check_catalogue

    report = check_catalogue(Catalogue.load())
    rows = [row for row in report["findings"] if row["rule_id"] == "thermal.provenance"]
    assert all(row["severity"] == "review" and row["actual"]["tier"] == "assumption" for row in rows)
