"""S38: real NetBBS stdio truce headers, marking and keeper response.

Private accounts/world only. A documented grade-five player fixture is
queued through the owning server; this is not progression/acquisition
acceptance. Creation, travel, targeting, firing and logout use real keys.
"""

import argparse
import asyncio
import json
from pathlib import Path
import subprocess
from collections.abc import Callable


from accept_s10_netbbs import Connection, NativeProbe, wait
from accept_p4_netbbs import navigate
from blacksite.server.world.actors import Actor


async def enter_row(probe: NativeProbe, caller: Connection) -> None:
    await probe.walk(caller, (21, 14))
    await caller.caller.write(b"b")
    await wait(lambda: probe.game.players[caller.session.player_id].progress.get("wake_combat") == "skipped")
    for destination in ("vatside-clinics", "core-plaza", "sodium-row"):
        await probe.travel(caller, destination)
    await wait(lambda: "TRUCE" in caller.caller.screen.screen_text().splitlines()[0])


async def shoot_until(probe: NativeProbe, caller: Connection, target: Actor, condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(40):
        while not condition():
            await navigate(probe, caller, target)
            await probe.target(caller, target.id)
            await caller.caller.write(b"f")
            await asyncio.sleep(.25)


async def accept(root: Path, door_python: Path, width: int, height: int,
                 modern: bool, show: bool) -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert not subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    root.mkdir(parents=True, exist_ok=False)
    probe = NativeProbe(root, door_python, show, door_environment={
        "DOOR_BLACKSITE_PRESENTATION": "1" if modern else "0"}, show_all_tiers=True)
    await probe.start()
    cases = []
    try:
        for tier in ("16", "256", "truecolor"):
            kwargs = {"archetype": 3, "sixteen": tier == "16", "truecolor": tier == "truecolor"}
            first = await probe.open(width, height, "TruceA"+tier, **kwargs)
            second = await probe.open(width, height, "TruceB"+tier, **kwargs)
            for caller in (first, second):
                assert caller.session.caps["tier"] == tier, caller.session.caps
                player = probe.game.players[caller.session.player_id]
                player.grade = 5  # Explicit PvP fixture, not an earned-grade claim.
                probe.game.queue("save", player.bbs_user_id, player, immediate=True)
                await enter_row(probe, caller)
            await probe.walk(first, (12, 5))
            await probe.walk(second, (14, 5))
            source, victim = first.avatar.actor, second.avatar.actor
            await probe.target(first, victim.id)
            await wait(lambda: "Firing marks you" in first.caller.screen.screen_text())
            probe.save(first, f"truce-player-warning-{width}x{height}-{tier}")
            await shoot_until(probe, first, victim, lambda: source.marked)
            await wait(lambda: any(line["text"] == "Sable is coming for you." for line in first.session.log_ring))
            lines = [line["text"] for line in first.session.log_ring]
            mark = "You break Sodium Row's truce. You are Marked for 15 min."
            assert lines.index(mark) < lines.index("Sable is coming for you.")
            await wait(lambda: first.session.ack_revision == first.session.view_revision)
            probe.save(first, f"truce-marked-{width}x{height}-{tier}")
            await probe.leave(first, f"finished-player-a-{width}x{height}-{tier}")
            await probe.leave(second, f"finished-player-b-{width}x{height}-{tier}")

            caller = await probe.open(width, height, "TruceN"+tier, **kwargs)
            assert caller.session.caps["tier"] == tier, caller.session.caps
            await enter_row(probe, caller)
            zone = probe.service.world.zones["sodium-row"]
            regular = next(a for a in zone.actors.values() if a.behaviour.get("template") == "npc-sodium-regular")
            guards = [a for a in zone.actors.values() if a.behaviour.get("template") == "npc-sable-enforcer"]
            await navigate(probe, caller, regular)
            await probe.target(caller, regular.id)
            await wait(lambda: "Truce: Sable answers" in caller.caller.screen.screen_text())
            probe.save(caller, f"truce-regular-warning-{width}x{height}-{tier}")
            await shoot_until(probe, caller, regular, lambda: any(g.target == caller.avatar.actor.id for g in guards))
            await wait(lambda: any(line["text"] == "Sable is coming for you." for line in caller.session.log_ring))
            probe.save(caller, f"truce-keeper-response-{width}x{height}-{tier}")
            assert not caller.avatar.actor.marked
            cases.append({"size": [width, height], "tier": tier, "presentation": modern,
                          "player_marked": True, "regular_attack_provokes_keeper": True,
                          "mark_before_chase": True, "grade_fixture": 5})
            await probe.leave(caller, f"finished-regular-{width}x{height}-{tier}")
        assert not probe.errors
        (root/"result.json").write_text(json.dumps({"head": head, "cases": cases,
            "transport": "NetBBS Telnet -> registered native stdio", "human_acceptance": False}, indent=2)+"\n",
            encoding="utf-8", newline="\n")
    finally:
        await probe.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--door-python", type=Path, required=True)
    parser.add_argument("--size", choices=("80x24", "132x50"), required=True)
    parser.add_argument("--presentation", choices=("legacy", "modern"), required=True)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    width, height = map(int, args.size.split("x"))
    asyncio.run(accept(args.root.resolve(), args.door_python, width, height,
                       args.presentation == "modern", args.show))
