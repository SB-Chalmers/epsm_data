# SPDX-License-Identifier: MIT
# Copyright (c) 2026 EPSM Development contributors
# License: See LICENSE at the project root.
"""Public operation logging keeps calculation inputs and host configuration separate."""

import inspect
import logging

from epsm_data import Catalogue


def test_public_operation_accepts_explicit_context():
    parameter = inspect.signature(Catalogue.load).parameters["log_context"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is None


def test_import_does_not_install_output_handlers():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import epsm_data; import logging; assert not any(isinstance(h, logging.StreamHandler) for h in logging.getLogger('epsm_data').handlers)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not result.stdout and not result.stderr


def test_catalogue_load_links_nested_operations(caplog):
    with caplog.at_level(logging.DEBUG):
        catalogue = Catalogue.load(log_context={"study_id": "catalogue-test"})
    assert catalogue.ids()
    records = [r for r in caplog.records if hasattr(r, "epsm_event")]
    root = next(r for r in records if r.epsm_event == "catalogue.load.started")
    assert root.epsm_context["operation_id"]
    assert not any("parametric" in r.epsm_event for r in records)
    assert all(r.epsm_context["study_id"] == "catalogue-test" for r in records)
    assert records[-1].epsm_event == "catalogue.load.completed"


def test_loggers_are_named_after_the_package_area(caplog):
    with caplog.at_level(logging.DEBUG, logger="epsm_data"):
        Catalogue.load().for_year("multi_family", 1960, state="existing")
    names = {record.name for record in caplog.records if getattr(record, "epsm_event", "")}
    assert names == {"epsm_data.catalogue"}
