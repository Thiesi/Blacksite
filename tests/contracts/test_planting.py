"""Game 9.1/9.3: plants and replacement supplies use real source writes."""

from typing import Any
from dataclasses import replace

import pytest

from blacksite.content.schema import DataSpec, Stage, StageTarget
from blacksite.server.protocol import Frame
from tests.character_helpers import act, place
from tests.contracts.test_adapter import live, shipped
from tests.contracts.test_engine import template
from tests.lattice.test_engine import intent, runners
from tests.lattice.test_encounters import enter


def commission(owner: Any, players: tuple[str, ...], target: StageTarget) -> str:
    pickup = StageTarget('item', zone='core-plaza', tile=(30,5), item='slv_power')
    stages = (Stage('supply', 'fetch', pickup, 'carry', 'carried', 'fixture:plant-supply'),
        Stage('plant', 'plant', target, 'channel', 'planted', 'fixture:plant', requires_item='slv_power'))
    spec = template('fixture-plant', story=True, stages=stages)
    owner.content.contracts[spec.id] = spec
    owner.state.engine.templates[spec.id] = spec
    offer = owner.state.engine.story_offer(spec.id, players[0])
    proposal = owner.propose(players[0], offer, players)
    for pid in players:
        owner.consent(proposal.id, pid)
    owner.start(proposal.id, players[0])
    return spec.id


def core_plant(runners: tuple[Any, ...]) -> tuple[Any, ...]:
    game, caller, _, _ = runners
    owner = game.core.contracts
    core = owner.content.cores['lat-civic-ledger']
    target = StageTarget('core_room', core=core.id, room=core.entry)
    tid = commission(owner, (caller.session.player_id,), target)
    game.commit_commerce()
    iid = next(i for i,j in owner.state.engine.instances.items() if j.template == tid)
    pickup = owner.state.engine.instances[iid].stages[0].targets[0]
    owner.actions.perform(caller.session, iid, pickup)
    game.commit_commerce()
    presence = enter(game, caller, core.id)
    for ice in owner.lat.encounters.core(presence).ice.values():
        ice.integrity = 0  # Isolate custody/channel rules from S14 combat.
    return game, caller, owner, iid, presence


def test_game_9_1_core_plant_charges_ten_trace_and_consumes_only_after_three_second_commit(runners: tuple[Any, ...]) -> None:
    game, caller, owner, iid, presence = core_plant(runners)
    player = owner.game.players[presence.player_id]
    supplied = owner.actions.carried(player, iid, 'slv_power')
    before = presence.trace
    owner.actions.start_plant(presence, iid)
    assert presence.procedure.until-game.clock.now_tick() == 30
    assert presence.trace-before == 10
    game.step(29)
    assert not owner.commerce.pending and supplied.id in player.inventory
    game.step()
    assert owner.commerce.pending and supplied.id in player.inventory
    assert owner.state.engine.instances[iid].state == 'active'
    game.commit_commerce(error=True)
    assert supplied.id in player.inventory and owner.state.engine.instances[iid].state == 'active'
    owner.actions.start_plant(presence, iid)
    game.step(30)
    game.commit_commerce()
    assert supplied.id not in player.inventory and supplied.id not in owner.commerce.items
    assert owner.state.engine.instances[iid].state == 'complete'
    assert not owner.actions.core_rows(presence)
    with pytest.raises(ValueError, match='active planting'):
        owner.actions.start_plant(presence, iid)


def test_game_9_1_core_menu_starts_plant_and_cancel_or_damage_keeps_supply(runners: tuple[Any, ...]) -> None:
    game, caller, owner, iid, presence = core_plant(runners)
    player = owner.game.players[presence.player_id]
    supplied = owner.actions.carried(player, iid, 'slv_power')
    intent(game, caller, 'interact')
    intent(game, caller, 'menu_select', row='plant:'+iid)
    assert presence.procedure and presence.procedure.kind == 'plant'
    intent(game, caller, 'menu_close')
    assert presence.procedure is None and not owner.commerce.pending
    assert supplied.id in player.inventory
    owner.actions.start_plant(presence, iid)
    presence.hit_serial += 1
    game.step()
    assert presence.procedure is None and supplied.id in player.inventory
    assert owner.state.engine.instances[iid].state == 'active'


