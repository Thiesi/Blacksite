"""Server-authoritative social layer; game design §11/§14, terminal UI §5."""

from collections.abc import Callable
from dataclasses import dataclass
import re
from typing import Any
import unicodedata

from blacksite.content.ids import display_width
from blacksite.server.clock import Clock, TICK_HZ
from blacksite.server.loop import TickContext
from blacksite.server.protocol import Frame
from blacksite.server.sessions import CHAT_PER_WINDOW, CHAT_WINDOW_SECONDS, Session, Sessions
from blacksite.server.wake import menu
from blacksite.server.world.simulation import MENU_TIMEOUT_SECONDS, ZoneSimulation

SAY_RADIUS = 20  # Game design §11.
CHAT_COLUMNS = 200  # Terminal UI §5.2.
LOG_LINE_BYTES = 768  # Transport budget: fifty replay lines fit in a 64KiB frame.


def sanitize(text: str, columns: int = CHAT_COLUMNS) -> str:
    """Strip terminal commands as units, normalize NFC, bound cells and bytes."""
    text = re.sub(r"(?:\x1b\]|\x9d)[^\x07\x1b\x9c]*(?:\x07|\x1b\\|\x9c|$)", "", text)
    text = re.sub(r"(?:\x1b[P^_]|[\x90\x9e\x9f]).*?(?:\x1b\\|\x9c|$)", "", text, flags=re.DOTALL)
    text = re.sub(r"(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"\x1b(?:[ -/]*[@-~]|.*$)", "", text)
    text = unicodedata.normalize("NFC", "".join(c for c in text if not unicodedata.category(c).startswith("C")))
    result: list[str] = []
    cells = size = 0
    for char in text:
        width, encoded = display_width(char), len(char.encode("utf-8"))
        if cells + width > columns or size + encoded > LOG_LINE_BYTES:
            break
        if width or result:
            result.append(char)
            cells += width
            size += encoded
    return "".join(result).strip()


@dataclass
class Sitrep:
    cursor: int
    opened: int
    last_request: str = ""


class Chat:
    def __init__(self, sessions: Sessions, sim: ZoneSimulation, clock: Clock, characters: Any = None) -> None:
        self.sessions, self.sim, self.clock, self.characters = sessions, sim, clock, characters
        self.sitreps: dict[str, Sitrep] = {}
        self.serial = 0
        self.outbox: list[dict[str, Any]] = []
        self.settings_fallback: dict[str, dict[str, Any]] = {}
        self.crew_of: Callable[[Session], str | None] = lambda s: None  # S22 installs membership.
        self.lattice_at: Callable[[Session], tuple[str, str] | None] = lambda s: None
        self.status_of: Callable[[Session], str] = lambda session: ""
        self.rank_of: Callable[[Session], str] = lambda session: ""
        self.reported_location: Callable[[Session, Session], str | None] = lambda viewer, target: None

    def ready(self, session: Session) -> bool:
        av = self.sim.avatars.get(session.user_id)
        return bool(session.role == "caller" and not session.closed and av and av.actor.id == session.player_id)

    def online(self) -> list[Session]:
        return [s for s in self.sessions.active.values() if self.ready(s)]

    def settings(self, session: Session) -> dict[str, Any]:
        if self.characters:
            return self.characters.players[session.player_id].settings
        return self.settings_fallback.setdefault(session.user_id, {})

    def save_settings(self, session: Session) -> None:
        if self.characters:
            self.characters.queue("save", session.user_id, self.characters.players[session.player_id], immediate=True)

    def name(self, session: Session) -> str:
        return sanitize(self.sim.avatars[session.user_id].actor.name, 24)

    def label(self, session: Session) -> str:
        return f"{self.name(session)} ({sanitize(str(session.door_info.get('handle', '')), 24)})"

    def target(self, name: str) -> Session | None:
        key = sanitize(name).casefold()
        matches = [s for s in self.online() if key in (self.name(s).casefold(), sanitize(str(s.door_info.get("handle", ""))).casefold())]
        return matches[0] if len(matches) == 1 else None

    def toast(self, session: Session, text: str) -> None:
        session.send(Frame("toast", {"text": text, "role": "ui_text", "seconds": 4}))

    def known(self, name: str) -> list[tuple[str, str]]:
        key = sanitize(name).casefold()
        if self.characters:
            return [(p.id, p.bbs_user_id) for p in self.characters.players.values()
                    if key in (sanitize(p.name).casefold(), sanitize(p.bbs_handle).casefold())]
        return [(s.player_id, s.user_id) for s in self.online()
                if key in (self.name(s).casefold(), sanitize(str(s.door_info.get("handle", ""))).casefold())]

    def allowed(self, session: Session, tick: int) -> bool:
        if session.allow("chat", tick, CHAT_PER_WINDOW, CHAT_WINDOW_SECONDS):
            return True
        self.toast(session, "You can send four lines every five seconds.")
        return False

    def emit(self, recipient: Session, channel: str, text: str, source: Session | None = None) -> None:
        if source and source.user_id in self.settings(recipient).get("ignored", []):
            return
        faction = self.characters.content.factions.get(self.faction(recipient)) if self.characters and channel == "faction" else None
        recipient.send(Frame("log", {"lines": [{"channel": channel, "text": sanitize(text),
            "role": faction.colour if faction else "chan_" + ({"system":"sys", "shout":"say"}.get(channel, channel)), "at": self.clock.now_utc().isoformat()}]}))

    def faction(self, session: Session) -> str | None:
        return self.characters.players[session.player_id].faction if self.characters else self.sim.avatars[session.user_id].actor.faction

    def recipients(self, sender: Session, channel: str) -> list[Session]:
        actor = self.sim.avatars[sender.user_id].actor
        if channel in ("crew", "faction"):
            group = self.crew_of if channel == "crew" else self.faction
            membership = group(sender)
            return [s for s in self.online() if membership and group(s) == membership]
        location = self.lattice_at(sender)
        if location:
            return [s for s in self.online() if self.lattice_at(s) is not None
                    and (self.lattice_at(s)[0] == location[0] if channel == "shout"
                         else self.lattice_at(s) == location)]
        if actor.zone is None:
            return []
        result = []
        for session in self.online():
            if self.lattice_at(session) is not None:
                continue
            other = self.sim.avatars[session.user_id].actor
            if other.zone == actor.zone and (channel != "say" or (other.x-actor.x)**2 + (other.y-actor.y)**2 <= SAY_RADIUS**2):
                result.append(session)
        return result

    def speak(self, sender: Session, channel: str, text: str, tick: int, target: str = "") -> None:
        text = sanitize(text)
        if not text:
            return
        if channel not in ("say", "shout", "whisper", "crew", "faction"):
            self.toast(sender, "That channel is server-owned.")
            return
        if not self.allowed(sender, tick):
            return
        if channel == "whisper":
            peer = self.target(target)
            if peer is None:
                self.toast(sender, "No unique caller matches. Use a character name.")
                return
            line = f"{self.label(sender)} -> {self.label(peer)}: {text}"
            for recipient in {s.id: s for s in (sender, peer)}.values():
                self.emit(recipient, channel, line, sender)
            return
        recipients = self.recipients(sender, channel)
        if not recipients:
            self.toast(sender, "You have no audience on that channel.")
        for recipient in recipients:
            self.emit(recipient, "lat" if self.lattice_at(sender) and channel in ("say", "shout") else channel,
                      f"{self.name(sender)}: {text}", sender)

    def emote(self, sender: Session, eid: str, target: str, text: str, tick: int) -> None:
        free = sanitize(text)
        spec = self.sim.world.content.emotes.get(eid)
        if not free and spec is None:
            self.toast(sender, "You do not know that emote.")
            return
        peer = self.target(target) if target else None
        if target and (peer is None or peer not in self.recipients(sender, "zone")):
            self.toast(sender, "No unique caller is here by that name.")
            return
        if not self.allowed(sender, tick):
            return
        for recipient in self.recipients(sender, "zone"):
            if free:
                line = f"{self.name(sender)} {free}"
            elif peer:
                form = spec.first_targeted if recipient is sender else spec.targeted
                line = form.format(name=self.name(sender), target="you" if recipient is peer else self.name(peer))
            else:
                line = (spec.first if recipient is sender else spec.third).format(name=self.name(sender), target="")
            self.emit(recipient, "lat" if self.lattice_at(sender) else "zone", line, sender)

    def prompt(self, session: Session, channel: str) -> None:
        self.serial += 1
        pid = f"chat:{session.id}:{self.serial}"
        session.pending_prompts["chat"] = {"id": pid, "channel": channel}
        label = "Whisper (name: text)" if channel == "whisper" else channel.title()
        session.send(Frame("prompt", {"id": pid, "kind": "line", "label": label, "max_len": CHAT_COLUMNS}))

    def command(self, session: Session, channel: str, text: str, tick: int) -> None:
        text = sanitize(text)
        if channel == "say" and text.startswith("/"):
            verb, _, rest = text[1:].partition(" ")
            verb = verb.casefold()
            if verb == "me":
                self.emote(session, "", "", rest, tick)
            elif verb in self.sim.world.content.emotes:
                self.emote(session, verb, rest, "", tick)
            elif verb in ("ignore", "unignore", "report", "hide", "show"):
                if verb in ("hide", "show"):
                    self.change_hidden(session, verb == "hide")
                elif verb in ("ignore", "unignore"):
                    self.ignore(session, rest, verb == "ignore")
                else:
                    name, _, report = rest.partition(":")
                    self.report(session, name, report, tick)
            elif verb in ("say", "shout", "whisper", "crew", "faction"):
                self.command(session, verb, rest, tick)
            else:
                self.toast(session, "You do not know that command.")
        elif channel == "whisper":
            name, sep, body = text.partition(":")
            if sep:
                self.speak(session, channel, body, tick, name)
            else:
                self.toast(session, "Use name: text for a whisper.")
        else:
            self.speak(session, channel, text, tick)

    def change_hidden(self, session: Session, hidden: bool) -> None:
        self.settings(session)["sitrep_hidden"] = hidden
        self.save_settings(session)
        self.toast(session, "Your zone is hidden." if hidden else "Your zone is visible.")

    def ignore(self, session: Session, name: str, enabled: bool = True) -> None:
        identities = {user for _, user in self.known(name)}
        if len(identities) != 1:
            self.toast(session, "No unique caller matches. Use a character name.")
            return
        target = identities.pop()
        if target == session.user_id:
            self.toast(session, "You cannot ignore yourself.")
            return
        ignored = self.settings(session).setdefault("ignored", [])
        if enabled and target not in ignored:
            ignored.append(target)
        elif not enabled and target in ignored:
            ignored.remove(target)
        self.save_settings(session)
        self.toast(session, "Ignored." if enabled else "Unignored.")

    def report(self, session: Session, name: str, text: str, tick: int) -> None:
        matches, text = self.known(name), sanitize(text)
        if len(matches) != 1 or not text:
            self.toast(session, "Use a unique character name and a report message.")
            return
        if not self.allowed(session, tick):
            return
        self.serial += 1
        self.outbox.append({"session": session.id, "row": {"reporter": session.player_id, "target": matches[0][0],
            "reporter_user": session.user_id, "target_user": matches[0][1], "target_name": sanitize(name),
            "text": text, "at": self.clock.now_utc().isoformat(), "action": "report", "token": f"{session.id}:{self.serial}"}})

    def committed(self, effect: dict[str, Any], success: bool) -> None:
        session = self.sessions.active.get(effect["session"])
        if session:
            self.toast(session, "Reported." if success else "Your report could not be saved. Try again.")

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        if not self.ready(session):
            return False
        name = frame.data.get("name", "") if frame.type == "intent" else ""
        args = frame.data.get("args", {})
        key = frame.data.get("k", "") if frame.type == "key" else ""
        pending = session.pending_prompts.get("chat")
        if pending and ((frame.type == "line" and frame.data["id"] == pending["id"]) or (name == "prompt_cancel" and args.get("id") == pending["id"])):
            session.pending_prompts.pop("chat")
            if frame.type == "line":
                self.command(session, pending["channel"], frame.data["text"], tick)
            return True
        if pending and (frame.type == "key" or name in ("move", "sprint")):
            return True
        if name == "settings":
            if type(args.get("sitrep_hidden")) is bool:
                self.change_hidden(session, args["sitrep_hidden"])
            return True
        if session.id in self.sitreps:
            screen = self.sitreps[session.id]
            if name == "menu_close":
                self.close_sitrep(session)
            elif name == "menu_cursor" and type(args.get("delta")) is int:
                screen.cursor = max(0, min(len(self.online())-1, screen.cursor+args["delta"]))
            elif name == "menu_select" and args.get("key") == "h":
                if frame.data.get("expected_revision") != session.view_revision or frame.data.get("request_id") == screen.last_request:
                    return True
                screen.last_request = frame.data["request_id"]
                self.change_hidden(session, not self.settings(session).get("sitrep_hidden", False))
            return True
        if name in ("chat", "emote", "ignore", "report", "settings"):
            if name == "settings":
                if type(args.get("sitrep_hidden")) is bool:
                    self.change_hidden(session, args["sitrep_hidden"])
            elif all(isinstance(args.get(k, ""), str) for k in ("channel", "text", "target", "id", "name")):
                if name == "chat": self.speak(session, args.get("channel", "say"), args.get("text", ""), tick, args.get("target", ""))
                elif name == "emote": self.emote(session, args.get("id", ""), args.get("target", ""), args.get("text", ""), tick)
                elif name == "ignore": self.ignore(session, args.get("name", ""), args.get("enabled", True) is not False)
                else: self.report(session, args.get("name", ""), args.get("text", ""), tick)
            return True
        # Respect existing character/menu/travel contexts and the vi keymap.
        if (self.characters and session.id in self.characters.screens) or session.id in self.sim.maps or self.sim.avatars[session.user_id].travel:
            return False
        action = name
        if key:
            table = next((m for m in self.sim.keymap.get("keymaps", []) if m["id"] == session.keymap_id), {})
            action = next((a for a, keys in table.get("bindings", {}).items() if key in keys), "")
        if action.startswith("chat_"):
            self.prompt(session, action[5:])
            return True
        if action == "sitrep":
            self.sitreps[session.id] = Sitrep(0, tick)
            return True
        return False

    def close_sitrep(self, session: Session) -> None:
        self.sitreps.pop(session.id, None)
        self.sim.external_views.pop(session.id, None)
        self.sim.reset_view(session, self.sim.avatars[session.user_id])

    def tick(self, ctx: TickContext) -> None:
        for sid, screen in tuple(self.sitreps.items()):
            session = self.sessions.active.get(sid)
            if session is None or not self.ready(session):
                self.sitreps.pop(sid)
                self.sim.external_views.pop(sid, None)
                continue
            av = self.sim.avatars[session.user_id]
            if ctx.tick-screen.opened >= MENU_TIMEOUT_SECONDS*TICK_HZ and self.sim.world.zones[av.zone].allows_hostile(av.actor.position):
                self.close_sitrep(session)
                continue
            hidden = self.settings(session).get("sitrep_hidden", False)
            rows = []
            for other in sorted(self.online(), key=lambda s:self.name(s).casefold()):
                oa = self.sim.avatars[other.user_id]
                location = "hidden" if hidden or self.settings(other).get("sitrep_hidden", False) else (self.sim.world.zones[oa.actor.zone].template.meta.name if oa.actor.zone else "in transit")
                location = self.reported_location(session, other) or location
                rows.append({"id": other.player_id, "cells": [self.name(other), sanitize(str(other.door_info.get("handle", ""))), self.faction(other) or "Freelance", location, "jacked" if oa.actor.stance == "jacked" else "body", self.rank_of(other), self.status_of(other)]})
            body = menu("SITREP", rows, min(screen.cursor, max(0,len(rows)-1)),
                        "Your zone is hidden; others' zones are hidden from you." if hidden else "Online characters. H hides your zone.", "H hide/show zone  Esc/B returns")
            body["columns"] = ["Name", "Handle", "Faction", "Zone", "Link", "Rank", "Status"]
            if rows:
                selected = rows[body["cursor"]]["cells"]
                body["detail"] = f"{selected[6] or selected[4]} | Zone: {selected[3]}\nName: {selected[0]}\nHandle: {selected[1]}\nFaction: {selected[2]}  Rank: {selected[5] or 'none'}"
            body["actions"] = [{"key":"h", "label":"hide/show zone"}]
            self.sim.external_views[sid] = "menu", body
