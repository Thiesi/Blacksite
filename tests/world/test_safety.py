"""Safety flags consumed by character logout; game design §2 and §5.1."""

from blacksite.server.world.safety import safety_at
from tests.character_helpers import place
from tests.world.test_exits import character_game


def test_pocket_inside_contested(world):
    zone = world.zones["vatside-clinics"]
    assert safety_at(zone,(10,8)) == "pocket"
    assert safety_at(zone,(32,18)) == "contested"


def test_safety_word_on_view(content_tree):
    game,caller = character_game(content_tree)
    place(game,caller,"vatside-clinics",(10,8))
    body = game.core.characters.sim.views[caller.session.id].previous["body"]
    assert body["me"]["safety"] == "pocket"


def test_logout_instant_in_pocket(content_tree):
    game,caller = character_game(content_tree)
    place(game,caller,"vatside-clinics",(10,8))
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    game.core.sessions.disconnect(caller.session)
    assert avatar.actor.id not in game.core.world.actors
    assert not game.core.characters.sleepers
