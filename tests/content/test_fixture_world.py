"""S02: the fixture world's numbers come from the design (00-game-design.md
sections 17.1-17.3 and 9.4), and the validator CLI reports it."""

import shutil
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.content.validate import main
from tests.content.support import FIXTURE_WORLD


@pytest.fixture(scope="module")
def tree():
    return load_content(FIXTURE_WORLD)


def test_sidearm_matches_17_1(tree) -> None:
    item = tree.items["wpn_kestrel_sidearm"]
    w = item.weapon
    assert (w.range, w.damage, w.cooldown, w.accuracy, w.ammo, w.damage_type) == (6, 12, 0.8, 55, "ammo_9x", "kinetic")
    assert (item.weight, item.base_price, item.tier) == (1.0, 120, 1)


def test_ammo_coverall_patch_match_17_1(tree) -> None:
    ammo = tree.items["ammo_9x"]
    assert (ammo.stack_max, ammo.base_price) == (50, 25)
    coverall = tree.items["arm_wake_coverall"]
    a = coverall.armour.armour
    assert (a.kinetic, a.energy, a.chemical, a.dissonance) == (2, 2, 4, 0)
    assert (coverall.weight, coverall.base_price) == (1.0, 0)
    patch = tree.items["con_sablier_patch"]
    assert patch.consumable.effects == {"health": 25} and patch.base_price == 40


def test_programs_match_17_2(tree) -> None:
    rows = {p.id: (p.tier, p.slots, p.cast_seconds, p.cooldown_seconds, p.effect.amount, p.price)
            for p in tree.programs.values()}
    assert rows == {
        "prg_pick": (1, 1, 0.8, 1.0, 10, 150),
        "prg_umbrella": (1, 1, 0.5, 4.0, 15, 200),
        "prg_skeleton": (1, 1, 1.5, 5, 0, 200),
    }


def test_ice_matches_17_3(tree) -> None:
    trip, tick = tree.ice["ice_tripwire"], tree.ice["ice_ticker"]
    assert (trip.integrity, trip.attack, trip.cooldown_seconds, trip.trigger, trip.black) == (20, 8, 1.0, "entry", False)
    assert (tick.integrity, tick.attack, tick.trigger, tick.black) == (15, 0, "touch", False)


def test_first_job_reward_matches_9_4(tree) -> None:
    reward = tree.contracts["fx-first-job"].reward
    assert reward.chits == (200, 200) and reward.xp == 100
    assert reward.standing_mode == "explicit" and set(reward.standing.values()) == {5}


def test_fixture_shape_matches_s02(tree) -> None:
    sizes = {z: (v.width, v.height, v.meta.safety) for z, v in tree.zones.items()}
    assert sizes == {"fx-safe": (40, 20, "safe"), "fx-street": (60, 24, "contested"), "fx-open": (40, 20, "open")}
    assert tree.zones["fx-street"].meta.pockets
    assert len(tree.sectors["fx-sector"].cells) == 5
    assert (tree.cores["fx-core-a"].tier, tree.cores["fx-core-b"].tier) == (1, 2)
    control = tree.cores["fx-core-a"].rooms[2].controls[0]
    assert (control.target.zone, control.target.object) == ("fx-street", "fx-street-gate")
    assert tree.asymmetries == (("fx-alpha", "fx-beta"),)
    assert tree.bundles["fx-world"].status == "active"


def test_cli_reports_ok(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(FIXTURE_WORLD)]) == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("ok, 3 zones, 1 sector, 2 cores, hash ")
    assert len(out.rsplit(" ", 1)[1]) == 64


def test_cli_reports_problems(scratch_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = scratch_dir / "world"
    shutil.copytree(FIXTURE_WORLD, root)
    meta = root / "zones" / "fx-street.json"
    meta.write_text(meta.read_text(encoding="utf-8").replace('"target_zone": "fx-safe"', '"target_zone": "nowhere"'),
                    encoding="utf-8", newline="\n")
    assert main([str(root)]) == 1
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2 and lines[-1] == "1 problem"
    assert lines[0].startswith("content/zones/fx-street.json:") and "exit to-safe" in lines[0]
