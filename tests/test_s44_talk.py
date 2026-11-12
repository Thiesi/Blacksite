"""S44 part 6: the Row's Ask lines (entities 1.11 `ask` offers, #185 6755418093)."""

from copy import deepcopy
from dataclasses import replace
from random import Random

import pytest

from karst41.content.schema import DialogueLine, DialogueNode, Offer
from karst41.content.validate import validate
from karst41.server.dialogue import Facts, evaluate
from karst41.server.npcs.templates import make_actor
from karst41.server.views import presentation
from tests.character_helpers import place
from tests.test_dialogue_runtime import content, open_talker, press, setup  # noqa: F401 (fixture)

END = "The Halo. Vesper. Work if you want it, a price on it either way. Everybody ends up there."
PEACE = ("Nobody draws. Somebody does, we come for them, whoever they are. They pay. "
         "A few think they're quicker than us. Fewer are.")


def row(content, template, aid):
    content = deepcopy(content)
    content.zones = {key: replace(zone, meta=replace(zone.meta, spawners=())) for key, zone in content.zones.items()}
    game, caller, player = setup(content)
    place(game, caller, 'sodium-row', (25, 3))
    actor = make_actor(game.core.characters.content.npcs[template], aid,
                       {'spawner': aid, 'home': (26, 3), 'pause': 10000})
    game.core.world.enter(actor, 'sodium-row', (26, 3))
    return game, caller, player, actor


def page(game, caller):
    kind, body = game.core.characters.sim.external_views[caller.session.id]
    assert kind == 'menu' and body['kind'] == 'talker'
    return body


def speech(caller):
    return [(line.get('speaker'), line.get('speaker_role'), line['text'])
            for line in caller.session.log_ring if line.get('kind') == 'speech']


@pytest.mark.parametrize('template,label,question,answer,name,role', [
    ('npc-sodium-regular', 'Ask about the end', "What's down the end?", END, 'Sodium regular', 'civilian'),
    ('npc-sable-enforcer', 'Ask about the peace', "What's the arrangement here?", PEACE, 'Sable enforcer', 'security'),
])
def test_s44_ask_through_real_views(content, template, label, question, answer, name, role):
    game, caller, player, actor = row(content, template, 'asked')
    open_talker(game, caller)
    body = page(game, caller)
    assert {'key': 'a', 'label': label} in body['actions']
    assert answer not in str(body)  # Ordinary selection never picks the answer.
    press(game, caller, 'a')
    body = page(game, caller)
    assert answer in str(body) and {'key': 'a', 'label': label} in body['actions']
    said = speech(caller)
    assert said[-2] == (player.name, 'caller', f'{player.name}: {question}')
    assert said[-1] == (name, role, f'{name}: {answer}')


def test_s44_talking_enforcer_still_presents_as_security(content):
    game, caller, _, guard = row(content, 'npc-sable-enforcer', 'keeper')
    assert game.core.dialogue.contact(caller.session, guard.id) is not None
    viewer = game.core.characters.sim.avatars[caller.session.user_id].actor
    assert presentation.presented_class(guard, viewer, game.core.characters.content) == 'security'
    assert presentation.true_class(guard, game.core.characters.content) == 'security'


def test_s44_enforcer_carries_the_reference_line(content):
    node = content.dialogue['row-enforcer']
    assert [bark.text for bark in node.barks] == ['Nobody draws on the Row. You can. Then you pay.']


def talker(*offers, lines=None):
    return DialogueNode('t', 'T', lines or (DialogueLine('answer', 'An answer.'), DialogueLine('fallback', 'Hello.')),
                        offers=offers)


def test_s44_answer_lines_are_never_picked_by_ordinary_selection():
    node = talker(Offer('ask', 'Ask', 'a', 'answer', asks='Why?'))
    assert evaluate(node, Facts(), Random(1)).id == 'fallback'


@pytest.mark.parametrize('offer,problem', [
    (Offer('ask', 'Ask', 'a', 'missing', asks='Why?'), "not one of this talker's lines"),
    (Offer('ask', 'Ask', 'a', 'fallback', asks='Why?'), 'fallback line cannot be an answer'),
    (Offer('ask', 'Ask', 'a', 'answer'), 'question must contain'),
    (Offer('ask', 'Ask', 'a', 'answer', asks='x' * 201), 'question must contain'),
    (Offer('ask', 'Ask', 'a', 'answer', asks=' '.join(['x' * 34] * 5)), 'question wraps'),
    (Offer('contract', 'Work', 'c', 'answer', asks='Why?'), 'only an ask offer carries a question'),
])
def test_s44_validator_checks_ask_offers(content, offer, problem):
    tree = deepcopy(content)
    tree.dialogue['row-street-regular'] = replace(talker(offer), id='row-street-regular')
    assert any(problem in p.message for p in validate(tree)), [p.message for p in validate(tree)][:5]


def test_s44_validator_fails_an_over_long_keeper_name(content):
    tree = deepcopy(content)
    tree.factions['sable'] = replace(tree.factions['sable'], short='Sablish')  # 7 cells.
    assert any('price notice fits at most 6' in p.message for p in validate(tree))
