"""Replacement policy placeholder.

Expected responsibilities:
- Nominal service life vs observed replacement lag behavior.
- Deterministic and stochastic replacement decision logic.
"""


def choose_replacement_year(*args, **kwargs):
    """Return replacement timing decision for a component."""
    raise NotImplementedError("Implement replacement policy")
