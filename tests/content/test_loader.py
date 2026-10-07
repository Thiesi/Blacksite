"""S02: loading, overrides, and the content hash (02-architecture.md 2.4, 6.3)."""

import shutil
from pathlib import Path

from blacksite.content.loader import content_hash, load_content
from tests.content.support import FIXTURE_WORLD, World, find


def test_fixture_loads() -> None:
    tree = load_content(FIXTURE_WORLD)
    assert tree.load_problems == []
    assert sorted(tree.zones) == ["fx-open", "fx-safe", "fx-street"]
    assert sorted(tree.sectors) == ["fx-sector"]
    assert sorted(tree.cores) == ["fx-core-a", "fx-core-b"]
    assert len(tree.items) == 4 and len(tree.ice) == 2 and len(tree.programs) == 3
    assert len(tree.npcs) == 2 and len(tree.factions) == 2
    assert len(tree.contracts) == 1 and len(tree.events) == 1
    assert len(tree.text) == 1 and len(tree.art) == 1
    street = tree.zones["fx-street"]
    assert (street.width, street.height) == (60, 24)
    assert street.tile_at((58, 6)) == "door"
    assert len(tree.hash) == 64


def test_local_override_wins_by_id(world: World, scratch_dir: Path) -> None:
    local = World(scratch_dir / "local")
    sidearm = find(world.read("items.json")["items"], "wpn_kestrel_sidearm")
    sidearm["weapon"]["damage"] = 99
    local.write("items.json", {"schema": 1, "items": [sidearm]})
    local.write("zones/fx-open.json", world.read("zones/fx-open.json") | {"name": "Overridden Waste"})
    shutil.copy(world.path("zones/fx-open.map"), local.path("zones/fx-open.map"))

    tree = load_content(world.root, local.root)
    assert tree.load_problems == []
    assert tree.items["wpn_kestrel_sidearm"].weapon.damage == 99
    assert tree.items["ammo_9x"].stack_max == 50  # not overridden, still there
    assert tree.zones["fx-open"].meta.name == "Overridden Waste"
    assert tree.source("items", "wpn_kestrel_sidearm") == "content.local/items.json"
    assert tree.source("items", "ammo_9x") == "content/items.json"
    assert tree.hash != load_content(world.root).hash


def test_local_zone_needs_both_files(world: World, scratch_dir: Path) -> None:
    local = World(scratch_dir / "local")
    local.write("zones/fx-open.json", world.read("zones/fx-open.json"))
    tree = load_content(world.root, local.root)
    assert any("needs both .json and .map" in p.message for p in tree.load_problems)


def test_hash_stable_across_order(scratch_dir: Path) -> None:
    files = {"a.json": b"1", "zones/b.json": b"2", "text/c.md": b"3"}
    first, second = scratch_dir / "first", scratch_dir / "second"
    for root, order in ((first, sorted(files)), (second, sorted(files, reverse=True))):
        for rel in order:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(files[rel])
    assert content_hash(first) == content_hash(second)
    (second / "text/c.md").write_bytes(b"4")
    assert content_hash(first) != content_hash(second)


def test_hash_covers_paths_and_layers(scratch_dir: Path) -> None:
    a, b = scratch_dir / "a", scratch_dir / "b"
    for root, name in ((a, "one.json"), (b, "two.json")):
        root.mkdir()
        (root / name).write_bytes(b"same bytes")
    assert content_hash(a) != content_hash(b)  # same bytes, different path
    empty = scratch_dir / "empty"
    empty.mkdir()
    # The same file in the shipped layer or the local layer hashes differently.
    assert content_hash(a, empty) != content_hash(empty, a)


def test_hash_ignores_package_files(scratch_dir: Path) -> None:
    root = scratch_dir / "tree"
    root.mkdir()
    (root / "tiles.json").write_bytes(b"{}")
    before = content_hash(root)
    (root / "README.md").write_text("notes")
    (root / "__init__.py").write_text("")
    assert content_hash(root) == before


def test_bad_json_reports_line(world: World) -> None:
    world.write_text("ice.json", '{\n  "schema": 1,\n  "ice": [\n    {"id": }\n  ]\n}\n')
    problems = world.load().load_problems
    assert len(problems) == 1
    assert problems[0].path == "content/ice.json" and problems[0].line == 4


