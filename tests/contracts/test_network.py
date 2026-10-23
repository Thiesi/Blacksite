"""Game 9.3: actual lift/control receipts advance frozen mission state."""

from dataclasses import replace

import pytest

from blacksite.content.schema import DataSpec, EvidenceRecord, Stage, StageTarget
from tests.contracts.test_engine import template
from tests.lattice.test_engine import runners, intent
from tests.lattice.test_encounters import enter
from tests.lattice.test_interlock import flip, control_room


def accept(game, caller, stages, evidence=()):
    owner = game.core.contracts
    job = template('network', story=True, stages=stages, evidence_assets=evidence)
    owner.content.contracts[job.id] = job
    owner.state.engine.templates[job.id] = job
    draft = owner.state.fork()
    instance = draft.engine.accept(draft.engine.story_offer(job.id, caller.session.player_id),
                                  (owner.participant(caller.session.player_id),), owner.now())
    owner.write(draft)
    game.commit_commerce()
    return owner, instance.id


def test_game_9_3_actual_control_and_contract_progress_commit_or_rollback_together(runners) -> None:
    game, caller, other, outsider = runners
    presence = enter(game, caller, 'lat-civic-ledger')
    spec = control_room(game, presence)
    stage = Stage('flip', 'hack', StageTarget('core_control', core=presence.core, control=spec.id),
                  'flip', 'flipped', 'fixture:flip')
    owner, iid = accept(game, caller, (stage,))
    flip(game, caller)
    effect = game.core.commerce.outbox[0]
    assert effect['interlock_state'] and effect['contracts_state']['engine']['instances'][iid]['state'] == 'complete'
    game.commit_commerce(error=True)
    assert owner.state.engine.instances[iid].state == 'active'
    flip(game, caller)
    game.commit_commerce()
    assert owner.state.engine.instances[iid].state == 'complete'


def test_game_9_3_mission_lift_is_scoped_to_exact_room_data_and_joins_evidence_atomically(runners) -> None:
    game, caller, other, outsider = runners
    core = game.core.loop.content.cores['lat-civic-ledger']
    data = DataSpec('fixture-evidence', 'evidence', 1800, asset='fixture-record', scope='mission')
    rooms = tuple(replace(room, data=(*room.data, data)) if room.id == core.entry else room for room in core.rooms)
    game.core.loop.content.cores[core.id] = replace(core, rooms=rooms)
    presence = enter(game, caller, core.id)
    encounters = game.core.lattice.encounters
    stage = Stage('lift', 'hack', StageTarget('core_room', core=core.id, room=core.entry, data=data.id),
                  'lift', 'lifted', 'fixture:lift')
    game.core.loop.content.evidence['fixture-record'] = EvidenceRecord('fixture-record', 'optional',
        'You hold the signed record.', 'A local manifest', 'The load is reserved.', related_objective='network',
        related_stage='lift', question='Who changed the load?', next_action='Bring the record back.')
    owner, iid = accept(game, caller, (stage,), ('fixture-record',))
    scope = owner.mission_of(presence.player_id, data.id)
    assert scope == iid+':lift:0'
    assert owner.mission_of(presence.player_id, 'other-data') is None
    assert owner.mission_of(other.session.player_id, data.id) is None
    key = encounters.source(presence, data)
    assert scope in key and caller.session.user_id in key
    source = game.core.lattice.sources.refresh(key, data, game.clock.now_tick())
    intent(game, caller, 'lat.lift', target=data.id, generation=source.generation)
    assert presence.procedure
    game.step(presence.procedure.until-game.clock.now_tick())
    effect = game.core.commerce.outbox[0]
    assert effect['contracts_state']['journal'][presence.player_id]['fixture-record']['claim'] == 'The load is reserved.'
    game.commit_commerce(error=True)
    assert not owner.state.journal and owner.state.engine.instances[iid].state == 'active'
    source = game.core.lattice.sources.refresh(key, data, game.clock.now_tick())
    intent(game, caller, 'lat.lift', target=data.id, generation=source.generation)
    game.step(presence.procedure.until-game.clock.now_tick())
    effects = game.commit_commerce()
    assert effects[0]['contracts_state']['engine']['instances'][iid]['state'] == 'complete'
    assert owner.state.journal[presence.player_id]['fixture-record']['instance'] == iid
    assert owner.mission_of(presence.player_id, data.id) is None


def test_game_9_3_enter_objective_uses_real_admission_and_ordinary_exploration_adds_no_receipt(runners) -> None:
    game, caller, other, outsider = runners
    core = game.core.loop.content.cores['lat-civic-ledger']
    stage = Stage('enter', 'hack', StageTarget('core_room', core=core.id, room=core.entry),
                  'enter', 'entered', 'fixture:enter')
    owner, iid = accept(game, caller, (stage,))
    presence = enter(game, caller, core.id)
    assert owner.state.engine.instances[iid].state == 'active'
    game.commit_commerce()
    assert owner.state.engine.instances[iid].state == 'complete'
    assert presence.core == core.id
    assert not game.core.commerce.pending
