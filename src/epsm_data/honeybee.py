"""Export a catalogue archetype as honeybee-energy objects for a user's own rooms.

``to_honeybee`` returns a :class:`HoneybeeArchetype` holding a ConstructionSet, a
ProgramType and an IdealAirSystem built from one catalogue configuration, plus the
facade, airtightness, shading and ground inputs that need room geometry.
:meth:`HoneybeeArchetype.apply_to_room` assigns everything to a Honeybee Room.

The mapping follows epsm_core where Honeybee can express the same thing:

* Constructions come unchanged from ``Catalogue.handover`` (layers outside to inside).
* Sveby (or measured-use) values become schedules and loads. Residential occupancy is
  17:00-07:00 every day; office and school loads follow an explicit list of active
  dates (Sveby's 225 and 220 days). Without one, :func:`swedish_active_dates` gives a
  labelled EPSM calendar: weekdays minus Swedish public holidays, July and the
  Christmas break.
* Household and business electricity keep the full electrical input, with the share
  that does not become heat as ``lost_fraction`` (Sveby: 70 % becomes heat).
* Ventilation is outdoor air through the ideal-air system, which carries the template's
  sensible heat recovery. No economiser; cooling off unless the profile enables it.
* Infiltration is a constant rate per m2 Atemp (TABULA ACH is converted with the
  catalogue reference height, as EPSM does) and is spread over the room's exposed area.
* Sveby solar shading becomes a reduced window SHGC. epsm_core instead multiplies
  incident solar on the window. With EnergyPlus's simple glazing, halving SHGC cuts
  transmitted solar to about 38 % but the net window gain is close to a 0.5 multiplier.
* Ground floors get an ISO 13370 equivalent soil layer and need the ground temperature
  from :func:`ground_temperature_idf`. epsm_core uses Kiva, which Honeybee lacks, so
  ground losses will differ somewhat.
* Ideal air reports delivered heat only. Apply ``heating_cop`` afterwards.

Requires the optional dependency: ``pip install "epsm_data[honeybee]"``.
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from .profiles import select_operating_profile
from .templates import heating_delivery_template

#: Energy to heat one litre of water from 10 to 60 C, in kWh (4.186 kJ/kg K x 50 K).
_KWH_PER_LITRE = 4.186 * 50 / 3600
#: ISO 13370 default soil conductivity (clay or silt), W/(m K).
SOIL_CONDUCTIVITY_W_MK = 2.0
_RSI_FLOOR, _RSE = 0.17, 0.04
_RESIDENTIAL = ("single_family", "multi_family")
#: Honeybee writes every non-leap run period as 2017, which starts on a Sunday, so
#: dated schedules are built on the 2017 calendar.
CALENDAR_YEAR = 2017


def _require_honeybee():
    try:
        import honeybee_energy  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised without the extra
        raise ImportError(
            'Honeybee export needs honeybee-energy: pip install "epsm_data[honeybee]"'
        ) from exc


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def _easter(year):
    """Gregorian Easter Sunday (anonymous algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 19 * l) // 433
    month = (h + l - 7 * m + 90) // 25
    return date(year, month, (h + l - 7 * m + 33 * month + 19) % 32)


def swedish_holidays(year):
    """Swedish public holidays and the de facto days off (eves) in ``year``."""
    easter = _easter(year)
    midsummer_eve = next(date(year, 6, d) for d in range(19, 26) if date(year, 6, d).weekday() == 4)
    return {
        date(year, 1, 1), date(year, 1, 6), easter - timedelta(days=2), easter + timedelta(days=1),
        date(year, 5, 1), easter + timedelta(days=39), date(year, 6, 6), midsummer_eve,
        date(year, 12, 24), date(year, 12, 25), date(year, 12, 26), date(year, 12, 31),
    }


