"""Game 9.4: fresh Wakes can finish both shipped first-job routes."""

from dataclasses import replace
from collections import deque
from pathlib import Path
from typing import Any

import pytest

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.server.contracts.panels import Panel
from tests.character_helpers import act, create, place
from blacksite.server.protocol import Frame
from tests.harness import HeadlessServer
from tests.lattice.test_engine import intent
from tests.lattice.test_interlock import flip


def first_job(repo_root: Path, archetype: int = 0) -> tuple[Any, ...]:
    content = load_content(repo_root/'src/blacksite/content')
    assert not validate(content)
    # Route mechanics are isolated from NPC scheduling. Native acceptance
    # retains shipped traffic and proves the actual sheltered release.
    content.zones = {k: replace(z, meta=replace(z.meta, spawners=())) for k, z in content.zones.items()}
    game = HeadlessServer(content, character_state={})
    caller = game.connect()
    create(game, caller, archetype=archetype, card='none')
    owner, pid = game.core.contracts, caller.session.player_id
    player = owner.game.players[pid]
    player.progress['wake_combat'] = 'skipped'
    place(game, caller, 'sodium-tin-halo', (8,14))
    offer = owner.offer('vesper-first-thing', pid, 'vesper')
    proposal = owner.propose(pid, offer, (pid,))
    owner.consent(proposal.id, pid)
    owner.start(proposal.id, pid)
    game.commit_commerce()
    iid = next(iid for iid,j in owner.state.engine.instances.items() if j.template == 'vesper-first-thing')
    place(game, caller, 'terraces-blocks', (71,25))
    stage = owner.state.engine.instances[iid].stages[0]
    owner.actions.perform(caller.session, iid, stage.targets[0])
    game.commit_commerce()
    return game, caller, owner, iid


def test_game_9_4_public_arrivals_reach_the_latch_without_renting_an_apartment(repo_root: Path) -> None:
    game,caller,owner,iid = first_job(repo_root)
    zone = owner.world.zones['terraces-blocks']
    actor = game.core.combat.actor(owner.game.players[caller.session.player_id])
    hatch = zone.objects['stairwell-c-parcel-hatch'].spec.tile
    arrivals = [exit.target_tile for other in owner.world.zones.values()
                for exit in other.template.meta.exits if exit.target_zone == zone.id and not exit.requirement]
    assert arrivals
    exits = {e.tile for e in zone.template.meta.exits if e.kind == 'street'}
    for arrival in arrivals:
        pending,seen = deque([arrival]),{arrival}
        while pending:
            x,y = pending.popleft()
            for tile in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if tile not in seen and tile not in exits and zone.can_enter(actor,tile):
                    seen.add(tile)
                    pending.append(tile)
        assert any(max(abs(x-hatch[0]),abs(y-hatch[1])) <= 1 for x,y in seen)


def test_game_9_1_clinic_board_preserves_recruitment_and_uses_a_separate_terminal(repo_root: Path) -> None:
    game,caller,owner,iid = first_job(repo_root)
    zone = owner.world.zones['vatside-clinics']
    actor = game.core.combat.actor(owner.game.players[caller.session.player_id])
    recruiter = zone.objects['sablier-recruiter']
    assert 'contract_handler' not in recruiter.spec.params
    # Commission the existing contact API; named recruiter bodies arrive
    # in S27. S19's separate board must not intercept that interaction.
    recruiter.spec.params['recruiters'] = ['sablier']
    place(game,caller,zone.id,owner.world.free_tile(zone.id,recruiter.spec.tile,actor))
    act(game,caller,Frame('key',{'k':'e','t':0}))
    assert caller.session.id in game.core.factions.menus
    assert caller.session.id not in owner.panels.menus
    act(game,caller,Frame('key',{'k':'escape','t':0}))
    board = zone.objects['clinic-public-west']
    place(game,caller,zone.id,owner.world.free_tile(zone.id,board.spec.tile,actor))
    act(game,caller,Frame('key',{'k':'e','t':0}))
    assert owner.panels.menus[caller.session.id].handler == 'sablier'


