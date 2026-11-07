"""Game 5.6 / architecture 5.5.2: exit underfoot and dispatch parity."""

import json
from pathlib import Path

import pytest

from blacksite.content.loader import ContentTree, load_content
from blacksite.server.protocol import Frame
from tests.presentation.exit_underfoot_matrix import CASES, PROMOTED, execute, setup


@pytest.fixture(scope='module')
def content() -> ContentTree:
    return load_content(Path(__file__).resolve().parents[2]/'src/blacksite/content')


@pytest.mark.parametrize('case', CASES)
@pytest.mark.parametrize('key', ['e', 'j'])
def test_game_5_6_predicted_equals_dispatched_and_j_equals_main(
        content: ContentTree, case: str, key: str) -> None:
    game, caller = setup(content, case)
    actual = execute(game, caller, Frame('key', {'k': key}))
    assert actual['predicted'] == actual['outcome']['handler']
    # JSON normalises tuples, just as the separately run main driver does.
    actual = json.loads(json.dumps(actual))
    baseline = json.loads(Path(__file__).with_name('exit-underfoot-baseline.json').read_text())[case][key]
    if key == 'j':
        # E focus may intentionally change even in a run that presses J.
        assert actual['predicted'] == baseline['predicted']
        assert actual['focus'][1] == baseline['focus'][1]
        assert actual['outcome'] == baseline['outcome']
    elif case not in PROMOTED:
        assert actual == baseline, (case, key, actual, baseline)
    else:
        assert actual['outcome']['handler'] == 'characters'
        assert actual['focus'][0]['verb'] == 'go to'
        assert not actual['outcome']['dialogue'] and not actual['outcome']['menus']
        assert baseline['outcome']['handler'] in ('contracts', 'commerce', 'npcs')
        if case in ('lift', 'tram'):
            assert actual['outcome']['travel']
        else:
            assert actual['outcome']['body'][0] != baseline['outcome']['body'][0]
    if key == 'e' and case == 'talker-off-exit':
        assert actual['outcome']['dialogue'] == 'row-street-regular'
    if key == 'e' and case == 'mission-action':
        assert actual['focus'][0]['verb'] == 'survey'
        assert actual['focus'][0]['id'] == 's39-contact'
        assert actual['outcome']['missions'][0][2] == 'complete'
        assert actual['outcome']['body'][0] == 'sodium-tin-halo'


def test_game_5_6_explicit_targeted_talk_is_never_promoted(content: ContentTree) -> None:
    game, caller = setup(content, 'contract-giver')
    actual = execute(game, caller, Frame('intent', {'name': 'talk', 'args': {'target': 's39-contact'}}))
    assert actual['outcome']['handler'] == 'contracts'
    assert actual['outcome']['dialogue'] == 's39-giver'
    assert actual['outcome']['body'][0] == 'sodium-tin-halo'