def swedish_active_dates(year, n_days):
    """``n_days`` working days in ``year``: an EPSM calendar assumption, not a Sveby rule.

    Starts from weekdays that are not Swedish holidays, then removes, in order, July,
    the Christmas and New Year break, the February sports week (week 8), the autumn
    week (week 44) and the week after Easter, until ``n_days`` remain.
    """
    days = [date(year, 1, 1) + timedelta(days=i) for i in range(366 if calendar.isleap(year) else 365)]
    holidays = swedish_holidays(year)
    active = [d for d in days if d.weekday() < 5 and d not in holidays]
    if len(active) < n_days:
        raise ValueError(f"{year} has only {len(active)} working days, fewer than {n_days}")
    easter = _easter(year)
    order = (
        [d for d in active if d.month == 7]
        + [d for d in active if (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 6)]
        + [d for d in active if d.isocalendar()[1] == 8]
        + [d for d in active if d.isocalendar()[1] == 44]
        + [d for d in active if easter + timedelta(days=1) < d <= easter + timedelta(days=7)]
    )
    removed = set()
    for d in order:
        if len(active) - len(removed) == n_days:
            break
        removed.add(d)
    result = [d for d in active if d not in removed]
    if len(result) != n_days:
        raise ValueError(f"Cannot reach {n_days} active days in {year}")
    return tuple(result)


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------

def _hours(start, hours, on=1.0, off=0.0):
    return [on if (h - start) % 24 < hours else off for h in range(24)]


def _schedule_day(identifier, hourly):
    from honeybee_energy.schedule.day import ScheduleDay
    from ladybug.dt import Time

    values, times = [], []
    for hour, value in enumerate(hourly):
        if not values or value != values[-1]:
            values.append(value)
            times.append(Time(hour, 0))
    return ScheduleDay(identifier, values, times)


def _constant(identifier, value, limit):
    from honeybee_energy.schedule.ruleset import ScheduleRuleset

    return ScheduleRuleset.from_constant_value(identifier, value, limit)


def _daily(identifier, hourly, limit):
    from honeybee_energy.schedule.ruleset import ScheduleRuleset

    return ScheduleRuleset(identifier, _schedule_day(identifier + "_day", hourly),
                           schedule_type_limit=limit)


def _calendar(identifier, active_hourly, idle_hourly, active_dates, year, limit):
    """Ruleset that is ``active_hourly`` on the given weekdays, ``idle_hourly`` otherwise.

    Active weekdays become Monday-Friday rules over date ranges with no idle weekday
    inside, so the run period must start on the weekday of 1 January ``year``
    (see :meth:`HoneybeeArchetype.simulation_parameter`).
    """
    from honeybee_energy.schedule.rule import ScheduleRule
    from honeybee_energy.schedule.ruleset import ScheduleRuleset
    from ladybug.dt import Date

    active_set = set(active_dates)
    if any(d.year != year or d.weekday() > 4 for d in active_set):
        raise ValueError("Active dates must be weekdays in the calendar year")
    leap = calendar.isleap(year)
    on_day = _schedule_day(identifier + "_active", active_hourly)
    idle_day = _schedule_day(identifier + "_idle", idle_hourly)
    ranges, start, last = [], None, None
    day = date(year, 1, 1)
    while day.year == year:
        if day.weekday() < 5:
            if day in active_set:
                start = start or day
                last = day
            elif start is not None:
                ranges.append((start, last))
                start = None
        day += timedelta(days=1)
    if start is not None:
        ranges.append((start, last))
    rules = [
        ScheduleRule(on_day, apply_monday=True, apply_tuesday=True, apply_wednesday=True,
                     apply_thursday=True, apply_friday=True,
                     start_date=Date(a.month, a.day, leap), end_date=Date(b.month, b.day, leap))
        for a, b in ranges
    ]
    return ScheduleRuleset(identifier, idle_day, rules, limit, holiday_schedule=idle_day)


