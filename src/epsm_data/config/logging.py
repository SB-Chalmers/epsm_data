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
    level : int or str, optional
        Logger level, default INFO.
    log_file : Path, optional
        Explicit destination for append-mode logging. Parent directories are
        created only when a path is supplied.
    fmt : str, optional
        Log line format.
    date_fmt : str, optional
        Timestamp format.

    Notes
    -----
    Repeated setup replaces only handlers owned by this helper. Conflicting
    foreign handlers are reported before changing configuration. OFF suppresses
    standalone output. The host application owns any other logging setup.
    """
    root_logger = logging.getLogger("epsm_data")
    threshold = logging.CRITICAL + 1 if level == "OFF" else level
    if isinstance(threshold, str):
        threshold = logging.getLevelName(threshold.upper())
    if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold < 0:
        raise ValueError("Use a standard logging level or OFF")
    owned = [h for h in root_logger.handlers if getattr(h, "_epsm_data_owned", False)]
    if any(h not in owned and not isinstance(h, logging.NullHandler) for h in root_logger.handlers):
        raise ValueError("Unmanaged log handlers conflict: epsm_data")
    formatter = logging.Formatter(fmt, datefmt=date_fmt)
    prepared = []
    try:
        if level != "OFF":
            console = logging.StreamHandler(sys.stderr)
            prepared.append(console)
            if log_file is not None:
                log_file = Path(log_file)
                log_file.parent.mkdir(parents=True, exist_ok=True)
                prepared.append(logging.FileHandler(log_file, encoding="utf-8"))
        else:
            prepared.append(logging.NullHandler())
        for handler in prepared:
            handler._epsm_data_owned = True
            handler.setLevel(threshold)
            handler.setFormatter(formatter)
    except BaseException:
        for handler in prepared:
            handler.close()
        raise
    for handler in owned:
        root_logger.removeHandler(handler)
        handler.close()
    root_logger.setLevel(threshold)
    root_logger.propagate = False
    for handler in prepared:
        root_logger.addHandler(handler)
