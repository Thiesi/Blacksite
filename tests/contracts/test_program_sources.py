"""Game 17.2: real program sources guard and commit acquisition together."""

from dataclasses import replace
from typing import Any

import pytest

from blacksite.content.schema import DataSpec, Reward, Stage, StageTarget, VendorStock
from blacksite.server.clock import TICK_HZ
from tests.character_helpers import place
from tests.contracts.test_engine import template
from tests.lattice.test_engine import runners
from tests.lattice.test_encounters import enter
from tests.npcs.test_engine import city


def test_game_17_2_vendor_checks_program_guard_without_spending_and_rolls_back_acquisition(city: tuple[Any, ...]) -> None:
    game, caller = city
    owner, commerce = game.core.contracts, game.core.commerce
    player = owner.game.players[caller.session.player_id]
    pid = 'prg_blackout'
    owner.lat.season = 1
    owner.content.programs[pid] = replace(owner.content.programs[pid],
        acquisition_requires=('standing:wardens:10', 'once_per_season'))
    vendor = owner.content.vendors['vesper']
    owner.content.vendors[vendor.id] = replace(vendor, stock=(*vendor.stock, VendorStock(pid)))
    place(game, caller, 'sodium-tin-halo', (8,14))
    player.chits_hand = 10000
    args = {'target':'vesper', 'item':pid}
    with pytest.raises(ValueError, match='acquisition requirements'):
        commerce.propose(caller.session, 'vendor.buy', args)
    assert not commerce.pending and player.chits_hand == 10000
    assert pid not in player.progress['known_programs']
    player.standing['wardens'] = 10
    game.step(TICK_HZ+1)
    commerce.propose(caller.session, 'vendor.buy', args)
    game.commit_commerce(error=True)
    assert player.chits_hand == 10000 and pid not in player.progress['known_programs']
    assert not player.progress.get('program_acquisitions')
    game.step(TICK_HZ+1)
    commerce.propose(caller.session, 'vendor.buy', args)
    game.commit_commerce()
    assert player.chits_hand < 10000
    assert player.progress['program_acquisitions']['1'] == [pid]
    assert pid in player.progress['known_programs']


def test_game_17_2_data_guard_runs_before_channel_cost_and_commits_with_source(runners: tuple[Any, ...]) -> None:
    game, caller, _, _ = runners
    owner, pid = game.core.contracts, 'prg_blackout'
    owner.lat.season = 1
    owner.content.programs[pid] = replace(owner.content.programs[pid],
        acquisition_requires=('archetype:cantor', 'once_per_season'))
    core = owner.content.cores['lat-civic-ledger']
    data = DataSpec('fixture-program', 'program', 0, asset=pid, amount=1, scope='identity')
    owner.content.cores[core.id] = replace(core, rooms=tuple(replace(r, data=(*r.data,data))
        if r.id == core.entry else r for r in core.rooms))
    presence = enter(game, caller, core.id)
    player = owner.game.players[presence.player_id]
    encounters = owner.lat.encounters
    key = encounters.source(presence, data)
    source = owner.lat.sources.refresh(key, data, game.clock.now_tick())
    trace = presence.trace
    with pytest.raises(ValueError, match='acquisition requirements'):
        encounters.start_lift(presence, data.id, source.generation)
    assert presence.procedure is None and presence.trace == trace
    assert source.available and not owner.lat.sources.reserved
    owner.content.programs[pid] = replace(owner.content.programs[pid],
        acquisition_requires=('archetype:hardline', 'once_per_season'))
    encounters.start_lift(presence, data.id, source.generation)
    game.step(presence.procedure.until-game.clock.now_tick())
    game.commit_commerce(error=True)
    assert pid not in player.progress['known_programs']
    assert not player.progress.get('program_acquisitions')
    encounters.start_lift(presence, data.id, source.generation)
    game.step(presence.procedure.until-game.clock.now_tick())
    effects = game.commit_commerce()
    assert pid in player.progress['known_programs']
    assert player.progress['program_acquisitions']['1'] == [pid]
    assert effects[0]['lattice_state']['sources'][key]['generation'] == source.generation+1


def test_game_17_2_contract_guard_uses_its_rewarded_standing_in_same_transaction(city: tuple[Any, ...]) -> None:
    game, caller = city
    owner, pid = game.core.contracts, 'prg_blackout'
    player = owner.game.players[caller.session.player_id]
    owner.lat.season = 1
    owner.content.programs[pid] = replace(owner.content.programs[pid],
        acquisition_requires=('standing:wardens:10', 'once_per_season'))
    target = StageTarget('zone_tile', zone='vatside-clinics', tile=(20,3))
    stage = Stage('inspect', 'survey', target, 'inspect', 'observed', 'fixture:program-source')
    spec = template('program-source', story=True, stages=(stage,), reward=Reward(
        chits=(200,200), xp=100, standing={'wardens':10}, standing_mode='explicit', programs=(pid,)))
    owner.content.contracts[spec.id] = spec
    owner.state.engine.templates[spec.id] = spec
    offer = owner.state.engine.story_offer(spec.id, player.id)
    proposal = owner.propose(player.id, offer, (player.id,))
    owner.consent(proposal.id, player.id)
    owner.start(proposal.id, player.id)
    game.commit_commerce()
    iid = next(iter(owner.state.engine.instances))
    owner.actions.perform(caller.session, iid, target)
    game.commit_commerce()
    owner.claim(iid, player.id)
    game.commit_commerce(error=True)
    assert player.standing.get('wardens',0) == 0 and pid not in player.progress['known_programs']
    assert owner.state.engine.instances[iid].state == 'complete'
    owner.claim(iid, player.id)
    game.commit_commerce()
    assert player.standing['wardens'] == 10 and pid in player.progress['known_programs']
    assert player.progress['program_acquisitions']['1'] == [pid]
