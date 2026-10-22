"""Game 5.3: durable player tools, owned instances and local commands."""

from copy import deepcopy
from typing import Any, TYPE_CHECKING

from blacksite.server.clock import TICK_HZ
from blacksite.server.inventory import Inventory
from blacksite.server.npcs.behaviours import step_toward
from blacksite.server.players import Player
from blacksite.server.drugs import detox_until
from blacksite.server.protocol import Frame
from blacksite.server.rules.combat import distance
from blacksite.server.rules import combat as rules
from blacksite.server.npcs.templates import LOST_SIGHT_SECONDS
from blacksite.server.sessions import Session
from blacksite.server.wake import menu, wrapped
from blacksite.server.world.actors import Actor

if TYPE_CHECKING:
    from blacksite.server.progression_engine import ProgressionEngine


class Drones:
    def __init__(self, progression: "ProgressionEngine") -> None:
        self.progression, self.game, self.commerce = progression, progression.game, progression.commerce
        self.world, self.sim = self.game.world, self.commerce.sim
        self.actors: dict[str, Actor] = {}
        self.menus: dict[str, int] = {}
        self.requests: dict[str, list[str]] = {}
        self.pending: set[str] = set()
        self.pending_attacks: set[str] = set()

    def records(self, player: Player) -> dict[str, dict[str, Any]]:
        return player.progress.get("drones", {})

    def slots(self, player: Player) -> int:
        return max(0,int(self.progression.base_modifiers(player).bonus("drone_slots")))

    def restore(self, player: Player, iid: str) -> Actor | None:
        if iid in self.actors:
            return self.actors[iid]
        record = self.records(player).get(iid)
        item = self.commerce.items.get(iid)
        if not record or not item or item.owner != player.id or record["zone"] not in self.world.zones:
            return None
        template = self.game.content.items[item.template]
        block = template.drone
        if block is None:
            return None
        health = block.health if item.health is None else min(block.health,item.health)
        actor = Actor(player.id+":drone:"+iid.rsplit(":",1)[-1],template.name,kind="drone",
            health=health,health_max=block.health,faction=player.faction,owner=player.id,
            target=record.get("target") or None,stance="normal" if health else "dead",
            modifiers={"move_ms":block.move_ms},behaviour={"player_drone":True,"item":iid,
                "evasion":block.evasion,"mode":record.get("mode","follow")})
        try:
            tile = self.world.free_tile(record["zone"],tuple(record["tile"]))
            self.world.enter(actor,record["zone"],tile)
        except ValueError:
            return None  # A crowded deployment resumes when a tile clears.
        self.actors[iid] = actor
        return actor

    def body(self, player: Player) -> Actor | None:
        return self.game.combat.actor(player)

    def in_range(self, player: Player, actor: Actor) -> bool:
        body = self.body(player)
        item = self.commerce.items.get(str(actor.behaviour.get("item")))
        block = self.game.content.items[item.template].drone if item else None
        return bool(body and block and body.zone == actor.zone and body.zone is not None
                    and distance(body.position,actor.position) <= block.control_range)

    def controller_body(self, actor: Actor, *, acting: bool) -> Actor | None:
        """Only a live online controller authorizes harm; gear keeps identity."""
        iid = str(actor.behaviour.get("item",""))
        player = self.game.players.get(actor.owner)
        item = self.commerce.items.get(iid)
        if (player is None or player.id in self.game.deleting or item is None or item.owner != player.id
                or self.actors.get(iid) is not actor or iid not in self.records(player)):
            return None
        body = self.body(player)
        if acting:
            if (body is None or body.zone is None or body.health <= 0 or body.stance in ("down","dead","sleeper")
                    or self.game.combat.session(player.id) is None or not self.in_range(player,actor)
                    or list(self.records(player)).index(iid) >= self.slots(player)
                    or detox_until(player) > self.game.clock.now_utc().timestamp()):
                return None
        elif body is None or body.zone is None:
            # A defender's owned gear retains its grade and last body-safety
            # protection while offline. This record never authorizes attacks.
            body = player.actor()
            body.zone,body.x,body.y = player.zone,*player.tile
        return body

    def modifier_layers(self, player: Player) -> list[dict[str, float]]:
        if not self.records(player) or not self.game.combat.session(player.id):
            return []
        layers = []
        for iid in list(self.records(player))[:self.slots(player)]:
            actor = self.actors.get(iid)
            item = self.commerce.items.get(iid)
            if not actor or actor.health <= 0 or not item or not self.in_range(player,actor):
                continue
            block = self.game.content.items[item.template].drone
            if block and block.effects.get("carry_kg"):
                layers.append({"carry_kg":float(block.effects["carry_kg"])})
        return layers

    def command(self, player: Player, iid: str, action: str, target: str = "", *, system: bool = False) -> bool:
        if self.commerce.pending:
            if system:
                return False
            raise ValueError("The city is busy. Your drone command has not started.")
        if iid in self.pending or player.id in self.game.deleting:
            return False
        item = self.commerce.items.get(iid)
        if not item or item.owner != player.id or not self.game.content.items[item.template].drone:
            raise ValueError("Choose a drone you own.")
        block = self.game.content.items[item.template].drone
        actor = self.restore(player,iid) if iid in self.records(player) else None
        body = self.body(player)
        session = self.game.combat.session(player.id)
        if not system and (session is None or not self.commerce.ready(session)):
            raise ValueError("Return to your body before commanding a drone.")
        draft,items = deepcopy(player),deepcopy(self.commerce.items)
        records = deepcopy(self.records(player))
        message = ""
        if action == "deploy":
            if actor or iid in records:
                raise ValueError("That instance is already deployed.")
            if iid not in draft.inventory or item.stack != 1:
                raise ValueError("Carry the drone before deploying it.")
            if len(records) >= self.slots(player):
                raise ValueError(f"You have {self.slots(player)} drone slots. Recall one or install an uplink.")
            if item.health == 0:
                raise ValueError("That drone has no working health.")
            if not body or body.zone is None:
                raise ValueError("Deploy from a physical zone.")
            tile = self.world.free_tile(body.zone,body.position)
            if distance(tile,body.position) > 1.5:
                raise ValueError("No adjacent tile is free for deployment.")
            draft.inventory.remove(iid)
            draft.equipment = {key:value for key,value in draft.equipment.items() if value != iid}
            items[iid].health = block.health if item.health is None else item.health
            records[iid] = {"zone":body.zone,"tile":list(tile),"mode":"follow","target":""}
            message = "You deploy "+self.game.content.items[item.template].name+". It follows."
        elif action in ("follow","hold","target","recall"):
            if actor is None or iid not in records or actor.health <= 0:
                raise ValueError("That drone is not deployed.")
            if not system and not self.in_range(player,actor):
                raise ValueError("Your drone is outside its control range.")
            if action == "recall":
                if not system and self.game.clock.now_tick() < actor.cooldowns.get("combat",0):
                    raise ValueError("Recall after ten quiet seconds; the drone is still in combat.")
                items[iid].health = actor.health
                capacity = self.progression.modifiers(draft).secured_slots
                if system and items[iid].secured and sum(items[key].secured for key in draft.inventory) >= capacity:
                    items[iid].secured = False
                    message = actor.name+" returns unsecured because secured slots are full. "
                    if session is None:
                        draft.progress.setdefault("drone_notices",[]).append(message.strip())
                Inventory(items,self.game.content.items,capacity).add(draft,items[iid])
                records.pop(iid)
                message += "You recall "+actor.name+" with its current health."
            else:
                if action == "target":
                    other = self.world.actors.get(target)
                    if not block.attack or not other or not self.game.combat.legal(actor,other) or not self.game.combat.visible(actor,other):
                        raise ValueError("Choose a visible, unprotected threat for a combat drone.")
                else:
                    target = ""
                desired = {"zone":actor.zone,"tile":list(actor.position),"mode":action,"target":target}
                if action == "target":
                    desired["target_tile"] = list(other.position)
                if records[iid].get("mode") == action and records[iid].get("target","") == target:
                    return False
                records[iid] = desired
                items[iid].health = actor.health
                message = actor.name+(" follows you." if action == "follow" else " holds here." if action == "hold" else " takes your target.")
        else:
            raise ValueError("Choose deploy, follow, hold, target or recall.")
        draft.progress["drones"] = records
        patch = {key:deepcopy(getattr(draft,key)) for key in ("inventory","equipment","progress")
                 if getattr(draft,key) != getattr(player,key)}
        self.pending.add(iid)
        def committed(success: bool) -> None:
            self.pending.discard(iid)
            if success:
                if action == "recall":
                    self.world.leave(actor)
                    self.actors.pop(iid,None)
                elif action == "deploy":
                    self.restore(player,iid)
                else:
                    actor.behaviour["mode"] = action
                    actor.target = target or None
                    if action == "target":
                        actor.behaviour["last_target"] = (tuple(records[iid]["target_tile"]),self.game.clock.now_tick())
                self.progression.sync_actor(player)
                if body:
                    self.game.combat.log(body,message)
            elif session:
                self.commerce.toast(session,"The command could not be saved. Your drone remains as it was.")
        return self.commerce.settle(player,patch,items,self.commerce.caches,self.commerce.serial,committed)

    def destroy(self, actor: Actor) -> None:
        iid = str(actor.behaviour.get("item",""))
        if iid in self.pending:
            return
        player = self.game.players.get(actor.owner)
        if player is None:
            self.world.leave(actor); self.actors.pop(iid,None)
            return
        self.pending.add(iid)
        actor.stance = "dead"
        def propose() -> None:
            if player.id not in self.game.players or player.id in self.game.deleting:
                self.pending.discard(iid)
                return
            draft,items = deepcopy(player),deepcopy(self.commerce.items)
            draft.progress.setdefault("drones",{}).pop(iid,None)
            items.pop(iid,None)
            def committed(success: bool) -> None:
                self.pending.discard(iid)
                if success:
                    self.world.leave(actor); self.actors.pop(iid,None)
                    self.progression.sync_actor(player)
                    body = self.body(player)
                    if body:
                        self.game.combat.log(body,actor.name+" is destroyed.",True)
                else:
                    actor.health,actor.stance = 1,"normal"
            self.commerce.settle(player,{"progress":draft.progress},items,self.commerce.caches,self.commerce.serial,committed)
        try:
            self.commerce.enqueue_system(propose)
        except ValueError:
            self.pending.discard(iid)  # The dead actor retries next tick.

    def checkpoint(self, player: Player, iid: str, actor: Actor) -> None:
        if self.commerce.pending or iid in self.pending or player.id in self.game.deleting or player.id not in self.game.players:
            return
        item = self.commerce.items.get(iid)
        if not item or item.health == actor.health:
            return
        items = deepcopy(self.commerce.items)
        items[iid].health = actor.health
        self.pending.add(iid)
        self.commerce.settle(player,{},items,self.commerce.caches,self.commerce.serial,
                             lambda success:self.pending.discard(iid))

    def hunt(self, player: Player, actor: Actor, tile: tuple[int, int], tick: int) -> None:
        body = self.body(player)
        block = self.game.content.items[self.commerce.items[actor.behaviour["item"]].template].drone
        if not body or body.zone != actor.zone:
            return
        avoid = {(actor.x+dx,actor.y+dy) for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))
                 if distance(body.position,(actor.x+dx,actor.y+dy)) > block.control_range}
        step_toward(actor,self.world.zones[actor.zone],tile,tick,avoid=avoid)

    def attack(self, player: Player, iid: str, actor: Actor, tick: int) -> None:
        body = self.controller_body(actor,acting=True)
        item = self.commerce.items.get(iid)
        block = self.game.content.items[item.template].drone if item else None
        if not body or not block or not block.attack or actor.stance in ("down","dead"):
            return
        combat = self.game.combat
        target = self.world.actors.get(actor.target) if actor.behaviour.get("mode") == "target" else None
        if target is None:
            # Actual hostile exchanges identify an attacker; merely
            # selecting the controller is never a licence to retaliate.
            for protected in (body,actor):
                if tick < protected.cooldowns.get("attacked",0):
                    candidate = self.world.actors.get(protected.behaviour.get("last_attacker"))
                    if candidate and combat.legal(actor,candidate) and combat.visible(actor,candidate):
                        target = candidate
                        break
        if target is None or not combat.legal(actor,target):
            return
        visible = combat.visible(actor,target)
        if visible:
            actor.behaviour["last_target"] = target.position,tick
        elif block.hunt and actor.behaviour.get("last_target"):
            tile,seen = actor.behaviour["last_target"]
            if tick-seen < rules.ticks(LOST_SIGHT_SECONDS):
                self.hunt(player,actor,tile,tick)
            return
        else:
            return
        if distance(actor.position,target.position) > (block.attack.range or 1.5):
            if block.hunt or actor.behaviour.get("mode") == "target":
                self.hunt(player,actor,target.position,tick)
            return
        if tick < max(actor.cooldowns.get("weapon",0),actor.cooldowns.get("knockdown",0)):
            return
        if not combat.warn(body,target,tick):
            return
        if self.commerce.pending:
            if iid not in self.pending_attacks:
                self.pending_attacks.add(iid)
                def resume() -> None:
                    self.pending_attacks.discard(iid)
                    self.attack(player,iid,actor,self.game.clock.now_tick())
                try:
                    self.commerce.enqueue_system(resume)
                except ValueError:
                    self.pending_attacks.discard(iid)  # Recheck next tick under backpressure.
            return
        combat.mark(actor,target)
        jam = max((float(effect.get("weapon_multiplier",1)) for effect in actor.effects),default=1)
        seconds = rules.action_seconds(block.attack.cooldown,actor.shock,jam)
        actor.cooldowns["weapon"] = rules.cooldown_deadline(tick,seconds,actor.cooldowns.get("weapon",0))
        skill = self.progression.modifiers(player).skill(player,"drones")
        for _ in range(block.attack.hits):
            combat.shot(actor,target,block.attack,item.quality,skill)

    def view(self, session: Session) -> dict[str, Any]:
        player = self.game.players[session.player_id]
        ids = [iid for iid in player.inventory if self.game.content.items[self.commerce.items[iid].template].drone]
        ids += list(self.records(player))
        rows = []
        for iid in ids:
            item = self.commerce.items.get(iid)
            if item is None:
                continue
            template = self.game.content.items[item.template]
            actor = self.actors.get(iid)
            health = actor.health if actor else item.health if item.health is not None else template.drone.health
            status = str(actor.behaviour["mode"]) if actor else "packed"
            rows.append({"id":iid,"cells":[template.name,status,f"{health}/{template.drone.health}"]})
        cursor = min(self.menus[session.id],max(0,len(rows)-1))
        detail = f"Drone slots {len(self.records(player))}/{self.slots(player)}. Select a unit. Idle mode toggles earn no skill."
        if rows:
            template = self.game.content.items[self.commerce.items[rows[cursor]["id"]].template]
            detail += f" {template.drone.tool}. Control range {template.drone.control_range}. Recall keeps health."
            actor = self.actors.get(rows[cursor]["id"])
            body = self.body(player)
            target = self.world.actors.get(body.target) if body else None
            if actor and template.drone.attack and target:
                if not self.game.combat.legal(actor,target):
                    status = "protected; no attack"
                else:
                    other = self.progression.controller(target)
                    other_body = self.controller_body(target,acting=False) if target.behaviour.get("player_drone") else target
                    marked = bool(other and self.game.combat.relation(body,target) != "hostile" and any(
                        self.world.zones[person.zone].safety_at(person.position) != "open" for person in (body,other_body)))
                    status = "order marks you for 15 minutes" if marked else "order gives a two-second warning"
                detail = f"Target {target.name}: {status}.\n"+detail
        else:
            rows = [{"id":"none","cells":["You carry no drone."]}]
        details = "\n".join(line for paragraph in detail.split("\n") for line in wrapped(paragraph,52))
        return {**menu("DRONES",rows,cursor,details,"U deploy  R recall  F follow  H hold  T current target  Esc/B returns"),
                "actions":[{"key":key,"label":label} for key,label in
                    (("u","deploy"),("r","recall"),("f","follow"),("h","hold"),("t","target"))]}

    def close(self, session: Session) -> None:
        self.menus.pop(session.id,None)
        if self.sim.external_views.get(session.id,("",))[0] == "menu":
            self.sim.external_views.pop(session.id,None)
        self.sim.reset_view(session,self.sim.avatars[session.user_id])

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        player = self.game.players.get(session.player_id)
        if player is None:
            return False
        name = frame.data.get("name","") if frame.type == "intent" else ""
        args = frame.data.get("args",{})
        key = frame.data.get("k","") if frame.type == "key" else ""
        table = next((m for m in self.sim.keymap.get("keymaps",[]) if m["id"] == session.keymap_id),{})
        action = next((a for a,keys in table.get("bindings",{}).items() if key in keys),name)
        try:
            if name in ("drone.open","drones.open") or action == "drone_menu":
                if self.commerce.ready(session) and session.id not in self.sim.external_views and session.id not in self.sim.maps:
                    self.menus[session.id] = 0
                    self.sim.external_views[session.id] = "menu",self.view(session)
                return True
            if session.id in self.menus:
                if name == "menu_close":
                    self.close(session)
                elif name == "menu_cursor" and type(args.get("delta")) is int:
                    self.menus[session.id] = max(0,min(len(self.view(session)["rows"])-1,self.menus[session.id]+args["delta"]))
                elif name == "menu_select" and frame.data.get("expected_revision") == session.view_revision:
                    view = self.view(session)
                    iid = view["rows"][view["cursor"]]["id"]
                    if args.get("row") != iid:
                        return True
                    command = {"u":"deploy","r":"recall","f":"follow","h":"hold","t":"target"}.get(args.get("key"))
                    if command:
                        self.submit(session,frame,iid,command,self.body(player).target or "")
                return True
            iid = args.get("item","")
            if name == "drone.command":
                self.submit(session,frame,iid,args.get("command",""),args.get("target","") or "")
                return True
            if name == "inv.use" and iid in player.inventory and self.game.content.items[self.commerce.items[iid].template].drone:
                self.submit(session,frame,iid,"deploy","")
                return True
        except (ValueError,KeyError,TypeError) as exc:
            self.commerce.toast(session,str(exc) if isinstance(exc,ValueError) else "That drone command is unavailable.")
            return True
        return False

    def submit(self, session: Session, frame: Frame, iid: str, action: str, target: str) -> None:
        if not isinstance(iid,str) or not isinstance(action,str) or not isinstance(target,str):
            raise ValueError("Choose your drone, a command and a target.")
        request = frame.data.get("request_id","")
        if request and request in self.requests.get(session.id,()):
            return
        if self.command(self.game.players[session.player_id],iid,action,target) and request:
            self.requests.setdefault(session.id,[]).append(request)
            self.requests[session.id] = self.requests[session.id][-128:]

    def tick(self, tick: int) -> None:
        for player in tuple(self.game.players.values()):
            if player.id in self.game.deleting:
                continue
            body = self.body(player)
            if body and self.game.combat.session(player.id) and player.progress.get("drone_notices"):
                for notice in player.progress.pop("drone_notices"):
                    self.game.combat.log(body,notice,True)
                self.game.queue("save",player.bbs_user_id,player,immediate=False)
            for iid in tuple(self.records(player)):
                actor = self.restore(player,iid)
                if actor is None:
                    continue
                if actor.health <= 0:
                    self.destroy(actor)
                    continue
                body = self.body(player)
                online = self.game.combat.session(player.id)
                over_limit = list(self.records(player)).index(iid) >= self.slots(player)
                inactive = body is not None and (body.health <= 0 or body.stance in ("down","dead","sleeper"))
                if (online is None or over_limit or inactive) and tick >= actor.cooldowns.get("combat",0):
                    self.command(player,iid,"recall",system=True)
                    continue
                if actor.shock and tick-actor.cooldowns.get("last_hit",tick) >= rules.ticks(rules.SHOCK_DELAY):
                    actor.shock = max(0,actor.shock-rules.SHOCK_DECAY/TICK_HZ)
                actor.marked = bool(body and body.marked)
                if body and body.zone == actor.zone and actor.behaviour.get("mode") == "follow" and distance(body.position,actor.position) > 1.5:
                    step_toward(actor,self.world.zones[actor.zone],body.position,tick)
                self.attack(player,iid,actor,tick)
                if actor.zone:
                    self.records(player)[iid].update(zone=actor.zone,tile=list(actor.position))
                    if tick % (5*TICK_HZ) == 0:
                        self.game.queue("save",player.bbs_user_id,player,immediate=False)
                        self.checkpoint(player,iid,actor)
        for iid,actor in tuple(self.actors.items()):
            if actor.owner not in self.game.players or iid not in self.commerce.items:
                self.world.leave(actor); self.actors.pop(iid,None)
        for sid in tuple(self.menus):
            session = self.game.sessions.active.get(sid)
            if session is None or session.closed or not self.commerce.ready(session):
                self.menus.pop(sid,None)
                if self.sim.external_views.get(sid,("",))[0] == "menu":
                    self.sim.external_views.pop(sid,None)
            else:
                self.sim.external_views[sid] = "menu",self.view(session)
        for sid in self.requests.keys()-self.game.sessions.active.keys():
            self.requests.pop(sid,None)
