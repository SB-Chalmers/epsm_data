"""Synthetic construction fixtures and editable offline shared-registry copies."""

import json
import shutil
from importlib.resources import files

import pytest

from examples.archetype import make_example


@pytest.fixture
def archetype():
    return make_example()


@pytest.fixture
def detailed_copy(tmp_path, request):
    data = {}
    root = files("epsm_data.datasets.layered")
    for name in ("materials", "assemblies", "archetypes", "honeybee", "boverket"):
        path = tmp_path / f"{name}.json"
        shutil.copyfile(root.joinpath(path.name), path)
        data[name] = json.loads(path.read_text())
    return tmp_path, data
