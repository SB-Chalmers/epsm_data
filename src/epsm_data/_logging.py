# SPDX-License-Identifier: MIT
# Copyright (c) 2026 EPSM Development contributors
# License: See LICENSE at the project root.
"""Package-local standard-library logging helpers; no output on import."""

from __future__ import annotations

import inspect
import logging
from contextvars import ContextVar
from functools import wraps
from time import monotonic
from uuid import uuid4

_context = ContextVar(__name__ + ".context", default=None)
_SELECTED = ("category", "construction_year", "archetype_id", "state", "year")


def operation(event, *, level=logging.INFO):
    """Log started/completed/failed events for a public operation.

    ``log_context`` is an optional keyword-only mapping of scalar identifiers. It
    never enters physical models; nested operations inherit it with a parent id.
    """

    def decorate(function):
        signature = inspect.signature(function)
        logger = logging.getLogger(function.__module__)

        def emit(context, suffix, details, error=None):
            logger.log(logging.ERROR if error is not None else level, "%s %s",
                       event.replace(".", " "), suffix,
                       extra={"epsm_event": f"{event}.{suffix}", "epsm_context": dict(context),
                              "epsm_details": dict(details)})

        @wraps(function)
        def wrapped(*args, log_context=None, **kwargs):
            parent = dict(_context.get() or {}) if log_context is None else dict(log_context)
            if any(not isinstance(key, str) or not isinstance(value, (str, int, bool, type(None)))
                   for key, value in parent.items()):
                raise TypeError("log_context must contain scalar identifiers")
            context = {**parent, "operation_id": uuid4().hex}
            if parent.get("operation_id"):
                context["parent_operation_id"] = parent["operation_id"]
            bound = signature.bind(*args, **kwargs).arguments
            details = {key: bound[key] for key in _SELECTED
                       if isinstance(bound.get(key), (str, int, bool))}
            token = _context.set(context)
            started = monotonic()
            emit(context, "started", details)
            try:
                result = function(*args, **kwargs)
            except Exception as error:
                emit(context, "failed", {**details, "duration_s": monotonic() - started,
                                         "error_type": type(error).__name__}, error)
                raise
            finally:
                _context.reset(token)
            emit(context, "completed", {**details, "duration_s": monotonic() - started})
            return result

        parameters = list(signature.parameters.values())
        index = next((i for i, p in enumerate(parameters) if p.kind == p.VAR_KEYWORD),
                     len(parameters))
        parameters.insert(index, inspect.Parameter("log_context", inspect.Parameter.KEYWORD_ONLY,
                                                   default=None))
        wrapped.__signature__ = signature.replace(parameters=parameters)
        return wrapped

    return decorate
