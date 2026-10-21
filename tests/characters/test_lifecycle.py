"""S07: headless multi-session identity, commit and restart scenarios."""

from datetime import timedelta
from pathlib import Path
import base64,json,zlib
from blacksite.server.players import pack_memory,unpack_memory
from blacksite.server.protocol import Frame
from blacksite.server.storage.db import Storage
from tests.harness import HeadlessServer
from tests.character_helpers import act,create,place,state
import pytest


def test_create_is_committed_before_rewards_or_body_and_retry_is_single(game: HeadlessServer) -> None:
    client=game.connect()
    create(game,client,commit=False)
    assert client.session.player_id is None and not game.core.world.actors
    game.commit_characters(error=True)
    assert not game.core.characters.players
    assert game.core.characters.wakes[client.session.id].stage == "card"
    act(game,client,Frame("intent",{"name":"menu_select","args":{}}))
    effects=game.commit_characters()
    game.step()
    player=game.core.characters.players[client.session.player_id]
    assert (player.archetype,player.health,player.stamina,player.chits_hand,player.grade)==("ghost",90,77,200,1)
    assert player.standing == {"unmoored":10} and player.faction is None
    assert player.rig["slots"] == ["prg_pick","prg_umbrella",None]
    assert len([e for e in effects if e["action"]=="create"])==1
    item_effect=next(e for e in effects if e["action"]=="create")
    counts={}
    for item in item_effect["items"]:
        counts[item["template"]]=counts.get(item["template"],0)+item["stack"]
    assert counts==dict(game.core.loop.content.starts["ghost"].items)


def test_safe_logout_reconnect_rename_and_terrain_survive_restart(game: HeadlessServer) -> None:
    client=game.connect()
    create(game,client)
    pid=client.session.player_id
    act(game,client,Frame("key",{"k":"down","t":0}))
    player=game.core.characters.players[pid]
    tile=player.tile
    game.core.sessions.disconnect(client.session)
    assert not game.core.world.actors
    other=HeadlessServer(game.core.loop.content,character_state=state(game))
    back=other.connect({"user_id":1,"handle":"New BBS Handle"})
    assert back.session.player_id==pid
    assert other.core.world.actors[pid].position==tile
    assert other.core.characters.players[pid].bbs_handle=="New BBS Handle"
    avatar=other.core.characters.sim.avatars[back.session.user_id]
    assert avatar.perception.remembered["vatside-wake-hall"]
    assert not other.core.characters.wakes
    welcome=other.frames_for(back)[0]
    assert welcome.data["player"]["name"]=="Wide界"


def test_contested_sleeper_reconnect_and_expiry(game: HeadlessServer) -> None:
    a=game.connect()
    create(game,a)
    place(game,a,"vatside-clinics",(30,18))
    assert game.core.characters.sim.views[a.session.id].previous["body"]["me"]["zone"]=="vatside-clinics"
    pid=a.session.player_id
    game.core.sessions.disconnect(a.session)
    assert game.core.world.actors[pid].stance=="sleeper"
    game.step(590)
    back=game.connect()
    assert game.core.world.actors[pid].position==(30,18)
    assert game.core.world.actors[pid].stance=="normal"
    game.core.sessions.disconnect(a.session) # replaced transport cannot detach it
    assert pid in game.core.world.actors
    game.core.sessions.disconnect(back.session)
    game.step(600)
    player=game.core.characters.players[pid]
    assert player.zone=="vatside-wake-hall" and player.clone_debt==0
    assert not game.core.characters.sleepers
    again=game.connect()
    assert again.session.player_id==pid and again.session.subscribed==player.zone


def test_contested_offline_restart_reconciles_real_elapsed_time(game: HeadlessServer) -> None:
    client=game.connect();create(game,client)
    place(game,client,"vatside-clinics",(30,18))
    game.core.sessions.disconnect(client.session)
    snapshot=state(game)
    snapshot["players"][0]["progress"]["offline_at"]=(game.clock.now_utc()-timedelta(seconds=120)).isoformat()
    restart=HeadlessServer(game.core.loop.content,character_state=snapshot)
    back=restart.connect()
    assert back.session.subscribed=="vatside-wake-hall"


