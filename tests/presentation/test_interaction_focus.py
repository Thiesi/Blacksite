"""Architecture 5.5.2: one E/J decision, unchanged mechanics and disclosure."""

from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
from typing import Any

import pytest

from blacksite.content.loader import load_content
from blacksite.content.schema import ObjectSpec, StageTarget
from blacksite.door import chrome
from blacksite.door.cells import display_width
from blacksite.door.model import Display
from blacksite.layout import compute
from blacksite.server.bus import Event
from blacksite.server.commerce import CommerceMenu
from blacksite.server.lattice.presence import Presence
from blacksite.server.loop import TickContext
from blacksite.server.interaction import object_interaction
from blacksite.server.views import presentation
from blacksite.server.protocol import Frame
from blacksite.server.world.zone import ObjectState
from tests.character_helpers import create, place
from tests.harness import HeadlessServer
from tests.fake_terminal import FakeTerminal
from tests.door.conftest import info
from tests.presentation.interaction_matrix import ORDER, run_matrix


E = Frame('key', {'k': 'e', 't': 0})


@pytest.fixture
def focus_game(repo_root: Path) -> tuple[HeadlessServer, Any]:
    game = HeadlessServer(load_content(repo_root/'src/blacksite/content'), character_state={})
    caller = game.connect()
    create(game, caller, archetype=0, card='none')
    game.commit_characters()
    game.commit_commerce()
    return game, caller


def dispatch(game: HeadlessServer, caller: Any, frame: Frame = E) -> None:
    game.core._echo(Event('input', {'session': caller.session, 'frame': frame, 'tick': game.clock.now_tick()}))


def test_arch_5_5_2_predicted_equals_dispatched_and_pre_p3_behavior(repo_root: Path) -> None:
    labels: set[tuple[str, str]] = set()
    def inspect(core: Any, session: Any, prediction: Any) -> None:
        if prediction and prediction.choice.focus:
            focus = prediction.choice.focus
            assert_label_source(core, session, focus)
            labels.add((focus.verb, focus.label))
    result, _ = run_matrix(repo_root, inspect_focus=inspect)
    baseline = json.loads(Path(__file__).with_name('interaction-baseline.json').read_text())
    assert result['cases'] == baseline['cases']
    assert result['sha256'] == baseline['sha256'], 'E/J behavior differs from the independently executed pre-P3 baseline'
    assert result['handlers'] == baseline['handlers']
    packet = json.loads((repo_root/'docs/ops/captures/issue104-hint-labels/focus-labels.json').read_text())
    assert sorted(labels) == [tuple(pair) for pair in packet['matrix_pairs']]


def assert_label_source(core: Any, session: Any, focus: Any) -> None:
    """Every matrix label names its selected entity; ids are not a fallback."""
    if not focus.label:
        assert focus.verb in ('jack in', 'jack out')
        return
    actor = core.characters.sim.avatars[session.user_id].actor
    if focus.id in core.world.actors:
        assert focus.label == presentation.name(core.world.actors[focus.id], actor, core.characters.content)
        return
    zone = core.world.zones[actor.zone]
    if focus.id in zone.objects:
        assert focus.label == zone.objects[focus.id].spec.params.get('name')
        return
    for exit in zone.template.meta.exits:
        if focus.id == exit.id:
            assert focus.label == core.world.zones[exit.target_zone].template.meta.name
            return
    presence = core.lattice.presences.get(session.player_id)
    if presence:
        cell = core.lattice.sectors.cells[presence.sector][presence.cell]
        assert focus.id == presence.sector+':'+cell.id and focus.label == cell.label
        return
    pytest.fail(f'No authored label source for {focus!r}')


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
@pytest.mark.parametrize('tier', ['16', '256', 'truecolor'])
@pytest.mark.parametrize('keymap', ['arrows', 'vi'])
def test_ui_3_focus_changes_only_existing_hint_cells(focus_game: tuple[HeadlessServer, Any], info: Any,
                                                  size: tuple[int, int], tier: str, keymap: str) -> None:
    game, caller = focus_game
    core = game.core
    caller.session.caps.update(width=size[0], height=size[1])
    caller.session.keymap_id = keymap
    place(game, caller, 'vatside-wake-hall', (34, 15))
    game.commit_commerce()
    game.step()
    body = core.characters.sim.views[caller.session.id].previous['body']
    assert body['focus']['id'] == 'wake-outfitter'
    legacy = deepcopy(body)
    legacy.pop('focus')
    legacy.pop('jack_focus')
    legacy['hint'] = 'Tab target  F fire  X weapon  1-5 quick  V abilities  E interact  I inventory  ? help'
    def render(document: dict[str, Any]) -> FakeTerminal:
        model = Display(replace(info, width=size[0], height=size[1], color_depth=tier))
        model.receive(Frame('welcome', {'keymap': asdict(core.characters.content.keymaps),
            'palette': asdict(core.characters.content.palette), 'player': {'settings': {'keymap': keymap}}}), 0)
        model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': document}), 1)
        terminal = FakeTerminal(*size)
        terminal.write(model.render(1)[0])
        return terminal
    before, after = render(legacy), render(body)
    hint = compute(*size).hint
    changed = {y for y in range(size[1]) if before.grid[y] != after.grid[y]
        or any(before.renditions.get((x, y)) != after.renditions.get((x, y)) for x in range(size[0]))}
    assert changed == {hint.y}
    assert 'E open Sablier Wake Outfitter' in after.screen_text().splitlines()[hint.y]
    jack_key = 'Ctrl-O' if keymap == 'vi' else 'J'
    assert jack_key+' jack in at Tutorial terminal' in after.screen_text().splitlines()[hint.y]
    row = after.screen_text().splitlines()[hint.y][hint.x:hint.right].rstrip()
    context = ['E open Sablier Wake Outfitter', jack_key+' jack in at Tutorial terminal']
    optional = legacy['hint'].split('  ')
    assert row.split('  ')[:2] == context
    assert all(group in optional for group in row.split('  ')[2:]), (row, optional)
    assert '? help' in row


