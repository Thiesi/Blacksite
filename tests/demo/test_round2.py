"""Demo only: round 2's reach rule, walk-off line, first-meeting fix, seats and barks."""

from dataclasses import replace

from karst41.content.loader import load_content
from karst41.server import demo_seated, demo_truce
from karst41.server.protocol import Frame
from karst41.server.views import presentation
from tests.character_helpers import act, create, place
from tests.demo.test_truce_standin import body, boot, spawn
from tests.harness import HeadlessServer


def reach(a, b):
    return max(abs(a.x-b.x), abs(a.y-b.y))


def page_open(game, caller):
    act(game, caller, Frame('key', {'k': 'e', 't': 0}))
    game.commit_commerce()
    game.step()


def test_a_wanderer_stays_in_reach_of_an_adjacent_caller(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (40, 12))
    npc = spawn(game, 'sodium-row', 'npc-sodium-regular', (41, 12))
    npc.behaviour['region'] = None
    start = npc.position
    moved = False
    for _ in range(300):
        game.step()
        moved = moved or npc.position != start
        assert reach(npc, body(game, caller)) <= 1
    assert moved  # it still fidgets; it just doesn't leave


def test_the_warden_keeps_reach_exactly_as_the_regulars_do(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (40, 12))
    warden = spawn(game, 'sodium-row', 'npc-plainclothes-warden', (41, 12))
    warden.behaviour['region'] = None
    for _ in range(300):
        game.step()
        assert reach(warden, body(game, caller)) <= 1


def test_a_wanderer_with_nobody_beside_it_still_wanders(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (40, 12))
    npc = spawn(game, 'sodium-row', 'npc-sodium-regular', (60, 12))
    npc.behaviour['region'] = None
    start = npc.position
    game.step(300)
    assert npc.position != start


def test_a_page_closed_by_someone_leaving_says_so_under_their_cover_name(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (40, 12))
    warden = spawn(game, 'sodium-row', 'npc-plainclothes-warden', (41, 12))
    page_open(game, caller)
    assert caller.session.id in game.core.dialogue.menus
    warden.x, warden.y = 44, 12  # stands in for flee, hunt or event motion
    game.core.world.zones['sodium-row'].position_update(warden)
    game.step()
    assert caller.session.id not in game.core.dialogue.menus
    said = [line['text'] for line in caller.session.log_ring]
    assert 'Sodium regular walks off.' in said
    assert not any('Warden' in text for text in said)


def test_a_caller_who_moves_away_does_not_make_anyone_walk_off(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (40, 12))
    npc = spawn(game, 'sodium-row', 'npc-row-card-player', (41, 12))
    page_open(game, caller)
    body(game, caller).x = 37
    game.core.world.zones['sodium-row'].position_update(body(game, caller))
    game.step()
    assert caller.session.id not in game.core.dialogue.menus
    assert not any('walks off' in line['text'] for line in caller.session.log_ring)
    assert npc.position == (41, 12)


def test_a_first_meeting_that_never_showed_is_not_met(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (40, 12))
    npc = spawn(game, 'sodium-row', 'npc-row-card-player', (41, 12))
    player = game.core.characters.players[caller.session.player_id]
    act(game, caller, Frame('key', {'k': 'e', 't': 0}))
    npc.x, npc.y = 45, 12  # gone before the save commits
    game.core.world.zones['sodium-row'].position_update(npc)
    game.commit_commerce()
    assert caller.session.id not in game.core.dialogue.menus
    game.commit_commerce()  # the undo's own write
    assert 'row-card-player' not in player.progress.get('met_talkers', [])


def test_a_first_meeting_that_showed_is_met(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (40, 12))
    spawn(game, 'sodium-row', 'npc-row-card-player', (41, 12))
    page_open(game, caller)
    player = game.core.characters.players[caller.session.player_id]
    assert 'row-card-player' in player.progress['met_talkers']


def seated_world(repo_root, monkeypatch):
    monkeypatch.setenv('KARST41_DEMO', demo_truce.DEMO)
    monkeypatch.setenv('KARST41_DEMO_SEATED', '1')
    game = HeadlessServer(load_content(repo_root/'src/karst41/content'), character_state={})
    caller = game.connect()
    create(game, caller, card='none')
    game.core.characters.players[caller.session.player_id].progress['wake_combat'] = 'skipped'
    return game, caller


def seated_drinkers(game, zone_id):
    return [a for a in game.core.world.zones[zone_id].actors.values()
            if a.behaviour.get('spawner') in demo_seated.SEATS[zone_id]
            and a.behaviour.get('posts') and any(p.seated and p.tile == tuple(a.behaviour['home'])
                                               for p in a.behaviour['posts'])]