@pytest.mark.parametrize('archetype', range(4))
@pytest.mark.parametrize('route', ('manual', 'loan'))
def test_game_9_4_fresh_wake_shared_latch_delivery_and_once_only_reward(repo_root: Path, archetype: int, route: str) -> None:
    game, caller, owner, iid = first_job(repo_root, archetype)
    pid = caller.session.player_id
    player = owner.game.players[pid]
    job = owner.state.engine.instances[iid]
    assert job.index == 1 and 'stairwell-c-latch-record' in owner.state.journal[pid]
    hatch = owner.world.zones['terraces-blocks'].objects['stairwell-c-parcel-hatch']
    assert not hatch.open
    if route == 'manual':
        owner.actions.perform(caller.session, iid, job.stages[1].targets[0])
        assert owner.actions.channels[caller.session.id].until-game.clock.now_tick() == 50
        game.step(50)
    else:
        lat = game.core.lattice
        lat.jack_in(caller.session, 'stairwell-c-loan')
        game.commit_commerce()
        presence = lat.presences[pid]
        assert presence.cell == 'lat-terraces-c11'
        intent(game, caller, 'lat.enter', core='lat-stairwell-c')
        assert presence.core == 'lat-stairwell-c'
        assert not lat.encounters.defenders(presence)
        flip(game, caller, 'parcel-release')
        assert presence.trace == 0
    assert not hatch.open and owner.state.engine.instances[iid].index == 1
    game.commit_commerce()
    assert hatch.open and owner.state.engine.instances[iid].index == 2
    if route == 'loan':
        intent(game, caller, 'lat.jack_out')
        game.step(30)
        assert pid not in game.core.lattice.presences
    place(game, caller, 'terraces-blocks', (72,24))
    owner.actions.perform(caller.session, iid, owner.state.engine.instances[iid].stages[2].targets[0])
    game.commit_commerce()
    parcel = next(item for item in owner.commerce.items.values() if item.mission == iid)
    assert parcel.bound and parcel.owner == pid
    assert not owner.control_permit(pid, 'lat-stairwell-c', 'parcel-release')
    place(game, caller, 'sodium-tin-halo', (8,14))
    act(game, caller, Frame('key', {'k':'e', 't':0}))
    game.commit_commerce()
    assert owner.state.engine.instances[iid].state == 'complete'
    assert not owner.control_permit(pid, 'lat-stairwell-c', 'parcel-release')
    chits, xp, standing = player.chits_hand, player.xp, dict(player.standing)
    owner.claim(iid, pid)
    game.commit_commerce()
    # Operator's documented premium applies after the fixed base reward.
    assert player.chits_hand-chits == (220 if player.archetype == 'operator' else 200)
    assert player.xp-xp == 100
    assert all(player.standing[f]-standing.get(f, 0) == 5 for f in owner.content.factions)
    assert parcel.id not in owner.commerce.items
    settled = player.chits_hand, player.xp, dict(player.standing)
    owner.claim(iid, pid)
    assert not owner.commerce.pending
    assert (player.chits_hand, player.xp, player.standing) == settled


def test_game_9_4_failed_manual_write_preserves_latch_and_retry(repo_root: Path) -> None:
    game, caller, owner, iid = first_job(repo_root)
    target = owner.state.engine.instances[iid].stages[1].targets[0]
    owner.actions.perform(caller.session, iid, target)
    game.step(50)
    game.commit_commerce(error=True)
    hatch = owner.world.zones['terraces-blocks'].objects['stairwell-c-parcel-hatch']
    assert not hatch.open and owner.state.engine.instances[iid].index == 1
    owner.actions.perform(caller.session, iid, target)
    game.step(50)
    game.commit_commerce()
    assert hatch.open and owner.state.engine.instances[iid].index == 2


def test_game_9_4_vesper_job_counter_keeps_trade_available(repo_root: Path) -> None:
    game, caller, owner, iid = first_job(repo_root)
    place(game, caller, 'sodium-tin-halo', (8,14))
    panel = Panel(game.clock.now_tick(), target='vesper', handler='vesper')
    owner.panels.menus[caller.session.id] = panel
    assert any(a['key'] == 'v' for a in owner.panels.body(caller.session, panel)['actions'])
    owner.panels.act(caller.session, panel, 'v', '')
    assert caller.session.id not in owner.panels.menus
    assert owner.commerce.menus[caller.session.id].kind == 'vendor'
    assert owner.commerce.menus[caller.session.id].target == 'vesper'
