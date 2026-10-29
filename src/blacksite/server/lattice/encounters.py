"""Authoritative core rooms and encounters. No transport or storage calls.

Defenders return attributed events; reward proposals share Commerce's
transaction outbox. Caller views expose costs and phases before an action.
"""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from hashlib import blake2b
from math import ceil
from random import Random
from typing import TYPE_CHECKING, Any

from blacksite.layout import compute as screen_layout
from blacksite.content.schema import DataSpec, ProgramTemplate
from blacksite.formatting import display_number
from blacksite.server.clock import TICK_HZ
from blacksite.server.inventory import Inventory
from blacksite.server.items import make_item
from blacksite.server.lattice.cores import CORE_IDLE_RESET_SECONDS, TRACE_PER_SECOND, CoreGraph, trace_thresholds
from blacksite.server.lattice.ice import Ice, IceEvent, Location, Runner
from blacksite.server.lattice.presence import INTEGRITY_MAX, Presence, Procedure, directional_neighbour, movement_ticks
from blacksite.server.lattice.programs import Cast, Effects, attack_damage, bind, can_cast, cast_ticks, occupied_slots, ticks, trace_gain, learn as learn_program
from blacksite.server.lattice.silt import Descent, adjacent_hidden, generate, survey_directions
from blacksite.server.lattice.silt_scene import BandGraph
from blacksite.server.players import Player
from blacksite.server.progression import Grant, award
from blacksite.server.sessions import Session
from blacksite.server.protocol import Frame
from blacksite.server.skills import Use
from blacksite.server.wake import menu, wrapped

if TYPE_CHECKING:
    from blacksite.server.lattice.engine import Lattice

LIFT_SECONDS = 3  # Game 6.1/6.7.
LIFT_TRACE = 10  # World Lattice 7.
FORCED_SHOCK = 100  # Game 6.1.
KEY_WINDOW_SECONDS = 10  # Game 17.2, Locksmith.
DISTRICT_HUNTER_TIER = 3  # Game 6.7: baseline hunter outside a tiered core.


@dataclass
class Instance:
    id: str
    graph: CoreGraph | BandGraph
    ice: dict[str, Ice]
    rng: Random
    empty_since: int | None = None


@dataclass
class EncounterMenu:
    kind: str
    cursor: int = 0
    slot: int = 0
    target: str = ""
    label: str = ""


