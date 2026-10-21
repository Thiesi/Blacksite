"""S01: the package skeleton installs, imports, and runs."""

import importlib
import tomllib
from pathlib import Path

import blacksite
from blacksite import version

PACKAGES = [
    "blacksite",
    "blacksite.version",
    "blacksite.server",
    "blacksite.door",
    "blacksite.admin",
    "blacksite.bot",
    "blacksite.content",
]

def _pyproject(repo_root: Path) -> dict:
    with (repo_root / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)


def test_packages_import() -> None:
    for name in PACKAGES:
        importlib.import_module(name)


def test_version_constants(repo_root: Path) -> None:
    # 02-architecture.md section 5.1 and section 6.2.
    project = _pyproject(repo_root)["project"]
    assert version.PACKAGE_VERSION == project["version"]
    assert blacksite.__version__ == version.PACKAGE_VERSION
    assert version.PROTOCOL_MAJOR == 1
    assert version.CONTENT_SCHEMA == 1
    assert version.WORLD_SCHEMA == 2


def test_no_runtime_dependencies(repo_root: Path) -> None:
    # AGENTS.md section 1 and 02-architecture.md section 14.
    project = _pyproject(repo_root)["project"]
    assert project["dependencies"] == []
    assert project["optional-dependencies"]["test"] == ["pytest"]
