"""Loader.

Constructs domain objects from raw Excel, JSON, and Boverket API data.
Depends on infra/io/ for raw data and infra/api/ for Boverket resources.
"""

import pandas as pd
from uuid import uuid4

from epsm_data.domain.material import OpaqueMaterial, GlazingMaterial, GasMaterial
from epsm_data.domain.layer import Layer, WindowConstruction
from epsm_data.domain.component import Components
from epsm_data.domain.element import Elements, WindowElement
from epsm_data.domain.building import BuildingArchetype, ConstructionSet
from epsm_data.domain.enums import Roughness, ShearingLayer, BuildingElement
from epsm_data.thermal.standards import TABULA_CMF
from epsm_data.infra.io.excel_reader import (
    read_opaque_materials_sheet,
    read_layers_sheet,
    read_components_sheet,
    read_elements_sheet,
    read_buildings_sheet,
    read_window_elements_sheet,
)
from epsm_data.infra.io.json_reader import (
    read_energyplus_json,
    read_window_material_json,
    read_window_construction_json,
)
from epsm_data.infra.api.boverket_client import fetch_material_resources, parse_material_api

def resolve_fractions(raw_fracs: list[float | None]) -> list[float]:
    """Fill missing area fractions so they sum to 1.0.

    Args:
        raw_fracs: List of fractions, with None for missing values.

    Returns:
        Complete list of fractions summing to 1.0.

    Raises:
        ValueError: If known fractions already exceed 1.0.
    """
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
    """Extract construction year from an archetype string e.g. 'CMF_1950' -> 1950.

    Args:
        archetype: Archetype identifier string.

    Returns:
        Four-digit year as int, or None if not found.
    """
    for part in archetype.split("_"):
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


# ─────────────────────────────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────────────────────────────

def load_opaque_materials(excel_path: str, json_path: str) -> list[OpaqueMaterial]:
    """Load and construct OpaqueMaterial instances from Excel, JSON and Boverket API.

    Args:
        excel_path: Path to the Excel workbook.
        json_path: Path to the EnergyPlus/Honeybee JSON file.

    Returns:
        List of validated OpaqueMaterial instances.
    """
    df = read_opaque_materials_sheet(excel_path)
    resource_lookup = {str(r["ResourceId"]): r for r in fetch_material_resources()}
    energyplus_data = read_energyplus_json(json_path)

    results, skipped = [], []

    for _, row in df.iterrows():
        name = str(row.get("Material Name", "Unknown"))

        ignore = row.get("Ignore?")
        if pd.notna(ignore) and str(ignore).strip().upper() == "X":
            skipped.append((name, "Marked as ignored"))
            continue

        boverket_id = row.get("Boverket ID")
        ep_id = row.get("Honeybee Identifier")

        if pd.isna(boverket_id) or str(boverket_id).strip() == "":
            skipped.append((name, "No Boverket ID"))
            continue
        if pd.isna(ep_id) or str(ep_id).strip() == "":
            skipped.append((name, "No Honeybee Identifier"))
            continue

        boverket_id = str(boverket_id).strip()
        ep_id = str(ep_id).strip()

        material_json = resource_lookup.get(boverket_id)
        if not material_json:
            skipped.append((name, f"Boverket ID {boverket_id} not found"))
            continue

        ep_data = energyplus_data.get(ep_id)
        if not ep_data:
            skipped.append((name, f"Honeybee ID '{ep_id}' not found"))
            continue

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


