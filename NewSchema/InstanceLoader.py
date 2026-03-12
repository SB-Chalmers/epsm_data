import os
import json
import pandas as pd
from Classes import (OpaqueMaterial, Roughness,
    Layer, Components, ShearingLayer, Elements,
    TABULA_CMF, BuildingElement, Buildings
)
from DataFetcher import fetch_all_materials, parse_material_api

EXCEL_PATH = "data/Material_Database.xlsx"
JSON_PATH = os.path.join(os.getcwd(), "data/opaque_material.json")


def resolve_fractions(raw_fracs: list[float | None]) -> list[float]:
    missing = [i for i, f in enumerate(raw_fracs) if f is None]
    if not missing:
        return list(raw_fracs)
    known_sum = sum(f for f in raw_fracs if f is not None)
    if known_sum > 1.0:
        raise ValueError(f"Known fractions sum to {known_sum:.4f}, exceeds 1.0.")
    fill = (1.0 - known_sum) / len(missing)
    result = list(raw_fracs)
    for i in missing:
        result[i] = fill
    return result


def parse_age_from_archetype(archetype: str) -> int | None:
    for part in archetype.split("_"):
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


def load_opaque_materials() -> list[OpaqueMaterial]:
    df = pd.read_excel(EXCEL_PATH, sheet_name="Opaque_Materials", header=1)
    df.columns = ["Material Name", "Ignore?", "Boverket ID", "Boverket Match Confidence",
                  "Honeybee Identifier", "Honeybee Match Confidence", "Combined Match Confidence"]

    resource_lookup = {str(r["ResourceId"]): r for r in fetch_all_materials()}

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        energyplus_data = json.load(f)

    results, skipped = [], []

    for _, row in df.iterrows():
        name = str(row.get("Material Name", "Unknown"))

        ignore = row.get("Ignore?")
        if pd.notna(ignore) and str(ignore).strip().upper() == "X":
            skipped.append((name, "Marked as ignored")); continue

        boverket_id = row.get("Boverket ID")
        ep_id = row.get("Honeybee Identifier")

        if pd.isna(boverket_id) or str(boverket_id).strip() == "":
            skipped.append((name, "No Boverket ID")); continue
        if pd.isna(ep_id) or str(ep_id).strip() == "":
            skipped.append((name, "No Honeybee Identifier")); continue

        boverket_id = str(boverket_id).strip()
        ep_id = str(ep_id).strip()

        material_json = resource_lookup.get(boverket_id)
        if not material_json:
            skipped.append((name, f"Boverket ID {boverket_id} not found")); continue

        ep_data = energyplus_data.get(ep_id)
        if not ep_data:
            skipped.append((name, f"Honeybee ID '{ep_id}' not found")); continue

        try:
            ec = parse_material_api(material_json, name)
            opaque = OpaqueMaterial(
                name=name,
                json_id=ep_id,
                boverket_id=boverket_id,
                material_type=ep_data.get("type"),
                roughness=Roughness(ep_data.get("roughness")),
                density=ep_data.get("density"),
                specific_heat=ep_data.get("specific_heat"),
                thermal_absorptance=ep_data.get("thermal_absorptance"),
                solar_absorptance=ep_data.get("solar_absorptance"),
                visible_absorptance=ep_data.get("visible_absorptance"),
                conductivity=ep_data.get("conductivity"),
                embodied_carbon=ec,
            )
            results.append(opaque)
        except Exception as e:
            skipped.append((name, str(e)))

    print(f"\nOpaqueMaterial — loaded: {len(results)}, skipped: {len(skipped)}")
    if skipped:
        for name, reason in skipped:
            print(f"  '{name}': {reason}")
    return results


