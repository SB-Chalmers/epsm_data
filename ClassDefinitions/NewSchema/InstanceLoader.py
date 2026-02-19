import os
import json
import pandas as pd
from Classes import (
    EmbodiedCarbon2, OpaqueMaterial2, Roughness2,
    Layer2, Components2, ShearingLayer2, Element2,
    TABULA_CMF
)
from DataFetcher import fetch_all_materials, parse_material_api

# all load_ functions

EXCEL_PATH = "Material_Database.xlsx"
JSON_PATH = os.path.join(os.getcwd(), "ExtractingMaterials", "opaque_material.json")

# Helpers
def resolve_fractions(raw_fracs: list[float | None]) -> list[float]:
    missing = [i for i, f in enumerate(raw_fracs) if f is None]
    if not missing:
        return list(raw_fracs)
    known_sum = sum(f for f in raw_fracs if f is not None)
    if known_sum > 1.001:
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


# Loaders
def load_opaque_materials() -> list[OpaqueMaterial2]:
    df = pd.read_excel(EXCEL_PATH, sheet_name="Opaque_Materials")
    resource_lookup = {str(r["ResourceId"]): r for r in fetch_all_materials()}

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        energyplus_data = json.load(f)

    results, skipped = [], []

    for _, row in df.iterrows():
        name = str(row.get("Material Name", "Unknown"))
        boverket_id = row.get("Boverket ID")
        ep_id = row.get("EnergyPlus Identifier")

        if pd.isna(boverket_id) or str(boverket_id).strip() == "":
            skipped.append((name, "No Boverket ID")); continue
        if pd.isna(ep_id) or str(ep_id).strip() == "":
            skipped.append((name, "No EnergyPlus Identifier")); continue

        boverket_id = str(boverket_id).strip()
        ep_id = str(ep_id).strip()

        material_json = resource_lookup.get(boverket_id)
        if not material_json:
            skipped.append((name, f"Boverket ID {boverket_id} not found")); continue

        ep_data = energyplus_data.get(ep_id)
        if not ep_data:
            skipped.append((name, f"EnergyPlus ID '{ep_id}' not found")); continue

        try:
            ec = parse_material_api(material_json, name)
            opaque = OpaqueMaterial2(
                name=name,
                json_id=ep_id,
                boverket_id=boverket_id,
                material_type=ep_data.get("type"),
                roughness=Roughness2(ep_data.get("roughness")),
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

    print(f"\nOpaqueMaterial2 — loaded: {len(results)}, skipped: {len(skipped)}")
    if skipped:
        for name, reason in skipped:
            print(f"  '{name}': {reason}")

    return results


def load_layers(opaque_lookup: dict[str, OpaqueMaterial2]) -> list[Layer2]:
    df = pd.read_excel(EXCEL_PATH, sheet_name="Layers")

    mat_indices, i = [], 1
    while f"Material {i}" in df.columns:
        mat_indices.append(i); i += 1

    results, skipped, thickness_warnings = [], [], []

    for _, row in df.iterrows():
        name = str(row.get("Layer Name", "Unknown"))

        ignore = row.get("Ignore?")
        if pd.notna(ignore) and str(ignore).strip().lower() in ("yes", "y", "true", "1"):
            skipped.append((name, "Marked as ignored")); continue

        layer_code = row.get("Layer Code")
        if pd.isna(layer_code) or str(layer_code).strip() == "":
            skipped.append((name, "Missing layer code")); continue
        layer_code = str(layer_code).strip()

        thickness_raw = row.get("Layer Thickness")
        if pd.isna(thickness_raw):
            skipped.append((name, "Missing thickness")); continue
        try:
            thickness = float(str(thickness_raw).replace(",", "."))
        except ValueError:
            skipped.append((name, f"Invalid thickness: '{thickness_raw}'")); continue

        archetype = str(row.get("Archetype", "")).strip()
        is_composite = str(row.get("Composite Layer?", "No")).strip().lower() == "yes"

        raw_materials, parse_error = [], None
        for idx in mat_indices:
            mat_name = row.get(f"Material {idx}")
            if pd.isna(mat_name) or str(mat_name).strip() == "":
                break
            mat_name = str(mat_name).strip()

            frac_raw = row.get(f"Material {idx} Area Ratio")
            thick_raw = row.get(f"Material {idx} Thickness")

            mat_thickness = None
            if pd.notna(thick_raw) and str(thick_raw).strip() != "":
                try:
                    mat_thickness = float(str(thick_raw).replace(",", "."))
                except ValueError:
                    parse_error = f"Material {idx} '{mat_name}' invalid thickness"; break

            frac = None
            if pd.notna(frac_raw) and str(frac_raw).strip() != "":
                try:
                    frac = float(str(frac_raw).replace(",", "."))
                except ValueError:
                    parse_error = f"Material {idx} '{mat_name}' invalid area ratio"; break

            opaque = opaque_lookup.get(mat_name)
            if opaque is None:
                parse_error = f"Material '{mat_name}' not found"; break

            raw_materials.append((opaque, frac, mat_thickness))

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

        thicknesses = [
            thickness if not is_composite else (t if t is not None else 0.0)
            for _, _, t in raw_materials
        ]
        materials_tuple = tuple(
            (mat, frac, t)
            for (mat, _, _), frac, t in zip(raw_materials, fracs, thicknesses)
        )

        try:
            layer = Layer2(
                name=name, layer_code=layer_code, thickness=thickness,
                materials=materials_tuple, archetype=archetype, is_composite=is_composite,
            )
        except Exception as e:
            skipped.append((name, str(e))); continue

        warning = layer.check_thickness_consistency()
        if warning:
            thickness_warnings.append((name, warning))

        results.append(layer)

    print(f"\nLayer2 — loaded: {len(results)}, skipped: {len(skipped)}, thickness warnings: {len(thickness_warnings)}")
    
    return results


def load_components(layer_lookup: dict[str, Layer2]) -> list[Components2]:
    df = pd.read_excel(EXCEL_PATH, sheet_name="Components")
    df["Component Code"] = df["Component Code"].ffill()

    results, skipped = [], []

    for comp_code, group in df.groupby("Component Code", sort=False):
        comp_code = str(comp_code).strip()
        layer_entries, parse_error = [], None

        for _, row in group.iterrows():
            layer_code = row.get("Layers")
            if pd.isna(layer_code) or str(layer_code).strip() == "":
                parse_error = "Missing layer code"; break

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
        shearing_str = str(group.iloc[0].get("Shearing Layer", "")).strip()

        try:
            shearing_layer = ShearingLayer2(shearing_str)
        except ValueError:
            skipped.append((comp_code, f"Invalid shearing layer '{shearing_str}'")); continue

        try:
            component = Components2(
                name=comp_code,
                archetype=str(group.iloc[0].get("Archetype", "")).strip(),
                layers=tuple(layer_entries),
                shearing_layer=shearing_layer,
            )
            results.append(component)
        except Exception as e:
            skipped.append((comp_code, str(e)))

    print(f"\nComponents2 — loaded: {len(results)}, skipped: {len(skipped)}")
    if skipped:
        for name, reason in skipped:
            print(f"  '{name}': {reason}")
    return results


def load_elements(components_lookup: dict[str, Components2]) -> list[Element2]:
    groups: dict[str, list[Components2]] = {}
    skipped, tabula_warnings = [], []

    for comp_name, comp in components_lookup.items():
        parts = comp_name.rsplit("_", 2)
        if len(parts) < 3:
            skipped.append((comp_name, "Cannot parse base name")); continue
        groups.setdefault(parts[0], []).append(comp)

    shearing_order = [
        ShearingLayer2.Skin, ShearingLayer2.Space,
        ShearingLayer2.Structure, ShearingLayer2.Services, ShearingLayer2.Stuff,
    ]
    results = []

    for base_name, comps in groups.items():
        comps_sorted = sorted(
            comps,
            key=lambda c: shearing_order.index(c.shearing_layer)
            if c.shearing_layer in shearing_order else 999
        )

        archetype = comps_sorted[0].archetype
        age = parse_age_from_archetype(archetype)
        if age is None:
            skipped.append((base_name, f"Could not parse age from '{archetype}'")); continue

        try:
            element = Element2(
                name=base_name, archetype=archetype,
                age=age, components=tuple(comps_sorted),
            )
        except Exception as e:
            skipped.append((base_name, str(e))); continue

        warning = element.check_tabula(TABULA_CMF)
        if warning:
            tabula_warnings.append((base_name, warning))

        results.append(element)

    print(f"\nElement2 — loaded: {len(results)}, skipped: {len(skipped)}, Tabula warnings: {len(tabula_warnings)}")
    if skipped:
        for name, reason in skipped:
            print(f"  '{name}': {reason}")
    if tabula_warnings:
        for name, reason in tabula_warnings:
            print(f"  [TABULA] '{name}': {reason}")
    return results