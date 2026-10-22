"""S20 native NetBBS: real admission, faction chat, Marked combat and leave.

Fixtures: grade five, +30 admission standing and attack-delayed Wardens.
Clinic Row supplies the shipped contested lane; Sink placement is S25.
The aggressor is Sablier so the Warden starts neutral: Sable is already
hostile to Wardens under the canonical matrix. One HP after marking
isolates the kill receipt; targeting and every shot use caller keys.
"""
import argparse
import asyncio
import json
from pathlib import Path
import traceback

from accept_s10_netbbs import NativeProbe, Connection, wait
from accept_s16_netbbs import key, commit_key, select
from blacksite.server.npcs.templates import make_actor
from blacksite.server.rules.character import grade_threshold


async def admission(probe: NativeProbe, connection: Connection, faction: str, cancel: bool = False) -> None:
    f = probe.service.core.factions
    await probe.walk(connection, (8, 10))
    await key(connection, b'e')
    await wait(lambda: connection.session.id in f.menus)
    screen = f.menus[connection.session.id]
    await select(connection, lambda: f.body(connection.session, screen)[1]['rows'], screen, faction)
    await commit_key(probe, connection, b'j', lambda: bool(screen.confirm))
    p = probe.game.players[connection.session.player_id]
    assert p.faction is None
    if cancel:
        await key(connection, b'\x1b')
        await wait(lambda: connection.session.id not in f.menus)
        assert p.faction is None
        return
    await commit_key(probe, connection, b'y', lambda: p.faction == faction)
    probe.save(connection, f's20-joined-{faction}-{connection.session.caps["width"]}')
    await key(connection, b'\x1b')
    await wait(lambda: connection.session.id not in f.menus)


async def faction_line(connection: Connection, text: str) -> None:
    session = connection.session
    await key(connection, b'\x06')
    await wait(lambda: 'chat' in session.pending_prompts)
    prompt = session.pending_prompts['chat']['id']
    await wait(lambda: 'Faction:' in connection.caller.screen.screen_text())
    await connection.caller.write(text.encode()+b'\r')
    await wait(lambda: session.pending_prompts.get('chat', {}).get('id') != prompt)


def grade(probe: NativeProbe, connection: Connection) -> None:
    p = probe.game.players[connection.session.player_id]
    p.update_progression(grade_threshold(5))
    p.update_personhood(probe.game.identity(p.bbs_user_id), probe.service.clock.now_utc())
    probe.game.queue('save', p.bbs_user_id, p, immediate=True)
    probe.service._character_writes()


