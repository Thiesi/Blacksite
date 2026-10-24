"""Game 13.4: talker interaction through production inputs and commits."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from blacksite.content.loader import ContentTree, load_content
from blacksite.content.schema import Bark, DialogueLine, DialogueNode, Offer
from blacksite.server.players import Player
from blacksite.server.npcs.templates import make_actor
from blacksite.server.protocol import Frame
from tests.character_helpers import act, create, place
from tests.harness import FakeClient, HeadlessServer
from tests.combat.test_engine import body, build_duel, fire


@pytest.fixture(scope='module')
def content() -> ContentTree:
    tree = load_content(Path(__file__).parents[1]/'src/blacksite/content')
    tree.dialogue['vesper'] = DialogueNode('vesper', 'Vesper', (
        DialogueLine('marked', 'Take the back seat.', ('marked',)),
        DialogueLine('first', 'Show me the card.', ('first_meeting',)),
        DialogueLine('wake', 'Your lease still runs.', ('is_wake',)),
        DialogueLine('fallback', 'Sit. The door stays open.')),
        title='fixer', offers=(Offer('contract', 'Work', 'c', 'vesper-first-thing'),
                               Offer('vendor', 'Trade', 'v', 'vesper')),
        barks=(Bark('The ring stays dark.'),))
    zone = tree.zones['sodium-tin-halo']
    objects = tuple(replace(obj, params={**obj.params, 'dialogue': 'vesper'})
                    if obj.id == 'vesper' else obj for obj in zone.meta.objects)
    tree.zones[zone.id] = replace(zone, meta=replace(zone.meta, objects=objects))
    return tree


def setup(content: ContentTree, width: int = 80, height: int = 24) -> tuple[HeadlessServer, FakeClient, Player]:
    game = HeadlessServer(deepcopy(content), character_state={})
    caller = game.connect(width=width, height=height)
    create(game, caller, name='Wide界', card='none')
    player = game.core.characters.players[caller.session.player_id]
    tile = game.core.world.zones['sodium-tin-halo'].objects['vesper'].spec.tile
    place(game, caller, 'sodium-tin-halo', tile)
    return game, caller, player


def press(game: HeadlessServer, caller: FakeClient, key: str) -> None:
    act(game, caller, Frame('key', {'k': key, 't': 0}))


def open_talker(game: HeadlessServer, caller: FakeClient) -> None:
    press(game, caller, 'e')
    game.commit_commerce()
    game.step()


def test_game_13_4_talker_precedes_the_board_and_records_only_a_committed_meeting(content: ContentTree) -> None:
    game, caller, player = setup(content)
    original = player.chits_hand, dict(player.standing), list(player.inventory)
    press(game, caller, 'e')
    assert 'met_talkers' not in player.progress
    assert caller.session.id not in game.core.contracts.panels.menus
    game.commit_commerce()
    game.step()
    kind, body = game.core.characters.sim.external_views[caller.session.id]
    assert kind == 'menu' and body['kind'] == 'talker'
    assert body['title'] == 'Vesper - fixer' and body['detail'] == 'Show me the card.'
    assert {action['key'] for action in body['actions']} == {'c', 'v', 'b'}
    assert Player.from_record(player.record()).progress['met_talkers'] == ['vesper']
    press(game, caller, 'b')
    assert caller.session.id not in game.core.dialogue.menus
    assert (player.chits_hand, player.standing, player.inventory) == original


def test_game_13_4_failed_intro_save_can_retry_the_first_meeting(content: ContentTree) -> None:
    game, caller, player = setup(content)
    press(game, caller, 'e')
    game.commit_commerce(error=True)
    assert not player.progress.get('met_talkers')
    assert caller.session.id not in game.core.dialogue.menus
    open_talker(game, caller)
    assert game.core.dialogue.menus[caller.session.id].line == 'Show me the card.'


def test_game_13_4_marked_line_has_priority_and_grade_is_not_discharge(content: ContentTree) -> None:
    game, caller, player = setup(content)
    open_talker(game, caller)
    press(game, caller, 'escape')
    player.marked_until = (game.clock.now_utc()+timedelta(minutes=5)).isoformat()
    open_talker(game, caller)
    assert game.core.dialogue.menus[caller.session.id].line == 'Take the back seat.'
    press(game, caller, 'b')
    player.marked_until, player.grade, player.legal_at = None, 20, None
    open_talker(game, caller)
    assert game.core.dialogue.menus[caller.session.id].line == 'Your lease still runs.'


@pytest.mark.parametrize('action', ['c', 'v'])
def test_game_13_4_chosen_action_opens_the_owning_system_without_accepting_or_buying(
        content: ContentTree, action: str) -> None:
    game, caller, player = setup(content)
    open_talker(game, caller)
    before = player.chits_hand, list(player.inventory)
    press(game, caller, action)
    assert caller.session.id not in game.core.dialogue.menus
    if action == 'c':
        panel = game.core.contracts.panels.menus[caller.session.id]
        assert panel.handler == 'vesper' and panel.target == 'vesper'
        assert not game.core.contracts.state.engine.instances
    else:
        panel = game.core.commerce.menus[caller.session.id]
        assert panel.kind == 'vendor' and panel.target == 'vesper'
    press(game, caller, 'b')
    assert (player.chits_hand, player.inventory) == before


def test_game_13_4_remote_talk_target_is_refused_and_disconnect_clears_the_menu(content: ContentTree) -> None:
    game, caller, player = setup(content)
    place(game, caller, 'vatside-wake-hall', (6, 5))
    act(game, caller, Frame('intent', {'name': 'talk', 'args': {'target': 'vesper'}}))
    assert not player.progress.get('met_talkers') and not game.core.dialogue.menus
    place(game, caller, 'sodium-tin-halo', game.core.world.zones['sodium-tin-halo'].objects['vesper'].spec.tile)
    open_talker(game, caller)
    game.core.sessions.disconnect(caller.session)
    assert caller.session.id not in game.core.dialogue.menus


def test_game_13_4_terminal_talker_uses_its_current_lattice_cell_and_colour_role(content: ContentTree) -> None:
    tree = deepcopy(content)
    tree.dialogue['ninety-nine'] = DialogueNode('ninety-nine', 'Ninety-Nine', (
        DialogueLine('fallback', 'You leave the original in place. //99'),), terminal=True)
    sector_id = tree.zones['sodium-tin-halo'].meta.sector
    sector = tree.sectors[sector_id]
    tree.sectors[sector_id] = replace(sector, cells=tuple(
        replace(cell, dialogue='ninety-nine') if cell.id == sector.entry else cell for cell in sector.cells))
    game, caller, player = setup(tree)
    zone = game.core.world.zones['sodium-tin-halo']
    terminal = next(obj for obj in zone.objects.values() if obj.spec.kind == 'terminal')
    place(game, caller, zone.id, terminal.spec.tile)
    press(game, caller, 'j')
    game.commit_commerce()  # Settle the real jack-in exploration receipt.
    presence = game.core.lattice.presences[player.id]
    assert presence.cell == sector.entry
    game.frames_for(caller)
    open_talker(game, caller)
    screen = game.core.dialogue.menus[caller.session.id]
    assert screen.contact.lattice and screen.line.endswith('//99')
    logs = [line for frame in game.frames_for(caller) if frame.type == 'log' for line in frame.data['lines']]
    assert any(line['text'].endswith('//99') and line['channel'] == 'lat'
               and line['role'] == 'chan_lat' for line in logs)
    press(game, caller, 'b')
    assert game.core.lattice.presences[player.id] is presence
    assert player.progress['met_talkers'] == ['ninety-nine']


def test_game_13_4_barks_measure_real_distance_and_suppress_the_active_talker(content: ContentTree) -> None:
    game, caller, player = setup(content)
    dialogue = game.core.dialogue
    zone = game.core.world.zones[player.zone]
    point = zone.objects['vesper'].spec.tile
    # Explicit placement/clock fixtures isolate audience and scheduling;
    # they are not native travel or pacing evidence.
    game.frames_for(caller)
    dialogue.barks.next_due.clear()
    def tick_at(tick: int) -> list[str]:
        game.clock.advance(tick-game.clock.now_tick()-1)
        game.step()
        return [line['text'] for frame in game.frames_for(caller) if frame.type == 'log'
                for line in frame.data['lines'] if 'The ring stays dark.' in line['text']]
    start = ((game.clock.now_tick()//10)+1)*10
    assert len(tick_at(start)) == 1
    assert not tick_at(start+890)
    open_talker(game, caller)
    assert not tick_at(start+900)
    press(game, caller, 'b')
    assert len(tick_at(start+910)) == 1
    place(game, caller, zone.id, (point[0]+7, point[1]))
    assert not tick_at(start+1810)


@pytest.mark.parametrize('safe', [False, True])
def test_game_13_4_talking_preserves_real_world_damage_and_safe_room_refusal(
        repo_root: Path, monkeypatch: pytest.MonkeyPatch, safe: bool) -> None:
    game, listener, shooter = build_duel(repo_root)
    tree = game.core.loop.content
    tree.dialogue['field-handler'] = DialogueNode('field-handler', 'Route worker', (
        DialogueLine('fallback', 'You keep the return lane clear.'),))
    original = next(npc for npc in tree.npcs.values() if not npc.training)
    template = replace(original, id='dialogue-field-worker', name='Route worker',
                       faction=None, behaviours=(), dialogue='field-handler', health=100)
    tree.npcs[template.id] = template
    if safe:
        place(game, listener, 'core-precinct', (10, 5))
        place(game, shooter, 'core-precinct', (12, 5))
    actor = body(game, listener)
    npc = make_actor(template, 'test-origin:dialogue-worker', {})
    game.core.world.enter(npc, actor.zone, (actor.x, actor.y+1))
    open_talker(game, listener)
    assert listener.session.id in game.core.dialogue.menus
    before = actor.health
    from blacksite.server.rules import combat as combat_rules
    monkeypatch.setattr(combat_rules, 'to_hit', lambda *args: 100)
    fire(game, shooter, listener)  # Ordinary neutral-fire warning.
    game.step(20)  # Respect the ordinary two-second warning window.
    fire(game, shooter, listener)  # Deliberate second press, normal receipt.
    if safe:
        assert actor.health == before
    else:
        assert actor.health < before
    assert listener.session.id in game.core.dialogue.menus
    press(game, listener, 'b')
    assert listener.session.id not in game.core.dialogue.menus
