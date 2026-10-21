"""S13 real NetBBS native stdio: bodies, sectors, gates and escape.

All travel uses real keys. The unsafe-body scenario grants grade five
and clears earlier heat to isolate damage; no extra money or teleports.
"""

import argparse
import asyncio
from collections import deque
import json
from pathlib import Path

from accept_s10_netbbs import Connection, NativeProbe, wait
from blacksite.admin.client import request


async def lat_walk(probe: NativeProbe, caller: Connection, target: str) -> None:
    lattice = probe.service.core.lattice
    presence = lattice.presences[caller.session.player_id]
    cells = lattice.sectors.cells[presence.sector]
    async with asyncio.timeout(60):
        while presence.cell != target:
            todo, previous = deque([presence.cell]), {presence.cell: None}
            while todo and target not in previous:
                source_id = todo.popleft()
                for cid in cells[source_id].neighbours:
                    if cid not in previous and cells[cid].access_kind == "public":
                        previous[cid] = source_id
                        todo.append(cid)
            if target not in previous:
                raise AssertionError((presence.sector, target, "no public route"))
            step = target
            while previous[step] != presence.cell:
                step = previous[step]
            source = cells[presence.cell]
            other = cells[step]
            dx, dy = other.pos[0]-source.pos[0], other.pos[1]-source.pos[1]
            key = b"\x1b[C" if dx > 0 else b"\x1b[D" if dx < 0 else b"\x1b[B" if dy > 0 else b"\x1b[A"
            await caller.caller.write(key)
            await wait(lambda: presence.cell == step, 3)


