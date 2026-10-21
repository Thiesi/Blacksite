"""S10 real NetBBS native stdio: training, PvP, clones, loot and safety.

Uses explicit grade-five/funding/shock fixtures because S16 earning is
not implemented. Movement, targeting, firing and menus use real keys.
No teleports. Run the NetBBS interpreter with --show in a real terminal.
"""

import argparse
import asyncio
from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
from typing import Any

from accept_s04_netbbs import Database, DatabaseLane, DoorProfile, REPO, TelnetServer, browse_doors, create_door, create_user
from accept_s06_netbbs import ZoneCaller
from blacksite.server.app import Server
from blacksite.server.inventory import Inventory
from blacksite.server.items import make_item
from blacksite.server.rules import character


async def wait(condition: Any, timeout: float = 10) -> None:
    async with asyncio.timeout(timeout):
        while not condition(): await asyncio.sleep(.02)


class CombatCaller(ZoneCaller):
    hit_border_seen = False

    def replay(self) -> None:
        super().replay()
        if self.screen.grid[0][:5] == ["-"]*5:
            self.hit_border_seen = True


@dataclass
class Connection:
    caller: CombatCaller
    writer: asyncio.StreamWriter
    pump: asyncio.Task[None]
    session: Any
    avatar: Any


class NativeProbe:
    def __init__(self, root: Path, python: Path, show: bool) -> None:
        # Resolving a Unix venv's Python symlink launches the base interpreter
        # instead, losing the installed wheel. Preserve the venv path.
        self.root,self.python,self.show = root.resolve(),python.absolute(),show
        self.service = Server(self.root/"world",tcp=True)
        self.connections: list[Connection] = []
        self.accounts: deque[tuple[Any,bool]] = deque()
        self.errors: list[str] = []

    async def start(self) -> None:
        self.root.mkdir(parents=True,exist_ok=True)
        await self.service.start()
        self.game,self.commerce,self.combat = self.service.core.characters,self.service.core.commerce,self.service.core.combat
        self.db = Database(self.root/"node.db"); self.lane = DatabaseLane(self.db.path)
        owner = create_user(self.db,"S10SysOp",password="LocalProbe-S10",user_level=10)
        create_door(self.db,"Blacksite",str(self.python),args=("-m","blacksite.door"),creator=owner,
            profile=DoorProfile(install_dir=str(REPO),encoding="utf-8",max_sessions=16,multinode_certified=True,
                time_limit=900,environment={"DOOR_BLACKSITE_INSTALL_DIR":str(self.service.install_dir)}).validate())
        async def handler(session: Any) -> None:
            user,sixteen = self.accounts.popleft()
            # Exercise NetBBS's real native-door 16-colour capability path.
            if sixteen: session.sixteen_colors = True
            try:
                await browse_doors(session,self.lane,user)
                await session.write_line("You return to the node.")
            except Exception as exc:
                self.errors.append(repr(exc)); raise
        self.node=TelnetServer("127.0.0.1",0,handler,terminal_type_wait_seconds=.1)
        await self.node.start()

    def report(self, message: str) -> None:
        print(message,flush=True)
        with (self.root/"progress.log").open("a",encoding="utf-8") as stream: stream.write(message+"\n")

    async def open(self, width: int, height: int, label: str, archetype: int = 0, sixteen: bool = False) -> Connection:
        user=create_user(self.db,f"S10{label}{width}",password="LocalProbe-S10",user_level=10)
        self.accounts.append((user,sixteen))
        reader,writer=await asyncio.open_connection("127.0.0.1",self.node.port)
        async def send(data: bytes) -> None:
            writer.write(data); await writer.drain()
        writer.write(b"\xff\xfb\x1f\xff\xfa\x1f"+width.to_bytes(2,"big")+height.to_bytes(2,"big")+b"\xff\xf0")
        writer.write(b"\xff\xfb\x18\xff\xfa\x18\x00xterm-256color\xff\xf0");await writer.drain()
        caller=CombatCaller(lambda:reader.read(65536),send,width,height,self.show and sixteen)
        await caller.expect("Available doors");await caller.write(b"\x1b[B\r")
        try:
            await caller.until(lambda:"THE WAKE" in caller.screen.screen_text(),timeout=10)
        except BaseException:
            (self.root/f"failed-launch-{label}-{width}.ans").write_bytes(caller.output)
            (self.root/f"failed-launch-{label}-{width}.txt").write_text(caller.screen.screen_text(),encoding="utf-8")
            writer.close();await writer.wait_closed()
            raise
        async def pump() -> None:
            while chunk:=await reader.read(65536): caller.output.extend(chunk);caller.replay()
        task=asyncio.create_task(pump())
        session=next(s for s in self.game.sessions.active.values() if s.id in self.game.wakes)
        connection=Connection(caller,writer,task,session,None)
        self.connections.append(connection)
        for index in range(archetype):
            await caller.write(b"\x1b[B")
            await wait(lambda:self.game.wakes[session.id].cursor==index+1)
        await wait(lambda:session.ack_revision==session.view_revision)
        await caller.write(b"\r");await wait(lambda:"Name (Enter keeps default):" in caller.screen.screen_text())
        await caller.write(f"{label}界{width}".encode()+b"\r")
        await wait(lambda:"Briefing" in caller.screen.screen_text());await caller.write(b"s")
        await wait(lambda:"Recruiter cards" in caller.screen.screen_text());await caller.write(b"\x1b")
        await wait(lambda:session.player_id in self.game.players)
        await wait(lambda:"Wake Hall" in caller.screen.screen_text().splitlines()[0])
        connection.avatar=self.game.sim.avatars[session.user_id]
        if sixteen: assert session.caps["tier"]=="16",session.caps
        return connection

    async def walk(self, connection: Connection, target: tuple[int,int]) -> None:
        av=connection.avatar
        zone=self.service.world.zones[av.zone]
        while av.actor.position!=target:
            start=av.actor.position
            occupied={a.position for a in zone.actors.values() if a is not av.actor and not (a.behaviour.get("training") and a.owner!=av.actor.id)}
            pending,previous=deque([start]),{start:None}
            exits={e.tile for e in zone.template.meta.exits if e.kind=="street"}
            while pending and target not in previous:
                x,y=pending.popleft()
                for tile in ((x+1,y),(x,y+1),(x-1,y),(x,y-1)):
                    if tile not in previous and tile not in occupied and zone.passable(tile) and (tile not in exits or tile==target):
                        previous[tile]=(x,y);pending.append(tile)
            assert target in previous,(zone.id,start,target)
            step=target
            while previous[step]!=start: step=previous[step]
            await wait(lambda:self.service.clock.now_tick()>=max(av.actor.cooldowns.get("move",0),av.actor.cooldowns.get("knockdown",0)))
            vector=step[0]-start[0],step[1]-start[1]
            await connection.caller.write({(1,0):b"\x1b[C",(-1,0):b"\x1b[D",(0,1):b"\x1b[B",(0,-1):b"\x1b[A"}[vector])
            await wait(lambda:av.actor.position!=start or av.zone!=zone.id)
            if av.zone!=zone.id: break

    async def travel(self, connection: Connection, destination: str) -> None:
        av=connection.avatar
        origin=av.zone
        exit_=next(e for e in self.service.world.zones[origin].template.meta.exits if e.target_zone==destination)
        await self.walk(connection,exit_.tile)
        if av.zone==origin: await connection.caller.write(b"e")
        await wait(lambda:av.zone==destination)
        await wait(lambda:self.service.world.zones[destination].template.meta.name in connection.caller.screen.screen_text().splitlines()[0])

    def fixture(self, connection: Connection) -> None:
        player=self.game.players[connection.session.player_id]
        player.update_progression(1700)
        player.chits_hand,player.chits_bank=1000,500
        actor=connection.avatar.actor
        actor.health=actor.health_max=character.health_max(player.attributes["vitals"])
        actor.stamina=actor.stamina_max=character.stamina_max(player.attributes["nerve"],player.attributes["frame"])
        actor.shock=75
        actor.cooldowns["last_hit"]=self.service.clock.now_tick()
        inventory=Inventory(self.commerce.items,self.game.content.items)
        serial=self.combat.next_serial()
        missing=200-sum(self.commerce.items[i].stack for i in player.inventory if self.commerce.items[i].template=="ammo_9x")
        while missing>0:
            serial+=1;amount=min(50,missing)
            inventory.add(player,make_item(f"{player.origin}:item:{serial}",self.game.content.items["ammo_9x"],player.id,self.service.clock.now_utc().isoformat(),amount))
            missing-=amount
        self.commerce.serial=serial
        self.game.snapshot(player,connection.avatar)
        self.game.queue("save",player.bbs_user_id,player,items=[i.record() for i in self.commerce.items.values() if i.owner==player.id],immediate=True)
        self.service._character_writes()

    async def leave(self, connection: Connection, label: str) -> None:
        caller=connection.caller;mark=len(caller.output)
        await caller.write(b"\x18y");await wait(lambda:b"Left Blacksite." in caller.output[mark:])
        await caller.write(b" ")
        await wait(lambda:b"Available doors" in re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]",b"",bytes(caller.output[mark:])))
        await caller.write(b"b");await wait(lambda:b"You return to the node." in caller.output[mark:])
        self.save(connection,label)
        connection.writer.close();await connection.writer.wait_closed();await connection.pump
        self.connections.remove(connection)

    def save(self, connection: Connection, label: str) -> None:
        (self.root/(label+".ans")).write_bytes(connection.caller.output)
        (self.root/(label+".txt")).write_text(connection.caller.screen.screen_text(),encoding="utf-8")

    async def close(self) -> None:
        for index,connection in enumerate(self.connections):
            self.save(connection,f"unfinished-{index}")
            connection.writer.close();connection.pump.cancel()
        await self.node.stop();self.lane.close();await self.service.stop();self.db.close()


