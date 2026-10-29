"""S20 adapter: recruitment, durable membership and faction services."""

from blacksite.server.interaction import Focus, Interaction, interact, object_interaction
from blacksite.server.views import presentation
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from blacksite.server import factions as rules
from blacksite.server.clock import TICK_HZ
from blacksite.server.loop import TickContext
from blacksite.server.players import Player
from blacksite.server.progression_engine import ProgressionEngine
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session
from blacksite.server.wake import menu
from blacksite.server.world.simulation import MENU_TIMEOUT_SECONDS


@dataclass
class FactionMenu:
    target: str
    cursor: int
    opened: int
    confirm: str = ""
    pitch: bool = False
    vat: bool = False
    vat_cursor: int = 0


class Factions:
    def __init__(self, progression: ProgressionEngine) -> None:
        self.progression, self.game = progression, progression.game
        self.commerce, self.content, self.clock = progression.commerce, progression.content, progression.clock
        self.sim, self.world, self.lat = progression.sim, self.game.world, progression.lattice
        self.game.factions = self
        self.menus: dict[str, FactionMenu] = {}
        self.requests: dict[str, list[str]] = {}
        self.notices: dict[tuple[str, str], int] = {}
        # S21 freezes due rent before a membership eligibility change.
        self.before_membership_change: Callable[[Player], bool] = lambda player: True
        self.curfew: Callable[[str], bool] = lambda zone: False  # S24.
        self.preview: Callable[[Player, str], rules.EventOffer | None] = lambda player, kind: None  # S24.
        self.lat.interlock.cut_patch = self.cut_patch
        for player in self.game.players.values():
            self.clear_loan(player)
            if rules.normalize_card_standing(player, self.content.wake_cards):
                self.game.queue("save", player.bbs_user_id, player, immediate=True)
        attached = self.game.attached
        def on_attach(session: Session, player: Player) -> None:
            attached(session, player)
            self.refresh(player)
        self.game.attached = on_attach

    def ready(self, session: Session) -> Player:
        if not self.commerce.ready(session):
            raise ValueError("Return to your body before contacting a recruiter.")
        return self.game.players[session.player_id]

    def site(self, faction: str) -> Any:
        return next((site for sid, site in self.content.faction_sites.items()
                     if site.faction == faction and self.content.active("faction_sites", sid)), None)

    def card(self, faction: str) -> Any:
        return next((card for card in self.content.wake_cards.values()
                     if (card.faction or card.id) == faction), None)

    def refresh(self, player: Player) -> None:
        if not rules.perk(player, "unmoored"):
            self.clear_loan(player)
        for actor in self.world.actors.values():
            if actor.id == player.id or actor.behaviour.get("player_drone") and actor.owner == player.id:
                if actor.faction != player.faction:
                    actor.faction = player.faction
                    if actor.zone:
                        self.world.zones[actor.zone].revision += 1

    def log(self, player: Player, text: str) -> None:
        session = self.game.combat.session(player.id)
        if session:
            self.sim.log(session, text)
            self.commerce.toast(session, text)

    def standing_patch(self, player: Player, changes: dict[str, int],
                       mode: str = "propagate") -> dict[str, Any]:
        """Source owners include this in their receipt, never a later payment."""
        draft = deepcopy(player)
        rules.apply_vector(draft, self.content.factions, changes, mode)
        return {"standing": draft.standing} if draft.standing != player.standing else {}

    def cut_patch(self, player: Player, core: str) -> dict[str, Any]:
        if self.lat.interlock.permit(player.id, core, "cut"):
            return {}
        owner = self.lat.interlock.owned(core) or self.content.cores[core].affiliation
        return self.standing_patch(player, {owner: rules.CUT_STANDING}, "explicit") if owner in self.content.factions else {}

    def notify_standing(self, player: Player, before: dict[str, int], reason: str) -> None:
        for fid, value in player.standing.items():
            delta = value-before.get(fid, 0)
            key = player.id, fid
            if delta and self.clock.now_tick() >= self.notices.get(key, 0):
                self.notices[key] = self.clock.now_tick()+10*TICK_HZ
                self.log(player, f"{self.content.factions[fid].short} {delta:+d} ({value:+d}): {reason}.")

    def status_of(self, session: Session) -> str:
        player = self.game.players.get(session.player_id)
        if not player:
            return ""
        for label, until in (("Marked", player.marked_until), ("Heat", player.warden_heat_until)):
            if until:
                remaining = max(0, int((datetime.fromisoformat(until)-self.clock.now_utc()).total_seconds()))
                if remaining:
                    return f"{label} {remaining//60:02d}:{remaining%60:02d}"
        return ""

    def rank_of(self, session: Session) -> str:
        player = self.game.players.get(session.player_id)
        return rules.rank(player, self.content.factions) if player else ""

    def inspector_location(self, viewer: Session, target: Session) -> str | None:
        player = self.game.players.get(viewer.player_id)
        other = self.game.players.get(target.player_id)
        if not player or not other or not rules.perk(player, "wardens"):
            return None
        actor = self.game.combat.actor(other)
        if (actor and actor.zone and other.marked_until
                and datetime.fromisoformat(other.marked_until) > self.clock.now_utc()):
            return "MARKED "+self.world.zones[actor.zone].template.meta.name
        return None

    def vats(self, player: Player) -> dict[str, Any]:
        visited = player.progress.get("reward_receipts", {})
        return {site.faction: site.vat for sid, site in self.content.faction_sites.items()
                if self.content.active("faction_sites", sid) and site.vat
                and (site.faction == player.faction or "zone_discovery:"+site.vat.zone in visited)}

    def vat(self, player: Player) -> tuple[str, tuple[int, int]] | None:
        chosen = player.progress.get("faction_vat")
        if chosen and rules.perk(player, "sablier") and chosen in self.vats(player):
            location = self.vats(player)[chosen]
        else:
            if player.progress.get("faction_respawn") != "hall":
                return None
            site = self.site(player.faction) if player.faction else None
            definition = self.content.factions.get(player.faction)
            location = site.vat if site else definition.vat if definition else None
        if location and location.zone in self.world.zones:
            return location.zone, self.world.free_tile(location.zone, location.tile)
        return None

    def modifier_layers(self, player: Player) -> tuple[dict[str, float], ...]:
        presence = self.lat.presences.get(player.id)
        effect = presence.effects.active.get("prg_residual_fragment") if presence else None
        return ({"programs": effect.amount},) if effect and self.loan_programs(player) else ()

    def loan_programs(self, player: Player) -> set[str]:
        return {"prg_residual_fragment"} if rules.perk(player, "unmoored") and player.progress.get("faction_loan") else set()

    def clear_loan(self, player: Player) -> None:
        """Called on jack-out or loss of eligibility; never remove learned programs."""
        if not player.progress.pop("faction_loan", False):
            return
        player.progress.get("lattice_charges", {}).pop("prg_residual_fragment", None)
        player.rig["slots"] = [pid if pid != "prg_residual_fragment" else None for pid in player.rig.get("slots", [])]
        presence = self.lat.presences.get(player.id)
        if presence:
            presence.rig = tuple(pid if pid != "prg_residual_fragment" else None for pid in presence.rig)
            presence.effects.active.pop("prg_residual_fragment", None)
            if presence.cast and presence.cast.program == "prg_residual_fragment":
                presence.cast = None
        self.game.queue("save", player.bbs_user_id, player, immediate=True)

    def containment_fee(self, player: Player, identity: dict[str, Any]) -> int:
        # Game 7.6: waive the service only, never the consumable's 1500 price.
        return 0 if rules.perk(player, "halvard") and rules.claim_daily(identity, "halvard-service", self.clock.now_utc()) else rules.CONTAINMENT_SERVICE_FEE

    def rotating(self, vendor: Any, item: str) -> bool:
        fixed = {row.item for row in vendor.stock}
        fixed.update(self.content.items[row.item].weapon.ammo for row in vendor.stock
                     if row.item in self.content.items and self.content.items[row.item].weapon)
        template = self.content.items.get(item)
        return bool(vendor.daily_rotation and item not in fixed and template
                    and template.class_ in ("weapon", "armour", "gear") and not template.no_vendor_sale
                    and not item.startswith("story_") and item in {row.item for row in self.commerce.stock(vendor)})

    def reservation(self, counter: str, item: str) -> Player | None:
        now = self.clock.now_utc().timestamp()
        return next((player for player in self.game.players.values()
                     if rules.perk(player, "sable") and (hold := player.progress.get("faction_reservation", {}))
                     and hold.get("counter") == counter and hold.get("item") == item and hold.get("until", 0) > now), None)

    def stock_available(self, player: Player, vendor: Any, counter: str, item: str) -> bool:
        if not self.rotating(vendor, item):
            return True
        holder = self.reservation(counter, item)
        return holder is None or holder.id == player.id

    def reserve_stock(self, session: Session, target: str, item: str) -> None:
        player = self.ready(session)
        vendor, counter = self.commerce.vendor(session, target)
        if not rules.perk(player, "sable") or vendor.faction != "sable" or not self.rotating(vendor, item):
            raise ValueError("Reserve only optional rotating Sable stock at +90 membership.")
        if self.reservation(counter, item):
            raise ValueError("That item is already reserved. Fixed public stock stays available.")
        identity = deepcopy(self.game.identities[player.bbs_user_id])
        if not rules.claim_daily(identity, "sable-reservation", self.clock.now_utc()):
            raise ValueError("Today's reservation is already used.")
        progress = deepcopy(player.progress)
        progress["faction_reservation"] = {"counter": counter, "item": item,
                                           "until": self.clock.now_utc().timestamp()+rules.SABLE_RESERVATION_SECONDS}
        self.commerce.settle(player, {"progress": progress}, self.commerce.items, self.commerce.caches,
            self.commerce.serial, lambda success: self.log(player, "Optional stock reserved for ten minutes."
                if success else "The reservation could not be saved. Today's use is unspent."), identity)

    def service(self, session: Session, target: str, faction: str, action: str) -> None:
        player = self.ready(session)
        if self.commerce.pending:
            self.commerce.enqueue_system(lambda: self.service(session, target, faction, action)
                if self.game.sessions.active.get(session.id) is session and not session.closed else None)
            return
        if faction not in self.station(session, target) or player.faction != faction:
            raise ValueError("This service requires current membership.")
        if action != "vat-default" and not rules.perk(player, faction):
            raise ValueError("This service requires current +90 membership.")
        progress = deepcopy(player.progress)
        identity = deepcopy(self.game.identities[player.bbs_user_id])
        if action == "vat-default":
            progress["faction_respawn"] = "public" if progress.get("faction_respawn") == "hall" else "hall"
            progress.pop("faction_vat", None)
            text = "Ordinary decant destination: "+("faction vat when commissioned; public fallback" if progress["faction_respawn"] == "hall" else "nearest public vat")+"."
        elif action == "loan" and faction == "unmoored":
            from blacksite.server.lattice.programs import can_acquire
            program = self.content.programs["prg_residual_fragment"]
            if not can_acquire(program, player.archetype, player.standing, set(), bound_loan=True):
                raise ValueError("You do not meet this bound program's acquisition requirements.")
            if not rules.claim_daily(identity, "unmoored-loan", self.clock.now_utc()):
                raise ValueError("Today's bound loan is already claimed.")
            progress["faction_loan"] = True
            progress.setdefault("lattice_charges", {})["prg_residual_fragment"] = 1
            text = "Bound Residual Fragment loan. Load it in a free rig slot; jack-out consumes the loan."
        elif action.startswith("vat:") and faction == "sablier":
            chosen = action[4:]
            if chosen not in self.vats(player):
                raise ValueError("Visit that protected vat before choosing it.")
            progress["faction_vat"] = chosen
            text = "Next decant: "+self.content.factions[chosen].name+" vat."
        elif action == "preview" and faction in ("kestrel", "choir", "ferrymen"):
            offer = self.preview(player, faction)
            if not offer:
                raise ValueError("No committed event is announced. Ordinary public services remain open.")
            text = offer.text
            from blacksite.server.event_forecasts import remember
            remember(progress, offer.plan_id, {'revision': offer.revision, 'text': offer.text}, self.clock.now_utc().timestamp())
            if faction == "kestrel":
                progress["convoy_reservation"] = offer.plan_id
        else:
            raise ValueError("Choose an offered faction service.")
        def finished(success: bool) -> None:
            self.log(player, text if success else "The service could not be saved. Nothing is consumed.")
        self.commerce.settle(player, {"progress": progress}, self.commerce.items,
                             self.commerce.caches, self.commerce.serial, finished, identity)

    def station(self, session: Session, target: str) -> tuple[str, ...]:
        player = self.ready(session)
        actor = self.game.combat.actor(player)
        zone = self.world.zones[actor.zone]
        obj = zone.objects.get(target)
        if obj:
            self.commerce.nearby(session, target)
            offered = obj.spec.params.get("recruiters", ())
        else:
            recruiter = zone.actors.get(target)
            if (not recruiter or recruiter.stance in ("down", "dead")
                    or max(abs(recruiter.x-actor.x), abs(recruiter.y-actor.y)) > 1
                    or not self.game.combat.visible(actor, recruiter)):
                raise ValueError("Stand beside the recruiter or contact desk.")
            offered = tuple(fid for fid, f in self.content.factions.items()
                if f.recruiter and f.recruiter == recruiter.behaviour.get("template"))
        result = tuple(fid for fid in offered if fid in self.content.factions and self.content.active("factions", fid))
        if not result:
            raise ValueError("This is not a recruitment contact.")
        return result

    def propose(self, session: Session, target: str, action: str, faction: str) -> None:
        player = self.ready(session)
        if self.commerce.pending:
            def later() -> None:
                if self.game.sessions.active.get(session.id) is session and not session.closed:
                    try:
                        self.propose(session, target, action, faction)
                    except ValueError as exc:
                        self.log(player, str(exc))
            self.commerce.enqueue_system(later)
            return
        if faction not in self.station(session, target):
            raise ValueError("Choose a faction represented by this contact.")
        if not self.before_membership_change(player):
            if self.commerce.pending:
                self.propose(session, target, action, faction)
            return
        draft = deepcopy(player)
        if action == "join":
            rules.join(draft, self.content.factions, faction, self.clock.now_utc())
            message = "You join "+self.content.factions[faction].name+". The faction channel is open."
        elif action == "leave":
            if player.faction != faction:
                raise ValueError("You are not a member of that faction.")
            rules.leave(draft, self.content.factions, self.clock.now_utc())
            message = "You leave. Standing -50. Seven days before another faction."
        else:
            raise ValueError("Choose join or leave.")
        patch = {field: deepcopy(getattr(draft, field)) for field in ("faction", "standing", "progress")
                 if getattr(player, field) != getattr(draft, field)}
        def finished(success: bool) -> None:
            if success:
                self.refresh(player)
                self.log(player, message)
            else:
                self.log(player, "The membership change could not be saved. Your membership stays unchanged.")
        if not self.commerce.settle(player, patch, self.commerce.items, self.commerce.caches,
                                    self.commerce.serial, finished):
            raise ValueError("The city is busy. Try again.")

    def close(self, session: Session) -> None:
        self.menus.pop(session.id, None)
        self.sim.external_views.pop(session.id, None)
        avatar = self.sim.avatars.get(session.user_id)
        if avatar:
            self.sim.reset_view(session, avatar)

    def body(self, session: Session, screen: FactionMenu) -> tuple[str, dict[str, Any]]:
        player = self.ready(session)
        ids = self.station(session, screen.target)
        screen.cursor = max(0, min(screen.cursor, len(ids)-1))
        fid = ids[screen.cursor]
        faction, card = self.content.factions[fid], self.card(fid)
        if screen.vat:
            choices = self.vats(player)
            screen.vat_cursor = max(0, min(screen.vat_cursor, len(choices)-1))
            rows = [{"id": key, "cells": [self.content.factions[key].short,
                     self.content.zones[vat.zone].meta.name]} for key, vat in choices.items()]
            body = menu("ATTENDING / NEXT DECANT", rows, screen.vat_cursor,
                "Choose a visited, protected faction vat.\nThis selection lasts for one decant.\nBelow +90 or on leaving: ordinary destination.", "Enter selects  Esc/B returns")
            body["actions"] = [{"key": "enter", "label": "next decant here"}]
            return "menu", body
        if screen.pitch:
            asset = self.content.text.get(card.pitch) if card else None
            return "text", {"title": faction.name+" / RECRUITER", "lines": asset.body.splitlines() if asset else ["No message."],
                            "hint": "Esc/B returns"}
        rows = [{"id": key, "cells": [self.content.factions[key].short,
                 f"{rules.standing(player, key):+d}", rules.rank(player, self.content.factions, key),
                 "member" if player.faction == key else ""]} for key in ids]
        if screen.confirm:
            verb = screen.confirm
            hint = "Y confirms. Esc/B leaves without changing membership."
            if verb == "leave":
                hint += "\nStanding -50. Seven-day joining cooldown."
            else:
                hint += "\nOne faction at a time. Leaving later costs standing and a cooldown."
            body = menu(faction.short.upper()+" / "+verb.upper(), rows, screen.cursor, hint, "Y confirm  Esc/B returns")
            body.update(kind="faction", actions=[{"key": "y", "label": "confirm "+verb}])
            return "menu", body
        site = self.site(fid)
        hall = self.content.zones[site.hall].meta.name if site and site.hall in self.content.zones else "not yet open"
        detail = f"Standing {rules.standing(player, fid):+d}. Join: discharged and +30.\nTaking a card is not membership.\nHall: {hall}."
        cooldown = player.progress.get("faction_cooldown_until", 0)
        if cooldown > self.clock.now_utc().timestamp():
            detail = detail.rsplit("\nHall:", 1)[0]+"\nJoin after "+datetime.fromtimestamp(cooldown, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")+"."
        detail += "\nPerks: +90 membership; stop below it or on leaving."
        actions = [{"key": "i", "label": "recruiter's pitch"}]
        if rules.perk(player, fid):
            if fid == "unmoored":
                actions.append({"key": "r", "label": "bound residual loan"})
            elif fid == "sablier":
                actions.append({"key": "r", "label": "choose next decant vat"})
            elif fid in ("kestrel", "choir", "ferrymen"):
                actions.append({"key": "r", "label": "reserve escort" if fid == "kestrel" else "announced event preview"})
            elif fid == "halvard":
                detail += "\nContainment charge service: one free 150-chit fee per UTC day; consumable stays full price."
            elif fid == "sable":
                detail += "\nAt a Sable rotating counter: R reserves its optional item for ten minutes, once per UTC day."
            elif fid == "wardens":
                detail += "\nInspector: sitrep shows active Marked players' zones."

        if player.faction == fid:
            actions.append({"key": "l", "label": "leave"})
            actions.append({"key": "v", "label": "decant: "+("hall" if player.progress.get("faction_respawn") == "hall" else "public")+" (toggle)"})
        elif player.faction is None:
            actions.append({"key": "j", "label": "join"})
        if rules.perk(player, fid):
            descriptions = {
                "halvard": ["One free 150-chit charge service fee per UTC day.",
                            "The consumable still costs its normal price."],
                "sablier": ["R chooses a visited faction vat for next decant.",
                            "V changes ordinary public/hall preference."],
                "kestrel": ["R reserves an escort slot on a committed Convoy.",
                            "The public escort contract stays open."],
                "wardens": ["Sitrep reveals active Marked players' zones.",
                            "No coordinates. Other privacy stays unchanged."],
                "choir": ["R reads the next announced Surge's ICE variants.",
                          "Ordinary encounter labels remain public."],
                "sable": ["At a Sable counter: R reserves optional stock.",
                          "10 min, once per UTC day. Fixed stock stays open."],
                "unmoored": ["R claims a bound Residual Fragment once per day.",
                             "Jack-out consumes it. No permanent program."],
                "ferrymen": ["R reads a committed Ring-fall forecast free.",
                             "Paid charts and public warnings remain open."],
            }
            detail = "\n".join([f"+90 {rules.rank(player, self.content.factions, fid)}.",
                                *descriptions[fid], "Stops below +90 or on leaving."])
        body = menu("FACTIONS / RECRUITMENT", rows, screen.cursor, detail, "Esc/B returns")
        body.update(kind="faction", actions=actions)
        return "menu", body

    def interaction(self, session: Session, frame: Frame) -> Interaction | None:
        if session.id in self.menus:
            return Interaction()
        if (not self.commerce.ready(session) or session.id in self.sim.external_views
                or session.pending_prompts or not interact(frame)):
            return None
        actor = self.game.combat.actor(self.game.players[session.player_id])
        zone = self.world.zones[actor.zone]
        objects = sorted((o for o in zone.objects.values()
            if max(abs(o.spec.tile[0]-actor.x), abs(o.spec.tile[1]-actor.y)) <= 1),
            key=lambda o: (o.spec.tile != actor.position, o.spec.id))
        if objects and objects[0].spec.params.get('recruiters'):
            return object_interaction(objects[0])
        other = next((other for other in zone.actors.values()
            if other is not actor and max(abs(other.x-actor.x), abs(other.y-actor.y)) <= 1
            and any(f.recruiter and f.recruiter == other.behaviour.get('template')
                    for f in self.content.factions.values())), None)
        if other:
            return Interaction(Focus(other.id, presentation.name(other, actor, self.content), 'talk to'),
                               other, other.position, other.id)
        return None

    def input(self, session: Session, frame: Frame, tick: int, *, interaction: Interaction | None = None) -> bool:
        name = frame.data.get("name", "") if frame.type == "intent" else ""
        args = frame.data.get("args", {})
        key = frame.data.get("k", "") if frame.type == "key" else ""
        screen = self.menus.get(session.id)
        try:
            if screen:
                if name == "menu_close" or key in ("escape", "b", "B"):
                    if screen.vat:
                        screen.vat = False
                    elif screen.pitch:
                        screen.pitch = False
                    else:
                        self.close(session)
                elif name == "menu_cursor" and type(args.get("delta")) is int and not screen.confirm:
                    if screen.vat:
                        screen.vat_cursor = max(0, min(screen.vat_cursor+args["delta"], len(self.vats(self.game.players[session.player_id]))-1))
                    else:
                        screen.cursor = max(0, min(screen.cursor+args["delta"], len(self.station(session, screen.target))-1))
                elif name == "menu_select":
                    if frame.data.get("expected_revision") != session.view_revision:
                        return True
                    request = frame.data.get("request_id")
                    if request and request in self.requests.get(session.id, ()):
                        return True
                    ids = self.station(session, screen.target)
                    selected = ids[screen.cursor]
                    if screen.vat:
                        choices = list(self.vats(self.game.players[session.player_id]))
                        if (not choices or args.get("key") != "enter"
                                or args.get("row") != choices[screen.vat_cursor]):
                            raise ValueError("Choose a currently unlocked vat.")
                        self.service(session, screen.target, selected, "vat:"+choices[screen.vat_cursor])
                        screen.vat = False
                        return True
                    if args.get("row") != selected:
                        raise ValueError("Inspect the current contact before choosing.")
                    action = args.get("key", "enter")
                    if screen.confirm and action == "y":
                        confirm, screen.confirm = screen.confirm, ""
                        self.propose(session, screen.target, confirm, selected)
                    elif action in ("r", "v"):
                        _, body = self.body(session, screen)
                        if action not in {row["key"] for row in body["actions"]}:
                            raise ValueError("Choose an offered faction service.")
                        if selected == "sablier" and action == "r":
                            screen.vat, screen.vat_cursor = True, 0
                        else:
                            service = "vat-default" if action == "v" else "loan" if selected == "unmoored" else "preview"
                            self.service(session, screen.target, selected, service)
                    elif action == "i":
                        screen.pitch = True
                    elif action in ("j", "l"):
                        _, body = self.body(session, screen)
                        if action not in {row["key"] for row in body["actions"]}:
                            raise ValueError("Choose an action offered by this contact.")
                        draft = deepcopy(self.game.players[session.player_id])
                        if action == "j":
                            rules.join(draft, self.content.factions, selected, self.clock.now_utc())
                        else:
                            rules.leave(draft, self.content.factions, self.clock.now_utc())
                        screen.confirm = "join" if action == "j" else "leave"
                    if request:
                        self.requests.setdefault(session.id, []).append(request)
                        self.requests[session.id] = self.requests[session.id][-128:]
                return True
            if (not self.commerce.ready(session) or session.id in self.sim.external_views
                    or session.pending_prompts):
                return False
            if name == "faction.open":
                target = args.get("target", "")
                self.station(session, target)
                self.menus[session.id] = FactionMenu(target, 0, tick)
                return True
            if name != "interact" and key not in ("e", "E"):
                return False
            choice = interaction or self.interaction(session, frame)
            if choice:
                target = choice.focus.id
                self.station(session, target)
                self.menus[session.id] = FactionMenu(target, 0, tick)
                return True
        except (ValueError, KeyError, TypeError) as exc:
            self.commerce.toast(session, str(exc) if isinstance(exc, ValueError) else "That recruitment contact is unavailable.")
            return True
        return False

    def tick(self, ctx: TickContext) -> None:
        for player in self.game.players.values():
            if player.progress.get("faction_loan") and not rules.perk(player, "unmoored"):
                self.clear_loan(player)
        self.requests = {sid: rows for sid, rows in self.requests.items() if sid in self.game.sessions.active}
        for sid, screen in tuple(self.menus.items()):
            session = self.game.sessions.active.get(sid)
            if not session:
                self.menus.pop(sid, None)
                self.sim.external_views.pop(sid, None)
                continue
            try:
                player = self.ready(session)
                actor = self.game.combat.actor(player)
                if ctx.tick-screen.opened >= MENU_TIMEOUT_SECONDS*TICK_HZ and self.world.zones[actor.zone].allows_hostile(actor.position):
                    raise ValueError("The contact closes.")
                self.sim.external_views[sid] = self.body(session, screen)
            except (ValueError, KeyError):
                self.close(session)
