"""Game 6.7/17.3: step actual warnings, counters and defender deadlines."""

from pathlib import Path
from random import Random

import pytest

from blacksite.content.loader import load_content
from blacksite.server.lattice.ice import Ice, Runner
from blacksite.server.lattice.programs import Effects


@pytest.fixture(scope="module")
def catalog():
    return load_content(Path(__file__).parents[2] / "src/blacksite/content")


def defender(catalog, kind, tier=3):
    return Ice.spawn("node:ice:"+kind, catalog.ice["ice_"+kind], ("core", "entry"), tier, 0)


def runner(catalog, program=None, archetype="ghost", trace=0):
    effects = Effects()
    if program:
        effects.install(catalog.programs[program], 0)
    return Runner("alice", ("core", "entry"), trace, 20, archetype, effects)


def step(ice, who, start, end):
    rng = Random(1)
    return [(tick, event) for tick in range(start, end+1)
            for event in ice.advance(tick, tick/10, {who.id: who}, {}, rng)]


def test_design_17_3_tripwire_fires_three_times_then_alarms(catalog):
    ice, who = defender(catalog, "tripwire"), runner(catalog)
    events = step(ice, who, 0, 65)
    assert [(t, e.amount) for t, e in events if e.kind == "hit"] == [(20, 8), (30, 8), (40, 8)]
    assert [(t, e.amount) for t, e in events if e.kind == "trace"] == [(50, 10), (60, 10)]
    assert ice.phase == "alarm"


def test_design_17_2_sneakers_shroud_and_nobody_delay_real_attacks(catalog):
    tripwire = defender(catalog, "tripwire")
    events = step(tripwire, runner(catalog, "prg_sneakers"), 0, 50)
    assert [t for t, e in events if e.kind == "hit"] == [50]
    mastiff = defender(catalog, "mastiff")
    events = step(mastiff, runner(catalog, "prg_shroud"), 0, 80)
    assert [t for t, e in events if e.kind == "hit"] == [80]
    tripwire = defender(catalog, "tripwire")
    events = step(tripwire, runner(catalog, "prg_nobody"), 0, 70)
    assert [t for t, e in events if e.kind == "hit"] == [70]


def test_design_17_3_ticker_touch_and_live_decoy_counter(catalog):
    ice, who = defender(catalog, "ticker"), runner(catalog, "prg_smoke")
    assert not any(e.kind == "trace" for _, e in step(ice, who, 0, 20))
    ice.activate(who, 20, "touch")
    events = step(ice, who, 20, 40)
    assert [(t, e.amount) for t, e in events if e.kind == "trace"] == [(30, .5), (40, .5)]


def test_design_17_3_bluecoat_requires_trace_and_dispatches_only_after_real_pin(catalog):
    ice, who = defender(catalog, "bluecoat"), runner(catalog, trace=49)
    assert not any(e.kind == "hit" for _, e in step(ice, who, 0, 20))
    who.trace = 50
    events = step(ice, who, 21, 41)
    hit = next(e for _, e in events if e.kind == "hit")
    assert hit.pin == 4
    ice.confirm_pin(who.id, 41)
    assert [t for t, e in step(ice, who, 42, 81) if e.kind == "dispatch"] == [81]
    protected, who = defender(catalog, "bluecoat"), runner(catalog, "prg_slicker", trace=50)
    hit = next(e for _, e in step(protected, who, 0, 20) if e.kind == "hit")
    assert who.effects.receive(hit.amount, pin_seconds=hit.pin).pin_seconds == 0
    assert not any(e.kind == "dispatch" for _, e in step(protected, who, 21, 80))


def test_design_17_3_shiv_report_can_be_stopped_before_four_seconds(catalog):
    ice, who = defender(catalog, "shiv"), runner(catalog)
    assert not any(e.kind == "report" for _, e in step(ice, who, 0, 39))
    assert [t for t, e in step(ice, who, 40, 90) if e.kind == "report"] == [40]
    ice = defender(catalog, "shiv")
    step(ice, who, 0, 12)
    ice.hit(45, who.id, 12)
    assert not step(ice, who, 13, 90)


