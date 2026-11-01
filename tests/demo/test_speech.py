"""Demo only: ambient barks as log lines on demo/sodium-row-evening."""

from tests.demo.test_truce_standin import boot, body, spawn
from tests.character_helpers import place


def speech(caller):
    return [line for line in caller.session.log_ring if line.get("kind") == "speech"]


def test_a_nearby_talker_barks_once_per_interval(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, "sodium-row", (40, 12))
    spawn(game, "sodium-row", "npc-row-card-player", (44, 12), group="cards")
    game.step(3)
    said = speech(caller)
    assert len(said) == 1
    game.step(20)
    assert len(speech(caller)) == 1  # the bark interval holds


def test_out_of_earshot_and_demo_off_stay_silent(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch, demo=False)
    place(game, caller, "sodium-row", (40, 12))
    spawn(game, "sodium-row", "npc-row-card-player", (44, 12), group="cards")
    game.step(3)
    assert not speech(caller)


def test_one_ambient_line_per_caller_per_gap(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, "sodium-row", (40, 12))
    for i, x in enumerate((43, 45, 47)):
        spawn(game, "sodium-row", "npc-row-card-player" if i == 0 else "npc-row-kestrel-crew", (x, 12), group=f"talk{i}")
    game.step(5)
    assert len(speech(caller)) == 1  # three talkers in earshot, one line


def test_no_barks_while_in_combat(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, "sodium-row", (40, 12))
    body(game, caller).cooldowns["combat"] = 10**9  # in combat before the talker arrives
    spawn(game, "sodium-row", "npc-row-card-player", (44, 12), group="cards")
    game.step(5)
    assert not speech(caller)
