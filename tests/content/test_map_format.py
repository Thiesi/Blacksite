"""S02: the `.map` grid format (04-assets.md section 3)."""

from blacksite.content.formats import dump_map, parse_map

LEGEND = {"#": "wall", ".": "floor", " ": "void", "~": "water"}
CHARS = {v: k for k, v in LEGEND.items()}


def test_round_trip_grid() -> None:
    text = "#####\n#.~.#\n#. .#\n#####\n"
    grid, problems = parse_map(text, "x.map", LEGEND)
    assert problems == []
    assert grid is not None
    assert grid[1] == ("wall", "floor", "water", "floor", "wall")
    assert dump_map(grid, CHARS) == text
    again, _ = parse_map(dump_map(grid, CHARS), "x.map", LEGEND)
    assert again == grid


def test_round_trip_keeps_trailing_space() -> None:
    # A trailing space is a "void" cell here and must survive a dump.
    text = "### \n#.# \n### \n"
    grid, problems = parse_map(text, "x.map", LEGEND)
    assert problems == [] and grid is not None and grid[0][-1] == "void"
    assert dump_map(grid, CHARS) == text


def test_ragged_rows_rejected() -> None:
    grid, problems = parse_map("####\n#..\n####\n", "x.map", LEGEND)
    assert grid is None
    assert [(p.line, "3 wide" in p.message) for p in problems] == [(2, True)]


def test_unknown_glyph_reported_with_line() -> None:
    grid, problems = parse_map("####\n#..#\n#.X#\n####\n", "zones/x.map", LEGEND)
    assert grid is None
    assert len(problems) == 1
    assert problems[0].path == "zones/x.map"
    assert problems[0].line == 3
    assert "column 3" in problems[0].message and "'X'" in problems[0].message


def test_trailing_whitespace_is_significant() -> None:
    # A trailing space is a cell, so this row is wider than the others.
    _, problems = parse_map("####\n#.. \n####\n", "x.map", {"#": "wall", ".": "floor"})
    assert problems and "unknown glyph ' '" in problems[0].message


def test_crlf_line_endings_accepted() -> None:
    lf, _ = parse_map("##\n#.\n", "x.map", LEGEND)
    crlf, problems = parse_map("##\r\n#.\r\n", "x.map", LEGEND)
    assert problems == [] and crlf == lf


def test_wide_glyph_rejected() -> None:
    # 04-assets.md section 3 and S02 notes: map glyphs are one cell wide.
    _, problems = parse_map("##\n#界\n", "x.map", {**LEGEND, "界": "floor"})
    assert problems and "not one cell wide" in problems[0].message


def test_empty_map_rejected() -> None:
    grid, problems = parse_map("", "x.map", LEGEND)
    assert grid is None and problems[0].message == "map is empty"