def test_posted_drinkers_fill_their_seats_and_hold_before_errands(repo_root, monkeypatch):
    game, caller = seated_world(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (3, 12))  # wakes the Row
    game.step(5)
    row = seated_drinkers(game, 'sodium-row')
    want = {p.tile for sp in game.core.world.zones['sodium-row'].template.meta.spawners
            if sp.id in demo_seated.SEATS['sodium-row'] for p in sp.posts if p.home and p.seated}
    assert len(want) == 6
    assert {a.position for a in row} == want
    game.step(200)
    assert {a.position for a in row} == want


def test_every_halo_seat_is_filled(repo_root, monkeypatch):
    game, caller = seated_world(repo_root, monkeypatch)
    place(game, caller, 'sodium-tin-halo', (12, 12))
    game.step(5)
    want = {p.tile for sp in game.core.world.zones['sodium-tin-halo'].template.meta.spawners
            for p in sp.posts if p.home and p.seated}
    assert len(want) == 3
    assert {a.position for a in seated_drinkers(game, 'sodium-tin-halo')} == want


def test_seated_drinkers_stay_civilian_and_can_be_talked_to(repo_root, monkeypatch):
    game, caller = seated_world(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (56, 6))  # beside the Clause seat at (55, 5)
    game.step(5)
    drinker = next(a for a in seated_drinkers(game, 'sodium-row') if a.position == (55, 5))
    assert presentation.true_class(drinker, game.core.world.content) == 'civilian'
    assert game.core.dialogue.contact(caller.session, drinker.id) is not None


def test_posts_replace_the_old_seated_switch(repo_root, monkeypatch):
    game, caller = seated_world(repo_root, monkeypatch)
    content = game.core.world.content
    assert [b.kind for b in content.npcs['npc-sodium-regular'].behaviours] == ['wander']
    assert [b.kind for b in content.npcs['npc-plainclothes-warden'].behaviours] == ['wander']
    monkeypatch.delenv('KARST41_DEMO_SEATED')
    plain = HeadlessServer(load_content(repo_root/'src/karst41/content'), character_state={})
    spawners = plain.core.world.zones['sodium-row'].template.meta.spawners
    assert not any('-seat' in sp.id for sp in spawners)
    assert [b.kind for b in plain.core.world.content.npcs['npc-row-clause-regular'].behaviours] == ['wander']
    assert plain.core.world.zones['sodium-row'].template.meta.moving_budget == 4


def test_the_doorstep_pair_stands_in_the_light_and_leaves_the_door_clear(repo_root, monkeypatch):
    game, caller = seated_world(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (70, 12))
    game.step(5)
    zone = game.core.world.zones['sodium-row']
    pair = [a for a in zone.actors.values() if str(a.behaviour.get('spawner')).startswith('halo-doorstep')]
    start = {a.position for a in pair}
    assert start == {(85, 11), (87, 13)}
    assert all(presentation.true_class(a, game.core.world.content) == 'civilian' for a in pair)
    game.step(100)
    assert {a.position for a in pair} == start


def test_the_regulars_and_the_warden_share_every_spoken_word(repo_root):
    content = load_content(repo_root/'src/karst41/content')
    assert content.npcs['npc-sodium-regular'].dialogue == content.npcs['npc-plainclothes-warden'].dialogue


def test_barks_keep_the_disclosure_and_voice_rules(repo_root):
    content = load_content(repo_root/'src/karst41/content')
    records = ('row-halvard-offduty', 'row-sablier-offduty', 'row-kestrel-crew', 'row-choir-listener',
               'row-clause-regular', 'row-unmoored-runner', 'row-card-player', 'row-street-regular',
               'solenne', 'dolf')
    barks = [bark.text for did in records for bark in content.dialogue[did].barks]
    assert len(barks) == 51  # Round 3's 48 plus the three approved regular barks.
    assert len(set(barks)) == len(barks)
    lowered = ' '.join(barks).lower()
    for banned in ('—', 'cyberpunk', 'hacker', 'cyberspace', 'arranged', 'back room', 'alley door',
                   'sign grid', 'plainclothes', 'custodian', 'tenant'):
        assert banned not in lowered, banned
    # Other crowds may talk about Wardens. The set the Warden itself speaks may not.
    assert not any('warden' in b.text.lower() for b in content.dialogue['row-street-regular'].barks)
    # The spoken pull reaches along the street: every street record points at the Halo.
    for did in records[:8]:
        assert any('halo' in b.text.lower() or 'vesper' in b.text.lower() for b in content.dialogue[did].barks), did
