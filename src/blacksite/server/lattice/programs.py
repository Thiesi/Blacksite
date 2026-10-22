"""Pure loadout, cast and shield rules. Game design 6.7 and 17.2."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import ceil

from blacksite.content.schema import Number, ProgramTemplate
from blacksite.server.clock import TICK_HZ

TAR_CAST_MULTIPLIER = 2  # Game 17.3, Tar.
SANDMAN_LOADER_MULTIPLIER = 2  # Game 17.3, Sandman.


def ticks(seconds: float) -> int:
    return ceil(round(max(0, seconds) * TICK_HZ, 8))


def occupied_slots(rig: Sequence[str | None], programs: Mapping[str, ProgramTemplate]) -> dict[int, int]:
    """Map each occupied cell to its binding; None may be reserved space."""
    occupied: dict[int, int] = {}
    seen: set[str] = set()
    for index, pid in enumerate(rig):
        if pid is None:
            continue
        if pid not in programs:
            raise ValueError("That program is not available.")
        if index in occupied or pid in seen:
            raise ValueError("Each program needs its own complete slot space.")
        seen.add(pid)
        end = index + programs[pid].slots
        if end > len(rig):
            raise ValueError("That program does not fit this rig.")
        for cell in range(index, end):
            occupied[cell] = index
    return occupied


def bind(rig: Sequence[str | None], slot: int, program: str | None,
         known: set[str], programs: Mapping[str, ProgramTemplate]) -> tuple[str | None, ...]:
    if not 0 <= slot < len(rig):
        raise ValueError("Choose a rig slot.")
    occupied = occupied_slots(rig, programs)
    if slot in occupied and occupied[slot] != slot:
        raise ValueError("That cell belongs to a larger program. Unload its first slot.")
    if program is not None and program not in known:
        raise ValueError("You have not learned that program.")
    if program is not None and program in rig and rig[slot] != program:
        raise ValueError(f"That program is already in slot {rig.index(program)+1}. Unload it there first.")
    result = list(rig)
    result[slot] = program
    occupied_slots(result, programs)
    return tuple(result)


@dataclass
class Effect:
    program: str
    until: int | None
    amount: float = 0
    kind: str = ""
    params: dict[str, Number | str | bool] = field(default_factory=dict)


@dataclass
class Shield:
    program: str
    budget: float
    pin_once: bool = False
    black_meat_once: bool = False
    cantillation_multiplier: float = 1


@dataclass(frozen=True)
class IncomingHit:
    integrity: float
    meat: int
    pin_seconds: float


@dataclass
class Effects:
    active: dict[str, Effect] = field(default_factory=dict)
    shield: Shield | None = None
    decoy: float = 0

    def has(self, program: str, tick: int) -> bool:
        effect = self.active.get(program)
        return effect is not None and (effect.until is None or tick < effect.until)

    def expire(self, tick: int) -> None:
        self.active = {key: value for key, value in self.active.items()
                       if value.until is None or tick < value.until}
        if "prg_understudy" not in self.active:
            self.decoy = 0

    def install(self, program: ProgramTemplate, tick: int) -> None:
        params = program.effect.params
        if program.effect.kind == "absorb":
            if not self.can_replace_shield(program):
                raise ValueError("Your current shield already gives more protection.")
            self.shield = Shield(program.id, float(program.effect.amount),
                bool(params.get("pin_once")), bool(params.get("black_meat_once")),
                float(params.get("cantillation_multiplier", 1)))
            return
        until = tick + ticks(float(program.duration)) if program.duration else None
        self.active[program.id] = Effect(program.id, until, float(program.effect.amount),
                                         program.effect.kind, dict(program.effect.params))
        if program.effect.kind == "decoy":
            self.decoy = float(program.effect.amount)

    def can_replace_shield(self, program: ProgramTemplate) -> bool:
        current = self.shield
        params = program.effect.params
        return (current is None or float(program.effect.amount) > current.budget
                or bool(params.get("pin_once")) and not current.pin_once
                or bool(params.get("black_meat_once")) and not current.black_meat_once
                or float(params.get("cantillation_multiplier", 1)) < current.cantillation_multiplier)

    def consume_next_cast(self, tick: int) -> None:
        for key, effect in tuple(self.active.items()):
            if self.has(key, tick) and effect.params.get("next_cast"):
                self.active.pop(key)

    def receive(self, amount: float, meat: int = 0, *, cantillation: bool = False,
                pin_seconds: float = 0, decoy: bool = True) -> IncomingHit:
        """A volley consumes one shared budget, never one shield per pellet."""
        amount = max(0, amount)
        if decoy and self.decoy > 0:
            self.decoy = max(0, self.decoy - amount)
            return IncomingHit(0, 0, 0)
        shield = self.shield
        if shield:
            if cantillation:
                amount *= shield.cantillation_multiplier
            if pin_seconds and shield.pin_once:
                pin_seconds, shield.pin_once = 0, False
            if meat and shield.black_meat_once:
                meat, shield.black_meat_once = 0, False
            absorbed = min(shield.budget, amount)
            shield.budget -= absorbed
            amount -= absorbed
            if shield.budget <= 0:
                self.shield = None
        return IncomingHit(amount, meat, pin_seconds)


@dataclass
class Cast:
    program: str
    target: str
    until: int
    scope: str
    last_hit: int


def cast_ticks(program: ProgramTemplate, effects: Effects, tick: int, *,
               tar: bool = False, sandman: bool = False) -> int:
    if program.cast_seconds is None:
        raise ValueError("That program works while loaded; it needs no cast.")
    seconds = float(program.cast_seconds)
    active = [e for key, e in effects.active.items() if effects.has(key, tick)]
    overclock = any(e.params.get("cancel_tar") for e in active)
    if tar and not overclock:
        seconds *= TAR_CAST_MULTIPLIER
    if sandman and program.class_ == "loader" and not effects.has("prg_nobody", tick):
        seconds *= SANDMAN_LOADER_MULTIPLIER
    for effect in active:
        if effect.kind == "cast_speed":
            seconds *= effect.amount
    return ticks(seconds)


def attack_damage(program: ProgramTemplate, integrity: float, resonance: float = 0,
                  multiplier: float = 1) -> float:
    amount = float(program.effect.amount)
    params = program.effect.params
    if integrity <= float(params.get("execute_threshold", -1)):
        amount = float(params.get("execute_damage", amount))
    if params.get("resonance_divisor"):
        amount += resonance / float(params["resonance_divisor"])
    return amount * multiplier


def trace_gain(amount: float, effects: Effects, tick: int, *, suppressed: bool = False,
               multiplier: float = 1, fixed: bool = False) -> float:
    if suppressed or effects.has("prg_nobody", tick):
        return 0
    gain = amount if fixed else amount * multiplier
    for key, effect in effects.active.items():
        if gain > 0 and effects.has(key, tick) and effect.params.get("gain_multiplier"):
            gain *= float(effect.params["gain_multiplier"])
    return gain


def can_acquire(program: ProgramTemplate, archetype: str, standing: Mapping[str, int],
                acquired: set[str], *, bound_loan: bool = False) -> bool:
    for value in program.acquisition_requires:
        parts = value.split(":")
        if value == "once_per_season" and program.id in acquired:
            return False
        if value == "bound_loan" and not bound_loan:
            return False
        if parts[0] == "archetype" and archetype != parts[1]:
            return False
        if parts[0] == "standing" and standing.get(parts[1], 0) < int(parts[2]):
            return False
    return True


def can_cast(program: ProgramTemplate, archetype: str, charges: Mapping[str, int]) -> bool:
    return all((archetype == value.split(":")[1] if value.startswith("archetype:") else
                charges.get(program.id, 0) > 0 if value == "bound_charge" else True)
               for value in program.cast_requires)
