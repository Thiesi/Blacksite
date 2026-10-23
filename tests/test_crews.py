"""Game 10: live rules, consent races, frozen offers and grade scaling."""
from fractions import Fraction
import pytest

from blacksite.server.clock import TICK_HZ
from blacksite.server.crews import Registry, share_multiplier, shared_xp


def party(count=2):
    reg = Registry('origin', 'boot')
    crew = reg.accept('b', reg.invite('a', 'b', 0).id, 0)
    for member in 'cde'[:count-2]:
        reg.accept(member, reg.invite('a', member, 0).id, 0)
    return reg, crew


def test_game_10_first_consent_creates_two_members_not_a_one_person_crew():
    reg = Registry('origin', 'boot')
    invite = reg.invite('a', 'b', 0)
    assert not reg.crews and reg.crew_of('a') is None
    with pytest.raises(ValueError, match='available'):
        reg.accept('stranger', invite.id, 1)
    crew = reg.accept('b', invite.id, 1)
    assert crew.members == ('a', 'b') and crew.leader == 'a'
    assert reg.together('a', 'b') and not reg.together('a', 'stranger')


def test_game_10_invite_expires_after_exactly_60_seconds_and_retry_does_not_extend():
    reg = Registry('origin', 'boot')
    invite = reg.invite('a', 'b', 0)
    assert reg.invite('a', 'b', 59*TICK_HZ).until_tick == invite.until_tick
    with pytest.raises(ValueError, match='expired'):
        reg.accept('b', invite.id, 60*TICK_HZ)
    newer = reg.invite('a', 'b', 60*TICK_HZ)
    assert reg.accept('b', newer.id, 120*TICK_HZ-1).members == ('a', 'b')


def test_game_10_existing_outstanding_invites_follow_first_created_crew():
    reg = Registry('origin', 'boot')
    one, two = reg.invite('a', 'b', 0), reg.invite('a', 'c', 0)
    crew = reg.accept('b', one.id, 1)
    assert reg.accept('c', two.id, 2) is crew
    assert crew.members == ('a', 'b', 'c')


def test_game_10_accepting_a_different_crew_revokes_outgoing_invites():
    reg = Registry('origin', 'boot')
    outgoing = reg.invite('b', 'c', 0)
    reg.accept('b', reg.invite('a', 'b', 0).id, 1)
    with pytest.raises(ValueError, match='available'):
        reg.accept('c', outgoing.id, 2)
    assert reg.crew_of('c') is None


def test_game_10_size_five_is_rechecked_at_accept_not_just_invite():
    reg, crew = party(4)
    one, two = reg.invite('a', 'e', 1), reg.invite('a', 'f', 1)
    reg.accept('e', one.id, 2)
    with pytest.raises(ValueError, match='filled'):
        reg.accept('f', two.id, 2)
    assert len(crew.members) == 5 and reg.crew_of('f') is None
    with pytest.raises(ValueError, match='five'):
        reg.invite('a', 'g', 3)


def test_game_10_leader_only_kick_promote_and_member_invites_require_permission():
    reg, crew = party(3)
    with pytest.raises(ValueError, match='leader'):
        reg.invite('b', 'd', 1)
    with pytest.raises(ValueError, match='leader'):
        reg.kick('b', 'a')
    reg.invitations_allowed('a', True)
    offer = reg.invite('b', 'd', 1)
    reg.invitations_allowed('a', False)
    with pytest.raises(ValueError, match='approval'):
        reg.accept('d', offer.id, 2)
    reg.promote('a', 'c')
    with pytest.raises(ValueError, match='leader'):
        reg.promote('a', 'b')
    assert crew.leader == 'c'


def test_game_10_leader_disconnect_chooses_longest_serving_without_reordering_promotion():
    reg, crew = party(4)
    original = crew.members
    reg.promote('a', 'c')
    change = reg.remove('c')
    assert change.leader == crew.leader == 'a'
    assert crew.members == ('a', 'b', 'd') and original == ('a', 'b', 'c', 'd')
    assert reg.remove('a').leader == 'b'


def test_game_10_single_remainder_dissolves_and_pending_invites_do_not_restore_it():
    reg, crew = party()
    offer = reg.invite('a', 'c', 1)
    change = reg.leave('b')
    assert change.dissolved and not reg.crews and not reg.memberships
    with pytest.raises(ValueError, match='available'):
        reg.accept('c', offer.id, 2)
    assert reg.remove('unknown') is None


def test_game_10_only_operator_in_same_crew_sets_one_beacon_and_leaving_clears_it():
    reg, crew = party(3)
    with pytest.raises(ValueError, match='Operator'):
        reg.beacon('a', 'b', False)
    with pytest.raises(ValueError, match='own crew'):
        reg.beacon('a', 'stranger', True)
    reg.beacon('a', 'b', True)
    assert crew.beacon == ('a', 'b')
    reg.beacon('a', None, True)
    assert crew.beacon is None
    reg.beacon('c', 'a', True)
    assert crew.beacon == ('c', 'a')
    reg.leave('c')
    assert crew.beacon is None


def test_game_10_round_robin_offer_waits_10_seconds_and_rotation_commits_once():
    reg, crew = party(3)
    reg.loot_mode('a', 'round_robin')
    offer = reg.offer('a', 0)
    assert offer.recipient == 'a' and offer.permits('a', 0)
    assert not offer.permits('b', 10*TICK_HZ-1)
    assert offer.permits('b', 10*TICK_HZ)
    assert reg.offer('a', 1).recipient == 'a'  # Rejected/uncommitted receipt.
    assert reg.commit_offer(offer) and not reg.commit_offer(offer)
    assert reg.offer('a', 2).recipient == 'b'
    reg.loot_mode('a', 'ffa')
    assert not offer.permits('b', 1)  # A mode change cannot rewrite this drop.
    assert reg.offer('a', 3).permits('b', 3)


def test_game_10_rotation_keeps_next_member_when_an_earlier_member_leaves():
    reg, crew = party(4)
    reg.loot_mode('a', 'round_robin')
    reg.commit_offer(reg.offer('a', 0))  # Next b.
    reg.leave('a')
    assert reg.offer('b', 1).recipient == 'b'
    old = reg.offer('b', 1)
    reg.leave('b')
    assert old.members == ('b', 'c', 'd') and reg.commit_offer(old)
    assert reg.offer('c', 2).recipient == 'c'


def test_game_10_new_boot_cannot_reuse_a_previous_crew_id():
    first, old = party()
    second = Registry('origin', 'next-boot')
    fresh = second.accept('b', second.invite('a', 'b', 0).id, 0)
    assert old.id != fresh.id and not second.commit_offer(first.offer('a', 1))


@pytest.mark.parametrize('gap,expected', [(0, 1), (5, 1), (6, Fraction(19, 20)),
                                         (15, Fraction(1, 2)), (20, Fraction(1, 4)), (29, Fraction(1, 4))])
def test_game_10_shared_xp_uses_only_grade_gap_and_rounds_down(gap, expected):
    assert share_multiplier(1, 1+gap) == share_multiplier(1+gap, 1) == expected
    assert shared_xp(21, 1, 1+gap) == int(21*expected)
    assert shared_xp(0, 1, 1+gap) == 0