async def run_size(probe: NativeProbe, width: int, height: int) -> dict:
    a = await probe.open(width, height, 'S20A', 0, True)
    grade(probe, a)
    pa = probe.game.players[a.session.player_id]
    pa.standing['sablier'] = 30
    await admission(probe, a, 'sablier')
    await probe.walk(a, (12, 10))
    c = await probe.open(width, height, 'S20C', 0, True)
    grade(probe, c)
    pc = probe.game.players[c.session.player_id]
    pc.standing['halvard'] = 30
    await admission(probe, c, 'halvard', cancel=True)
    await admission(probe, c, 'halvard')
    await probe.walk(c, (13, 10))
    d = await probe.open(width, height, 'S20D', 0, True)
    grade(probe, d)
    pd = probe.game.players[d.session.player_id]
    pd.standing['halvard'] = 30
    await admission(probe, d, 'halvard')
    await probe.walk(d, (14, 10))
    b = await probe.open(width, height, 'S20B', 0, True)
    grade(probe, b)
    await probe.walk(b, (15, 10))
    token = f'CONTAINMENT HOLDS {width}'
    outsider_mark = len(b.caller.output)
    await faction_line(c, token)
    await wait(lambda: token in d.caller.screen.screen_text())
    assert token.encode() not in b.caller.output[outsider_mark:]
    probe.save(d, f's20-faction-chat-{width}')
    f = probe.service.core.factions
    await probe.walk(d, (8, 10))
    await key(d, b'e'); await wait(lambda: d.session.id in f.menus)
    screen = f.menus[d.session.id]
    await select(d, lambda: f.body(d.session, screen)[1]['rows'], screen, 'halvard')
    await commit_key(probe, d, b'l', lambda: bool(screen.confirm))
    await commit_key(probe, d, b'y', lambda: pd.faction is None)
    await wait(lambda: 'Join after' in d.caller.screen.screen_text())
    assert pd.standing['halvard'] == -20
    assert pd.progress['faction_cooldown_until'] > probe.service.clock.now_utc().timestamp()+6*86400
    probe.save(d, f's20-leave-cooldown-{width}')
    await key(d, b'\x1b'); await wait(lambda: d.session.id not in f.menus)
    mark = len(d.caller.output)
    await faction_line(c, f'CHANNEL CLOSED {width}')
    await asyncio.sleep(.5)
    assert f'CHANNEL CLOSED {width}'.encode() not in d.caller.output[mark:]
    await probe.leave(d, f's20-left-faction-{width}')

    for connection, tile in ((a, (25, 3)), (b, (27, 3)), (c, (25, 5))):
        await probe.travel(connection, 'vatside-clinics')
        await probe.walk(connection, tile)
    zone = probe.service.world.zones['vatside-clinics']
    ward = make_actor(probe.game.content.npcs['npc-warden-response'], f's20-fixture-warden:{width}',
                      {'home': (29, 3), 'phase': 0})
    # Observe actual AI targeting without the fixture killing the aggressor
    # before the third caller can exercise the durable Marked-kill receipt.
    ward.cooldowns['weapon'] = probe.service.clock.now_tick()+6000
    probe.service.world.enter(ward, zone.id, probe.service.world.free_tile(zone.id, (29, 3)))
    assert not probe.service.core.npcs.hostile(ward, a.avatar.actor)
    probe.report(f'S20 {width}x{height}: membership/chat/leave passed; starting live contested combat')
    await probe.target(a, b.session.player_id)
    async with asyncio.timeout(15):
        while not a.avatar.actor.marked:
            await key(a, b'f')
            await asyncio.sleep(.4)
    await wait(lambda: ward.target == pa.id)
    await probe.target(b, pa.id)
    probe.save(b, f's20-marked-red-target-{width}')
    await key(b, b'W')
    await wait(lambda: b.session.id in probe.service.core.chat.sitreps)
    await wait(lambda: 'Marked ' in b.caller.screen.screen_text())
    probe.save(b, f's20-marked-sitrep-{width}')
    await key(b, b'\x1b')
    await wait(lambda: b.session.id not in probe.service.core.chat.sitreps)
    await probe.target(c, pa.id)
    for npc in zone.actors.values():
        if npc.kind != 'player' and npc.faction == 'wardens':
            npc.cooldowns['weapon'] = probe.service.clock.now_tick()+6000
    pa.health = a.avatar.actor.health = 1
    async with asyncio.timeout(20):
        while a.avatar.actor.stance not in ('down', 'dead'):
            await key(c, b'f')
            await asyncio.sleep(.5)
    await wait(lambda: pc.standing.get('wardens', 0) == 5, 10)
    assert not pc.marked_until and pa.progress['combat']['stage'] == 'dead'
    probe.save(c, f's20-marked-kill-receipt-{width}')
    result = {'size': [width, height], 'wide_names': True, 'cancelled_join_unchanged': True,
              'member_chat_only': True, 'leave_standing': -20, 'cooldown_days': 7,
              'marked_red_target': True, 'warden_targeted_marked_neutral': True,
              'marked_kill_wardens': pc.standing['wardens'], 'killer_unmarked': True}
    probe.service.world.leave(ward)
    for connection in (b, c, a):
        await probe.leave(connection, f's20-return-{connection.session.player_id.rsplit(":", 1)[-1]}-{width}')
    probe.report(f'S20 PASS {width}x{height}: membership/chat/leave, Marked/Warden/+5 receipt')
    return result