def _annual_sum(active_hourly, idle_hourly, active_days, year):
    days = 366 if calendar.isleap(year) else 365
    return active_days * sum(active_hourly) + (days - active_days) * sum(idle_hourly)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HoneybeeArchetype:
    """Honeybee objects and room-level inputs for one catalogue configuration.

    Attributes
    ----------
    construction_set, program_type, hvac
        honeybee-energy ConstructionSet, ProgramType and IdealAirSystem.
    constructions : dict
        Role name to the Honeybee construction used (the window already shaded).
    wwr_by_orientation : dict
        Window-to-wall ratio for walls facing N, E, S and W.
    infiltration_l_s_m2 : float or None
        Constant infiltration per m2 Atemp, applied by ``apply_to_room``.
    self_draught_total_ach : float or None
        Measured total air change (infiltration included) for self-draught buildings
        under ``standard="measured"``; ``apply_to_room`` sets the natural part.
    thermal_bridge_delta_u_w_m2k : float or None
        TABULA surcharge on the envelope area, applied to walls and top by
        ``apply_to_room``.
    heating_cop : float
        Seasonal COP for converting ideal heating to purchased heat-pump electricity.
    """

    archetype_id: str
    category: str
    era: str
    state: str | None
    ventilation_template_id: str
    construction_set: object
    program_type: object
    hvac: object
    constructions: dict
    wwr_by_orientation: dict
    solar_shading_factor: float
    infiltration_l_s_m2: float | None
    self_draught_total_ach: float | None
    thermal_bridge_delta_u_w_m2k: float | None
    heating_cop: float
    calendar_year: int
    notes: tuple = field(default_factory=tuple)

    def simulation_parameter(self, epw_path=None, **kwargs):
        """A SimulationParameter whose run period starts on 1 January's real weekday.

        With ``epw_path``, approximate winter (99.6 %) and summer (0.4 %) design days
        from the weather file are added, as EnergyPlus zone sizing needs them.
        """
        from honeybee_energy.simulation.parameter import SimulationParameter
        from honeybee_energy.simulation.runperiod import RunPeriod

        weekday = date(self.calendar_year, 1, 1).strftime("%A")
        parameter = SimulationParameter(run_period=RunPeriod(start_day_of_week=weekday), **kwargs)
        if epw_path is not None:
            from ladybug.epw import EPW

            epw = EPW(epw_path)
            for kind in ("WinterDesignDay", "SummerDesignDay"):
                parameter.sizing_parameter.add_design_day(epw.approximate_design_day(kind))
        return parameter

    def apply_to_room(self, room, *, atemp_m2=None, exposed_perimeter_m=None, add_windows=True):
        """Assign the archetype to one Honeybee Room, in place, and return it.

        Same as ``apply_to_rooms([room], ...)[0]``; use ``apply_to_rooms`` for a
        building of several rooms so ground and thermal bridges are sized once.
        """
        return self.apply_to_rooms([room], atemp_m2=atemp_m2, exposed_perimeter_m=exposed_perimeter_m,
                                   add_windows=add_windows)[0]

    def apply_to_rooms(self, rooms, *, atemp_m2=None, exposed_perimeter_m=None, add_windows=True):
        """Assign the archetype to the Rooms of one building, in place, and return them.

        Parameters
        ----------
        rooms : list of honeybee.room.Room
            Geometry in metres with boundary conditions already set (for example
            after ``Room.solve_adjacency``).
        atemp_m2 : float, optional
            Heated floor area of the building (default: the rooms' floor area). It is
            shared out by floor area and sets the infiltration flow.
        exposed_perimeter_m : float, optional
            Exposed perimeter of the ground floor for ISO 13370 (default: the bottom
            edges of outdoor and ground walls standing on ground-contact floors).
        add_windows : bool
            Add windows at the catalogue WWR on outdoor walls that have none.
        """
        from honeybee.boundarycondition import Ground, Outdoors
        from honeybee.facetype import Floor, RoofCeiling, Wall

        rooms = list(rooms)
        floor_area = sum(r.floor_area for r in rooms)
        atemp = floor_area if atemp_m2 is None else atemp_m2
        if atemp <= 0 or floor_area <= 0:
            raise ValueError("Rooms need a positive floor area")
        ground_floors, perimeter = [], 0.0
        for room in rooms:
            energy = room.properties.energy
            energy.construction_set = self.construction_set
            energy.program_type = self.program_type
            energy.hvac = self.hvac
            if add_windows:
                for face in room.faces:
                    if (isinstance(face.type, Wall) and isinstance(face.boundary_condition, Outdoors)
                            and not face.apertures):
                        ratio = self.wwr_by_orientation[orientation(face.azimuth)]
                        if ratio > 0:
                            face.apertures_by_ratio(ratio, tolerance=0.01)
            share = atemp * room.floor_area / floor_area
            infiltration_m3_s = 0.0
            if self.infiltration_l_s_m2 is not None:
                infiltration_m3_s = self.infiltration_l_s_m2 * share / 1000
                energy.absolute_infiltration(infiltration_m3_s)
            if self.self_draught_total_ach is not None and room.volume > 0:
                natural = max(self.self_draught_total_ach - infiltration_m3_s * 3600 / room.volume, 0.05)
                ventilation = energy.ventilation.duplicate()
                ventilation.identifier = f"{ventilation.identifier}_{room.identifier}"[:100]
                ventilation.air_changes_per_hour = natural
                energy.ventilation = ventilation
            floors = [f for f in room.faces
                      if isinstance(f.type, Floor) and isinstance(f.boundary_condition, Ground)]
            if floors:
                ground_floors += floors
                z0 = min(f.geometry.min.z for f in floors)
                for wall in room.faces:
                    if isinstance(wall.type, Wall) and isinstance(wall.boundary_condition, (Outdoors, Ground)):
                        perimeter += sum(seg.length for seg in wall.geometry.boundary_segments
                                         if abs(seg.p1.z - z0) < 0.01 and abs(seg.p2.z - z0) < 0.01)
        if ground_floors and "GROUND_FLOOR" in self.constructions:
            area = sum(f.area for f in ground_floors)
            if exposed_perimeter_m is not None:
                perimeter = exposed_perimeter_m
            construction = ground_construction(
                self.constructions["GROUND_FLOOR"], area, perimeter,
                wall_thickness_m=_thickness(self.constructions.get("EXT_WALL")))
            for face in ground_floors:
                face.properties.energy.construction = construction
        if self.thermal_bridge_delta_u_w_m2k:
            self._apply_bridges(rooms, Outdoors, Ground, Wall, RoofCeiling)
        return rooms

    def _apply_bridges(self, rooms, Outdoors, Ground, Wall, RoofCeiling):
        """Spread the TABULA surcharge on the whole envelope over walls and roofs."""
        envelope = conductance = 0.0
        bridged = []
        for face in (f for room in rooms for f in room.faces):
            if not isinstance(face.boundary_condition, (Outdoors, Ground)):
                continue
            envelope += face.area
            if isinstance(face.boundary_condition, Outdoors) and isinstance(face.type, (Wall, RoofCeiling)):
                conductance += face.properties.energy.construction.u_factor * face.punched_geometry.area
                bridged.append(face)
        if not conductance:
            return
        fraction = self.thermal_bridge_delta_u_w_m2k * envelope / conductance
        cache = {}
        for face in bridged:
            base = face.properties.energy.construction
            if base.identifier not in cache:
                cache[base.identifier] = bridged_construction(base, fraction)
            face.properties.energy.construction = cache[base.identifier]


