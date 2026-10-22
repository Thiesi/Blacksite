"""Game 6.7: closing a transport never bypasses a dangerous escape."""

from dataclasses import replace

from tests.lattice.test_engine import actor, jack, runners


def gated(game, client):
    presence = jack(game, client)
    presence.cell = next(c.id for c in game.core.lattice.sectors.records[presence.sector].cells
                         if c.access_kind == "gated")
    return presence


def test_game_6_7_disconnect_keeps_body_until_bounded_escape(runners):
    game, a, b, c = runners
    presence = gated(game, a)
    body = actor(game, a)
    game.core.sessions.disconnect(a.session)
    assert presence.player_id in game.core.lattice.presences
    assert body.stance == "jacked" and game.core.world.actors[body.id] is body
    for _ in range(3):
        body.behaviour["hit_serial"] = body.behaviour.get("hit_serial", 0) + 1
        game.step(5)
    assert presence.escape.interruptions == 3
    game.step(presence.escape.until_tick - game.clock.now_tick())
    assert body.id not in game.core.lattice.presences
    assert not game.core.lattice.orphans
    assert body.zone is None  # This fixture's physical body is protected.


def test_game_6_7_reconnect_reuses_live_body_and_escape(runners):
    game, a, b, c = runners
    presence = gated(game, a)
    body = actor(game, a)
    game.core.sessions.disconnect(a.session)
    body.health -= 7
    health, position, escape = body.health, body.position, presence.escape
    fresh = game.connect(a.session.door_info)
    assert actor(game, fresh) is body
    assert body.position == position and body.health == health and body.stance == "jacked"
    assert game.core.lattice.presences[body.id] is presence and presence.escape is escape
    assert fresh.session.subscribed == presence.sector
    assert a.session.id not in game.core.world.zones[body.zone].listeners
    assert not game.core.lattice.orphans
    game.step(escape.until_tick - game.clock.now_tick())
    assert body.stance == "normal" and body.id not in game.core.lattice.presences


def test_game_6_7_raised_cap_chooser_does_not_retire_different_body(runners):
    game, a, b, c = runners
    presence = gated(game, a)
    body = actor(game, a)
    chars = game.core.characters
    game.core.sessions.disconnect(a.session)
    chars.cap = 2
    # Two characters of one identity: the second is an explicit test fixture.
    original = chars.players[body.id]
    second = replace(original, id=body.id + ":second", name="Other body", progress={})
    chars.players[second.id] = second
    fresh = game.connect(a.session.door_info)
    assert fresh.session.player_id is None and body.id in game.core.lattice.orphans
    chars.attach(fresh.session, second)
    other = actor(game, fresh)
    game.step(presence.escape.until_tick - game.clock.now_tick())
    assert chars.sim.avatars[fresh.session.user_id].actor is other
    assert other.zone and other.stance == "normal" and body.zone is None
    assert fresh.session.player_id == second.id


def test_game_6_7_shutdown_flushes_disconnected_escape(runners):
    game, a, b, c = runners
    presence = gated(game, a)
    body = actor(game, a)
    game.core.sessions.disconnect(a.session)
    presence.integrity = 37
    game.core.shutdown()
    assert not game.core.lattice.presences and not game.core.lattice.orphans
    assert game.core.characters.players[body.id].progress["lattice"]["integrity"] == 37
    assert body.stance != "jacked"


def test_game_6_7_losing_portable_rig_does_not_expand_native_rig(runners):
    game, a, b, c = runners
    player = game.core.characters.players[a.session.player_id]
    player.archetype = "ghost"
    player.rig = {"slots": ["prg_pick", "prg_umbrella", None, None, None, None]}
    presence = jack(game, a)
    assert len(presence.rig) == game.core.loop.content.starts["ghost"].rig_slots == 3
