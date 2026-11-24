"""Honeybee export: valid honeybee-energy objects with the catalogue's physics."""

import math
from datetime import date

import pytest

pytest.importorskip("honeybee_energy")

from honeybee.boundarycondition import Ground, Outdoors  # noqa: E402
from honeybee.facetype import Floor, Wall  # noqa: E402
from honeybee.model import Model  # noqa: E402
from honeybee.room import Room  # noqa: E402
from ladybug_geometry.geometry3d import Point3D  # noqa: E402

from epsm_data import Catalogue  # noqa: E402
from epsm_data.honeybee import (  # noqa: E402
    CALENDAR_YEAR,
    iso13370_floor_u,
    orientation,
    swedish_active_dates,
    swedish_holidays,
    to_honeybee,
)


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


def _configurations(catalogue):
    for aid in catalogue.ids():
        states = (None,) if aid.endswith("se07") else ("existing", "standard", "advanced")
        for state in states:
            yield aid, state


def test_every_configuration_exports_and_round_trips(catalogue):
    from honeybee_energy.constructionset import ConstructionSet
    from honeybee_energy.hvac.idealair import IdealAirSystem
    from honeybee_energy.programtype import ProgramType

    for aid, state in _configurations(catalogue):
        export = to_honeybee(catalogue, aid, state=state)
        assert ConstructionSet.from_dict(export.construction_set.to_dict()).identifier
        assert ProgramType.from_dict(export.program_type.to_dict()).identifier
        assert IdealAirSystem.from_dict(export.hvac.to_dict()).economizer_type == "NoEconomizer"
        room = Room.from_box(f"r_{aid}_{state}", 12, 8, 3)
        export.apply_to_room(room)
        Model("m", [room]).check_all(raise_exception=True)


def test_constructions_keep_catalogue_u_values(catalogue):
    export = to_honeybee(catalogue, "mf_se03", state="existing")
    bundle = catalogue.handover("mf_se03", state="existing")
    for role, metrics in bundle["roles"].items():
        if role == "WINDOW":
            continue
        assert math.isclose(1 / export.constructions[role].r_value,
                            1 / (1 / metrics["nominal_u_w_m2k"] - metrics["rsi_m2k_w"] - metrics["rse_m2k_w"]),
                            rel_tol=1e-9)
    assert export.construction_set.wall_set.exterior_construction is export.constructions["EXT_WALL"]
    # Intermediate floor: the ceiling is catalogue order, the floor its reciprocal.
    ceiling = export.construction_set.roof_ceiling_set.interior_construction
    floor = export.construction_set.floor_set.interior_construction
    assert [m.identifier for m in floor.materials] == [m.identifier for m in reversed(ceiling.materials)]


def test_window_shgc_carries_sveby_shading(catalogue):
    assert to_honeybee(catalogue, "mf_se03", state="existing").solar_shading_factor == 1.0
    export = to_honeybee(catalogue, "mf_se03", state="existing", solar_shading_factor=0.5)
    glass = catalogue.handover("mf_se03", state="existing")["honeybee"]["WINDOW"]["materials"][0]
    material = export.constructions["WINDOW"].materials[0]
    assert export.solar_shading_factor == 0.5
    assert math.isclose(material.shgc, glass["shgc"] * 0.5)
    assert material.u_factor == glass["u_factor"]
    assert to_honeybee(catalogue, "school_se03", state="existing").solar_shading_factor == 0.65


def test_residential_program_matches_sveby(catalogue):
    export = to_honeybee(catalogue, "mf_se03", state="existing")
    program = export.program_type
    occupancy = program.people.occupancy_schedule.values(timestep=1)[:24]
    assert sum(occupancy) == 14 and occupancy[17] == 1 and occupancy[7] == 0
    assert math.isclose(program.people.latent_fraction, 30 / 80)
    equipment = program.electric_equipment
    assert math.isclose(equipment.watts_per_area * 8760 / 1000, 21.0)
    assert math.isclose(equipment.watts_per_area * (1 - equipment.lost_fraction), 21000 * 0.7 / 8760)
    assert math.isclose(program.ventilation.flow_per_area, 0.35 / 1000)
    assert program.setpoint.heating_setpoint == 21
    assert export.hvac.cooling_availability is not None  # cooling off
    shw = program.service_hot_water
    assert math.isclose(shw.flow_per_area * 8760 * 4.186 * 50 / 3600, 21.0, rel_tol=1e-9)