def orientation(azimuth):
    """N, E, S or W for an outward normal azimuth in degrees clockwise from north."""
    azimuth %= 360
    if azimuth >= 315 or azimuth < 45:
        return "N"
    if azimuth < 135:
        return "E"
    if azimuth < 225:
        return "S"
    return "W"


def _thickness(construction):
    return sum(getattr(m, "thickness", 0.0) for m in construction.materials) if construction else 0.3


def iso13370_floor_u(area_m2, exposed_perimeter_m, floor_r_m2k_w, *, wall_thickness_m=0.3,
                     soil_conductivity_w_mk=SOIL_CONDUCTIVITY_W_MK):
    """ISO 13370 slab-on-ground U-value, W/(m2 K), with surface films."""
    if area_m2 <= 0 or exposed_perimeter_m <= 0:
        raise ValueError("ISO 13370 needs a positive floor area and exposed perimeter")
    b = area_m2 / (0.5 * exposed_perimeter_m)
    dt = wall_thickness_m + soil_conductivity_w_mk * (_RSI_FLOOR + floor_r_m2k_w + _RSE)
    if dt < b:
        return 2 * soil_conductivity_w_mk / (math.pi * b + dt) * math.log(math.pi * b / dt + 1)
    return soil_conductivity_w_mk / (0.457 * b + dt)


