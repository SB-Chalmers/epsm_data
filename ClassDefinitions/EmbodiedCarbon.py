class EmbodiedCarbon:
    """
    Contains properties listed in Boverket's klimatdatabas
    https://klimatdatabasen.boverket.se/
    """

    def __init__(
        self,
        product_name: str,
        resource_id: str,
        A1_A3_conservative: float,  # kg CO₂e/kg
        A4: float,                  # kg CO₂e/kg
        A5_conservative: float,     # kg CO₂e/kg
        A1_A3_typical: float,       # kg CO₂e/kg
        A1_A3_factor_conservative: float,
        A5_factor_byggspill: float,
        conversion_factor: float,   # kg/m³
        technical_service_life: int # years
    ):
        if not product_name:
            raise ValueError("Product name cannot be empty.")

        self.product_name = product_name.strip().lower()
        self.resource_id = str(resource_id)

        self.A1_A3_conservative = A1_A3_conservative
        self.A4 = A4
        self.A5_conservative = A5_conservative
        self.A1_A3_typical = A1_A3_typical
        self.A1_A3_factor_conservative = A1_A3_factor_conservative
        self.A5_factor_byggspill = A5_factor_byggspill
        self.conversion_factor = conversion_factor
        self.technical_service_life = technical_service_life

        # Validation
        values = [
            A1_A3_conservative,
            A4,
            A5_conservative,
            A1_A3_typical,
            A1_A3_factor_conservative,
            A5_factor_byggspill,
            conversion_factor,
        ]

        if any(v < 0 for v in values):
            raise ValueError("Embodied carbon values must be non-negative.")
        
        if self.A1_A3_conservative < self.A1_A3_typical:
            raise ValueError(
                "A1-A3 conservative value cannot be lower than typical value."
            )
        
        if self.A1_A3_factor_conservative < 1:
            raise ValueError(
                "A1-A3 conservative factor must be ≥ 1."
            )

        if self.A5_factor_byggspill < 1:
            raise ValueError(
                "A5 waste factor must be ≥ 1."
            )
        
        if not (1 <= self.technical_service_life <= 200):
            raise ValueError(
                "Technical service life must be between 1 and 200 years."
            )

    # Factory methods
    @classmethod
    def from_boverket(cls, data: dict) -> "EmbodiedCarbon":
        """Create an EmbodiedCarbon instance from a Boverket JSON entry."""

        data_items = data.get("DataItems", [])
        if not data_items:
            raise ValueError("No DataItems found in Boverket entry")

        gwp_items = data_items[0].get("DataValueItems", [])

        def get_value(code_name: str) -> float:
            for item in gwp_items:
                if item.get("DataModuleCode") == code_name:
                    return float(item.get("Value", 0))
            return 0.0

        tsl_str = str(data.get("RefServiceLifeNormal", ">50"))
        try:
            technical_service_life = int(tsl_str.strip(">").split()[0])
        except Exception:
            technical_service_life = 50

        return cls(
            product_name=data.get("Name", "Unknown"),
            resource_id=data.get("ResourceId"),
            A1_A3_conservative=get_value("A1-A3 Conservative"),
            A4=get_value("A4"),
            A5_conservative=get_value("A5.1"),
            A1_A3_typical=get_value("A1-A3 Typical"),
            A1_A3_factor_conservative=float(
                data.get("ConservativeDataConversionFactor", 1)
            ),
            A5_factor_byggspill=float(
                data.get("WasteFactor", 1)
            ),
            conversion_factor=float(
                data.get("Conversions", [{}])[0].get("Value", 1)
            ),
            technical_service_life=technical_service_life
        )

    # Serialization
    def to_dict(self) -> dict:
        """Return a dictionary of all properties."""
        return {
            "product_name": self.product_name,
            "resource_id": self.resource_id,
            "A1_A3_conservative": self.A1_A3_conservative,
            "A4": self.A4,
            "A5_conservative": self.A5_conservative,
            "A1_A3_typical": self.A1_A3_typical,
            "A1_A3_factor_conservative": self.A1_A3_factor_conservative,
            "A5_factor_byggspill": self.A5_factor_byggspill,
            "conversion_factor": self.conversion_factor,
            "technical_service_life": self.technical_service_life,
        }

    def print_info(self):
        """Print all properties of the embodied carbon instance."""
        print("Embodied Carbon Information:")
        for key, value in self.to_dict().items():
            print(f"{key}: {value}")
