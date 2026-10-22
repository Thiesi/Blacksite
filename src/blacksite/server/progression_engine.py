"""Progression adapters: server-owned skill spending and modifier access.

S16's owning engines attach reward grants to their existing transactions.
This facade owns UI and manual spending; it never pays post-commit XP.
"""

from copy import deepcopy
from collections.abc import Callable
from typing import Any

from blacksite.server.commerce import Commerce
from blacksite.server.modifiers import Modifiers, collect
from blacksite.server.loop import TickContext
from blacksite.server.players import Player
from blacksite.server.progression import Award, Grant, award
from blacksite.server.progression_views import character_sheet, skill_menu
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session
from blacksite.server.skills import LINE_GROUP, Use, gain, spend
from blacksite.server.world.actors import Actor


class ProgressionEngine:
    def __init__(self, commerce: Commerce) -> None:
        self.commerce, self.game, self.sim = commerce, commerce.game, commerce.sim
        self.clock, self.content = self.game.clock, self.game.content
        self.game.progression = self
        self.menus: dict[str, int] = {}
        self.requests: dict[str, list[str]] = {}
        self.crew_of: Callable[[str], str | None] = lambda pid: None  # S22.
        self.permit_combat: Callable[[str, str], bool] = lambda source, target: True  # S19.

    def modifiers(self, player: Player) -> Modifiers:
        return collect(player, self.commerce.items, self.content.items,
                       self.clock.now_utc().timestamp())

    def controller(self, actor: Actor) -> Player | None:
        if actor.id in self.game.players:
            return self.game.players[actor.id]
        if actor.kind == "drone" and actor.behaviour.get("player_drone"):
            return self.game.players.get(actor.owner)
        return None

    def sync_actor(self, player: Player) -> None:
        from blacksite.server.inventory import Inventory
        from blacksite.server.rules import character
        actor = self.game.combat.actor(player)
        if actor is None:
            return
        mods = self.modifiers(player)
        before = (actor.modifiers, actor.health_max, actor.stamina_max, actor.overweight)
        pools = actor.health, actor.stamina, actor.shock
        actor.modifiers = dict(mods.values)
        actor.modifiers["shock_floor"] = (100 if player.progress.get("surgery_shock_until", 0)
            > self.clock.now_utc().timestamp() else mods.bonus("shock"))
        actor.health_max = mods.health_max(player)
        actor.stamina_max = character.stamina_max(mods.attribute(player, "nerve"), mods.attribute(player, "frame"))
        actor.health, actor.stamina = min(actor.health, actor.health_max), min(actor.stamina, actor.stamina_max)
        actor.shock = max(actor.shock, actor.modifiers["shock_floor"])
        actor.overweight = Inventory(self.commerce.items, self.content.items).weight(player) > (
            character.carry_kg(mods.attribute(player, "frame"))+mods.bonus("carry_kg"))
        if pools != (actor.health, actor.stamina, actor.shock):
            player.health, player.stamina, player.shock = actor.health, actor.stamina, actor.shock
            self.game.queue("save", player.bbs_user_id, player, immediate=False)
        if actor.zone and before != (actor.modifiers, actor.health_max, actor.stamina_max, actor.overweight):
            self.game.world.zones[actor.zone].revision += 1

    def sheet(self, player: Player, cursor: int) -> dict[str, Any]:
        from datetime import datetime
        identity = self.game.identities[player.bbs_user_id]
        days = max(0, (self.clock.now_utc()-datetime.fromisoformat(identity["first_decanted_at"])).days)
        return character_sheet(player, self.content, self.commerce.items,
                               self.clock.now_utc().timestamp(), days, cursor, self.modifiers(player))

    def reward_patch(self, player: Player, grant: Grant) -> tuple[dict[str, Any], dict[str, Any], Award | None]:
        """The source owner joins this patch to its item/spawn transaction."""
        draft = deepcopy(player)
        identity = deepcopy(self.game.identities[player.bbs_user_id])
        actor = self.game.combat.actor(player)
        if actor:
            draft.health, draft.stamina, draft.shock = actor.health, actor.stamina, actor.shock
        result = award(draft, identity, grant, self.clock.now_utc(), self.modifiers(player))
        patch = {key: deepcopy(getattr(draft, key)) for key in
                 ("xp", "grade", "attributes", "health", "legal_at")
                 if getattr(draft, key) != getattr(player, key)}
        progress = {key: deepcopy(value) for key, value in draft.progress.items()
                    if key not in player.progress or player.progress[key] != value}
        if progress:
            patch["progress"] = {**deepcopy(player.progress), **progress}
        return patch, identity, result

    def gain(self, draft: Player, use: Use) -> float:
        return gain(draft, use, self.clock.now_utc(), self.content.skills.get(use.line))

    def record_use(self, pid: str, use: Use) -> None:
        """A completed server action supplies facts; the queue serializes caps."""
        occurred = self.clock.now_utc()
        def propose() -> None:
            player = self.game.players.get(pid)
            if player is None or pid in self.game.deleting:
                return
            draft = deepcopy(player)
            amount = gain(draft, use, occurred, self.content.skills.get(use.line))
            if not amount:
                return
            def committed(success: bool) -> None:
                if success:
                    self.sync_actor(player)
                    self.game.dirty_screens.update(s.id for s in self.game.sessions.active.values()
                                                   if s.player_id == pid)
            self.commerce.settle(player, {"skills": draft.skills, "attributes": draft.attributes,
                "progress": draft.progress}, self.commerce.items, self.commerce.caches,
                self.commerce.serial, committed)
        self.commerce.enqueue_system(propose)

    def notify_reward(self, player: Player, result: Award | None) -> None:
        """Publication only; the owning receipt has already committed XP."""
        if result is None:
            return
        actor = self.game.combat.actor(player)
        if actor:
            mods = self.modifiers(player)
            actor.health_max = mods.health_max(player)
            actor.health = min(actor.health_max, player.health)
        session = self.game.combat.session(player.id)
        if session and not session.closed:
            self.game.dirty_screens.add(session.id)
            text = f"You gain {result.xp} XP."
            if result.grade > result.old_grade:
                grade = next((g for g in self.content.grades.values() if g.grade == result.grade), None)
                text += " "+(grade.promotion if grade else f"You reach grade {result.grade}.")
                self.commerce.toast(session, text)
            session.send(Frame("log", {"lines": [{"channel": "system", "text": text,
                "role": "chan_sys", "at": self.clock.now_utc().isoformat()}]}))

    def open_skills(self, session: Session) -> None:
        self.game.screens.pop(session.id, None)
        self.menus[session.id] = 0
        self.publish_menu(session)

    def publish_menu(self, session: Session) -> None:
        player = self.game.players[session.player_id]
        self.sim.external_views[session.id] = ("menu", skill_menu(player, self.content,
            self.menus[session.id], self.clock.now_utc().timestamp()))

    def close_skills(self, session: Session, *, return_to_sheet: bool = True) -> None:
        self.menus.pop(session.id, None)
        view = self.sim.external_views.get(session.id)
        if view and view[0] == "menu":
            self.sim.external_views.pop(session.id, None)
        if return_to_sheet and not session.closed and session.player_id in self.game.players:
            self.game.screens[session.id] = ("sheet", 0)
            self.game.dirty_screens.add(session.id)

    def spend(self, session: Session, line: str) -> bool:
        if self.commerce.pending:
            self.commerce.toast(session, "The city is busy. Try again.")
            return False
        player = self.game.players[session.player_id]
        draft = deepcopy(player)
        amount = spend(draft, line)
        patch = {"skills": draft.skills, "attributes": draft.attributes, "progress": draft.progress}

        def committed(success: bool) -> None:
            if success:
                actor = self.game.combat.actor(player)
                if actor:
                    from blacksite.server.rules import character
                    mods = self.modifiers(player)
                    actor.health_max = mods.health_max(player)
                    actor.stamina_max = character.stamina_max(mods.attribute(player, "nerve"), mods.attribute(player, "frame"))
                self.commerce.toast(session, f"{line.title()} rises by {amount:g}. One grade point spent.")
                self.game.dirty_screens.add(session.id)
            elif not session.closed:
                self.commerce.toast(session, "The skill did not settle. Your grade point remains.")
            if session.id in self.menus and not session.closed:
                self.publish_menu(session)

        return self.commerce.settle(player, patch, self.commerce.items,
            self.commerce.caches, self.commerce.serial, committed)

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        player = self.game.players.get(session.player_id)
        if player:
            self.sync_actor(player)
        if session.id not in self.menus:
            return False
        if session.closed or session.player_id not in self.game.players:
            self.close_skills(session)
            return True
        name = frame.data.get("name", "") if frame.type == "intent" else ""
        args = frame.data.get("args", {})
        if name == "menu_close":
            self.close_skills(session)
        elif name == "menu_cursor" and type(args.get("delta")) is int:
            self.menus[session.id] = max(0, min(len(LINE_GROUP)-1, self.menus[session.id]+args["delta"]))
            self.publish_menu(session)
        elif name == "menu_select":
            if frame.data.get("expected_revision") != session.view_revision:
                return True
            request = frame.data.get("request_id", "")
            if request and request in self.requests.get(session.id, ()):
                return True
            line = tuple(LINE_GROUP)[self.menus[session.id]]
            if args.get("key") != "+" or args.get("row") != line:
                return True
            try:
                if self.spend(session, line) and request:
                    self.requests.setdefault(session.id, []).append(request)
                    self.requests[session.id] = self.requests[session.id][-128:]
            except ValueError as exc:
                self.commerce.toast(session, str(exc))
        return True

    def tick(self, ctx: TickContext) -> None:
        for player in self.game.players.values():
            self.sync_actor(player)
        for sid in tuple(self.menus):
            session = self.game.sessions.active.get(sid)
            if session is None or session.closed or session.player_id not in self.game.players:
                self.menus.pop(sid, None)
                self.sim.external_views.pop(sid, None)
                continue
            actor = self.game.combat.actor(self.game.players[session.player_id])
            if actor is None or actor.stance in ("down", "dead", "sleeper"):
                self.close_skills(session, return_to_sheet=False)
            elif ctx.tick % 10 == 0 or session.needs_full_view:
                self.publish_menu(session)
        for sid in tuple(self.requests):
            if sid not in self.game.sessions.active:
                self.requests.pop(sid, None)
        if ctx.tick % 10 == 0:
            self.game.dirty_screens.update(s.id for s in ctx.sessions
                if self.game.screens.get(s.id, (None,))[0] == "sheet")
