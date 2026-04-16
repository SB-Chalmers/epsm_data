"""JSON reader.

Expected responsibilities:
- Load local material/property JSON files.
- Validate schema shape before handoff.
"""

import json


def read_energyplus_json(json_path: str) -> dict:
    """Load and return the EnergyPlus/Honeybee material properties JSON file.

    Args:
        json_path: Path to the local JSON file.

    Returns:
        Dict keyed by Honeybee material identifier, each containing
        thermal properties (conductivity, density, roughness, etc.).

    Raises:
        FileNotFoundError: If the file does not exist at json_path.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)
    
def read_window_material_json(json_path: str) -> dict:
    """Load the Honeybee window material properties JSON.

    Args:
        json_path: Path to the window_material JSON file.

    Returns:
        Dict keyed by Honeybee material identifier containing
        glazing and gas material properties.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_window_construction_json(json_path: str) -> dict:
    """Load the Honeybee window construction JSON.

    Args:
        json_path: Path to the window_construction JSON file.

    Returns:
        Dict keyed by construction identifier, each containing
        an ordered list of material identifiers.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)
