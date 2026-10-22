"""Deterministic defender phases and attributed events; game 6.7/17.3.

No body, socket or storage access belongs here. The encounter controller
rechecks authority when applying each event to a presence or physical body.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from random import Random
from typing import Literal

from blacksite.content.schema import IceTemplate
from blacksite.server.clock import TICK_HZ
from blacksite.server.lattice.programs import Effects, ticks

FIRST_WARNING_SECONDS = 2  # Game 6.7.
MASTIFF_MOVE_SECONDS = 3
DRIFT_MOVE_SECONDS = 4
HUNTER_MOVE_SECONDS = 1
SWEEPER_DWELL_SECONDS = 2
CHORISTER_PHASE_SECONDS = 5  # Game 6.6.
HEAL_INTERVAL_SECONDS = 1  # Game 17.3, Suture.
CANTILLATION_RESONANCE_DIVISOR = 4  # Game 6.7.

Location = tuple[str, str]


@dataclass
class Runner:
    id: str
    location: Location
    trace: float
    resonance: float
    archetype: str
    effects: Effects
    alert_all: bool = False


@dataclass(frozen=True)
class IceEvent:
    kind: Literal["hit", "trace", "report", "dispatch", "strip", "move", "pull", "warning", "heal", "expire", "copy"]
    source: str
    target: str = ""
    amount: float = 0
    meat: int = 0
    pin: float = 0
    location: Location | None = None
    at: int | None = None
    cantillation: bool = False
    program: str = ""


@dataclass
class Activation:
    started: int
    warned: int
    next_trace: int
    report_at: int
    reported: bool = False
    pin_attempted: bool = False
    dispatch_at: int | None = None
    pull_at: int = 0


@dataclass
class Ice:
    id: str
    template: IceTemplate
    location: Location
    integrity: float
    maximum: float
    attack: float
    meat_damage: int
    born: int
    affiliation: str | None = None
    target: str = ""
    phase: str = "idle"
    activations: dict[str, Activation] = field(default_factory=dict)
    next_attack: int = 0
    next_move: int = 0
    next_heal: int = 0
    shots: int = 0
    gate_open: bool = False
    gate_until_utc: float = 0
    mirror_until: int = 0
    patrol: tuple[Location, ...] = ()
    patrol_index: int = 0
    trail: list[Location] = field(default_factory=list)
    effects: Effects = field(default_factory=Effects)
    provoked: bool = False
    phase_origin: int = 0
    copied_program: str | None = None
    copy_ready_at: int = 0
    sweep_occupies_until: int = 0
    sweep_warned: dict[str, int] = field(default_factory=dict)

    @classmethod
    def spawn(cls, iid: str, template: IceTemplate, location: Location, tier: int,
              tick: int, affiliation: str | None = None) -> "Ice":
        variants = [v for v in template.tier_stats if v.tier <= tier]
        stats = max(variants, key=lambda v: v.tier) if variants else None
        hp = stats.integrity if stats else template.integrity
        move_seconds = (float(template.params.get("warning_seconds", 0)) if template.class_ == "sweeper" else
                        HUNTER_MOVE_SECONDS if template.behaviour == "hunter" else
                        DRIFT_MOVE_SECONDS if template.class_ == "drift" else MASTIFF_MOVE_SECONDS)
        return cls(iid, template, location, hp, hp, stats.attack if stats else template.attack,
                   stats.meat_damage if stats else template.meat_damage, tick, affiliation,
                   next_move=tick + ticks(move_seconds),
                   next_heal=tick + ticks(HEAL_INTERVAL_SECONDS), phase_origin=tick)

    @property
    def alive(self) -> bool:
        return self.integrity > 0

    def hidden_from(self, runner: Runner, tick: int) -> bool:
        effects = runner.effects
        return (effects.has("prg_nobody", tick)
                or self.affiliation == "halvard" and effects.has("prg_signet", tick)
                or self.template.class_ == "mastiff" and effects.has("prg_shroud", tick))

    def activate(self, runner: Runner, tick: int, cause: str = "entry") -> list[IceEvent]:
        if runner.id in self.activations or self.hidden_from(runner, tick):
            return []
        delay = 0
        if cause == "entry" and runner.effects.has("prg_sneakers", tick):
            delay += ticks(runner.effects.active["prg_sneakers"].amount)
        if self.template.class_ == "sandman" and runner.effects.has("prg_shroud", tick):
            delay += ticks(float(runner.effects.active["prg_shroud"].params.get("sandman_seconds", 0)))
        started = tick + delay
        warned = started + ticks(FIRST_WARNING_SECONDS)
        if self.template.class_ == "sweeper":
            warned = max(tick, self.sweep_warned.get(runner.id, tick) + ticks(FIRST_WARNING_SECONDS))
        params = self.template.params
        self.activations[runner.id] = Activation(started, warned, started + ticks(1),
            started + ticks(float(params.get("report_seconds", 0))),
            pull_at=started + ticks(float(params.get("pull_seconds", 0))))
        if self.template.class_ == "chorister" and not self.provoked:
            return []
        self.phase = "warning"
        return [IceEvent("warning", self.id, runner.id, max(0, warned-tick)/TICK_HZ)]

    def blocks(self, utc: float) -> bool:
        if not self.alive or self.gate_open or utc < self.gate_until_utc:
            return False
        if self.template.class_ == "turnstile":
            return True
        if self.template.class_ == "lockstep":
            period = float(self.template.params["period_seconds"])
            return utc % period >= float(self.template.params["open_seconds"])
        return False

    def signal_phase(self, tick: int) -> tuple[str, int]:
        duration = ticks(CHORISTER_PHASE_SECONDS)
        elapsed = max(0, tick-self.phase_origin)
        return ("listening", "sampling", "release")[(elapsed//duration) % 3], duration-elapsed % duration

    def hit(self, amount: float, attacker: str, tick: int) -> None:
        self.integrity = max(0, self.integrity-amount)
        if self.template.class_ == "chorister":
            if not self.provoked:
                for active in self.activations.values():
                    active.warned = tick + ticks(FIRST_WARNING_SECONDS)
                self.phase = "warning"
            self.provoked = True
        if self.template.class_ == "undertow":
            for active in self.activations.values():
                active.pull_at = tick + ticks(float(self.template.params["pull_seconds"]))
        if not self.alive:
            self.phase = "dead"

    def intercept(self, amount: float, attacker: str, tick: int, *,
                  ignore_mirror: bool = False, cantillation: bool = False) -> tuple[float, IceEvent | None]:
        if self.template.class_ == "mirror" and self.alive and tick >= self.mirror_until and not ignore_mirror:
            self.mirror_until = tick + ticks(float(self.template.params["reflect_cooldown_seconds"]))
            self.phase = "reflecting"
            return 0, IceEvent("hit", self.id, attacker, amount, location=self.location,
                               at=tick+ticks(FIRST_WARNING_SECONDS), cantillation=cantillation)
        return amount, None

    def copy(self, program: str, runner: str, tick: int) -> None:
        if self.template.class_ == "shade":
            self.copied_program, self.target = program, runner
            self.copy_ready_at = tick + ticks(FIRST_WARNING_SECONDS)

    def confirm_pin(self, target: str, tick: int) -> None:
        if target in self.activations:
            self.activations[target].dispatch_at = tick + ticks(float(self.template.params.get("pin_seconds", 0)))

    def follow(self, target: str, destination: Location) -> None:
        if self.template.behaviour == "hunter" and self.target == target:
            previous = self.trail[-1] if self.trail else self.location
            if previous != destination:
                self.trail.append(destination)

    def advance(self, tick: int, utc: float, runners: Mapping[str, Runner],
                neighbours: Mapping[Location, Sequence[Location]], rng: Random) -> list[IceEvent]:
        if not self.alive:
            return []
        events: list[IceEvent] = []
        kind, params = self.template.class_, self.template.params
        self.effects.expire(tick)
        if self.template.behaviour == "hunter":
            if self.target not in runners or tick-self.born >= ticks(float(params.get("lifetime_seconds", 180))):
                self.integrity, self.phase = 0, "gone"
                return [IceEvent("expire", self.id)]
            if self.trail and tick >= self.next_move:
                self.location = self.trail.pop(0)
                self.next_move = tick + ticks(HUNTER_MOVE_SECONDS)
                events.append(IceEvent("move", self.id, location=self.location))
        elif kind == "sweeper":
            for runner in runners.values():
                if runner.location[0] == self.location[0]:
                    self.sweep_warned.setdefault(runner.id, tick)
            if self.patrol and tick >= self.next_move:
                if self.sweep_occupies_until:
                    self.sweep_occupies_until = 0
                    self.sweep_warned = {r.id: tick for r in runners.values() if r.location[0] == self.location[0]}
                    self.next_move = tick + ticks(float(params["warning_seconds"]))
                    events.append(IceEvent("warning", self.id, amount=float(params["warning_seconds"]),
                                           location=self.patrol[(self.patrol_index+1) % len(self.patrol)]))
                else:
                    self.patrol_index = (self.patrol_index+1) % len(self.patrol)
                    self.location = self.patrol[self.patrol_index]
                    self.sweep_occupies_until = tick + ticks(SWEEPER_DWELL_SECONDS)
                    self.next_move = self.sweep_occupies_until
                    events.append(IceEvent("move", self.id, location=self.location))
            self.phase = "occupying" if self.sweep_occupies_until else "warning"
        elif self.template.behaviour == "roaming" and tick >= self.next_move:
            if self.patrol:
                self.patrol_index = (self.patrol_index+1) % len(self.patrol)
                target = self.patrol[self.patrol_index]
            else:
                choices = tuple(neighbours.get(self.location, ()))
                target = rng.choice(choices) if choices else self.location
            self.location = target
            self.next_move = tick + ticks(DRIFT_MOVE_SECONDS if kind == "drift" else MASTIFF_MOVE_SECONDS)
            events.append(IceEvent("move", self.id, location=self.location))

        present = [r for r in runners.values() if r.location == self.location and not self.hidden_from(r, tick)]
        for runner in present:
            trigger = self.template.trigger
            if (runner.alert_all or trigger in ("always", "entry") or trigger == "trace" and runner.trace >= (self.template.trigger_trace or 0)
                    or self.template.behaviour == "hunter" and runner.id == self.target):
                events.extend(self.activate(runner, tick, "trace" if runner.alert_all else "entry" if trigger == "entry" else "always"))
        if kind == "chorister" and not self.provoked:
            self.phase = self.signal_phase(tick)[0]
            return events

        for pid, active in self.activations.items():
            runner = runners.get(pid)
            if runner is None or runner.location[0] != self.location[0] or tick < active.started:
                continue
            if kind == "bluecoat" and active.dispatch_at is not None and tick >= active.dispatch_at:
                active.dispatch_at = None
                events.append(IceEvent("dispatch", self.id, pid))
            if self.hidden_from(runner, tick):
                continue
            if kind == "shiv" and runner.location == self.location and not active.reported and tick >= active.report_at:
                active.reported = True
                events.append(IceEvent("report", self.id, pid))
            if kind == "sandman" and runner.location == self.location:
                events.append(IceEvent("strip", self.id, pid))
            if kind == "undertow" and runner.location == self.location and tick >= active.pull_at:
                active.pull_at = tick + ticks(float(params["pull_seconds"]))
                events.append(IceEvent("pull", self.id, pid))
            if (kind == "ticker" or kind == "tripwire" and self.shots >= int(params.get("shots", 3))) and tick >= active.next_trace:
                active.next_trace = tick + ticks(1)
                amount = float(params.get("trace_per_second", params.get("surviving_trace_per_second", 0)))
                if kind == "ticker" and any(e.kind == "decoy" or e.params.get("gain_multiplier") for key, e in runner.effects.active.items() if runner.effects.has(key, tick)):
                    amount *= float(params.get("decoy_trace_multiplier", 1))
                events.append(IceEvent("trace", self.id, pid, amount))

        if kind == "suture" and tick >= self.next_heal:
            self.next_heal = tick + ticks(HEAL_INTERVAL_SECONDS)
            events.append(IceEvent("heal", self.id, amount=float(params["healing_per_second"]), location=self.location))
        if not self.attack or tick < self.next_attack or kind == "sweeper" and not self.sweep_occupies_until:
            return events
        if kind == "tripwire" and self.shots >= int(params.get("shots", 3)):
            self.phase = "alarm"
            return events
        candidates = [r for r in present if r.id in self.activations and tick >= self.activations[r.id].warned]
        if self.template.behaviour == "hunter":
            candidates = [r for r in candidates if r.id == self.target]
        if not candidates:
            return events
        runner = next((r for r in candidates if r.id == self.target), sorted(candidates, key=lambda r:r.id)[0])
        self.target = runner.id
        active = self.activations[runner.id]
        amount = self.attack
        if kind == "cantillation":
            amount = 0 if runner.archetype == "cantor" else max(float(params.get("damage_min", 10)), self.attack-runner.resonance/CANTILLATION_RESONANCE_DIVISOR)
        pin = float(params.get("pin_seconds", 0)) if not active.pin_attempted else 0
        active.pin_attempted = active.pin_attempted or bool(pin)
        for _ in range(int(params.get("hits", 1))):
            events.append(IceEvent("hit", self.id, runner.id, amount, self.meat_damage, pin,
                                   cantillation=kind == "cantillation"))
        if kind == "shade" and self.copied_program and tick >= self.copy_ready_at:
            events.append(IceEvent("copy", self.id, runner.id, program=self.copied_program))
            self.copied_program = None
        self.shots += 1
        if kind == "tripwire" and self.shots == int(params.get("shots", 3)):
            for activation in self.activations.values():
                activation.next_trace = tick + ticks(HEAL_INTERVAL_SECONDS)
        self.next_attack = tick + ticks(float(self.template.cooldown_seconds))
        self.phase = "attacking"
        return events