async def accept(root: Path, door_python: Path, show: bool) -> None:
    probe=NativeProbe(root,door_python,show)
    await probe.start()
    results=[]
    try:
        for width,height in ((80,24),(132,50)):
            a=await probe.open(width,height,"Cantor",2,True)
            b=await probe.open(width,height,"Ghost",1)
            for connection,parking in ((a,(22,14)),(b,(24,14))):
                await probe.walk(connection,(21,14))
                await wait(lambda:any(n.owner==connection.avatar.actor.id for n in probe.service.world.actors.values()))
                await connection.caller.write(b"\t")
                started=time.monotonic()
                async with asyncio.timeout(35):
                    while probe.game.players[connection.session.player_id].progress.get("wake_combat")!="done":
                        await connection.caller.write(b"f");await asyncio.sleep(.2)
                probe.report(f"PASS private training {width}x{height}: {time.monotonic()-started:.1f}s, nonlethal, real Tab/F")
                await probe.walk(connection,parking)
            # Bind Steady and Jam through the real server-driven menu.
            actor=a.avatar.actor
            await a.caller.write(b"v");await wait(lambda:a.session.id in probe.combat.menus)
            await wait(lambda:"ABILITIES" in a.caller.screen.screen_text())
            await wait(lambda:a.session.ack_revision==a.session.view_revision)
            await a.caller.write(b"1");await wait(lambda:probe.game.players[a.session.player_id].progress.get("quick_abilities",{}).get("1")=="hymn_steady")
            for index in range(5):
                await a.caller.write(b"\x1b[B");await wait(lambda:probe.combat.menus[a.session.id]==index+1)
            await wait(lambda:a.session.ack_revision==a.session.view_revision)
            await a.caller.write(b"2");await wait(lambda:probe.game.players[a.session.player_id].progress["quick_abilities"].get("2")=="dis_jam")
            await a.caller.write(b"\x1b");await wait(lambda:a.session.id not in probe.combat.menus)
            await wait(lambda:"Wake Hall" in a.caller.screen.screen_text().splitlines()[0])
            await wait(lambda:a.session.ack_revision==a.session.view_revision)
            actor.shock=60;actor.cooldowns["last_hit"]=probe.service.clock.now_tick()
            await a.caller.write(b"1");await wait(lambda:actor.cooldowns.get("ability:hymn_steady",0)>probe.service.clock.now_tick())
            assert actor.shock<=40
            for connection,tile in ((a,(25,3)),(b,(27,3))):
                await probe.travel(connection,"vatside-clinics");await probe.walk(connection,tile)
            for connection in (a,b): probe.fixture(connection)
            for connection,other in ((a,b),(b,a)):
                await connection.caller.write(b"\t")
                await wait(lambda:connection.avatar.actor.target==other.avatar.actor.id)
                await wait(lambda:"TARGET" in connection.caller.screen.screen_text())
                await connection.caller.write(b"f")
            await asyncio.sleep(2.2)
            await a.caller.write(b"2")
            await wait(lambda:any(e.get("weapon_multiplier")==1.5 for e in b.avatar.actor.effects))
            jam=True;shock_seen=False;both_hurt=False;started=time.monotonic()
            async with asyncio.timeout(100):
                while all(c.avatar.actor.stance!="down" for c in (a,b)):
                    for connection in (a,b): await connection.caller.write(b"f")
                    shock_seen|=any(c.avatar.actor.shock>=80 for c in (a,b))
                    both_hurt|=all(c.avatar.actor.health<c.avatar.actor.health_max for c in (a,b))
                    await asyncio.sleep(.2)
            loser=next(c for c in (a,b) if c.avatar.actor.stance=="down")
            duel_seconds=round(time.monotonic()-started,1)
            winner=b if loser is a else a
            player=probe.game.players[loser.session.player_id]
            await wait(lambda:loser.avatar.actor.stance=="dead",7)
            await wait(lambda:"SABLIER DECANT" in loser.caller.screen.screen_text())
            assert player.chits_hand==900 and player.chits_bank==500 and player.xp==1696
            cid,cache=next((cid,cache) for cid,cache in probe.commerce.caches.items() if cache.get("victim")==player.id)
            assert all(probe.commerce.items[i].template!="arm_wake_coverall" for i in cache["items"])
            # Adjacent move into the loser's former tile; E opens the cache.
            await probe.walk(winner,tuple(cache["tile"]))
            await winner.caller.write(b"e");await wait(lambda:winner.session.id in probe.commerce.menus)
            await wait(lambda:probe.game.sim.overlays.get(winner.session.id,(None,{}))[0]=="menu")
            await wait(lambda:winner.session.ack_revision==winner.session.view_revision)
            screen=probe.commerce.menus[winner.session.id]
            rows=probe.commerce.body(winner.session,screen)["rows"]
            iid=next(r["id"] for r in rows if probe.commerce.items[r["id"]].template=="con_kestrel_ration")
            for index in range(next(i for i,r in enumerate(rows) if r["id"]==iid)):
                await winner.caller.write(b"\x1b[B");await wait(lambda:probe.commerce.menus[winner.session.id].cursor==index+1)
            await wait(lambda:winner.session.ack_revision==winner.session.view_revision)
            await winner.caller.write(b"\r");await wait(lambda:iid not in probe.commerce.caches[cid]["items"])
            await winner.caller.write(b"\x1b");await wait(lambda:winner.session.id not in probe.commerce.menus)
            await wait(lambda:loser.avatar.actor.stance=="normal",25)
            assert loser.avatar.zone=="vatside-wake-hall" and loser.avatar.actor.health==loser.avatar.actor.health_max
            assert any(probe.commerce.items[i].bound for i in player.inventory)
            for connection,tile in ((winner,(5,3)),(loser,(7,3))):
                if connection.avatar.zone=="vatside-wake-hall": await probe.travel(connection,"vatside-clinics")
                await probe.travel(connection,"core-plaza");await probe.walk(connection,tile)
            before=b.avatar.actor.health
            await a.caller.write(b"\t");await wait(lambda:a.avatar.actor.target==b.avatar.actor.id)
            await a.caller.write(b"f");await asyncio.sleep(.3)
            assert b.avatar.actor.health==before
            assert any("Protected" in row["text"] for row in a.session.log_ring)
            assert both_hurt and shock_seen and a.caller.hit_border_seen
            saved=next(p for p in probe.service.storage.character_state()["players"] if p["id"]==player.id)
            assert saved["chits_hand"]==900 and saved["chits_bank"]==500
            probe.report(f"PASS combat {width}x{height}: both HP fall, shock slow, Jam, down/dead/decant, clone charge 100, loot, loan kit, plaza safety, 16-colour border")
            await probe.leave(a,f"combat-cantor-{width}x{height}");await probe.leave(b,f"combat-ghost-{width}x{height}")
            results.append({"size":[width,height],"combat_seconds":duel_seconds,"both_hurt":both_hurt,
                "shock_slow":shock_seen,"jam":jam,"clone_charge":100,"bank":500,"cache_loot":True,"safe_refusal":True,"hit_flash_16":True})
        assert not probe.errors,probe.errors
        (probe.root/"result.json").write_text(json.dumps({"passed":True,"transport":"NetBBS Telnet native stdio",
            "scenario_funding":True,"grade_fixture":5,"shock_fixture":75,"teleports":False,"human_playtest":False,"runs":results},indent=2),encoding="utf-8")
    finally: await probe.close()


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--door-python",type=Path,required=True)
    parser.add_argument("--show",action="store_true")
    args=parser.parse_args()
    asyncio.run(accept(args.root,args.door_python,args.show))
