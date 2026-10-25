"""Every archetype carries a simple ventilation template and facade WWR assumptions."""

import pytest

from epsm_data import Catalogue

TOPOLOGIES = {"S", "F", "FT", "FTX"}


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


def _configurations(catalogue):
    for aid in catalogue.ids():
        for state in catalogue.renovation_states(aid) or (None,):
            yield aid, state


def test_every_configuration_has_an_airflow_only_ventilation_template(catalogue):
    seen = 0
    for aid, state in _configurations(catalogue):
        template = catalogue.get(aid, state=state).hvac_template
        assert template is not None, (aid, state)
        airflow = template.values["airflow"]
        assert set(template.values) == {"airflow"}
        assert airflow["topology"] in TOPOLOGIES
        if airflow["topology"] == "S":
            assert airflow["mechanical_vent_l_s_m2"] == 0 and airflow["natural_exchange_ach"] > 0
        if airflow["topology"] != "FTX":
            assert airflow.get("sensible_recovery_effectiveness", 0) == 0
        seen += 1
    assert seen == 76


def test_standard_keeps_the_existing_system_and_advanced_installs_ftx(catalogue):
    for aid in catalogue.ids():
        if not catalogue.renovation_states(aid):
            continue
        existing, standard, advanced = (
            catalogue.get(aid, state=state).hvac_template for state in ("existing", "standard", "advanced"))
        assert standard is existing
        assert advanced.values["airflow"]["topology"] == "FTX"
        assert advanced.values["airflow"]["sensible_recovery_effectiveness"] == 0.8


def test_ventilation_assignment_follows_the_period_rule(catalogue):
    topology = {aid: catalogue.get(aid, state="existing" if catalogue.renovation_states(aid) else None)
                .hvac_template.values["airflow"]["topology"] for aid in catalogue.ids()}
    assert topology["sf_se01"] == topology["mf_se01"] == topology["office_se01"] == "S"
    assert topology["mf_se02"] == "F" and topology["office_se02"] == "FT"
    assert all(topology[f"{kind}_se0{era}"] == "FTX" for kind in ("sf", "mf", "office", "school")
               for era in (6, 7))


def test_ventilation_templates_are_listed_with_the_catalogue(catalogue):
    ids = {aid: catalogue.get(aid).hvac_template.template_id for aid in ("sf_se07", "mf_se07")}
    assert set(ids.values()) <= set(catalogue.hvac_templates)
    assert catalogue.get("generic_se03", state="existing").hvac_template is (
        catalogue.get("mf_se03", state="existing").hvac_template)


@pytest.mark.parametrize("aid, default", [
    ("sf_se02", 0.18), ("mf_se04", 0.24), ("office_se05", 0.3), ("school_se01", 0.25),
    ("generic_se02", 0.24),
])
def test_facade_assumptions_give_a_default_and_four_orientations(catalogue, aid, default):
    facade = catalogue.facade_assumptions(aid)
    assert facade["default_wwr"] == default
    ratios = facade["wwr_by_orientation"]
    assert set(ratios) == {"N", "E", "S", "W"}
    assert all(0 < value < 0.95 for value in ratios.values())
    # The four-facade mean equals the default, so either form gives the same glazed area.
    assert sum(ratios.values()) / 4 == pytest.approx(default)
    assert ratios["S"] >= ratios["N"]
    assert facade["basis"] and facade["tier"] in {"tabula", "assumption"}


def test_unknown_archetype_has_no_facade_assumptions(catalogue):
    with pytest.raises(KeyError):
        catalogue.facade_assumptions("hospital_se01")
