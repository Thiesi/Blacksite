"""S02: ID rules (04-assets.md section 8, 00-game-design.md section 17)."""

from blacksite.content.cp437 import CP437_GRAPHIC, round_trips
from blacksite.content.ids import display_width, is_catalog_id, is_slug, valid_id


def test_slug_rules() -> None:
    for good in ("core-plaza", "fx-safe", "text-ration-1", "a", "lat-shaft", "1"):
        assert is_slug(good), good
    for bad in ("Core-Plaza", "core_plaza", "-core", "core-", "core--plaza", "", "core plaza", "zoné"):
        assert not is_slug(bad), bad
    for good in ("wpn_kestrel_sidearm", "prg_pick", "ice_tripwire", "hymn_steady", "ammo_9x"):
        assert is_catalog_id(good), good
    for bad in ("prg", "_pick", "9x_ammo", "prg-pick", "Prg_pick"):
        assert not is_catalog_id(bad), bad
    # Catalog form is accepted only for catalog kinds; zones stay hyphenated.
    assert valid_id("item", "wpn_kestrel_sidearm") and valid_id("item", "fx-item")
    assert valid_id("ice", "ice_tripwire") and valid_id("program", "prg_pick")
    assert not valid_id("zones", "core_plaza")
    assert not valid_id("cores", "lat_shaft")


def test_display_width() -> None:
    # 03-terminal-ui.md section 6: wide characters take two cells.
    assert display_width("a") == 1
    assert display_width("█") == 1
    assert display_width("界") == 2
    assert display_width("Ａ") == 2
    assert display_width("́") == 0


def test_cp437_graphic_table() -> None:
    # 03-terminal-ui.md section 1: glyphs round-trip through CP437 as drawn.
    assert len(CP437_GRAPHIC) == 255
    assert len(set(CP437_GRAPHIC.values())) == 255
    for char in "♦♣♥♠•←↑→↓§█▓▒░▀▄─│┌┐└┘├┤┬┴┼═║╔╗╚╝≡°±·":
        assert round_trips(char), char
    for char in "×✓€界\u0007":
        assert not round_trips(char), char
