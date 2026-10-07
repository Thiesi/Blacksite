"""S02 review fixes: precise lines, strict JSON, stray files, bundle
dependencies, and bounded effect checks."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest

from blacksite.content.formats import DecodeError, decode, locate_path, parse_json
from blacksite.content.loader import load_content
from tests.content.support import World, find


def test_line_points_at_the_field_in_a_one_record_file(world: World) -> None:
    # `neighbours` appears in every room; the error must name the right one.
    world.edit("cores/fx-core-b.json", lambda d: find(d["rooms"], "r-vault").update(neighbours="oops"))
    problems = world.load().load_problems
    assert len(problems) == 1 and "rooms[1].neighbours" in problems[0].message
    lines = world.path("cores/fx-core-b.json").read_text().splitlines()
    assert lines[problems[0].line - 1].strip() == '"neighbours": "oops",'


def test_missing_field_points_at_its_record(world: World) -> None:
    world.edit("cores/fx-core-b.json", lambda d: find(d["rooms"], "r-ice").pop("neighbours"))
    problem = world.load().load_problems[0]
    assert "rooms[2].neighbours: missing" in problem.message
    lines = world.path("cores/fx-core-b.json").read_text().splitlines()
    assert lines[problem.line - 1].strip() == "{" and '"r-ice"' in lines[problem.line]


def test_locate_path_walks_arrays_and_objects() -> None:
    text = '{\n "a": [\n  {"b": 1},\n  {"b": 2,\n   "c": [3, 4]}\n ]\n}\n'
    assert locate_path(text, "a[0].b") == 3
    assert locate_path(text, "a[1].c") == 5
    assert locate_path(text, "a[1].zzz") == 4


def test_duplicate_json_key_rejected() -> None:
    data, problems = parse_json('{\n  "tier": 1,\n  "tier": 2\n}\n', "ice.json")
    assert data is None and "duplicate key 'tier'" in problems[0].message and problems[0].line == 2


def test_nan_rejected() -> None:
    data, problems = parse_json('{"weight": NaN}', "items.json")
    assert data is None and "NaN is not a number" in problems[0].message


@dataclass(frozen=True)
class _One:
    level: Literal[1, 2]


def test_literal_does_not_accept_bool() -> None:
    assert decode(_One, {"level": 1}).level == 1
    with pytest.raises(DecodeError):
        decode(_One, {"level": True})


def test_stray_files_reported(world: World) -> None:
    world.write("item.json", {"schema": 1, "items": []})
    world.write_text("zones/fx-open.txt", "notes")
    world.write_text("dialogue/oops.txt", "notes")
    world.write_text("text/deep/nested.md", "x")
    stray = sorted(p.path for p in world.load().load_problems if "not a content file" in p.message)
    assert stray == ["content/dialogue/oops.txt", "content/item.json",
                     "content/text/deep/nested.md", "content/zones/fx-open.txt"]


def test_readme_is_not_stray(world: World) -> None:
    world.write_text("README.md", "notes")
    assert world.messages() == []


def test_missing_local_directory_reported(world: World, scratch_dir: Path) -> None:
    tree = load_content(world.root, scratch_dir / "no-such-dir")
    assert [p.message for p in tree.load_problems] == ["local override directory does not exist"]


def test_text_asset_in_both_formats(world: World) -> None:
    world.write_text("text/text-fx-gate-1.txt", "plain")
    assert any("exists as both .md and .txt" in p.message for p in world.load().load_problems)


def test_bundle_must_declare_bundles_it_uses(world: World) -> None:
    # Move the ammo into its own active bundle; the sidearm in fx-world uses it.
    world.edit("bundles/fx-world.json", lambda d: d["members"]["items"].remove("ammo_9x"))
    world.write("bundles/fx-ammo.json", {"schema": 1, "id": "fx-ammo", "status": "active",
                                         "members": {"items": ["ammo_9x"]}})
    messages = world.messages()
    assert messages and all("which bundle 'fx-world' does not depend on" in m for m in messages)
    world.edit("bundles/fx-world.json", lambda d: d.update(depends=["fx-ammo"]))
    assert world.messages() == []


def test_bundle_dependency_is_transitive(world: World) -> None:
    world.edit("bundles/fx-world.json", lambda d: (d["members"]["items"].remove("ammo_9x"),
                                                   d.update(depends=["fx-mid"])))
    world.write("bundles/fx-mid.json", {"schema": 1, "id": "fx-mid", "status": "active",
                                        "depends": ["fx-ammo"], "members": {}})
    world.write("bundles/fx-ammo.json", {"schema": 1, "id": "fx-ammo", "status": "active",
                                         "members": {"items": ["ammo_9x"]}})
    assert world.messages() == []


def test_huge_effect_region_is_bounded(world: World) -> None:
    world.edit("events.json", lambda d: d["events"][0]["effects"][0].update(
        region={"x": 0, "y": 0, "w": 1000000, "h": 1000}))
    start = time.monotonic()
    messages = world.messages()
    assert time.monotonic() - start < 10
    assert any("effect 0: region is outside fx-open" in m for m in messages)


def test_number_argument_rejects_double_minus(world: World) -> None:
    world.edit("contracts.json", lambda d: d["contracts"][0].update(unlock_conditions=["grade_at_least --5"]))
    assert any("'--5' is not a number" in m for m in world.messages())
