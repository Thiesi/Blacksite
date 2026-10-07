"""S02: the shipped content tree validates (grows with every content slice)."""

from blacksite.content.cp437 import round_trips
from blacksite.content.loader import load_content
from blacksite.content.validate import REQUIRED_ROLES, validate
from tests.content.support import SHIPPED

# 04-assets.md section 2 and the gazetteer sketch legend.
STARTER_TILES = {
    "wall", "floor", "cover-1", "cover-2", "cover-3", "door", "locked-door",
    "terminal", "relay", "exit", "water", "hazard", "vendor", "vat", "light",
    "hardware",
}
GAZETTEER_LEGEND = {"#": "wall", ".": "floor", "+": "door", "T": "terminal", "R": "relay",
                    ">": "exit", "~": "water", "!": "hazard", "$": "vendor", "V": "vat", "L": "light"}


def test_shipped_content_validates() -> None:
    tree = load_content(SHIPPED)
    assert validate(tree) == []


def test_shipped_starter_tables() -> None:
    tree = load_content(SHIPPED)
    assert set(tree.tiles) == STARTER_TILES
    for char, tile in GAZETTEER_LEGEND.items():
        assert tree.tiles[tile].char == char
    assert [tree.tiles[f"cover-{n}"].cover for n in (1, 2, 3)] == [1, 2, 3]
    assert tree.palette is not None and REQUIRED_ROLES <= tree.palette.roles.keys()
    assert tree.keymaps is not None
    assert sorted(k.id for k in tree.keymaps.keymaps) == ["arrows", "vi"]


def test_every_glyph_round_trips_cp437() -> None:
    # 03-terminal-ui.md section 1: a test asserts this for glyphs.json.
    tree = load_content(SHIPPED)
    assert tree.glyphs is not None
    for gid, char in tree.glyphs.glyphs.items():
        assert round_trips(char), gid


def test_keymaps_follow_the_table() -> None:
    # 03-terminal-ui.md section 5.1.
    tree = load_content(SHIPPED)
    assert tree.keymaps is not None
    maps = {k.id: k.bindings for k in tree.keymaps.keymaps}
    assert maps["arrows"]["move_up"] == ("up",) and maps["vi"]["move_up"] == ("k",)
    assert maps["arrows"]["move_up_left"] == ("home",) and maps["vi"]["move_down_right"] == ("n",)
    assert maps["vi"]["sprint_left"] == ("H",) and maps["arrows"]["sprint_left"] == ("shift-left",)
    assert maps["arrows"]["jack"] == ("j", "J") and maps["vi"]["jack"] == ("ctrl-o",)
    assert "enter" in maps["arrows"]["chat_say"] and "enter" in maps["vi"]["chat_say"]
    assert maps["vi"]["program_7"] == ("7",) and maps["vi"]["quick_5"] == ("5",)
