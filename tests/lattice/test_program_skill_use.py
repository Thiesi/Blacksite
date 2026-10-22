"""Game 3.5: Programs learns semantic changes, excluding timer refreshes."""

from blacksite.server.lattice.programs import Cast
from tests.lattice.test_engine import jack, runners


def complete(game, presence, program, target=""):
    encounters = game.core.lattice.encounters
    game.clock.advance(1)
    encounters.complete_cast(presence, Cast(program,target,game.clock.now_tick(),
        encounters.location(presence)[0],presence.hit_serial))
    game.commit_commerce()


def test_game_3_5_access_change_learns_once_without_refresh_farming(runners):
    game, a, b, c = runners
    presence = jack(game,a)
    player = game.core.characters.players[presence.player_id]
    before = player.skills["programs"]
    complete(game,presence,"prg_signet")
    assert player.skills["programs"] == before+.15
    complete(game,presence,"prg_signet")
    assert player.skills["programs"] == before+.15


def test_game_3_5_restore_requires_a_real_integrity_change(runners):
    game, a, b, c = runners
    presence = jack(game,a)
    player = game.core.characters.players[presence.player_id]
    program = next(p.id for p in game.core.loop.content.programs.values() if p.effect.kind == "restore")
    before = player.skills["programs"]
    complete(game,presence,program)
    assert player.skills["programs"] == before
    presence.integrity -= 10
    complete(game,presence,program)
    assert player.skills["programs"] == before+.15
