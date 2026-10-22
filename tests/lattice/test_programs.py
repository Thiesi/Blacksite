"""Game 6.7/17.2: capacity, effects and acquisition are real choices."""

from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.server.lattice.programs import (
    Effects, attack_damage, bind, can_acquire, can_cast, cast_ticks,
    occupied_slots, trace_gain,
)


@pytest.fixture(scope="module")
def programs():
    return load_content(Path(__file__).parents[2] / "src/blacksite/content").programs


def test_design_17_2_all_35_numeric_rows_match_the_canon(programs, repo_root):
    section = (repo_root / "docs/design/00-game-design.md").read_text(encoding="utf-8").split(
        "### 17.2 Programs", 1)[1].split("### 17.3 ICE", 1)[0]
    rows = [[s.strip() for s in line.strip("|").split("|")]
            for line in section.splitlines() if line.startswith("| `prg_")]
    assert len(rows) == 35 and set(programs) == {r[0].strip("`") for r in rows}
    for pid, name, kind, tier, slots, cast, cooldown, effect, price in rows:
        program = programs[pid.strip("`")]
        assert (program.name, program.class_, program.tier, program.slots, program.price) == (
            name, kind, int(tier), int(slots), int(price))
        assert program.cast_seconds == (None if cast == "—" else float(cast.removesuffix(" s")))
        assert program.cooldown_seconds == (None if cooldown in ("—", "single use") else float(cooldown.removesuffix(" s")))
        assert program.description == effect


def test_design_6_7_two_slot_program_cannot_be_overbound(programs):
    rig = ("prg_lance", None, "prg_umbrella")
    assert occupied_slots(rig, programs) == {0: 0, 1: 0, 2: 2}
    with pytest.raises(ValueError, match="larger program"):
        bind(rig, 1, "prg_pick", set(programs), programs)
    with pytest.raises(ValueError, match="fit"):
        bind((None, None, None), 2, "prg_lance", set(programs), programs)
    with pytest.raises(ValueError, match="own complete"):
        occupied_slots(("prg_pick", "prg_pick", None), programs)
    assert bind(rig, 0, None, set(programs), programs) == (None, None, "prg_umbrella")


def test_design_17_2_hornets_depletes_one_umbrella_budget(programs):
    effects = Effects()
    effects.install(programs["prg_umbrella"], 0)
    hits = [effects.receive(4).integrity for _ in range(5)]
    assert hits == [0, 0, 0, 1, 4]
    assert effects.shield is None


def test_design_17_2_slicker_and_bunker_protect_once(programs):
    effects = Effects()
    effects.install(programs["prg_slicker"], 0)
    assert effects.receive(10, pin_seconds=4).pin_seconds == 0
    assert effects.receive(10, pin_seconds=4).pin_seconds == 4
    effects.install(programs["prg_bunker"], 0)
    assert effects.receive(25, 10).meat == 0
    assert effects.receive(25, 10).meat == 10
    assert effects.shield.budget == 10
    effects.install(programs["prg_umbrella"], 0)
    assert effects.shield.budget == 15  # Replaces remaining Bunker budget.


def test_design_17_2_wetsuit_halves_before_absorbing_and_decoy_takes_a_hit(programs):
    effects = Effects()
    effects.install(programs["prg_wetsuit"], 0)
    assert effects.receive(25, cantillation=True).integrity == 0
    assert effects.shield.budget == 27.5
    effects.install(programs["prg_understudy"], 0)
    hit = effects.receive(100, 25)
    assert (hit.integrity, hit.meat, effects.decoy) == (0, 0, 0)
    assert effects.shield.budget == 27.5


def test_design_6_7_shield_replacement_adds_budget_or_a_tactical_protection(programs):
    effects = Effects()
    effects.install(programs["prg_bunker"], 0)
    effects.receive(5)
    with pytest.raises(ValueError, match="already gives more"):
        effects.install(programs["prg_umbrella"], 1)
    assert effects.shield.budget == 55 and effects.shield.black_meat_once
    effects.install(programs["prg_wetsuit"], 1)
    assert effects.shield.budget == 40
    assert effects.shield.cantillation_multiplier == .5
    effects.install(programs["prg_slicker"], 2)
    assert effects.shield.budget == 25 and effects.shield.pin_once


def test_design_17_2_loaders_stack_after_tar_cancellation_and_round_up(programs):
    effects = Effects()
    effects.install(programs["prg_overclock"], 0)
    effects.install(programs["prg_caffeine"], 0)
    assert cast_ticks(programs["prg_redline"], effects, 1, tar=True, sandman=True) == 6
    assert cast_ticks(programs["prg_pick"], effects, 1, tar=True) == 5
    effects.expire(100)
    assert not effects.has("prg_overclock", 100)
    assert effects.has("prg_caffeine", 100)  # Waiting cannot spend the next cast.
    assert cast_ticks(programs["prg_pick"], effects, 100, tar=True) == 12
    with pytest.raises(ValueError, match="while loaded"):
        cast_ticks(programs["prg_ledger"], effects, 100)


def test_design_17_2_acquisition_is_not_a_recurring_cast_requirement(programs):
    cantillation = programs["prg_choir_cantillation_2"]
    assert can_acquire(cantillation, "cantor", {"choir": 50}, set())
    assert not can_acquire(cantillation, "ghost", {"choir": 100}, set())
    assert not can_acquire(cantillation, "cantor", {"choir": 49}, set())
    assert can_cast(cantillation, "cantor", {})
    blackout = programs["prg_blackout"]
    assert not can_acquire(blackout, "ghost", {}, {blackout.id})
    assert can_cast(blackout, "ghost", {})
    fragment = programs["prg_residual_fragment"]
    assert not can_cast(fragment, "ghost", {})
    assert can_cast(fragment, "ghost", {fragment.id: 1})
    assert not can_acquire(fragment, "ghost", {}, set())
    assert can_acquire(fragment, "ghost", {}, set(), bound_loan=True)


def test_design_17_2_caffeine_is_consumed_by_one_accepted_cast(programs):
    effects = Effects()
    effects.install(programs["prg_overclock"], 0)
    effects.install(programs["prg_caffeine"], 0)
    assert cast_ticks(programs["prg_pick"], effects, 1) == 5
    effects.consume_next_cast(1)
    assert cast_ticks(programs["prg_pick"], effects, 1) == 6
    assert effects.has("prg_overclock", 1)


def test_design_17_2_attack_trace_replaces_default_and_has_explicit_suppression(programs):
    effects = Effects()
    assert programs["prg_burn"].trace_cost == 15
    assert programs["prg_blackout"].trace_cost == 25
    assert trace_gain(15, effects, 0, fixed=True) == 15
    effects.install(programs["prg_smoke"], 0)
    assert trace_gain(15, effects, 1, fixed=True, multiplier=.9) == 11.25
    assert trace_gain(3, effects, 1, multiplier=.9) == pytest.approx(2.025)
    assert trace_gain(15, effects, 1, suppressed=True) == 0
    effects.install(programs["prg_nobody"], 1)
    assert trace_gain(25, effects, 2, fixed=True) == 0


def test_design_17_2_drill_executes_and_cantillation_uses_resonance(programs):
    assert attack_damage(programs["prg_drill"], 30) == 45
    assert attack_damage(programs["prg_drill"], 31) == 30
    assert attack_damage(programs["prg_choir_cantillation_1"], 100, 45) == 29
    assert attack_damage(programs["prg_choir_cantillation_2"], 100, 45) == 55
