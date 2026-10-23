"""Architecture 15.2: real SQLite rollback, acknowledgement loss and replay."""

import json
from pathlib import Path
import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest

from blacksite.content.loader import ContentTree, load_content
from blacksite.server.contracts.engine import Engine, Participant
from blacksite.server.contracts.transactions import join_state
from blacksite.server.progression import Grant
from blacksite.server.storage.db import Storage
from tests.character_helpers import create
from tests.contracts.test_engine import finish, template
from tests.harness import HeadlessServer


@pytest.fixture(scope='module')
def content() -> ContentTree:
    return load_content(Path(__file__).parents[2]/'src/blacksite/content')


@pytest.fixture
def source(content: ContentTree, tmp_path: Path) -> Iterator[tuple[Any, ...]]:
    game = HeadlessServer(content, character_state={})
    caller = game.connect({'user_id': 1, 'handle': 'Source', 'node_name': 'test'})
    create(game, caller, name='Source', archetype=1)
    player = game.core.characters.players[caller.session.player_id]
    player.chits_hand = 0  # Isolate this receipt from the ordinary starter funds.
    store = Storage(tmp_path/'contracts.db', game.clock)
    store.mark_dirty('players', player.id, player.record())
    store.mark_dirty('identities', player.bbs_user_id, game.core.characters.identities[player.bbs_user_id])
    for iid, item in game.core.commerce.items.items():
        store.mark_dirty('items', iid, item.record())
    store.flush_now()
    job = template()
    engine = Engine('test-origin', {job.id: job})
    now = game.clock.now_utc().timestamp()
    draft = engine.fork()
    offer = draft.board('wardens', now)[0]
    instance = draft.accept(offer, (Participant(player.id, player.bbs_user_id),), now)
    game.clock.advance(200)
    finish(draft, instance.id, (player.id,))
    payout = draft.claim(instance.id, player.id, game.clock.now_utc().timestamp())[0]
    patch, identity, award = game.core.progression.reward_patch(player,
        Grant('contract', payout.receipt, True, amount=payout.payment.xp))
    patch['chits_hand'] = player.chits_hand + payout.payment.chits
    patch.update(game.core.factions.standing_patch(player, payout.payment.standing, 'propagate'))
    installed, prior, queued = [], [], []
    commerce = game.core.commerce
    assert commerce.settle(player, patch, commerce.items, commerce.caches, commerce.serial,
                           lambda success: prior.append((success, bool(installed))), identity)
    effect = commerce.outbox.pop(0)
    join_state(effect, {'engine': draft.record()}, installed.append)
    commerce.enqueue_system(lambda: queued.append(bool(installed)))
    try:
        yield game, player, store, engine, draft, instance, effect, installed, prior, queued
    finally:
        store.close()


def test_architecture_15_2_contract_reward_and_receipt_rollback_together(source) -> None:
    game, player, store, engine, draft, instance, effect, installed, prior, queued = source
    store.db.execute("""CREATE TRIGGER fail_contract BEFORE INSERT ON meta
        WHEN NEW.key = 'contracts_state'
        BEGIN SELECT RAISE(ABORT, 'fixture contract write failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match='fixture contract write failure'):
        store.commerce_write(game.core.commerce.prepare(effect))
    game.core.commerce.committed(effect, False)
    restored = store.character_state()
    row = next(p for p in restored['players'] if p['id'] == player.id)
    assert row['chits_hand'] == row['xp'] == player.chits_hand == player.xp == 0
    assert not restored['contracts'] and not installed and not engine.claims
    assert prior == [(False, False)] and queued == [False]


def test_architecture_15_2_installs_contract_before_source_callback_and_next_proposal(source) -> None:
    game, player, store, engine, draft, instance, effect, installed, prior, queued = source
    store.mark_dirty('meta', 'contracts_state', {'engine': {'serial': -1}})
    store.commerce_write(game.core.commerce.prepare(effect))
    game.core.commerce.committed(effect, True)
    assert player.xp == 200 and player.chits_hand == 200
    assert prior == [(True, True)] and queued == [True]
    assert ('meta', 'contracts_state') not in store.dirty
    expected = json.loads(json.dumps({'engine': draft.record()}))
    assert store.meta('contracts_state') == expected
    assert json.loads(json.dumps(installed[0])) == expected
    assert installed[0]['engine']['instances'][instance.id]['paid'] == [player.id]


def test_architecture_15_2_restart_after_durable_write_before_ack_does_not_pay_again(source) -> None:
    game, player, store, engine, draft, instance, effect, installed, prior, queued = source
    store.commerce_write(game.core.commerce.prepare(effect))
    # Simulate process loss before Commerce.committed publishes the receipt.
    assert player.chits_hand == player.xp == 0 and not installed
    restored = store.character_state()
    durable = Engine('test-origin', engine.templates, restored['contracts']['engine'])
    assert durable.claim(instance.id, player.id, game.clock.now_utc().timestamp()) == ()
    row = next(p for p in restored['players'] if p['id'] == player.id)
    assert row['xp'] == 200 and row['chits_hand'] == 200
    assert durable.completed[player.id] == {instance.template}


def test_architecture_15_2_queued_source_uses_frozen_contract_snapshot(source) -> None:
    game, player, store, engine, draft, instance, effect, installed, prior, queued = source
    draft.instances[instance.id].runtime['later_uncommitted_change'] = True
    prepared = game.core.commerce.prepare(effect)
    assert 'later_uncommitted_change' not in prepared['contracts_state']['engine']['instances'][instance.id]['runtime']
    store.commerce_write(prepared)
    game.core.commerce.committed(effect, True)
    assert 'later_uncommitted_change' not in installed[0]['engine']['instances'][instance.id]['runtime']