@pytest.mark.parametrize('kind', ['light', 'camera', 'salvage_field', 'descent_console'])
def test_arch_5_5_2_s25a_underfoot_and_explicit_j(focus_game: tuple[HeadlessServer, Any], kind: str) -> None:
    game, caller = focus_game
    core = game.core
    zone = core.world.zones['vatside-wake-hall']
    terminal = next(obj for obj in zone.objects.values() if obj.spec.kind == 'terminal')
    tile = terminal.spec.tile[0]+1, terminal.spec.tile[1]
    place(game, caller, zone.id, tile)
    game.commit_commerce()
    zone.objects['fixture-prop'] = ObjectState(ObjectSpec('fixture-prop', tile, kind,
        params={'name': 'Sealed season door', 'season_door': True} if kind == 'descent_console' else {}))
    e, jack = core.interaction_views(caller.session)
    assert jack and jack['id'] == terminal.spec.id
    assert e and e['id'] == ('fixture-prop' if kind == 'descent_console' else terminal.spec.id)
    dispatch(game, caller)
    assert (caller.session.player_id in core.lattice.presences) == (kind != 'descent_console')
    if kind == 'descent_console':
        assert caller.session.log_ring[-1]['text'] == 'Sealed season door'
        dispatch(game, caller, Frame('key', {'k': 'j'}))
        assert caller.session.player_id in core.lattice.presences


def test_arch_5_5_2_unseen_winner_is_masked_without_falling_through(focus_game: tuple[HeadlessServer, Any]) -> None:
    game, caller = focus_game
    core = game.core
    zone = core.world.zones['vatside-wake-hall']
    # An opaque intervening wall can hide a cabinet within Interlock's
    # existing three-tile inspection range. Do not change that rule in P3.
    place(game, caller, zone.id, (15, 5))
    zone.objects.clear()
    obj = ObjectState(ObjectSpec('fixture-hidden-cabinet', (18, 5), 'hardware', {'name': 'Hidden cabinet'}))
    zone.objects[obj.spec.id] = obj
    core.lattice.interlock.hardware = {(zone.id, obj.spec.id): {}}
    zone.geometry[16, 5] = 'wall'
    zone.geometry_revision += 1
    result = core.resolve_interaction(caller.session, E)
    assert result.route.name == 'interlock' and result.choice.focus.id == obj.spec.id
    assert core.interaction_views(caller.session)[0] is None
    dispatch(game, caller)
    assert core.lattice.interlock.menus[caller.session.id][:2] == (zone.id, obj.spec.id)


@pytest.mark.parametrize('keymap,key', [('arrows', 'j'), ('vi', 'ctrl-o')])
def test_arch_5_5_2_j_keymap_and_jacked_return(focus_game: tuple[HeadlessServer, Any], keymap: str, key: str) -> None:
    game, caller = focus_game
    core, session = game.core, caller.session
    session.keymap_id = keymap
    avatar = core.characters.sim.avatars[session.user_id]
    lat = core.lattice
    sector = 'lat-vatside'
    cell = lat.sectors.entrance(sector)
    presence = Presence(avatar.actor.id+':presence', avatar.actor.id, sector, cell,
                        ('prg_pick', 'prg_umbrella', None), loaned_rig=True)
    lat.presences[session.player_id] = presence
    avatar.actor.stance = 'jacked'
    focus, jack = core.interaction_views(session)
    assert jack == {'id': avatar.actor.id, 'label': '', 'verb': 'jack out'}
    predicted = core.resolve_interaction(session, Frame('key', {'k': key}))
    assert predicted.route.name == 'lattice'
    dispatch(game, caller, Frame('key', {'k': key}))
    assert session.player_id not in lat.presences or presence.escape is not None


