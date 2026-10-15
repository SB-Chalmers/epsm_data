"""Nominal handovers use the authored model and explicit portable source context."""

from copy import deepcopy

import pytest

from epsm_data import (
    Archetype,
    Catalogue,
    export_nominal_constructions,
    validate_nominal_handover,
)
from epsm_data.layered import _load_calibrated_archetype as load_calibrated_archetype


@pytest.mark.parametrize("identifier,state", [
    (identifier, state)
    for identifier in ("sf_se02", "mf_se02", "office_se05", "school_se05")
    for state in ("existing", "standard", "advanced")
] + [("mf_se07", None)])
def test_shared_model_nominal_bundle_preserves_complete_old_handover(identifier, state):
    catalogue = Catalogue.load()
    old = load_calibrated_archetype(archetype_id=identifier, renovation_state=state,
        detailed=catalogue.detailed, catalogue=catalogue.parametric).to_nominal_dict()
    archetype = catalogue.get(identifier, state=state)
    metadata = catalogue.nominal_metadata(identifier, state=state)
    before = deepcopy(metadata)
    actual = export_nominal_constructions(archetype, metadata=metadata)
    assert actual == old
    assert metadata == before
    assert metadata["assessment_status"] == "not_assessed"
    assert validate_nominal_handover(actual) == {"honeybee": True, "core": True}


def test_nominal_context_does_not_request_calibration_or_target_acceptance(monkeypatch):
    import epsm_data.layered as layered

    catalogue = Catalogue.load()
    catalogue.parametric = catalogue.parametric.with_property(
        "multi_family", "SE.02", "existing", "roof",
        {"value": .9, "source": "proxy", "note": "Deliberate target mismatch"})
    monkeypatch.setattr(layered, "_load_calibrated_archetype",
                        lambda **kwargs: pytest.fail("Calibration requested"))
    archetype = catalogue.get("mf_se02")
    metadata = catalogue.nominal_metadata("mf_se02")
    actual = export_nominal_constructions(archetype, metadata=metadata)
    assert actual["core"]["TOP_FLOOR"]["layers"]
    assert not actual["readiness"]["ground_validation"]
    assert not actual["readiness"]["simulation"]


def test_source_draft_keeps_its_actual_roof_roles_and_evidence():
    catalogue = Catalogue.load()
    archetype = catalogue.get("school_fridhem")
    actual = export_nominal_constructions(archetype,
        metadata=catalogue.nominal_metadata("school_fridhem"))
    assert actual["role_profile"] == "school_source_draft"
    assert "ROOF" in actual["core"] and "TOP_FLOOR" not in actual["core"]
    assert actual["record_annotations"]
    assert actual["sources"]
    assert not actual["readiness"]["simulation"]


def test_explicit_metadata_is_required_and_invalid_inputs_do_not_guess_context():
    archetype = Archetype("custom", "Incomplete")
    with pytest.raises(TypeError, match="metadata"):
        export_nominal_constructions(archetype)
    with pytest.raises(ValueError, match="metadata"):
        export_nominal_constructions(archetype, metadata={})
    catalogue = Catalogue.load()
    metadata = catalogue.nominal_metadata("mf_se02")
    with pytest.raises(ValueError, match="construction"):
        export_nominal_constructions(archetype, metadata=metadata)


def test_nominal_context_is_detached_and_loaded_metadata_access_has_no_io(monkeypatch):
    import epsm_data.detailed as detailed_module
    import epsm_data.profiles as profiles

    catalogue = Catalogue.load()
    monkeypatch.setattr(detailed_module, "files", lambda *args: pytest.fail("Registry lookup"))
    monkeypatch.setattr(profiles, "files", lambda *args: pytest.fail("Profile lookup"))
    metadata = catalogue.nominal_metadata("mf_se02")
    first = next(iter(metadata["material_references"]))
    metadata["material_references"][first]["json_id"] = "modified"
    assert catalogue.nominal_metadata("mf_se02")["material_references"][first]["json_id"] != "modified"
