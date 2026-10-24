"""Game 8.3/14: escrow lifetime, rounding and exactly-once settlement."""

from fractions import Fraction

import pytest

from blacksite.server.market import Bounties, Market
from blacksite.server.rules.market import (BOUNTY_MIN_CHITS, BOUNTY_MIN_TARGET_GRADE,
    BOUNTY_SECONDS, LISTING_EXPIRIES, MARKET_ACTION_SECONDS, MARKET_FEE, fee)


def listing(market: Market, buyout: int | None = 100) -> str:
    return market.list_item('seller', 'exact-instance', 50, buyout, 86400, 0).id


def test_game_8_3_and_14_numbers_and_whole_chit_fee() -> None:
    assert MARKET_FEE == Fraction(5, 100)
    assert LISTING_EXPIRIES == (86400, 259200, 604800)
    assert (BOUNTY_MIN_CHITS, BOUNTY_MIN_TARGET_GRADE, BOUNTY_SECONDS, MARKET_ACTION_SECONDS) == (100, 5, 604800, 1)
    assert [fee(n) for n in (1, 19, 20, 21, 50, 100)] == [1, 1, 1, 2, 3, 5]
    assert fee(10**16+1) == 500000000000001


@pytest.mark.parametrize('value', [0, -1, True, 1.5])
def test_game_8_3_prices_are_positive_whole_chits(value: int) -> None:
    with pytest.raises(ValueError):
        Market('origin').list_item('seller', 'item', value, None, 86400, 0)


def test_game_8_3_only_current_high_bid_remains_held() -> None:
    market = Market('origin')
    lid = listing(market)
    first, old = market.bid(lid, 'one', 60, 1)
    assert old is None
    second, old = market.bid(lid, 'two', 70, 2)
    assert old is first and first.status == 'outbid'
    assert market.highest(lid) is second
    with pytest.raises(ValueError, match='active bid'):
        market.cancel(lid, 'seller', 3)
    sold, refund = market.buyout(lid, 'two', 4)
    assert refund is second and refund.status == 'refunded'
    assert (sold.winner, sold.price, sold.item) == ('two', 100, 'exact-instance')
    assert market.expire(86400) == []
    with pytest.raises(ValueError, match='no longer open'):
        market.buyout(lid, 'one', 5)


def test_game_8_3_bid_cannot_overpay_available_buyout() -> None:
    market = Market('origin')
    lid = listing(market)
    with pytest.raises(ValueError, match='buyout'):
        market.bid(lid, 'buyer', 101, 1)
    assert market.highest(lid) is None


def test_game_8_3_expiry_sells_held_bid_once_after_restart() -> None:
    market = Market('origin')
    lid = listing(market, None)
    market.bid(lid, 'buyer', 60, 1)
    assert not market.expire(86399)
    restored = Market('origin', market.record())
    [(sold, bid)] = restored.expire(86400)
    assert (sold.winner, sold.price, bid.status) == ('buyer', 60, 'won')
    assert not Market('origin', restored.record()).expire(86401)


def test_game_8_3_unsold_expiry_and_cancel_return_exact_instance() -> None:
    market = Market('origin')
    lid = listing(market)
    [(returned, bid)] = market.expire(86400)
    assert returned.item == 'exact-instance' and returned.status == 'expired' and bid is None
    lid2 = market.list_item('seller', 'second-instance', 50, None, 86400, 86401).id
    returned, bid = market.cancel(lid2, 'seller', 86402)
    assert returned.item == 'second-instance' and returned.status == 'cancelled' and bid is None


def test_game_8_3_retiring_bidder_never_revives_refunded_bid() -> None:
    market = Market('origin')
    lid = listing(market)
    market.bid(lid, 'old-bidder', 60, 1)
    winner, _ = market.bid(lid, 'retiring', 70, 2)
    returns, refunds = market.retire('retiring', 3)
    assert not returns and refunds == [winner]
    assert market.highest(lid) is None
    [(returned, bid)] = market.expire(86400)
    assert returned.winner is None and bid is None


def test_game_8_3_retiring_seller_refunds_current_escrow() -> None:
    market = Market('origin')
    lid = listing(market)
    bid, _ = market.bid(lid, 'buyer', 60, 1)
    returns, refunds = market.retire('seller', 2)
    assert returns == [market.listings[lid]] and refunds == [bid]
    assert bid.status == 'refunded'
    assert market.retire('seller', 3) == ([], [])


