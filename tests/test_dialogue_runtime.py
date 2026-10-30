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
    # Only this fixture's Vesper is active. Shipped cast and all future
    # placement remain authoring content under issue #82.
    bundle = tree.bundles['s27-cast']
    tree.bundles[bundle.id] = replace(bundle, members={
        **bundle.members, 'dialogue': tuple(did for did in bundle.members['dialogue'] if did != 'vesper')})
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


def test_game_13_4_story_hotkey_selects_its_card_ahead_of_an_unrelated_active_job(content: ContentTree) -> None:
    game, caller, player = setup(content)
    owner = game.core.contracts
    other = replace(owner.content.contracts['vesper-first-thing'], id='unrelated-story')
    owner.content.contracts[other.id] = other
    owner.state.engine.templates[other.id] = other
    owner.state.engine.accept(owner.state.engine.story_offer(other.id, player.id),
                              (owner.participant(player.id),), owner.now())
    open_talker(game, caller)
    press(game, caller, 'c')
    panel = owner.panels.menus[caller.session.id]
    assert owner.panels.rows(caller.session, panel)[panel.cursor]['id'] == 'vesper-first-thing'


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
    bundle = tree.bundles['s27-cast']
    tree.bundles[bundle.id] = replace(bundle, members={
        **bundle.members, 'dialogue': tuple(did for did in bundle.members['dialogue'] if did != 'ninety-nine')})
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


def test_arch_5_5_3_authored_barks_stay_dormant_until_p8(content: ContentTree) -> None:
    game, caller, player = setup(content)
    zone = game.core.world.zones[player.zone]
    game.frames_for(caller)
    state = zone.rng.getstate()
    # The dialogue subsystem must not run a competing emitter or consume
    # simulation randomness while P8 is pending.
    from types import SimpleNamespace
    game.core.dialogue.tick(SimpleNamespace(tick=900, sessions=[caller.session]))
    assert zone.rng.getstate() == state
    assert not [line for frame in game.frames_for(caller) if frame.type == 'log'
                for line in frame.data['lines'] if 'The ring stays dark.' in line['text']]


def test_arch_5_5_2_talker_focus_is_pure_and_matches_e(content: ContentTree) -> None:
    game, caller, player = setup(content)
    zone = game.core.world.zones[player.zone]
    state = zone.rng.getstate()
    for _ in range(3):
        focus, _ = game.core.interaction_views(caller.session)
        assert focus == {'id': 'vesper', 'label': 'Vesper', 'verb': 'talk to'}
    assert zone.rng.getstate() == state
    assert not game.core.dialogue.menus and 'met_talkers' not in player.progress
    game.frames_for(caller)
    open_talker(game, caller)
    assert game.core.dialogue.menus[caller.session.id].contact.target == focus['id']
    speech = [line for frame in game.frames_for(caller) if frame.type == 'log'
              for line in frame.data['lines'] if line['kind'] == 'speech']
    assert any(line['speaker'] == 'Vesper' and line['speaker_role'] == 'service' for line in speech)


@pytest.mark.parametrize('kind', ['vendor', 'service'])
def test_entities_1_11_handoff_uses_the_local_counter_not_template_object_id(
        content: ContentTree, kind: str) -> None:
    tree = deepcopy(content)
    tree.vendors['fixture-counter'] = replace(tree.vendors['vesper'], id='fixture-counter',
        object_id=None, clinic='sablier' if kind == 'service' else None)
    tree.dialogue['vesper'] = replace(tree.dialogue['vesper'], offers=(
        Offer(kind, 'Read terms', 's' if kind == 'service' else 'v', 'fixture-counter'),))
    zone = tree.zones['sodium-tin-halo']
    tree.zones[zone.id] = replace(zone, meta=replace(zone.meta, objects=tuple(
        replace(obj, params={**obj.params, 'vendor': 'fixture-counter'}) if obj.id == 'vesper' else obj
        for obj in zone.meta.objects)))
    game, caller, player = setup(tree)
    before = player.chits_hand, list(player.inventory), dict(player.implants)
    open_talker(game, caller)
    press(game, caller, 's' if kind == 'service' else 'v')
    assert caller.session.id not in game.core.dialogue.menus
    if kind == 'service':
        assert game.core.progression.clinics.menus[caller.session.id].target == 'vesper'
    else:
        assert game.core.commerce.menus[caller.session.id].target == 'vesper'
    press(game, caller, 'b')
    assert (player.chits_hand, player.inventory, player.implants) == before


