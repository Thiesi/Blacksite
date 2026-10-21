from pathlib import Path
import pytest
from blacksite.content.loader import load_content
from tests.harness import HeadlessServer


@pytest.fixture
def game(repo_root: Path) -> HeadlessServer:
    return HeadlessServer(load_content(repo_root / "src/blacksite/content"), character_state={})
