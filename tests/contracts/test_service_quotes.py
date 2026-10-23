"""Game 7.5/UI 11: an expiring benefit cannot silently raise a bill."""

from tests.server.test_clinics import clinic, review, select
from tests.server.test_substances import give


def test_game_7_5_expired_discount_refreshes_confirmation_without_charge_or_rng_roll(clinic) -> None:
    game, client, player, engine = clinic
    item = give(game, client, 'imp_halvard_reflex_arm')
    factor = [.8]
    engine.service_multiplier = lambda player, vendor: factor[0]
    screen = review(game, client, engine, 'install:'+item+':arms1')
    assert screen.quoted.service_price > 0
    before = player.chits_hand, game.core.world.zones['vatside-clinics'].rng.getstate()
    factor[0] = 1  # The allocation expires before this final keystroke.
    select(game, client, 'y', 'expired-service-quote')
    assert player.chits_hand == before[0]
    assert game.core.world.zones['vatside-clinics'].rng.getstate() == before[1]
    assert not game.core.commerce.pending and not screen.confirm
    assert 'arms1' not in player.implants
    review(game, client, engine, 'install:'+item+':arms1')
    total = screen.quoted.total
    select(game, client, 'y', 'fresh-service-quote')
    game.commit_commerce()
    assert player.chits_hand == before[0]-total