def test_name_uniqueness_and_default_one_character(game: HeadlessServer) -> None:
    a=game.connect();create(game,a,name="Straße")
    b=game.connect({"user_id":2,"handle":"STRASSE"})
    game.step()
    act(game,b,Frame("intent",{"name":"menu_select","args":{}}))
    wake=game.core.characters.wakes[b.session.id]
    act(game,b,Frame("line",{"id":wake.prompt_id,"text":""}))
    assert wake.stage=="name" and "already in use" in wake.error
    game.core.sessions.disconnect(a.session)
    again=game.connect()
    assert again.session.player_id==a.session.player_id and len(game.core.characters.owned("1"))==1


def test_delete_requires_name_and_identity_clock_receipts_debt_survive(game: HeadlessServer) -> None:
    a=game.connect();create(game,a)
    manager=game.core.characters
    pid=a.session.player_id
    identity=manager.identities["1"]
    identity["receipts"]={"contract:one":True}
    first=identity["first_decanted_at"]
    manager.players[pid].clone_debt=123
    for typed in ("wrong", manager.players[pid].name):
        act(game,a,Frame("intent",{"name":"delete_character","args":{}}))
        act(game,a,Frame("line",{"id":"delete:"+pid,"text":typed}))
        if typed=="wrong":
            assert pid in manager.players and not manager.deleting
    effects=game.commit_characters()
    assert pid not in manager.players and not game.core.world.actors
    assert not any(e["action"]=="save" and e["player"]["id"]==pid for e in effects[1:])
    game.step(20)
    create(game,a,name="New Wake",card="none")
    player=manager.players[a.session.player_id]
    assert player.id!=pid and player.clone_debt==123 and not player.standing
    assert identity["first_decanted_at"]==first
    assert manager.identities["1"]["receipts"]=={"contract:one":True}


def test_compact_memory_bitmap_is_20000_bits_and_remembers_old_geometry() -> None:
    memory={(x,y):"wall" if x%2 else "floor" for y in range(100) for x in range(200)}
    blob=pack_memory(memory,200,100)
    assert unpack_memory(blob,200,100)==memory
    payload=json.loads(zlib.decompress(base64.b64decode(blob)))
    assert len(base64.b64decode(payload[3]))==2500 and len(blob)<1000


def test_storage_creation_atomic_restart_and_delete_never_resurrect(game: HeadlessServer,scratch_dir: Path) -> None:
    a=game.connect();effects=create(game,a)
    # Run the exact outbox against the real storage layer (no simulation I/O).
    store=Storage(scratch_dir/"world.db",game.clock)
    try:
        # The harness has a deterministic origin; set the isolated DB to match.
        store.mark_dirty("meta","origin",game.core.sessions.origin);store.flush_now()
        for effect in effects:
            store.character_write(effect)
        store.flush_now()
        loaded=store.character_state()
        assert loaded["players"][0]["name"]=="Wide界"
        assert store.db.execute("SELECT count(*) FROM items").fetchone()[0]>0
        pid=a.session.player_id
        # A stale write-behind identity must not undo the deletion's retained debt.
        game.core.characters.players[pid].clone_debt=123
        store.mark_dirty("identities","1",{**loaded["identities"]["1"],"clone_debt":0})
        act(game,a,Frame("intent",{"name":"delete_character","args":{}}))
        act(game,a,Frame("line",{"id":"delete:"+pid,"text":"Wide界"}))
        for effect in game.core.characters.outbox:
            store.character_write(effect)
        store.flush_now()
        assert not store.character_state()["players"]
        assert store.db.execute("SELECT count(*) FROM items").fetchone()[0]==0
        assert store.character_state()["identities"]["1"]["first_decanted_at"]
        assert store.character_state()["identities"]["1"]["clone_debt"]==123
    finally:
        store.close()


@pytest.mark.parametrize("archetype",range(4))
def test_all_starter_abilities_gear_and_no_card(game: HeadlessServer,archetype: int) -> None:
    a=game.connect();effects=create(game,a,archetype=archetype,card="none")
    player=game.core.characters.players[a.session.player_id]
    assert not player.standing and player.faction is None
    assert player.progress["known_programs"]==["prg_pick","prg_umbrella"]
    items=next(e["items"] for e in effects if e["action"]=="create")
    by_id={item["id"]:item for item in items}
    armour=by_id[player.equipment["body"]]["template"]
    assert armour==("arm_kestrel_vest" if archetype==0 else "arm_wake_coverall")
    if archetype==2:
        assert by_id[player.implants["head"]]["template"]=="imp_res_first_ear"
        assert player.progress["known_hymns"]==["hymn_steady"]
    if archetype==3:
        assert any(item["template"]=="drn_kestrel_mule" for item in items)


