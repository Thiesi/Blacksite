"""S11 real native door: populated streets, refusal, heat and local guards.

The heat interval is actually waited at both sizes. No player teleports,
extra money, faction membership or progression fixtures are needed.
"""

import argparse
import asyncio
from collections import deque
import json
from pathlib import Path
import time

from accept_s10_netbbs import Connection, NativeProbe, wait
from blacksite.admin.client import request
from blacksite.server.world.actors import Actor
from blacksite.server.world.sight import line_of_sight


async def approach(probe: NativeProbe, caller: Connection, target: Actor,
                   *, hostile_tile: bool = True) -> None:
    actor=caller.avatar.actor
    zone=probe.service.world.zones[actor.zone]
    async with asyncio.timeout(20):
        while not probe.combat.visible(target,actor) or (actor.x-target.x)**2+(actor.y-target.y)**2>16:
            # A moving patrol may leave a geometrically close tile behind
            # a wall or another body. Choose a reachable visible approach,
            # then take only one real-key step before planning again.
            occupied={a.position for a in zone.actors.values() if a is not actor}
            exits={e.tile for e in zone.template.meta.exits if e.kind=='street'}
            pending,previous=deque([actor.position]),{actor.position:None}
            while pending:
                x,y=pending.popleft()
                for tile in ((x+1,y),(x,y+1),(x-1,y),(x,y-1)):
                    if tile not in previous and tile not in occupied and tile not in exits and zone.passable(tile):
                        previous[tile]=(x,y);pending.append(tile)
            candidates=[tile for tile in previous if (not hostile_tile or zone.allows_hostile(tile))
                and (tile[0]-target.x)**2+(tile[1]-target.y)**2<=16
                and line_of_sight(zone,tile,target.position)]
            if not candidates:
                await asyncio.sleep(.1)
                continue
            tile=min(candidates,key=lambda p:(p[0]-actor.x)**2+(p[1]-actor.y)**2)
            if tile == actor.position:
                await asyncio.sleep(.1)
                continue
            step=tile
            while previous[step]!=actor.position:
                step=previous[step]
            # A new actor can occupy even that first step after the search.
            try:
                async with asyncio.timeout(1):
                    await probe.walk(caller,step)
            except TimeoutError:
                pass



async def profile(probe: NativeProbe, width: int, height: int) -> float:
    for zone in probe.service.world.zones.values():
        zone.activate("s11-profiling",probe.service.clock.now_tick())
    try:
        await asyncio.sleep(2)
        probe.service.core.loop.timings.clear()
        await asyncio.sleep(10)
        status=await request(probe.service.install_dir,"status")
        count = len(probe.service.world.zones)
        assert status["active_zones"]==count and status["tick_p99_ms"]<10,status
        probe.report(f"PASS admin status {width}x{height}: all {count} zones active, p99 {status['tick_p99_ms']:.3f} ms")
        return status["tick_p99_ms"]
    finally:
        for zone in probe.service.world.zones.values():
            zone.deactivate("s11-profiling",probe.service.clock.now_tick())


async def sodium_response(probe: NativeProbe, caller: Connection, width: int, height: int) -> None:
    actor=caller.avatar.actor
    await probe.walk(caller,(16,5))
    sodium=probe.service.world.zones[actor.zone]
    guards=[a for a in sodium.actors.values() if a.behaviour.get("template")=="npc-sable-enforcer"]
    regular=min((a for a in sodium.actors.values() if a.behaviour.get("template")=="npc-sodium-regular"),
                key=lambda a:(a.x-actor.x)**2+(a.y-actor.y)**2)
    # A moving civilian can leave weapon range between warning and firing.
    # Approach and keep pressing real F until an actual shot provokes guards.
    async with asyncio.timeout(30):
        while not any(a.target==actor.id for a in guards):
            if (regular.x-actor.x)**2+(regular.y-actor.y)**2>16:
                occupied={a.position for a in sodium.actors.values()}
                candidates=[(x,y) for x in range(regular.x-1,regular.x+2) for y in range(regular.y-1,regular.y+2)
                    if sodium.passable((x,y)) and (x,y) not in occupied]
                tile=min(candidates,key=lambda p:(p[0]-actor.x)**2+(p[1]-actor.y)**2)
                await probe.walk(caller,tile)
            await probe.target(caller,regular.id)
            await caller.caller.write(b"f")
            await asyncio.sleep(.25)
    assert not any(a.faction=="wardens" and a.target==actor.id for a in sodium.actors.values())
    probe.save(caller,f"s11-sodium-{width}x{height}")
    probe.report(f"PASS local response {width}x{height}: Sable enforcers answer provocation, no Wardens")


