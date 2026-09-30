"""Reference fidelity, deterministic propagation and strict LoD1 validation."""

import json
from itertools import product

import pytest

from epsm_data import ArchetypeKey, ParametricCatalogue, load_parametric_catalogue
from epsm_data.parametric import (
    CATEGORIES,
    ELEMENTS,
    ERAS,
    STATES,
    SYSTEMS,
    ZONES,
    content_hash,
    era_for_year,
    main,
)


@pytest.fixture(scope="module")
def catalogue():
    # Explicit partial caller catalogue derived from the current schema.
    data = load_parametric_catalogue().to_dict()
    data.pop("claim_metadata", None)
    for category in ("office", "school", "generic"):
        data["categories"][category]["anchors"] = {}
        data["categories"][category]["overrides"] = []
    for category in ("multi_family", "single_family"):
        for role in ("internal_wall", "intermediate_floor"):
            data["categories"][category]["anchors"].pop(role, None)
        data["categories"][category]["overrides"] = []
    data["categories"]["single_family"]["anchors"].pop("basement_wall", None)
    return ParametricCatalogue(data)


def reference(value, era="SE.03", state="advanced"):
    return dict(value=value, era=era, state=state, source="proxy", note="Test supplied evidence")


def slot(catalogue, category="office", era="SE.03", state="advanced"):
    return catalogue.get_slot(ArchetypeKey(category, era, "SE.Zone1", state, "S"))






@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(margin_percent=-1),
        lambda p: p.update(margin_percent=True),
        lambda p: p.update(margin_percent=float("inf")),
        lambda p: p.update(source="missing"),
        lambda p: p.update(note=""),
        lambda p: p.update(unknown=1),
        lambda p: p.update(benchmarks={}),
        lambda p: p["benchmarks"].update(roof=0),
        lambda p: p["benchmarks"].update(roof=float("nan")),
        lambda p: p.update(margin_percent=1e308, benchmarks={"roof": 1e308}),
        lambda p: p["benchmarks"].update(internal_wall=0.1),
        lambda p: p["benchmarks"].update(ground_floor=0.1),
    ],
)
def test_invalid_guardrail_definitions(mutation):
    data = load_parametric_catalogue().to_dict()
    data["performance_guardrail"] = {"source": "proxy", "note": "Synthetic optional guardrail", "margin_percent": 25, "benchmarks": {"roof": 0.08, "external_wall": 0.10, "window": 0.60}}
    mutation(data["performance_guardrail"])
    with pytest.raises(ValueError):
        ParametricCatalogue(data)
















def test_dimensions_ids_search_and_portable_export(catalogue):
    assert len(catalogue.slots) == len({s.slot_id for s in catalogue.slots}) == 1080
    assert set(catalogue.dimensions["categories"]) == set(CATEGORIES)
    assert dict(catalogue.dimensions["eras"]) == ERAS
    assert catalogue.dimensions["zones"] == ZONES
    assert catalogue.dimensions["states"] == STATES
    assert catalogue.dimensions["ventilation"] == SYSTEMS
    assert len(catalogue.search(category="school")) == 216
    assert (
        len(
            catalogue.search(
                climate_zone="SE.Zone2", renovation_state="standard", ventilation_system="FTX"
            )
        )
        == 30
    )
    assert not catalogue.search(lod1_complete_only=True)
    assert "slots" not in catalogue.to_dict()
    assert (
        ParametricCatalogue(json.loads(json.dumps(catalogue.to_dict()))).release_id
        == catalogue.release_id
    )
    assert catalogue.get_slot("multi_family:SE.02:SE.Zone3:existing:F").key.to_dict() == dict(
        category="multi_family",
        era="SE.02",
        climate_zone="SE.Zone3",
        renovation_state="existing",
        ventilation_system="F",
    )
    assert era_for_year(1960) == "SE.01"
    assert era_for_year(2005) == "SE.05"
    assert era_for_year(2006) == era_for_year(2035) == "SE.06"
    for invalid in ("office:SE.03", "retail:SE.01:SE.Zone1:existing:S"):
        with pytest.raises(ValueError):
            catalogue.get_slot(invalid)
    with pytest.raises(ValueError):
        catalogue.search(category="retail")
    with pytest.raises(ValueError):
        era_for_year(0)




