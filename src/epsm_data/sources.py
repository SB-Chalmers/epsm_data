"""Pure projections of linked Honeybee thermal and Boverket carbon records."""

from .domain import EmbodiedCarbon

OPAQUE_FIELDS = (
    "roughness",
    "conductivity",
    "density",
    "specific_heat",
    "thermal_absorptance",
    "solar_absorptance",
    "visible_absorptance",
)
WINDOW_FIELDS = ("u_value", "shgc", "vt")


def carbon_record(resource, name):
    """Preserve published kg-based GWP-GHG AR4 values and conversion factors."""
    values = {}
    for item in resource.get("DataItems", ()):
        if item.get("PropertyCode") != "GWP-GHG AR4":
            continue
        if item.get("PropertyUnitCode") != "kg CO2 eq./kg":
            raise ValueError("Unsupported Boverket carbon unit")
        for value in item["DataValueItems"]:
            module = value["DataModuleCode"]
            if module in values:
                raise ValueError("Duplicate Boverket GWP module")
            values[module] = value["Value"]
    required = ("A1-A3 Conservative", "A1-A3 Typical", "A4", "A5.1")
    if any(values.get(key) is None for key in required):
        return None
    return EmbodiedCarbon(
        name=name,
        resource_id=str(resource["ResourceId"]),
        boverket_name=resource["Name"],
        A1_A3_conservative=values["A1-A3 Conservative"],
        A1_A3_typical=values["A1-A3 Typical"],
        A4_transport=values["A4"],
        A5_conservative=values["A5.1"],
        conservative_factor=resource["ConservativeDataConversionFactor"],
        conversion_factor=next(
            (
                item["Value"]
                for item in resource.get("Conversions", ())
                if item["Field"] == "Volume" and item["Unit"] == "kg/m³"
            ),
            None,
        ),
        technical_service_life=resource["RefServiceLifeNormal"],
        biogenic_carbon=resource.get("CalculatedBiogenicCarbon"),
    )
