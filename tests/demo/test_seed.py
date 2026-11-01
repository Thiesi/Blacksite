"""Demo only: the playtest seed edits a saved character through storage."""

import importlib.util
from copy import deepcopy
from pathlib import Path

from blacksite.content.loader import load_content
from blacksite.server.rules.character import health_max
from blacksite.server.storage.db import Storage
from tests.character_helpers import create, state
from tests.harness import HeadlessServer

ROOT = Path(__file__).resolve().parents[2]


def seed_main():
    spec = importlib.util.spec_from_file_location("demo_seed", ROOT/"scripts/demo_sodium/seed.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def test_seed_prepares_a_playtest_character(tmp_path):
    content = load_content(ROOT/"src/blacksite/content")
    game = HeadlessServer(deepcopy(content), character_state={})
    caller = game.connect()
    create(game, caller, name="Ash", card="none")
    storage = Storage(tmp_path/"world.db", game.clock)
    live = state(game)
    for row in live["players"]:
        storage.mark_dirty("players", row["id"], row)
    for user, identity in live["identities"].items():
        storage.mark_dirty("identities", user, identity)
    storage.flush_now()
    storage.close()
    before = next(p for p in live["players"] if p["name"] == "Ash")

    assert seed_main()(["--install-dir", str(tmp_path), "--name", "Ash", "--grade", "5",
                        "--faction", "kestrel", "--completed", "vesper-first-thing"]) == 0

    storage = Storage(tmp_path/"world.db", game.clock)
    saved = storage.character_state()
    storage.close()
    ash = next(p for p in saved["players"] if p["name"] == "Ash")
    assert ash["grade"] == 5 and ash["faction"] == "kestrel" and ash["standing"]["kestrel"] >= 30
    assert ash["legal_at"]
    # The game's grade-up path ran: Vitals rose, grade points were granted, health is full.
    assert ash["attributes"]["vitals"] > before["attributes"]["vitals"]
    assert ash["progress"].get("points", 0) > before["progress"].get("points", 0)
    assert ash["health"] == health_max(ash["attributes"]["vitals"])
    assert "vesper-first-thing" in saved["contracts"]["engine"]["completed"][ash["id"]]
    restarted = HeadlessServer(deepcopy(content), character_state=saved)
    player = restarted.core.characters.players[ash["id"]]
    assert player.grade == 5 and player.faction == "kestrel"


def test_seed_refuses_an_unknown_name(tmp_path):
    content = load_content(ROOT/"src/blacksite/content")
    game = HeadlessServer(deepcopy(content), character_state={})
    storage = Storage(tmp_path/"world.db", game.clock)
    storage.close()
    assert seed_main()(["--install-dir", str(tmp_path), "--name", "Nobody"]) == 2