def test_arch_5_5_2_lattice_cells_inspect_before_using_uplinks(focus_game: tuple[HeadlessServer, Any]) -> None:
    game, caller = focus_game
    core, session = game.core, caller.session
    lat = core.lattice
    actor = core.characters.sim.avatars[session.user_id].actor
    inspected = uplinks = 0
    for sector, cells in lat.sectors.cells.items():
        for cell in cells.values():
            presence = Presence(actor.id+':presence', actor.id, sector, cell.id,
                                ('prg_pick', 'prg_umbrella', None), loaned_rig=True)
            lat.presences[session.player_id] = presence
            actor.stance = 'jacked'
            lat.encounters.menus.clear()
            session.log_ring.clear()
            result = core.resolve_interaction(session, E)
            assert result.route.name == 'lattice'
            dispatch(game, caller)
            if result.choice.kind == 'encounter':
                inspected += 1
                assert result.choice.focus.id == sector+':'+cell.id
                assert session.id in lat.encounters.menus
                assert presence.destination is None  # Inspection precedes an uplink.
            elif cell.uplink:
                uplinks += 1
                assert result.choice.focus.id == sector+':'+cell.id
                assert session.id not in lat.encounters.menus
                assert presence.destination == (cell.uplink.sector, cell.uplink.cell) or session.log_ring
            else:
                assert result.choice.focus is None and presence.destination is None
    assert inspected and uplinks


def query_state(game: HeadlessServer, caller: Any) -> dict[str, Any]:
    core = game.core
    return deepcopy({
        'players': [player.record() for player in core.characters.players.values()],
        'identities': core.characters.identities,
        'items': [item.record() for item in core.commerce.items.values()],
        'actors': {key: asdict(actor) for key, actor in core.world.actors.items()},
        'objects': {zid: {oid: asdict(obj) for oid, obj in zone.objects.items()}
                    for zid, zone in core.world.zones.items()},
        'rng': {zid: zone.rng.getstate() for zid, zone in core.world.zones.items()},
        'presence': {pid: asdict(p) for pid, p in core.lattice.presences.items()},
        'commerce': (core.commerce.pending, core.commerce.outbox, core.commerce.waiting),
        'characters_outbox': core.characters.outbox,
        'session': (caller.session.send_queue, caller.session.log_ring, caller.session.pending_prompts),
    })


@pytest.mark.parametrize('jacked', [False, True])
def test_arch_5_5_2_queries_are_pure(focus_game: tuple[HeadlessServer, Any], jacked: bool) -> None:
    game, caller = focus_game
    core, session = game.core, caller.session
    place(game, caller, 'vatside-wake-hall', (34, 15))
    game.commit_commerce()
    if jacked:
        core.lattice.jack_in(session)
    before = query_state(game, caller)
    for key in ('e', 'j'):
        for route in core.input_routes():
            route.query(session, Frame('key', {'k': key}))
        core.resolve_interaction(session, Frame('key', {'k': key}))
    assert query_state(game, caller) == before


@pytest.mark.parametrize('mode', ['commerce', 'chat-key', 'chat-intent', 'travel', 'down'])
def test_arch_5_5_2_modal_and_disabled_states_do_not_advertise_world_targets(
        focus_game: tuple[HeadlessServer, Any], mode: str) -> None:
    game, caller = focus_game
    core, session = game.core, caller.session
    place(game, caller, 'vatside-wake-hall', (34, 15))
    game.commit_commerce()
    frame = E
    if mode == 'commerce':
        core.commerce.menus[session.id] = CommerceMenu('inventory')
        expected = 'commerce'
    elif mode.startswith('chat'):
        # Two tiles from the outfitter counter, so its NPC service does not
        # own E before the chat handler. No NPC placement changes are needed.
        place(game, caller, 'vatside-wake-hall', (36, 15))
        game.commit_commerce()
        session.pending_prompts['chat'] = {'id': 'chat', 'channel': 'say'}
        if mode == 'chat-intent':
            frame = Frame('intent', {'name': 'interact', 'args': {}})
            # Existing chat blocks keys, not Interact intents. Preserve that
            # distinction rather than "fixing" it during presentation work.
            expected = 'terminal'
        else:
            expected = 'chat'
    elif mode == 'travel':
        from blacksite.server.world.exits import schedule
        avatar = core.characters.sim.avatars[session.user_id]
        ex = core.world.zones[avatar.zone].template.meta.exits[0]
        avatar.travel = schedule(replace(ex, kind='lift'), game.clock.now_utc().timestamp())
        expected = 'characters'
    else:
        core.characters.players[session.player_id].progress['combat'] = {'stage': 'down'}
        expected = 'combat'
    result = core.resolve_interaction(session, frame)
    assert result.route.name == expected
    assert result.choice.focus is None or mode == 'chat-intent'
    assert [route.name for route in core.input_routes()] == list(ORDER)
    dispatch(game, caller, frame)


