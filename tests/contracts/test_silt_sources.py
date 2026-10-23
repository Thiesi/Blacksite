"""Game 9.3: mission Silt records belong to this graph and this roster."""

import pytest

from blacksite.content.schema import Bundle, DataSpec, Stage, StageTarget
from blacksite.server.contracts.ledger import Ledger
from blacksite.server.lattice.silt import generate
from blacksite.server.lattice.silt_scene import BandGraph
from tests.contracts.test_engine import template
from tests.lattice.test_engine import intent, runners
from tests.lattice.test_silt_encounters import descend


def commission(game, caller):
    owner = game.core.contracts
    data = DataSpec('fixture-silt-record', 'text', 0, asset='lattice-training-record', scope='mission')
    target = StageTarget('silt_data', sector='lat-chapel-ward', band='shallows', data=data.id)
    stage = Stage('silt-copy', 'hack', target, 'lift', 'lifted', 'fixture:silt-copy')
    job = template('silt-copy', story=True, stages=(stage,), mission_data=(data,))
    owner.content.contracts[job.id] = job
    owner.state.engine.templates[job.id] = job
    draft = owner.state.fork()
    instance = draft.engine.accept(draft.engine.story_offer(job.id, caller.session.player_id),
        (owner.participant(caller.session.player_id),), owner.now())
    owner.write(draft)
    game.commit_commerce()
    return owner, instance.id, data


def test_game_9_3_required_silt_copy_is_visible_and_keeps_its_site_across_seeds(runners):
    game, caller, _, _ = runners
    owner, iid, data = commission(game, caller)
    rooms, sites = set(), set()
    for nonce in range(40):
        descent = generate('fixture', 1, 'lat-chapel-ward', nonce, owner.content.silt)
        band = descent.bands[0]
        graph = BandGraph(descent, band, owner.content)
        room = next(r for r in graph.rooms.values() if any(d.id == data.id for d in r.data))
        assert not next(c for c in band.cells if c.id == room.id).hidden
        assert room.id != band.riser
        rooms.add(room.id)
        sites.add(graph.sites[data.id])
    assert len(rooms) > 1 and sites == {'lat-chapel-ward:shallows:fixture-silt-record'}
    other = generate('fixture', 1, 'lat-core', 1, owner.content.silt)
    assert all(d.id != data.id for r in BandGraph(other, other.bands[0], owner.content).rooms.values() for d in r.data)


def test_game_9_3_actual_generated_silt_lift_uses_mission_receipt_and_atomic_progress(runners):
    game, caller, outsider, _ = runners
    owner, iid, data = commission(game, caller)
    presence = descend(game, caller)
    encounters = game.core.lattice.encounters
    instance = encounters.core(presence)
    # Source/receipt isolation: S14 separately proves navigation and ICE.
    presence.room = next(r.id for r in instance.graph.rooms.values() if any(d.id == data.id for d in r.data))
    for ice in instance.ice.values():
        ice.integrity = 0
    assert owner.mission_of(presence.player_id, data.id) == iid+':silt-copy:0'
    key = encounters.source(presence, data)
    assert ':silt:lat-chapel-ward:shallows:fixture-silt-record' in key
    assert iid+':silt-copy:0' in key
    source = game.core.lattice.sources.refresh(key, data, game.clock.now_tick())
    intent(game, caller, 'lat.lift', target=data.id, generation=source.generation)
    game.step(presence.procedure.until-game.clock.now_tick())
    game.commit_commerce(error=True)
    assert owner.state.engine.instances[iid].state == 'active'
    assert key not in owner.game.players[presence.player_id].progress.get('mission_sources', {})
    source = game.core.lattice.sources.refresh(key, data, game.clock.now_tick())
    intent(game, caller, 'lat.lift', target=data.id, generation=source.generation)
    game.step(presence.procedure.until-game.clock.now_tick())
    effects = game.commit_commerce()
    assert owner.state.engine.instances[iid].state == 'complete'
    assert effects[0]['contracts_state']['engine']['instances'][iid]['state'] == 'complete'
    assert owner.mission_of(presence.player_id, data.id) is None
    outsider_presence = descend(game, outsider)
    outsider_instance = encounters.core(outsider_presence)
    outsider_presence.room = next(r.id for r in outsider_instance.graph.rooms.values() if any(d.id == data.id for d in r.data))
    assert owner.mission_of(outsider_presence.player_id, data.id) is None
    source = game.core.lattice.sources.refresh(encounters.source(outsider_presence, data), data, game.clock.now_tick())
    with pytest.raises(ValueError, match='active contract'):
        encounters.start_lift(outsider_presence, data.id, source.generation)


def test_game_9_3_inactive_story_bundle_adds_no_live_silt_record_or_offer(runners):
    game, caller, _, _ = runners
    owner, iid, data = commission(game, caller)
    job = owner.state.engine.instances[iid].template
    owner.content.bundles['fixture-authoring'] = Bundle('fixture-authoring', 'authoring', {'contracts': (job,)})
    descent = generate('fixture', 1, 'lat-chapel-ward', 1, owner.content.silt)
    graph = BandGraph(descent, descent.bands[0], owner.content)
    assert all(d.id != data.id for r in graph.rooms.values() for d in r.data)
    assert job not in Ledger(owner.origin, owner.content).engine.templates
