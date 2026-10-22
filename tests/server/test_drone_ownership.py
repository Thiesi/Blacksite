"""Game 5.3: one persistent item, controlled deployment and no recall repair."""

import pytest

from blacksite.server.protocol import Frame
from tests.character_helpers import act, place, state
from tests.combat.test_engine import body, build_duel
from tests.harness import HeadlessServer
from tests.server.test_substances import give


@pytest.fixture
def operator(repo_root):
    game,a,b = build_duel(repo_root,first_archetype=3)
    player = game.core.characters.players[a.session.player_id]
    assert player.archetype == "operator"
    return game,a,b,player,game.core.progression.drones


def test_game_5_3_deploy_save_failure_keeps_exact_instance_then_use_deploys(operator):
    game,a,b,player,engine = operator
    iid = give(game,a,"drn_kestrel_mule")
    game.core.commerce.items[iid].quality = 1.08
    act(game,a,Frame("intent",{"name":"inv.use","args":{"item":iid}}))
    assert iid in player.inventory and iid not in engine.actors
    game.commit_commerce(error=True)
    assert iid in player.inventory and not engine.records(player)
    act(game,a,Frame("intent",{"name":"inv.use","args":{"item":iid}}))
    game.commit_commerce()
    assert iid not in player.inventory and engine.actors[iid].health == 60
    assert game.core.commerce.items[iid].owner == player.id
    assert game.core.commerce.items[iid].quality == 1.08
    assert game.core.progression.modifiers(player).bonus("carry_kg") == 20
    with pytest.raises(ValueError,match="already deployed"):
        engine.command(player,iid,"deploy")


def test_game_5_3_recall_and_restart_preserve_condition_without_cloning(operator):
    game,a,b,player,engine = operator
    iid = give(game,a,"drn_halvard_sentry")
    engine.command(player,iid,"deploy"); game.commit_commerce()
    actor = engine.actors[iid]
    actor.health = 17
    assert engine.command(player,iid,"recall")
    assert actor.id in game.core.world.actors and iid not in player.inventory
    game.commit_commerce()
    assert actor.id not in game.core.world.actors and player.inventory.count(iid) == 1
    assert game.core.commerce.items[iid].health == 17
    engine.command(player,iid,"deploy"); game.commit_commerce()
    assert engine.actors[iid].health == 17
    restored = HeadlessServer(game.core.loop.content,character_state=state(game),clock=game.clock)
    returning = restored.connect({"user_id":1,"handle":"Wake界1","node_name":"test"})
    restored.step()
    resident = restored.core.characters.players[player.id]
    drones = restored.core.progression.drones
    if iid not in drones.actors:
        drones.command(resident,iid,"deploy"); restored.commit_commerce()
    assert drones.actors[iid].health == 17
    assert iid not in resident.inventory and len([key for key in restored.core.commerce.items if key == iid]) == 1


def test_game_3_2_operator_two_slots_uplink_adds_one_and_foreign_commands_refuse(operator):
    game,a,b,player,engine = operator
    ids = [give(game,a,tid) for tid in ("drn_kestrel_mule","drn_ostrom_eye","drn_halvard_sentry")]
    for iid in ids[:2]:
        engine.command(player,iid,"deploy"); game.commit_commerce()
    with pytest.raises(ValueError,match="2 drone slots"):
        engine.command(player,ids[2],"deploy")
    uplink = give(game,a,"imp_ow_drone_uplink")
    player.implants["head"] = uplink
    engine.command(player,ids[2],"deploy"); game.commit_commerce()
    assert len(engine.records(player)) == 3
    other = game.core.characters.players[b.session.player_id]
    with pytest.raises(ValueError,match="you own"):
        engine.command(other,ids[0],"recall")


@pytest.mark.parametrize("archetype",[0,1,2])
def test_game_3_2_other_archetypes_need_an_uplink(repo_root,archetype):
    game,a,b = build_duel(repo_root,first_archetype=archetype)
    player = game.core.characters.players[a.session.player_id]
    engine = game.core.progression.drones
    iid = give(game,a,"drn_kestrel_mule")
    with pytest.raises(ValueError,match="0 drone slots"):
        engine.command(player,iid,"deploy")
    player.implants["head"] = give(game,a,"imp_ow_drone_uplink")  # Disclosed installed-hardware fixture.
    engine.command(player,iid,"deploy"); game.commit_commerce()
    assert len(engine.records(player)) == 1


def test_game_5_3_hold_follow_and_idle_toggles_do_not_farm_skill(operator):
    game,a,b,player,engine = operator
    iid = give(game,a,"drn_kestrel_mule")
    engine.command(player,iid,"deploy"); game.commit_commerce()
    actor = engine.actors[iid]
    start = actor.position
    before = player.skills["drones"]
    engine.command(player,iid,"hold"); game.commit_commerce()
    zone = game.core.world.zones[actor.zone]
    occupied = {other.position for other in zone.actors.values() if other.id not in (actor.id,player.id)}
    destination = next((actor.x+3*dx,actor.y+3*dy) for dx,dy in ((-1,0),(1,0),(0,1),(0,-1))
        if all(zone.passable((actor.x+n*dx,actor.y+n*dy)) and (actor.x+n*dx,actor.y+n*dy) not in occupied for n in (1,2,3)))
    place(game,a,actor.zone,destination)
    game.step(10)
    assert actor.position == start
    engine.command(player,iid,"follow"); game.commit_commerce()
    game.step(20)
    assert actor.position != start
    assert player.skills["drones"] == before


def test_game_5_3_destroyed_unit_deletes_once_with_rollback_and_no_controller_defeat_xp(operator):
    game,a,b,player,engine = operator
    iid = give(game,a,"drn_halvard_sentry")
    engine.command(player,iid,"deploy"); game.commit_commerce()
    actor = engine.actors[iid]
    opponent = game.core.characters.players[b.session.player_id]
    xp = opponent.xp
    game.core.combat.hurt(body(game,b),actor,999)
    assert iid in engine.records(player) and iid in game.core.commerce.items
    game.commit_commerce(error=True)
    assert actor.health == 1 and iid in engine.records(player)
    game.core.combat.hurt(body(game,b),actor,999)
    game.commit_commerce()
    assert iid not in game.core.commerce.items and iid not in engine.records(player)
    assert actor.id not in game.core.world.actors and opponent.xp == xp
