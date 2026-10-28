"""S18 actual native NetBBS: sign, store, locked visitor, bed, evict, reclaim.

Three labelled room/letting/bank anchors occupy spare Wake floors. Grade,
300-chit signing funds, a quality rifle and the final reclaim fee are
fixtures. Only housing's injected UTC clock jumps 22 days; movement,
menus, signing, logout, reconnect, eviction and collection use real keys.
S25 owns production Terraces placement; S28 owns operator clock tooling.
"""

import argparse
import asyncio
from datetime import timedelta
import json
from pathlib import Path
import re
import traceback

from accept_s10_netbbs import NativeProbe, CombatCaller, Connection, wait
from accept_s16_netbbs import key, commit_key, select, loan
from housing_fixture import build_fixture
from blacksite.server.clock import ManualClock
from blacksite.server.rules.character import grade_threshold
from netbbs.auth.users import get_user_by_id


async def finish_bed_logout(probe: NativeProbe, connection: Connection, label: str) -> None:
    await wait(lambda: b"Left Blacksite." in connection.caller.output)
    mark = len(connection.caller.output)
    await connection.caller.write(b" ")
    await wait(lambda: b"Available doors" in re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]", b"", bytes(connection.caller.output[mark:])))
    await connection.caller.write(b"b")
    await wait(lambda: b"You return to the node." in connection.caller.output[mark:])
    probe.save(connection, label)
    connection.writer.close()
    await connection.writer.wait_closed()
    await connection.pump
    probe.connections.remove(connection)


async def reconnect(probe: NativeProbe, previous: Connection, width: int, height: int,
                    expected_zone: str = 'Wake Hall') -> Connection:
    user = get_user_by_id(probe.db, int(previous.session.door_info["user_id"]))
    probe.accounts.append((user, True))
    reader, writer = await asyncio.open_connection("127.0.0.1", probe.node.port)
    async def send(data: bytes) -> None:
        writer.write(data)
        await writer.drain()
    writer.write(b"\xff\xfb\x1f\xff\xfa\x1f"+width.to_bytes(2, "big")+height.to_bytes(2, "big")+b"\xff\xf0")
    writer.write(b"\xff\xfb\x18\xff\xfa\x18\x00xterm-256color\xff\xf0")
    await writer.drain()
    caller = CombatCaller(lambda: reader.read(65536), send, width, height, probe.show)
    await caller.expect("Available doors")
    await caller.write(b"\x1b[B\r")
    await caller.until(lambda: expected_zone in caller.screen.screen_text().splitlines()[0], timeout=15)
    async def pump() -> None:
        while chunk := await reader.read(65536):
            caller.output.extend(chunk)
            caller.replay()
    task = asyncio.create_task(pump())
    # A server restart can reuse a process-local session id. Match the
    # newly attached live body; the previous transport has already left.
    session = next(s for s in probe.game.sessions.active.values()
                   if s.player_id == previous.session.player_id and not s.closed)
    result = Connection(caller, writer, task, session, probe.game.sim.avatars[session.user_id])
    probe.connections.append(result)
    return result


async def choose(probe: NativeProbe, connection: Connection, row: str) -> None:
    housing = probe.service.core.apartments
    screen = housing.menus[connection.session.id]
    await select(connection, lambda: housing.body(connection.session, screen)["rows"], screen, row)


async def bed(probe: NativeProbe, connection: Connection, unit, label: str) -> None:
    housing = probe.service.core.apartments
    await probe.walk(connection, unit.tile((3, 2)))
    await key(connection, b"e")
    await wait(lambda: connection.session.id in housing.menus)
    await choose(probe, connection, "logout")
    probe.save(connection, label+"-menu")
    await commit_key(probe, connection, b"\r", lambda: connection.session.closed)
    await finish_bed_logout(probe, connection, label)


