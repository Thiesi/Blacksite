"""Game design 3.1, 5.3, 5.4: independent numeric examples."""

from blacksite.server.rules import combat as c
import pytest


def test_design_5_3_hit_range_damage_melee_and_rounding() -> None:
    assert c.to_hit(55,20,10,1,5)==40
    assert c.to_hit(999,100,0)==95 and c.to_hit(0,0,999)==5
    assert c.range_penalty(4,8)==0 and c.range_penalty(6,8)==10
    assert c.damage(20,100,10)==20 and c.damage(20,100,10,True)==25
    assert c.damage(1,0,99)==1
    assert c.action_seconds(.8,80,1.5)==pytest.approx(1.8)
    assert c.ticks(1.01)==11 and c.ticks(.8)==8
    assert (c.DOWN_SECONDS,c.DECANT_SECONDS,c.LOOT_PRIVATE_SECONDS,c.CACHE_SECONDS)==(5,20,60,300)


def test_design_5_4_debt_fade_earned_only_and_no_grade_loss() -> None:
    assert c.clone_settlement(1000,5,1700,1500,0)==(900,0,1696,100)
    assert c.clone_settlement(0,5,1500,1500,7)==(0,57,1500,50)
    assert c.earned_chits(100,57)==(75,32)
    assert c.earned_chits(3,32)==(3,32)