@pytest.mark.parametrize('key', ['J', 'Ctrl-O'])
def test_ui_3_focus_hint_shortens_only_labels_and_keeps_help(key: str) -> None:
    context = [('E talk to', 'Long界 name '*20), (f'{key} jack in at', 'Terminal界 '*20)]
    raw = '  '.join((prefix+' '+label).rstrip() for prefix, label in context)
    hint = chrome.focus_hint(raw+'  Move: arrows  Shift: sprint  ? help  Ctrl-X leave', 78, context)
    groups = hint.split('  ')
    assert display_width(hint) <= 78
    assert groups[0].startswith('E talk to Long界') and groups[0].endswith('...')
    assert groups[1].startswith(key+' jack in at Terminal界') and groups[1].endswith('...')
    assert all(group in ('Move: arrows', 'Shift: sprint', '? help', 'Ctrl-X leave') for group in groups[2:])
    short = [('E open', 'Counter'), (key+' jack in at', 'Terminal')]
    raw = '  '.join(prefix+' '+label for prefix, label in short)
    result = chrome.focus_hint(raw+'  This group cannot possibly fit in the remaining space  ? help  M map', 78, short)
    assert result == raw+'  ? help  M map'


@pytest.mark.parametrize('width', [78, 130])
@pytest.mark.parametrize('key', ['J', 'Ctrl-O'])
def test_ui_11_objective_and_cost_precede_shortened_context(width: int, key: str) -> None:
    objective = {'next_action': 'Survey here', 'progress': '0/1', 'cost': '2s'}
    context = [('E open', 'Sablier '+('counter '*20)), (key+' jack in at', 'Tutorial '+('terminal '*20))]
    raw = '  '.join((prefix+' '+label).rstrip() for prefix, label in context)
    hint = chrome.focus_hint(raw+'  Next: Survey here 0/1 | 2s | E act Q jobs  F8 relays',
                             width, context, objective)
    groups = hint.split('  ')
    assert groups[0] == 'Next: Survey here 0/1 | 2s'
    assert groups[1].startswith('E open Sablier') and groups[1].endswith('...')
    assert groups[2].startswith(key+' jack in at Tutorial') and groups[2].endswith('...')
    assert display_width(hint) <= width


def test_ui_11_drop_j_then_e_before_shortening_objective() -> None:
    context = [('E open', 'Sablier counter'), ('J jack in at', 'Tutorial terminal')]
    raw = '  '.join(prefix+' '+label for prefix, label in context)
    objective = {'next_action': 'Survey the marked parcel at the gate', 'progress': '0/1', 'cost': '2s'}
    hint = chrome.focus_hint(raw+'  Next: legacy', 78, context, objective)
    assert hint.startswith('Next: Survey the marked parcel at the gate 0/1 | 2s  E open Sablier')
    assert 'J jack in at' not in hint
    objective['next_action'] = 'Survey the marked parcel at the far end of the gate'
    hint = chrome.focus_hint(raw+'  Next: legacy', 78, context, objective)
    assert 'E open' not in hint and 'J jack in at' not in hint
    assert objective['next_action'] in hint  # Still no objective shortening.
    objective['next_action'] += ' beyond the long passage '*8
    objective['cost'] = '5s E: manual 5 s, network 0 trace'
    hint = chrome.focus_hint(raw+'  Next: legacy', 78, context, objective)
    assert hint.startswith('Next: Survey ') and '...' in hint
    assert hint.endswith('0/1 | '+objective['cost'])
    assert display_width(hint) <= 78