def load_layers(opaque_lookup: dict[str, OpaqueMaterial]) -> list[Layer]:
    df = pd.read_excel(EXCEL_PATH, sheet_name="Layers", header=1)
    df.columns = ["Layer Code", "Layer Thickness", "Composite Layer?",
                  "Material 1", "Material 1 Area Ratio",
                  "Material 2", "Material 2 Area Ratio",
                  "Material 3", "Material 3 Area Ratio",
                  "Notes", "Ignore?", "Layer Use Intensity", "Duplicate Check"]

    mat_indices = [1, 2, 3]
    results, skipped = [], []

    for _, row in df.iterrows():
        layer_code = row.get("Layer Code")
        if pd.isna(layer_code) or str(layer_code).strip() == "":
            continue
        layer_code = str(layer_code).strip()
        name = layer_code

        ignore = row.get("Ignore?")
        if pd.notna(ignore) and str(ignore).strip().upper() == "X":
            skipped.append((name, "Marked as ignored")); continue

        thickness_raw = row.get("Layer Thickness")
        if pd.isna(thickness_raw):
            skipped.append((name, "Missing thickness")); continue
        try:
            layer_thickness = float(str(thickness_raw).replace(",", "."))
        except ValueError:
            skipped.append((name, f"Invalid thickness: '{thickness_raw}'")); continue

        is_composite = str(row.get("Composite Layer?", "S")).strip().upper() == "C"

        raw_materials, parse_error = [], None
        for idx in mat_indices:
            mat_name = row.get(f"Material {idx}")
            if pd.isna(mat_name) or str(mat_name).strip() == "":
                break
            mat_name = str(mat_name).strip()

            opaque = opaque_lookup.get(mat_name)
            if opaque is None:
                parse_error = f"Material '{mat_name}' not found"; break

            frac_raw = row.get(f"Material {idx} Area Ratio")
            frac = None
            if pd.notna(frac_raw) and str(frac_raw).strip() != "":
                try:
                    frac = float(str(frac_raw).replace(",", "."))
                except ValueError:
                    parse_error = f"Material {idx} '{mat_name}': invalid area ratio"; break

            raw_materials.append((opaque, frac, layer_thickness))

        if parse_error or not raw_materials:
            skipped.append((name, parse_error or "No valid materials")); continue
        if is_composite and len(raw_materials) < 2:
            skipped.append((name, "Composite but fewer than 2 materials")); continue
        if not is_composite and len(raw_materials) > 1:
            skipped.append((name, "Multiple materials but not composite")); continue

        try:
            fracs = resolve_fractions([f for _, f, _ in raw_materials])
        except ValueError as e:
            skipped.append((name, f"Fraction error: {e}")); continue

        materials_tuple = tuple(
            (mat, frac, mat_t)
            for (mat, _, mat_t), frac in zip(raw_materials, fracs)
        )

        try:
            layer = Layer(
                name=name,
                layer_code=layer_code,
                thickness=layer_thickness,
                materials=materials_tuple,
                is_composite=is_composite,
            )
        except Exception as e:
            skipped.append((name, str(e))); continue

        results.append(layer)

    print(f"\nLayer — loaded: {len(results)}, skipped: {len(skipped)}")
    if skipped:
        for n, reason in skipped:
            print(f"  '{n}': {reason}")
    return results


def load_components(layer_lookup: dict[str, Layer]) -> list[Components]:
    df = pd.read_excel(EXCEL_PATH, sheet_name="Components", header=1)
    df.columns = ["Component Code", "Layers", "Application", "Layer Index",
                  "Shearing Layer", "Archetype", "Notes", "Flag"]
    df["Component Code"] = df["Component Code"].ffill()

    results, skipped = [], []

    for comp_code, group in df.groupby("Component Code", sort=False):
        comp_code = str(comp_code).strip()
        layer_entries, parse_error = [], None

        for _, row in group.iterrows():
            layer_code = row.get("Layers")
            if pd.isna(layer_code) or str(layer_code).strip() == "":
                print(f"  [WARN] '{comp_code}': blank row skipped")
                continue

            layer_code = str(layer_code).strip()
            layer = layer_lookup.get(layer_code)
            if layer is None:
                parse_error = f"Layer '{layer_code}' not found"; break

            try:
                index = int(row.get("Layer Index"))
            except (ValueError, TypeError):
                parse_error = f"Invalid layer index for '{layer_code}'"; break

            layer_entries.append((layer, index))

        if parse_error or not layer_entries:
            skipped.append((comp_code, parse_error or "No valid layers")); continue

        layer_entries.sort(key=lambda x: x[1])

        first_row = group.iloc[0]
        shearing_str = str(first_row.get("Shearing Layer", "")).strip().capitalize()

        try:
            shearing_layer = ShearingLayer(shearing_str)
        except ValueError:
            skipped.append((comp_code, f"Invalid shearing layer '{shearing_str}'")); continue

        try:
            application = BuildingElement(str(first_row.get("Application", "")).strip().upper())
        except ValueError:
            skipped.append((comp_code, f"Invalid application '{first_row.get('Application')}'")); continue

        try:
            component = Components(
                name=comp_code,
                archetype=str(first_row.get("Archetype", "")).strip(),
                application=application,
                layers=tuple(layer_entries),
                shearing_layer=shearing_layer,
            )
            results.append(component)
        except Exception as e:
            skipped.append((comp_code, str(e)))

    print(f"\nComponents — loaded: {len(results)}, skipped: {len(skipped)}")
    if skipped:
        for name, reason in skipped:
            print(f"  '{name}': {reason}")
    return results


