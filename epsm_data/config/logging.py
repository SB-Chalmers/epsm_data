"""Centralized logging configuration for epsm_data.

Call ``setup_logging()`` once at your entry point to configure console
and (optionally) file logging with consistent formatting.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_DEFAULT_FMT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DEFAULT_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    *,
    level: int | str = logging.INFO,
    log_file: Path | None = None,
    fmt: str = _DEFAULT_FMT,
    date_fmt: str = _DEFAULT_DATE_FMT,
) -> None:
    """Configure the ``epsm_data`` logger hierarchy.

    Parameters
    ----------
    level : Root log level (default INFO).
    log_file : If given, also write to this file (append mode).
    fmt : Log line format.
    date_fmt : Timestamp format.
    """
    root_logger = logging.getLogger("epsm_data")
    root_logger.setLevel(level)

    # Avoid adding duplicate handlers on repeated calls
    if root_logger.handlers:
        return

    formatter = logging.Formatter(fmt, datefmt=date_fmt)

    # Console handler — stderr
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    # File handler — optional
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