def ground_construction(floor, area_m2, exposed_perimeter_m, *, wall_thickness_m=0.3):
    """``floor`` plus a no-mass soil layer giving the ISO 13370 U-value.

    EnergyPlus applies the ground temperature directly to the outer face, so the soil
    layer carries the ISO resistance beyond the floor layers and the inside film.
    """
    from honeybee_energy.construction.opaque import OpaqueConstruction
    from honeybee_energy.material.opaque import EnergyMaterialNoMass

    u = iso13370_floor_u(area_m2, exposed_perimeter_m, floor.r_value, wall_thickness_m=wall_thickness_m)
    soil_r = max(1 / u - _RSI_FLOOR - floor.r_value, 0.001)
    tag = f"{area_m2:.1f}_{exposed_perimeter_m:.1f}"
    soil = EnergyMaterialNoMass(f"iso13370_soil_{soil_r:.3f}", soil_r, "MediumRough")
    construction = OpaqueConstruction(f"{floor.identifier}_iso13370_{tag}"[:100],
                                      [soil] + list(floor.materials))
    construction.user_data = {"iso13370_u_w_m2k": u, "soil_resistance_m2k_w": soil_r,
                              "ground_floor_area_m2": area_m2,
                              "exposed_perimeter_m": exposed_perimeter_m}
    return construction


def bridged_construction(construction, uplift_fraction):
    """``construction`` with its U-factor raised by ``uplift_fraction``.

    The layer with the largest resistance loses the extra conductance, keeping its
    thickness and mass.
    """
    from honeybee_energy.construction.opaque import OpaqueConstruction

    materials = [m.duplicate() for m in construction.materials]
    target_r = 1 / (construction.u_factor * (1 + uplift_fraction))
    delta = 1 / construction.u_factor - target_r
    layer = max(range(len(materials)), key=lambda i: materials[i].r_value)
    material = materials[layer]
    if delta >= material.r_value:
        raise ValueError(f"Thermal bridge uplift too large for {construction.identifier}")
    material.identifier = f"{material.identifier}_bridged_{uplift_fraction:.4f}"[:100]
    material.conductivity = material.thickness / (material.r_value - delta)
    bridged = OpaqueConstruction(f"{construction.identifier}_bridged_{uplift_fraction:.4f}"[:100],
                                 materials)
    bridged.user_data = {"thermal_bridge_uplift_fraction": uplift_fraction}
    return bridged


def ground_temperature_idf(epw_path):
    """``Site:GroundTemperature:BuildingSurface`` at the EPW annual mean air temperature.

    ISO 13370's steady-state method refers ground losses to the annual mean outdoor
    temperature. Pass the string as ``additional_string`` when simulating; without it
    EnergyPlus uses its 18 C default under every ground floor.
    """
    from ladybug.epw import EPW

    mean = sum(EPW(epw_path).dry_bulb_temperature.values) / 8760
    return "Site:GroundTemperature:BuildingSurface,\n  " + ",\n  ".join([f"{mean:.2f}"] * 11) + \
        f",\n  {mean:.2f};"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _hb_construction(record):
    from honeybee_energy.construction.opaque import OpaqueConstruction
    from honeybee_energy.construction.window import WindowConstruction

    cls = WindowConstruction if record["type"] == "WindowConstruction" else OpaqueConstruction
    return cls.from_dict(record)


def _window(record, factor):
    from honeybee_energy.construction.window import WindowConstruction
    from honeybee_energy.material.glazing import EnergyWindowMaterialSimpleGlazSys

    glass = record["materials"][0]
    shgc = glass["shgc"] * factor
    material = EnergyWindowMaterialSimpleGlazSys(
        f"{glass['identifier']}_shaded_{factor:.2f}"[:100], glass["u_factor"], shgc, glass["vt"])
    construction = WindowConstruction(f"{record['identifier']}_shaded_{factor:.2f}"[:100], [material])
    construction.user_data = {"unshaded_shgc": glass["shgc"], "solar_shading_factor": factor}
    return construction


