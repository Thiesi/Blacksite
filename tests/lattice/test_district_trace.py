"""Game 6.7/world Lattice 7: action trace survives the core boundary."""

from dataclasses import replace

from tests.lattice.test_engine import actor, intent, jack, runners
from tests.lattice.test_encounters import cast


def gated(lattice, sid):
    return next(cell for cell in lattice.sectors.records[sid].cells
                if cell.access_kind == 'gated' and any(lattice.sectors.cells[sid][n].access_kind == 'public'
                                                     for n in cell.neighbours))


def test_world_7_district_burn_charges_trace_and_dispatches_at_threshold(runners):
    game, a, b, c = runners
    first, second = jack(game, a), jack(game, b)
    lattice = game.core.lattice
    cell = gated(lattice, 'lat-core')
    first.cell = second.cell = cell.id
    zone = game.core.world.zones[actor(game, a).zone]
    zone.template = replace(zone.template, meta=replace(zone.template.meta, safety='contested'))
    for client in (a, b):
        game.core.characters.players[client.session.player_id].grade = 5
    first.rig = ('prg_burn', None, None)
    cast(game, a, 'prg_burn', second.player_id)
    assert first.trace == 15 and second.integrity == 82
    lattice.encounters.trace(first, 85)
    player = game.core.characters.players[first.player_id]
    assert player.warden_heat_until and player.progress['lattice_registry_until']
    assert len([npc for npc in game.core.world.actors.values() if npc.behaviour.get('response') == player.id]) == 2


def test_world_7_public_cells_and_nobody_suppress_district_trace(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    lattice = game.core.lattice
    lattice.encounters.trace(presence, 15)
    assert presence.trace == 0
    presence.cell = gated(lattice, presence.sector).id
    presence.effects.install(game.core.loop.content.programs['prg_nobody'], game.clock.now_tick())
    lattice.encounters.trace(presence, 15)
    assert presence.trace == 0


def test_game_6_7_street_lockout_is_identity_scoped_and_preserves_public_links(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    lattice = game.core.lattice
    cell = gated(lattice, 'lat-chapel-ward')
    public = next(n for n in cell.neighbours if lattice.sectors.cells['lat-chapel-ward'][n].access_kind == 'public')
    presence.sector, presence.cell = 'lat-chapel-ward', cell.id
    lattice.encounters.trace(presence, 100)
    assert presence.player_id not in lattice.presences and actor(game, a).shock == 60
    fresh = jack(game, a)
    fresh.sector, fresh.cell, fresh.key_tier = 'lat-chapel-ward', public, 2
    intent(game, a, 'lat.move', cell=cell.id)
    assert fresh.destination is None
    other = jack(game, b)
    other.sector, other.cell, other.key_tier = 'lat-chapel-ward', public, 2
    intent(game, b, 'lat.move', cell=cell.id)
    assert other.destination == ('lat-chapel-ward', cell.id)
    assert not lattice.sources.locked(game.core.characters.players[other.player_id].bbs_user_id,
                                     'lat-chapel-ward', game.clock.now_utc().timestamp())


def test_game_6_7_untiered_corporate_district_uses_base_hunter(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    lattice = game.core.lattice
    presence.sector, presence.cell = 'lat-spire', gated(lattice, 'lat-spire').id
    lattice.encounters.trace(presence, 100)
    hunter = next(iter(lattice.encounters.hunters.values()))
    assert (hunter.maximum, hunter.attack, hunter.meat_damage) == (80, 20, 0)
    assert hunter.target == presence.player_id


def test_game_6_7_core_notices_carried_trace_once_per_run(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    lattice = game.core.lattice
    presence.cell = next(cell.id for cell in lattice.sectors.records['lat-core'].cells if cell.core_id == 'lat-civic-ledger')
    presence.trace = 80
    intent(game, a, 'lat.enter', core='lat-civic-ledger')
    player = game.core.characters.players[presence.player_id]
    deadline = player.progress['lattice_registry_until']
    intent(game, a, 'lat.leave')
    intent(game, a, 'lat.enter', core='lat-civic-ledger')
    assert player.progress['lattice_registry_until'] == deadline
