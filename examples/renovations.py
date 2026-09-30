"""Create and query a sourced-by-caller renovation catalogue; no default prices."""

import json

from epsm_data import ParameterDefinition, RenovationCatalogue, RenovationMeasure


def main():
    measure = RenovationMeasure(
        measure_id="example.window_replacement",
        category="envelope",
        name="Window replacement",
        description="Illustrative catalogue definition",
        target="window",
        parameters=(
            ParameterDefinition("u_value_w_m2k", "number", "Whole-window U-value", "W/(m2 K)"),
            ParameterDefinition("solar_heat_gain_coefficient", "number", "Solar gain factor", "1"),
        ),
        applicability_notes=("Workflow must verify window geometry and installation scope.",),
    )
    catalogue = RenovationCatalogue([measure])
    assert catalogue.get(measure.measure_id) == measure
    assert catalogue.filter(category="envelope") == (measure,)
    payload = json.dumps(measure.to_dict(), indent=2)
    assert RenovationMeasure.from_dict(json.loads(payload)) == measure
    print(payload)


if __name__ == "__main__":
    main()