def _construction_set(identifier, bundle, factor):
    from honeybee_energy.constructionset import ConstructionSet

    hb = bundle["honeybee"]
    built = {role: _hb_construction(record) for role, record in hb.items() if role != "WINDOW"}
    if "WINDOW" in hb:
        built["WINDOW"] = _window(hb["WINDOW"], factor)
    reciprocal = {role: _hb_construction(value["honeybee"])
                  for role, value in bundle["reciprocal"].items()}
    cs = ConstructionSet(identifier)
    if "EXT_WALL" in built:
        cs.wall_set.exterior_construction = built["EXT_WALL"]
    if "BASEMENT_WALL" in built:
        cs.wall_set.ground_construction = built["BASEMENT_WALL"]
    if "INT_WALL_NONLOADBEARING" in built:
        cs.wall_set.interior_construction = built["INT_WALL_NONLOADBEARING"]
    if "GROUND_FLOOR" in built:
        cs.floor_set.ground_construction = built["GROUND_FLOOR"]
        cs.floor_set.exterior_construction = built["GROUND_FLOOR"]
    if "INTERMEDIATE_FLOOR" in built:
        # Catalogue order is upper room to lower room: that is the ceiling seen from
        # the room below; the floor of the room above is its reciprocal.
        cs.roof_ceiling_set.interior_construction = built["INTERMEDIATE_FLOOR"]
        cs.floor_set.interior_construction = reciprocal["INTERMEDIATE_FLOOR"]
    if "TOP_FLOOR" in built:
        cs.roof_ceiling_set.exterior_construction = built["TOP_FLOOR"]
    if "WINDOW" in built:
        cs.aperture_set.window_construction = built["WINDOW"]
        cs.aperture_set.operable_construction = built["WINDOW"]
        cs.aperture_set.skylight_construction = built["WINDOW"]
    return cs, built


def _shading_factor(values, category):
    if category in _RESIDENTIAL:
        # EPSM's calibrated housing model applies no Sveby shading (factor 1.0), so the
        # export matches it; pass solar_shading_factor=0.5 for Sveby's total factor.
        return 1.0
    completion = values.get("completion_inputs", {})
    if category == "office":
        return completion["solar_shading_total_factor"]
    return completion["solar_shading_behavior_factor"]


def _program(identifier, category, values, airflow, *, year, active_dates):
    from honeybee_energy.lib.scheduletypelimits import (
        activity_level,
        fractional,
        on_off,
        temperature,
    )
    from honeybee_energy.load.equipment import ElectricEquipment
    from honeybee_energy.load.hotwater import ServiceHotWater
    from honeybee_energy.load.infiltration import Infiltration
    from honeybee_energy.load.lighting import Lighting
    from honeybee_energy.load.people import People
    from honeybee_energy.load.setpoint import Setpoint
    from honeybee_energy.load.ventilation import Ventilation
    from honeybee_energy.programtype import ProgramType

    use = values["use"]
    always = _constant(f"{identifier}_always_on", 1, fractional)
    lighting = None
    if category in _RESIDENTIAL:
        completion = values["model_completion_defaults"]
        start, end = use["occupancy_start_hour"], use["occupancy_end_hour"]
        occupancy = _daily(f"{identifier}_occupancy", _hours(start, (end - start) % 24), fractional)
        total_w = use["occupant_activity_total_w"]
        people = People(f"{identifier}_people", completion["occupant_density_per_m2"]["value"],
                        occupancy, _constant(f"{identifier}_activity", total_w, activity_level),
                        latent_fraction=use["occupant_latent_w"] / total_w)
        heat = use["household_electricity_internal_gain_fraction"]
        equipment = ElectricEquipment(
            f"{identifier}_household_electricity",
            use["household_electricity_kwh_m2_year"] * 1000 / 8760, always, lost_fraction=1 - heat)
        dhw_schedule, dhw_hours = always, 8760
        mech_flow, vent_schedule = values["airflow"]["minimum_outdoor_air_l_s_m2"], always
        cooling_enabled = completion["cooling_enabled"]["value"]
        heating_c, cooling_c = use["heating_setpoint_c"], use["cooling_setpoint_c"]
        dhw_kwh = use["dhw_kwh_m2_year"]
    else:
        inputs, completion = values["operation_inputs"], values["completion_inputs"]
        days = len(active_dates)
        cal = lambda name, on, off, limit=fractional: _calendar(  # noqa: E731
            f"{identifier}_{name}", on, off, active_dates, year, limit)
        zero = [0.0] * 24
        if category == "office":
            start, hours = inputs["occupancy_start_hour"], inputs["occupancy_hours"]
            occupancy = cal("occupancy", _hours(start, hours, on=inputs["occupancy_on_fraction"]), zero)
            standby = completion.get("standby_fraction", 0)
            eq_on, eq_off = _hours(start, hours, off=standby), [standby] * 24
            watts = use["business_electricity_kwh_m2_year"] * 1000 / _annual_sum(eq_on, eq_off, days, year)
            equipment = ElectricEquipment(f"{identifier}_business_electricity", watts,
                                          cal("equipment", eq_on, eq_off),
                                          lost_fraction=1 - use["available_heat_fraction"])
            dhw_on = _hours(start, hours)
            mech_flow = use["mechanical_vent_l_s_m2"]
            vent_schedule = cal("ventilation", _hours(inputs["ventilation_start_hour"],
                                                      inputs["ventilation_hours"]), zero)
            heating_c, cooling_c = use["heating_setpoint_c"], use["cooling_setpoint_c"]
        else:  # school classrooms
            operating = _hours(completion["operating_start_hour"], completion["operating_hours"])
            occupancy = cal("occupancy", _hours(completion["occupancy_start_hour"],
                                                completion["occupancy_hours"]), zero)
            equipment = ElectricEquipment(f"{identifier}_equipment", inputs["equipment_gain_w_m2"],
                                          cal("equipment", operating, zero))
            lighting = Lighting(f"{identifier}_lighting", inputs["lighting_gain_w_m2"],
                                cal("lighting", operating, zero))
            dhw_on = operating
            mech_flow = inputs["mechanical_vent_l_s_m2"]
            vent_schedule = cal("ventilation", operating, zero)
            heating_c, cooling_c = use["heating_setpoint_c"], completion["cooling_setpoint_c"]
        people = People(f"{identifier}_people", inputs["occupant_density_per_m2"], occupancy,
                        _constant(f"{identifier}_activity", inputs["occupant_activity_w"], activity_level))
        dhw_schedule = cal("dhw", dhw_on, zero)
        dhw_hours = _annual_sum(dhw_on, zero, days, year)
        cooling_enabled = completion["cooling_enabled"]
        dhw_kwh = use["dhw_kwh_m2_year"]
    # Self-draught gets the profile's outdoor-air flow too, as EPSM's record route does
    # (Sveby 0.35 L/s m2 for housing); only the heat recovery differs by topology.
    ventilation = Ventilation(f"{identifier}_ventilation", flow_per_area=mech_flow / 1000,
                              schedule=vent_schedule)
    hot_water = ServiceHotWater(f"{identifier}_dhw", dhw_kwh / _KWH_PER_LITRE / dhw_hours,
                                dhw_schedule, sensible_fraction=0, latent_fraction=0)
    setpoint = Setpoint(f"{identifier}_setpoint",
                        _constant(f"{identifier}_heating_c", heating_c, temperature),
                        _constant(f"{identifier}_cooling_c", cooling_c, temperature))
    program = ProgramType(
        identifier, people=people, lighting=lighting, electric_equipment=equipment,
        service_hot_water=hot_water,
        # Placeholder per exposed m2; apply_to_room sets the Atemp-based flow.
        infiltration=Infiltration(f"{identifier}_infiltration", 0.0, always),
        ventilation=ventilation, setpoint=setpoint)
    return program, cooling_enabled, _constant(f"{identifier}_cooling_off", 0, on_off)


