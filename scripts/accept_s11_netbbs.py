"""S11 real native door: populated streets, refusal, heat and local guards.

The heat interval is actually waited at both sizes. No player teleports,
extra money, faction membership or progression fixtures are needed.
"""

import argparse
import asyncio
import json
from pathlib import Path
import time

from accept_s10_netbbs import NativeProbe, wait
from blacksite.admin.client import request


async def profile(probe: NativeProbe, width: int, height: int) -> float:
    for zone in probe.service.world.zones.values():
        zone.activate("s11-profiling",probe.service.clock.now_tick())
    try:
        await asyncio.sleep(2)
        probe.service.core.loop.timings.clear()
        await asyncio.sleep(10)
        status=await request(probe.service.install_dir,"status")
        assert status["active_zones"]==10 and status["tick_p99_ms"]<10,status
        probe.report(f"PASS admin status {width}x{height}: all 10 zones active, p99 {status['tick_p99_ms']:.3f} ms")
        return status["tick_p99_ms"]
    finally:
        for zone in probe.service.world.zones.values():
            zone.deactivate("s11-profiling",probe.service.clock.now_tick())


async def accept(root: Path, door_python: Path, show: bool) -> None:
    probe=NativeProbe(root,door_python,show)
    await probe.start()
    results=[]
    try:
        for width,height in ((80,24),(132,50)):
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
            target=next(a for a in plaza.actors.values() if a.behaviour.get("template")=="npc-civilian" and probe.combat.visible(actor,a))
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
            await asyncio.sleep(3)
            assert patrol.target is None
            assert not probe.game.me(caller.session)["heat_until"]
            probe.report(f"PASS actual ten-minute heat expiry {width}x{height}: patrol ignores Freelance again")
            await probe.travel(caller,"core-plaza")
            await probe.travel(caller,"sodium-row")
            await probe.walk(caller,(16,5))
            sodium=probe.service.world.zones[actor.zone]
            regular=next(a for a in sodium.actors.values() if a.behaviour.get("template")=="npc-sodium-regular" and probe.combat.visible(actor,a))
            await probe.target(caller,regular.id)
            await caller.caller.write(b"f");await asyncio.sleep(2.2)
            await caller.caller.write(b"f")
            guards=[a for a in sodium.actors.values() if a.behaviour.get("template")=="npc-sable-enforcer"]
            await wait(lambda:any(a.target==actor.id for a in guards),3)
            assert not any(a.faction=="wardens" and a.target==actor.id for a in sodium.actors.values())
            probe.save(caller,f"s11-sodium-{width}x{height}")
            probe.report(f"PASS local response {width}x{height}: Sable enforcers answer provocation, no Wardens")
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
    args=parser.parse_args()
    asyncio.run(accept(args.root,args.door_python,args.show))
