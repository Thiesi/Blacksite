"""Game design 5.5 and 7.2: lifecycle, safe patrols and committed loot."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from blacksite.content.loader import load_content
from blacksite.content.schema import Behaviour, Region, Spawner
from blacksite.content.validate import validate
from blacksite.server.npcs.behaviours import patrol
from blacksite.server.npcs.templates import relation
from blacksite.server.protocol import Frame
from blacksite.server.storage.db import Storage
from tests.character_helpers import act, create, place, state
from tests.harness import HeadlessServer


@pytest.fixture
def city(repo_root):
    content = load_content(repo_root/"src/blacksite/content")
    content.zones = {key: replace(z, meta=replace(z.meta, spawners=())) for key,z in content.zones.items()}
    game = HeadlessServer(content, character_state={})
    caller = game.connect()
    create(game, caller, card="none")
    player = game.core.characters.players[caller.session.player_id]
    player.progress["wake_combat"] = "skipped"
    place(game, caller, "vatside-clinics", (20,3))
    return game, caller


def body(game, caller):
    return game.core.characters.sim.avatars[caller.session.user_id].actor


def spawn(game, key="npc-sable-enforcer", count=1, tile=(24,3)):
    zone = game.core.world.zones["vatside-clinics"]
    spec = Spawner("test-group", key, count, 60, region=Region(tile[0],tile[1],max(1,count),1), condition="always")
    zone.template = replace(zone.template, meta=replace(zone.template.meta, spawners=(spec,)))
    game.step()
    return sorted((a for a in zone.actors.values() if a.kind != "player"), key=lambda a:a.id)


def test_design_5_5_count_respawn_and_lazy_catchup(city):
    game, caller = city
    actors = spawn(game, count=2)
    assert len(actors) == 2
    old = actors[0]
    game.core.npcs.spawners.removed(old, game.core.combat.now())
    game.core.world.leave(old)
    game.clock.advance(599); game.step()
    assert len([a for a in game.core.world.actors.values() if a.kind == "npc"]) == 2
    game.clock.advance(100000); game.step()
    assert len([a for a in game.core.world.actors.values() if a.kind == "npc"]) == 2
    assert old.id not in game.core.world.actors


def test_design_5_5_dormant_35_minutes_rebuilds_but_keeps_anchor(city):
    game, caller = city
    actor = spawn(game)[0]
    zone = game.core.world.zones[actor.zone]
    place(game, caller, "core-plaza", (20,3))
    game.clock.advance(35*60*10); game.step()
    assert actor.id not in game.core.world.actors
    place(game, caller, zone.id, (20,3))
    assert len([a for a in zone.actors.values() if a.kind == "npc"]) == 1


def test_design_5_5_named_service_anchor_stays_on_dormancy(city):
    game, caller = city
    actor = spawn(game,"npc-sablier-orderly")[0]
    place(game, caller,"core-plaza",(20,3))
    game.clock.advance(35*60*10);game.step()
    assert game.core.world.actors[actor.id] is actor


def test_design_5_5_event_spawner_waits_for_explicit_event(city):
    game, caller=city
    actor=spawn(game)[0]
    zone=game.core.world.zones[actor.zone]
    game.core.world.leave(actor)
    spec=replace(zone.template.meta.spawners[0],condition="event:test-event")
    zone.template=replace(zone.template,meta=replace(zone.template.meta,spawners=(spec,)))
    game.step()
    assert not [a for a in zone.actors.values() if a.kind=="npc"]
    game.core.npcs.spawners.enabled_events.add("test-event");game.step()
    assert len([a for a in zone.actors.values() if a.kind=="npc"])==1


def test_design_5_5_wander_region_and_evaluation_stagger(city):
    game,caller=city
    actors=spawn(game,"npc-patient",count=5,tile=(25,3))
    phases=set()
    for _ in range(30):
        game.step()
        for actor in actors:
            assert actor.behaviour["region"].contains(actor.position)
            if actor.behaviour.get("evaluated")==game.clock.now_tick():
                assert game.clock.now_tick()%5==actor.behaviour["phase"]
                phases.add(actor.behaviour["phase"])
    assert len(phases)==5


def test_design_5_5_patrol_loop_and_bounce(city):
    game,caller=city
    actor=spawn(game)[0];zone=game.core.world.zones[actor.zone]
    points=[(24,3),(26,3)]
    seen=set()
    for tick in range(100,130):
        patrol(actor,zone,points,tick,True)
        seen.add(actor.position)
    assert set(points)<=seen and actor.behaviour["patrol_direction"] in (-1,1)


def test_design_5_5_patrols_slide_around_head_on_traffic(city):
    game,caller=city
    a,b=spawn(game,count=2)
    zone=game.core.world.zones[a.zone]
    game.core.world.leave(a);game.core.world.leave(b)
    game.core.world.enter(a,zone.id,(24,3));game.core.world.enter(b,zone.id,(27,3))
    a.behaviour["waypoint"]=1
    b.behaviour["waypoint"]=0
    points=[(24,3),(27,3)]
    visited={a.id:set(),b.id:set()}
    for tick in range(100,180):
        for actor in (a,b):
            patrol(actor,zone,points,tick,True)
            visited[actor.id].add(actor.position)
    assert all(set(points)<=positions for positions in visited.values())


def test_design_7_2_matrix_freelance_and_hostile_guard(city):
    game,caller=city
    actor=spawn(game)[0];runner=body(game,caller)
    assert relation(game.core.world.content,"sable","kestrel")=="H"
    assert relation(game.core.world.content,"kestrel","kestrel")=="A"
    assert not game.core.npcs.hostile(actor,runner)
    runner.faction="kestrel"
    game.step(5)
    assert actor.target==runner.id
    game.step(30);game.commit_commerce()
    assert runner.cooldowns.get("combat",0)>0


def test_design_5_5_open_does_not_make_freelance_hostile(city):
    game,caller=city
    actor=spawn(game)[0];runner=body(game,caller)
    zone=game.core.world.zones[actor.zone]
    zone.template=replace(zone.template,meta=replace(zone.template.meta,safety="open"))
    assert not game.core.npcs.hostile(actor,runner)
    content=game.core.world.content
    content.npcs["npc-sable-enforcer"]=replace(content.npcs["npc-sable-enforcer"],behaviours=(Behaviour("guard",{"hostile_all":True}),))
    assert game.core.npcs.hostile(actor,runner)


def test_design_5_5_provocation_expires_after_five_minutes(city):
    game,caller=city
    actor=spawn(game)[0];runner=body(game,caller)
    game.core.npcs.provoked(runner,actor)
    assert game.core.npcs.hostile(actor,runner)
    game.clock.advance(3000);game.step()
    assert not game.core.npcs.hostile(actor,runner)
    game.step(5)
    assert actor.target is None


def test_design_5_5_hunt_loses_sight_after_twenty_seconds(city):
    game,caller=city
    actor=spawn(game)[0];runner=body(game,caller)
    runner.faction="kestrel"
    game.step(5)
    assert actor.target==runner.id
    game.core.npcs.combat.visible=lambda source,target:False
    game.step(195)
    assert actor.target==runner.id
    game.step(10)
    assert actor.target is None


def test_design_5_5_flee_below_twenty_percent(city):
    game,caller=city
    actor=spawn(game)[0];runner=body(game,caller)
    game.core.npcs.provoked(runner,actor)
    actor.health=actor.health_max//10
    game.step(5)
    assert actor.behaviour["state"]=="flee"


def test_design_5_5_warning_heat_response_and_no_safe_damage(city):
    game,caller=city
    place(game,caller,"core-plaza",(20,3))
    source=body(game,caller)
    npc=game.core.world.content.npcs["npc-civilian"]
    from blacksite.server.npcs.templates import make_actor
    target=make_actor(npc,"test-civilian",{})
    game.core.world.enter(target,source.zone,(22,3))
    hp=(source.health,target.health)
    for _ in range(3):
        act(game,caller,Frame("intent",{"name":"fire","args":{"target":target.id}}))
        game.commit_commerce()
    player=game.core.characters.players[source.id]
    assert 599 < (datetime.fromisoformat(player.warden_heat_until)-game.clock.now_utc()).total_seconds() <= 600
    assert len([a for a in game.core.world.actors.values() if a.behaviour.get("response")==source.id])==2
    game.step(100);game.commit_commerce()
    assert (source.health,target.health)==hp
    assert game.core.characters.me(caller.session)["heat_until"]
    assert any("Wardens: lower" in line["text"] for line in caller.session.log_ring)


def test_design_5_5_heat_restart_curfew_and_expiry(city,tmp_path):
    game,caller=city
    runner=body(game,caller)
    player=game.core.characters.players[runner.id]
    place(game,caller,"core-plaza",(20,3))
    game.core.npcs.heat_multiplier=2
    game.core.npcs.refused(runner,runner)
    until=player.warden_heat_until
    assert (datetime.fromisoformat(until)-game.clock.now_utc()).total_seconds()==1200
    saved=state(game)
    restarted=HeadlessServer(game.core.world.content,character_state=saved,clock=game.clock)
    assert restarted.core.characters.players[runner.id].warden_heat_until==until
    with_store=Storage(tmp_path/"world.db",game.clock)
    with_store.mark_dirty("players",player.id,player.record());with_store.flush_now()
    assert with_store.character_state()["players"][0]["warden_heat_until"]==until
    with_store.close()
    game.clock.advance(12000);game.step()
    assert not game.core.characters.me(caller.session)["heat_until"]


def test_design_5_5_heat_pursuit_stops_at_pocket_and_expiry(city):
    game,caller=city
    guard=spawn(game,"npc-warden-response")[0]
    runner=body(game,caller);player=game.core.characters.players[runner.id]
    player.warden_heat_until=(game.clock.now_utc()+timedelta(seconds=600)).isoformat()
    game.step(5)
    assert guard.target==runner.id
    zone=game.core.world.zones[runner.zone]
    zone.template=replace(zone.template,meta=replace(zone.template.meta,pockets=(Region(19,2,3,3),)))
    hp=runner.health
    game.step(50);game.commit_commerce()
    assert guard.target is None and runner.health==hp
    zone.template=replace(zone.template,meta=replace(zone.template.meta,pockets=()))
    game.clock.advance(6000);game.step(5)
    assert guard.target is None


@pytest.mark.parametrize("failure",[False,True])
def test_design_5_5_npc_loot_commits_once_and_respawn_receipt(city,tmp_path,failure):
    game,caller=city
    actor=spawn(game,"npc-sodium-regular")[0]
    source=body(game,caller)
    game.core.combat.hurt(source,actor,1000)
    game.core.combat.hurt(source,actor,1000)
    assert not game.core.commerce.caches and actor.stance=="dead"
    effects=game.commit_commerce(error=failure)
    assert len(effects)==1
    if failure:
        assert actor.id in game.core.world.actors and actor.health==1
        assert not game.core.commerce.caches
        return
    assert actor.id not in game.core.world.actors
    assert len(game.core.commerce.caches)==1
    cache=next(iter(game.core.commerce.caches.values()))
    assert cache["killer"]==source.id and len(cache["items"])==1
    store=Storage(tmp_path/"npc.db",game.clock)
    store.commerce_write(effects[0])
    restored=store.character_state()
    slot=next(iter(restored["npcs"]["slots"].values()))
    assert slot["until"]==game.core.combat.now()+60
    assert len(restored["commerce"]["caches"])==1
    store.close()


def test_design_7_2_shipped_matrix_matches_canon_and_hub_validates(repo_root):
    content=load_content(repo_root/"src/blacksite/content")
    assert validate(content)==[]
    assert len(content.factions)==8
    assert all(zone.meta.spawners for zone in content.zones.values())
    table=(repo_root/"docs/design/00-game-design.md").read_text(encoding="utf-8").split("### 7.2 Relations matrix")[1].split("### 7.3")[0]
    ids=["halvard","sablier","kestrel","wardens","choir","sable","unmoored","ferrymen"]
    for fid in ids:
        row=next(line for line in table.splitlines() if line.startswith("| "+fid.title()+" |"))
        cells=[c.strip() for c in row.split("|")[2:-1]]
        assert content.factions[fid].relations=={other:cells[i] for i,other in enumerate(ids) if other!=fid}


def test_design_5_3_mission_ownership_consent_and_nonlethal_subdue(city):
    game,caller=city
    source=body(game,caller)
    engine=game.core.npcs
    target=engine.spawn_mission(source,"escort-test","npc-sablier-orderly",(24,3))
    assert not engine.escort(source,target)
    target.behaviour["willing"]=True
    assert engine.escort(source,target)
    game.step(10)
    assert target.x < 24
    target.behaviour.pop("escort")
    game.core.world.enter(target,source.zone,(21,3))
    target.shock=80
    assert engine.subdue(source,target)
    game.step(29)
    assert target.id in game.core.world.actors
    game.step()
    assert target.stance=="restrained" and target.behaviour["resolution"]=="subdued"
    assert not game.core.commerce.caches


def test_design_5_3_other_caller_cannot_harm_mission_and_subdue_interrupts(city):
    game,caller=city
    source=body(game,caller)
    target=game.core.npcs.spawn_mission(source,"clear-test","npc-maintenance-drone",(21,3))
    other=game.connect({"user_id":2,"handle":"Other界","node_name":"test"})
    create(game,other,name="Other",card="none");place(game,other,source.zone,(22,3))
    assert not game.core.combat.legal(body(game,other),target)
    assert not game.core.combat.legal(target,body(game,other))
    target.shock=80
    assert game.core.npcs.subdue(source,target)
    source.cooldowns["last_hit"]=game.clock.now_tick()
    game.step(30)
    assert target.id in game.core.world.actors and not game.core.npcs.restraints


def test_design_18_maintenance_drone_warns_before_harm(city):
    game,caller=city
    source=body(game,caller)
    target=game.core.npcs.spawn_mission(source,"drone-test","npc-maintenance-drone",(24,3))
    hp=source.health
    game.step(19)
    assert source.health==hp
    game.step(25);game.commit_commerce()
    assert source.cooldowns.get("combat",0)>0


def test_design_5_5_npc_sight_matches_full_fov_for_walls_radius_and_stealth(city):
    from blacksite.server.world.sight import sees_actor, visible_tiles
    game,caller=city
    observer=spawn(game)[0];target=body(game,caller)
    zone=game.core.world.zones[observer.zone]
    radius=zone.template.meta.sight_radius
    for stance in ("normal","stealth"):
        target.stance=stance
        for tile in ((20,3),(35,3),(37,3),(24,8),(12,8)):
            target.x,target.y=tile
            expected=sees_actor(observer,target,visible_tiles(observer,zone,radius),radius)
            assert game.core.combat.visible(observer,target)==expected
