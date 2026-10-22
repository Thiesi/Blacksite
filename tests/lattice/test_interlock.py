"""Game 6.4: durable controls, physical bodies and bounded disruption."""

from copy import deepcopy
from dataclasses import replace

import pytest

from blacksite.server.clock import TICK_HZ
from tests.character_helpers import place, state
from tests.harness import HeadlessServer
from tests.lattice.test_engine import actor, intent, runners
from tests.lattice.test_encounters import enter


def flip(game, client, cid="hall-doors"):
    presence = game.core.lattice.presences[client.session.player_id]
    intent(game, client, "lat.flip", control=cid)
    assert presence.procedure and presence.procedure.kind == "flip"
    game.step(presence.procedure.until-game.clock.now_tick())


def control_room(game, presence, cid="hall-doors"):
    instance = game.core.lattice.encounters.core(presence)
    presence.room = next(r.id for r in instance.graph.rooms.values() if any(c.id == cid for c in r.controls))
    for ice in instance.ice.values():
        ice.integrity = 0  # Isolate interlock from S14 encounter tests.
    spec = game.core.lattice.interlock.controls[presence.core, cid]
    obj = game.core.world.zones[spec.target.zone].objects[spec.target.object]
    obj.spec = replace(obj.spec, params={**obj.spec.params, "open": False})
    obj.open = False
    return spec


def cut_fixture(game, client):
    interlock = game.core.lattice.interlock
    (zid, oid), _ = next((key, core) for key, core in interlock.hardware.items() if core == "lat-civic-ledger")
    zone = game.core.world.zones[zid]
    zone.template = replace(zone.template, meta=replace(zone.template.meta, safety="open", pockets=()))
    tile = zone.objects[oid].spec.tile
    place(game, client, zid, tile)
    return zid, oid


