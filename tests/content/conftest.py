"""Fixtures for content tests."""

from pathlib import Path

import pytest

from tests.content.support import World, copy_world


@pytest.fixture
def world(scratch_dir: Path) -> World:
    """A scratch copy of the fixture world to mutate."""
    return copy_world(scratch_dir)