def test_design_17_3_lockstep_uses_injected_schedule_and_keys_open_turnstile(catalog):
    ice = defender(catalog, "lockstep")
    assert not ice.blocks(9.9)
    assert ice.blocks(10) and ice.blocks(59.9)
    assert not ice.blocks(60)
    ice.gate_until_utc = 35
    assert not ice.blocks(30) and ice.blocks(35)
    gate = defender(catalog, "turnstile")
    assert gate.blocks(0)
    gate.gate_open = True
    assert not gate.blocks(0)


def test_design_17_3_mirror_announces_reflection_and_lance_bypasses_it(catalog):
    ice = defender(catalog, "mirror", 4)
    damage, reflection = ice.intercept(120, "alice", 0)
    assert damage == 0 and reflection.amount == 120 and reflection.at == 20
    assert ice.intercept(10, "alice", 10) == (10, None)
    assert ice.intercept(45, "alice", 50, ignore_mirror=True) == (45, None)
    assert ice.intercept(10, "alice", 50)[0] == 0


@pytest.mark.parametrize("tier,hp,damage,meat", [(3,80,20,0), (4,120,25,0), (5,150,30,15)])
def test_design_17_3_hound_tiers_follow_exact_target_and_expire(catalog, tier, hp, damage, meat):
    ice, who = defender(catalog, "hound", tier), runner(catalog, trace=100)
    ice.target = who.id
    assert (ice.integrity, ice.attack, ice.meat_damage) == (hp, damage, meat)
    step(ice, who, 0, 5)
    who.location = ("district", "public-approach")
    ice.follow(who.id, who.location)
    step(ice, who, 6, 10)
    assert ice.location == who.location
    assert any(e.kind == "hit" for _, e in step(ice, who, 11, 20))
    assert any(e.kind == "expire" for _, e in step(ice, who, 1800, 1800))


def test_design_17_3_cantillation_resonance_and_cantor_immunity(catalog):
    who = runner(catalog)
    hit = next(e for _, e in step(defender(catalog, "cantillation"), who, 0, 20) if e.kind == "hit")
    assert hit.amount == 20
    who.archetype = "cantor"
    hit = next(e for _, e in step(defender(catalog, "cantillation"), who, 0, 20) if e.kind == "hit")
    assert hit.amount == 0


def test_design_6_7_undertow_channel_restarts_on_a_hit(catalog):
    ice, who = defender(catalog, "undertow"), runner(catalog)
    assert not any(e.kind == "pull" for _, e in step(ice, who, 0, 20))
    ice.hit(10, who.id, 20)
    assert not any(e.kind == "pull" for _, e in step(ice, who, 21, 49))
    assert [t for t, e in step(ice, who, 50, 50) if e.kind == "pull"] == [50]


def test_design_6_6_chorister_is_a_procedure_until_attacked(catalog):
    ice, who = defender(catalog, "chorister"), runner(catalog)
    assert not any(e.kind == "hit" for _, e in step(ice, who, 0, 70))
    assert ice.signal_phase(0) == ("listening", 50)
    assert ice.signal_phase(50) == ("sampling", 50)
    assert ice.signal_phase(100) == ("release", 50)
    ice.hit(10, who.id, 70)
    assert not any(e.kind == "hit" for _, e in step(ice, who, 71, 89))
    assert any(e.kind == "hit" for _, e in step(ice, who, 90, 90))


def test_design_6_7_sweeper_warns_then_occupies_without_invented_invulnerability(catalog):
    ice, who = defender(catalog, "sweeper", 4), runner(catalog)
    ice.patrol = (("core","entry"), ("core","next"))
    assert not any(e.kind == "hit" for _, e in step(ice, who, 0, 49))
    who.location = ("core", "next")
    assert any(e.kind == "hit" for _, e in step(ice, who, 50, 50))
    events = step(ice, who, 51, 70)
    assert any(e.kind == "warning" and e.amount == 5 for _, e in events)
    assert ice.phase == "warning"
    ice.hit(250, who.id, 71)
    assert not ice.alive
