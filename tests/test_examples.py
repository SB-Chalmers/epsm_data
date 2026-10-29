"""Run every example notebook from a fresh kernel."""

import importlib.util
import os
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")
pytest.importorskip("ipykernel")

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
NOTEBOOKS = sorted(EXAMPLES.glob("*.ipynb"))
NEEDS_MATPLOTLIB = {"04_renovation_states_and_sections.ipynb"}


def test_examples_are_present():
    assert [path.name for path in NOTEBOOKS] == [
        "01_select_an_archetype.ipynb",
        "02_operation_and_systems.ipynb",
        "03_author_and_edit.ipynb",
        "04_renovation_states_and_sections.ipynb",
    ]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda path: path.stem)
def test_example_runs(path, monkeypatch):
    if path.name in NEEDS_MATPLOTLIB and importlib.util.find_spec("matplotlib") is None:
        pytest.skip("needs matplotlib (the visualization extra)")
    # The kernel imports this checkout's epsm_data, as the test run does.
    paths = [str(EXAMPLES.parent / "src"), os.environ.get("PYTHONPATH", "")]
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(path for path in paths if path))
    notebook = nbformat.read(path, as_version=4)
    nbclient.NotebookClient(
        notebook,
        timeout=600,
        kernel_name="python3",
        resources={"metadata": {"path": str(EXAMPLES)}},
    ).execute()
