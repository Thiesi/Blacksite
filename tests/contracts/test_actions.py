"""Game 9: physical actions verify location, bound supplies and interrupts."""

from dataclasses import replace
from copy import deepcopy

import pytest

from blacksite.content.schema import Stage, StageTarget
from blacksite.server.contracts.ledger import Ledger
from blacksite.server.inventory import Inventory
from tests.contracts.test_engine import template
from tests.npcs.test_engine import city, body


def job(city, *, seconds=0, quantity=1):
    game, caller = city
    owner = game.core.contracts
    pickup = StageTarget('item', zone='vatside-clinics', tile=(20, 3), item='slv_power')
    delivery = replace(pickup, tile=(26, 3))
    stages = (Stage('collect', 'fetch', pickup, 'carry', 'carried', 'fixture:collect',
                    quantity=quantity, seconds=seconds),
              Stage('deliver', 'fetch', delivery, 'carry', 'delivered', 'fixture:deliver', quantity=quantity))
    job = template('delivery', story=True, stages=stages)
    owner.content.contracts[job.id] = job
    owner.state.engine.templates[job.id] = job
    draft = owner.state.fork()
    instance = draft.engine.accept(draft.engine.story_offer(job.id, caller.session.player_id),
                                  (owner.participant(caller.session.player_id),), owner.now())
    owner.write(draft)
    game.commit_commerce()
    return owner, instance.id, pickup, delivery


def test_game_9_3_pickup_is_bound_and_cannot_be_replaced_by_preexisting_public_salvage(city) -> None:
    game, caller = city
    owner, iid, pickup, delivery = job(city)
    player = game.core.characters.players[caller.session.player_id]
    owner.actions.perform(caller.session, iid, pickup)
    game.commit_commerce(error=True)
    assert not any(item.mission == iid for item in owner.commerce.items.values())
    owner.actions.perform(caller.session, iid, pickup)
    game.commit_commerce()
    supplied = next(item for item in owner.commerce.items.values() if item.mission == iid)
    assert supplied.bound and supplied.owner == player.id and supplied.id in player.inventory
    inventory = Inventory(deepcopy(owner.commerce.items), owner.content.items)
    with pytest.raises(ValueError, match='contract objective'):
        inventory.remove(deepcopy(player), supplied.id, 1, lambda: 'new')
    with pytest.raises(ValueError, match='cannot be split'):
        inventory.split(deepcopy(player), supplied.id, 1, lambda: 'new')
    with pytest.raises(ValueError, match='labelled objective'):
        inventory.slots(player, supplied.id)
    with pytest.raises(ValueError, match='next to'):
        owner.actions.perform(caller.session, iid, delivery)
    actor = body(game, caller)
    game.core.world.enter(actor, actor.zone, (25, 3))
    owner.actions.perform(caller.session, iid, delivery)
    game.commit_commerce()
    assert supplied.id not in player.inventory and supplied.id not in owner.commerce.items
    assert owner.state.engine.instances[iid].state == 'complete'


def test_game_9_1_stack_delivery_counts_each_bound_unit_once(city) -> None:
    game, caller = city
    # The shipped power unit is unstackable. Exercise the general stage
    # contract with a fixture stack, without changing shipped balance.
    game.core.loop.content.items['slv_power'] = replace(game.core.loop.content.items['slv_power'], stack_max=10)
    owner, iid, pickup, delivery = job(city, quantity=2)
    for _ in range(2):
        owner.actions.perform(caller.session, iid, pickup)
        game.commit_commerce()
    supplied = [i for i in owner.commerce.items.values() if i.mission == iid]
    assert len(supplied) == 1 and supplied[0].stack == 2
    actor = body(game, caller)
    game.core.world.enter(actor, actor.zone, (25, 3))
    for _ in range(2):
        owner.actions.perform(caller.session, iid, delivery)
        game.commit_commerce()
    assert owner.state.engine.instances[iid].state == 'complete'
    assert len(owner.state.engine.instances[iid].stages[1].subjects) == 2


def test_game_9_3_channel_movement_damage_cancel_and_save_failure_do_not_spend_supplies(city) -> None:
    game, caller = city
    owner, iid, pickup, delivery = job(city, seconds=5)
    actor = body(game, caller)
    owner.actions.perform(caller.session, iid, pickup)
    assert actor.behaviour['channel']['remaining'] == 5
    actor.cooldowns['last_hit'] = game.clock.now_tick()
    owner.actions.tick(game.clock.now_tick()+50)
    assert not owner.actions.channels and not owner.commerce.pending
    assert owner.state.engine.instances[iid].index == 0
    owner.actions.perform(caller.session, iid, pickup)
    game.core.world.enter(actor, actor.zone, (21, 3))
    owner.actions.tick(game.clock.now_tick()+50)
    assert not owner.actions.channels and not owner.commerce.pending
    owner.actions.perform(caller.session, iid, pickup)
    owner.actions.tick(game.clock.now_tick()+49)
    assert not owner.commerce.pending
    owner.actions.tick(game.clock.now_tick()+50)
    game.commit_commerce(error=True)
    assert owner.state.engine.instances[iid].index == 0
    assert not any(item.mission == iid for item in owner.commerce.items.values())


def test_game_9_3_withdrawal_removes_bound_supplies_in_same_write(city) -> None:
    game, caller = city
    owner, iid, pickup, delivery = job(city)
    owner.actions.perform(caller.session, iid, pickup)
    game.commit_commerce()
    supplied = next(item for item in owner.commerce.items.values() if item.mission == iid)
    draft = owner.state.fork()
    draft.engine.withdraw(iid, caller.session.player_id)
    owner.write(draft)
    effect = owner.commerce.outbox[0]
    assert supplied.id in effect['delete_items']
    assert supplied.id not in effect['player_patches'][caller.session.player_id]['inventory']
    game.commit_commerce(error=True)
    assert supplied.id in owner.commerce.items
    owner.write(draft)
    game.commit_commerce()
    assert supplied.id not in owner.commerce.items
