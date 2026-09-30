"""Test the library boundary, portable records, and meaningful construction cases."""

import importlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from epsm_data import (
    BuildingElement,
    RenovationEvent,
    archetype_from_dict,
    archetype_to_dict,
    build_archetype,
)
from epsm_data.thermal import compute_element_thermal

ROOT = Path(__file__).resolve().parents[1]


def test_base_import_and_examples_without_optional_dependencies():
    script = """
import importlib.abc
import runpy
import sys

class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {
            "pandas", "openpyxl", "requests", "certifi", "matplotlib", "networkx",
            "pyvis", "sqlalchemy", "epsm_core", "pipelines", "ARCHIVE",
        }:
            raise ImportError("optional dependency blocked: " + fullname)

sys.meta_path.insert(0, BlockOptional())
import epsm_data
assert not hasattr(epsm_data, "run_build_baseline")
from epsm_data import load_parametric_catalogue
assert load_parametric_catalogue().summary()["slot_count"] == 1080
for example in sys.argv[1:]:
    runpy.run_path(example, run_name="__main__")
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(ROOT / "examples/archetype.py"),
            str(ROOT / "examples/renovations.py"),
        ],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_roundtrip_preserves_ids_history_and_physics(archetype):
    before = archetype.construction_set
    after = replace(before, version_id=uuid4(), valid_from_year=2030)
    event = RenovationEvent(
        "example.windows",
        2030,
        "user",
        (),
        (),
        before.version_id,
        after.version_id,
        cost_sek=1000,
        embodied_carbon_delta=20,
    )
    changed = archetype.with_renovation(event, after)
    restored = archetype_from_dict(json.loads(json.dumps(archetype_to_dict(changed))))
    assert restored == changed
    assert restored.envelope_u_values == archetype.envelope_u_values
    assert archetype.renovation_log == ()
    assert restored.current_year == 2030


def composite_spec(fractions):
    layer = {"material_id": ["a", "b"], "thickness": 0.2}
    if fractions is not None:
        layer["area_fraction"] = fractions
    return {
        "archetype_id": "COMPOSITE",
        "display_name": "Composite example",
        "construction_year": 1960,
        "building_typology": "multi_family",
        "elements": {
            "EXT_WALL": {
                "components": [
                    {"shearing_layer": "Skin", "layers": [layer]},
                    {
                        "shearing_layer": "Structure",
                        "layers": [
                            {"material_id": "a", "thickness": 0.1},
                        ],
                    },
                ]
            }
        },
    }


def materials(archetype):
    a = archetype.construction_set.elements[BuildingElement.EXT_WALL].components[0].layers[0]
    a = a.layer.materials[0].material
    return {"a": a, "b": replace(a, name="Other", conductivity=0.2, density=800)}


@pytest.mark.parametrize("fractions", [None, [1.0], [0.5, 0.4], [-0.1, 1.1], [float("nan"), 1]])
def test_invalid_composites_are_rejected(archetype, fractions):
    with pytest.raises(ValueError):
        build_archetype(composite_spec(fractions), materials=materials(archetype))


def test_unknown_material_is_not_resolved_implicitly():
    with pytest.raises(KeyError):
        build_archetype(composite_spec([0.5, 0.5]), materials={})


def test_thermal_results_and_unique_layer_ids(archetype):
    arch = build_archetype(composite_spec([0.5, 0.5]), materials=materials(archetype))
    element = arch.construction_set.elements[BuildingElement.EXT_WALL]
    layers = [slot.layer for c in element.components for slot in c.layers]
    assert len({layer.layer_code for layer in layers}) == 2
    expected = 1 / (0.17 + 0.2 / 0.15 + 0.1 / 0.1)
    assert element.u_value == pytest.approx(expected)
    assert compute_element_thermal(element).u_value == pytest.approx(expected)
    assert compute_element_thermal(element).reference_u_value is None
    assert compute_element_thermal(element, reference_u_value=3).reference_warning
    assert archetype_from_dict(archetype_to_dict(arch)) == arch


def test_invalid_record_version_and_role(archetype):
    payload = archetype_to_dict(archetype)
    payload["format_version"] = 999
    with pytest.raises(ValueError):
        archetype_from_dict(payload)
    payload = archetype_to_dict(archetype)
    payload["archetype"]["construction_set"]["elements"]["EXT_WALL"]["application"] = "ROOF"
    with pytest.raises(ValueError):
        archetype_from_dict(payload)


def test_removed_modules_are_not_in_package():
    for name in (
        "epsm_data.lifecycle",
        "epsm_data.domain.scenario",
        "epsm_data.infra.db",
        "epsm_data.governed",
        "epsm_data.archetype_catalogue",
        "epsm_data.layer_packages",
        "epsm_data.calibration",
        "epsm_data.carbon",
        "epsm_data.epsm_core_adapter",
        "epsm_data.datasets.tabula_se",
        "epsm_data.datasets.betsi_layers",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)


def test_optional_graph_supports_window_records(archetype):
    pytest.importorskip("networkx")
    pytest.importorskip("pyvis")
    from epsm_data.infra.graph import build_graph

    graph = build_graph([archetype], list(archetype.construction_set.elements.values()))
    assert graph.nodes[archetype.window.name]["u_value"] == 2.5
    assert graph.has_edge(archetype.archetype_id, archetype.window.name)
