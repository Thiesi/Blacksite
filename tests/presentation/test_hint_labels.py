"""Issue 104 / terminal UI 11: labels and aliases preserve input choices."""

from dataclasses import asdict, replace
import re
from typing import Any

import pytest

from blacksite.content.schema import ObjectSpec
from blacksite.content.validate import validate
from blacksite.door import chrome
from blacksite.door.model import Display
from blacksite.hints import focus_context
from blacksite.layout import compute
from blacksite.server.interaction import object_interaction
from blacksite.server.protocol import Frame
from blacksite.server.world.zone import ObjectState
from tests.character_helpers import place
from tests.door.conftest import info
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer
from tests.presentation.test_interaction_focus import focus_game


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
@pytest.mark.parametrize('tier', ['16', '256', 'truecolor'])
@pytest.mark.parametrize('keymap', ['arrows', 'vi'])
def test_ui_11_shared_terminal_has_one_group_and_no_generic_e(
    focus_game: tuple[HeadlessServer, Any], info: Any,
    size: tuple[int, int], tier: str, keymap: str,
) -> None:
    game, caller = focus_game
    caller.session.caps.update(width=size[0], height=size[1])
    caller.session.keymap_id = keymap
    place(game, caller, 'vatside-wake-hall', (36, 15))
    game.commit_commerce()
    game.step()
    body = game.core.characters.sim.views[caller.session.id].previous['body']
    assert body['focus'] == body['jack_focus']
    assert body['focus']['id'] == 'wake-terminal'
    model = Display(replace(info, width=size[0], height=size[1], color_depth=tier))
    model.receive(Frame('welcome', {'keymap': asdict(game.core.characters.content.keymaps),
        'palette': asdict(game.core.characters.content.palette),
        'player': {'settings': {'keymap': keymap}}}), 0)
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 1)
    terminal = FakeTerminal(*size)
    terminal.write(model.render(1)[0])
    row = terminal.screen_text().splitlines()[compute(*size).hint.y]
    alias = 'E/Ctrl-O' if keymap == 'vi' else 'E/J'
    assert row.count(alias+' jack in at Tutorial terminal') == 1
    assert 'E act' not in row and 'E interact' not in row
    assert '  J jack in at' not in row and '  Ctrl-O jack in at' not in row


@pytest.mark.parametrize(('other_id', 'other_verb'), [
    ('other-terminal', 'jack in at'), ('terminal', 'inspect'),
])
def test_ui_11_equal_names_do_not_hide_distinct_targets_or_verbs(other_id: str, other_verb: str) -> None:
    focus = {'id': 'terminal', 'verb': 'jack in at', 'label': 'Public terminal'}
    jack = {'id': other_id, 'verb': other_verb, 'label': 'Public terminal'}
    assert focus_context(focus, jack) == [
        ('E jack in at', 'Public terminal'), ('J '+other_verb, 'Public terminal')]


def test_ui_11_person_wording_only_changes_inspection(focus_game: tuple[HeadlessServer, Any]) -> None:
    game, _ = focus_game
    obj = ObjectState(ObjectSpec('person', (1, 1), 'vendor',
                                {'name': 'Counter attendant', 'inspect_verb': 'look at'}))
    inspection = object_interaction(obj, 'inspect')
    assert inspection.focus.verb == 'look at' and inspection.value is obj
    assert object_interaction(obj, 'open').focus.verb == 'open'
    content = game.core.characters.content
    person = next(o for o in content.zones['vatside-wake-hall'].meta.objects if o.id == 'vantongeren-desk')
    person.params['inspect_verb'] = 'grant membership'
    assert any('inspect_verb' in problem.message for problem in validate(content))


def test_ui_11_objective_retains_jobs_help_without_generic_e() -> None:
    context = [('E survey', 'Parcel')]
    objective = {'next_action': 'Survey Parcel', 'progress': '0/1', 'cost': '2s'}
    row = chrome.focus_hint('E survey Parcel  Next: legacy | E act Q jobs', 130, context, objective)
    assert row.startswith('Next: Survey Parcel 0/1 | 2s  E survey Parcel')
    assert 'Q jobs' in row and 'E act' not in row


@pytest.mark.parametrize('jack_key', ['J', 'Ctrl-O'])
def test_ui_11_combined_group_drops_j_before_a_fitting_e(jack_key: str) -> None:
    focus = {'id': 'terminal', 'label': 'Tutorial terminal', 'verb': 'jack in at'}
    context = focus_context(focus, focus, jack_key)
    raw = context[0][0]+' '+context[0][1]
    objective = {'next_action': 'Survey the marked loan cabinet', 'progress': '0/1', 'cost': '5s no fee'}
    row = chrome.focus_hint(raw+'  Next: legacy', 78, context, objective)
    assert row == 'Next: Survey the marked loan cabinet 0/1 | 5s no fee  E jack in at Tutorial...'


def test_ui_11_every_shipped_generic_public_terminal_uses_one_name_form(
    focus_game: tuple[HeadlessServer, Any],
) -> None:
    game, _ = focus_game
    public = []
    for zone in game.core.characters.content.zones.values():
        for obj in zone.meta.objects:
            name = str(obj.params.get('name', ''))
            if obj.kind == 'terminal' and ('public' in obj.id.split('-')
                    or re.search(r'\bpublic\b', name, re.IGNORECASE)):
                public.append(obj.id)
                assert re.fullmatch(r'Public terminal \([A-Z][^()]+\)', name), (zone.id, obj.id, name)
    assert public


def test_ui_11_shipped_people_use_look_at_and_things_keep_inspect(
    focus_game: tuple[HeadlessServer, Any],
) -> None:
    game, _ = focus_game
    # Role names catch omitted markers; explicit overrides also cover named
    # people whose names carry no occupation. Boards and counters are things.
    roles = re.compile(r'\b(recruiter|liaison|technicians?|tout|concierge|dealer|grocer|quartermaster|contract handler)$',
                       re.IGNORECASE)
    people = things = 0
    for zone in game.core.characters.content.zones.values():
        for spec in zone.meta.objects:
            name = str(spec.params.get('name', ''))
            if not name:
                continue
            person = bool(name.startswith('Dr. ') or roles.search(name)
                          or spec.params.get('inspect_verb') == 'look at')
            obj = ObjectState(spec)
            choice = object_interaction(obj, 'inspect')
            assert choice.focus.verb == ('look at' if person else 'inspect'), (zone.id, spec.id, name)
            assert choice.value is obj and choice.tile == spec.tile
            assert object_interaction(obj, 'open').focus.verb == 'open'
            people += person
            things += not person
    assert people and things
