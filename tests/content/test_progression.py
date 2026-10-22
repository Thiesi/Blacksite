"""Game 3.3-3.5 and 8.5: content schedules are validated and explicit."""

from dataclasses import replace
from pathlib import Path

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.server.rules.character import grade_threshold


def shipped():
    return load_content(Path(__file__).resolve().parents[2]/"src/blacksite/content")


def test_game_3_4_grade_titles_and_thresholds_have_no_creation_benefit():
    tree = shipped()
    grades = {row.grade: row for row in tree.grades.values()}
    assert set(grades) == set(range(1, 31))
    assert grades[1].title == "Wake" and grades[5].title == "Ninety-Day"
    assert [grade_threshold(g) for g in (1, 5, 10, 30)] == [0, 1500, 5500, 46500]
    assert all(row.promotion and "—" not in row.promotion for row in grades.values())


def test_game_3_5_content_schedule_matches_all_meaningful_use_rates():
    skills = shipped().skills
    expected = {"kinetic": ("frame", "weapon_hit", .2), "melee": ("frame", "melee_hit", .3),
        "armour": ("frame", "armour_absorb", .1), "energy": ("nerve", "weapon_hit", .2),
        "stealth": ("nerve", "stealth_second", .05), "drones": ("nerve", "drone_command", .1),
        "lattice": ("cortex", "authored_cell", .05), "programs": ("cortex", "program_change", .15),
        "fabrication": ("cortex", "fabricate", 1), "hymns": ("resonance", "hymn_restore", .15),
        "dissonance": ("resonance", "dissonance_threat", .15), "listening": ("resonance", "hidden_authored", .5)}
    assert set(skills) == set(expected)
    for line, (attribute, action, gain) in expected.items():
        assert skills[line].attribute == attribute and skills[line].uses == {action: gain}
        assert skills[line].maximum == 100 and skills[line].daily_cap == 2


def test_game_8_5_portable_rigs_are_explicit_and_surgery_cannot_be_skipped():
    tree = shipped()
    portable = {t.id for t in tree.items.values() if t.implant and t.implant.portable}
    assert portable == {"item_rig_portable_ow_brick", "item_rig_portable_ow_slab", "item_rig_portable_halvard_case"}
    bad = tree.items["imp_rig_ow_deepwater"]
    tree.items[bad.id] = replace(bad, implant=replace(bad.implant, portable=True))
    assert any("portable rig" in p.message for p in validate(tree))


def test_game_3_4_validator_rejects_duplicate_grade_and_missing_skill():
    tree = shipped()
    tree.grades["grade-5"] = replace(tree.grades["grade-5"], grade=4)
    del tree.skills["drones"]
    problems = validate(tree)
    assert any("grades 1-30 exactly once" in p.message for p in problems)
    assert any("twelve game 3.3" in p.message for p in problems)


def test_game_5_3_all_eight_drone_tools_have_typed_catalog_behaviour():
    tree = shipped()
    drones = [t.drone for t in tree.items.values() if t.drone]
    assert len(drones) == 8
    assert all(d.attack or d.weapon or d.effects for d in drones)
    assert all(d.move_ms == 200 and d.control_range > 0 for d in drones)
    assert all(d.attack.melee or d.attack.accuracy == 75 for d in drones if d.attack)
    assert tree.items["drn_halvard_hound"].drone.hunt
    assert tree.items["drn_halvard_hound"].drone.attack.damage == 30
