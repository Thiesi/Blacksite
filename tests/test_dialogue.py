"""Game 13.4 / entities 1.11: personal conditions and optional voices."""

from dataclasses import replace
from random import Random

import pytest

from blacksite.content.schema import Bark, DIALOGUE_CONDITIONS, DialogueLine, DialogueNode, Offer
from blacksite.server.dialogue import BarkScheduler, Facts, condition, eligible_offers, evaluate


TALKER = DialogueNode('vesper', 'Vesper', (DialogueLine('fallback', 'Sit. The door stays open.'),))


CONDITION_CASES = (
    ('first_meeting', Facts(), Facts(met=frozenset({'vesper'}))),
    ('grade_below 5', Facts(grade=4), Facts(grade=5)),
    ('grade_at_least 5', Facts(grade=5), Facts(grade=4)),
    ('is_wake', Facts(legal=False), Facts(legal=True)),
    ('standing_below sable 10', Facts(standing={'sable': 9}), Facts(standing={'sable': 10})),
    ('standing_at_least sable 10', Facts(standing={'sable': 10}), Facts(standing={'sable': 9})),
    ('member_of sable', Facts(faction='sable'), Facts()),
    ('not_member_of sable', Facts(), Facts(faction='sable')),
    ('enemy_of_me', Facts(enemy=True), Facts()),
    ('marked', Facts(marked=True), Facts()),
    ('not_marked', Facts(), Facts(marked=True)),
    ('has_contract delivery', Facts(contracts={'delivery': 0}), Facts()),
    ('contract_stage delivery 0', Facts(contracts={'delivery': 0}), Facts(contracts={'delivery': 1})),
    ('completed_contract delivery', Facts(completed=frozenset({'delivery'})), Facts()),
    ('has_item power', Facts(items=frozenset({'power'})), Facts()),
    ('season_stage finale_done', Facts(season_stage='finale_done'), Facts()),
    ('chronicle_choice 1 seal', Facts(chronicle={1: 'seal'}), Facts(chronicle={1: 'open'})),
    ('event_active exhale', Facts(events=frozenset({'exhale'})), Facts()),
    ('archetype ghost', Facts(archetype='ghost'), Facts()),
    ('balance CUST', Facts(balance=-1), Facts(balance=1)),
    ('has_evidence thermal', Facts(evidence=frozenset({'thermal'})), Facts()),
    ('receipt clinic', Facts(receipts=frozenset({'clinic'})), Facts()),
    ('service_state sump allocated', Facts(services={'sump': 'allocated'}), Facts(services={'sump': 'fault'})),
    ('legal', Facts(legal=True), Facts()),
    ('not_legal', Facts(), Facts(legal=True)),
)


@pytest.mark.parametrize(('text', 'yes', 'no'), CONDITION_CASES)
def test_game_13_4_each_condition_changes_with_the_viewers_actual_facts(
        text: str, yes: Facts, no: Facts) -> None:
    assert condition(text, TALKER, yes)
    assert not condition(text, TALKER, no)


def test_game_13_4_closed_condition_set_is_fully_exercised() -> None:
    assert {case[0].split()[0] for case in CONDITION_CASES} == set(DIALOGUE_CONDITIONS)


def test_game_13_4_first_match_and_personal_offer_do_not_consume_first_meeting() -> None:
    talker = replace(TALKER, lines=(DialogueLine('marked', 'Take the back seat.', ('marked',)),
                                  DialogueLine('new', 'Show me the card.', ('first_meeting',)),
                                  *TALKER.lines), offers=(
        Offer('contract', 'Work', 'c', 'delivery', ('not_marked',)),))
    facts = Facts()
    assert evaluate(talker, facts, Random(0)).id == 'new'
    assert evaluate(talker, Facts(marked=True), Random(0)).id == 'marked'
    assert evaluate(talker, replace(facts, met=frozenset({'vesper'})), Random(0)).id == 'fallback'
    assert eligible_offers(talker, facts) == talker.offers
    assert not eligible_offers(talker, Facts(marked=True))
    assert not facts.met  # The adapter records only a committed interaction.


def test_game_13_4_required_opposing_voice_and_instructions_are_never_skipped() -> None:
    rng = Random(7)
    talker = replace(TALKER, lines=(DialogueLine('required', 'Read the labelled record.', tag='CUST', required=True),
                                  *TALKER.lines))
    assert all(evaluate(talker, Facts(balance=3), rng).id == 'required' for _ in range(100))


def test_game_13_4_optional_opposing_voice_uses_seeded_balance_weights() -> None:
    talker = replace(TALKER, lines=(DialogueLine('voice', 'The door remembers.', tag='CUST'), *TALKER.lines))
    class Draw(Random):
        def random(self) -> float:
            return .8

    assert evaluate(talker, Facts(balance=0), Draw()).id == 'voice'
    assert evaluate(talker, Facts(balance=-3), Draw()).id == 'voice'
    assert evaluate(talker, Facts(balance=1), Draw()).id == 'voice'
    assert evaluate(talker, Facts(balance=2), Draw()).id == 'voice'
    assert evaluate(talker, Facts(balance=3), Draw()).id == 'fallback'
    first, second = Random(17), Random(17)
    assert [evaluate(talker, Facts(balance=1), first).id for _ in range(100)] == [
        evaluate(talker, Facts(balance=1), second).id for _ in range(100)]


def test_game_13_4_bark_needs_an_audience_and_stays_silent_during_interaction() -> None:
    talker = replace(TALKER, barks=(Bark('The ring stays dark.'),))
    scheduler, rng = BarkScheduler(), Random(0)
    assert scheduler.choose(talker, 0, rng, nearby=False, interacting=False) is None
    assert scheduler.choose(talker, 0, rng, nearby=True, interacting=True) is None
    assert not scheduler.next_due
    assert scheduler.choose(talker, 0, rng, nearby=True, interacting=False) == talker.barks[0]
    assert scheduler.choose(talker, 899, rng, nearby=True, interacting=False) is None
    assert scheduler.choose(talker, 900, rng, nearby=True, interacting=False) == talker.barks[0]
