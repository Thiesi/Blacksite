"""Game 6.5/6.6: seeded live scenes, visible procedures and free escape."""

from blacksite.server.lattice.silt import generate
from blacksite.server.lattice.silt_scene import BandGraph
from tests.lattice.test_engine import actor, intent, jack, runners


def descend(game, client):
    presence = jack(game, client)
    # Scene isolation: S13 separately tests the public route to this cell.
    presence.sector = "lat-chapel-ward"
    presence.cell = next(c.id for c in game.core.lattice.sectors.records[presence.sector].cells
                         if c.kind == "descent")
    intent(game, client, "lat.descend", risk=True)
    assert presence.descent is None and game.core.commerce.pending
    game.commit_commerce()
    game.step()
    assert presence.descent and presence.depth == 0
    return presence


def test_game_6_5_any_public_loan_rig_descends_only_after_nonce_commit(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    assert len(presence.rig) == 3
    presence.sector = "lat-chapel-ward"
    presence.cell = next(c.id for c in game.core.lattice.sectors.records[presence.sector].cells if c.kind == "descent")
    intent(game, a, "lat.descend", risk=True)
    game.commit_commerce(error=True)
    assert presence.descent is None and game.core.lattice.sources.nonce == 0
    intent(game, a, "lat.descend", risk=True)
    effects = game.commit_commerce()
    assert effects[0]["lattice_state"]["nonce"] == game.core.lattice.sources.nonce == 1
    assert presence.descent and len(presence.rig) == 3
    game.step(15)
    assert presence.trace == 0


def test_game_6_5_bands_have_visible_continuation_and_risers_after_undertow(runners):
    game, a, b, c = runners
    presence = descend(game, a)
    encounters = game.core.lattice.encounters
    for depth in range(5):
        encounters.enter_band(presence, depth)
        graph = encounters.core(presence).graph
        assert presence.room == graph.band.riser
        assert graph.band.route(presence.room, graph.band.riser)
        if depth < 4:
            assert any(graph.band.route(graph.band.riser, sink) for sink in graph.band.sinks)
        else:
            assert graph.band.sinks == ()
    # A lower-band entry always returns through a labelled riser.
    intent(game, a, "lat.leave")
    assert presence.depth == 3
    intent(game, a, "lat.jack_out")
    assert presence.escape
    game.step(presence.escape.until_tick-game.clock.now_tick())
    assert presence.player_id not in game.core.lattice.presences


def test_game_6_5_generated_sites_are_stable_across_descents(runners):
    game, a, b, c = runners
    one, two = descend(game, a), descend(game, b)
    encounters = game.core.lattice.encounters
    assert one.descent != two.descent
    encounters.enter_band(one, 2)
    encounters.enter_band(two, 2)
    first = next(d for r in encounters.core(one).graph.rooms.values() for d in r.data if d.kind == "contribution")
    second = next(d for r in encounters.core(two).graph.rooms.values() for d in r.data if d.id == first.id)
    assert encounters.source(one, first) == encounters.source(two, second)
    assert game.core.lattice.location(a.session)[0] != game.core.lattice.location(b.session)[0]


def test_game_6_6_chorister_visible_survey_hold_and_no_repeat_reward(runners):
    game, a, b, c = runners
    presence = descend(game, a)
    before_xp = game.core.characters.players[presence.player_id].xp
    encounters = game.core.lattice.encounters
    encounters.enter_band(presence, 2)
    graph = encounters.core(presence).graph
    signal = next(i for i in encounters.core(presence).ice.values() if i.template.class_ == "chorister")
    # Place at the authored signal to isolate the labelled sampling cycle.
    presence.room = signal.location[1]
    signal.phase_origin = game.clock.now_tick()
    intent(game, a, "lat.survey")
    game.step(presence.procedure.until-game.clock.now_tick())
    assert signal.id in presence.survey_records
    game.step(signal.phase_origin+50-game.clock.now_tick())
    intent(game, a, "lat.sample")
    game.step(presence.procedure.until-game.clock.now_tick())
    assert signal.id in presence.sampled
    assert presence.mapping_until == game.clock.now_tick()+3000
    assert not game.core.characters.players[presence.player_id].progress.get("lattice_units")
    assert game.core.characters.players[presence.player_id].xp == before_xp
    intent(game, a, "lat.sample")
    assert presence.procedure is None


def test_game_6_6_seeded_populations_and_sweeper_routes_are_replayable(runners):
    game, a, b, c = runners
    content = game.core.loop.content
    for nonce in range(30):
        descent = generate("o", 1, "lat-chapel-ward", nonce, content.silt)
        for band in descent.bands:
            first, replay = BandGraph(descent, band, content), BandGraph(descent, band, content)
            assert first.rooms == replay.rooms and first.patrols == replay.patrols
            assert sum("ice_chorister" in r.ice for r in first.rooms.values()) == (band.depth == 2)
            for route in first.patrols.values():
                assert len(route) == 4 and band.riser not in route
                assert all(not band.cell(cid).hidden for cid in route)
                assert all(b in band.cell(a).neighbours for a, b in zip(route, (*route[1:], route[0])))
