"""Game 8.6: publish substance clocks and forced unseating after commit."""

from copy import deepcopy
from typing import TYPE_CHECKING

from blacksite.content.schema import ItemTemplate
from blacksite.server import drugs, implants
from blacksite.server.clock import TICK_HZ
from blacksite.server.modifiers import collect
from blacksite.server.players import Player
from blacksite.server.protocol import Frame
from blacksite.server.rules.combat import DOWN_SECONDS

if TYPE_CHECKING:
    from blacksite.server.progression_engine import ProgressionEngine


class Substances:
    def __init__(self, progression: "ProgressionEngine") -> None:
        self.progression = progression
        self.game, self.commerce = progression.game, progression.commerce
        self.pending: set[str] = set()

    def advance(self, draft: Player, now: float) -> tuple[drugs.Step, tuple[str, ...]]:
        result = drugs.advance(draft, self.game.content.items, now)
        mods = collect(draft, self.commerce.items, self.game.content.items, now)
        ejected = implants.enforce_tolerance(draft, self.commerce.items, self.game.content.items, mods, now)
        if ejected:
            mods = collect(draft, self.commerce.items, self.game.content.items, now)
        if draft.progress.get("combat", {}).get("stage") not in ("down", "dead"):
            draft.health = min(mods.health_max(draft), max(0, draft.health+result.health_delta))
            if draft.health == 0:
                draft.progress["combat"] = {"stage": "down", "until": now+DOWN_SECONDS, "killer": ""}
        return result, ejected

    def consume(self, draft: Player, template: ItemTemplate, now: float) -> str:
        step, ejected = self.advance(draft, now)
        result = drugs.dose(draft, template, self.progression.modifiers(draft), now)
        notes = [" Dependency takes hold. Detox at a Sablier clinic clears it."] if result.dependency_started else []
        notes += [" "+self.game.content.items[tid].name+" fades. The crash begins." for tid in step.crashes_started]
        if ejected:
            notes.append(" Chrome fades. Excess hardware unseats; you keep the items.")
        return "".join(notes)

    def effects(self, player: Player) -> list[dict[str, object]]:
        now = self.game.clock.now_utc().timestamp()
        statuses: list[dict[str, object]] = []
        dependent = {state["template"] for state in player.dependencies}
        for state in player.drugs_active:
            positive = now < state["effect_until"]
            if not positive and (state["template"] in dependent or now >= state["crash_until"]):
                continue
            until = state["effect_until"] if positive else state["crash_until"]
            statuses.append({"kind": "substance", "template": state["template"],
                "label": self.game.content.items[state["template"]].name,
                "phase": "effect" if positive else "crash", "seconds": max(0, until-now)})
        statuses += [{"kind": "substance", "template": tid, "label": self.game.content.items[tid].name,
                      "phase": "dependency", "seconds": None} for tid in sorted(dependent)]
        return statuses

    def refresh(self, pid: str) -> None:
        if pid in self.pending:
            return
        self.pending.add(pid)
        def propose() -> None:
            player = self.game.players.get(pid)
            if player is None or pid in self.game.deleting:
                self.pending.discard(pid)
                return
            draft = deepcopy(player)
            actor = self.game.combat.actor(player)
            if actor:
                draft.health, draft.stamina, draft.shock = actor.health, actor.stamina, actor.shock
            result, ejected = self.advance(draft, self.game.clock.now_utc().timestamp())
            patch = {key: deepcopy(getattr(draft, key)) for key in
                     ("health", "stamina", "shock", "implants", "drugs_active", "dependencies", "progress")
                     if getattr(draft, key) != getattr(player, key)}
            if not patch:
                self.pending.discard(pid)
                return
            def committed(success: bool) -> None:
                self.pending.discard(pid)
                if not success:
                    return
                current = self.game.combat.actor(player)
                if current:
                    if "health" in patch:
                        current.health = player.health
                    if "shock" in patch:
                        current.shock = player.shock
                    if player.progress.get("combat", {}).get("stage") == "down":
                        current.stance = "down"
                        current.effects.clear()
                self.progression.sync_actor(player)
                lines = [self.game.content.items[tid].name+" fades. The crash begins." for tid in result.crashes_started]
                if ejected:
                    names = ", ".join(self.game.content.items[self.commerce.items[iid].template].name for iid in ejected)
                    lines.append(names+" unseats. You keep the hardware; shock holds for thirty seconds.")
                if result.detox_completed:
                    lines.append("Detox ends. Your dependencies clear. You can leave the clinic.")
                session = self.game.combat.session(pid)
                if session and lines:
                    session.send(Frame("log", {"lines": [{"channel": "system", "text": line,
                        "role": "chan_sys", "at": self.game.clock.now_utc().isoformat()} for line in lines]}))
                self.game.dirty_screens.update(s.id for s in self.game.sessions.active.values() if s.player_id == pid)
            self.commerce.settle(player, patch, self.commerce.items, self.commerce.caches,
                                 self.commerce.serial, committed)
        try:
            self.commerce.enqueue_system(propose)
        except ValueError:
            self.pending.discard(pid)  # Retry the persisted clocks next second.

    def tick(self, tick: int) -> None:
        if tick % TICK_HZ:
            return
        for player in tuple(self.game.players.values()):
            if player.drugs_active or player.progress.get("detox"):
                self.refresh(player.id)