def test_game_6_4_flip_commits_before_object_and_trace(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    spec = control_room(game, presence)
    zone = game.core.world.zones[spec.target.zone]
    obj = zone.objects[spec.target.object]
    flip(game, a)
    before_trace = presence.trace
    assert not obj.open and game.core.commerce.pending
    effects = game.commit_commerce()
    assert obj.open and presence.trace == before_trace+10
    assert effects[0]["interlock_state"]["effects"]["lat-civic-ledger:hall-doors"]["expires"] > game.clock.now_utc().timestamp()
    assert any("Nobody" in line["text"] for f in game.frames_for(b) if f.type == "log" for line in f.data["lines"])


def test_game_6_4_failed_save_does_not_flip_or_charge_trace(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    spec = control_room(game, presence)
    flip(game, a)
    before = presence.trace
    game.commit_commerce(error=True)
    assert not game.core.world.zones[spec.target.zone].objects[spec.target.object].open
    assert presence.trace == before
    flip(game, a)
    game.commit_commerce()
    assert game.core.world.zones[spec.target.zone].objects[spec.target.object].open


def test_game_6_4_flip_interrupts_on_damage_and_cancel(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    control_room(game, presence)
    intent(game, a, "lat.flip", control="hall-doors")
    presence.hit_serial += 1
    game.step(20)
    assert presence.procedure is None and not game.core.commerce.pending
    intent(game, a, "lat.flip", control="hall-doors")
    intent(game, a, "lat.cancel")
    game.step(20)
    assert not game.core.commerce.pending


def test_game_6_4_control_restart_and_elapsed_reset(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    spec = control_room(game, presence)
    flip(game, a)
    effects = game.commit_commerce()
    saved = state(game)
    saved["interlock"] = effects[0]["interlock_state"]
    content = game.core.loop.content
    z = content.zones[spec.target.zone]
    content.zones[z.id] = replace(z, meta=replace(z.meta, objects=tuple(
        replace(o, params={**o.params, "open": False}) if o.id == spec.target.object else o for o in z.meta.objects)))
    restored = HeadlessServer(content, character_state=saved, clock=game.clock)
    obj = restored.core.world.zones[spec.target.zone].objects[spec.target.object]
    assert obj.open
    game.clock.advance(300*TICK_HZ)
    restored.step()
    assert not obj.open


def test_game_6_4_cut_both_unsafe_bodies_offline(runners):
    game, a, b, c = runners
    one = enter(game, b, "lat-civic-ledger")
    two = enter(game, c, "lat-civic-ledger")
    control_room(game, one)
    zid, oid = cut_fixture(game, a)
    # Both physical bodies are in an open fixture, not the original safe plaza.
    place(game, b, zid, (30, 5))
    place(game, c, zid, (31, 6))
    interlock = game.core.lattice.interlock
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid)
    game.step(5*TICK_HZ)
    assert one.player_id in game.core.lattice.presences
    effects = game.commit_commerce()
    assert not game.core.lattice.presences
    assert actor(game, b).shock == actor(game, c).shock == 100
    assert interlock.offline("lat-civic-ledger") == 600
    assert effects[0]["interlock_state"]["cores"]["lat-civic-ledger"]["offline_until"] > game.clock.now_utc().timestamp()
    with pytest.raises(ValueError, match="offline"):
        interlock.authorize_cut(a.session, "lat-civic-ledger", zid, oid)


def test_game_6_4_cut_ejects_a_retained_disconnected_runner(runners):
    game, a, b, c = runners
    presence = enter(game, b, "lat-civic-ledger")
    control_room(game, presence)
    zid, oid = cut_fixture(game, a)
    interlock = game.core.lattice.interlock
    body = actor(game, b)
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid)
    game.step(4*TICK_HZ)
    # Disconnect just before the cut completes, while bounded escape still
    # retains this exact physical body and closed Session object.
    game.core.sessions.disconnect(b.session)
    assert b.session.closed and presence.player_id in game.core.lattice.orphans
    assert game.core.lattice.orphans[presence.player_id][1].actor is body
    game.step(TICK_HZ)
    receipt = game.commit_commerce()[0]
    assert presence.player_id not in game.core.lattice.presences
    assert presence.player_id not in game.core.lattice.orphans
    assert body.shock == 100
    assert receipt["players"][0]["shock"] == 100
    assert interlock.offline("lat-civic-ledger") == 600


def test_game_6_4_mixed_safe_body_refuses_whole_cut(runners):
    game, a, b, c = runners
    one = enter(game, b, "lat-civic-ledger")
    two = enter(game, c, "lat-civic-ledger")
    control_room(game, one)
    zid, oid = cut_fixture(game, a)
    place(game, b, zid, (30, 5))
    # A separate safe body in the Wake defeats the whole action.
    place(game, c, "vatside-wake-hall", (6, 5))
    interlock = game.core.lattice.interlock
    with pytest.raises(ValueError, match="protected"):
        interlock.start_cut(a.session, "lat-civic-ledger", zid, oid)
    assert not interlock.cuts and not game.core.commerce.pending
    assert actor(game, b).shock == actor(game, c).shock == 0


def test_game_6_4_cut_rechecks_new_protected_runner(runners):
    game, a, b, c = runners
    one = enter(game, b, "lat-civic-ledger")
    control_room(game, one)
    zid, oid = cut_fixture(game, a)
    place(game, b, zid, (30, 5))
    interlock = game.core.lattice.interlock
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid)
    # Third caller enters after commitment with a safe body in another zone.
    enter(game, c, "lat-civic-ledger")
    place(game, c, "vatside-wake-hall", (6, 5))
    game.step(5*TICK_HZ)
    assert not game.core.commerce.pending and not interlock.offline("lat-civic-ledger")
    assert len(game.core.lattice.presences) == 2


def test_game_6_4_cut_any_damage_interrupts(runners):
    game, a, b, c = runners
    zid, oid = cut_fixture(game, a)
    interlock = game.core.lattice.interlock
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid)
    actor(game, a).behaviour["hit_serial"] = 1
    game.step(5*TICK_HZ)
    assert not interlock.cuts and not game.core.commerce.pending


def test_game_6_4_hardware_hotkey_confirm_and_cancel(runners):
    from blacksite.server.protocol import Frame
    from tests.character_helpers import act
    game, a, b, c = runners
    zid, oid = cut_fixture(game, a)
    interlock = game.core.lattice.interlock
    act(game, a, Frame("key", {"k": "e", "t": 0}))
    assert interlock.menus[a.session.id] == (zid, oid, False)
    assert game.core.characters.sim.external_views[a.session.id][1]["title"] == "HARDWARE"
    intent(game, a, "menu_select", row="cut", key="c")
    assert interlock.menus[a.session.id][2]
    intent(game, a, "menu_close")
    assert not interlock.cuts and not interlock.offline("lat-civic-ledger")
    act(game, a, Frame("key", {"k": "e", "t": 0}))
    intent(game, a, "menu_select", row="cut", key="c")
    intent(game, a, "menu_select", row="cut", key="y")
    assert a.session.player_id in interlock.cuts
    assert a.session.id not in interlock.menus


