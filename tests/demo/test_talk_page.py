"""Demo round 3: a talk page never holds you, and the truce warning reaches the door."""

from dataclasses import replace
from typing import Any

from blacksite.content.schema import Offer
from blacksite.server.protocol import Frame
from tests.character_helpers import act, create, place
from tests.demo.test_truce_standin import body, boot, spawn
from tests.presentation.test_client_foundations import content, display  # noqa: F401

NPC_NOTICE = 'Fire here and Sable comes. No Halo.'


def on_page(repo_root, monkeypatch, *, keymap=None):
    game, caller = boot(repo_root, monkeypatch)
    if keymap:
        caller.session.keymap_id = keymap
    place(game, caller, 'sodium-row', (40, 12))
    npc = spawn(game, 'sodium-row', 'npc-row-card-player', (41, 12))
    act(game, caller, Frame('key', {'k': 'e', 't': 0}))
    game.commit_commerce()
    game.step()
    assert caller.session.id in game.core.dialogue.menus
    return game, caller, npc


def test_a_movement_key_closes_the_page_and_moves_in_the_same_press(repo_root, monkeypatch):
    game, caller, _ = on_page(repo_root, monkeypatch)
    before = body(game, caller).position
    act(game, caller, Frame('key', {'k': 'left', 't': 0}))  # one frame, no step between
    assert caller.session.id not in game.core.dialogue.menus
    assert body(game, caller).position == (before[0]-1, before[1])
    assert caller.session.id not in game.core.characters.sim.external_views


def test_the_door_sends_an_unclaimed_key_on_a_talker_page(content: Any):
    model = display(content, 80, 24)
    model.receive(Frame('view', {'rev': 1, 'kind': 'menu', 'body': {
        'kind': 'talker', 'title': 'T', 'rows': [], 'cursor': 0, 'detail': 'Hi', 'hint': 'x',
        'actions': [{'key': 'c', 'label': 'Work'}, {'key': 'b', 'label': 'Back'}]}}), 0.0)
    assert model.key('up', 0.0)[0].type == 'key'
    assert model.key('left', 0.0)[0].data['k'] == 'left'
    assert model.key('z', 0.0) == []  # an unadvertised key still grants nothing
    assert model.key('c', 0.0)[0].data['name'] == 'menu_select'
    assert model.key('b', 0.0)[0].data['name'] == 'menu_close'
    model.selected_keymap = 'vi'
    assert model.key('j', 0.0)[0].data['k'] == 'j'
    assert model.key('c', 0.0)[0].data['name'] == 'menu_select'


def test_other_menus_keep_their_arrows(content: Any):
    model = display(content, 80, 24)
    model.receive(Frame('view', {'rev': 1, 'kind': 'menu', 'body': {
        'title': 'Shop', 'rows': [{'id': 'a', 'cells': ['a']}], 'cursor': 0, 'hint': 'x', 'actions': []}}), 0.0)
    assert model.key('down', 0.0)[0].data['name'] == 'menu_cursor'


def test_a_key_an_offer_claims_stays_an_offer(repo_root, monkeypatch):
    game, caller, npc = on_page(repo_root, monkeypatch, keymap='vi')
    tree = game.core.dialogue.content
    talker = tree.dialogue['row-card-player']
    tree.dialogue['row-card-player'] = replace(talker, offers=(Offer('vendor', 'Trade', 'h', 'row-clause'),))
    before = body(game, caller).position
    screen = game.core.dialogue.menus[caller.session.id]
    frame = Frame('key', {'k': 'h', 't': 0})
    assert not game.core.dialogue.walks_away(caller.session, screen, frame, 'h')
    tree.dialogue['row-card-player'] = talker
    assert game.core.dialogue.walks_away(caller.session, screen, frame, 'h')
    assert body(game, caller).position == before


def test_a_key_that_is_not_movement_leaves_the_page_up(repo_root, monkeypatch):
    game, caller, _ = on_page(repo_root, monkeypatch)
    act(game, caller, Frame('key', {'k': 'z', 't': 0}))
    assert caller.session.id in game.core.dialogue.menus


def test_a_hit_closes_the_page_without_a_key_and_says_nothing_about_walking(repo_root, monkeypatch):
    game, caller, _ = on_page(repo_root, monkeypatch)
    guard = spawn(game, 'sodium-row', 'npc-row-enforcer', (42, 12), group='enforcers')
    runner = body(game, caller)
    line = game.core.dialogue.menus[caller.session.id].line
    template = game.core.dialogue.content.npcs['npc-row-enforcer']
    arm = game.core.dialogue.content.items[template.weapon].weapon
    for _ in range(200):
        game.core.combat.shot(guard, runner, arm)
        if runner.cooldowns.get('last_hit') != game.core.dialogue.menus[caller.session.id].hit:
            break
    game.step()
    assert caller.session.id not in game.core.dialogue.menus
    assert not any('walks off' in line.get('text', '') for line in caller.session.log_ring)
    assert any(line in entry.get('text', '') for entry in caller.session.log_ring)  # the words stay in the log


def zone_views(game, caller):
    return [f for f in game.frames_for(caller) if f.type == 'view' and f.data.get('kind') == 'zone']


def test_the_truce_warning_reaches_the_door_in_real_view_frames(repo_root, monkeypatch, content: Any):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (40, 12))
    regular = spawn(game, 'sodium-row', 'npc-sodium-regular', (42, 12), group='regulars')
    regular.behaviour['region'] = None
    body(game, caller).target = regular.id
    game.step(2)
    views = zone_views(game, caller)
    assert views[-1].data['body']['target']['warning'] == 'Truce: Sable answers'
    model = display(content, 80, 24)
    for rev, frame in enumerate(views):
        model.receive(Frame('view', {**frame.data, 'rev': rev+1}), 0.0)
    assert model.toast is not None and model.toast[0] == NPC_NOTICE


def test_the_warning_for_a_player_target_still_arrives(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    other = game.connect({'user_id': 2, 'handle': 'Other', 'node_name': 'test'})
    create(game, other, card='none')
    place(game, caller, 'sodium-row', (60, 12))
    place(game, other, 'sodium-row', (62, 12))
    me, them = body(game, caller), body(game, other)
    me.faction, them.faction = 'halvard', 'unmoored'
    monkeypatch.setattr(game.core.combat, 'legal', lambda source, target: True)
    me.target = them.id
    game.step(2)
    assert zone_views(game, caller)[-1].data['body']['target']['warning'] == 'Firing marks you'
