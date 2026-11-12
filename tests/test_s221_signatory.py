"""#221: grade 5 is Signatory (canon #219); personhood is calendar only."""

from dataclasses import replace
from pathlib import Path
from random import Random

import pytest

from karst41.content.loader import load_content
from karst41.content.validate import validate
from karst41.server.contracts.requirements import describe
from karst41.server.dialogue import Facts, condition, evaluate


@pytest.fixture(scope='module')
def content():
    return load_content(Path(__file__).parents[1]/'src/karst41/content')


@pytest.mark.parametrize('grade,legal,signatory', [
    (1, False, False), (4, False, False), (5, False, True), (30, False, True), (1, True, True)])
def test_221_signatory_condition_is_grade_5_or_personhood(content, grade, legal, signatory):
    talker = content.dialogue['ivey']
    facts = Facts(grade=grade, legal=legal)
    assert condition('signatory', talker, facts) is signatory
    assert condition('not_signatory', talker, facts) is not signatory
    assert condition('is_wake', talker, facts) is not legal  # A Signatory is still a Wake.


@pytest.mark.parametrize('grade,legal,asked', [(1, False, True), (5, False, False), (1, True, False)])
def test_221_ivey_asks_for_a_signature_only_before_one(content, grade, legal, asked):
    line = evaluate(content.dialogue['ivey'], Facts(grade=grade, legal=legal, met=frozenset({'ivey'})), Random(0))
    assert (line.text == "A Wake wants a lease? Show me a Civic signature. I don't rent to numbers.") is asked


def test_221_grade_5_is_the_signatory_milestone(content):
    grade = next(g for g in content.grades.values() if g.grade == 5)
    assert grade.title == 'Signatory'
    assert grade.promotion == ("You reach grade 5. Civic registers your signature: you can rent and join. "
                               "The days still count.")
    tree = replace(content, grades={**content.grades, grade.id: replace(grade, title='Ninety-Day')})
    assert any('grade 5 is the Signatory milestone' in p.message for p in validate(tree))


def test_221_signatory_requirement_reads_plainly(content):
    assert describe('signatory', content) == 'Signatory (grade 5) or day 90'


def test_221_no_shipped_line_promises_an_early_discharge(content):
    root = Path(__file__).parents[1]/'src/karst41/content'
    texts = [p.read_text(encoding='utf-8') for p in (root/'text').glob('*')]
    texts += [line.text for talker in content.dialogue.values() for line in talker.lines]
    for text in texts:
        lowered = text.lower()
        assert 'early discharge' not in lowered and 'earn the discharge' not in lowered
        assert 'work certificate' not in lowered and 'clear it early' not in lowered
