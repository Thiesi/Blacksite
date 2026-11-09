"""UI 4 / game 5.5: physical talk-page escape and committed first meetings."""

from copy import deepcopy
from dataclasses import replace

import pytest

from karst41.server.npcs.templates import make_actor, REACH_ACTIVE_TICKS
from karst41.content.schema import ObjectSpec
from karst41.server.world.zone import ObjectState
from tests.character_helpers import place
from tests.combat.test_engine import body
from tests.test_dialogue_runtime import content, setup, open_talker, press


def street(content):
    content = deepcopy(content)
    content.zones = {key: replace(zone, meta=replace(zone.meta, spawners=()))
                     for key, zone in content.zones.items()}
    game, caller, player = setup(content)
    place(game, caller, 'sodium-row', (25, 3))
    template = content.npcs['npc-sodium-regular']
    game.core.characters.content.npcs[template.id] = replace(template, dialogue='vesper')
    target = make_actor(game.core.characters.content.npcs[template.id], 'talker',
                        {'spawner': 'test-crowd', 'home': (26, 3), 'pause': 10000})
    game.core.world.enter(target, 'sodium-row', (26, 3))
    return game, caller, player, target


@pytest.mark.parametrize('keymap,key,delta', [
    ('arrows', 'down', (0, 1)), ('arrows', 'pgup', (1, -1)),
    ('arrows', 'pgdn', (1, 1)), ('arrows', 'home', (-1, -1)),
    ('arrows', 'end', (-1, 1)), ('vi', 'j', (0, 1)),
    ('vi', 'b', (0, 0)), ('vi', 'down', (0, 0)),
])
def test_ui_4_talker_movement_is_one_press_and_back_wins(content, keymap, key, delta):
    game, caller, _, target = street(content)
    caller.session.keymap_id = keymap
    if delta[0] and delta[1]:
        # Leave both corner tiles clear under ordinary diagonal collision.
        game.core.world.enter(target, target.zone, (25, 3-delta[1]))
    open_talker(game, caller)
    assert caller.session.id in game.core.dialogue.menus
    source = body(game, caller)
    before = source.position
    press(game, caller, key)
    assert source.position == (before[0]+delta[0], before[1]+delta[1])
    assert (caller.session.id in game.core.dialogue.menus) == (keymap == 'vi' and key == 'down')


def test_ui_4_offer_beats_vi_movement(content):
    game, caller, _, _ = street(content)
    caller.session.keymap_id = 'vi'
    node = game.core.characters.content.dialogue['vesper']
    game.core.characters.content.dialogue[node.id] = replace(node, offers=(replace(node.offers[0], hotkey='j'),))
    zone = game.core.world.zones['sodium-row']
    zone.objects['test-board'] = ObjectState(ObjectSpec('test-board', (24, 3), 'terminal',
        {'name': 'Work board', 'contract_handler': 'vesper'}))
    open_talker(game, caller)
    before = body(game, caller).position
    press(game, caller, 'j')
    assert body(game, caller).position == before
    assert caller.session.id not in game.core.dialogue.menus
    assert caller.session.id in game.core.contracts.panels.menus


def test_game_5_5_open_page_holds_its_person_after_activity_expires(content):
    game, caller, _, target = street(content)
    open_talker(game, caller)
    tick = caller.session.last_action_tick+REACH_ACTIVE_TICKS+1
    zone = game.core.world.zones[target.zone]
    assert game.core.npcs.reach_holders(target, zone, tick) == [body(game, caller).position]
    another = make_actor(game.core.characters.content.npcs['npc-sodium-regular'], 'other', {'home': (24, 3)})
    game.core.world.enter(another, target.zone, (24, 3))
    assert game.core.npcs.reach_holders(another, zone, tick) == []


@pytest.mark.parametrize('reason', ['person-left', 'other-screen'])
def test_game_13_4_unshown_intro_is_compensated_and_next_e_still_gets_first_line(content, reason):
    game, caller, player, target = street(content)
    press(game, caller, 'e')
    assert game.core.commerce.pending and not player.progress.get('met_talkers')
    if reason == 'person-left':
        game.core.world.enter(target, target.zone, (30, 3))
    else:
        game.core.characters.sim.external_views[caller.session.id] = 'text', {'title': 'Inventory'}
    effects = game.commit_commerce()
    assert len(effects) == 2  # Meeting write followed by a durable compensation.
    assert not player.progress['met_talkers'] and caller.session.id not in game.core.dialogue.menus
    game.core.world.enter(target, target.zone, (26, 3))
    game.core.characters.sim.external_views.pop(caller.session.id, None)
    open_talker(game, caller)
    assert game.core.dialogue.menus[caller.session.id].line == 'Show me the card.'


def test_ui_4_hit_closes_physical_talker_next_tick_without_walkoff(content):
    game, caller, _, attacker = street(content)
    open_talker(game, caller)
    source = body(game, caller)
    game.core.combat.hurt(attacker, source, 1)
    assert caller.session.id in game.core.dialogue.menus
    game.step()
    assert caller.session.id not in game.core.dialogue.menus
    assert not any('walks off.' in line['text'] for line in caller.session.log_ring)


@pytest.mark.parametrize('covered', [False, True])
@pytest.mark.parametrize('reason', ['person-left', 'caller-moved', 'down', 'dead', 'back'])
def test_ui_4_walkoff_only_reports_a_live_person_leaving_a_stationary_caller(content, reason, covered):
    game, caller, _, target = street(content)
    if covered:
        tree = game.core.characters.content
        template = tree.npcs['npc-plainclothes-warden']
        tree.npcs[template.id] = replace(template, dialogue='vesper')
        target.behaviour['template'] = template.id
        target.name, target.faction = template.name, template.faction
    open_talker(game, caller)
    if reason == 'person-left':
        game.core.world.enter(target, target.zone, (30, 3))
    elif reason == 'caller-moved':
        press(game, caller, 'down')
    elif reason in ('down', 'dead'):
        target.stance = reason
    else:
        press(game, caller, 'b')
    game.step()
    lines = [line for line in caller.session.log_ring if 'walks off.' in line['text']]
    assert bool(lines) == (reason == 'person-left')
    if lines:
        assert lines[0]['text'] == 'Sodium regular walks off.'
        assert (lines[0]['kind'], lines[0]['channel'], lines[0]['role']) == ('system', 'system', 'muted')


def test_game_5_5_real_shot_and_flee_produces_walkoff(content):
    game, caller, _, target = street(content)
    open_talker(game, caller)
    source = body(game, caller)
    target.health = target.health_max = 1000
    # The actual shot calls exchange/provoked, then ordinary NPC ticks flee.
    # No target teleport, act stub, or preselected flee state supplies the close.
    arm = game.core.characters.content.items['wpn_kestrel_sidearm'].weapon
    game.core.combat.shot(source, target, arm)
    assert game.core.npcs.hostile(target, source)
    before = source.position
    for _ in range(30):
        game.step()
        game.commit_commerce()
        game.frames_for(caller)
        caller.session.acknowledge(caller.session.view_revision)
        if caller.session.id not in game.core.dialogue.menus:
            break
    assert source.position == before
    assert target.behaviour['state'] == 'flee'
    assert any(line['text'] == 'Sodium regular walks off.' for line in caller.session.log_ring)