def test_game_6_4_safe_hardware_requires_scoped_permit(runners):
    game, a, b, c = runners
    interlock = game.core.lattice.interlock
    (zid, oid), _ = next((key, core) for key, core in interlock.hardware.items() if core == "lat-civic-ledger")
    place(game, a, zid, game.core.world.zones[zid].objects[oid].spec.tile)
    with pytest.raises(ValueError, match="work order"):
        interlock.start_cut(a.session, "lat-civic-ledger", zid, oid)
    interlock.permit = lambda pid, core, action: pid == a.session.player_id and core == "lat-civic-ledger" and action == "cut"
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid)
    game.step(5*TICK_HZ)
    game.commit_commerce()
    assert interlock.offline("lat-civic-ledger") == 600


def test_game_6_4_cut_receipt_saves_both_players_and_deadline_atomically(runners, tmp_path):
    from blacksite.server.storage.db import Storage
    game, a, b, c = runners
    one = enter(game, b, "lat-civic-ledger")
    enter(game, c, "lat-civic-ledger")
    control_room(game, one)
    zid, oid = cut_fixture(game, a)
    interlock = game.core.lattice.interlock
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid)
    game.step(5*TICK_HZ)
    receipt = game.commit_commerce()[0]
    storage = Storage(tmp_path/"world.db", game.clock)
    try:
        storage.commerce_write(receipt)
        saved = storage.character_state()
        assert {p["id"]: p["shock"] for p in saved["players"]} == {
            b.session.player_id: 100, c.session.player_id: 100}
        assert saved["interlock"]["cores"]["lat-civic-ledger"]["offline_until"] == interlock.now()+600
    finally:
        storage.close()


def test_game_6_4_silt_riser_does_not_restore_an_offline_origin(runners):
    game, a, b, c = runners
    presence = enter(game, b, "lat-civic-ledger")
    control_room(game, presence)
    encounters = game.core.lattice.encounters
    graph = encounters.core(presence).graph
    graph.rooms[presence.room] = replace(graph.rooms[presence.room], descent=True)
    encounters.descend(b.session, risk=True)
    assert presence.descent is None
    game.commit_commerce()  # Commit the nonce before descent is published.
    assert presence.descent
    zid, oid = cut_fixture(game, a)
    interlock = game.core.lattice.interlock
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid)
    game.step(5*TICK_HZ)
    game.commit_commerce()
    assert presence.player_id in game.core.lattice.presences and presence.descent
    presence.room = encounters.core(presence).graph.entry
    encounters.leave_core(b.session)
    assert presence.instance is None and presence.core is None and presence.descent is None
    assert game.core.lattice.public(presence)


def test_game_6_4_shaft_two_hardware_locations_cut_one_core(runners):
    from blacksite.content.schema import HardwareLocation, ObjectSpec
    game, a, b, c = runners
    content = game.core.loop.content
    locations = []
    for zid, tile in (("core-plaza", (29, 5)), ("vatside-clinics", (29, 5))):
        zone = content.zones[zid]
        spec = ObjectSpec("fixture-shaft-"+zid, tile, "hardware", {})
        content.zones[zid] = replace(zone, meta=replace(zone.meta, objects=zone.meta.objects+(spec,)))
        locations.append(HardwareLocation(zid, tile, spec.id))
    core = content.cores["lat-shaft"]
    content.cores[core.id] = replace(core, hardware=tuple(locations), rooms=tuple(replace(r, controls=()) for r in core.rooms))
    for bid, bundle in tuple(content.bundles.items()):
        if core.id in bundle.members.get("cores", ()):
            content.bundles[bid] = replace(bundle, members={**bundle.members,
                "cores": tuple(cid for cid in bundle.members["cores"] if cid != core.id)})
    restored = HeadlessServer(content, character_state=state(game), clock=game.clock)
    caller = restored.connect({"user_id": 1, "handle": "Shaft\u754c", "node_name": "test"})
    interlock = restored.core.lattice.interlock
    interlock.permit = lambda pid, cid, action: cid == "lat-shaft" and action == "cut"
    assert {key for key, cid in interlock.hardware.items() if cid == core.id} == {
        (location.zone, location.object_id) for location in locations}
    for location in locations:
        place(restored, caller, location.zone, location.tile)
        interlock.start_cut(caller.session, core.id, location.zone, location.object_id)
        restored.step(5*TICK_HZ)
        restored.commit_commerce()
        assert interlock.offline(core.id) == 600
        restored.clock.advance(600*TICK_HZ)
