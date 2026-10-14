"""Compatibility access to cohort inference now owned by epsm_workflows.

No workflow package is imported until an old caller explicitly requests a name.
"""


def __getattr__(name):
    from epsm_workflows import cohorts
    try:
        return getattr(cohorts, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
