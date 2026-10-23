"""Game 8.3/14 and architecture 15.2: admission, replay and SQLite atomicity."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from blacksite.server.clock import TICK_HZ
from blacksite.server.protocol import Frame
from blacksite.server.storage import migrations
from blacksite.server.storage.db import Storage
from tests.character_helpers import act
from tests.server.test_market_engine import content, listed, trade_game


def request(game: Any, caller: Any, name: str, args: dict[str, Any], nonce: str) -> Frame:
    return Frame('intent', {'name': name, 'args': args, 'request_id': nonce,
                           'expected_revision': caller.session.view_revision})


def test_game_14_rate_limit_shared_between_bid_and_bounty_and_replay_is_dropped(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, _, _ = trade_game
    lid = listed(trade_game)
    caller = clients[1]
    act(game, caller, request(game, caller, 'market.bid', {'listing': lid, 'chits': 60}, 'bid-one'))
    game.commit_commerce()
    excess = request(game, caller, 'bounty.post', {'target': players[2].id, 'chits': 100}, 'too-soon')
    act(game, caller, excess)
    game.commit_commerce()
    assert players[1].chits_bank == 940 and not game.core.market.bounties.rows, {
        'messages': [(f.type, f.data) for f in game.frames_for(caller) if f.type in ('toast', 'bye')],
        'requests': game.core.market.views.requests.get(caller.session.id),
        'ready': game.core.commerce.ready(caller.session)}
    game.clock.advance(TICK_HZ)
    act(game, caller, excess)
    assert not game.core.commerce.pending
    act(game, caller, request(game, caller, 'bounty.post', {'target': players[2].id, 'chits': 100}, 'fresh-post'))
    game.commit_commerce()
    assert players[1].chits_bank == 840 and len(game.core.market.bounties.rows) == 1


def test_arch_15_2_stale_financial_request_and_malformed_terminal_change_nothing(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, iid, _ = trade_game
    caller = clients[0]
    frame = request(game, caller, 'market.list', {'item': iid, 'price': 50, 'expiry': 86400}, 'stale')
    frame.data['expected_revision'] -= 1
    act(game, caller, frame)
    assert not game.core.commerce.pending and iid in players[0].inventory
    act(game, caller, request(game, caller, 'market.list', {
        'item': iid, 'price': 50, 'expiry': 86400, 'terminal': []}, 'bad-terminal'))
    assert not game.core.commerce.pending and not game.core.market.market.listings
    assert not caller.session.closed


def test_arch_15_2_operator_cancel_waits_for_commit_and_refunds_once(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, iid, _ = trade_game
    owner = game.core.market
    lid = listed(trade_game)
    owner.execute(clients[1].session, 'bid', {'listing': lid, 'chits': 60})
    game.commit_commerce()
    replies = []
    owner.admin('market.cancel', {'listing': lid}, replies.append)
    assert not replies and players[1].chits_bank == 940
    game.commit_commerce(error=True)
    assert replies == [{'ok': False}] and owner.market.listings[lid].status == 'open'
    owner.admin('market.cancel', {'listing': lid}, replies.append)
    game.commit_commerce()
    assert replies[-1] == {'ok': True} and players[1].chits_bank == 1000
    assert game.core.commerce.items[iid].owner == players[0].id and iid in players[0].inventory
    owner.admin('market.cancel', {'listing': lid}, replies.append)
    assert replies[-1]['ok'] is False and not game.core.commerce.pending


def test_game_8_3_unsold_return_cannot_be_used_as_permanent_impound(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, iid, _ = trade_game
    lid = listed(trade_game)
    players[0].attributes['frame'] = 0
    game.core.market.execute(clients[0].session, 'cancel', {'listing': lid})
    game.commit_commerce()
    assert iid in players[0].inventory and game.core.commerce.items[iid].owner == players[0].id
    assert game.core.combat.actor(players[0]).overweight
    assert iid not in game.core.market.lat.interlock.state.get('impounds', {}).get(players[0].id, {}).get('items', {})


def test_game_8_3_unsold_expiry_returns_inventory(trade_game: tuple[Any, ...]) -> None:
    game, _, players, iid, _ = trade_game
    listed(trade_game)
    game.clock.advance(86400*TICK_HZ)
    game.core.market.expire()
    game.commit_commerce()
    assert iid in players[0].inventory and game.core.commerce.items[iid].owner == players[0].id


def test_arch_15_2_caller_cannot_use_operator_market_frame(trade_game: tuple[Any, ...]) -> None:
    game, clients, _, _, _ = trade_game
    lid = listed(trade_game)
    clients[1].send(Frame('admin.market.cancel', {'listing': lid}))
    assert game.core.market.market.listings[lid].status == 'open'
    assert any(f.type == 'bye' and f.data['reason'] == 'forbidden' for f in game.frames_for(clients[1]))


def test_game_3_1_collection_uses_effective_carry_capacity(trade_game: tuple[Any, ...], monkeypatch: Any) -> None:
    game, clients, players, iid, _ = trade_game
    lid = listed(trade_game)
    owner = game.core.market
    owner.execute(clients[1].session, 'buyout', {'listing': lid})
    game.commit_commerce()
    players[1].attributes['frame'] = 0
    mods = SimpleNamespace(attribute=lambda player, attr: 0, bonus=lambda kind: 100 if kind == 'carry_kg' else 0)
    with monkeypatch.context() as patch:
        patch.setattr(game.core.progression, 'modifiers', lambda player: mods)
        owner.execute(clients[1].session, 'collect', {'item': iid})
    game.commit_commerce()
    assert iid in players[1].inventory


def test_arch_15_2_sql_failure_rolls_back_bank_goods_treasury_and_market_rows(trade_game: tuple[Any, ...], tmp_path: Path, monkeypatch: Any) -> None:
    game, clients, players, iid, _ = trade_game
    store = Storage(tmp_path/'world.db', game.clock)
    commerce, owner = game.core.commerce, game.core.market
    def persist() -> None:
        effect = commerce.outbox.pop(0)
        store.commerce_write(commerce.prepare(effect))
        commerce.committed(effect, True)
    try:
        for player in players:
            store.mark_dirty('players', player.id, player.record())
        for item in commerce.items.values():
            store.mark_dirty('items', item.id, item.record())
        store.flush_now()
        owner.execute(clients[0].session, 'list', {'item': iid, 'price': 50, 'buyout': 100, 'expiry': 86400})
        persist()
        lid = next(iter(owner.market.listings))
        before = deepcopy(store.character_state())
        owner.execute(clients[1].session, 'buyout', {'listing': lid})
        effect = commerce.outbox.pop(0)
        prepared = commerce.prepare(effect)
        original = store._json
        def fail_on_sale(value: Any) -> str:
            if isinstance(value, dict) and value.get('id') == lid and value.get('status') == 'sold':
                raise OSError('injected failure after bank/item/treasury SQL')
            return original(value)
        with monkeypatch.context() as patch:
            patch.setattr(store, '_json', fail_on_sale)
            with pytest.raises(OSError):
                store.commerce_write(prepared)
        commerce.committed(effect, False)
        assert store.character_state() == before
        assert players[0].chits_bank == players[1].chits_bank == 1000
        assert commerce.items[iid].owner == 'market'
        owner.execute(clients[1].session, 'buyout', {'listing': lid})
        persist()
        saved = store.character_state()
        assert saved['market']['listings'][0]['status'] == 'sold'
        assert saved['relays']['factions']['kestrel']['treasury'] == 5
        assert {p['id']: p['chits_bank'] for p in saved['players']}[players[1].id] == 900
    finally:
        store.close()


def test_arch_6_2_schema_3_upgrade_preserves_existing_bank_and_item(trade_game: tuple[Any, ...], tmp_path: Path, monkeypatch: Any) -> None:
    game, _, players, iid, _ = trade_game
    path = tmp_path/'upgrade.db'
    with monkeypatch.context() as patch:
        patch.setattr(migrations, 'WORLD_SCHEMA', 3)
        old = Storage(path, game.clock)
        old.mark_dirty('players', players[0].id, players[0].record())
        old.mark_dirty('items', iid, game.core.commerce.items[iid].record())
        old.flush_now()
        old.close()
    upgraded = Storage(path, game.clock)
    try:
        saved = upgraded.character_state()
        assert saved['players'][0]['chits_bank'] == 1000
        assert saved['items'][0]['id'] == iid and saved['items'][0]['quality'] == 1.12
        assert saved['market'] == {'serial': 0, 'listings': [], 'bids': []}
        assert saved['bounties'] == {'serial': 0, 'rows': []}
    finally:
        upgraded.close()
