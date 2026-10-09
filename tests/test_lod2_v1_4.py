"""v1.4 adopts only the explicitly authorized MF SE.02 existing-window hypothesis.

References: evidence/lod2_v1_4/window-diagnostic.json; the frozen v1.3 catalogue.
The retrospective window-only benefit is not the joint wall/roof/flow benefit.
"""

import json
from pathlib import Path

from epsm_data.layered import load_calibrated_archetype
from epsm_data.parametric import ParametricCatalogue, load_parametric_catalogue
from epsm_data.release import core_inputs


def test_window_exports_and_provisional_evidence():
    catalogue = load_parametric_catalogue()
    assert catalogue.to_dict()["catalogue_release"] == "epsm-lod2-v1.4"
    assert catalogue.to_dict()["database_version"] == "1.5.0"
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
    assert bundle["dataset_release"] == "epsm-lod2-v1.4"
    assert bundle["core"]["WINDOW"]["u_value_w_m2k"] == 2.2
    assert bundle["core"]["WINDOW"]["solar_heat_gain_coefficient"] == 0.7
    assert core_inputs("mf_se02")["glazing"].u_value_w_m2k == 2.2
    assert len(bundle["core"]) >= 7


def test_only_authorized_thermal_cell_changes():
    prior = Path(__file__).resolve().parents[1] / "evidence/lod2_v1_4/prior/catalogue.json"
    old = ParametricCatalogue(json.loads(prior.read_text()))
    new = load_parametric_catalogue()
    changed = []
    for category in new.dimensions["categories"]:
        for era in new.dimensions["eras"]:
            for state in new.dimensions["states"]:
                a = old.resolve_construction(category, era, state)
                b = new.resolve_construction(category, era, state)
                for role in a.properties:
                    if a.properties[role].value != b.properties[role].value:
                        changed.append((category, era, state, role))
    assert changed == [("multi_family", "SE.02", "existing", "window")]