def load_elements(components_lookup: dict[str, Components]) -> list[Elements]:
    df = pd.read_excel(EXCEL_PATH, sheet_name="Elements", header=1)

    fixed_cols = ["Element Code", "Element Type", "Archetype"]
    component_cols = [f"Component {i}" for i in range(1, len(df.columns) - 2)]
    df.columns = fixed_cols + component_cols

    shearing_order = [
        ShearingLayer.Skin, ShearingLayer.Space,
        ShearingLayer.Structure, ShearingLayer.Services, ShearingLayer.Stuff,
    ]

    results, skipped, tabula_warnings, no_matches = [], [], [], []

    for _, row in df.iterrows():
        element_code = row.get("Element Code")
        if pd.isna(element_code) or str(element_code).strip() == "":
            continue
        element_code = str(element_code).strip()

        archetype = str(row.get("Archetype", "")).strip()
        element_type_str = str(row.get("Element Type", "")).strip()

        age = parse_age_from_archetype(archetype)
        if age is None:
            skipped.append((element_code, f"Could not parse age from '{archetype}'")); continue

        element_type = BuildingElement.from_name(element_type_str)
        if element_type is None:
            skipped.append((element_code, f"Unrecognised element type '{element_type_str}'")); continue

        comp_codes = []
        found_no_match = False
        for col in component_cols:
            val = row.get(col)
            if pd.isna(val) or str(val).strip() == "":
                continue
            if str(val).strip() == "No matches found":
                no_matches.append(element_code)
                found_no_match = True
                break
            comp_codes.append(str(val).strip())

        if found_no_match:
            continue

        if not comp_codes:
            skipped.append((element_code, "No components found")); continue

        comps, parse_error = [], None
        for code in comp_codes:
            comp = components_lookup.get(code)
            if comp is None:
                parse_error = f"Component '{code}' not found"; break
            comps.append(comp)

        if parse_error:
            skipped.append((element_code, parse_error)); continue

        comps_sorted = sorted(
            comps,
            key=lambda c: shearing_order.index(c.shearing_layer)
            if c.shearing_layer in shearing_order else 999
        )

        try:
            element = Elements(
                name=element_code,
                archetype=archetype,
                age=age,
                components=tuple(comps_sorted),
                application=element_type,
            )
        except Exception as e:
            skipped.append((element_code, str(e))); continue

        warning = element.check_tabula(TABULA_CMF)
        if warning:
            tabula_warnings.append((element_code, warning))

        results.append(element)

    print(f"\nElement — loaded: {len(results)}, skipped: {len(skipped)}, no matches: {len(no_matches)}, Tabula warnings: {len(tabula_warnings)}")
    if skipped:
        for name, reason in skipped:
            print(f"  '{name}': {reason}")
    if no_matches:
        print(f"\n  No matches found:")
        for name in no_matches:
            print(f"  '{name}': No matches found in Excel")
    if tabula_warnings:
        for name, reason in tabula_warnings:
            print(f"  [TABULA] '{name}': {reason}")
    return results

def load_buildings(elements_lookup: dict[str, Elements]) -> list[Buildings]:
    df = pd.read_excel(EXCEL_PATH, sheet_name="Building", header=1)
    df.columns = [
        "Archetype", "Multiple Ext Walls",
        "Roof", "Top Floor", "Intermediate Floor", "Ground Floor", "Basement Floor",
        "Ext Wall", "Ext Wall Low", "Ext Wall Medium", "Ext Wall High",
        "Basement Wall", "Int Wall Loadbearing", "Int Wall Nonloadbearing"
    ]

    element_cols = [
        "Roof", "Top Floor", "Intermediate Floor", "Ground Floor", "Basement Floor",
        "Ext Wall", "Ext Wall Low", "Ext Wall Medium", "Ext Wall High",
        "Basement Wall", "Int Wall Loadbearing", "Int Wall Nonloadbearing"
    ]

    skip_values = {"not required", "no components assigned to this element", "no match", ""}

    results, skipped = [], []

    for _, row in df.iterrows():
        archetype = row.get("Archetype")
        if pd.isna(archetype) or str(archetype).strip() == "":
            continue
        archetype = str(archetype).strip()

        age = parse_age_from_archetype(archetype)
        if age is None:
            skipped.append((archetype, f"Could not parse age from '{archetype}'")); continue
        
        multiple_ext = str(row.get("Multiple Ext Walls", "")).strip().lower() == "yes"
        if multiple_ext:
            missing = [c for c in ["Ext Wall Low", "Ext Wall Medium", "Ext Wall High"]
                    if str(row.get(c, "")).strip().lower() in skip_values]
            if missing:
                print(f"  [WARN] '{archetype}': marked multiple ext walls but missing: {missing}")
        else:
            if str(row.get("Ext Wall", "")).strip().lower() in skip_values:
                print(f"  [WARN] '{archetype}': single ext wall expected but not assigned")

        elements_tuple, parse_error = [], None
        for col in element_cols:
            val = row.get(col)
            if pd.isna(val) or str(val).strip().lower() in skip_values:
                continue
            element_code = str(val).strip()
            element = elements_lookup.get(element_code)
            if element is None:
                print(f"  [WARN] '{archetype}': element '{element_code}' was not loaded")
                continue
            elements_tuple.append((element.name, element.application))

        if not elements_tuple:
            skipped.append((archetype, "No elements found")); continue
        
        # Check for duplicate element types within the building
        seen_types = set()
        for _, app in elements_tuple:
            if app in seen_types:
                print(f"  [WARN] '{archetype}': duplicate element type '{app.value}'")
            seen_types.add(app)

        try:
            building = Buildings(
                name=archetype,
                age=age,
                elements=tuple(elements_tuple),
            )
            results.append(building)
        except Exception as e:
            skipped.append((archetype, str(e)))

    print(f"\nBuilding — loaded: {len(results)}, skipped: {len(skipped)}")
    if skipped:
        for name, reason in skipped:
            print(f"  '{name}': {reason}")
    return results