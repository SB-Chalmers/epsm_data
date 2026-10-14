"""Executable illustrative renovation definitions; no dates or default prices."""

import json

from epsm_data import (
    BuildingElement,
    ConstructionOperation,
    RenovationCatalogue,
    RenovationMeasure,
    SystemOperation,
    reference_construction_set,
    reference_hvac_template,
)


def main():
    construction = reference_construction_set()
    window = construction.elements[BuildingElement.WINDOW]
    replacement = window.with_changes(name="Illustrative replacement",u_value=1.1,shgc=.55)
    windows = RenovationMeasure(
        "example.windows","envelope","Replace windows","Illustrative explicit inputs","window",
        operations=(ConstructionOperation("replace_element",BuildingElement.WINDOW,element=replacement),),
        source_references=("example:synthetic-construction",),
    )
    ftx = RenovationMeasure(
        "example.ftx","systems","Install FTX","Illustrative HVAC template","hvac",
        operations=(SystemOperation("replace_hvac",reference_hvac_template()),),
        requires_measure_ids=("example.windows",),
        source_references=("epsm:modelling-assumptions:illustrative-reference",),
    )
    catalogue = RenovationCatalogue((windows,ftx))
    changed = windows.apply(construction)
    assert changed.elements[BuildingElement.WINDOW].u_value == 1.1
    assert construction.elements[BuildingElement.WINDOW].u_value == 1.6
    # Core executes these resolved measures on actual building elements in order.
    assert ftx in catalogue.applicable(changed,applied_measure_ids=(windows.measure_id,))
    restored = RenovationCatalogue.from_dict(json.loads(json.dumps(catalogue.to_dict())))
    assert tuple(restored) == tuple(catalogue)
    print("Validated window and FTX definitions; Core supplies physical stages and quantities.")


if __name__ == "__main__":
    main()
