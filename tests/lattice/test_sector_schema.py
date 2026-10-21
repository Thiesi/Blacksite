"""Explicit staged core access never weakens ordinary references."""

from dataclasses import replace

from blacksite.content.loader import load_content
from blacksite.content.schema import Sector, Uplink
from blacksite.content.validate import validate


def test_placeholder_is_explicit_and_cannot_hide_an_active_core(repo_root) -> None:
    content=load_content(repo_root/"tests/fixtures/world")
    sector=content.sectors["fx-sector"]
    cell=next(c for c in sector.cells if c.id=="c-core-b")
    placeholder=replace(cell,core_id=None,core_placeholder=True,planned_core="lat-future")
    content.sectors[sector.id]=replace(sector,cells=tuple(placeholder if c.id==cell.id else c for c in sector.cells))
    assert validate(content)==[]
    content.sectors[sector.id]=replace(sector,cells=tuple(replace(placeholder,planned_core="fx-core-b") if c.id==cell.id else c for c in sector.cells))
    assert any("active core must replace" in p.message for p in validate(content))


def test_placeholder_does_not_allow_missing_normal_reference(repo_root) -> None:
    content=load_content(repo_root/"tests/fixtures/world")
    sector=content.sectors["fx-sector"]
    content.sectors[sector.id]=replace(sector,cells=tuple(replace(c,core_id=None) if c.id=="c-core-b" else c for c in sector.cells))
    assert any("a core entrance needs core_id" in p.message for p in validate(content))


def test_layout_bounds_and_uplink_reciprocity_validate(repo_root) -> None:
    content=load_content(repo_root/"tests/fixtures/world")
    sector=content.sectors["fx-sector"]
    entrance=sector.cells[0]
    other=replace(entrance,id="other",neighbours=(),pos=(0,0))
    content.sectors["other-sector"]=Sector("other-sector","Other",(other,))
    content.sectors[sector.id]=replace(sector,cells=tuple(replace(c,uplink=Uplink("other-sector","other")) if c.id==entrance.id else c for c in sector.cells))
    assert any("uplink is not reciprocal" in p.message for p in validate(content))
    content.sectors["other-sector"]=replace(content.sectors["other-sector"],cells=(replace(other,uplink=Uplink(sector.id,entrance.id),pos=(8,0)),))
    problems=validate(content)
    assert any("outside layout bounds" in p.message for p in problems)
    assert not any("uplink is not reciprocal" in p.message for p in problems)