def load_layers(excel_path: str, opaque_lookup: dict[str, OpaqueMaterial]) -> list[Layer]:
    """Load and construct Layer instances from Excel.

    Args:
        excel_path: Path to the Excel workbook.
        opaque_lookup: Dict of OpaqueMaterial instances keyed by name.

    Returns:
        List of validated Layer instances.
    """
    df = read_layers_sheet(excel_path)
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
            skipped.append((name, "Marked as ignored"))
            continue

        thickness_raw = row.get("Layer Thickness")
        if pd.isna(thickness_raw):
            skipped.append((name, "Missing thickness"))
            continue
        try:
            layer_thickness = float(str(thickness_raw).replace(",", "."))
        except ValueError:
            skipped.append((name, f"Invalid thickness: '{thickness_raw}'"))
            continue

        is_composite = str(row.get("Composite Layer?", "S")).strip().upper() == "C"

        raw_materials, parse_error = [], None
        for idx in mat_indices:
            mat_name = row.get(f"Material {idx}")
            if pd.isna(mat_name) or str(mat_name).strip() == "":
                break
            mat_name = str(mat_name).strip()

            opaque = opaque_lookup.get(mat_name)
            if opaque is None:
                parse_error = f"Material '{mat_name}' not found"
                break

            frac_raw = row.get(f"Material {idx} Area Ratio")
            frac = None
            if pd.notna(frac_raw) and str(frac_raw).strip() != "":
                try:
                    frac = float(str(frac_raw).replace(",", "."))
                except ValueError:
                    parse_error = f"Material {idx} '{mat_name}': invalid area ratio"
                    break

            raw_materials.append((opaque, frac, layer_thickness))

        if parse_error or not raw_materials:
            skipped.append((name, parse_error or "No valid materials"))
            continue
        if is_composite and len(raw_materials) < 2:
            skipped.append((name, "Composite but fewer than 2 materials"))
            continue
        if not is_composite and len(raw_materials) > 1:
            skipped.append((name, "Multiple materials but not composite"))
            continue

        try:
            fracs = resolve_fractions([f for _, f, _ in raw_materials])
        except ValueError as e:
            skipped.append((name, f"Fraction error: {e}"))
            continue

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
            skipped.append((name, str(e)))
            continue

        results.append(layer)

    print(f"\nLayer — loaded: {len(results)}, skipped: {len(skipped)}")
    if skipped:
        for n, reason in skipped:
            print(f"  '{n}': {reason}")
    return results


def load_components(excel_path: str, layer_lookup: dict[str, Layer]) -> list[Components]:
    """Load and construct Components instances from Excel.

    Args:
        excel_path: Path to the Excel workbook.
        layer_lookup: Dict of Layer instances keyed by layer code.

    Returns:
        List of validated Components instances.
    """
    df = read_components_sheet(excel_path)
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
                parse_error = f"Layer '{layer_code}' not found"
                break

            try:
                index = int(row.get("Layer Index"))
            except (ValueError, TypeError):
                parse_error = f"Invalid layer index for '{layer_code}'"
                break

            layer_entries.append((layer, index))

        if parse_error or not layer_entries:
            skipped.append((comp_code, parse_error or "No valid layers"))
            continue

        layer_entries.sort(key=lambda x: x[1])

        first_row = group.iloc[0]
        shearing_str = str(first_row.get("Shearing Layer", "")).strip().capitalize()

        try:
            shearing_layer = ShearingLayer(shearing_str)
        except ValueError:
            skipped.append((comp_code, f"Invalid shearing layer '{shearing_str}'"))
            continue

        try:
            application = BuildingElement(str(first_row.get("Application", "")).strip().upper())
        except ValueError:
            skipped.append((comp_code, f"Invalid application '{first_row.get('Application')}'"))
            continue

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