@pytest.mark.parametrize("era,state", tuple(product(ERAS, STATES)))
def test_anchor_at_any_era_state_and_replacement(catalogue, era, state):
    updated = catalogue.with_anchor("office", "external_wall", reference(0.42, era, state))
    assert slot(updated, era=era, state=state).properties["external_wall"].value == 0.42
    curve_id = catalogue.to_dict()["categories"]["office"]["curves"]["external_wall"]
    curves = catalogue.to_dict()["curves"][curve_id]["values"]
    for target_era, target_state in product(ERAS, STATES):
        resolved = slot(updated, era=target_era, state=target_state).properties["external_wall"]
        assert resolved.value == pytest.approx(
            0.42 * curves[target_era][target_state] / curves[era][state]
        )
        assert resolved.curve == curve_id
        assert resolved.assumed
    replaced = updated.with_anchor("office", "external_wall", reference(0.84, era, state))
    assert slot(replaced).properties["external_wall"].value == pytest.approx(
        2 * slot(updated).properties["external_wall"].value
    )
    assert slot(catalogue).properties["external_wall"].value is None
    assert slot(updated, "generic").properties["external_wall"].value is None
    assert slot(updated).properties["roof"].value is None


def test_override_precedence_is_local_and_survives_anchor_replacement(catalogue):
    initial_overrides = catalogue.to_dict()["categories"]["office"]["overrides"]
    overridden = catalogue.with_override("office", "roof", reference(0.12))
    assert slot(overridden).properties["roof"].mode == "overridden"
    assert slot(overridden, era="SE.04").properties["roof"].value is None
    anchored = overridden.with_anchor("office", "roof", reference(0.3, "SE.01", "existing"))
    replaced = anchored.with_anchor("office", "roof", reference(0.6, "SE.02", "standard"))
    assert slot(replaced).properties["roof"].value == 0.12
    assert slot(replaced).properties["roof"].override["note"]
    assert (
        slot(replaced, era="SE.04").properties["roof"].value
        != slot(anchored, era="SE.04").properties["roof"].value
    )
    twice = replaced.with_override("office", "roof", reference(0.13))
    overrides = twice.to_dict()["categories"]["office"]["overrides"]
    assert len(overrides) == len(initial_overrides) + 1
    assert sum(
        row["property"] == "roof" and row["era"] == "SE.03" and row["state"] == "advanced"
        for row in overrides
    ) == 1
    assert slot(twice).properties["roof"].value == 0.13
    masked = twice.with_override("office", "roof", reference(None))
    assert slot(masked).properties["roof"].value is None
    assert not slot(masked).lod1_complete


def test_zone_and_ventilation_invariance(catalogue):
    catalogue = catalogue.with_override("school", "window", reference(1.1))
    for category, era, state in product(CATEGORIES, ERAS, STATES):
        expected = slot(catalogue, category, era, state)
        for zone, system in product(ZONES, SYSTEMS):
            resolved = catalogue.get_slot(ArchetypeKey(category, era, zone, state, system))
            assert resolved.construction_set.to_dict() == expected.construction_set.to_dict()
            assert resolved.infiltration.to_dict() == expected.infiltration.to_dict()






def test_infiltration_inheritance_and_explicit_references(catalogue):
    for era, state in product(ERAS, STATES):
        mf = slot(catalogue, "multi_family", era, state).infiltration
        for category in ("office", "school", "generic"):
            inherited = slot(catalogue, category, era, state).infiltration
            assert inherited.value == mf.value
            assert inherited.mode == "inherited"
            assert inherited.anchor["category"] == "multi_family"
    overridden = catalogue.with_override("multi_family", "infiltration", reference(0.07))
    assert slot(overridden, "multi_family").infiltration.value == 0.07
    assert (
        slot(overridden, "office").infiltration.value
        == slot(catalogue, "office").infiltration.value
    )
    assert slot(overridden, "office").infiltration.override is None
    assert slot(overridden, "single_family").infiltration.value != 0.07
    new_anchor = catalogue.with_anchor("multi_family", "infiltration", reference(0.17))
    assert slot(new_anchor, "office").infiltration.value == 0.17
    independent = overridden.with_anchor("office", "infiltration", reference(0.15))
    assert slot(independent).infiltration.value == 0.15
    assert slot(independent).infiltration.mode == "direct"
    independent = independent.with_override("office", "infiltration", reference(0))
    assert slot(independent).infiltration.value == 0


