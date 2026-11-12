"""#221/#223: the grade 5 price notice, once per character.

At grade 5 contested-zone grade protection ends (bible 4.3). The notice is
the S44 price-notice path, separate from the grade's promotion line.
"""

from karst41.content.loader import load_content
from karst41.door.cells import display_width
from karst41.door.model import Display
from karst41.door.present.chrome import NOTICE_SECONDS
from karst41.server.progression import Award
from karst41.server.protocol import Frame
from karst41.server.rules.character import GRADE5_NOTICE
from tests.character_helpers import create
from tests.harness import HeadlessServer

# Presentation lead's wording, word for word; fits a menu/talk hint row.
TEXT = "Grade 5: G5+ can attack you in CONTESTED zones."
MENU_HINT_ROOM = 51  # 78 cells less "  Esc/B back  Ctrl-X leaves" (80x24).


def toasts(frames):
    return [frame.data for frame in frames if frame.type == "toast"]


def promoted(old: int, new: int) -> Award:
    return Award(10, old, new, 3 * (new - old), 100, False)


def game_with(repo_root, uid=1):
    game = HeadlessServer(load_content(repo_root/"src/karst41/content"), character_state={})
    caller = game.connect({"user_id": uid, "handle": "Grade", "node_name": "S221"})
    create(game, caller, card="none")
    game.frames_for(caller)
    return game, caller, game.core.characters.players[caller.session.player_id]


def test_221_grade5_notice_text_and_fit():
    assert GRADE5_NOTICE == TEXT
    assert display_width(TEXT) <= MENU_HINT_ROOM


def test_221_grade5_notice_once_per_character_as_a_price_notice(repo_root):
    game, caller, player = game_with(repo_root)
    game.core.progression.notify_reward(player, promoted(3, 4))
    assert not [t for t in toasts(game.frames_for(caller)) if t["text"] == TEXT]
    game.core.progression.notify_reward(player, promoted(4, 5))
    shown = [t for t in toasts(game.frames_for(caller)) if t["text"] == TEXT]
    assert len(shown) == 1 and shown[0]["price"] is True and shown[0]["kind"] == "notice"
    game.core.progression.notify_reward(player, promoted(4, 6))  # Never again for this character.
    game.core.progression.notify_reward(player, promoted(5, 6))
    assert not [t for t in toasts(game.frames_for(caller)) if t["text"] == TEXT]
    assert player.progress["grade5_notice"] == "shown"


def test_221_grade5_reached_offline_shows_at_the_next_attach(repo_root):
    game, caller, player = game_with(repo_root)
    game.core.sessions.disconnect(caller.session)
    game.step(2)
    game.core.progression.notify_reward(player, promoted(4, 5))
    assert player.progress["grade5_notice"] == "due"
    again = game.connect({"user_id": 1, "handle": "Grade", "node_name": "S221"})
    game.step(2)
    shown = [t for t in toasts(game.frames_for(again)) if t["text"] == TEXT]
    assert len(shown) == 1 and shown[0]["price"] is True
    assert player.progress["grade5_notice"] == "shown"
    saves = [e for e in game.commit_characters() if e["action"] == "save" and e["player"]["id"] == player.id]
    assert saves[-1]["player"]["progress"]["grade5_notice"] == "shown"  # Persisted, not left to a checkpoint.


def test_221_grade5_notice_held_in_header_counts_from_its_return(info):
    """A promotion mid-fight: the notice waits in the header, then returns whole."""
    display = Display(info, presentation=True)
    me = {"zone_name": "Vatside", "safety": "contested", "clock": "21:00"}
    threatened = {"warning": "", "relation": "hostile"}  # A fight: no truce warning, no other notice.
    display.receive(Frame("view", {"rev": 1, "kind": "zone", "body": {"me": me, "target": threatened}}), 0)
    display.receive(Frame("toast", {"text": TEXT, "role": "warning", "seconds": 4, "kind": "notice",
                                    "price": True}), 0)
    assert display.toast is not None and display.toast[0] == TEXT and display._notice_to_header(0)
    display.update(30, 30)
    display.key("x", 30)  # A key while it sits in the header doesn't count.
    assert display.toast is not None
    calm = {"warning": "", "relation": "neutral"}
    display.receive(Frame("view", {"rev": 2, "kind": "zone", "body": {"me": me, "target": calm}}), 31)
    display.update(31, 31)
    assert not display._notice_to_header(31)
    assert display.toast is not None and display.toast[0] == TEXT
    assert display.toast[2] >= 31 + NOTICE_SECONDS - 1
    display.key("x", 32)
    display.update(32 + NOTICE_SECONDS, 32 + NOTICE_SECONDS)
    assert display.toast is None


def test_221_side_panel_grade_follows_the_promotion_at_once(repo_root):
    """A promotion with no other change in the zone still republishes me.grade."""
    game, caller, player = game_with(repo_root)
    game.step(4)
    game.frames_for(caller)
    player.update_progression(1500)
    game.core.progression.notify_reward(player, promoted(4, 5))
    game.step(2)
    views = [f for f in game.frames_for(caller) if f.type == "view"]
    assert views and views[-1].data["body"]["me"]["grade"] == 5
