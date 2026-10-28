"""Small immutable authoring helpers; no catalogue loading or I/O."""

from dataclasses import replace


class Editable:
    """Return a validated replacement; never modify a shared catalogue object."""

    def with_changes(self, **changes):
        """Return a copy with the given fields replaced; the original is unchanged."""
        return replace(self, **changes)