async def accept(root: Path, door_python: Path, show: bool,
                 sizes: tuple[tuple[int, int], ...] = ((80, 24), (132, 50))) -> None:
    probe = NativeProbe(root, door_python, show)
    await probe.start()
    results = []
    try:
        lattice = probe.service.core.lattice
        for width, height in sizes:
            a = await probe.open(width, height, "LatticeA", 0, True)
            b = await probe.open(width, height, "LatticeB", 1)
            for caller in (a, b):
                await probe.walk(caller, (21, 14))
                await caller.caller.write(b"b")
                await wait(lambda: probe.game.players[caller.session.player_id].progress.get("wake_combat") == "skipped")
                await probe.travel(caller, "vatside-clinics")
                await probe.travel(caller, "core-plaza")
            await probe.walk(a, (30, 5))
            await probe.walk(b, (31, 6))
            original = a.avatar.actor.position
            await a.caller.write(b"e")
            await wait(lambda: "INTEGRITY 100" in a.caller.screen.screen_text())
            await wait(lambda: "▒" in b.caller.screen.screen_text())
            assert a.avatar.actor.stance == "jacked" and a.avatar.actor.position == original
            assert a.session.subscribed == "lat-core" and a.avatar.actor.zone == "core-plaza"
            assert probe.combat.evasion(a.avatar.actor) == 0
            assert "Pick" in a.caller.screen.screen_text() and "Umbrella" in a.caller.screen.screen_text()
            await probe.target(b, a.avatar.actor.id)
            hp = a.avatar.actor.health
            await b.caller.write(b"f")
            await wait(lambda: "Protected:" in b.caller.screen.screen_text())
            assert a.avatar.actor.health == hp
            await probe.walk(b, (56, 5))
            await b.caller.write(b"e")
            await wait(lambda: "INTEGRITY 100" in b.caller.screen.screen_text())
            await wait(lambda: probe.game.players[b.session.player_id].name in a.caller.screen.screen_text())
            await wait(lambda: probe.game.players[a.session.player_id].name in b.caller.screen.screen_text())
            rows = await request(probe.service.install_dir, "lattice.who")
            assert len(rows) == 2 and len({row["cell"] for row in rows}) == 1
            probe.save(a, f"s13-together-{width}x{height}")
            probe.report(f"PASS two callers {width}x{height}: separate real terminals, same cell, loan/native rig, jacked glyph, safe refusal")

            # Reach a real boundary and demonstrate a named refusal.
            presence = lattice.presences[a.session.player_id]
            core = lattice.sectors.records["lat-core"]
            source = next(c for c in core.cells if c.access_kind == "public" and any(lattice.sectors.cells[core.id][n].access_kind == "gated" for n in c.neighbours))
            gated = next(lattice.sectors.cells[core.id][n] for n in source.neighbours if lattice.sectors.cells[core.id][n].access_kind == "gated")
            await lat_walk(probe, a, source.id)
            before = presence.cell
            dx, dy = gated.pos[0]-source.pos[0], gated.pos[1]-source.pos[1]
            await a.caller.write(b"\x1b[C" if dx > 0 else b"\x1b[D" if dx < 0 else b"\x1b[B" if dy > 0 else b"\x1b[A")
            await wait(lambda: "key program tier 2" in a.caller.screen.screen_text())
            assert presence.cell == before and presence.destination is None
            probe.save(a, f"s13-gate-{width}x{height}")

            # Every authored sector is reached through its public baseline link.
            visited = {"lat-core"}
            for sid in sorted(set(lattice.sectors.records)-visited):
                uplink = next(c for c in core.cells if c.uplink and c.uplink.sector == sid)
                await lat_walk(probe, a, uplink.id)
                await a.caller.write(b"e")
                await wait(lambda: presence.sector == sid)
                await wait(lambda: lattice.sectors.records[sid].district.upper()+" / LATTICE" in a.caller.screen.screen_text())
                assert a.avatar.actor.position == original
                visited.add(sid)
                probe.save(a, f"s13-{sid}-{width}x{height}")
                await a.caller.write(b"e")
                await wait(lambda: presence.sector == "lat-core")
            probe.report(f"PASS all eleven sectors {width}x{height}: real public uplinks, committed layouts, no physical travel")
            for caller in (a, b):
                await caller.caller.write(b"j")
                await wait(lambda: caller.session.player_id not in lattice.presences)
                await wait(lambda: probe.service.world.zones["core-plaza"].template.meta.name in caller.caller.screen.screen_text().splitlines()[0])
                assert caller.session.subscribed == "core-plaza" and caller.avatar.actor.stance == "normal"
            probe.report(f"PASS public jack-out {width}x{height}: both bodies normal, zone subscriptions restored")

            # Canonical quiet Clinic alley: real shot at a native-rig body.
            # Clear prior heat before walking through the contested street.
            for caller in (a, b):
                probe.game.players[caller.session.player_id].warden_heat_until = None
            for caller in (a, b):
                await probe.travel(caller, "vatside-clinics")
                player = probe.game.players[caller.session.player_id]
                player.update_progression(1700)
                # S11 separately verifies the actual ten-minute heat wait.
                # Isolate this body's damage scenario from the prior safe
                # refusal rather than wait those deadlines a second time.
                player.warden_heat_until = None
                probe.game.queue("save", caller.session.user_id, player, immediate=True)
            await probe.walk(a, (25, 25))
            await probe.walk(b, (27, 25))
            await b.caller.write(b"j")
            await wait(lambda: b.session.player_id in lattice.presences)
            assert probe.combat.evasion(b.avatar.actor) == 0
            assert probe.service.world.zones[b.avatar.actor.zone].allows_hostile(b.avatar.actor.position)
            await probe.target(a, b.avatar.actor.id)
            hp = b.avatar.actor.health
            async with asyncio.timeout(12):
                while b.avatar.actor.health == hp:
                    await a.caller.write(b"f")
                    await asyncio.sleep(.3)
            await wait(lambda: "HP "+str(b.avatar.actor.health)+"/" in b.caller.screen.screen_text())
            assert b.avatar.actor.stance == "jacked" and b.avatar.actor.position == (27, 25)
            probe.save(b, f"s13-unsafe-body-{width}x{height}")
            await b.caller.write(b"j")
            await wait(lambda: b.session.player_id not in lattice.presences)
            probe.report(f"PASS unsafe body {width}x{height}: grade-five/cleared-prior-heat fixture, native jack, zero evasion, real weapon hit, HP visible, public escape")
            for caller, label in ((a, "a"), (b, "b")):
                await probe.leave(caller, f"s13-complete-{label}-{width}x{height}")
            results.append({"size": [width, height], "sectors": sorted(visited), "safe_refusal": True,
                            "unsafe_body_hit": True, "extra_money": False, "fixture": "grade five and clear prior refusal heat for isolated unsafe PvP"})
        assert not probe.errors, probe.errors
        (probe.root/"result.json").write_text(json.dumps({"passed": True,
            "transport": "NetBBS Telnet native stdio", "teleports": False,
            "human_playtest": False, "runs": results}, indent=2), encoding="utf-8")
    except BaseException:
        diagnostic = []
        for index, caller in enumerate(probe.connections):
            probe.save(caller, f"s13-failed-{index}")
            av = caller.avatar
            if av:
                overlay = probe.game.sim.external_views.get(caller.session.id)
                diagnostic.append({"player": caller.session.player_id, "zone": av.zone,
                    "stance": av.actor.stance, "position": av.actor.position,
                    "tick": probe.service.clock.now_tick(), "last_tick": probe.service.core.loop.last_tick,
                    "cooldowns": av.actor.cooldowns, "hp": av.actor.health, "shock": av.actor.shock,
                    "last_input_tick": caller.session.last_input_tick,
                    "view_revision": caller.session.view_revision, "ack_revision": caller.session.ack_revision,
                    "input_queue": len(caller.session.input_queue), "send_queue": len(caller.session.send_queue),
                    "service_failure": repr(probe.service.failure) if probe.service.failure else None,
                    "chat": caller.session.pending_prompts.get("chat"),
                    "screen": probe.game.screens.get(caller.session.id),
                    "map": probe.game.sim.maps.get(caller.session.id),
                    "overlay": (overlay[0], overlay[1].get("title")) if overlay else None})
        (probe.root/"failure-state.json").write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
        raise
    finally:
        await probe.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--door-python", type=Path, required=True)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--size", choices=("both", "80", "132"), default="both", help="isolate a failed profile; default runs both")
    args = parser.parse_args()
    sizes = ((80, 24), (132, 50)) if args.size == "both" else ((80, 24),) if args.size == "80" else ((132, 50),)
    asyncio.run(accept(args.root, args.door_python, args.show, sizes))
