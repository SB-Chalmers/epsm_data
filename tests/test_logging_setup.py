# SPDX-License-Identifier: MIT
# Copyright (c) 2026 EPSM Development contributors
# License: See LICENSE at the project root.
"""Explicit standalone setup updates its owned output without duplication."""

import logging

import pytest

from epsm_data.config.logging import setup_logging


@pytest.fixture(autouse=True)
def restore_logger():
    logger = logging.getLogger("epsm_data")
    original = logger.handlers[:], logger.level, logger.propagate
    logger.handlers = [logging.NullHandler()]
    yield
    for handler in logger.handlers:
        if handler not in original[0]:
            handler.close()
    logger.handlers, logger.level, logger.propagate = original


def test_null_handler_does_not_prevent_explicit_setup(tmp_path, capsys):
    path = tmp_path / "events.log"
    setup_logging(log_file=path)
    logging.getLogger("epsm_data.test").info("Selected construction")
    assert "Selected construction" in capsys.readouterr().err
    assert path.read_text().count("Selected construction") == 1


def test_repeated_setup_changes_levels_and_destination(tmp_path, capsys):
    first, second = tmp_path / "first.log", tmp_path / "second.log"
    setup_logging(log_file=first)
    setup_logging(level="DEBUG", log_file=second)
    logging.getLogger("epsm_data.test").debug("Cache selected")
    assert capsys.readouterr().err.count("Cache selected") == 1
    assert first.read_text() == ""
    assert second.read_text().count("Cache selected") == 1


def test_foreign_handler_conflict_does_not_change_logger():
    logger = logging.getLogger("epsm_data")
    foreign = logging.StreamHandler()
    logger.addHandler(foreign)
    level = logger.level
    with pytest.raises(ValueError, match="epsm_data"):
        setup_logging()
    assert foreign in logger.handlers and logger.level == level
