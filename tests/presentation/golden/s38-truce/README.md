# S38 truce view contracts

`tests/door/test_truce_render.py` exercises both terminal sizes, both
presentations and all three colour tiers, including the longest keeper
warning. P6 intentionally draws different terrain glyphs at 16 colours,
so each colour has its own glyph contract and corresponding style file.
These use the shared `assert_golden` helper; none is a native capture or
human presentation approval.
