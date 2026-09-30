"""Catalogue behavior and portable parameter/cost metadata."""

import json

import pytest

from epsm_data import Cost, ParameterDefinition, RenovationCatalogue, RenovationMeasure


def test_catalogue_roundtrip_and_lookup():
    measure = RenovationMeasure(
        "windows",
        "envelope",
        "Windows",
        "Example",
        "window",
        parameters=(ParameterDefinition("u", "number", "Target U", "W/(m2 K)"),),
        cost=Cost(50, "SEK", "m2_window"),
        service_life_years=30,
        source_references=("example:synthetic-cost",),
    )
    restored = RenovationMeasure.from_dict(json.loads(json.dumps(measure.to_dict())))
    assert restored == measure
    catalogue = RenovationCatalogue([restored])
    assert catalogue.filter(category="envelope") == (measure,)
    assert catalogue.filter(category="systems") == ()
    assert catalogue.get("windows") == measure
    with pytest.raises(KeyError):
        catalogue.get("missing")
    with pytest.raises(ValueError):
        catalogue.add(measure)


def test_optional_metadata_stays_unknown():
    measure = RenovationMeasure("draft", "systems", "Draft", "Unsourced example", "heating")
    assert measure.cost is None
    assert measure.service_life_years is None
    assert measure.source_references == ()


@pytest.mark.parametrize(
    "amount,currency,unit",
    [
        (-1, "SEK", "m2"),
        (float("nan"), "SEK", "m2"),
        (20, "", "m2"),
        (20, "SEK", ""),
    ],
)
def test_invalid_cost(amount, currency, unit):
    with pytest.raises(ValueError):
        Cost(amount, currency, unit)


def test_invalid_parameters():
    with pytest.raises(ValueError):
        ParameterDefinition("x", "float", "Unportable type")
    parameter = ParameterDefinition("x", "number", "Example")
    with pytest.raises(ValueError):
        RenovationMeasure(
            "draft",
            "systems",
            "Draft",
            "Example",
            "heating",
            parameters=(parameter, parameter),
        )