def test_measured_use_changes_setpoint(catalogue):
    export = to_honeybee(catalogue, "mf_se01", state="existing", standard="measured")
    assert export.program_type.setpoint.heating_setpoint == 22.2


def test_heat_recovery_follows_template(catalogue):
    assert to_honeybee(catalogue, "mf_se03", state="advanced").hvac.sensible_heat_recovery == 0.8
    exhaust = to_honeybee(catalogue, "mf_se03", state="existing", ventilation="F")
    assert exhaust.hvac.sensible_heat_recovery == 0
    natural = to_honeybee(catalogue, "mf_se01", state="existing", ventilation="S")
    assert natural.hvac.sensible_heat_recovery == 0
    assert math.isclose(natural.program_type.ventilation.flow_per_area, 0.35 / 1000)
    assert natural.program_type.ventilation.air_changes_per_hour == 0


def test_office_calendar_and_annual_electricity(catalogue):
    export = to_honeybee(catalogue, "office_se03", state="existing")
    equipment = export.program_type.electric_equipment
    annual = sum(equipment.schedule.values(timestep=1)) * equipment.watts_per_area / 1000
    assert math.isclose(annual, 50.0, rel_tol=1e-6)
    occupancy = export.program_type.people.occupancy_schedule.values(timestep=1)
    active_days = sum(1 for d in range(365) if max(occupancy[24 * d:24 * d + 24]) > 0)
    assert active_days == 225


def test_swedish_calendar():
    days = swedish_active_dates(CALENDAR_YEAR, 225)
    assert len(days) == 225 and all(d.weekday() < 5 for d in days)
    assert not set(days) & swedish_holidays(CALENDAR_YEAR)
    assert date(2017, 4, 14) in swedish_holidays(2017)  # Good Friday
    assert date(2017, 6, 23) in swedish_holidays(2017)  # Midsummer Eve
    assert not any(d.month == 7 for d in days)


def test_apply_to_rooms_sets_infiltration_windows_and_ground(catalogue):
    export = to_honeybee(catalogue, "mf_se03", state="existing")
    rooms = [Room.from_box(f"s{i}", 30, 12, 3, origin=Point3D(0, 0, 3 * i)) for i in range(3)]
    Room.solve_adjacency(rooms, 0.01)
    export.apply_to_rooms(rooms)
    flow = sum(r.properties.energy.infiltration.flow_per_exterior_area * r.exposed_area for r in rooms)
    assert math.isclose(flow, export.infiltration_l_s_m2 * 3 * 360 / 1000)
    for face in rooms[0].faces:
        if isinstance(face.type, Wall) and isinstance(face.boundary_condition, Outdoors):
            ratio = sum(a.area for a in face.apertures) / face.area
            assert math.isclose(ratio, export.wwr_by_orientation[orientation(face.azimuth)], abs_tol=0.01)
    ground = [f for f in rooms[0].faces if isinstance(f.type, Floor) and isinstance(f.boundary_condition, Ground)]
    construction = ground[0].properties.energy.construction
    assert construction.user_data["exposed_perimeter_m"] == 84
    assert math.isclose(1 / (construction.r_value + 0.17),
                        construction.user_data["iso13370_u_w_m2k"], rel_tol=1e-9)


def test_iso13370_matches_standard_example():
    # Large slab, low insulation: U falls with B'; dt < B' branch.
    u_small = iso13370_floor_u(100, 40, 0.5)
    u_large = iso13370_floor_u(1000, 130, 0.5)
    assert 0 < u_large < u_small < 1
    assert math.isclose(iso13370_floor_u(10, 4, 5.0), 2.0 / (0.457 * 5 + 0.3 + 2.0 * 5.21))


def test_office_thermal_bridges_raise_wall_u(catalogue):
    export = to_honeybee(catalogue, "office_se03", state="existing")
    assert export.thermal_bridge_delta_u_w_m2k
    rooms = [Room.from_box("o", 30, 12, 3)]
    export.apply_to_rooms(rooms)
    wall = next(f for f in rooms[0].faces if isinstance(f.type, Wall))
    assert wall.properties.energy.construction.u_factor > export.constructions["EXT_WALL"].u_factor


def test_orientation():
    assert [orientation(a) for a in (0, 44, 45, 134, 135, 224, 225, 314, 315)] == list("NNEESSWWN")
