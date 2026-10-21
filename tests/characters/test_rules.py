"""Game design 3.1-3.4 / 4: exact numbers, names and identity lease."""

from datetime import datetime, timedelta, timezone
import pytest
from blacksite.server.rules import character as c


@pytest.mark.parametrize("vitals,health", [(1, 52), (20, 90), (40, 130), (100, 250)])
def test_health(vitals: int, health: int) -> None:
    assert c.health_max(vitals) == health


def test_start_tables_derived_values_and_twelve_skills() -> None:
    assert dict(c.ARCHETYPES) == {"hardline": (40,20,15,5,40), "ghost": (15,40,35,10,20), "cantor": (10,20,25,45,25), "operator": (20,30,30,5,30)}
    assert c.stamina_max(40,15) == 77 and c.stamina_max(20,40) == 70
    assert c.tolerance(20) == 4 and c.tolerance(40,"hardline") == 6 and c.tolerance(100) == 10
    assert c.evasion(40) == 13 and c.evasion(40,2) == 15
    assert c.carry_kg(15) == 7.5
    assert sum(len(lines) for _,lines in c.SKILL_GROUPS) == 12
    assert (c.START_CHITS,c.CARD_STANDING,c.SLEEPER_SECONDS,c.SHOCK_DECAY_PER_SECOND) == (200,10,60,5)


def test_skill_groups_and_grade_vitals() -> None:
    values = c.attributes("hardline", {"kinetic": 5, "melee": 3, "armour": 2, "stealth": 30}, grade=5)
    assert values == {"frame":41,"nerve":23,"cortex":15,"resonance":5,"vitals":44}


def test_grade_thresholds_cannot_lose_awarded_grade() -> None:
    assert c.grade_threshold(1) == 0
    assert [c.grade_threshold(g) for g in (5,10,30)] == [1500,5500,46500]
    assert c.grade_for(299) == 1 and c.grade_for(300) == 2
    assert c.grade_for(10**9) == 30 and c.grade_for(0,previous=10) == 10
    assert c.POINTS_PER_GRADE == 3
    assert all(c.grade_threshold(g)<c.grade_threshold(g+1) for g in range(1,30))


def test_personhood_grade_or_ninety_real_days_never_reset() -> None:
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    assert c.legal_at(start,4,start+timedelta(days=89)) is None
    due=c.legal_at(start,1,start+timedelta(days=120))
    assert due == (start+timedelta(days=90)).isoformat()
    early=c.legal_at(start,5,start+timedelta(days=2))
    assert early == (start+timedelta(days=2)).isoformat()
    assert c.legal_at(start,1,start+timedelta(days=100),early)==early


@pytest.mark.parametrize("name,valid", [("界"*12,True),("界"*13,False),("A",False),("A_B-2'",True),("  ",False),("Wake\x1b",False),("Anne É",True)])
def test_name_width_and_characters(name: str, valid: bool) -> None:
    assert c.valid_name(c.normalize_name(name)) is valid
    assert c.name_key("STRASSE") == c.name_key("Straße")


def test_starter_melee_keeps_unspecified_accuracy_but_ranged_requires_it(repo_root: object) -> None:
    from dataclasses import replace
    from blacksite.content.loader import load_content
    from blacksite.content.validate import validate
    content=load_content(repo_root/"src/blacksite/content")
    assert content.items["wpn_kestrel_baton"].weapon.accuracy is None
    ranged=content.items["wpn_kestrel_sidearm"]
    content.items[ranged.id]=replace(ranged,weapon=replace(ranged.weapon,accuracy=None))
    assert any("ranged weapon needs accuracy" in str(problem) for problem in validate(content))
