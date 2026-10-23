"""Synthetic construction fixtures and editable offline shared-registry copies."""

import pytest

from examples.archetype import make_example


@pytest.fixture
def archetype():
    return make_example()