def test_wrong_type_names_field_and_line(world: World) -> None:
    world.edit("ice.json", lambda d: find(d["ice"], "ice_ticker").update(trigger="sometimes"))
    problems = world.load().load_problems
    assert len(problems) == 1
    assert "ice[1].trigger" in problems[0].message and "is not one of" in problems[0].message
    assert problems[0].line == world.path("ice.json").read_text().splitlines().index(
        '      "trigger": "sometimes",') + 1


def test_unknown_field_rejected(world: World) -> None:
    world.edit("zones/fx-safe.json", lambda d: d.update(colour="red"))
    assert any("colour: unknown field" in p.message for p in world.load().load_problems)


def test_duplicate_id_in_table(world: World) -> None:
    world.edit("items.json", lambda d: d["items"].append(dict(d["items"][0])))
    assert any("duplicate items id 'wpn_kestrel_sidearm'" in p.message for p in world.load().load_problems)


def test_file_name_must_match_id(world: World) -> None:
    world.edit("sectors/fx-sector.json", lambda d: d.update(id="fx-other"))
    assert any("file name must be fx-other.json" in p.message for p in world.load().load_problems)


def test_local_terminal_tables_merge(world: World, scratch_dir: Path) -> None:
    local = World(scratch_dir / "local")
    local.write("glyphs.json", {"schema": 1, "glyphs": {"extra": "♣"}})
    palette = world.read("palette.json")
    local.write("palette.json", {"schema": 1, "roles": {"wall": palette["roles"]["floor"]}})
    keymaps = world.read("keymaps.json")
    vi = find(keymaps["keymaps"], "vi")
    vi["bindings"]["help"] = ["F1"]
    local.write("keymaps.json", {"schema": 1, "actions": {}, "keymaps": [vi]})
    tree = load_content(world.root, local.root)
    assert tree.load_problems == []
    assert tree.glyphs.glyphs["extra"] == "♣" and tree.glyphs.glyphs["wall"] == "█"
    assert tree.palette.roles["wall"] == tree.palette.roles["floor"]
    assert "cover" in tree.palette.roles
    maps = {k.id: k for k in tree.keymaps.keymaps}
    assert maps["vi"].bindings["help"] == ("F1",) and maps["arrows"].bindings["help"] == ("?",)
    assert "fire" in tree.keymaps.actions


def test_malformed_asymmetries(world: World) -> None:
    world.edit("factions.json", lambda d: d.update(asymmetries=[["fx-alpha"]]))
    assert any("must be a pair of faction ids" in p.message for p in world.load().load_problems)
    world.edit("factions.json", lambda d: d.update(asymmetries="fx-alpha"))
    assert any("asymmetries must be a list of pairs" in p.message for p in world.load().load_problems)


def test_missing_root(scratch_dir: Path) -> None:
    tree = load_content(scratch_dir / "nothing")
    assert [p.message for p in tree.load_problems] == ["content directory does not exist"]


def test_sidecar_without_art(world: World) -> None:
    world.path("art/art-fx-sigil.ans").unlink()
    assert any("sidecar without art-fx-sigil.ans" in p.message for p in world.load().load_problems)


def test_table_shape_problems(world: World) -> None:
    world.write_text("npcs.json", "[]\n")
    world.write("hymns.json", {"schema": 1, "hymn": []})
    world.write("routes.json", {"schema": 2, "routes": []})
    world.edit("items.json", lambda d: d["items"][0].update(schema=2))
    messages = [p.message for p in world.load().load_problems]
    assert "top level must be an object" in messages
    assert 'missing list "hymns"' in messages
    assert "schema must be 1" in messages
    assert any("items[0].schema: is 2, this build reads 1" in m for m in messages)


def test_loader_is_not_imported_by_the_door() -> None:
    # S02 notes: content is read by the server only.
    import blacksite.door
    import blacksite.door.__main__  # noqa: F401
    import sys

    door_modules = [m for m in sys.modules if m.startswith("blacksite.door")]
    assert door_modules
    for name in door_modules:
        source = Path(sys.modules[name].__file__ or "").read_text(encoding="utf-8")
        assert "blacksite.content" not in source