class Encounters:
    def __init__(self, lattice: "Lattice") -> None:
        self.lat = lattice
        self.game, self.combat, self.content = lattice.game, lattice.combat, lattice.content
        self.clock, self.commerce = lattice.clock, lattice.combat.commerce
        self.instances: dict[str, Instance] = {}
        self.hunters: dict[str, Ice] = {}
        self.menus: dict[str, EncounterMenu] = {}
        self.delayed: list[IceEvent] = []
        self.dispatch: Callable[[Player], None] = lambda player: None
        self.report: Callable[[Player, str, bool], None] = lambda player, owner, exact: None
        self.reports: dict[tuple[str, str], tuple[float, str, tuple[int, int]]] = {}
        self.descents: dict[str, Descent] = {}
        self.empty_descents: dict[str, int] = {}
        self.commerce.after_settle = self.flush_hits
        self.mission_of: Callable[[str, str], str | None] = lambda pid, source: None  # S19.
        self.contract_rows: Callable[[Presence], list[dict[str, Any]]] = lambda presence: []
        self.start_contract_plant: Callable[[Presence, str], None] = lambda presence, job: None
        self.finish_contract_plant: Callable[[Presence, Procedure], None] = lambda presence, procedure: None
        self.inspect_contract: Callable[[Presence], None] = lambda presence: None

    def known_programs(self, player: Player) -> set[str]:
        loans = self.game.factions.loan_programs(player) if hasattr(self.game, "factions") else set()
        return set(self.content.starts[player.archetype].programs) | set(player.progress.get("known_programs", [])) | loans

    def move_multiplier(self, player: Player) -> float:
        return self.game.progression.modifiers(player).multiplier("cell_move_multiplier")

    def publish_report(self, player: Player, owner: str, exact: bool) -> None:
        actor = self.combat.actor(player)
        if actor is None or not actor.zone:
            return
        if exact:
            self.reports[player.id, owner] = self.clock.now_utc().timestamp()+300, actor.zone, actor.position
        text = (f"Reported body: {player.name}, {self.game.world.zones[actor.zone].template.meta.name} "
                f"{actor.position[0]},{actor.position[1]}." if exact else "A runner is inside the faction's core.")
        for session in self.game.sessions.active.values():
            recipient = self.game.players.get(session.player_id)
            if recipient and recipient.faction == owner and not session.closed:
                session.send(Frame("log", {"lines": [{"channel": "faction", "text": text,
                    "role": "warning", "at": self.clock.now_utc().isoformat()}]}))

    def reported_location(self, viewer: Session, target: Session) -> str | None:
        observer = self.game.players.get(viewer.player_id)
        if observer is None:
            return None
        report = self.reports.get((target.player_id, observer.faction))
        if report and report[0] > self.clock.now_utc().timestamp():
            return f"REPORTED {self.game.world.zones[report[1]].template.meta.name} {report[2][0]},{report[2][1]}"
        return None

    def location(self, presence: Presence) -> Location:
        return (presence.instance, presence.room) if presence.instance else (presence.sector, presence.cell)

    def session(self, pid: str) -> Session | None:
        held = self.lat.orphans.get(pid)
        return held[0] if held else self.lat.session(pid)

    def actor(self, presence: Presence):
        return self.combat.actor(self.game.players[presence.player_id])

    def log(self, presence: Presence, text: str, warning: bool = False) -> None:
        session = self.session(presence.player_id)
        if session and not session.closed:
            self.lat.log(session, text, warning)

    def hit_serial(self, presence: Presence) -> int:
        actor = self.actor(presence)
        return presence.hit_serial + int(actor.behaviour.get("hit_serial", 0))

    def idle(self, presence: Presence) -> bool:
        return not (presence.cast or presence.procedure or presence.destination
                    or presence.room_destination or presence.escape)

    def core(self, presence: Presence) -> Instance | None:
        return self.instances.get(presence.instance)

    def defenders(self, presence: Presence, *, room_only: bool = True) -> list[Ice]:
        instance = self.core(presence)
        candidates = list(instance.ice.values()) if instance else []
        candidates += [ice for ice in self.hunters.values() if ice.target == presence.player_id]
        return [ice for ice in candidates if ice.alive and
                (ice.location == self.location(presence) if room_only else
                 ice.location[0] == self.location(presence)[0])]

    def runner_targets(self, presence: Presence) -> list[Presence]:
        return [other for other in self.lat.presences.values()
                if other.player_id != presence.player_id
                and self.location(other) == self.location(presence)
                and (actor := self.actor(other)) is not None and actor.stance == "jacked"]

    def spawn(self, core_id: str, iid: str) -> Instance:
        graph = CoreGraph(self.content.cores[core_id])
        seed = int.from_bytes(blake2b(iid.encode(), digest_size=16).digest(), "big")
        defenders = {}
        tick = self.clock.now_tick()
        for room in graph.rooms.values():
            for index, template_id in enumerate(room.ice):
                template = self.content.ice[template_id]
                if room.ice_events.get(template_id) and room.ice_events[template_id] not in self.lat.events:
                    continue
                if template.behaviour == "hunter":
                    continue  # Hunters are attributed to the trace-100 runner.
                key = f"{iid}:{room.id}:{index}"
                defenders[key] = Ice.spawn(key, template, (iid, room.id), graph.spec.tier, tick,
                                            graph.spec.affiliation)
                if template.behaviour == "roaming" and template.class_ != "drift":
                    route = room.ice_patrols.get(template_id) or graph.patrol(room.id)
                    defenders[key].patrol = tuple((iid, rid) for rid in route)
                    defenders[key].patrol_index = route.index(room.id)
        return Instance(iid, graph, defenders, Random(seed))

    def can_enter(self, presence: Presence, core_id: str) -> bool:
        cell = self.lat.sectors.cells[presence.sector][presence.cell]
        if cell.core_id == core_id:
            return True
        # The Wake lesson is also available at its actual physical terminal.
        actor = self.actor(presence)
        terminal = self.lat.terminal(actor) if actor and actor.zone else None
        return bool(core_id == "lat-wake-hall" and terminal and
                    terminal.spec.params.get("training_core") == core_id and
                    presence.cell == self.lat.sectors.entrance(presence.sector))

    def enter(self, session: Session, core_id: str, risk: bool = False) -> None:
        apartment = self.lat.interlock.private.apartment(core_id)
        if apartment and not self.lat.interlock.private.before_access(apartment["resident"]):
            raise ValueError("The lease is being reconciled. Inspect the current entrance again.")
        presence = self.lat.presences[session.player_id]
        if not self.idle(presence) or presence.instance:
            raise ValueError("Finish your current action before entering a core.")
        spec = self.content.cores.get(core_id)
        if (not spec or not self.content.active("cores", core_id) or spec.template
                or not self.can_enter(presence, core_id)):
            raise ValueError("No live core entrance is here.")
        player = self.game.players[presence.player_id]
        if self.lat.sources.locked(player.bbs_user_id, core_id, self.clock.now_utc().timestamp()):
            raise ValueError("This identity's five-minute core lockout is still active.")
        if self.lat.interlock.offline(core_id):
            raise ValueError("The core is offline. Its hardware is dark.")
        threats = [self.content.ice[i] for room in spec.rooms for i in room.ice]
        if spec.trace_policy == "corporate":
            threats.append(self.content.ice["ice_hound"])
        black = any(Ice.spawn("inspection", template, ("", ""), spec.tier, 0).meat_damage
                    for template in threats)
        if black and not risk:
            raise ValueError("BLACK ICE: NPC feedback can injure your body here. Choose Enter with NPC risk.")
        iid = spec.id + (":" + player.id if spec.training else "")
        instance = self.instances.get(iid)
        if instance is None or (instance.empty_since is not None and
                self.clock.now_tick()-instance.empty_since >= ticks(CORE_IDLE_RESET_SECONDS)):
            instance = self.instances[iid] = self.spawn(core_id, iid)
        instance.empty_since = None
        self.lat.notify(presence, player.name+" enters a core.", exclude=player.id)
        presence.core, presence.instance, presence.room = core_id, iid, instance.graph.entry
        presence.target = ""
        if risk and black and spec.owner_kind not in ("private", "relay"):
            presence.risk_consent.add(iid)
        self.log(presence, "You enter "+spec.name+". B returns along the entry; J starts escape.")
        if black:
            self.log(presence, "BLACK ICE / NPC BODY RISK remains active for this run.", True)
        self.trace(presence, 0, entered=True)
        if hasattr(self.game, 'contracts'):
            self.game.contracts.entered(presence)

    def leave_core(self, session: Session) -> None:
        presence = self.lat.presences[session.player_id]
        instance = self.core(presence)
        if not instance:
            return
        if presence.descent:
            if presence.room != instance.graph.entry:
                known = presence.found_silt.setdefault(instance.id, set())
                route = instance.graph.band.route(presence.room, instance.graph.entry, known)
                if len(route) > 1:
                    self.move(presence, route[1])
                return
            if presence.depth:
                self.enter_band(presence, presence.depth-1, presence.return_cells.get(presence.depth-1))
            else:
                origin = presence.silt_return or (None, None, None)
                presence.instance, presence.core, presence.room = (
                    (None, None, None) if origin[1] and self.lat.interlock.offline(origin[1]) else origin)
                presence.descent = None
                presence.silt_return = None
                presence.cast = presence.procedure = None
                self.follow(presence)
                self.log(presence, "You rise to the entrance you used.")
            return
        if presence.room != instance.graph.entry:
            route = instance.graph.route(presence.room, instance.graph.entry)
            if len(route) > 1:
                self.move(presence, route[1])
            return
        presence.cast = presence.procedure = None
        presence.room_destination = None
        presence.core = presence.instance = presence.room = None
        presence.target = ""
        self.follow(presence)
        self.log(presence, "You return to the district entrance.")

    def move(self, presence: Presence, target: str) -> None:
        instance = self.core(presence)
        if not instance or not instance.graph.adjacent(presence.room, target):
            raise ValueError("Choose a linked room.")
        if presence.descent:
            cell = instance.graph.band.cell(target)
            if cell.hidden and target not in presence.found_silt.get(instance.id, set()):
                raise ValueError("Survey or Lantern can reveal that branch. A visible route continues.")
        if self.clock.now_tick() < presence.pinned_until:
            raise ValueError("You are pinned. J still starts escape.")
        if not self.idle(presence):
            raise ValueError("Finish or cancel the current action first.")
        retreat = (instance.graph.band.route(presence.room, instance.graph.entry,
                   presence.found_silt.get(instance.id, set())) if presence.descent else
                   instance.graph.route(presence.room, instance.graph.entry))
        if len(retreat) <= 1 or target != retreat[1]:
            for ice in self.defenders(presence):
                if ice.blocks(self.clock.now_utc().timestamp()) and ice.id not in presence.opened:
                    self.activate(ice, presence, "passage")
                    raise ValueError(ice.template.name+" blocks passage. Use its key or destroy it; retreat stays open.")
        player = self.game.players[presence.player_id]
        duration = movement_ticks(self.game.progression.modifiers(player).attribute(player, "cortex"), self.move_multiplier(player))
        presence.redline_move = presence.effects.has("prg_redline", self.clock.now_tick())
        if presence.redline_move:
            duration = min(duration, ticks(float(self.content.programs["prg_redline"].effect.amount)))
        presence.room_destination, presence.move_until = target, self.clock.now_tick()+duration

    def descend(self, session: Session, risk: bool = False) -> None:
        presence = self.lat.presences[session.player_id]
        if not self.idle(presence):
            raise ValueError("Finish or cancel the current action first.")
        if presence.descent:
            graph = self.core(presence).graph
            if presence.room not in graph.band.sinks:
                raise ValueError("Use a labelled sink to enter the next band; B returns to the riser.")
            presence.return_cells[presence.depth] = presence.room
            self.enter_band(presence, presence.depth+1)
            return
        instance = self.core(presence)
        cell = self.lat.sectors.cells[presence.sector][presence.cell]
        if not (instance and instance.graph.room(presence.room).descent or
                instance is None and cell.kind == "descent"):
            raise ValueError("No Silt descent is here.")
        if not risk:
            raise ValueError("SILT: warned NPC black feedback below can injure your body. Choose Descend with NPC risk.")
        if self.commerce.pending:
            raise ValueError("Let the current transfer settle before the descent.")
        context = self.location(presence)
        shared = self.game.crews.shared_silt(presence.player_id, context)
        if shared and shared in self.descents:
            self.enter_descent(presence, shared)
            return
        nonce = self.lat.sources.nonce+1
        context = self.location(presence)
        def finished(success: bool) -> None:
            if not success:
                self.log(presence, "The descent could not be saved. You remain at the entrance.", True)
                return
            self.lat.sources.nonce = nonce
            self.lat.sources.revision += 1
            # A committed nonce may be unused after a disconnect; it is never
            # reused, and no scene is published to a retired presence.
            if (self.lat.presences.get(presence.player_id) is not presence
                    or self.location(presence) != context or session.closed):
                return
            descent = generate(self.game.sessions.origin, self.lat.season, presence.sector,
                               nonce, self.content.silt)
            self.descents[descent.id] = descent
            self.game.crews.remember_silt(presence.player_id, context, descent.id)
            self.enter_descent(presence, descent.id)
        self.commerce.settle(None, {}, self.commerce.items, self.commerce.caches,
                             self.commerce.serial, finished)
        self.commerce.outbox[-1]["lattice_state"] = lambda: self.lat.sources.record(self.clock.now_tick(), nonce=nonce)

    def enter_descent(self, presence: Presence, descent: str) -> None:
        presence.silt_return = presence.instance, presence.core, presence.room
        presence.descent = descent
        presence.mapping_until = 0
        presence.survey_records.clear()
        presence.sampled.clear()
        presence.found_silt.clear()
        self.enter_band(presence, 0)

    def enter_band(self, presence: Presence, depth: int, room: str | None = None) -> None:
        descent = self.descents[presence.descent]
        band = descent.bands[depth]
        iid = descent.id+":"+band.id
        instance = self.instances.get(iid)
        if instance is None:
            graph = BandGraph(descent, band, self.content)
            defenders = {}
            tick = self.clock.now_tick()
            for chamber in graph.rooms.values():
                for index, template_id in enumerate(chamber.ice):
                    ice_id = iid+":"+chamber.id+":"+str(index)
                    ice = Ice.spawn(ice_id, self.content.ice[template_id], (iid, chamber.id), depth+1, tick)
                    route = graph.patrols.get(chamber.id+":"+str(index), ())
                    ice.patrol = tuple((iid, cell) for cell in route)
                    defenders[ice_id] = ice
            instance = self.instances[iid] = Instance(iid, graph, defenders, Random(descent.seed+depth))
        presence.depth, presence.instance, presence.core = depth, iid, band.id
        presence.room, presence.room_destination = room or band.riser, None
        presence.risk_consent.add(iid)
        presence.target = ""
        presence.trace = 0
        presence.cast = presence.procedure = None
        presence.found_silt.setdefault(iid, set()).add(presence.room)
        self.lat.sense_hidden(presence)
        self.follow(presence)
        self.log(presence, f"SILT / {band.name}. No trace. B follows the riser; J starts escape.")
        self.log(presence, "NPC BLACK FEEDBACK / BODY RISK below remains active.", True)

    def survey(self, presence: Presence, sample: bool = False) -> None:
        if not self.idle(presence) or sample and not presence.descent or presence.instance and not presence.descent:
            raise ValueError("Survey while idle in a district or the Silt; sample only in the Silt.")
        tick, player = self.clock.now_tick(), self.game.players[presence.player_id]
        signal = next((i for i in self.defenders(presence) if i.template.class_ == "chorister" and not i.provoked), None)
        if sample:
            if not signal or signal.id not in presence.survey_records or signal.signal_phase(tick)[0] != "sampling":
                raise ValueError("Record this signal during listening, then start a hold during sampling.")
            if signal.id in presence.sampled:
                raise ValueError("You already mapped this signal for this descent.")
        elif player.progress.get("lattice_cooldowns", {}).get("survey", 0) > self.clock.now_utc().timestamp():
            raise ValueError("Survey is cooling down for ten seconds.")
        presence.procedure = Procedure("sample" if sample else "survey", signal.id if signal else "",
            tick+ticks(3), self.location(presence)[0], self.hit_serial(presence))
        self.log(presence, "Hold for three seconds; Esc withdraws. No answer is required.")

    def complete_survey(self, presence: Presence, procedure: Procedure) -> None:
        tick = self.clock.now_tick()
        player = self.game.players[presence.player_id]
        if not presence.descent:
            player.progress.setdefault("lattice_cooldowns", {})["survey"] = self.clock.now_utc().timestamp()+10
            self.game.queue("save", player.bbs_user_id, player, immediate=True)
            cells = self.lat.sectors.cells[presence.sector]
            hidden = [cells[cid] for cid in cells[presence.cell].neighbours
                      if cells[cid].access_kind == "hidden" and cid not in self.lat.found(player, presence.sector)]
            if self.game.progression.modifiers(player).skill(player, "listening") >= 20:
                for cell in hidden:
                    self.lat.reveal(player, presence.sector, cell.id, learn=True)
                self.log(presence, "Survey reveals adjacent hidden cells." if hidden else "No hidden signal is adjacent.")
            else:
                origin = cells[presence.cell].pos
                directions = sorted({("north" if cell.pos[1] < origin[1] else "south" if cell.pos[1] > origin[1] else "")+
                    ("west" if cell.pos[0] < origin[0] else "east" if cell.pos[0] > origin[0] else "") for cell in hidden})
                self.log(presence,"Hidden signal directions: "+(", ".join(directions) if directions else "none adjacent")+". Listening 20 resolves them.")
            return
        graph = self.core(presence).graph
        known = presence.found_silt.setdefault(presence.instance, set())
        signal = self.target(presence, procedure.target)
        if procedure.kind == "sample":
            if not signal or signal.provoked or signal.signal_phase(tick)[0] != "sampling":
                self.log(presence, "The hold misses sampling. The cycle resets; withdraw or try its visible phase.", True)
                if signal:
                    signal.phase_origin = tick
                return
            presence.sampled.add(signal.id)
            presence.mapping_until = tick+ticks(300)
            self.log(presence, "Signal mapped for five minutes in this descent. No stat bonus or contribution payout.")
        else:
            player.progress.setdefault("lattice_cooldowns", {})["survey"] = self.clock.now_utc().timestamp()+10
            self.game.queue("save", player.bbs_user_id, player, immediate=True)
            if signal and not signal.provoked and signal.signal_phase(tick)[0] == "listening":
                presence.survey_records.add(signal.id)
                self.log(presence, "Signal recorded. Start a three-second hold in sampling.")
            if self.game.progression.modifiers(player).skill(player, "listening") >= 20 or presence.mapping_until > tick:
                known.update(c.id for c in adjacent_hidden(graph.band, presence.room, known))
                self.log(presence, "Survey reveals adjacent hidden branches.")
            else:
                directions = survey_directions(graph.band, presence.room, known)
                self.log(presence, "Hidden signal directions: "+(", ".join(directions) or "none adjacent")+".")

    def runner(self, presence: Presence) -> Runner:
        player = self.game.players[presence.player_id]
        return Runner(player.id, self.location(presence), presence.trace,
            player.attributes.get("resonance", 0), player.archetype, presence.effects,
            presence.trace >= 50 and self.policy(presence) == "corporate")

    def activate(self, ice: Ice, presence: Presence, cause: str) -> None:
        for event in ice.activate(self.runner(presence), self.clock.now_tick(), cause):
            self.event(ice, event)

    def follow(self, presence: Presence) -> None:
        for ice in self.hunters.values():
            ice.follow(presence.player_id, self.location(presence))

    def policy(self, presence: Presence) -> str:
        instance = self.core(presence)
        return instance.graph.spec.trace_policy or "street" if instance else self.lat.sectors.records[presence.sector].trace_policy

    def trace(self, presence: Presence, amount: float, *, fixed: bool = False, entered: bool = False) -> None:
        instance = self.core(presence)
        if (instance and instance.graph.spec.training or self.policy(presence) == "none"
                or self.lat.public(presence)):
            return
        sector = self.lat.sectors.records[presence.sector]
        scope = instance.id if instance else sector.id
        owner = instance.graph.spec.owner if instance else sector.trace_owner or ""
        previous = presence.trace
        presence.trace = min(100, max(0, previous+trace_gain(amount, presence.effects,
            self.clock.now_tick(), fixed=fixed,
            multiplier=self.game.progression.modifiers(self.game.players[presence.player_id]).multiplier("trace_multiplier"))))
        seen = presence.trace_seen.setdefault(scope, set())
        player = self.game.players[presence.player_id]
        for threshold in trace_thresholds(0 if entered else previous, presence.trace, seen):
            policy = self.policy(presence)
            self.log(presence, f"TRACE {threshold}: "+{
                ("civic", 50): "your name enters the Precinct registry for ten minutes.",
                ("civic", 100): "Wardens are dispatched to your body's location.",
                ("corporate", 50): "all defenders in this core wake." if instance else "the district records a trace alert.",
                ("corporate", 100): "a Hound follows your trail for up to three minutes.",
                ("black", 50): "the owner is told someone is inside.",
                ("black", 100): "the owner receives your name and body location for five minutes.",
                ("street", 50): "the owner receives a zone warning.",
                ("street", 100): "forced jack-out, shock 60, five-minute identity lockout.",
                }.get((policy, threshold), "the core records the crossing."), True)
            if policy == "civic":
                if threshold == 50:
                    player.progress["lattice_registry_until"] = self.clock.now_utc().timestamp()+600
                else:
                    self.dispatch(player)
            elif policy == "corporate" and threshold == 100:
                template = self.content.ice["ice_hound"]
                key = scope+":hound:"+player.id
                hunter = Ice.spawn(key, template, self.location(presence), instance.graph.spec.tier if instance else DISTRICT_HUNTER_TIER,
                                   self.clock.now_tick(), instance.graph.spec.affiliation if instance else sector.trace_owner)
                hunter.target = player.id
                self.hunters[key] = hunter
            elif policy in ("black", "street"):
                self.report(player, owner, threshold == 100 and policy == "black")
                if threshold == 100 and policy == "street":
                    self.lat.sources.lock(player.bbs_user_id, presence.core or presence.sector, self.clock.now_utc().timestamp())
                    self.force_out(presence, 60)
            self.game.queue("save", player.bbs_user_id, player, immediate=True)

    def force_out(self, presence: Presence, shock: int = FORCED_SHOCK) -> None:
        actor = self.actor(presence)
        if actor and actor.stance not in ("down", "dead"):
            actor.shock = max(actor.shock, shock)
        session = self.session(presence.player_id)
        if session:
            self.lat.leave(session, transition=False)

    def target(self, presence: Presence, target: str) -> Ice | None:
        return next((ice for ice in self.defenders(presence) if ice.id == target), None)

    def start_cast(self, presence: Presence, pid: str, target: str = "") -> None:
        if pid not in presence.rig or pid not in self.content.programs:
            raise ValueError("Load that program at a terminal or public district cell.")
        if not self.idle(presence):
            raise ValueError("Finish or cancel the current action first.")
        program = self.content.programs[pid]
        if program.effect.params.get("private_vestibule") and not self.lat.interlock.private.apartment(presence.core):
            raise ValueError("Passkey opens only a private delivery vestibule.")
        if program.cast_seconds is None:
            raise ValueError("Ledger works while loaded.")
        player = self.game.players[presence.player_id]
        now, tick = self.clock.now_utc().timestamp(), self.clock.now_tick()
        if player.progress.get("lattice_cooldowns", {}).get(pid, 0) > now:
            raise ValueError("That program is cooling down.")
        if program.id == "prg_residual_fragment" and program.id not in self.game.factions.loan_programs(player):
            raise ValueError("The bound faction loan is no longer eligible.")
        if not can_cast(program, player.archetype, player.progress.get("lattice_charges", {})):
            raise ValueError("That program needs its bound charge or archetype.")
        if "bound_charge" in program.cast_requires and self.commerce.pending:
            raise ValueError("Let your bound-charge transfer settle first.")
        if program.effect.params.get("single_use") and presence.effects.has(pid, tick):
            raise ValueError("That bound effect is already active for this run.")
        target = target or presence.target
        if program.target_class == "ice":
            ice = self.target(presence, target)
            if ice is None:
                raise ValueError("Select a living defender in this room.")
            if program.effect.params.get("hunter_only") and ice.template.behaviour != "hunter":
                raise ValueError("Hunter-Killer only targets hunters.")
        elif program.target_class == "runner":
            other = self.lat.presences.get(target.removesuffix(":presence"))
            if (other is None or self.location(other) != self.location(presence)
                    or self.lat.public(presence) or self.lat.public(other)
                    or not self.combat.permits_indirect(self.actor(presence), self.actor(other))):
                raise ValueError("Both runners and physical bodies must permit burning here.")
            target = other.player_id
        elif program.effect.kind == "area_damage" and not self.defenders(presence):
            raise ValueError("There are no defenders in this room.")
        elif program.effect.kind == "absorb" and not presence.effects.can_replace_shield(program):
            raise ValueError("Your current shield already gives more protection.")
        elif program.effect.kind == "restore" and presence.integrity >= presence.integrity_max:
            raise ValueError("Your integrity is already full.")
        elif pid == "prg_pulse" and not self.lat.crew_of(player.id):
            raise ValueError("You have no crew beacon audience.")
        elif pid == "prg_pulse" and presence.descent:
            raise ValueError("The Silt carries no remote crew beacon. Share the entrance in person.")
        defenders = self.defenders(presence)
        duration = cast_ticks(program, presence.effects, tick,
            tar=any(i.template.class_ == "tar" for i in defenders),
            sandman=any(i.template.class_ == "sandman" for i in defenders))
        presence.effects.consume_next_cast(tick)
        presence.cast = Cast(pid, target, tick+duration, self.location(presence)[0], self.hit_serial(presence))
        base_trace = float(program.trace_cost) if self.policy(presence) != "none" and not self.lat.public(presence) else 0
        self.log(presence, f"{program.name}: {duration/TICK_HZ:g}s cast, {base_trace:g} base trace.")

    def program_state(self, presence: Presence, cast: Cast) -> object:
        """Game 3.5: timer refreshes and bookkeeping are not a new effect."""
        def effects(value: Effects) -> dict[str, Any]:
            return {"active": {key: (effect.kind, effect.amount, effect.params)
                               for key, effect in value.active.items()},
                    "shield": value.shield, "decoy": value.decoy}
        other = self.lat.presences.get(cast.target)
        return deepcopy((presence.integrity, presence.trace, presence.opened, presence.key_tier,
            presence.key_programs, effects(presence.effects), presence.verified_maps, presence.found_silt,
            [(ice.id, ice.integrity, ice.provoked, effects(ice.effects)) for ice in self.defenders(presence)],
            (other.integrity, effects(other.effects)) if other else None))

    def complete_cast(self, presence: Presence, cast: Cast, *, charge_committed: bool = False) -> None:
        program = self.content.programs[cast.program]
        player = self.game.players[presence.player_id]
        tick, now = self.clock.now_tick(), self.clock.now_utc().timestamp()
        kind, params = program.effect.kind, program.effect.params
        if program.id == "prg_residual_fragment" and program.id not in self.game.factions.loan_programs(player):
            raise ValueError("The bound faction loan is no longer eligible.")
        if program.target_class == "runner" and self.commerce.pending:
            presence.cast = cast
            return  # Nothing is charged or Marked before a hit can resolve.
        if "bound_charge" in program.cast_requires and not charge_committed:
            if self.commerce.pending:
                presence.cast = cast
                return
            charges = player.progress.get("lattice_charges", {}).get(program.id, 0)
            if charges <= 0:
                raise ValueError("That bound charge is spent.")
            progress = deepcopy(player.progress)
            progress.setdefault("lattice_charges", {})[program.id] = charges-1
            def finished(success: bool) -> None:
                if (success and self.lat.presences.get(player.id) is presence
                        and self.location(presence)[0] == cast.scope):
                    self.complete_cast(presence, cast, charge_committed=True)
                elif not success:
                    self.log(presence, "The charge could not be saved. It remains unspent.", True)
            self.commerce.settle(player, {"progress": progress}, self.commerce.items,
                                 self.commerce.caches, self.commerce.serial, finished)
            return
        before = self.program_state(presence, cast)
        revealed = deferred_learning = False
        instance = self.core(presence)
        learn = not (instance and instance.graph.spec.training)
        if program.target_class == "runner":
            other_player = self.game.players.get(cast.target)
            crew = self.game.progression.crew_of(player.id)
            learn = bool(learn and other_player and other_player.bbs_user_id != player.bbs_user_id
                and (crew is None or crew != self.game.progression.crew_of(other_player.id))
                and self.game.progression.permit_combat(player.id, other_player.id))
        use = Use("program_change", "programs",
                  f"program:{player.id}:{program.id}:{cast.scope}:{cast.until}:{now}",
                  bool(learn), changed=True)
        if kind == "damage" and program.target_class == "runner":
            other = self.lat.presences.get(cast.target)
            if (other is None or self.location(other) != self.location(presence)
                    or self.lat.public(other) or self.lat.public(presence)
                    or not self.combat.permits_indirect(self.actor(presence), self.actor(other))):
                raise ValueError("That runner can no longer be burned here.")
            self.combat.mark_indirect(self.actor(presence), self.actor(other))
            self.receive(other, IceEvent("hit", player.id, other.player_id, float(program.effect.amount)),
                         name=player.name, player_source=player.id)
        elif kind in ("damage", "area_damage"):
            targets = self.defenders(presence) if kind == "area_damage" else [self.target(presence, cast.target)]
            if not targets or any(i is None for i in targets):
                raise ValueError("That defender is no longer in this room.")
            for ice in targets:
                mods = self.game.progression.modifiers(player)
                amount = attack_damage(program, ice.integrity, mods.attribute(player, "resonance"),
                                       multiplier=1+mods.skill(player, "programs")/200)
                amount, reflected = ice.intercept(amount, player.id, tick,
                    ignore_mirror=bool(params.get("ignore_mirror")),
                    cantillation=bool(params.get("resonance_divisor")))
                if reflected:
                    self.delayed.append(reflected)
                    self.log(presence, f"{ice.template.name} reflects {program.name} in two seconds. Move or shield.", True)
                amount = ice.effects.receive(amount).integrity
                ice.hit(amount, player.id, tick)
                self.activate(ice, presence, "attack")
                self.log(presence, f"{program.name} hits {ice.template.name}: {display_number(amount)}. Integrity {display_number(ice.integrity)}.")
        elif kind == "open_gate" and params.get("private_vestibule"):
            deferred_learning = True
            self.lat.interlock.open_vestibule(presence,
                lambda: self.game.progression.record_use(player.id, use), key_tier=program.tier)
        elif kind == "open_gate":
            gates = [i for i in self.defenders(presence) if i.blocks(now)]
            for ice in gates:
                if (ice.template.class_ == "turnstile" and program.effect.amount >= 1
                        or ice.template.class_ == "lockstep" and program.effect.amount >= 2
                        or params.get("faction") and ice.affiliation == params["faction"]):
                    presence.opened.add(ice.id)
            presence.key_tier = max(presence.key_tier, int(program.effect.amount))
            presence.key_programs.add(program.id)
            if program.duration:
                presence.effects.install(program, tick)
        elif kind == "restore":
            presence.integrity = min(presence.integrity_max, presence.integrity+float(program.effect.amount))
        elif kind == "trace" and program.effect.amount < 0:
            presence.trace = max(0, presence.trace+float(program.effect.amount))
            if params.get("break_hound_once"):
                hunter = next((i for i in self.hunters.values() if i.alive and i.target == player.id), None)
                if hunter:
                    hunter.integrity = 0
                    self.log(presence, "Cutout breaks the Hound's follow.")
        elif kind == "reveal":
            revealed = self.reveal(presence, program)
        else:
            presence.effects.install(program, tick)
        changed = revealed or before != self.program_state(presence, cast)
        if program.cooldown_seconds is not None:
            player.progress.setdefault("lattice_cooldowns", {})[program.id] = now+float(program.cooldown_seconds)
        presence.last_program = program.id
        for ice in self.defenders(presence):
            if ice.template.class_ == "shade":
                ice.copy(program.id, player.id, tick)
                self.log(presence, "Shade copies "+program.name+". Two-second warning.", True)
        self.trace(presence, float(program.trace_cost), fixed=program.id in ("prg_burn", "prg_blackout"))
        self.game.queue("save", player.bbs_user_id, player, immediate=True)
        if learn and changed and not deferred_learning:
            self.game.progression.record_use(player.id, use)

    def reveal(self, presence: Presence, program: ProgramTemplate) -> bool:
        revealed = False
        if presence.descent:
            if program.effect.params.get("crew_beacon"):
                raise ValueError("The Silt carries no remote crew beacon. Share the entrance in person.")
            graph = self.core(presence).graph
            known = presence.found_silt.setdefault(presence.instance, set())
            if program.effect.params.get("adjacent_hidden"):
                known.update(c.id for c in adjacent_hidden(graph.band, presence.room, known))
                self.log(presence, "The adjacent hidden branches resolve.")
            elif program.effect.params.get("true_core_map"):
                presence.verified_maps.add(presence.instance)
                self.log(presence, "Compass verifies the visible map and identifies decoys.")
            return False
        if program.effect.params.get("true_core_map"):
            presence.verified_maps.add(presence.instance or presence.sector)
            self.log(presence, "Compass verifies the authored room map. Suspect labels remain marked.")
        elif program.effect.params.get("crew_beacon"):
            presence.effects.install(program, self.clock.now_tick())
            effect = presence.effects.active[program.id]
            effect.params.update(sector=presence.sector, cell=presence.cell)
            self.log(presence, "Your crew beacon marks this entry for twenty seconds.")
        elif presence.instance:
            self.log(presence, "No hidden room branch is adjacent here.")
        else:
            player = self.game.players[presence.player_id]
            cell = self.lat.sectors.cells[presence.sector][presence.cell]
            for cid in cell.neighbours:
                if self.lat.sectors.cells[presence.sector][cid].access_kind == "hidden":
                    revealed |= self.lat.reveal(player, presence.sector, cid, learn=True)
        return revealed

    def source(self, presence: Presence, data: DataSpec) -> str:
        player = self.game.players[presence.player_id]
        suffix = ":identity:"+player.bbs_user_id if data.scope in ("identity", "mission") else ""
        if data.scope == "mission":
            suffix += ":mission:"+(self.mission_of(player.id, data.id) or "unassigned")
        if presence.descent:
            return f"{self.lat.season}:silt:{self.core(presence).graph.sites[data.id]}{suffix}"
        return f"{self.lat.season}:{presence.core}:{data.id}{suffix}"

    def start_lift(self, presence: Presence, target: str, generation: int) -> None:
        if not self.idle(presence):
            raise ValueError("Finish or cancel the current action first.")
        instance = self.core(presence)
        data = next((d for d in instance.graph.room(presence.room).data if d.id == target), None) if instance else None
        if not data:
            raise ValueError("Choose data in this room.")
        if data.scope == "mission" and not self.mission_of(presence.player_id, data.id):
            raise ValueError("This source requires an active contract objective.")
        player = self.game.players[presence.player_id]
        key = self.source(presence, data)
        acquisition = deepcopy(player.progress)
        for pid in data.programs or ((data.asset,) if data.kind == 'program' else ()):
            learn_program(self.content.programs[pid], acquisition, player.archetype, player.standing,
                          self.lat.season, allow_known=data.kind != 'program')
        if data.scope != "shared" and key in self.game.identity(player.bbs_user_id).get("lattice_receipts", {}):
            raise ValueError("This identity already holds that record.")
        source = self.lat.sources.refresh(key, data, self.clock.now_tick())
        if source.generation != generation or not source.available:
            raise ValueError("Inspect the current source availability before lifting.")
        for ice in self.defenders(presence):
            if ice.template.params.get("shields_data"):
                self.activate(ice, presence, "data")
                raise ValueError(ice.template.name+" shields this data. Break the pane first.")
            if ice.blocks(self.clock.now_utc().timestamp()) and ice.id not in presence.opened:
                self.activate(ice, presence, "data")
                raise ValueError(ice.template.name+" blocks the source. Open or destroy it first.")
            if ice.template.trigger in ("data", "touch"):
                self.activate(ice, presence, "data")
        if data.scope == 'shared':
            self.game.crews.check_data(player.id, self.lat.sources.unit_id(key, generation))
        multiplier = float(self.content.programs["prg_ledger"].effect.params["lift_multiplier"]) if "prg_ledger" in presence.rig else 1
        presence.procedure = Procedure("lift", target, self.clock.now_tick()+ticks(LIFT_SECONDS*multiplier),
                                      self.location(presence)[0], self.hit_serial(presence), generation, key)
        cost = trace_gain(LIFT_TRACE, presence.effects, self.clock.now_tick(),
            multiplier=self.game.progression.modifiers(player).multiplier("trace_multiplier")) if self.policy(presence) != "none" else 0
        self.trace(presence, LIFT_TRACE)
        self.log(presence, f"Lifting {data.label or data.id}: {LIFT_SECONDS*multiplier:g}s, {cost:g} trace on start.")

    def lift(self, presence: Presence, procedure: Procedure) -> None:
        instance = self.core(presence)
        if instance is None:
            return
        data = next(d for d in instance.graph.room(presence.room).data if d.id == procedure.target)
        key, player = self.source(presence, data), self.game.players[presence.player_id]
        if key != procedure.source:
            raise ValueError("The contract or source changed before the lift completed.")
        mission = self.mission_of(player.id, data.id) if data.scope == 'mission' else None
        if data.scope == 'mission' and mission is None:
            raise ValueError('That mission is no longer active.')
        unit_id = self.lat.sources.unit_id(key, procedure.generation)
        offer = self.game.crews.check_data(player.id, unit_id) if data.scope == 'shared' else None
        draft, items = deepcopy(player), deepcopy(self.commerce.items)
        identity = deepcopy(self.game.identity(player.bbs_user_id))
        if data.scope != "shared":
            identity.setdefault("lattice_receipts", {})[key] = unit_id
        serial = self.commerce.serial
        draft.progress.setdefault("lattice_receipts", {})[key] = unit_id
        if mission:
            mission_id, mission_stage, attempt = mission.rsplit(':', 2)
            binding = {'mission': mission_id, 'mission_stage': mission_stage+':'+attempt}
            draft.progress.setdefault('mission_sources', {})[key] = {
                **binding, 'unit': unit_id, 'asset': data.asset}
        if data.kind == "chits":
            draft.chits_hand += data.amount
        elif data.kind in ("salvage_data", "item", "schematic"):
            if data.kind == "schematic":
                known = draft.progress.setdefault("known_schematics", [])
                if data.asset not in known:
                    known.append(data.asset)
            else:
                template = self.content.items[data.asset]
                inventory = Inventory(items, self.content.items, self.game.progression.modifiers(draft).secured_slots)
                remaining = data.amount or 1
                while remaining:
                    serial += 1
                    count = min(remaining, template.stack_max)
                    supplied = make_item(f"{self.game.sessions.origin}:item:{serial}", template,
                                         player.id, self.clock.now_utc().isoformat(), count)
                    if mission:
                        supplied.bound, supplied.secured = True, False
                        supplied.mission, supplied.mission_stage = binding['mission'], binding['mission_stage']
                    inventory.add(draft, supplied)
                    remaining -= count
        elif data.kind in ("contribution", "contract_key", "evidence"):
            draft.progress.setdefault("lattice_units", {})[unit_id] = {
                "kind": data.kind, "asset": data.asset, "amount": data.amount,
                "source": key, "season": self.lat.season, "owner": player.bbs_user_id}
            if mission:
                draft.progress['lattice_units'][unit_id].update(binding)
        elif data.kind == "text":
            draft.progress.setdefault("lattice_records", {})[data.asset or data.id] = unit_id
        for pid in data.programs or ((data.asset,) if data.kind == 'program' else ()):
            learn_program(self.content.programs[pid], draft.progress, draft.archetype, draft.standing,
                          self.lat.season, allow_known=data.kind != 'program')
        reward = None
        grant = None
        if presence.core:
            grant = Grant("run", unit_id, True,
                scope=presence.core, core=presence.core, tier=instance.graph.spec.tier,
                training=instance.graph.spec.training)
            reward = award(draft, identity, grant, self.clock.now_utc(),
                self.game.progression.modifiers(draft))
        # Reserve only after inventory and reward validation succeeds.
        claim = self.lat.sources.propose(key, data, procedure.generation, self.clock.now_tick())
        def finished(success: bool) -> None:
            self.lat.sources.finish(claim, success)
            if success:
                if offer:
                    self.game.crews.registry.commit_offer(offer)
                self.log(presence, "Transfer committed: "+(data.label or data.id)+".")
                self.game.progression.notify_reward(player, reward)
            else:
                self.log(presence, "The transfer could not be saved. The source remains.", True)
        patch = {"progress": draft.progress, "chits_hand": draft.chits_hand,
                 "inventory": draft.inventory, "xp": draft.xp, "grade": draft.grade,
                 "attributes": draft.attributes, "health": draft.health, "legal_at": draft.legal_at}
        if not self.commerce.settle(player, patch, items, self.commerce.caches, serial, finished, identity):
            self.lat.sources.finish(claim, False)
            raise ValueError("The city is settling another transfer. Try again.")
        self.commerce.outbox[-1]["lattice_state"] = lambda: self.lat.sources.record(self.clock.now_tick(), claim)
        if grant and hasattr(self.game, 'crews'):
            self.game.crews.add_rewards(self.commerce.outbox[-1], player, grant)
        if hasattr(self.game, 'contracts'):
            self.game.contracts.lifted(self.commerce.outbox[-1], presence, data, unit_id)

    def receive(self, presence: Presence, event: IceEvent, *, name: str,
                player_source: str = "", reflection: bool = False) -> bool:
        # Defer the entire hit: consuming a shield before a durable player
        # transfer settles could lose damage or clear its consent too early.
        if self.commerce.pending:
            return False
        actor = self.actor(presence)
        if not actor or not actor.zone or actor.stance in ("down", "dead"):
            return True
        instance = self.core(presence)
        training = bool(instance and instance.graph.spec.training)
        if player_source:
            source = self.game.players.get(player_source)
            if not source or not self.combat.permits_indirect(self.combat.actor(source), actor):
                return True
        if self.lat.public(presence) and event.meat:
            return True  # A public district cell is not an NPC black-burn target.
        consent = bool(instance and instance.id in presence.risk_consent and
                       instance.graph.spec.owner_kind not in ("private", "relay"))
        permit = lambda: bool(actor.zone and (self.game.world.zones[actor.zone].allows_hostile(actor.position)
                                or consent and not player_source))
        redirected = presence.effects.decoy > 0 and not reflection
        hit = presence.effects.receive(event.amount, 0 if training or not permit() else event.meat,
            cantillation=event.cantillation, pin_seconds=event.pin, decoy=not reflection)
        presence.integrity = max(1 if training else 0, presence.integrity-hit.integrity)
        if hit.integrity or hit.meat or hit.pin_seconds:
            presence.hit_serial += 1
        if hit.meat:
            self.combat.feedback_hurt(actor, hit.meat, event.source, name, permit)
        if hit.pin_seconds:
            presence.pinned_until = max(presence.pinned_until, self.clock.now_tick()+ticks(hit.pin_seconds))
            ice = self.find_ice(event.source)
            if ice and ice.template.class_ == "bluecoat":
                ice.confirm_pin(presence.player_id, self.clock.now_tick())
        source_ice = self.find_ice(event.source)
        if (source_ice and source_ice.template.class_ == "drift" and not redirected
                and not presence.effects.has("prg_anchor", self.clock.now_tick())):
            self.displace(presence)
        self.log(presence, f"{name}: {display_number(hit.integrity)} integrity, {hit.meat} body damage"+
                 ("; decoy absorbs the hit." if redirected else "."), bool(hit.meat))
        if presence.integrity <= 0:
            self.force_out(presence)
        return True

    def displace(self, presence: Presence) -> None:
        instance = self.core(presence)
        if instance:
            room = instance.graph.room(presence.room)
            if any(i.blocks(self.clock.now_utc().timestamp()) and i.id not in presence.opened
                   for i in self.defenders(presence)):
                return
            choices = list(room.neighbours)
            if presence.descent:
                known = presence.found_silt.get(instance.id, set())
                choices = [rid for rid in choices if not instance.graph.band.cell(rid).hidden or rid in known]
            if not choices:
                return
            presence.room = instance.rng.choice(sorted(choices))
            if presence.descent:
                presence.found_silt.setdefault(instance.id, set()).add(presence.room)
        else:
            player = self.game.players[presence.player_id]
            source = self.lat.sectors.cells[presence.sector][presence.cell]
            from blacksite.server.lattice.sectors import permitted
            choices = [cid for cid in source.neighbours
                if (self.lat.sectors.cells[presence.sector][cid].access_kind != "hidden" or
                    cid in self.lat.found(player, presence.sector)) and
                (not self.lat.public(presence) or self.lat.sectors.cells[presence.sector][cid].access_kind == "public") and
                self.lat.accepts(player, presence, self.lat.sectors.cells[presence.sector][cid], self.lat.sectors.cells[presence.sector][cid].requirement)]
            if not choices:
                return
            presence.cell = sorted(choices)[0]
        presence.room_destination = presence.destination = None
        presence.cast = presence.procedure = None
        self.follow(presence)
        self.log(presence, "Drift displaces you by one legal adjacent link. Anchor prevents this.", True)

    def find_ice(self, iid: str) -> Ice | None:
        return self.hunters.get(iid) or next((i.ice[iid] for i in self.instances.values() if iid in i.ice), None)

    def event(self, ice: Ice, event: IceEvent) -> None:
        presence = self.lat.presences.get(event.target)
        if event.kind == "warning" and presence:
            self.log(presence, f"{ice.template.name}: {ice.template.role}, {event.amount:g}s warning. {ice.template.counter_label}.", True)
        elif event.kind == "hit" and presence:
            if not self.receive(presence, event, name=ice.template.name):
                self.delayed.append(event)
        elif event.kind == "trace" and presence:
            self.trace(presence, event.amount)
        elif event.kind == "report" and presence:
            self.log(presence, "Shiv reports your physical body location.", True)
            self.report(self.game.players[presence.player_id], ice.affiliation or "", True)
        elif event.kind == "dispatch" and presence:
            self.dispatch(self.game.players[presence.player_id])
        elif event.kind == "strip" and presence:
            for key, effect in tuple(presence.effects.active.items()):
                if effect.kind == "stealth":
                    presence.effects.active.pop(key)
        elif event.kind == "heal":
            for instance in self.instances.values():
                for other in instance.ice.values():
                    if other is not ice and other.alive and other.location == ice.location:
                        other.integrity = min(other.maximum, other.integrity+event.amount)
        elif event.kind == "pull" and presence and presence.descent:
            if not presence.effects.has("prg_anchor", self.clock.now_tick()) and presence.depth < 4:
                # Arrival always has a visible riser, and remembers the route
                # back to the band where the pull began.
                presence.return_cells[presence.depth] = presence.room
                self.enter_band(presence, presence.depth+1)
                self.log(presence, "Undertow pulls one band deeper. The riser remains open.", True)
        elif event.kind == "copy" and presence:
            program = self.content.programs[event.program]
            kind = program.effect.kind
            if kind in ("damage", "area_damage"):
                if not program.effect.params.get("hunter_only"):
                    copied = IceEvent("hit", ice.id, presence.player_id, float(program.effect.amount),
                                      location=ice.location, cantillation=bool(program.effect.params.get("resonance_divisor")))
                    if not self.receive(presence, copied, name="Shade / "+program.name):
                        self.delayed.append(copied)
            elif kind in ("absorb", "decoy", "cast_speed", "move_speed", "stealth", "immunity") or kind == "trace" and program.duration:
                if kind != "absorb" or ice.effects.can_replace_shield(program):
                    ice.effects.install(program, self.clock.now_tick())
            elif kind == "restore":
                ice.integrity = min(ice.maximum, ice.integrity+float(program.effect.amount))
            self.log(presence, "Shade echoes "+program.name+" with its original effect kind.", True)

    def pending_hit(self, pid: str) -> bool:
        tick = self.clock.now_tick()
        return any(e.target == pid and (e.at is None or e.at <= tick) for e in self.delayed)

    def flush_hits(self) -> None:
        """Apply due hits at the settlement boundary before more transfers.

        Repeated shop traffic cannot starve an earned hit or erase it at
        an escape deadline. No wall-clock wait enters the simulation.
        """
        tick = self.clock.now_tick()
        delayed, self.delayed = self.delayed, []
        for event in delayed:
            if event.at and tick < event.at:
                self.delayed.append(event)
                continue
            presence, ice = self.lat.presences.get(event.target), self.find_ice(event.source)
            if presence and ice and (event.location is None or event.location == self.location(presence)):
                if not self.receive(presence, event, name=ice.template.name, reflection=event.at is not None):
                    self.delayed.append(event)

    def advance(self, tick: int) -> None:
        utc = self.clock.now_utc().timestamp()
        used_descents = {p.descent for p in self.lat.presences.values() if p.descent}
        for did in tuple(self.descents):
            if did in used_descents or self.game.crews.retains_silt(did, tick):
                self.empty_descents.pop(did, None)
            else:
                since = self.empty_descents.setdefault(did, tick)
                if tick-since >= ticks(CORE_IDLE_RESET_SECONDS):
                    self.descents.pop(did)
                    self.empty_descents.pop(did)
                    self.instances = {iid: instance for iid, instance in self.instances.items()
                                      if not isinstance(instance.graph, BandGraph) or instance.graph.descent.id != did}
        active_instances = {p.instance for p in self.lat.presences.values() if p.instance}
        for iid, instance in self.instances.items():
            if iid in active_instances:
                instance.empty_since = None
            elif instance.empty_since is None:
                instance.empty_since = tick
        for presence in tuple(self.lat.presences.values()):
            actor = self.actor(presence)
            if not actor or actor.stance != "jacked":
                continue
            presence.effects.expire(tick)
            if presence.room_destination and tick >= presence.move_until:
                presence.room, presence.room_destination = presence.room_destination, None
                if hasattr(self.game, 'contracts'):
                    self.game.contracts.entered(presence)
                if presence.descent:
                    known = presence.found_silt.setdefault(presence.instance, set())
                    known.add(presence.room)
                    if presence.mapping_until > tick:
                        known.update(c.id for c in adjacent_hidden(self.core(presence).graph.band, presence.room, known))
                presence.target = ""
                self.lat.sense_hidden(presence)
                if presence.redline_move:
                    presence.integrity = max(0, presence.integrity-5)
                self.follow(presence)
                if presence.integrity <= 0:
                    self.force_out(presence)
                    continue
            instance = self.core(presence)
            if instance:
                self.trace(presence, TRACE_PER_SECOND[instance.graph.spec.tier]/TICK_HZ)
        runners = {p.player_id: self.runner(p) for p in self.lat.presences.values()
                   if self.actor(p) and self.actor(p).stance == "jacked"}
        neighbours = {(i.id, room.id): tuple((i.id, rid) for rid in room.neighbours)
                      for i in self.instances.values() for room in i.graph.rooms.values()}
        for instance in self.instances.values():
            if instance.id not in active_instances:
                continue
            if isinstance(instance.graph, CoreGraph):
                for room in instance.graph.rooms.values():
                    for index, template_id in enumerate(room.ice):
                        required = room.ice_events.get(template_id)
                        if required:
                            iid = f"{instance.id}:{room.id}:{index}"
                            if required not in self.lat.events:
                                instance.ice.pop(iid, None)
                            elif iid not in instance.ice:
                                ice = Ice.spawn(iid, self.content.ice[template_id], (instance.id, room.id),
                                    instance.graph.spec.tier, tick, instance.graph.spec.affiliation)
                                if ice.template.behaviour == "roaming" and ice.template.class_ != "drift":
                                    route = room.ice_patrols.get(template_id) or instance.graph.patrol(room.id)
                                    ice.patrol = tuple((instance.id, rid) for rid in route)
                                    ice.patrol_index = route.index(room.id)
                                instance.ice[iid] = ice
            for ice in instance.ice.values():
                for event in ice.advance(tick, utc, runners, neighbours, instance.rng):
                    self.event(ice, event)
        for ice in self.hunters.values():
            for event in ice.advance(tick, utc, runners, neighbours, Random(0)):
                self.event(ice, event)
        self.hunters = {key: ice for key, ice in self.hunters.items() if ice.alive}
        self.flush_hits()
        for presence in tuple(self.lat.presences.values()):
            cast, procedure = presence.cast, presence.procedure
            current = self.hit_serial(presence)
            if cast and (cast.scope != self.location(presence)[0] or cast.last_hit != current):
                presence.cast = None
                self.log(presence, "Your program cast is interrupted.", True)
            elif cast and tick >= cast.until:
                presence.cast = None
                try:
                    self.complete_cast(presence, cast)
                except ValueError as exc:
                    self.log(presence, str(exc), True)
            if procedure and (procedure.scope != self.location(presence)[0] or procedure.last_hit != current):
                presence.procedure = None
                self.log(presence, "Your transfer is interrupted. Nothing changes hands.", True)
            elif procedure and tick >= procedure.until and not self.commerce.pending:
                presence.procedure = None
                try:
                    if procedure.kind == "flip":
                        self.lat.interlock.complete_flip(presence, procedure)
                    elif procedure.kind == 'plant':
                        self.finish_contract_plant(presence, procedure)
                    elif procedure.kind == "theft":
                        self.lat.interlock.private.complete_theft(presence, procedure)
                    elif procedure.kind in ("survey", "sample"):
                        self.complete_survey(presence, procedure)
                    elif procedure.kind == "decoy":
                        self.log(presence, "The suspect route ends without data. Compass distinguishes this decoy.", True)
                    else:
                        self.lift(presence, procedure)
                except ValueError as exc:
                    self.log(presence, str(exc), True)

    def rows(self, presence: Presence, screen: EncounterMenu) -> list[dict[str, Any]]:
        player = self.game.players[presence.player_id]
        if screen.kind == "record":
            text = self.content.text[screen.target]
            return [{"id": str(index), "cells": [line]} for index, line in enumerate(text.body.splitlines()) if line]
        if screen.kind == "evidence":
            evidence = self.content.evidence[screen.target]
            values = ["OBSERVATION: "+evidence.observation, "SOURCE: "+evidence.source,
                      "SOURCE CLAIM: "+evidence.claim, *self.content.text[evidence.asset].body.splitlines()]
            return [{"id": str(index), "cells": [line]} for index, line in enumerate(values) if line]
        if screen.kind == "rig":
            occupied = occupied_slots(presence.rig, self.content.programs)
            return [{"id": str(index), "cells": [str(index+1), self.content.programs[pid].name if pid else
                    "Reserved" if index in occupied else "Empty"]} for index, pid in enumerate(presence.rig)]
        if screen.kind == "binding":
            known = self.known_programs(player)
            return [{"id": "", "cells": ["Unload"]}] + [{"id": pid, "cells": [self.content.programs[pid].name,
                    str(self.content.programs[pid].slots)+" slots"]} for pid in sorted(known)]
        instance = self.core(presence)
        if not instance:
            cell = self.lat.sectors.cells[presence.sector][presence.cell]
            core_id = cell.core_id
            if not core_id and self.can_enter(presence, "lat-wake-hall"):
                core_id = "lat-wake-hall"
            if cell.kind == "descent":
                return [{"id": "descend", "cells": ["Descend with NPC risk", "BLACK ICE can injure body"]},
                        {"id": "survey", "cells": ["Survey", "3s / 10s cooldown"]}]
            return ([{"id": "enter:"+core_id, "cells": ["Enter "+self.content.cores[core_id].name]},
                     {"id": "risk:"+core_id, "cells": ["Enter with NPC risk", "BLACK ICE may injure body"]}]
                    if core_id else []) + [{"id": "survey", "cells": ["Survey", "3s / 10s cooldown"]}]
        room = instance.graph.room(presence.room)
        rows = self.contract_rows(presence)+[{"id": "ice:"+i.id, "cells": [i.template.name, f"{display_number(i.integrity)} integrity", i.phase]}
                for i in self.defenders(presence)]
        for ice in self.defenders(presence):
            if ice.template.class_ == "liar" and instance.id not in presence.verified_maps:
                rows.append({"id": "bait:"+ice.id, "cells": ["UNVERIFIED data room", "suspect", "10s dead end / 15 trace"]})
        rows += [self.lat.interlock.control_row(presence.core, control) for control in room.controls]
        rows += self.lat.interlock.private.rows(presence)
        if presence.descent:
            rows += [{"id": "survey", "cells": ["Survey", "3s / 10s cooldown"]},
                     {"id": "sample", "cells": ["Hold sample", "3s during sampling"]}]
            if presence.room in instance.graph.band.sinks:
                rows.append({"id": "descend", "cells": ["Descend to next band"]})
        elif room.descent:
            rows.append({"id": "descend", "cells": ["Descend with NPC risk", "BLACK ICE can injure body"]})
        for data in room.data:
            source = self.lat.sources.refresh(self.source(presence, data), data, self.clock.now_tick())
            done = data.scope != "shared" and self.source(presence, data) in self.game.identity(player.bbs_user_id).get("lattice_receipts", {})
            read = done and data.kind == "text" and data.asset in self.content.text
            evidence = done and data.kind == "evidence" and data.asset in self.content.evidence
            locked = data.scope == "mission" and not self.mission_of(player.id, data.id)
            rows.append({"id": "read:"+data.asset if read else "evidence:"+data.asset if evidence else f"lift:{data.id}:{source.generation}", "cells": [data.label or data.id,
                f"{data.amount} chits" if data.kind == "chits" else data.kind,
                "needs contract" if locked else "recorded" if done else "ready" if source.available else "replenishing"]})
            offer = self.lat.sources.crew_offers.get(self.lat.sources.unit_id(self.source(presence, data), source.generation), {})
            turn = self.game.crews.offer_label(offer)
            if turn:
                rows[-1]['cells'].append(turn)
        return rows

    def select(self, session: Session, presence: Presence, row: str) -> None:
        screen = self.menus[session.id]
        if screen.kind in ("record", "evidence"):
            return
        if screen.kind == "rig":
            screen.kind, screen.slot, screen.cursor = "binding", int(row), 0
            return
        if screen.kind == "binding":
            if not self.idle(presence) or presence.instance or not self.lat.public(presence):
                raise ValueError("Load programs only while idle in a public district cell.")
            player = self.game.players[presence.player_id]
            known = self.known_programs(player)
            presence.rig = bind(presence.rig, screen.slot, row or None, known, self.content.programs)
            player.rig["slots"] = list(presence.rig)
            self.game.queue("save", player.bbs_user_id, player, immediate=True)
            screen.kind, screen.cursor = "rig", screen.slot
            return
        if row.startswith("ice:"):
            presence.target = row[4:]
            ice = self.target(presence, presence.target)
            if ice:
                self.log(presence, f"{ice.template.name}: {ice.template.role}, trigger {ice.template.trigger}, "
                    f"{display_number(ice.template.attack)} integrity / {ice.template.meat_damage} body damage; {ice.template.counter_label}.")
        elif row.startswith(("enter:", "risk:")):
            self.enter(session, row.split(":", 1)[1], row.startswith("risk:"))
        elif row.startswith("theft:"):
            self.lat.interlock.private.start_theft(presence, row[6:])
        elif row.startswith("lift:"):
            _, target, generation = row.split(":")
            self.start_lift(presence, target, int(generation))
        elif row.startswith('plant:'):
            self.start_contract_plant(presence, row[6:])
        elif row == "descend":
            self.descend(session, risk=True)
        elif row in ("survey", "sample"):
            self.survey(presence, row == "sample")
        elif row.startswith("read:"):
            data = next(d for d in self.core(presence).graph.room(presence.room).data if d.asset == row[5:])
            self.menus[session.id] = EncounterMenu("record", target=row[5:], label=data.label or data.id)
            return
        elif row.startswith("evidence:"):
            data = next(d for d in self.core(presence).graph.room(presence.room).data if d.asset == row[9:])
            self.menus[session.id] = EncounterMenu("evidence", target=row[9:], label=data.label or data.id)
            return
        elif row.startswith("bait:"):
            ice = self.target(presence, row[5:])
            if (not ice or ice.template.class_ != "liar" or not self.idle(presence)
                    or presence.instance in presence.verified_maps):
                raise ValueError("That suspect route is no longer available.")
            presence.procedure = Procedure("decoy", ice.id, self.clock.now_tick()+ticks(10),
                self.location(presence)[0], self.hit_serial(presence))
            self.trace(presence, 15)
            self.log(presence, "You follow an unverified route. Esc withdraws; spent trace remains.", True)
        elif row.startswith("control:"):
            self.lat.interlock.start_flip(presence, row[8:])
        self.menus.pop(session.id, None)

    def input(self, session: Session, presence: Presence, name: str, action: str,
              key: str, args: dict[str, Any], revision: int | None) -> bool:
        screen = self.menus.get(session.id)
        if screen:
            rows = self.rows(presence, screen)
            if name == "menu_close" or key in ("escape", "b", "B"):
                self.menus.pop(session.id)
            elif name == "menu_cursor" and type(args.get("delta")) is int:
                screen.cursor = max(0, min(screen.cursor+args["delta"], len(rows)-1))
            elif name == "menu_select" and revision == session.view_revision and rows:
                row = args.get("row") or rows[screen.cursor]["id"]
                if any(r["id"] == row for r in rows):
                    self.select(session, presence, row)
            return True
        if (key in ("b", "B") or name == "menu_close") and (presence.cast or presence.procedure or presence.destination or presence.room_destination):
            presence.cast = presence.procedure = None
            presence.destination = presence.room_destination = None
            return True
        if name == "lat.enter":
            cell = self.lat.sectors.cells[presence.sector][presence.cell]
            self.enter(session, args.get("core", cell.core_id or "lat-wake-hall"), args.get("risk") is True)
        elif name == "lat.room":
            self.move(presence, args.get("room", ""))
        elif name == "lat.leave" or (name == "menu_close" or key in ("b", "B")) and presence.instance:
            self.leave_core(session)
        elif name == "lat.theft":
            self.lat.interlock.private.start_theft(presence, args.get("item", ""))
        elif name == "lat.flip":
            self.lat.interlock.start_flip(presence, args.get("control", ""))
        elif name == "lat.lift":
            if type(args.get("generation")) is not int:
                raise ValueError("Inspect a source and use its displayed generation.")
            self.start_lift(presence, args.get("target", ""), args["generation"])
        elif name == "lat.descend":
            self.descend(session, args.get("risk") is True)
        elif name in ("lat.survey", "lat.sample"):
            self.survey(presence, name == "lat.sample")
        elif name == "lat.cast" or key in tuple("1234567") or action.startswith("program_"):
            slot = int(key)-1 if key in tuple("1234567") else int(action[8:])-1 if action.startswith("program_") else None
            pid = presence.rig[slot] if slot is not None and 0 <= slot < len(presence.rig) else args.get("program", "")
            self.start_cast(presence, pid, args.get("target", ""))
        elif name == "lat.target" or key in ("tab", "shift-tab") or action in ("target_next", "target_prev"):
            ids = [i.id for i in self.defenders(presence)]
            ids += [other.player_id for other in self.runner_targets(presence)]
            if key in ("tab", "shift-tab") or action in ("target_next", "target_prev"):
                step = -1 if key == "shift-tab" or action == "target_prev" else 1
                presence.target = (ids[(ids.index(presence.target)+step) % len(ids)]
                    if presence.target in ids else next(iter(ids if step > 0 else ids[::-1]), ""))
            elif args.get("target") in ids:
                presence.target = args["target"]
        elif name == "lat.rig" or action == "rig" or key in ("r", "R"):
            self.menus[session.id] = EncounterMenu("rig")
        elif name == "lat.cancel" or key == "escape":
            presence.cast = presence.procedure = None
            presence.destination = presence.room_destination = None
        elif action == "interact" or key in ("e", "E"):
            self.inspect_contract(presence)
            cell = self.lat.sectors.cells[presence.sector][presence.cell]
            if presence.instance or cell.core_id or cell.kind == "descent" or self.can_enter(presence, "lat-wake-hall"):
                self.menus[session.id] = EncounterMenu("room")
            else:
                return False
        elif presence.instance and (action.startswith("move_") or name == "move"):
            from blacksite.server.world.movement import direction
            instance = self.core(presence)
            source = instance.graph.room(presence.room)
            vector = direction(action[5:] if action.startswith("move_") else args.get("dir", ""))
            target = directional_neighbour(source.pos, {rid: instance.graph.room(rid).pos for rid in source.neighbours}, vector) if vector else None
            if target:
                self.move(presence, target)
        else:
            return False
        return True

    def view(self, session: Session, presence: Presence, body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        instance = self.core(presence)
        tick = self.clock.now_tick()
        player = self.game.players[presence.player_id]
        body["scope"] = self.location(presence)[0]
        body["beacons"] = []
        crew = self.lat.crew_of(player.id)
        if crew and not presence.instance:
            for other in self.lat.presences.values():
                if self.lat.crew_of(other.player_id) != crew or not other.effects.has("prg_pulse", tick):
                    continue
                effect = other.effects.active["prg_pulse"]
                if effect.params.get("sector") == presence.sector:
                    body["beacons"].append({"player": other.player_id,
                        "name": self.game.players[other.player_id].name, "cell": effect.params["cell"]})
        body["me"]["target"] = presence.target
        runner = next((other for other in self.runner_targets(presence)
                       if other.player_id == presence.target), None)
        body["runner_target"] = ({"id": runner.player_id,
            "name": self.game.players[runner.player_id].name,
            "integrity_percent": ceil(100*runner.integrity/runner.integrity_max),
            "burn_allowed": bool(not self.lat.public(presence) and not self.lat.public(runner)
                and self.combat.permits_indirect(self.actor(presence), self.actor(runner)))} if runner else None)
        shield = presence.effects.shield
        body["me"]["shield"] = ({"name": self.content.programs[shield.program].name,
            "budget": shield.budget, "pin_once": shield.pin_once, "black_meat_once": shield.black_meat_once}
            if shield else None)
        body["me"]["decoy"] = presence.effects.decoy
        body["me"]["effects"] = [{"name": self.content.programs[key].name,
            "seconds": max(0, effect.until-tick)/TICK_HZ if effect.until is not None else None}
            for key, effect in presence.effects.active.items() if presence.effects.has(key, tick)]
        body["me"]["cast"] = ({"name": self.content.programs[presence.cast.program].name,
             "ticks": max(0, presence.cast.until-tick)} if presence.cast else
             {"name": presence.procedure.kind.title(), "ticks": max(0, presence.procedure.until-tick)} if presence.procedure else None)
        body["me"]["hit_serial"] = self.hit_serial(presence)
        occupied = occupied_slots(presence.rig, self.content.programs)
        for row in body["me"]["rig"]:
            row["cd"] = max(0, player.progress.get("lattice_cooldowns", {}).get(row["program"], 0)-self.clock.now_utc().timestamp())
            slot = row["slot"]-1
            if row["program"] is None and slot in occupied:
                row["name"] = f"Reserved by {occupied[slot]+1}"
        if instance:
            graph = instance.graph
            body.update(title=graph.spec.name.upper()+" / CORE", layout_size=[8, 4],
                label=graph.room(presence.room).label,
                hint=self.lat.jack_key(session)+" escape  B retreat  E room  Tab target  1-7 cast  R rig")
            body["cells"] = [{"id": room.id, "x": room.pos[0], "y": room.pos[1], "kind": "room",
                "label": room.label} for room in graph.rooms.values()]
            body["edges"] = [{"a": room.id, "b": other, "kind": "public"}
                for room in graph.rooms.values() for other in room.neighbours if room.id < other]
            body["me"]["cell"] = presence.room
            body["presences"] = [{**row, "cell": self.lat.presences[row["id"].removesuffix(":presence")].room}
                for row in body["presences"]]
            body["room"] = [{"id": ice.id, "name": ice.template.name, "role": ice.template.role,
                "trigger": ice.template.trigger, "phase": ice.phase, "integrity": ice.integrity,
                "maximum": ice.maximum, "target": ice.target, "counter": ice.template.counter_label,
                "damage": ice.attack, "meat": ice.meat_damage,
                "warning_ticks": max(0, ice.activations[player.id].warned-tick) if player.id in ice.activations and ice.template.class_ != "sweeper" else 0,
                "cooldown_ticks": max(0, ice.next_attack-tick)} for ice in self.defenders(presence)]
            body["black_risk"] = instance.id in presence.risk_consent
            if (any(i.template.class_ == "liar" for i in self.defenders(presence))
                    and instance.id not in presence.verified_maps):
                alternatives = [room.label for room in graph.rooms.values() if room.id != presence.room]
                if alternatives:
                    index = int.from_bytes(blake2b(presence.room.encode(), digest_size=2).digest(), "big") % len(alternatives)
                    body["label"] = "SUSPECT: "+alternatives[index]
                    body["observation_label"] = graph.room(presence.room).label
            body["sweep_warnings"] = [{"cell": ice.patrol[(ice.patrol_index+1) % len(ice.patrol)][1],
                "ticks": max(0, ice.next_move-tick)} for ice in instance.ice.values()
                if ice.alive and ice.template.class_ == "sweeper" and ice.patrol and not ice.sweep_occupies_until]
            if presence.descent:
                known = presence.found_silt.get(instance.id, set())
                visible = {c.id for c in graph.band.cells if not c.hidden or c.id in known}
                body["cells"] = [c for c in body["cells"] if c["id"] in visible]
                for cell in body["cells"]:
                    cell["kind"] = graph.band.cell(cell["id"]).role
                body["edges"] = [e for e in body["edges"] if e["a"] in visible and e["b"] in visible]
                body.update(title="SILT / "+graph.spec.name.upper(), layout_size=[5, 4],
                    hint=self.lat.jack_key(session)+" escape  B rise  E survey/sample/lift  Arrows links")
                for row in body["room"]:
                    ice = self.find_ice(row["id"])
                    if ice.template.class_ == "chorister" and not ice.provoked:
                        phase, remaining = ice.signal_phase(tick)
                        row["phase"] = f"{phase} {remaining/TICK_HZ:.1f}s"
            room = graph.room(presence.room)
            data_rows = []
            for data in room.data:
                key = self.source(presence, data)
                source = self.lat.sources.refresh(key, data, tick)
                recorded = data.scope != "shared" and key in self.game.identity(player.bbs_user_id).get("lattice_receipts", {})
                data_rows.append({"id": data.id, "label": data.label or data.id, "kind": data.kind,
                    "amount": data.amount, "generation": source.generation,
                    "available": source.available and not recorded,
                    "recorded": recorded, "scope": data.scope,
                    "requires_contract": data.scope == "mission" and not self.mission_of(player.id, data.id),
                    "cast_seconds": LIFT_SECONDS*(float(self.content.programs["prg_ledger"].effect.params["lift_multiplier"]) if "prg_ledger" in presence.rig else 1),
                    "trace_cost": 0 if self.policy(presence) == "none" else LIFT_TRACE})
            body["room"] = {"id": room.id, "label": room.label, "ice": body["room"], "data": data_rows,
                "controls": [{"id": c.id, "label": c.label, "action": c.action,
                    "target": {"zone": c.target.zone, "object": c.target.object},
                    "reset_seconds": c.reset_seconds, "scope": c.scope,
                    "permission": c.permission, "cast_seconds": LIFT_SECONDS,
                    **self.lat.interlock.control_view(presence.core, c)} for c in room.controls]}
        screen = self.menus.get(session.id)
        if screen:
            rows = self.rows(presence, screen)
            screen.cursor = min(screen.cursor, max(0, len(rows)-1))
            detail = "Programs load only while idle in a public district cell. Cooldowns survive rebinding."
            if screen.kind in ("rig", "binding") and rows:
                selected = rows[screen.cursor]['id']
                pid = presence.rig[int(selected)] if screen.kind == "rig" else selected
                program = self.content.programs.get(pid)
                if program:
                    detail = (program.name+": "+program.description+"\n"+
                        f"Slots {program.slots}; cast {program.cast_seconds if program.cast_seconds is not None else 'passive'}s; "
                        f"cooldown {program.cooldown_seconds if program.cooldown_seconds is not None else 'single use'}s.")
            if screen.kind == "room":
                detail = "Select ICE to inspect and target. Select data to start a three-second lift."
                if rows and rows[screen.cursor]['cells'][-1].startswith('Crew turn:'):
                    detail = rows[screen.cursor]['cells'][-1]+'\n'+detail
            title = "ROOM" if screen.kind == "room" else "RIG"
            if screen.kind in ("record", "evidence"):
                title = (screen.label or screen.target.replace("-", " ")).upper()
                detail = rows[screen.cursor]["cells"][0] if rows else "No text."
            stats = f"HP {body['me']['body_hp']}/{body['me']['body_hp_max']}  INT {display_number(presence.integrity)}  TRACE {presence.trace:g}"
            if shield:
                stats += f"  SHIELD {shield.budget:g}"
            if presence.effects.decoy:
                stats += f"  DECOY {presence.effects.decoy:g}"
            if body.get('black_risk'):
                title = 'BLACK ICE / BODY RISK / '+title
            columns = screen_layout(session.caps['width'], session.caps['height']).encounter_width
            detail = stats+'\n'+'\n'.join(wrapped(detail, columns))
            result = menu(title, rows, screen.cursor, detail,
                          self.lat.jack_key(session)+" escape  Esc/B returns without acting")
            result.update(me=body['me'], scope=body['scope'], sector=body['sector'],
                          black_risk=body.get('black_risk', False), jack_key=self.lat.jack_key(session).lower())
            return "menu", result
        return "lattice", body

    def leave(self, presence: Presence) -> None:
        presence.cast = presence.procedure = None
        session = self.session(presence.player_id)
        if session:
            self.menus.pop(session.id, None)
