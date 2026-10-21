"""Shipped-map fixtures for deterministic S06 simulation checks."""

from pathlib import Path

import pytest

from blacksite.content.loader import ContentTree, load_content
from blacksite.server.world.registry import World
from tests.harness import HeadlessServer


@pytest.fixture(scope="session")
def content_tree() -> ContentTree:
    return load_content(Path(__file__).resolve().parents[2] / "src/blacksite/content")


@pytest.fixture
def world(content_tree: ContentTree) -> World:
    return World(content_tree, {key: index for index, key in enumerate(sorted(content_tree.zones))})


@pytest.fixture
def game(content_tree: ContentTree) -> HeadlessServer:
    return HeadlessServer(content_tree, "vatside-wake-hall")
