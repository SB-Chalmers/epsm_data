"""Names shared by epsm_data, epsm_core and epsm_lca.

Data defines them, Core produces values under them and LCA consumes them. They
are string enums, so serialized records stay plain text and compare equal to the
strings in older files.
"""

from enum import StrEnum


class QuantityDriver(StrEnum):
    """Quantities Core resolves for a renovation measure; cost rates and products use them."""

    ELEMENT_AREA_M2 = "element_area_m2"
    WINDOW_AREA_M2 = "window_area_m2"
    WINDOW_COUNT = "window_count"
    FLOOR_AREA_M2 = "floor_area_m2"
    AIRFLOW_L_S = "airflow_l_s"
    DUCT_LENGTH_M = "duct_length_m"
    SUPPLY_TERMINAL_COUNT = "supply_terminal_count"
    EXHAUST_TERMINAL_COUNT = "exhaust_terminal_count"
    AHU_COUNT = "ahu_count"
    RISER_COUNT = "riser_count"
    PV_AREA_M2 = "pv_area_m2"
    PV_CAPACITY_KWP = "pv_capacity_kwp"
    BUILDING = "building"


DRIVER_DESCRIPTIONS = {
    QuantityDriver.ELEMENT_AREA_M2: "Installed area of the targeted envelope elements",
    QuantityDriver.WINDOW_AREA_M2: "Area of the targeted windows",
    QuantityDriver.WINDOW_COUNT: "Targeted window area divided by the candidate's typical unit area",
    QuantityDriver.FLOOR_AREA_M2: "Load reference floor area",
    QuantityDriver.AIRFLOW_L_S: "Design mechanical airflow of the new system",
    QuantityDriver.DUCT_LENGTH_M: "New supply and exhaust duct length",
    QuantityDriver.SUPPLY_TERMINAL_COUNT: "New supply air terminals",
    QuantityDriver.EXHAUST_TERMINAL_COUNT: "New exhaust air terminals",
    QuantityDriver.AHU_COUNT: "Air handling units",
    QuantityDriver.RISER_COUNT: "Vertical duct risers",
    QuantityDriver.PV_AREA_M2: "Roof area used by PV",
    QuantityDriver.PV_CAPACITY_KWP: "Installed PV peak power",
    QuantityDriver.BUILDING: "One per renovated building",
}


class Carrier(StrEnum):
    """Purchased or exported energy carriers."""

    DISTRICT_HEATING = "district_heating"
    ELECTRICITY = "electricity"
    FUEL = "fuel"


class EndUse(StrEnum):
    """End uses that can be inside an operational energy boundary."""

    SPACE_HEATING = "space_heating"
    FANS = "fans"
    DHW = "dhw"


def boundary_name(uses):
    """Name an energy boundary from its covered end uses, in a fixed order."""
    covered = {EndUse(u) for u in uses}
    if covered == {EndUse.SPACE_HEATING, EndUse.FANS}:
        return "space_heating_and_fans"
    if covered == {EndUse.SPACE_HEATING, EndUse.FANS, EndUse.DHW}:
        return "space_heating_fans_and_dhw"
    return "+".join(u.value for u in EndUse if u in covered)


# Keys of an inventory row's factor references, read by epsm_lca: a Boverket
# resource, or a CarbonReference by identity and as its saved JSON record.
BOVERKET_REF = "boverket_id"
CARBON_REFERENCE_ID = "carbon_reference_id"
CARBON_REFERENCE = "carbon_reference"
