"""Game design 5.5 and 7.2: lifecycle, safe patrols and committed loot."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from random import Random

import pytest

from blacksite.content.loader import load_content
from blacksite.content.schema import Behaviour, Region, Spawner
from blacksite.content.validate import validate
from blacksite.server.npcs.behaviours import patrol
from blacksite.server.npcs.templates import WANDER_PAUSE_TICKS, make_actor, relation
from blacksite.server.protocol import Frame
from blacksite.server.storage.db import Storage
from tests.character_helpers import act, create, place, state
from tests.harness import FakeClient, HeadlessServer


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


@pytest.mark.parametrize("players, expected", [
    (((20, 3),), {(26, 3), (27, 3), (28, 3), (29, 3)}),
    (((20, 3), (29, 3)), {(24, 3), (25, 3)}),
    ((), {(x, 3) for x in range(21, 30)}),
])
def test_design_5_5_spawn_clearance_and_farthest_fallback(city, monkeypatch, players, expected):
    game, caller = city
    zone = game.core.world.zones["vatside-clinics"]
    runner = body(game, caller)
    game.core.world.leave(runner)
    for index, position in enumerate(players):
        player = deepcopy(runner)
        player.id = f"clearance-player-{index}"
        game.core.world.enter(player, zone.id, position)
    spec = Spawner("clearance", "npc-patient", 1, 60, region=Region(21, 3, 9, 1))
    choices = []
    def choose(candidates):
        choices.append(set(candidates))
        return candidates[0]
    monkeypatch.setattr(zone.rng, "choice", choose)
    assert game.core.npcs.spawners.location(zone, spec) in expected
    assert choices == [expected]  # Exactly one draw, including fallback ties.


def test_design_5_5_spawn_never_uses_a_player_tile(city, monkeypatch):
    game, caller = city
    zone = game.core.world.zones["vatside-clinics"]
    spec = Spawner("clearance", "npc-patient", 1, 60, tile=body(game, caller).position)
    def no_draw(candidates):
        pytest.fail("A deferred spawn must not draw RNG")
    monkeypatch.setattr(zone.rng, "choice", no_draw)
    assert game.core.npcs.spawners.location(zone, spec) is None


@pytest.mark.parametrize("tile", [(21, 3), (21, 4), (20, 4)])
def test_design_5_5_spawn_fills_an_adjacent_authored_post_when_no_farther_tile_exists(city, tile):
    game, caller = city
    zone = game.core.world.zones["vatside-clinics"]
    spec = Spawner("clearance", "npc-patient", 1, 60, tile=tile)
    assert game.core.npcs.spawners.location(zone, spec) == tile


def test_design_5_5_shipped_halo_post_fills_beside_arriving_caller(city, repo_root):
    game, caller = city
    zone = game.core.world.zones["sodium-tin-halo"]
    shipped = load_content(repo_root / "src/blacksite/content").zones[zone.id]
    spec = next(sp for sp in shipped.meta.spawners if sp.id == "halo-bouncer")
    zone.template = replace(zone.template, meta=replace(zone.template.meta, spawners=(spec,)))
    place(game, caller, zone.id, zone.template.meta.spawn)
    bouncers = [a for a in zone.actors.values() if a.behaviour.get("spawner") == spec.id]
    assert len(bouncers) == 1
    assert bouncers[0].position == (4, 3)
    assert body(game, caller).position == (3, 3)


@pytest.mark.parametrize("key", ["npc-patient", "npc-sodium-regular", "npc-plainclothes-warden"])
def test_design_5_5_every_wanderer_returns_from_outside_region_without_extra_rng(city, key):
    game, caller = city
    zone = game.core.world.zones["vatside-clinics"]
    region = Region(26, 3, 4, 1)
    actor = make_actor(game.core.loop.content.npcs[key], "returning-wanderer",
                       {"home": (26, 3), "region": region})
    game.core.world.enter(actor, zone.id, (24, 3))
    expected_rng = Random()
    expected_rng.setstate(zone.rng.getstate())
    expected_rng.choice((-1, 0, 1)); expected_rng.choice((-1, 0, 1))
    pause = expected_rng.randint(*WANDER_PAUSE_TICKS)
    avoid = game.core.npcs.spawners.reserved(zone)
    game.core.npcs.act(actor, zone, 100, avoid)
    assert actor.position == (25, 3)
    assert actor.behaviour["pause"] == 100 + pause
    assert zone.rng.getstate() == expected_rng.getstate()
    for tick in range(120, 201, 20):
        game.core.npcs.act(actor, zone, tick, avoid)
        if region.contains(actor.position):
            break
    assert region.contains(actor.position)


@pytest.mark.parametrize("kind", ["wander", "patrol"])
def test_design_5_5_tick_keeps_wander_and_patrol_off_exit(city, monkeypatch, kind):
    game, caller = city
    actor = spawn(game, "npc-patient")[0]
    zone = game.core.world.zones[actor.zone]
    blocked = (25, 3)
    exit_ = replace(zone.template.meta.exits[0], tile=blocked)
    zone.template = replace(zone.template, meta=replace(zone.template.meta, spawners=(), exits=(exit_,)))
    content = game.core.loop.content
    template = content.npcs[actor.behaviour["template"]]
    content.npcs[template.id] = replace(template,
        behaviours=(Behaviour(kind, {"waypoints": [blocked]}),))
    actor.behaviour.update(region=Region(23, 2, 5, 3), pause=0, state="idle")
    actor.cooldowns.clear()
    # The first attempted step goes straight onto the exit.
    values = iter((1, 0))
    monkeypatch.setattr(zone.rng, "choice", lambda candidates: next(values))
    before = actor.position
    game.step()
    assert actor.position != before
    assert actor.position != blocked


@pytest.mark.parametrize("key, exit_id, start", [
    ("npc-sodium-regular", "to-core-plaza", (3, 2)),
    ("npc-plainclothes-warden", "to-sodium-tin-halo", (94, 25)),
])
def test_design_5_5_shipped_row_wanderers_keep_plaza_and_halo_exits_clear(city, repo_root, monkeypatch, key, exit_id, start):
    game, caller = city
    place(game, caller, "sodium-row", (44, 20))
    zone = game.core.world.zones["sodium-row"]
    # Restore the shipped region, removed only by the isolated city fixture.
    shipped = load_content(repo_root / "src/blacksite/content").zones["sodium-row"]
    spec = next(sp for sp in shipped.meta.spawners if sp.npc == key)
    home = (max(spec.region.x, min(start[0], spec.region.x + spec.region.w - 1)),
            max(spec.region.y, min(start[1], spec.region.y + spec.region.h - 1)))
    actor = make_actor(game.core.loop.content.npcs[key], "row-wanderer",
                       {"home": home, "region": spec.region, "state": "idle"})
    game.core.world.enter(actor, zone.id, start)
    exit_ = next(ex for ex in zone.template.meta.exits if ex.id == exit_id)
    assert zone.can_enter(actor, exit_.tile)
    delta = (exit_.tile[0]-start[0], exit_.tile[1]-start[1])
    values = iter(delta)
    monkeypatch.setattr(zone.rng, "choice", lambda candidates: next(values))
    game.step()
    assert actor.position != exit_.tile
    assert actor.position != start


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


def test_design_5_5_local_guard_investigates_report_beyond_sight(city):
    game,caller=city
    guard=spawn(game)[0]
    zone=game.core.world.zones[guard.zone]
    runner=body(game,caller)
    game.core.world.enter(guard,zone.id,(50,3))
    from blacksite.server.npcs.templates import make_actor
    # This fixture exercises same-faction reporting, not the Row's now
    # unaffiliated street crowd (#147; keeper-wide response waits for S38).
    resident_template=replace(game.core.world.content.npcs["npc-sodium-regular"],faction="sable")
    resident=make_actor(resident_template,"reported-resident",{"spawner":"residents"})
    game.core.world.enter(resident,zone.id,(22,3))
    assert not game.core.combat.visible(guard,runner)
    game.core.npcs.provoked(runner,resident)
    assert guard.target==runner.id and guard.behaviour["last_position"]==runner.position
    game.step(5)
    assert guard.x<50


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


def test_design_5_5_refused_input_coalesces_saves_and_logs(city):
    game,caller=city
    place(game,caller,"core-plaza",(20,3))
    source=body(game,caller);game.core.characters.outbox.clear()
    for _ in range(20):
        game.core.npcs.refused(source,source)
    assert len(game.core.characters.outbox)==1
    assert sum("Wardens: lower" in line["text"] for line in caller.session.log_ring)==1
    game.clock.advance(9)
    game.core.npcs.refused(source,source)
    assert len(game.core.characters.outbox)==1
    player=game.core.characters.players[source.id]
    assert (datetime.fromisoformat(player.warden_heat_until)-game.clock.now_utc()).total_seconds()==600
    game.clock.advance()
    game.core.npcs.refused(source,source)
    assert len(game.core.characters.outbox)==2


def test_design_5_5_summoned_responders_never_reward_kills(city):
    game,caller=city
    responder=spawn(game,"npc-warden-response")[0]
    player=game.core.characters.players[caller.session.player_id]
    before=player.xp
    game.core.combat.hurt(body(game,caller),responder,1000)
    game.commit_commerce()
    assert not game.core.commerce.caches and player.xp == before


def test_architecture_6_2_nonfatal_npc_damage_checkpoints_but_down_is_immediate(city):
    game,caller=city
    guard=spawn(game)[0];runner=body(game,caller)
    game.core.characters.outbox.clear()
    game.core.combat.hurt(guard,runner,3)
    assert game.core.characters.outbox[-1]["immediate"] is False
    assert game.core.characters.outbox[-1]["player"]["health"]==runner.health
    game.core.combat.hurt(guard,runner,1000)
    assert runner.stance=="down" and game.core.characters.outbox[-1]["immediate"] is True


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


@pytest.mark.parametrize('reserved_kind', ['exit', 'object', 'spawn'])
def test_design_5_5_flee_keeps_service_and_exit_tiles_clear(
        city: tuple[HeadlessServer, FakeClient], reserved_kind: str) -> None:
    game, caller = city
    actor = spawn(game)[0]
    runner = body(game, caller)
    zone = game.core.world.zones[actor.zone]
    blocked = (25, 3)  # The next retreat step away from the caller at (20,3).
    exit_ = replace(zone.template.meta.exits[0],
                    tile=blocked if reserved_kind == 'exit' else (26, 3))
    meta = replace(zone.template.meta, exits=(exit_,),
                   spawn=blocked if reserved_kind == 'spawn' else zone.template.meta.spawn)
    zone.template = replace(zone.template, meta=meta)
    if reserved_kind == 'object':
        obj = next(iter(zone.objects.values()))
        obj.spec = replace(obj.spec, tile=blocked)
    avoid = game.core.npcs.spawners.reserved(zone)
    assert blocked in avoid and zone.passable(blocked)
    game.core.npcs.provoked(runner, actor)
    actor.health = actor.health_max // 10
    tick = game.clock.now_tick() + 100
    game.core.npcs.evaluate(actor, zone, tick)
    assert actor.behaviour['state'] == 'flee'
    before = actor.position
    game.core.npcs.act(actor, zone, tick, avoid)
    assert actor.position not in avoid
    assert actor.position != before
    assert sum((a-b)**2 for a,b in zip(actor.position, runner.position)) > sum(
        (a-b)**2 for a,b in zip(before, runner.position))



def test_game_7_2_unaffiliated_row_regular_does_not_alert_sable(
        city: tuple[HeadlessServer, FakeClient]) -> None:
    game, caller = city
    guard = spawn(game)[0]
    zone = game.core.world.zones[guard.zone]
    runner = body(game, caller)
    from blacksite.server.npcs.templates import make_actor
    resident = make_actor(game.core.world.content.npcs['npc-sodium-regular'], 'row-regular', {})
    assert resident.faction is None
    game.core.world.enter(resident, zone.id, (22, 3))
    game.core.npcs.provoked(runner, resident)
    assert guard.target is None