def test_briefing_resume_full_flow_and_frame_budget(game: HeadlessServer) -> None:
    a=game.connect();game.step()
    act(game,a,Frame("intent",{"name":"menu_select","args":{}}))
    wake=game.core.characters.wakes[a.session.id]
    act(game,a,Frame("line",{"id":wake.prompt_id,"text":""}))
    game.core.sessions.disconnect(a.session)
    back=game.connect();game.step()
    wake=game.core.characters.wakes[back.session.id]
    assert wake.stage=="briefing" and wake.name=="Wide界"
    count=3
    while wake.stage=="briefing":
        act(game,back,Frame("key",{"k":" ","t":0}));count+=1
    assert count<20 and wake.stage=="card"
    act(game,back,Frame("intent",{"name":"menu_close","args":{}}))
    game.commit_characters();game.step()
    assert back.session.player_id and not game.core.characters.players[back.session.player_id].standing


def test_raised_cap_offers_selection_without_changing_identity(game: HeadlessServer) -> None:
    a=game.connect();create(game,a)
    game.core.characters.cap=2
    game.core.sessions.disconnect(a.session)
    back=game.connect();game.step()
    assert game.core.characters.screens[back.session.id][0]=="characters"
    act(game,back,Frame("intent",{"name":"menu_cursor","args":{"delta":1}}))
    act(game,back,Frame("intent",{"name":"menu_select","args":{}}))
    create(game,back,name="Second Wake",card="none")
    assert len(game.core.characters.owned("1"))==2
    assert len(game.core.world.actors)==1


def test_grade_benefits_and_personhood_remain_after_xp_fade(game: HeadlessServer) -> None:
    a=game.connect();create(game,a)
    player=game.core.characters.players[a.session.player_id]
    assert player.progress["points"]==0
    player.update_progression(1500)
    game.step()
    assert player.grade==5 and player.attributes["vitals"]==24 and player.progress["points"]==12
    legal=player.legal_at
    assert legal is not None
    player.update_progression(0);game.step()
    assert player.grade==5 and player.progress["points"]==12 and player.legal_at==legal


def test_failed_storage_creation_rolls_back_all_reward_rows(game: HeadlessServer,scratch_dir: Path) -> None:
    import sqlite3
    a=game.connect();create(game,a,commit=False)
    effect=next(e for e in game.core.characters.outbox if e["action"]=="create")
    store=Storage(scratch_dir/"world.db",game.clock)
    try:
        store.db.execute("CREATE TRIGGER refuse_character BEFORE INSERT ON players BEGIN SELECT RAISE(ABORT,'injected write failure'); END")
        with pytest.raises(sqlite3.IntegrityError):
            store.character_write(effect)
        store.flush_now()
        assert store.db.execute("SELECT count(*) FROM players").fetchone()[0]==0
        assert store.db.execute("SELECT count(*) FROM items").fetchone()[0]==0
        assert not store.dirty
    finally:
        store.close()


def test_offline_character_cap_holds_service_lease_and_preserves_characters(scratch_dir: Path) -> None:
    from blacksite.admin.__main__ import character_cap
    from blacksite.server.storage.lease import Lease
    assert character_cap(scratch_dir,2)=={"character_cap":2}
    lease=Lease(scratch_dir/"world.db.sessions");lease.acquire()
    try:
        with pytest.raises(RuntimeError,match="lease"):
            character_cap(scratch_dir,3)
    finally:
        lease.release()
    store=Storage(scratch_dir/"world.db",HeadlessServer().clock)
    assert store.meta("character_cap")==2
    store.close()


