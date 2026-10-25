"""Unknown building type is an explicit selection of the existing MF donor."""

import pytest

from epsm_data import (
    ArchetypeKey,
    Catalogue,
    archetype_from_dict,
    archetype_to_dict,
    export_nominal_constructions,
)
from epsm_data.classification import CATEGORIES, ERAS, ZONES, states_for_era

LABEL = "Unknown building type — multifamily assumption"
CASES = [
    (era, start, state, zone)
    for era, (start, _) in ERAS.items()
    for state in states_for_era(era)
    for zone in ZONES
]


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.mark.parametrize("era,year,state,zone", CASES)
def test_generic_shares_exact_mf_fabric_and_operation(catalogue, era, year, state, zone):
    generic = catalogue.for_year("generic", year, state=state)
    donor = catalogue.for_year("multi_family", year, state=state)
    slot = catalogue.get_slot(ArchetypeKey("generic", era, zone, state))
    alias = "generic_se" + era.removeprefix("SE.")
    assert generic.archetype_id == alias
    assert generic.building_typology == "generic"
    assert generic.display_name == LABEL
    assert LABEL in generic.notes
    assert donor.archetype_id in " ".join(generic.notes)
    assert generic.construction_set is donor.construction_set
    assert generic.operating_profile is donor.operating_profile
    assert generic.construction_year == donor.construction_year
    assert generic.envelope_performance == donor.envelope_performance
    assert catalogue.get(alias, state=state).construction_set is donor.construction_set
    assert slot.key.category == "generic"
    assert slot.archetype_id == donor.archetype_id
    assert slot.construction_set_id == catalogue.get_slot(
        ArchetypeKey("multi_family", era, zone, state)
    ).construction_set_id
    selection = {
        "requested_category": "generic",
        "donor_category": "multi_family",
        "donor_archetype_id": donor.archetype_id,
        "assumption_label": LABEL,
    }
    assert slot.to_dict()["selection"] == selection
    metadata = catalogue.nominal_metadata(alias, state=state)
    assert metadata["category"] == "generic"
    assert metadata["selection"] == selection
    assert catalogue.completeness(alias, state=state) == catalogue.completeness(
        donor.archetype_id, state=state
    )
    assert catalogue.renovation_states(alias) == catalogue.renovation_states(donor.archetype_id)


def test_virtual_selection_does_not_add_definitions_or_default_slots(catalogue):
    original = catalogue.to_dict()
    assert "generic" not in CATEGORIES
    assert "generic" not in catalogue.dimensions["categories"]
    assert len(catalogue.ids()) == 28
    assert len(catalogue.search()) == 228
    assert catalogue.summary()["configuration_count"] == 76
    assert catalogue.ids(category="generic") == catalogue.ids(category="multi_family")
    assert len(catalogue.search(category="generic")) == 57
    for slot in catalogue.search(category="generic"):
        assert slot.key.category == "generic"
        assert slot.archetype_id in catalogue.ids(category="multi_family")
        assert catalogue.get_slot(slot.slot_id) == slot
    assert catalogue.to_dict() == original


def test_generic_identity_and_assumption_survive_exchange(catalogue):
    selected = catalogue.get("generic_se02", state="advanced")
    restored = archetype_from_dict(archetype_to_dict(selected))
    assert restored.archetype_id == "generic_se02"
    assert restored.display_name == LABEL
    assert restored.building_typology == "generic"
    assert restored.notes == selected.notes
    assert restored.operating_profile == selected.operating_profile
    metadata = catalogue.nominal_metadata("generic_se02", state="advanced")
    bundle = export_nominal_constructions(restored, metadata=metadata)
    assert bundle["archetype_id"] == "generic_se02"
    assert bundle["category"] == "generic"
    assert bundle["selection"] == metadata["selection"]


@pytest.mark.parametrize("state", ["existing", "standard", "advanced"])
def test_generic_se07_does_not_create_renovation_states(catalogue, state):
    with pytest.raises(ValueError, match="SE.07"):
        catalogue.get("generic_se07", state=state)
    with pytest.raises(ValueError, match="SE.07"):
        ArchetypeKey("generic", "SE.07", "SE.Zone3", state)


@pytest.mark.parametrize("alias", ["generic_se00", "generic_se08", "generic_se1", "generic"])
def test_unknown_virtual_aliases_are_not_guessed(catalogue, alias):
    with pytest.raises(KeyError):
        catalogue.get(alias)