def to_honeybee(catalogue, archetype_id, *, state=None, ventilation=None, standard="sveby",
                active_dates=None, solar_shading_factor=None):
    """Export one catalogue configuration as honeybee-energy objects.

    Parameters
    ----------
    catalogue : Catalogue
        Loaded catalogue, e.g. ``Catalogue.load()``.
    archetype_id, state, ventilation
        As in ``Catalogue.get``. ``ventilation`` is the observed system (S, F, FT, FTX).
    standard : str
        ``"sveby"`` (normal use) or ``"measured"`` (observed stock operation).
    active_dates : sequence of datetime.date, optional
        Office or school working days in 2017, the year Honeybee simulates; default
        :func:`swedish_active_dates` with Sveby's day count. Ignored for housing.
    solar_shading_factor : float, optional
        Factor on window SHGC. Default: 1.0 for housing, matching EPSM's calibrated
        model (Sveby's total factor would be 0.50); 0.50 for offices and the 0.65
        behaviour factor for schools.

    Returns
    -------
    HoneybeeArchetype
    """
    _require_honeybee()
    calendar_year = CALENDAR_YEAR
    from honeybee.altnumber import no_limit
    from honeybee_energy.hvac.idealair import IdealAirSystem

    meta = catalogue.nominal_metadata(archetype_id, state=state)
    category, era, selected = meta["category"], meta["era"], meta.get("state")
    archetype = catalogue.get(archetype_id, state=state, ventilation=ventilation)
    bundle = catalogue.handover(archetype_id, state=state, ventilation=ventilation)
    era_arg = era if (standard == "measured" and category == "multi_family") else None
    profile = select_operating_profile(category, standard=standard, era=era_arg)
    values = profile.to_dict()["values"]
    airflow = dict(archetype.hvac_template.values["airflow"])
    template_id = archetype.hvac_template.template_id
    identifier = f"epsm_{archetype_id}_{selected or 'single'}_{template_id.rsplit('.', 1)[-1]}".lower()
    factor = _shading_factor(values, category) if solar_shading_factor is None else solar_shading_factor
    if not 0 < factor <= 1:
        raise ValueError("solar_shading_factor must be in (0, 1]")
    cs, built = _construction_set(identifier, bundle, factor)
    notes = [f"Operating profile: {profile.profile_id} ({standard})",
             f"Ventilation template: {template_id}",
             "Ideal air reports delivered heat; multiply by 1/heating_cop for heat-pump electricity.",
             "Ground floors use ISO 13370 with ground_temperature_idf(); EPSM itself uses Kiva."]
    if category not in _RESIDENTIAL:
        n_days = values["reference_active_days"]
        if active_dates is None:
            active_dates = swedish_active_dates(calendar_year, n_days)
            notes.append(f"Calendar: EPSM assumption of {n_days} Swedish working days in {calendar_year}.")
        active_dates = tuple(sorted(active_dates))
    program, cooling_enabled, cooling_off = _program(
        identifier, category, values, airflow, year=calendar_year, active_dates=active_dates or ())
    hvac = IdealAirSystem(
        f"{identifier}_ideal_air", economizer_type="NoEconomizer",
        sensible_heat_recovery=airflow.get("sensible_recovery_effectiveness", 0) or 0,
        latent_heat_recovery=0, heating_limit=no_limit,
        cooling_limit=no_limit, cooling_availability=None if cooling_enabled else cooling_off)
    envelope = archetype.envelope_performance
    rate = None
    if envelope is not None:
        if envelope.infiltration_l_s_m2 is not None:
            rate = envelope.infiltration_l_s_m2
        elif envelope.infiltration_ach is not None:
            if envelope.infiltration_reference_basis == "tabula_reference_volume":
                height = catalogue_reference_height(catalogue, archetype_id, state)
                rate = envelope.infiltration_ach * height / 3.6
                notes.append(f"Infiltration: TABULA {envelope.infiltration_ach} ACH x {height} m "
                             "reference height, per m2 Atemp.")
            else:
                notes.append("Infiltration is ACH on conditioned volume; set it on the room.")
    total_ach = None
    if standard == "measured" and airflow.get("topology") == "S":
        measured = values.get("ventilation", {}).get("S", {})
        total_ach = measured.get("total_air_change_ach")
    return HoneybeeArchetype(
        archetype_id=archetype_id, category=category, era=era, state=selected,
        ventilation_template_id=template_id, construction_set=cs, program_type=program,
        hvac=hvac, constructions=built,
        wwr_by_orientation=catalogue.facade_assumptions(archetype_id)["wwr_by_orientation"],
        solar_shading_factor=factor, infiltration_l_s_m2=rate, self_draught_total_ach=total_ach,
        thermal_bridge_delta_u_w_m2k=getattr(envelope, "thermal_bridge_delta_u_w_m2k", None),
        heating_cop=heating_delivery_template().values["delivery"]["heating"]["heat_pump_cop"]["values"][0],
        calendar_year=calendar_year, notes=tuple(notes))


def catalogue_reference_height(catalogue, archetype_id, state=None):
    """The configuration's TABULA reference height in metres."""
    aid, _ = catalogue._resolve_selection(archetype_id)
    record = catalogue._data["archetypes"][aid]
    from .catalogue.catalogue import _state

    config = record.get("states", {}).get(_state(record, state), {})
    height = config.get("reference_height_m")
    if not height:
        raise ValueError(f"{archetype_id}: no reference_height_m for TABULA infiltration")
    return height


__all__ = [
    "HoneybeeArchetype", "to_honeybee", "swedish_active_dates", "swedish_holidays",
    "ground_temperature_idf", "iso13370_floor_u", "ground_construction",
    "bridged_construction", "orientation",
]