def test_exact_eight_property_completeness_and_pending_nulls(catalogue):
    assert catalogue.summary()["lod1_complete"] == 0
    assert len(slot(catalogue, "office").missing_properties) == 7
    assert len(slot(catalogue, "multi_family").missing_properties) == 2
    updated = catalogue
    for index, role in enumerate(ELEMENTS):
        updated = updated.with_anchor("generic", role, reference(0.3 + index))
        assert slot(updated, "generic").lod1_complete == (index == 6)
    assert updated.summary()["lod1_complete"] == 216
    assert len(updated.search(lod1_complete_only=True)) == 216
    zero = updated.with_anchor("generic", "infiltration", reference(0))
    assert slot(zero, "generic").lod1_complete
    missing = zero.with_anchor("generic", "infiltration", reference(None))
    assert not slot(missing, "generic").lod1_complete
    assert missing.summary()["lod1_complete"] == 0
    assert all(
        p.unit == "W/(m²K)" for p in slot(updated, "generic").construction_set.properties.values()
    )
    assert slot(updated, "generic").infiltration.unit == "1/h"


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, "0.3"])
def test_invalid_u_values_rejected(catalogue, value):
    with pytest.raises(ValueError):
        catalogue.with_anchor("office", "roof", reference(value))
    with pytest.raises(ValueError):
        catalogue.with_override("office", "roof", reference(value))


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True])
def test_invalid_infiltration_rejected(catalogue, value):
    with pytest.raises(ValueError):
        catalogue.with_anchor("office", "infiltration", reference(value))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["dimensions"]["zones"].append("SE.Zone4"),
        lambda d: d["dimensions"]["eras"].update({"SE.06": [2006, 2026]}),
        lambda d: d["dimensions"]["categories"].pop("generic"),
        lambda d: d["categories"]["office"]["curves"].update(roof="absent"),
        lambda d: d["curves"]["mf.roof"].update(source="absent"),
        lambda d: d["curves"]["mf.roof"]["era_sources"].update({"SE.06": "absent"}),
        lambda d: d["curves"]["mf.roof"]["values"]["SE.01"].update(existing=0),
        lambda d: d["curves"]["mf.internal_wall"].update(proxy="mf.internal_wall"),
        lambda d: d["categories"]["office"].update(infiltration_from="office"),
        lambda d: d["categories"]["office"]["anchors"].update(
            roof={**reference(0.2), "source": "absent"}
        ),
        lambda d: d["categories"]["office"]["anchors"].update(
            roof={k: v for k, v in reference(0.2).items() if k != "note"}
        ),
        lambda d: d["categories"]["office"]["overrides"].extend(
            [{**reference(0.2), "property": "roof"}] * 2
        ),
        lambda d: d.update(schema_version=True),
    ],
)
def test_malformed_dimensions_references_and_curves_rejected(catalogue, mutation):
    data = catalogue.to_dict()
    mutation(data)
    with pytest.raises(ValueError):
        ParametricCatalogue(data)


def test_derived_overflow_rejected_when_loading(catalogue):
    data = catalogue.to_dict()
    data["curves"][data["categories"]["office"]["curves"]["roof"]]["values"]["SE.01"]["existing"] = 1e-300
    data["categories"]["office"]["anchors"]["roof"] = reference(1e300, "SE.01", "existing")
    with pytest.raises(ValueError):
        ParametricCatalogue(data)


def test_content_identity_immutability_and_cli(catalogue, tmp_path, capsys):
    data = catalogue.to_dict()
    assert content_hash(dict(reversed(list(data.items())))) == catalogue.release_id
    data["categories"]["office"]["anchors"]["roof"] = reference(0.2)
    assert slot(catalogue).properties["roof"].value is None
    with pytest.raises(TypeError):
        catalogue.sources["proxy"]["title"] = "Changed"
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert load_parametric_catalogue(path).release_id != catalogue.release_id
    assert main(["--catalogue", str(path), "--check", "--summary"]) == 0
    assert json.loads(capsys.readouterr().out)["slot_count"] == 1080
    path.write_text("invalid", encoding="utf-8")
    with pytest.raises(ValueError):
        load_parametric_catalogue(path)