async def run_size(probe: NativeProbe, width: int, height: int) -> dict:
    connection = await probe.open(width, height, "S18A", 1, sixteen=True)
    housing = probe.service.core.apartments
    # Disclosed UTC injection affects lazy housing deadlines only. Live I/O,
    # sessions, tick channels and NetBBS keep their ordinary clocks.
    clock = ManualClock(epoch=probe.service.clock.now_utc())
    housing.clock = housing.geometry.clock = clock
    p = probe.game.players[connection.session.player_id]
    p.update_progression(grade_threshold(5))
    p.update_personhood(probe.game.identity(p.bbs_user_id), probe.service.clock.now_utc())
    p.chits_bank, p.chits_hand = 300, 0
    rifle = loan(probe, connection, "wpn_halvard_hv7")
    probe.commerce.items[rifle].quality = 1.09
    probe.game.queue("save", p.bbs_user_id, p, immediate=True)
    probe.service._character_writes()
    unit = housing.geometry.units["vatside-wake-hall:fixture-home-1"]
    await probe.walk(connection, (6, 8))
    await key(connection, b"e")
    await wait(lambda: connection.session.id in housing.menus)
    await choose(probe, connection, unit.id)
    probe.save(connection, f"s18-letting-{width}")
    await commit_key(probe, connection, b"\r", lambda: p.apartment_id is not None)
    assert p.chits_bank == 0 and housing.lease(p)["tier"] == 1
    aid = p.apartment_id
    await key(connection, b"\x1b")
    await wait(lambda: connection.session.id not in housing.menus)
    await probe.walk(connection, unit.anchor.doorstep)
    await commit_key(probe, connection, b"e", lambda: unit.region.contains(connection.avatar.actor.position))
    await probe.walk(connection, unit.tile((0, 2)))
    await key(connection, b"e")
    await wait(lambda: connection.session.id in housing.menus)
    await choose(probe, connection, rifle)
    await commit_key(probe, connection, b"\r", lambda: rifle in housing.lease(p)["storage"])
    await key(connection, b"t")
    await wait(lambda: not housing.menus[connection.session.id].deposit)
    await wait(lambda: "Quality 109%" in connection.caller.screen.screen_text())
    probe.save(connection, f"s18-storage-{width}")
    await key(connection, b"\x1b")
    await wait(lambda: connection.session.id not in housing.menus)

    second = await probe.open(width, height, "S18B", 1, sixteen=True)
    await probe.walk(second, unit.anchor.doorstep)
    await key(second, b"e")
    await wait(lambda: "Locked. Tier 1." in second.caller.screen.screen_text())
    assert not unit.region.contains(second.avatar.actor.position)
    probe.save(second, f"s18-locked-{width}")
    await probe.leave(second, f"s18-visitor-return-{width}")

    await bed(probe, connection, unit, f"s18-bed-{width}")
    connection = await reconnect(probe, connection, width, height)
    assert unit.region.contains(connection.avatar.actor.position) and p.apartment_id == aid
    probe.save(connection, f"s18-reconnect-home-{width}")
    await bed(probe, connection, unit, f"s18-bed-before-eviction-{width}")
    clock.epoch += timedelta(days=22)
    connection = await reconnect(probe, connection, width, height)
    await wait(lambda: p.apartment_id is None)
    await wait(lambda: "impound" in connection.caller.screen.screen_text())
    assert not unit.region.contains(connection.avatar.actor.position)
    probe.save(connection, f"s18-eviction-{width}")
    assert housing.private.core_id({"id": aid}) not in housing.content.cores
    await probe.walk(connection, (9, 8))
    await key(connection, b"e")
    await wait(lambda: connection.session.id in probe.commerce.menus)
    screen = probe.commerce.menus[connection.session.id]
    await select(connection, lambda: probe.commerce.body(connection.session, screen)["rows"], screen, "impound")
    await key(connection, b"\r")
    await wait(lambda: connection.session.id in housing.menus)
    await choose(probe, connection, rifle)
    await wait(lambda: "Fee 34" in connection.caller.screen.screen_text())
    probe.save(connection, f"s18-impound-{width}")
    p.chits_bank = 34  # Disclosed funding fixture; the actual fee is charged.
    await commit_key(probe, connection, b"\r", lambda: rifle in p.inventory)
    assert p.chits_bank == 0 and probe.commerce.items[rifle].quality == 1.09
    assert probe.commerce.items[rifle].owner == p.id
    assert connection.caller.screen.cell(width-1, height-1) == " "
    probe.save(connection, f"s18-reclaimed-{width}")
    await key(connection, b"\x1b")
    await wait(lambda: connection.session.id not in housing.menus)
    await probe.leave(connection, f"s18-return-{width}")
    probe.report(f"PASS S18 {width}x{height}: sign 300, store 109% rifle, locked visitor, bed reconnect, 22-day eviction, 34-chit reclaim; native16/wide names")
    return {"size": [width, height], "signing": 300, "quality": 1.09, "reclaim": 34,
            "bed_reconnect": True, "evicted": True, "native_tier": "16"}


async def accept(root: Path, python: Path, show: bool) -> None:
    shipped = Path(__file__).resolve().parents[1]/"src/blacksite/content"
    build_fixture(shipped, root/"world/content.local")
    probe = NativeProbe(root, python, show)
    await probe.start()
    try:
        probe.report("FIXTURE: three housing anchors/letting/impound on Wake floors; grade/funds/rifle; housing-only 22-day UTC injection")
        results = [await run_size(probe, *size) for size in ((80, 24), (132, 50))]
        assert not probe.errors and probe.service.failure is None
        (root/"s18-results.json").write_text(json.dumps({"passed": True, "runs": results,
            "transport": "NetBBS Telnet -> native stdio", "placement_fixture": True,
            "clock_fixture_days": 22, "production_placement_slice": "S25",
            "fixtures": ["three rooms and letting/bank on Wake", "grade 5", "300 signing chits",
                         "quality 1.09 HV-7", "34 reclaim chits", "housing-only UTC clock"]}, indent=2)+"\n", encoding="utf-8")
    except BaseException:
        (root/"failure-trace.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        await probe.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--door-python", type=Path, required=True)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, args.show))
