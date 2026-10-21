"""Game design 6.1: travel, recovery and a bounded escape channel."""

import pytest

from blacksite.server.lattice.presence import (
    EscapeChannel, Presence, directional_neighbour, movement_ticks, recover_integrity,
)


@pytest.mark.parametrize("cortex,ticks",[(0,10),(33,7),(40,6),(80,2),(100,2)])
def test_design_6_1_movement_rounds_up_after_floor(cortex: int, ticks: int) -> None:
    assert movement_ticks(cortex)==ticks


def test_design_6_1_movement_modifier_applies_before_floor() -> None:
    assert movement_ticks(90,2)==2
    assert movement_ticks(40,1.5)==9


def test_design_6_1_one_move_at_a_time_and_tick_delivery() -> None:
    presence=Presence("p","player","core","entrance",("prg_pick","prg_umbrella",None))
    assert presence.integrity==100 and presence.trace==0
    assert presence.begin_move("core","bank",10,40)
    assert not presence.begin_move("core","other",11,40)
    assert presence.arrive(15) is None and presence.cell=="entrance"
    assert presence.arrive(16)==("core","entrance") and presence.cell=="bank"
    assert presence.arrive(17) is None


def test_design_6_1_direction_uses_angle_then_distance() -> None:
    neighbours={"diagonal":(1,1),"right_far":(4,0),"right_near":(2,0),"left":(-1,0)}
    assert directional_neighbour((0,0),neighbours,(1,0))=="right_near"
    assert directional_neighbour((0,0),neighbours,(0,-1)) is None


def test_design_6_1_five_integrity_per_second_caps_at_100() -> None:
    assert recover_integrity(70,20)==80
    assert recover_integrity(99,10)==100
    assert recover_integrity(75,-1)==75


def test_design_6_1_escape_cannot_be_interrupted_forever() -> None:
    channel=EscapeChannel(20,0)
    assert not channel.advance(10,1) and channel.until_tick==30
    assert not channel.advance(20,2) and channel.until_tick==40
    assert not channel.advance(30,3) and channel.until_tick==50
    assert not channel.advance(40,4) and channel.until_tick==50
    assert channel.advance(50,5)


def test_design_6_1_no_damage_finishes_at_two_second_deadline() -> None:
    channel=EscapeChannel(20,0)
    assert not channel.advance(19,0)
    assert channel.advance(20,0)