def test_game_9_3_withdrawn_carrier_does_not_strand_remaining_worker_or_grant_outsider_supplies(live: tuple[Any, ...]) -> None:
    game, owner, callers, players = live
    target = StageTarget('zone_tile', zone='core-plaza', tile=(36,5))
    tid = commission(owner, tuple(p.id for p in players[:2]), target)
    game.commit_commerce()
    iid = next(i for i,j in owner.state.engine.instances.items() if j.template == tid)
    for index, caller in enumerate(callers):
        place(game, caller, 'core-plaza', (30+index,5))
    pickup = owner.state.engine.instances[iid].stages[0].targets[0]
    owner.actions.perform(callers[0].session, iid, pickup)
    game.commit_commerce()
    draft = owner.state.fork()
    owner.withdraw(draft, iid, players[0].id)
    owner.write(draft)
    game.commit_commerce()
    assert owner.state.engine.instances[iid].index == 1
    assert not any(item.mission == iid for item in owner.commerce.items.values())
    with pytest.raises(ValueError, match='labelled supply'):
        owner.actions.reissue(callers[2].session, iid, pickup)
    act(game, callers[1], Frame('key', {'k':'e','t':0}))
    game.commit_commerce(error=True)
    assert owner.actions.carried(players[1], iid, 'slv_power') is None
    act(game, callers[1], Frame('key', {'k':'e','t':0}))
    game.commit_commerce()
    supplied = owner.actions.carried(players[1], iid, 'slv_power')
    assert supplied and supplied.bound
    with pytest.raises(ValueError, match='already carry'):
        owner.actions.reissue(callers[1].session, iid, pickup)
    place(game, callers[1], 'core-plaza', (35,5))
    owner.actions.perform(callers[1].session, iid, target)
    assert owner.actions.channels[callers[1].session.id].until-game.clock.now_tick() == 30
    game.step(30)
    game.commit_commerce()
    assert owner.state.engine.instances[iid].state == 'complete'
    assert supplied.id not in owner.commerce.items


def test_game_9_3_crew_can_replace_a_withdrawn_carriers_lifted_supply_without_replaying_prior_stage(live: tuple[Any, ...]) -> None:
    game, owner, callers, players = live
    core = owner.content.cores['lat-civic-ledger']
    data = DataSpec('fixture-lifted-supply', 'item', 0, asset='slv_power', amount=1, scope='mission')
    owner.content.cores[core.id] = replace(core, rooms=tuple(replace(r, data=(*r.data,data))
        if r.id == core.entry else r for r in core.rooms))
    source = StageTarget('core_room', core=core.id, room=core.entry, data=data.id)
    delivery = StageTarget('zone_tile', zone='core-plaza', tile=(36,5))
    spec = template('lifted-supply', story=True, stages=(
        Stage('lift', 'hack', source, 'lift', 'lifted', 'fixture:lifted-supply'),
        Stage('deliver', 'fetch', delivery, 'carry', 'delivered', 'fixture:lifted-deliver', requires_item='slv_power')))
    owner.content.contracts[spec.id] = spec
    owner.state.engine.templates[spec.id] = spec
    proposal = owner.propose(players[0].id, owner.state.engine.story_offer(spec.id, players[0].id),
                             tuple(p.id for p in players[:2]))
    for player in players[:2]:
        owner.consent(proposal.id, player.id)
    owner.start(proposal.id, players[0].id)
    game.commit_commerce()
    iid = next(i for i,j in owner.state.engine.instances.items() if j.template == spec.id)
    for index in range(2):
        place(game, callers[index], 'core-plaza', (30+index,5))
        presence = enter(game, callers[index], core.id)
        for ice in owner.lat.encounters.core(presence).ice.values():
            ice.integrity = 0
        assert owner.mission_of(presence.player_id, data.id) == iid+':lift:0'
        key = owner.lat.encounters.source(presence, data)
        available = owner.lat.sources.refresh(key, data, game.clock.now_tick())
        owner.lat.encounters.start_lift(presence, data.id, available.generation)
        game.step(presence.procedure.until-game.clock.now_tick())
        game.commit_commerce()
        assert owner.state.engine.instances[iid].index == 1
        if index == 0:
            draft = owner.state.fork()
            owner.withdraw(draft, iid, players[0].id)
            owner.write(draft)
            game.commit_commerce()
            assert not any(item.mission == iid for item in owner.commerce.items.values())
    supplied = owner.actions.carried(players[1], iid, 'slv_power')
    assert supplied and supplied.bound
    intent(game, callers[1], 'lat.jack_out')
    game.step(30)
    place(game, callers[1], 'core-plaza', (36,5))
    owner.actions.perform(callers[1].session, iid, delivery)
    game.commit_commerce()
    assert owner.state.engine.instances[iid].state == 'complete'
    assert supplied.id not in owner.commerce.items
