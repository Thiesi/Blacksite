"""Entities 1.11: content mistakes fail before a caller opens a talker."""

from copy import deepcopy
from dataclasses import replace

import pytest

from blacksite.content.loader import ContentTree
from blacksite.content.schema import Bark, DialogueLine, Offer
from blacksite.content.validate import validate
from tests.test_dialogue_runtime import content


@pytest.mark.parametrize(('change', 'message'), [
    ({'lines': (DialogueLine('fallback', 'Read the record.', tag='CUST'),)}, 'fallback cannot'),
    ({'barks': (Bark(''),)}, 'bark text'),
    ({'barks': (Bark('Wait.', weight=0),)}, 'weight and interval'),
    ({'barks': (Bark('Wait.', min_interval_seconds=0),)}, 'weight and interval'),
    ({'offers': (Offer('vendor', 'Trade', 'b', 'vesper'),)}, 'unique single key'),
    ({'offers': (Offer('service', 'Surgery', 's', 'vesper'),)}, 'no clinic service'),
    ({'lines': (DialogueLine('bad', 'Wait.', ('unknown_flag',)), DialogueLine('fallback', 'Sit.'))}, 'unknown condition'),
    ({'lines': (DialogueLine('bad', 'Wait.', ('receipt no-such-receipt',)), DialogueLine('fallback', 'Sit.'))}, 'no branch group'),
    ({'lines': (DialogueLine('bad', 'Wait.', ('chronicle_choice 999 no-such-option',)), DialogueLine('fallback', 'Sit.'))}, 'no season 999 finale option'),
])
def test_game_13_4_invalid_talker_fails_validation_before_runtime(
        content: ContentTree, change: dict, message: str) -> None:
    tree = deepcopy(content)
    tree.dialogue['vesper'] = replace(tree.dialogue['vesper'], **change)
    assert any(message in problem.message for problem in validate(tree))


def test_game_13_4_clinic_vendor_is_a_valid_service_reference(content: ContentTree) -> None:
    tree = deepcopy(content)
    tree.dialogue['vesper'] = replace(tree.dialogue['vesper'],
        offers=(Offer('service', 'Surgery', 's', 'sablier-clinic'),))
    assert validate(tree) == []


def test_game_13_4_unknown_terminal_and_cell_talker_references_fail(content: ContentTree) -> None:
    tree = deepcopy(content)
    zone = tree.zones['sodium-tin-halo']
    tree.zones[zone.id] = replace(zone, meta=replace(zone.meta, objects=tuple(
        replace(obj, params={**obj.params, 'dialogue': 'missing-terminal-talker'})
        if obj.id == 'vesper' else obj for obj in zone.meta.objects)))
    sector = tree.sectors[zone.meta.sector]
    tree.sectors[sector.id] = replace(sector, cells=tuple(
        replace(cell, dialogue='missing-cell-talker') if cell.id == sector.entry else cell
        for cell in sector.cells))
    messages = [problem.message for problem in validate(tree)]
    assert any('missing-terminal-talker' in message for message in messages)
    assert any('missing-cell-talker' in message for message in messages)