async def hardware_size(probe: NativeProbe, width: int, height: int) -> dict:
    from accept_s16_netbbs import loan
    connection = await probe.open(width, height, "S20HW", 0, True)
    grade(probe, connection)
    p = probe.game.players[connection.session.player_id]
    p.chits_hand = 0
    iid = loan(probe, connection, "key_containment_charge")
    interlock = probe.service.core.lattice.interlock
    core = "lat-civic-ledger"
    (zid, oid), _ = next((key, value) for key, value in interlock.hardware.items() if value == core)
    await probe.travel(connection, "vatside-clinics")
    await probe.travel(connection, zid)
    zone = probe.service.world.zones[zid]
    ox, oy = zone.objects[oid].spec.tile
    occupied = {obj.spec.tile for obj in zone.objects.values()}
    tile = next((ox+dx, oy+dy) for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2))
                if zone.passable((ox+dx, oy+dy)) and (ox+dx, oy+dy) not in occupied)
    await probe.walk(connection, tile)
    await key(connection, b"e")
    await wait(lambda: connection.session.id in interlock.menus)
    await wait(lambda: probe.game.sim.external_views.get(connection.session.id, (None,))[0] == "menu")
    body = probe.game.sim.external_views[connection.session.id][1]
    assert {action["key"] for action in body["actions"]} == {"x"}
    assert "C manual" not in body["hint"]
    probe.save(connection, f"s20-range-two-hardware-{width}")
    await commit_key(probe, connection, b"x", lambda: interlock.menus[connection.session.id][2] == "charge")
    await wait(lambda: "service fee 150 chits" in connection.caller.screen.screen_text())
    probe.save(connection, f"s20-paid-quote-{width}")
    await key(connection, b"y")
    await wait(lambda: connection.session.id not in interlock.menus)
    await wait(lambda: "service fee is 150 chits" in connection.caller.screen.screen_text())
    assert p.id not in interlock.cuts and iid in p.inventory
    probe.save(connection, f"s20-unaffordable-no-channel-{width}")
    # Disclosed +90 membership fixture isolates the read-only waiver quote.
    # Admission itself is exercised with actual keys in the ordinary stage.
    p.faction, p.standing["halvard"] = "halvard", 90
    probe.service.core.factions.refresh(p)
    await key(connection, b"e")
    await wait(lambda: connection.session.id in interlock.menus)
    await commit_key(probe, connection, b"x", lambda: interlock.menus[connection.session.id][2] == "charge")
    await wait(lambda: "service fee 0 chits" in connection.caller.screen.screen_text())
    identity = probe.game.identities[p.bbs_user_id]
    assert "halvard-service" not in identity.get("receipts", {}).get("faction_perks", {})
    probe.save(connection, f"s20-free-quote-unspent-{width}")
    await commit_key(probe, connection, b"y", lambda: p.id in interlock.cuts)
    assert iid in p.inventory and not interlock.offline(core)
    await wait(lambda: iid not in p.inventory, 10)
    assert p.chits_hand == 0 and interlock.offline(core) > 590
    assert probe.game.identities[p.bbs_user_id]["receipts"]["faction_perks"]["halvard-service"] == probe.service.clock.now_utc().date().isoformat()
    probe.save(connection, f"s20-free-cut-committed-{width}")
    await probe.leave(connection, f"s20-hardware-return-{width}")
    # The next size reuses the fixture core without waiting ten real minutes.
    # This removes only the prior fixture's cooldown, never rewinds a clock.
    interlock.state["cores"].pop(core, None)
    probe.report(f"S20 HARDWARE PASS {width}x{height}: range actions, upfront fee, read-only quote and atomic free cut")
    return {"size": [width, height], "range_two_charge_only": True,
            "unaffordable_no_channel": True, "quote_does_not_spend_daily_use": True,
            "charge_and_waiver_committed": True}


async def accept(root: Path, python: Path, show: bool, stage: str = "factions") -> None:
    probe = NativeProbe(root, python, show)
    if stage == "hardware":
        from accept_s15_netbbs import fixture
        fixture(probe, "controls")
    await probe.start()
    try:
        probe.report('S20 fixtures: grade5/+30, delayed Warden, 1HP after Mark. Shipped Clinic Row; Sink geography remains S25.')
        if stage == "hardware":
            probe.report("HARDWARE FIXTURE: S15 labelled open Civic control zone; charge/zero chits; +90 Halvard membership after refusal; between-size core cooldown reset")
        run = hardware_size if stage == "hardware" else run_size
        results = [await run(probe, *size) for size in ((80, 24), (132, 50))]
        assert not probe.errors and probe.service.failure is None
        (root/('s20-hardware-results.json' if stage == 'hardware' else 's20-results.json')).write_text(json.dumps({'passed': True, 'stage': stage, 'runs': results,
            'transport': 'NetBBS Telnet -> registered native stdio',
            'fixtures': (['S15 labelled open Civic control zone', 'grade5', 'one charge and zero chits',
                          '+90 Halvard membership after refusal', 'between-size core cooldown reset']
                         if stage == 'hardware' else ['grade5', '+30 admission standing',
                         'attack-delayed Wardens for kill attribution', '1HP after Mark']),
            'contested_zone': 'S15 labelled open core-plaza' if stage == 'hardware' else 'vatside-clinics',
            'production_sink_slice': 'S25'}, indent=2)+'\n', encoding='utf-8')
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--stage', choices=('factions', 'hardware'), default='factions')
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, args.show, args.stage))