def test_character_sheet_reaches_all_twelve_skills(game: HeadlessServer) -> None:
    a=game.connect();create(game,a)
    act(game,a,Frame("key",{"k":"P","t":0}))
    for _ in range(35):
        act(game,a,Frame("intent",{"name":"menu_cursor","args":{"delta":1}}))
    manager=game.core.characters
    cursor=manager.screens[a.session.id][1]
    body=manager.sheet(manager.players[a.session.player_id],cursor)
    assert body["rows"][cursor]["cells"][0]=="Listening"


def test_failed_logout_flush_retains_latest_position_for_retry(game: HeadlessServer,scratch_dir: Path) -> None:
    import sqlite3
    a=game.connect();effects=create(game,a)
    store=Storage(scratch_dir/"world.db",game.clock)
    try:
        for effect in effects:store.character_write(effect)
        player=game.core.characters.players[a.session.player_id]
        player.tile=(6,9)
        effect={"action":"save","user":"1","identity":game.core.characters.identities["1"],"player":player.record(),"immediate":True}
        store.db.execute("CREATE TRIGGER refuse_save BEFORE INSERT ON players BEGIN SELECT RAISE(ABORT,'injected disk failure'); END")
        with pytest.raises(sqlite3.IntegrityError):store.character_write(effect)
        assert store.dirty["players",player.id]["tile"]==[6,9]
        store.db.execute("DROP TRIGGER refuse_save")
        store.flush_now()
        assert json.loads(store.db.execute("SELECT tile FROM players WHERE id=?",(player.id,)).fetchone()[0])==[6,9]
    finally:
        store.close()


def test_idle_online_character_gets_full_reconnect_grace_after_crash(game: HeadlessServer) -> None:
    from blacksite.server.clock import ManualClock
    a=game.connect();create(game,a)
    place(game,a,"vatside-clinics",(30,18))
    game.step(1200) # Two minutes idle online is not two minutes offline.
    restart_clock=ManualClock(epoch=game.clock.now_utc()+timedelta(seconds=1))
    restart=HeadlessServer(game.core.loop.content,character_state=state(game),clock=restart_clock)
    back=restart.connect()
    assert back.session.subscribed=="vatside-clinics"
    assert restart.core.world.actors[back.session.player_id].position==(30,18)


def test_shock_decays_five_per_second_after_three_second_hit_grace(game: HeadlessServer) -> None:
    # Game design 3.1 and 5.3.
    a=game.connect();create(game,a)
    actor=game.core.world.actors[a.session.player_id]
    actor.shock=50
    actor.cooldowns["last_hit"]=game.clock.now_tick()
    game.step(29)
    assert actor.shock==50
    game.step(10)
    assert actor.shock==45


def test_upgrade_from_shipped_schema_one_preserves_origin_and_old_rows(scratch_dir: Path) -> None:
    import sqlite3
    from importlib import import_module
    from blacksite.server.clock import ManualClock
    path=scratch_dir/"world.db"
    with sqlite3.connect(path) as db:
        import_module("blacksite.server.storage.migrations.0001_initial").apply(db)
        db.executemany("INSERT INTO meta(key,value) VALUES(?,?)",[("schema_version","1"),("origin",json.dumps("existing-origin"))])
        db.execute("INSERT INTO players(id,origin,bbs_user_id,health) VALUES('old','existing-origin','1',130)")
    store=Storage(path,ManualClock())
    try:
        assert store.origin=="existing-origin" and store.meta("schema_version")==2
        assert store.db.execute("SELECT health FROM players WHERE id='old'").fetchone()[0]==130
        assert {"name_key","progress"} <= store.player_columns
        assert store.meta("character_cap")==1
    finally:
        store.close()


def test_raised_cap_chooser_cannot_undo_sleeper_recovery_or_create_a_zoneless_sleeper(game: HeadlessServer) -> None:
    a=game.connect();create(game,a)
    game.core.characters.cap=2
    place(game,a,"vatside-clinics",(30,18))
    pid=a.session.player_id
    game.core.sessions.disconnect(a.session)
    chooser=game.connect()
    game.step(650)
    assert game.core.characters.players[pid].zone=="vatside-wake-hall"
    # Leaving the chooser must not treat an unattached avatar as a fresh
    # logout and later try to recover a physical body whose zone is None.
    game.core.sessions.disconnect(chooser.session)
    game.step(601)
    assert not game.core.characters.sleepers
    assert not game.core.world.actors
