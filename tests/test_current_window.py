"""Current adopted window assumption remains explicit and provisional."""


from epsm_data.layered import load_calibrated_archetype
from epsm_data.parametric import load_parametric_catalogue
from epsm_data.release import core_inputs


def test_window_exports_and_provisional_evidence():
    catalogue = load_parametric_catalogue()
    assert catalogue.to_dict()["database_version"] == "current"
    for zone in catalogue.dimensions["zones"]:
        for ventilation in catalogue.dimensions["ventilation"]:
            slot = catalogue.get_slot(f"multi_family:SE.02:{zone}:existing:{ventilation}")
            assert slot.properties["window"].value == 2.2
            assert slot.properties["window"].source == "v1_4_mf_se02_window_diagnostic"
            evidence = slot.properties["window"].evidence
            assert not evidence.get("basis_stale")
            assert evidence["classification"] == "engineering_assumption"
            assert "provisional" in evidence["confidence"]
    bundle = load_calibrated_archetype(archetype_id="mf_se02").to_nominal_dict()
    assert bundle["dataset_release"] == "current"
    assert bundle["core"]["WINDOW"]["u_value_w_m2k"] == 2.2
    assert bundle["core"]["WINDOW"]["solar_heat_gain_coefficient"] == 0.7
    assert core_inputs("mf_se02")["glazing"].u_value_w_m2k == 2.2
    assert len(bundle["core"]) >= 7

