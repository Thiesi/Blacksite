"""Game 6.7/17.2: program scopes and mission source authority."""

from dataclasses import replace

from blacksite.content.schema import ContractTemplate, Stage, StageTarget

from tests.lattice.test_engine import intent, jack, runners
from tests.lattice.test_encounters import cast, enter


def test_game_17_2_signet_opens_halvard_keys_after_cast_but_never_story_locks(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    lattice = game.core.lattice
    player = game.core.characters.players[presence.player_id]
    cell = next(c for c in lattice.sectors.records['lat-spire'].cells
                if c.gate_owner == 'halvard' and c.requirement == 'program:key:2')
    presence.sector, presence.cell = 'lat-spire', cell.neighbours[0]
    presence.rig = ('prg_signet', None, None)
    intent(game, a, 'lat.move', cell=cell.id)
    assert presence.destination is None
    cast(game, a, 'prg_signet')
    assert lattice.accepts(player, presence, cell, cell.requirement)
    assert not lattice.accepts(player, presence, replace(cell, gate_owner=None), cell.requirement)
    assert not lattice.accepts(player, presence, cell, 'event:ring-fall')
    assert not lattice.accepts(player, presence, cell, 'item:story_halvard_seal_beacon')
    intent(game, a, 'lat.move', cell=cell.id)
    assert presence.destination == ('lat-spire', cell.id)


def test_game_17_2_pulse_marks_entry_only_for_authorized_crew(runners):
    game, a, b, c = runners
    presence = enter(game, a, 'lat-civic-ledger')
    other, stranger = jack(game, b), jack(game, c)
    lattice = game.core.lattice
    lattice.crew_of = lambda pid: 'crew-a' if pid in (presence.player_id, other.player_id) else None
    presence.rig = ('prg_pulse', None, None)
    cast(game, a, 'prg_pulse')
    viewer = lattice.encounters.view(b.session, other, lattice.view(b.session, other))[1]
    outsider = lattice.encounters.view(c.session, stranger, lattice.view(c.session, stranger))[1]
    assert viewer['beacons'] == [{'player': presence.player_id, 'name': 'Runner1', 'cell': presence.cell}]
    assert not outsider['beacons']
    assert 'room' not in viewer['beacons'][0]
    effect = presence.effects.active['prg_pulse']
    entry = effect.params['cell']
    presence.cell = lattice.sectors.entrance(presence.sector)
    assert effect.params['cell'] == entry
    game.step(effect.until-game.clock.now_tick())
    viewer = lattice.encounters.view(b.session, other, lattice.view(b.session, other))[1]
    assert not viewer['beacons']


def test_game_6_7_mission_lift_never_crosses_into_another_contract(runners):
    game, a, b, c = runners
    presence = enter(game, a, 'lat-kestrel-branch')
    encounters = game.core.lattice.encounters
    instance = encounters.core(presence)
    room = next(r for r in instance.graph.rooms.values() if any(d.id == 'transaction-logs' for d in r.data))
    presence.room = room.id
    instance.ice.clear()  # Isolate receipts; guarded-source tests cover ICE.
    intent(game, a, 'lat.lift', target='transaction-logs', generation=0)
    assert presence.procedure is None
    owner = game.core.contracts
    draft = owner.state.fork()
    ids = []
    for name in ('mission-a', 'mission-b'):
        target = StageTarget('core_room', core=presence.core, room=room.id, data='transaction-logs')
        stage = Stage('copy', 'hack', target, 'lift', 'lifted', name+':copy')
        job = ContractTemplate(name, 'kestrel', story=True, stages=(stage,))
        owner.content.contracts[name] = draft.engine.templates[name] = job
        accepted = draft.engine.accept(draft.engine.story_offer(name, presence.player_id),
                                       (owner.participant(presence.player_id),), owner.now())
        ids.append(accepted.id)
    owner.write(draft)
    game.commit_commerce()
    assert encounters.mission_of(presence.player_id, 'transaction-logs') == ids[0]+':copy:0'
    intent(game, a, 'lat.lift', target='transaction-logs', generation=0)
    assert presence.procedure
    deadline = presence.procedure.until
    draft = owner.state.fork()
    owner.withdraw(draft, ids[0], presence.player_id)
    owner.write(draft)
    game.commit_commerce()
    assert encounters.mission_of(presence.player_id, 'transaction-logs') == ids[1]+':copy:0'
    game.step(deadline-game.clock.now_tick())
    assert not game.core.commerce.pending
    player = game.core.characters.players[presence.player_id]
    assert not player.progress.get('lattice_units')
    intent(game, a, 'lat.lift', target='transaction-logs', generation=0)
    game.step(presence.procedure.until-game.clock.now_tick())
    game.commit_commerce()
    unit = next(iter(player.progress['lattice_units'].values()))
    assert unit['kind'] == 'contract_key' and unit['mission'] == ids[1]
    assert unit['source'].endswith(':mission:'+ids[1]+':copy:0')
    assert player.chits_hand == 200 and player.chits_bank == 0
