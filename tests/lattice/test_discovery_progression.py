"""Game 3.5/6.5: real visits and authored surveys, never generated XP loops."""

import pytest

from blacksite.server.world.exits import schedule
from tests.lattice.test_engine import intent, jack, runners


def test_game_3_5_authored_cell_receipt_and_skill_commit_once(runners):
    game, a, b, c = runners
    presence = jack(game,a)
    player = game.core.characters.players[presence.player_id]
    assert player.xp == 5 and player.skills["lattice"] == .05
    key = presence.sector+"/"+presence.cell
    game.core.progression.record_discovery(player.id,"cell",key)
    game.commit_commerce()
    assert player.xp == 5 and player.skills["lattice"] == .05
    game.core.progression.record_discovery(player.id,"cell","different-authored-cell")
    game.commit_commerce(error=True)
    assert player.xp == 5 and player.skills["lattice"] == .05
    assert "cell_discovery:different-authored-cell" not in player.progress["reward_receipts"]


def test_game_3_5_real_arrival_and_movement_loops_pay_once(runners):
    game, a, b, c = runners
    sim = game.core.characters.sim
    avatar = sim.avatars[a.session.user_id]
    player = game.core.characters.players[a.session.player_id]
    exit = next(ex for ex in game.core.world.zones[avatar.zone].template.meta.exits
                if ex.kind == "street" and ex.target_zone in game.core.world.zones)
    avatar.travel = schedule(exit,game.clock.now_utc().timestamp())
    sim.transition(a.session,avatar,avatar.travel.arrival,game.clock.now_tick())
    assert player.xp == 0
    game.commit_commerce()
    assert player.xp == 25
    sim.arrival_hook(a.session,avatar)
    game.commit_commerce()
    assert player.xp == 25


def test_game_3_5_real_authored_cell_movement_loop_pays_once(runners):
    game, a, b, c = runners
    presence = jack(game,a)
    lat = game.core.lattice
    player = game.core.characters.players[presence.player_id]
    start = presence.cell
    target = next(cid for cid in lat.sectors.cells[presence.sector][start].neighbours
                  if lat.sectors.cells[presence.sector][cid].access_kind == "public")
    intent(game,a,"lat.move",cell=target)
    game.step(30)
    game.commit_commerce()
    assert presence.cell == target and player.xp == 10 and player.skills["lattice"] == .1
    for cell in (start,target):
        intent(game,a,"lat.move",cell=cell)
        game.step(30)
        game.commit_commerce()
    assert player.xp == 10 and player.skills["lattice"] == .1


def test_game_6_5_authored_survey_threshold_cooldown_and_one_hidden_gain(runners):
    game, a, b, c = runners
    presence = jack(game,a)
    lat, encounters = game.core.lattice, game.core.lattice.encounters
    player = game.core.characters.players[presence.player_id]
    sector, hidden = next((sid, cell) for sid, cells in lat.sectors.cells.items()
                          for cell in cells.values() if cell.access_kind == "hidden" and cell.neighbours)
    presence.sector, presence.cell = sector, hidden.neighbours[0]
    player.skills["listening"] = 19
    encounters.survey(presence)
    game.step(30)
    game.commit_commerce()
    assert hidden.id not in lat.found(player,sector)
    with pytest.raises(ValueError,match="cooling"):
        encounters.survey(presence)
    game.step(100)
    player.skills["listening"] = 20
    encounters.survey(presence)
    game.step(30)
    assert hidden.id not in lat.found(player,sector)  # Not published before storage.
    game.commit_commerce()
    assert hidden.id in lat.found(player,sector)
    after = player.skills["listening"]
    assert after >= 20.5
    assert not lat.reveal(player,sector,hidden.id,learn=True)
    game.commit_commerce()
    assert player.skills["listening"] == after


def test_game_3_5_failed_hidden_receipt_does_not_reveal_or_learn(runners):
    game, a, b, c = runners
    presence = jack(game,a)
    lat = game.core.lattice
    player = game.core.characters.players[presence.player_id]
    hidden = next(cell for cell in lat.sectors.records[presence.sector].cells if cell.access_kind == "hidden")
    before = player.skills["listening"]
    assert lat.reveal(player,presence.sector,hidden.id,learn=True)
    game.commit_commerce(error=True)
    assert hidden.id not in lat.found(player,presence.sector)
    assert player.skills["listening"] == before
    assert lat.reveal(player,presence.sector,hidden.id,learn=True)
    game.commit_commerce()
    assert player.skills["listening"] == before+.5