def test_game_7_2_talker_join_hotkey_opens_verbatim_terms_without_membership(content: ContentTree) -> None:
    tree = deepcopy(content)
    tree.dialogue['vesper'] = replace(tree.dialogue['vesper'], offers=(
        Offer('recruit', 'Read terms', 'j', 'wardens'),))
    zone = tree.zones['sodium-tin-halo']
    tree.zones[zone.id] = replace(zone, meta=replace(zone.meta, objects=tuple(
        replace(obj, params={**obj.params, 'recruiters': ['wardens']}) if obj.id == 'vesper' else obj
        for obj in zone.meta.objects)))
    game, caller, player = setup(tree)
    open_talker(game, caller)
    press(game, caller, 'j')
    assert caller.session.id not in game.core.dialogue.menus
    assert game.core.factions.menus[caller.session.id].target == 'vesper'
    assert player.faction is None and not player.legal_at
    assert game.core.factions.card('wardens').pitch == 'faction-wardens-pitch'
    press(game, caller, 'b')
    assert player.faction is None


def test_game_13_4_scripted_machine_bank_cannot_be_an_ordinary_talker(content: ContentTree) -> None:
    tree = deepcopy(content)
    tree.dialogue['vesper'] = replace(tree.dialogue['vesper'], machine_mind=True)
    game, caller, player = setup(tree)
    assert game.core.dialogue.contact(caller.session) is None
    open_talker(game, caller)
    assert not game.core.dialogue.menus and 'met_talkers' not in player.progress


def test_arch_5_5_2_unseen_actor_cannot_open_a_named_talker(
        content: ContentTree, monkeypatch: pytest.MonkeyPatch) -> None:
    game, caller, player = setup(content)
    tree = game.core.loop.content
    original = next(npc for npc in tree.npcs.values() if not npc.training)
    template = replace(original, id='hidden-contact', name='Hidden contact', faction=None,
                       behaviours=(), dialogue='vesper', health=100)
    tree.npcs[template.id] = template
    actor = game.core.characters.sim.avatars[caller.session.user_id].actor
    npc = make_actor(template, 'test-origin:hidden-contact', {})
    game.core.world.enter(npc, actor.zone, (actor.x, actor.y+1))
    monkeypatch.setattr(game.core.combat, 'visible', lambda viewer, target: False)
    assert game.core.dialogue.contact(caller.session, npc.id) is None
    act(game, caller, Frame('intent', {'name': 'talk', 'args': {'target': npc.id}}))
    assert not game.core.dialogue.menus and 'met_talkers' not in player.progress


@pytest.mark.parametrize('locked', [False, True])
def test_game_13_4_travel_hotkey_uses_the_selected_exit_and_its_existing_lock(
        content: ContentTree, locked: bool) -> None:
    tree = deepcopy(content)
    zone = tree.zones['sodium-tin-halo']
    exit = next(exit for exit in zone.meta.exits if not exit.hidden)
    tree.zones[zone.id] = replace(zone, meta=replace(zone.meta, objects=tuple(
        replace(obj, tile=exit.tile) if obj.id == 'vesper' else obj for obj in zone.meta.objects)))
    tree.dialogue['vesper'] = replace(tree.dialogue['vesper'], offers=(
        Offer('travel', 'Read route', 't', exit.target_zone),))
    game, caller, player = setup(tree)
    if locked:
        game.core.characters.sim.locked_exits.add((zone.id, exit.id))
    open_talker(game, caller)
    press(game, caller, 't')
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    assert caller.session.id not in game.core.dialogue.menus
    if locked:
        assert avatar.zone == zone.id and avatar.travel is None
    else:
        assert avatar.zone == exit.target_zone or avatar.travel.exit.id == exit.id


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