def test_game_8_3_admin_cancel_refunds_bid_and_preserves_identity() -> None:
    market = Market('origin')
    lid = listing(market)
    bid, _ = market.bid(lid, 'buyer', 60, 1)
    returned, refund = market.cancel(lid, None, 2)
    assert returned.item == 'exact-instance' and refund is bid and bid.status == 'refunded'


def test_game_8_3_bounty_refuses_wake_and_small_amount() -> None:
    bounties = Bounties('origin')
    with pytest.raises(ValueError, match='Nobody pays for a Wake'):
        bounties.post('poster', 'target', 4, 100, 0)
    with pytest.raises(ValueError, match='100 chits'):
        bounties.post('poster', 'target', 5, 99, 0)
    assert not bounties.rows


def test_game_8_3_safe_kill_does_not_settle_bounty() -> None:
    bounties = Bounties('origin')
    row = bounties.post('poster', 'target', 5, 100, 0)
    assert not bounties.claim('target', 'killer', 1, False)
    assert row.status == 'active'


def test_game_8_3_stacked_bounties_pay_killer_and_refund_own_only() -> None:
    bounties = Bounties('origin')
    own = bounties.post('killer', 'target', 5, 100, 0)
    other = bounties.post('other', 'target', 5, 200, 0)
    payments = bounties.claim('target', 'killer', 1, True)
    assert [(row.id, pid, row.status, row.chits) for row, pid in payments] == [
        (own.id, 'killer', 'refunded', 100), (other.id, 'killer', 'claimed', 200)]
    assert not Bounties('origin', bounties.record()).claim('target', 'killer', 2, True)


def test_game_8_3_deadline_refunds_instead_of_paying_late_kill() -> None:
    bounties = Bounties('origin')
    row = bounties.post('poster', 'target', 5, 100, 0)
    assert not bounties.claim('target', 'killer', BOUNTY_SECONDS, True)
    assert bounties.expire(BOUNTY_SECONDS) == [row]
    assert not bounties.expire(BOUNTY_SECONDS)


def test_game_8_3_retiring_target_or_poster_releases_escrow_once() -> None:
    bounties = Bounties('origin')
    first = bounties.post('poster', 'target', 5, 100, 0)
    second = bounties.post('target', 'another', 5, 200, 0)
    assert bounties.retire('target') == [first, second]
    assert not bounties.retire('target')


def test_game_8_3_held_bid_lookup_survives_restore_fork_and_release() -> None:
    market = Market('origin')
    lid = listing(market)
    market.bid(lid, 'first', 60, 1)
    market.bid(lid, 'second', 70, 2)
    restored = Market('origin', market.record())
    assert restored.highest(lid).bidder == 'second'
    fork = restored.fork()
    fork.retire('second', 3)
    assert fork.highest(lid) is None and restored.highest(lid).bidder == 'second'
    fork.bid(lid, 'third', 80, 4)
    assert fork.highest(lid).bidder == 'third'
    restored.buyout(lid, 'buyer', 5)
    assert restored.highest(lid) is None
    assert Market('origin', restored.record()).highest(lid) is None
    market.cancel(lid, None, 6)
    assert market.highest(lid) is None
    another = Market('origin')
    lid = listing(another)
    another.bid(lid, 'winner', 60, 1)
    another.expire(86400)
    assert another.highest(lid) is None


def test_arch_15_2_forks_isolate_live_changes_and_preserve_closed_history() -> None:
    market = Market('origin')
    closed = listing(market)
    market.bid(closed, 'old', 60, 1)
    market.cancel(closed, None, 2)
    active = listing(market)
    market.bid(active, 'bidder', 60, 3)
    before = market.record()
    fork = market.fork()
    fork.bid(active, 'other', 70, 4)
    with pytest.raises(ValueError):
        fork.buyout(closed, 'buyer', 5)
    fork.expire(86400)
    assert market.record() == before
    assert fork.listings[closed].status == 'cancelled'
    assert fork.listings[active].winner == 'other'
    bounties = Bounties('origin')
    old = bounties.post('poster', 'old-target', 5, 100, 0)
    bounties.claim('old-target', 'killer', 1, True)
    live = bounties.post('poster', 'live-target', 5, 200, 2)
    before_bounties = bounties.record()
    proposed = bounties.fork()
    proposed.refund(live.id)
    proposed.retire('poster')
    assert bounties.record() == before_bounties
    assert proposed.rows[old.id].status == 'claimed'
    assert proposed.rows[live.id].status == 'refunded'
