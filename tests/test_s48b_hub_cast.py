"""S48b: the hub cast is switched on (S48 part 4, creative lead's placement ruling)."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from karst41.content.loader import load_content
from karst41.content.validate import validate
from karst41.server import truce as truce_rules
from karst41.server.rules.combat import MARKED_SECONDS
from tests.character_helpers import create, place
from tests.harness import HeadlessServer
from tests.test_dialogue_runtime import press

SPOTS = {
    'vane': ('vatside-clinics', (44, 7)), 'quaye': ('core-plaza', (17, 29)), 'ranke': ('core-plaza', (34, 7)),
    'amsel': ('core-precinct', (27, 2)), 'brann': ('core-precinct', (41, 16)),
    'achterberg': ('core-tram-hub', (38, 3)), 'ivey': ('terraces-blocks', (103, 9)),
    'marsh': ('terraces-blocks', (108, 29)), 'solenne': ('sodium-row', (48, 19)), 'dolf': ('sodium-tin-halo', (16, 14)),
}
COUNTERS = {'vesper': 'npc-vendor-sodium-tin-halo-vesper', 'lindgren': 'npc-vendor-core-precinct-warden-quartermaster'}
MOVED = sorted([*SPOTS, *COUNTERS])
DOOR_RECRUITERS = ('achebe-roux', 'kettle', 'vance', 'vael')
WAKE_HALL = ('okafor', 'vantongeren')  # Technical lead: dormant until S48c restages the hall.


@pytest.fixture(scope='module')
def content():
    return load_content(Path(__file__).parents[1]/'src/karst41/content')


def test_s48b_moved_talkers_are_active_and_the_rest_stay_dormant(content):
    assert content.bundles['s48-hub-cast'].status == 'active'
    assert sorted(content.bundles['s48-hub-cast'].members['dialogue']) == MOVED
    cast = content.bundles['s27-cast']
    assert cast.status == 'authoring' and not set(MOVED) & set(cast.members['dialogue'])
    assert all(content.active('dialogue', t) for t in MOVED)
    assert not any(content.active('dialogue', t) for t in cast.members['dialogue'])
    assert set(DOOR_RECRUITERS) <= set(cast.members['dialogue'])  # Creative lead: the hall stays quiet.
    assert 'orderly' not in ''.join(MOVED)  # The orderlies wait for S48c with O1.
    assert set(WAKE_HALL) <= set(cast.members['dialogue'])
    assert not any(content.npcs[t].dialogue in WAKE_HALL for t in content.npcs if content.npcs[t].dialogue)


def test_s48b_a_moved_talker_may_not_reference_dormant_content(content):
    """No back door into authoring content (technical lead's condition)."""
    tree = deepcopy(content)
    vane = tree.dialogue['vane']
    line = replace(vane.lines[-1], id='leak', when=('has_contract war-s1-1-stairwell',))
    tree.dialogue['vane'] = replace(vane, lines=(line, *vane.lines))
    problems = [p.message for p in validate(tree)]
    assert any('authoring bundle' in message for message in problems)
    assert not [p for p in validate(content) if 'authoring bundle' in p.message]


@pytest.mark.parametrize('talker', sorted(SPOTS))
def test_s48b_each_talker_stands_at_its_post_and_answers_e(content, talker):
    zone_id, tile = SPOTS[talker]
    game = HeadlessServer(deepcopy(content), character_state={})
    caller = game.connect({'user_id': 1, 'handle': 'Cast', 'node_name': 'S48b'})
    create(game, caller, card='none')
    zone = arrive(game, caller, zone_id)
    actor = next(a for a in zone.actors.values() if a.behaviour.get('template') == f'npc-cast-{talker}')
    assert actor.position == tile and actor.name == content.dialogue[talker].name
    place(game, caller, zone_id, near(zone, tile))
    game.step(12)
    press(game, caller, 'e')
    game.commit_commerce()
    game.step(2)
    menu = game.core.dialogue.menus.get(caller.session.id)
    assert menu is not None and menu.contact.target == actor.id  # S42 reach: one step, in sight.


def near(zone, tile):
    """A free walkable tile one step from `tile`."""
    for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
        t = (tile[0]+dx, tile[1]+dy)
        if zone.passable(t) and not any(a.position == t for a in zone.actors.values()) and not any(
                o.spec.tile == t for o in zone.objects.values()):
            return t
    raise AssertionError(f'no free tile beside {tile}')


def arrive(game, caller, zone_id):
    """Spawners fill a zone once a caller is in it."""
    zone = game.core.world.zones[zone_id]
    place(game, caller, zone_id, zone.template.meta.spawn or next(e.tile for e in zone.template.meta.exits))
    game.step(30)
    return zone


def halo(content):
    game = HeadlessServer(deepcopy(content), character_state={})
    caller = game.connect({'user_id': 1, 'handle': 'Halo', 'node_name': 'S48b'})
    create(game, caller, card='none')
    zone = arrive(game, caller, 'sodium-tin-halo')
    vesper = next(a for a in zone.actors.values() if a.behaviour.get('template') == COUNTERS['vesper'])
    place(game, caller, 'sodium-tin-halo', near(zone, vesper.position))
    game.step(3)
    return game, caller, game.core.characters.players[caller.session.player_id], vesper


def toasts(game, caller):
    return [f.data['text'] for f in game.frames_for(caller) if f.type == 'toast']


def test_s48b_vesper_opens_her_talk_page_on_e(content):
    game, caller, player, vesper = halo(content)
    assert vesper.name == 'Vesper'
    press(game, caller, 'e')
    game.commit_commerce()
    game.step(2)
    menu = game.core.dialogue.menus.get(caller.session.id)
    assert menu is not None and menu.contact.talker == 'vesper'
    assert 'vesper' in player.progress.get('met_talkers', [])


def test_s48b_e_on_vesper_while_marked_is_refused_with_no_page(content):
    game, caller, player, vesper = halo(content)
    player.marked_until = truce_rules.iso(game.core.combat.now() + MARKED_SECONDS)
    game.frames_for(caller)
    press(game, caller, 'e')
    game.commit_commerce()
    game.step(2)
    assert caller.session.id not in game.core.dialogue.menus
    assert any(text.startswith('Vesper: "Not with that name.') for text in toasts(game, caller))
    assert 'vesper' not in player.progress.get('met_talkers', [])  # No meeting, so no errand clears.


def test_s48b_e_on_vesper_while_hunted_is_refused_with_no_page(content):
    game, caller, player, vesper = halo(content)
    player.keeper_answer = {'keeper': 'sable', 'zone': 'sodium-row',
                            'until': truce_rules.iso(game.core.combat.now() + 300)}
    game.frames_for(caller)
    press(game, caller, 'e')
    game.commit_commerce()
    assert caller.session.id not in game.core.dialogue.menus
    assert any("still asking about you" in text for text in toasts(game, caller))
    assert 'vesper' not in player.progress.get('met_talkers', [])


@pytest.mark.parametrize('key', ['v', 'c'])
def test_s48b_an_open_page_refuses_an_offer_once_the_caller_is_marked(content, key):
    game, caller, player, vesper = halo(content)
    press(game, caller, 'e')
    game.commit_commerce()
    game.step(2)
    assert caller.session.id in game.core.dialogue.menus
    player.marked_until = truce_rules.iso(game.core.combat.now() + MARKED_SECONDS)
    game.frames_for(caller)
    press(game, caller, key)
    game.step(2)
    assert caller.session.id not in game.core.commerce.menus
    assert caller.session.id not in game.core.contracts.panels.menus
    assert any(text.startswith('Vesper: "Not with that name.') for text in toasts(game, caller))


def line_for(content, talker, **facts):
    from random import Random
    from karst41.server.dialogue import Facts, evaluate
    return evaluate(content.dialogue[talker], Facts(met=frozenset({talker}), **facts), Random(0)).id


@pytest.mark.parametrize('talker', ['vane', 'ranke', 'solenne'])
def test_s48b_fillers_give_a_red_name_and_a_new_wake_their_own_line(content, talker):
    assert line_for(content, talker, marked=True) == 'marked'
    assert line_for(content, talker, grade=1, archetype='hardline') == 'wake'
    expected = 'signatory' if talker == 'vane' else 'greeting'  # Vane: "A signature now" is for a fresh one.
    assert line_for(content, talker, grade=6, legal=True, archetype='hardline') == expected
    assert line_for(content, talker, grade=12, legal=True, archetype='hardline') == 'greeting'


def test_s48b_vane_speaks_to_members_and_signatories(content):
    assert line_for(content, 'vane', grade=6, legal=True, faction='sablier') == 'member'
    assert line_for(content, 'vane', grade=5, faction='wardens') == 'signatory'


def test_s48b_vesper_greets_a_returning_player_differently_and_first_done_gives_way(content):
    vesper = content.dialogue['vesper']
    texts = {line.id: line.text for line in vesper.lines}
    assert texts['greeting'] != texts['first']
    assert line_for(content, 'vesper', grade=1, completed=frozenset({'vesper-first-thing'})) == 'first-done'
    assert line_for(content, 'vesper', grade=5, completed=frozenset({'vesper-first-thing'})) == 'greeting'


def test_s48b_e_at_public_terminal_1_still_jacks_in_with_ranke_there(content):
    """Ranke stands by the terminals, never on their interaction cells."""
    from karst41.server.protocol import Frame
    from tests.character_helpers import act
    game = HeadlessServer(deepcopy(content), character_state={})
    caller = game.connect({'user_id': 1, 'handle': 'Jack', 'node_name': 'S48b'})
    create(game, caller, card='none')
    zone = arrive(game, caller, 'core-plaza')
    ranke = next(a for a in zone.actors.values() if a.behaviour.get('template') == 'npc-cast-ranke')
    terminal = zone.objects['plaza-public-1'].spec.tile
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            spot = (terminal[0]+dx, terminal[1]+dy)
            assert max(abs(spot[0]-ranke.x), abs(spot[1]-ranke.y)) > 1  # No shared cell.
    place(game, caller, 'core-plaza', terminal)
    game.step(3)
    act(game, caller, Frame('key', {'k': 'e', 't': 0}))
    assert caller.session.player_id in game.core.lattice.presences