def test_ui_11_names_never_shorten_before_their_first_word() -> None:
    context = [('E open', '界'*60+' counter'), ('J jack in at', 'Tutorial terminal')]
    raw = '  '.join(prefix+' '+label for prefix, label in context)
    hint = chrome.focus_hint(raw+'  ? help  M map', 78, context)
    assert hint == '? help  M map'  # Drop J, then the unshrinkable E group.
    assert chrome.focus_hint('E open Counter  M map  ? help', 78,
                             [('E open', 'Counter')]) == 'E open Counter  ? help  M map'


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
def test_ui_11_zone_renderer_retains_objective_without_focus(
        focus_game: tuple[HeadlessServer, Any], info: Any, size: tuple[int, int]) -> None:
    # Unnamed or occluded targets may have no focus. Their active objective
    # still owns the compact hint, rather than falling back to tail clipping.
    objective = {'next_action': 'Release the parcel hatch at the end of the corridor',
                 'progress': '0/1', 'cost': '5s E: manual 5 s, network 0 trace'}
    game, caller = focus_game
    caller.session.caps.update(width=size[0], height=size[1])
    game.step()
    body = deepcopy(game.core.characters.sim.views[caller.session.id].previous['body'])
    body.update(objective=objective, hint='Next: legacy marker', focus=None, jack_focus=None)
    model = Display(replace(info, width=size[0], height=size[1]))
    model.receive(Frame('welcome', {'keymap': asdict(game.core.characters.content.keymaps),
                                   'palette': asdict(game.core.characters.content.palette)}), 0)
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 1)
    terminal = FakeTerminal(*size)
    terminal.write(model.render(1)[0])
    row = terminal.screen_text().splitlines()[compute(*size).hint.y]
    assert 'Next: Release' in row and objective['cost'] in row


def test_ui_3_channel_progress_owns_hint_row(focus_game: tuple[HeadlessServer, Any]) -> None:
    game, caller = focus_game
    place(game, caller, 'vatside-wake-hall', (34, 15))
    game.commit_commerce()
    sim = game.core.characters.sim
    channel = {'owner': 'contract', 'label': 'Planting', 'remaining': 1.5}
    sim.avatars[caller.session.user_id].actor.behaviour['channel'] = channel
    game.clock.advance()
    sim.publish(TickContext(game.clock.now_tick(), game.clock, game.core.bus, (caller.session,), game.core.characters.content))
    body = sim.views[caller.session.id].previous['body']
    assert body['focus']['id'] == 'wake-outfitter'  # Mechanics still select the same target.
    assert body['hint'] == 'Planting 1.5s  Stay still; Esc/B cancels.'


@pytest.mark.parametrize('verb,object_verb,tile_verb', [
    ('fetch', 'take', 'take'), ('plant', 'plant at', 'plant'),
    ('hack', 'hack', 'hack'), ('survey', 'survey', 'survey')])
def test_ui_3_contract_hint_words(focus_game: tuple[HeadlessServer, Any], verb: str,
                                 object_verb: str, tile_verb: str) -> None:
    game, caller = focus_game
    actor = game.core.characters.sim.avatars[caller.session.user_id].actor
    target = StageTarget('object', zone=actor.zone, object='wake-outfitter')
    choice = game.core.contracts.actions.target_interaction(actor, target, verb)
    assert choice.focus.record() == {'id': 'wake-outfitter', 'label': 'Sablier Wake Outfitter', 'verb': object_verb}
    target = StageTarget('tile', zone=actor.zone, tile=actor.position)
    choice = game.core.contracts.actions.target_interaction(actor, target, verb)
    assert choice.focus.label == 'here' and choice.focus.verb == tile_verb


def test_ui_3_unnamed_objects_keep_input_target_without_raw_id() -> None:
    obj = ObjectState(ObjectSpec('raw-internal-object-id', (1, 1), 'door', {}))
    choice = object_interaction(obj, 'use')
    assert choice.value is obj and choice.tile == obj.spec.tile and choice.focus is None


def test_arch_5_5_2_unnamed_recruiter_still_opens_selected_board(
        focus_game: tuple[HeadlessServer, Any]) -> None:
    game, caller = focus_game
    zone = game.core.world.zones['vatside-wake-hall']
    board = next(obj for obj in zone.objects.values() if obj.spec.params.get('recruiters'))
    board.spec = replace(board.spec, params={k: v for k, v in board.spec.params.items() if k != 'name'})
    # Input fixture, not movement acceptance: the board's own tile wins.
    place(game, caller, zone.id, board.spec.tile)
    game.commit_commerce()
    choice = game.core.resolve_interaction(caller.session, E)
    assert choice.route.name == 'factions' and choice.choice.focus is None
    dispatch(game, caller)
    assert game.core.factions.menus[caller.session.id].target == board.spec.id