async def accept(root: Path, door_python: Path, show: bool,
                 sizes: tuple[tuple[int, int], ...] = ((80,24),(132,50))) -> None:
    probe=NativeProbe(root,door_python,show)
    await probe.start()
    results=[]
    try:
        for width,height in sizes:
            caller=await probe.open(width,height,"NpcRunner",0,True)
            actor=caller.avatar.actor
            await probe.walk(caller,(21,14))
            await caller.caller.write(b"b")
            await wait(lambda:probe.game.players[actor.id].progress.get("wake_combat")=="skipped")
            await probe.travel(caller,"vatside-clinics")
            await probe.travel(caller,"core-plaza")
            await probe.walk(caller,(20,6))
            plaza=probe.service.world.zones["core-plaza"]
            before={a.id:a.position for a in plaza.actors.values() if a.kind!="player"}
            moved=set()
            for _ in range(30):
                await asyncio.sleep(.1)
                moved.update(a.behaviour.get("template") for a in plaza.actors.values()
                             if a.id in before and a.position!=before[a.id])
            assert {"npc-civilian","npc-warden-patrol","npc-courier"} <= moved,moved
            await wait(lambda:"~" in caller.caller.screen.screen_text())
            await profile(probe,width,height)
            # Profiling leaves the simulation running: civilians can walk
            # out of sight. Approach a real civilian instead of assuming
            # one is still visible from the earlier observation point.
            target=min((a for a in plaza.actors.values() if a.behaviour.get("template")=="npc-civilian"),
                       key=lambda a:(a.x-actor.x)**2+(a.y-actor.y)**2)
            await approach(probe,caller,target,hostile_tile=False)
            await probe.target(caller,target.id)
            hp=actor.health;target_hp=target.health
            started=time.monotonic()
            await caller.caller.write(b"f")
            await wait(lambda:probe.game.players[actor.id].warden_heat_until is not None,2)
            response=time.monotonic()-started
            assert len([a for a in plaza.actors.values() if a.behaviour.get("response")==actor.id])==2
            for _ in range(3):
                await caller.caller.write(b"f");await asyncio.sleep(.2)
            assert (actor.health,target.health)==(hp,target_hp)
            await wait(lambda:"HEAT" in caller.caller.screen.screen_text().splitlines()[0])
            probe.save(caller,f"s11-plaza-{width}x{height}")
            probe.report(f"PASS NPC plaza {width}x{height}: patrol, wander, courier, relation glyph, warning {response:.2f}s, two responders, safe HP")
            await probe.travel(caller,"vatside-clinics")
            await probe.walk(caller,(44,3))
            patrol=next(a for a in probe.service.world.zones[actor.zone].actors.values() if a.behaviour.get("template")=="npc-warden-patrol")
            await approach(probe,caller,patrol)
            await wait(lambda:patrol.target==actor.id,3)
            probe.report(f"PASS heat pursuit {width}x{height}: Clinic Row patrol targets caller after visible warning")
            # Retreat to the real public-clinic pocket before waiting out heat.
            clinic=next(o for o in probe.service.world.zones[actor.zone].objects.values() if o.spec.essential and o.spec.params.get("vendor"))
            await probe.walk(caller,clinic.spec.tile)
            assert not probe.service.world.zones[actor.zone].allows_hostile(actor.position)
            await wait(lambda:patrol.target is None,3)
            safe_hp=actor.health
            until=probe.game.players[actor.id].warden_heat_until
            from datetime import datetime
            while probe.combat.now()<datetime.fromisoformat(until).timestamp():
                await asyncio.sleep(min(30,datetime.fromisoformat(until).timestamp()-probe.combat.now()))
                probe.report(f"WAIT heat {width}x{height}: {max(0,datetime.fromisoformat(until).timestamp()-probe.combat.now()):.0f}s remain in protected clinic")
                assert actor.health==safe_hp
            await probe.walk(caller,(44,3))
            await approach(probe,caller,patrol)
            await asyncio.sleep(3)
            assert patrol.target is None
            assert not probe.game.me(caller.session)["heat_until"]
            probe.report(f"PASS actual ten-minute heat expiry {width}x{height}: patrol ignores Freelance again")
            await probe.travel(caller,"core-plaza")
            await probe.travel(caller,"sodium-row")
            await sodium_response(probe,caller,width,height)
            p99=await profile(probe,width,height)
            await probe.leave(caller,f"s11-complete-{width}x{height}")
            results.append({"size":[width,height],"warning_seconds":response,"heat_wait":"actual 600-second deadline",
                "safe_damage":False,"local_guards":True,"all_hub_p99_ms":p99})
        assert not probe.errors,probe.errors
        (probe.root/"result.json").write_text(json.dumps({"passed":True,"transport":"NetBBS Telnet native stdio",
            "teleports":False,"human_playtest":False,"runs":results},indent=2),encoding="utf-8")
    finally:
        await probe.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--door-python",type=Path,required=True)
    parser.add_argument("--show",action="store_true")
    parser.add_argument("--size", choices=("80x24", "132x50"),
                        help="Run one profile; the default runs both sizes.")
    args=parser.parse_args()
    sizes = (tuple(map(int,args.size.split("x"))),) if args.size else ((80,24),(132,50))
    asyncio.run(accept(args.root,args.door_python,args.show,sizes))
