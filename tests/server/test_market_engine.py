"""Game 8.3: real commerce sources, receipts and exact instance delivery."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from blacksite.content.loader import load_content
from blacksite.server.clock import TICK_HZ
from blacksite.server.items import make_item
from blacksite.server.market import Bounties
from blacksite.server.protocol import Frame
from blacksite.server.rules.character import grade_threshold
from blacksite.server.storage.db import Storage
from tests.character_helpers import create, place
from tests.harness import HeadlessServer


@pytest.fixture(scope='module')
def content() -> Any:
    return load_content(Path(__file__).parents[2]/'src/blacksite/content')


@pytest.fixture
def trade_game(content: Any) -> tuple[Any, ...]:
    game = HeadlessServer(content, character_state={})
    clients = []
    for uid in range(1, 5):
        client = game.connect({'user_id': uid, 'handle': f'Market界{uid}', 'node_name': 'test'})
        create(game, client, name=f'Trader界{uid}')
        clients.append(client)
    game.commit_commerce()
    players = [game.core.characters.players[c.session.player_id] for c in clients]
    zone = game.core.world.zones['vatside-wake-hall']
    terminal = next(o.spec for o in zone.objects.values() if o.spec.kind == 'terminal')
    for index, (client, player) in enumerate(zip(clients, players)):
        player.chits_bank = 1000
        player.grade = 2 if index == 3 else 5
        player.xp = grade_threshold(player.grade)
        player.legal_at = game.clock.now_utc().isoformat() if player.grade >= 5 else None
        tile = game.core.world.free_tile(zone.id, terminal.tile)
        assert max(abs(tile[0]-terminal.tile[0]), abs(tile[1]-terminal.tile[1])) <= 1
        place(game, client, zone.id, tile)
    game.commit_commerce()
    template = next(t for t in content.items.values() if t.class_ == 'weapon' and t.weapon.ammo and not t.no_vendor_sale)
    iid = f'{game.core.sessions.origin}:item:{game.core.combat.next_serial()+1}'
    item = make_item(iid, template, players[0].id, game.clock.now_utc().isoformat())
    item.quality, item.ammo, item.secured = 1.12, 3, False
    game.core.commerce.items[item.id] = item
    players[0].inventory.append(item.id)
    return game, clients, players, item.id, terminal.id


def listed(fixture: tuple[Any, ...]) -> str:
    game, clients, _, iid, terminal = fixture
    game.core.market.execute(clients[0].session, 'list', {
        'item': iid, 'price': 50, 'buyout': 100, 'expiry': 86400, 'terminal': terminal})
    game.commit_commerce()
    return next(iter(game.core.market.market.listings))


def test_game_8_3_buyout_reuses_escrow_and_commits_single_treasury(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, iid, terminal = trade_game
    owner = game.core.market
    before = deepcopy(game.core.commerce.items[iid].record())
    lid = listed(trade_game)
    assert iid not in players[0].inventory and game.core.commerce.items[iid].owner == 'market'
    players[1].chits_bank = 100
    owner.execute(clients[1].session, 'bid', {'listing': lid, 'chits': 60, 'terminal': terminal})
    game.commit_commerce()
    assert players[1].chits_bank == 40
    owner.execute(clients[1].session, 'buyout', {'listing': lid, 'terminal': terminal})
    game.commit_commerce()
    assert [p.chits_bank for p in players[:2]] == [1095, 0]
    assert game.core.relays.ledger.totals('kestrel') == {'influence': 0, 'treasury': 5, 'fraction': 0}
    item = game.core.commerce.items[iid].record()
    assert {k: v for k, v in item.items() if k != 'owner'} == {k: v for k, v in before.items() if k != 'owner'}
    entry = owner.lat.interlock.state['impounds'][players[1].id]['items'][iid]
    assert entry == {'fee': 0, 'source': 'market'}
    checkpoint = game.core.relays.ledger.fork()
    checkpoint.settle(game.core.relays.rates(), game.core.relays.now()+3600)
    assert game.core.relays.write(checkpoint)
    game.commit_commerce()
    assert game.core.relays.ledger.totals('kestrel')['treasury'] == 5
    owner.execute(clients[1].session, 'buyout', {'listing': lid, 'terminal': terminal})
    assert not game.core.commerce.pending
    assert players[1].chits_bank == 0


def test_game_8_3_failed_buyout_preserves_escrow_goods_and_retry(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, iid, terminal = trade_game
    owner = game.core.market
    lid = listed(trade_game)
    owner.execute(clients[1].session, 'bid', {'listing': lid, 'chits': 60})
    game.commit_commerce()
    owner.execute(clients[2].session, 'buyout', {'listing': lid})
    game.commit_commerce(error=True)
    assert owner.market.listings[lid].status == 'open'
    assert owner.market.highest(lid).bidder == players[1].id
    assert [p.chits_bank for p in players[:3]] == [1000, 940, 1000]
    assert game.core.commerce.items[iid].owner == 'market'
    owner.execute(clients[2].session, 'buyout', {'listing': lid})
    game.commit_commerce()
    assert [p.chits_bank for p in players[:3]] == [1095, 1000, 900]
    assert game.core.commerce.items[iid].owner == 'impound:'+players[2].id


def test_game_8_3_raising_own_bid_charges_difference(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, _, _ = trade_game
    lid = listed(trade_game)
    players[1].chits_bank = 100
    for amount in (60, 70):
        game.core.market.execute(clients[1].session, 'bid', {'listing': lid, 'chits': amount})
        game.commit_commerce()
    assert players[1].chits_bank == 30


def test_game_8_3_collect_preserves_instance_and_refuses_overweight(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, iid, terminal = trade_game
    owner = game.core.market
    lid = listed(trade_game)
    owner.execute(clients[1].session, 'buyout', {'listing': lid})
    game.commit_commerce()
    before = deepcopy(game.core.commerce.items[iid].record())
    players[1].attributes['frame'] = 0
    owner.execute(clients[1].session, 'collect', {'item': iid})
    assert not game.core.commerce.pending
    assert game.core.commerce.items[iid].record() == before
    players[1].attributes['frame'] = 100
    owner.execute(clients[1].session, 'collect', {'item': iid, 'terminal': terminal})
    game.commit_commerce()
    assert iid in players[1].inventory and game.core.commerce.items[iid].owner == players[1].id
    assert {k: v for k, v in game.core.commerce.items[iid].record().items() if k != 'owner'} == {k: v for k, v in before.items() if k != 'owner'}
    assert players[1].chits_bank == 900
    # The seller sees the listing snapshot, not a buyer's later condition.
    game.core.commerce.items[iid].ammo = 0
    assert owner.views.listing_item(owner.market.listings[lid]).ammo == 3
    game.core.commerce.items.pop(iid)
    from blacksite.server.market_views import Panel
    panel = Panel('market', terminal, 0, mine=True)
    assert owner.views.body(clients[0].session, panel)['rows'][0]['id'] == lid


def test_game_8_3_restricted_items_never_leave_inventory(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, iid, _ = trade_game
    item = game.core.commerce.items[iid]
    for field, value in (('secured', True), ('bound', True), ('mission', 'contract:one')):
        setattr(item, field, value)
        game.core.market.execute(clients[0].session, 'list', {'item': iid, 'price': 50, 'expiry': 86400})
        assert not game.core.commerce.pending and iid in players[0].inventory
        setattr(item, field, None if field == 'mission' else False)


def test_game_8_3_terminal_permissions_rechecked_for_delivery(trade_game: tuple[Any, ...], monkeypatch: Any) -> None:
    game, clients, players, iid, terminal = trade_game
    lid = listed(trade_game)
    game.core.market.execute(clients[1].session, 'buyout', {'listing': lid})
    game.commit_commerce()
    previous = game.core.world.object_access
    monkeypatch.setattr(game.core.world, 'object_access', lambda actor, spec: False if spec.id == terminal else previous(actor, spec))
    game.core.market.execute(clients[1].session, 'collect', {'item': iid, 'terminal': terminal})
    assert not game.core.commerce.pending and iid not in players[1].inventory
    assert iid in game.core.market.lat.interlock.state['impounds'][players[1].id]['items']


def test_game_8_3_expiry_persists_delivery_and_never_pays_twice(trade_game: tuple[Any, ...], tmp_path: Path) -> None:
    game, clients, players, iid, _ = trade_game
    lid = listed(trade_game)
    game.core.market.execute(clients[1].session, 'bid', {'listing': lid, 'chits': 60})
    game.commit_commerce()
    game.clock.advance(86400*TICK_HZ)
    game.core.market.expire()
    effects = game.commit_commerce()
    assert [p.chits_bank for p in players[:2]] == [1057, 940]
    store = Storage(tmp_path/'world.db', game.clock)
    try:
        for effect in effects:
            store.commerce_write(effect)
        saved = store.character_state()
        row = next(v for v in saved['market']['listings'] if v['id'] == lid)
        assert row['status'] == 'sold' and row['price'] == 60
        assert saved['relays']['factions']['kestrel']['treasury'] == 3
        assert saved['interlock']['impounds'][players[1].id]['items'][iid]['fee'] == 0
        assert next(v for v in saved['items'] if v['id'] == iid)['quality'] == 1.12
    finally:
        store.close()
    game.core.market.expire()
    assert not game.core.commerce.pending and players[0].chits_bank == 1057


def test_game_8_3_bounty_refuses_wake_without_escrow(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, _, _ = trade_game
    game.core.market.execute(clients[0].session, 'post', {'target': players[3].id, 'chits': 200})
    assert not game.core.commerce.pending and players[0].chits_bank == 1000
    assert not game.core.market.bounties.rows


def test_game_8_3_actual_death_source_pays_bounty_after_commit(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, _, _ = trade_game
    owner = game.core.market
    owner.execute(clients[0].session, 'post', {'target': players[1].id, 'chits': 200})
    game.commit_commerce()
    place(game, clients[1], 'vatside-clinics', (32, 18))
    players[1].progress['combat'] = {'stage': 'down', 'killer': players[2].id, 'until': 0}
    actor = game.core.combat.actor(players[1])
    game.core.combat.die(players[1], actor)
    assert players[2].chits_bank == 1000 and next(iter(owner.bounties.rows.values())).status == 'active'
    game.commit_commerce(error=True)
    assert players[2].chits_bank == 1000 and next(iter(owner.bounties.rows.values())).status == 'active'
    game.core.combat.die(players[1], actor)
    game.commit_commerce()
    assert players[2].chits_bank == 1200 and players[0].chits_bank == 800
    assert not Bounties(game.core.sessions.origin, owner.bounties.record()).claim(players[1].id, players[2].id, owner.now(), True)


def test_game_8_3_retirement_releases_others_escrow_before_delete(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, iid, _ = trade_game
    owner = game.core.market
    lid = listed(trade_game)
    owner.execute(clients[1].session, 'bid', {'listing': lid, 'chits': 60})
    game.commit_commerce()
    owner.execute(clients[2].session, 'post', {'target': players[0].id, 'chits': 200})
    game.commit_commerce()
    proceeded = []
    owner.prepare_retirement(clients[0].session, players[0], lambda: proceeded.append(True))
    assert not proceeded and players[1].chits_bank == 940 and players[2].chits_bank == 800
    game.commit_commerce(error=True)
    assert not proceeded and owner.market.listings[lid].status == 'open'
    owner.prepare_retirement(clients[0].session, players[0], lambda: proceeded.append(True))
    game.commit_commerce()
    assert proceeded == [True]
    assert players[1].chits_bank == 1000 and players[2].chits_bank == 1000
    assert owner.market.listings[lid].status == 'cancelled'
    assert iid in players[0].inventory and game.core.commerce.items[iid].owner == players[0].id


def test_arch_15_2_bounty_post_queued_behind_death_keeps_both_sources(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, _, _ = trade_game
    owner = game.core.market
    owner.execute(clients[0].session, 'post', {'target': players[1].id, 'chits': 200})
    game.commit_commerce()
    original = next(iter(owner.bounties.rows))
    place(game, clients[1], 'vatside-clinics', (32, 18))
    players[1].progress['combat'] = {'stage': 'down', 'killer': players[2].id, 'until': 0}
    game.core.combat.die(players[1], game.core.combat.actor(players[1]))
    assert game.core.commerce.pending and owner.bounties.rows[original].status == 'active'
    owner.request(clients[0].session, 'post', {'target': players[2].id, 'chits': 100})
    assert game.core.commerce.waiting and len(owner.bounties.rows) == 1
    game.commit_commerce()
    assert owner.bounties.rows[original].status == 'claimed'
    active = [row for row in owner.bounties.rows.values() if row.status == 'active']
    assert len(active) == 1 and active[0].target == players[2].id and active[0].chits == 100
    assert players[0].chits_bank == 700 and players[2].chits_bank == 1200
