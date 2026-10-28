"""Module paths from before the package layout, kept importable for one release.

Other packages imported these paths directly. Each name is an alias of the module that
replaced it; new code imports from the package root or the new module instead.
"""

import sys
from types import ModuleType

from .catalogue import catalogue, handover, keys, serialization
from .domain.element import surface_resistances
from .profiles import systems
from .renovation import operations

_MOVED = {
    "classification": keys,
    "library": catalogue,
    "nominal": handover,
    "operations": operations,
    "serialization": serialization,
    "templates": systems,
}


def _boundary_conditions():
    """``epsm_data.thermal.boundary_conditions``, as epsm_core still imports it."""
    module = ModuleType("epsm_data.thermal.boundary_conditions")
    module.get_boundary_resistances = surface_resistances
    module.get_rsi = lambda application: surface_resistances(application)[0]
    module.get_rse = lambda application: surface_resistances(application)[1]
    package = ModuleType("epsm_data.thermal")
    package.boundary_conditions = module
    return package, module


def register(package):
    """Make the old paths resolve to their replacements."""
    for name, module in _MOVED.items():
        sys.modules.setdefault(f"{package.__name__}.{name}", module)
    thermal, boundary = _boundary_conditions()
    sys.modules.setdefault(f"{package.__name__}.thermal", thermal)
    sys.modules.setdefault(f"{package.__name__}.thermal.boundary_conditions", boundary)
