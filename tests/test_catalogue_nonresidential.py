"""Authored nonresidential roles preserve physical boundaries and floor sides."""

from copy import deepcopy

import pytest

from epsm_data import Catalogue, ConstructionSet, Element, export_nominal_constructions
from epsm_data.domain import BuildingElement as Role


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture(scope="module")
def payload(catalogue):
    return catalogue.resolved_dict()


def configurations():
    return [
        (f"{category}_se{era:02d}", state)
        for category in ("office", "school")
        for era in range(1, 8)
        for state in ((None,) if era == 7 else ("existing", "standard", "advanced"))
    ]


def configuration(payload, aid, state):
    return payload["archetypes"][aid]["states"][state or "default"]


@pytest.mark.parametrize("aid", ["office_se01", "school_se01"])
@pytest.mark.parametrize("state", ["existing", "standard", "advanced"])
def test_old_basement_ceiling_and_soil_slab_are_distinct(catalogue, payload, aid, state):
    archetype = catalogue.get(aid, state=state)
    config = configuration(payload, aid, state)
    assert config["foundation_context"] == "unheated_basement"
    roles = archetype.construction_set.elements
    assert roles[Role.GROUND_FLOOR] is not roles[Role.BASEMENT_FLOOR]
    bundle = export_nominal_constructions(archetype, metadata=catalogue.nominal_metadata(aid, state=state))
    soil = bundle["core"]["BASEMENT_FLOOR"]["layers"]
    ceiling = bundle["core"]["GROUND_FLOOR"]["layers"]
    assert len(soil) == 1
    assert soil[0]["thickness_m"] == 0.1
    assert "Concrete" in roles[Role.BASEMENT_FLOOR].components[0].layers[0].layer.name
    assert "Shavings" in roles[Role.GROUND_FLOOR].components[0].layers[2].layer.name
    assert ceiling[-1]["thickness_m"] == 0.025
    assert config["boundary_details"]["BASEMENT_FLOOR"]["physical_boundary"] == "soil"
    assert config["boundary_details"]["GROUND_FLOOR"]["physical_boundary"] == "conditioned_to_unconditioned"
    # This is the raw material slab, before the project geometry/soil solver.
    assert bundle["roles"]["BASEMENT_FLOOR"]["nominal_u_w_m2k"] > 4
    assert bundle["roles"]["BASEMENT_FLOOR"]["mass_kg_m2"] == pytest.approx(
        0.1 * soil[0]["material"]["density_kg_m3"]
    )


@pytest.mark.parametrize("aid,state", configurations())
def test_top_roles_distinguish_attic_ceiling_and_weather_shell(catalogue, payload, aid, state):
    config = configuration(payload, aid, state)
    roles = catalogue.get(aid, state=state).construction_set.elements
    if config["roof_topology"] == "cold_attic":
        assert Role.TOP_FLOOR in roles and Role.ROOF in roles
        assert roles[Role.TOP_FLOOR] is not roles[Role.ROOF]
        assert roles[Role.ROOF] is catalogue.elements[config["weather_shell_element_id"]]
        assert config["boundary_details"]["TOP_FLOOR"]["physical_role"] == "attic_ceiling"
        assert config["boundary_details"]["ROOF"]["physical_boundary"] == "unconditioned_to_outdoors"
    else:
        assert Role.ROOF in roles
        assert Role.TOP_FLOOR not in roles
        assert config["boundary_details"]["ROOF"]["physical_role"] == "compact_roof"


@pytest.mark.parametrize("aid,state", configurations())
def test_floor_normalization_preserves_source_resistance_mass_and_capacity(catalogue, payload, aid, state):
    archetype = catalogue.get(aid, state=state)
    config = configuration(payload, aid, state)
    eid = payload["construction_sets"][config["construction_set_id"]]["elements"]["INTERMEDIATE_FLOOR"]
    element = payload["elements"][eid]
    assert element["side_convention"] == "bottom_to_top"
    assert config["boundary_details"]["INTERMEDIATE_FLOOR"]["layer_order"] == "lower_room_to_upper_room"
    source = element["source_sequence"]
    assert source["side_convention"] == "top_to_bottom"
    original = Element(
        name="Retained authored source order", archetype="", age=None,
        components=tuple(catalogue.components[cid] for cid in source["components"]),
        application=Role.INTERMEDIATE_FLOOR,
    )
    original_archetype = archetype.with_changes(construction_set=ConstructionSet(
        elements={Role.INTERMEDIATE_FLOOR: original}
    ))
    before = export_nominal_constructions(original_archetype)
    after = export_nominal_constructions(archetype)
    assert after["core"]["INTERMEDIATE_FLOOR"]["layers"] == list(
        reversed(before["core"]["INTERMEDIATE_FLOOR"]["layers"])
    )
    for metric in ("thickness_m", "resistance_m2k_w", "mass_kg_m2", "heat_capacity_j_m2k", "nominal_u_w_m2k"):
        assert after["roles"]["INTERMEDIATE_FLOOR"][metric] == pytest.approx(
            before["roles"]["INTERMEDIATE_FLOOR"][metric]
        )
    # The upper room now receives its thin finish, and the reciprocal ceiling
    # receives its acoustic/plaster soffit. Core integration verifies the faces.
    assert after["core"]["INTERMEDIATE_FLOOR"]["layers"][-1]["thickness_m"] == 0.0025


def test_residential_authored_order_is_not_implicitly_normalized(catalogue, payload):
    config = configuration(payload, "sf_se02", "existing")
    eid = payload["construction_sets"][config["construction_set_id"]]["elements"]["INTERMEDIATE_FLOOR"]
    assert payload["elements"][eid]["side_convention"] == "top_to_bottom"
    assert config["boundary_details"]["INTERMEDIATE_FLOOR"]["layer_order"] == "upper_room_to_lower_room"
    before = deepcopy(catalogue.get("sf_se02").construction_set.elements[Role.INTERMEDIATE_FLOOR])
    export_nominal_constructions(catalogue.get("sf_se02"))
    assert catalogue.get("sf_se02").construction_set.elements[Role.INTERMEDIATE_FLOOR] == before