def load_elements(excel_path: str, components_lookup: dict[str, Components]) -> list[Elements]:
    """Load and construct Elements instances from Excel.

    Args:
        excel_path: Path to the Excel workbook.
        components_lookup: Dict of Components instances keyed by name.

    Returns:
        List of validated Elements instances.
    """
    df = read_elements_sheet(excel_path)
    fixed_cols = ["Element Code", "Element Type", "Archetype"]
    component_cols = [c for c in df.columns if c not in fixed_cols]

    shearing_order = [
        ShearingLayer.Skin, ShearingLayer.Space,
        ShearingLayer.Structure, ShearingLayer.Services, ShearingLayer.Stuff,
    ]

    results, skipped, tabula_warnings, no_matches, dup_warnings = [], [], [], [], []

    for _, row in df.iterrows():
        element_code = row.get("Element Code")
        if pd.isna(element_code) or str(element_code).strip() == "":
            continue
        element_code = str(element_code).strip()

        archetype = str(row.get("Archetype", "")).strip()
        element_type_str = str(row.get("Element Type", "")).strip()

        age = parse_age_from_archetype(archetype)
        if age is None:
            skipped.append((element_code, f"Could not parse age from '{archetype}'"))
            continue

        element_type = BuildingElement.from_name(element_type_str)
        if element_type is None:
            skipped.append((element_code, f"Unrecognised element type '{element_type_str}'"))
            continue

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
            skipped.append((element_code, "No components found"))
            continue

        comps, parse_error = [], None
        for code in comp_codes:
            comp = components_lookup.get(code)
            if comp is None:
                parse_error = f"Component '{code}' not found"
                break
            if any(c.name == comp.name for c in comps):
                dup_warnings.append((element_code, comp.name))
                continue
            comps.append(comp)

        if parse_error:
            skipped.append((element_code, parse_error))
            continue

        comps_sorted = sorted(
            comps,
            key=lambda c: shearing_order.index(c.shearing_layer)
            if c.shearing_layer in shearing_order else 999,
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
            skipped.append((element_code, str(e)))
            continue

        warning = element.tabula_warning
        if warning:
            tabula_warnings.append((element_code, warning))

        results.append(element)

    print(f"\nElement — loaded: {len(results)}, skipped: {len(skipped)}, "
          f"no matches: {len(no_matches)}, Tabula warnings: {len(tabula_warnings)}, "
          f"dup warnings: {len(dup_warnings)}")
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
    if dup_warnings:
        print(f"\n  Duplicate components (kept one):")
        for element, component in dup_warnings:
            print(f"  [DUP] '{element}': duplicate component '{component}'")
    return results


def load_window_elements(
    excel_path: str,
    window_material_json_path: str,
    window_construction_json_path: str,
    resource_lookup: dict,
) -> list[WindowElement]:
    """Load and construct WindowElement instances from Excel and JSON files.

    Args:
        excel_path: Path to the Excel workbook.
        window_material_json_path: Path to the Honeybee window material JSON.
        window_construction_json_path: Path to the Honeybee window construction JSON.
        resource_lookup: Dict of Boverket API resources keyed by ResourceId string.

    Returns:
        List of validated WindowElement instances.
    """

    df = read_window_elements_sheet(excel_path)
    window_materials = read_window_material_json(window_material_json_path)
    window_constructions = read_window_construction_json(window_construction_json_path)

    results, skipped = [], []

    for _, row in df.iterrows():
        name = str(row.get("Material Name", "Unknown")).strip()
        if not name or name == "nan":
            continue

        boverket_id = row.get("Boverket ID")
        construction_id = row.get("HoneyBee Identifier Window Construction")

        if pd.isna(boverket_id) or str(boverket_id).strip() == "":
            skipped.append((name, "No Boverket ID"))
            continue
        if pd.isna(construction_id) or str(construction_id).strip() == "":
            skipped.append((name, "No Window Construction identifier"))
            continue

        boverket_id = str(int(float(str(boverket_id).strip())))
        construction_id = str(construction_id).strip()

        # fetch embodied carbon from Boverket API
        material_json = resource_lookup.get(boverket_id)
        if not material_json:
            skipped.append((name, f"Boverket ID {boverket_id} not found"))
            continue

        # fetch construction layer stack
        construction_data = window_constructions.get(construction_id)
        if not construction_data:
            skipped.append((name, f"Window construction '{construction_id}' not found"))
            continue

        # get U-value from TABULA_CMF for windows
        age_str = parse_age_from_archetype(name)
        u_value_declared = 2.0  # fallback default
        if age_str:
            decade_key = f"CMF_{(age_str // 10) * 10}"
            if decade_key in TABULA_CMF:
                u_value_declared = TABULA_CMF[decade_key].get("window", 2.0)

        try:
            ec = parse_material_api(material_json, name)

            # build the layer stack from construction materials
            layer_materials = []
            for mat_id in construction_data.get("materials", []):
                mat_data = window_materials.get(mat_id)
                if not mat_data:
                    raise ValueError(f"Window material '{mat_id}' not found in JSON")

                mat_type = mat_data.get("type")

                if mat_type == "EnergyWindowMaterialGlazing":
                    layer_materials.append(GlazingMaterial(
                        name=mat_id,
                        json_id=mat_id,
                        thickness=mat_data["thickness"],
                        solar_transmittance=mat_data["solar_transmittance"],
                        solar_reflectance=mat_data["solar_reflectance"],
                        solar_reflectance_back=mat_data["solar_reflectance_back"],
                        visible_transmittance=mat_data["visible_transmittance"],
                        visible_reflectance=mat_data["visible_reflectance"],
                        visible_reflectance_back=mat_data["visible_reflectance_back"],
                        infrared_transmittance=mat_data["infrared_transmittance"],
                        emissivity=mat_data["emissivity"],
                        emissivity_back=mat_data["emissivity_back"],
                        conductivity=mat_data["conductivity"],
                        dirt_correction=mat_data.get("dirt_correction", 1.0),
                        solar_diffusing=mat_data.get("solar_diffusing", False),
                        embodied_carbon=ec,
                    ))
                elif mat_type == "EnergyWindowMaterialGas":
                    layer_materials.append(GasMaterial(
                        name=mat_id,
                        json_id=mat_id,
                        thickness=mat_data["thickness"],
                        gas_type=mat_data["gas_type"],
                    ))
                else:
                    raise ValueError(f"Unsupported window material type '{mat_type}'")

            construction = WindowConstruction(
                name=name,
                json_id=construction_id,
                boverket_id=boverket_id,
                materials=tuple(layer_materials),
                u_value_declared=u_value_declared,
                embodied_carbon=ec,
            )

            # parse age from name or use a default
            age = parse_age_from_archetype(name) or 1950

            window_element = WindowElement(
                name=name,
                archetype=name,
                age=age,
                application=BuildingElement.WINDOW,
                construction=construction,
            )
            results.append(window_element)

        except Exception as e:
            skipped.append((name, str(e)))

    print(f"\nWindowElement — loaded: {len(results)}, skipped: {len(skipped)}")
    if skipped:
        for name, reason in skipped:
            print(f"  '{name}': {reason}")
    return results

def load_buildings(
    excel_path: str,
    elements_lookup: dict[str, Elements],
    window_lookup: dict[str, WindowElement],
) -> list[BuildingArchetype]:
    """Load and construct BuildingArchetype instances from Excel.

    Args:
        excel_path: Path to the Excel workbook.
        elements_lookup: Dict of Elements instances keyed by element code.
        window_lookup: Dict of WindowElement instances keyed by name.

    Returns:
        List of validated BuildingArchetype instances.
    """
    df = read_buildings_sheet(excel_path)

    element_cols = [
        "Roof", "Top Floor", "Intermediate Floor", "Ground Floor", "Basement Floor",
        "Ext Wall", "Ext Wall Low", "Ext Wall Medium", "Ext Wall High",
        "Basement Wall", "Int Wall Loadbearing", "Int Wall Nonloadbearing",
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
            skipped.append((archetype, f"Could not parse age from '{archetype}'"))
            continue

        multiple_ext = str(row.get("Multiple Ext Walls", "")).strip().lower() == "yes"
        if multiple_ext:
            missing = [c for c in ["Ext Wall Low", "Ext Wall Medium", "Ext Wall High"]
                       if str(row.get(c, "")).strip().lower() in skip_values]
            if missing:
                print(f"  [WARN] '{archetype}': marked multiple ext walls but missing: {missing}")
        else:
            if str(row.get("Ext Wall", "")).strip().lower() in skip_values:
                print(f"  [WARN] '{archetype}': single ext wall expected but not assigned")

        elements_dict = {}

        # load opaque elements
        for col in element_cols:
            val = row.get(col)
            if pd.isna(val) or str(val).strip().lower() in skip_values:
                continue
            element_code = str(val).strip()
            element = elements_lookup.get(element_code)
            if element is None:
                print(f"  [WARN] '{archetype}': element '{element_code}' was not loaded")
                continue
            elements_dict[element.application] = element

        # load window element
        window_val = row.get("Window element")
        if not pd.isna(window_val) and str(window_val).strip().lower() not in skip_values:
            window_code = str(window_val).strip()
            window = window_lookup.get(window_code)
            if window is None:
                print(f"  [WARN] '{archetype}': window element '{window_code}' was not loaded")
            else:
                elements_dict[BuildingElement.WINDOW] = window

        if not elements_dict:
            skipped.append((archetype, "No elements found"))
            continue

        seen_types = set()
        for app in elements_dict:
            if app in seen_types:
                print(f"  [WARN] '{archetype}': duplicate element type '{app.value}'")
            seen_types.add(app)

        try:
            construction_set = ConstructionSet(
                version_id=uuid4(),
                valid_from_year=age,
                elements=elements_dict,
            )
            building = BuildingArchetype(
                archetype_id=archetype,
                display_name=archetype,
                construction_year=age,
                building_typology="multi_family",
                construction_set=construction_set,
                heating_system="unknown",
                ventilation_system="unknown",
            )
            results.append(building)
        except Exception as e:
            skipped.append((archetype, str(e)))

    print(f"\nBuilding — loaded: {len(results)}, skipped: {len(skipped)}")
    if skipped:
        for name, reason in skipped:
            print(f"  '{name}': {reason}")
    return results