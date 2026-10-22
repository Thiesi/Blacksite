"""Game 8.6: deterministic substance clocks on persisted player drafts.

UTC seconds come from the simulation clock. The adapter consumes an item,
commits these records and publishes resource changes in the same receipt.
Nothing here waits, reads a clock or touches storage.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from math import floor

from blacksite.content.schema import ItemTemplate
from blacksite.server.modifiers import Modifiers
from blacksite.server.players import Player

DETOX_CHITS = 400  # Game 8.6.
DETOX_SECONDS = 600
DOSE_HISTORY = 10  # Entity 2.1 / S16.


@dataclass(frozen=True)
class Dose:
    dependency_started: bool
    effect_until: float
    crash_until: float


@dataclass(frozen=True)
class Step:
    health_delta: int = 0
    crashes_started: tuple[str, ...] = ()
    detox_completed: bool = False


def detox_until(player: Player) -> float:
    return float(player.progress.get("detox", {}).get("until", 0))


def dose(player: Player, template: ItemTemplate, modifiers: Modifiers, now: float) -> Dose:
    drug = template.drug
    if not drug:
        raise ValueError("That item is not a substance.")
    if detox_until(player) > now:
        raise ValueError("Detox is still in progress.")
    window = drug.addiction_window*modifiers.multiplier("addiction_window_multiplier")
    history = player.progress.setdefault("dose_log", {}).setdefault(template.id, [])
    history[:] = [stamp for stamp in history if now-window <= stamp <= now]
    history.append(now)
    history[:] = history[-DOSE_HISTORY:]
    dependent = any(d["template"] == template.id for d in player.dependencies)
    starts = len(history) >= drug.addiction_doses and not dependent
    if starts:
        player.dependencies.append({"template": template.id, "since": now})
    effect_until = now+drug.duration
    crash_until = effect_until+drug.duration/2*modifiers.multiplier("crash_duration_multiplier")
    # Repeated doses refresh one substance, rather than stack its bonus.
    player.drugs_active[:] = [state for state in player.drugs_active if state["template"] != template.id]
    player.drugs_active.append({"template": template.id, "started": now,
        "effect_until": effect_until, "crash_until": crash_until,
        "healed": 0, "damaged": 0, "crash_announced": False})
    return Dose(starts, effect_until, crash_until)


def advance(player: Player, templates: Mapping[str, ItemTemplate], now: float) -> Step:
    detox = player.progress.get("detox")
    if detox and now >= detox["until"]:
        player.dependencies.clear()
        player.drugs_active.clear()
        player.progress["dose_log"] = {}
        del player.progress["detox"]
        return Step(detox_completed=True)
    delta, crashes, remaining = 0, [], []
    for state in player.drugs_active:
        template = templates.get(state["template"])
        drug = template.drug if template else None
        if not drug:
            continue
        elapsed = max(0, min(now, state["effect_until"])-state["started"])
        effects = drug.effects
        healed = floor(effects.get("health_over_time", 0)*min(1, elapsed/max(1, effects.get("heal_seconds", 1))))
        damaged = floor(max(0, -effects.get("health_per_second", 0))*elapsed)
        delta += healed-state.get("healed", 0)-damaged+state.get("damaged", 0)
        state["healed"], state["damaged"] = healed, damaged
        if now >= state["effect_until"] and not state.get("crash_announced"):
            crashes.append(state["template"])
            state["crash_announced"] = True
        if now < state["crash_until"]:
            remaining.append(state)
    player.drugs_active = remaining
    return Step(delta, tuple(crashes))


def start_detox(player: Player, now: float, zone: str, tile: tuple[int, int]) -> float:
    """Caller verifies the real Sablier object's existing safe pocket first."""
    if detox_until(player) > now:
        raise ValueError("Detox is already in progress.")
    if not player.dependencies:
        raise ValueError("You have no dependency to treat.")
    if player.chits_hand < DETOX_CHITS:
        raise ValueError("Detox costs 400 chits carried in hand.")
    player.chits_hand -= DETOX_CHITS
    player.progress["detox"] = {"until": now+DETOX_SECONDS, "zone": zone, "tile": list(tile)}
    player.drugs_active.clear()
    return now+DETOX_SECONDS


def end_ringdust_crash(player: Player, now: float) -> bool:
    """Food ends the timed crash; a permanent dependency still needs detox."""
    before = len(player.drugs_active)
    player.drugs_active[:] = [state for state in player.drugs_active
        if state["template"] != "drug_ferry_ringdust" or now < state["effect_until"]]
    return len(player.drugs_active) != before
