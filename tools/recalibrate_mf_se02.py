"""Preview the historical bounded nominal search; never edits recipes.

Run with PYTHONPATH=src python tools/recalibrate_mf_se02.py. Baselines are
reviewed recipes after substitutions, before facade recalibration. Conductivity
is read from Honeybee definitions and is never a search variable. Ground roles
are excluded because their effective targets require geometry/boundary evidence.
The search retains its original base-plus-addition assumptions. Current v1.3
full recipes are not refitted by this helper; candidates are historical previews,
and some current targets have no feasible candidate under these bounds.
"""

import json
from copy import deepcopy
from itertools import product

from epsm_data import load_detailed_catalogue
from epsm_data.domain import BuildingElement
from epsm_data.thermal.boundary_conditions import get_boundary_resistances


def search(catalogue=None):
    catalogue = catalogue or load_detailed_catalogue()
    assemblies = catalogue.assemblies
    states = catalogue.archetypes["mf_se02"]["states"]
    conductivities = {
        mid: catalogue.resolve_material(mid)["properties"].get("conductivity")
        for mid in catalogue.materials
    }
    result = {}
    for prop, suffix in [
        ("roof", "top_floor"),
        ("external_wall", "ext_wall"),
        ("intermediate_floor", "intermediate_floor"),
        ("internal_wall", "int_wall_nonloadbearing"),
    ]:
        base = assemblies[f"mf_se02_existing_{suffix}"]
        additions = (
            [assemblies[f"mf_se02_{s}_{suffix}"] for s in ("standard", "advanced")]
            if prop in {"roof", "external_wall"}
            else []
        )
        recipes = [base, *additions]
        variables = []
        for ri, recipe in enumerate(recipes):
            constraints = {
                (c["component"], c["layer"]): c["allowed_thickness_mm"]
                for c in recipe.get("thickness_constraints", [])
            }
            for ci, comp in enumerate(recipe["components"]):
                for li, layer in enumerate(comp["layers"]):
                    choices = constraints.get((ci, li), layer.get("allowed_thickness_mm"))
                    if choices:
                        baseline = layer["thickness"] * 1000
                        if prop == "external_wall":
                            if ri == 0 and ci == 3:
                                baseline = 12.5
                            if ri == 1 and li == 1:
                                baseline = 50
                        variables.append((ri, ci, li, "thickness", choices, baseline))
            for c in recipe.get("framing_constraints", []):
                layer = recipe["components"][c["component"]]["layers"][c["layer"]]
                mi = layer["material_id"].index(c["material_id"])
                baseline = 0.15 if prop == "external_wall" else layer["area_fraction"][mi]
                variables.append(
                    (ri, c["component"], c["layer"], mi, c["allowed_area_fractions"], baseline)
                )

        def resistance(recipe, selection, ri, remove=0):
            total = 0
            values = {
                (v[1], v[2], v[3]): choice for v, choice in zip(variables, selection) if v[0] == ri
            }
            for ci, component in enumerate(recipe["components"]):
                if ci < remove:
                    continue
                for li, layer in enumerate(component["layers"]):
                    depth = values.get((ci, li, "thickness"), layer["thickness"] * 1000) / 1000
                    mids = layer["material_id"]
                    if isinstance(mids, str):
                        conductivity = conductivities[mids]
                    else:
                        fractions = list(layer["area_fraction"])
                        for mi in range(len(mids)):
                            if (ci, li, mi) in values:
                                fractions[mi] = values[ci, li, mi]
                                fractions[1 - mi] = 1 - fractions[mi]
                        conductivity = sum(
                            f * conductivities[mid] for f, mid in zip(fractions, mids)
                        )
                    total += depth / conductivity
            return total

        films = sum(get_boundary_resistances(BuildingElement(base["role"])))
        feasible, searched, best = 0, 0, None
        for selection in product(*(v[4] for v in variables)):
            searched += 1
            resistance_base = resistance(base, selection, 0)
            us = [1 / (films + resistance_base)]
            if additions:
                retained = (
                    resistance(base, selection, 0, remove=1)
                    if prop == "external_wall"
                    else resistance_base
                )
                us += [
                    1 / (films + retained + resistance(recipe, selection, ri))
                    for ri, recipe in enumerate(additions, 1)
                ]
            else:
                us *= 3
            errors = [
                abs(u / states[s]["target_snapshot"][prop]["value"] - 1)
                for u, s in zip(us, ("existing", "standard", "advanced"))
            ]
            if max(errors) > 0.02:
                continue
            feasible += 1
            score = (
                sum(abs(x - v[5]) for x, v in zip(selection, variables) if v[3] == "thickness"),
                sum(abs(x - v[5]) for x, v in zip(selection, variables) if v[3] != "thickness"),
                max(errors),
                *selection,
            )
            if best is None or score < best[0]:
                best = (score, selection, us)
        result[prop] = {
            "searched_candidates": searched,
            "feasible_candidates": feasible,
            "method": "Minimize summed thickness change (mm), then framing change, then largest relative U error, then numeric ordering; all three states must pass 2%.",
            "variables": [
                {
                    "assembly": f"mf_se02_{('existing', 'standard', 'advanced')[v[0]]}_{suffix}",
                    "component": v[1],
                    "layer": v[2],
                    "field": v[3],
                    "baseline": v[5],
                    "choices": v[4],
                }
                for v in variables
            ],
            "selected": None
            if best is None
            else {"score": best[0], "choices": best[1], "u_values": best[2]},
        }
    return deepcopy(result)


if __name__ == "__main__":
    print(json.dumps(search(), indent=2, allow_nan=False))
