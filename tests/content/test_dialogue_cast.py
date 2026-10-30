"""Game 13.4 / S27: complete authored cast, personal records and held delivery."""

from pathlib import Path
from random import Random
import re

import pytest

from blacksite.content.loader import ContentTree, load_content
from blacksite.content.schema import DIALOGUE_CONDITIONS
from blacksite.content.validate import validate
from blacksite.server.dialogue import Facts, eligible_offers, evaluate, matches


FIXED = {'vantongeren', 'brann', 'halvard', 'quell', 'reyes', 'anouk',
         'dispatcher', 'ninety-nine', 'vesper'}
MINOR = {'amsel', 'lindgren', 'ranke', 'maartens', 'stroud', 'okafor', 'vane',
         'holt', 'old-tam', 'duarte', 'pale', 'ghost-of-terrace-nine', 'ansgar',
         'ode', 'strand', 'loos', 'ivey', 'marsh', 'dolf', 'solenne',
         'lamplighter', 'sefa', 'wren', 'bram', 'ute', 'kroll', 'aalto'}
RECRUITERS = {'vael', 'achterberg', 'quaye', 'iloh', 'vance', 'achebe-roux', 'kettle'}


@pytest.fixture(scope='module')
def cast() -> ContentTree:
    return load_content(Path(__file__).parents[2]/'src/blacksite/content')


def test_game_13_4_complete_cast_loads_without_activating_placement(cast: ContentTree) -> None:
    assert set(cast.dialogue) == FIXED | MINOR | RECRUITERS | {'machine-mind-encounter'}
    assert validate(cast) == []
    assert set(cast.bundles['s27-cast'].members['dialogue']) == set(cast.dialogue)
    assert all(not cast.active('dialogue', did) for did in cast.dialogue)
    assert not any(obj.params.get('dialogue') for zone in cast.zones.values() for obj in zone.meta.objects)
    assert not any(npc.dialogue for npc in cast.npcs.values())
    assert not any(cell.dialogue for sector in cast.sectors.values() for cell in sector.cells)


@pytest.mark.parametrize('slug', sorted(FIXED))
def test_game_13_4_every_fixed_talker_has_required_situations(cast: ContentTree, slug: str) -> None:
    talker = cast.dialogue[slug]
    for condition in ('first_meeting', 'marked', 'is_wake', 'enemy_of_me', 'season_stage finale_done'):
        assert any(condition in line.when and line.required for line in talker.lines), (slug, condition)
    assert not talker.lines[-1].when
    # No hard-coded lease day or predicted event becomes an idle fact.
    assert all('day forty-one' not in line.text.lower() and 'day nine.' not in line.text.lower()
               for line in talker.lines)


@pytest.mark.parametrize('slug', sorted(FIXED))
def test_game_13_4_late_arrival_keeps_personal_dialogue_ahead_of_global_finale(
        cast: ContentTree, slug: str) -> None:
    talker = cast.dialogue[slug]
    assert evaluate(talker, Facts(season_stage='finale_done'), Random(0)).id == 'first'
    returning = Facts(met=frozenset({slug}), season_stage='finale_done')
    assert evaluate(talker, returning, Random(0)).id == 'wake'
    discharged = Facts(legal=True, met=frozenset({slug}), season_stage='finale_done')
    assert evaluate(talker, discharged, Random(0)).id == 'finale'


def test_game_13_4_authored_references_resolve_even_while_bundle_is_dormant(cast: ContentTree) -> None:
    kinds = {'FACTION':'factions', 'CONTRACT':'contracts', 'ITEM':'items', 'EVENT':'events',
             'EVIDENCE':'evidence', 'SERVICE':'services'}
    offers = {'contract':'contracts', 'vendor':'vendors', 'recruit':'factions', 'travel':'zones'}
    for talker in cast.dialogue.values():
        assert not talker.faction or talker.faction in cast.factions
        for condition in [c for line in talker.lines for c in line.when] + [c for offer in talker.offers for c in offer.when]:
            name, *args = condition.split()
            for kind, arg in zip(DIALOGUE_CONDITIONS[name], args, strict=True):
                if kind in kinds:
                    assert arg in getattr(cast, kinds[kind]), (talker.id, condition)
        for offer in talker.offers:
            assert offer.ref in (cast.services | cast.vendors if offer.kind == 'service'
                                 else getattr(cast, offers[offer.kind])), (talker.id, offer)


def test_game_13_4_source_reactions_require_each_viewers_actual_record(cast: ContentTree) -> None:
    records = set(cast.bundles['s19-season-one'].members['evidence'])
    covered = set()
    for talker in cast.dialogue.values():
        for line in talker.lines:
            if not line.id.startswith('record-'):
                continue
            condition, = line.when
            name, eid = condition.split()
            assert name == 'has_evidence' and eid in records and line.required
            covered.add(eid)
            for stage in ('open', 'finale_done'):
                facts = Facts(legal=True, met=frozenset({talker.id}), evidence=frozenset({eid}), season_stage=stage)
                assert evaluate(talker, facts, Random(0)) is line
            # A second caller's empty journal cannot see this historical line.
            assert not evaluate(talker, Facts(legal=True, met=frozenset({talker.id})), Random(0)).id.startswith('record-')
    assert covered == records


def test_game_13_4_terminal_and_encounter_records_keep_distinct_delivery(cast: ContentTree) -> None:
    assert {did for did, talker in cast.dialogue.items() if talker.terminal} == {'dispatcher', 'ninety-nine'}
    assert all(line.text.endswith('//99') for line in cast.dialogue['ninety-nine'].lines)
    encounter = cast.dialogue['machine-mind-encounter']
    assert encounter.machine_mind and not encounter.offers and not encounter.barks
    assert {line.tag for line in encounter.lines if line.required and 'season_stage finale_done' in line.when} == {'CUST', 'TEN'}
    assert not any(line.tag for line in cast.dialogue['wren'].lines)


def test_game_13_4_neutral_balance_keeps_both_required_encounter_registers(cast: ContentTree) -> None:
    bank = cast.dialogue['machine-mind-encounter']
    for condition, facts in (
            ('first_meeting', Facts(balance=0)),
            ('season_stage finale_done', Facts(balance=0, met=frozenset({bank.id}), season_stage='finale_done'))):
        assert {line.tag for line in bank.lines if line.required and condition in line.when
                and matches(line.when, bank, facts)} == {'CUST', 'TEN'}


def test_game_13_4_recruiters_offer_existing_terms_without_joining(cast: ContentTree) -> None:
    factions = set()
    for slug in RECRUITERS | {'vantongeren'}:
        talker = cast.dialogue[slug]
        action, = [offer for offer in eligible_offers(talker, Facts()) if offer.kind == 'recruit']
        assert action.hotkey == 'j' and action.ref == talker.faction
        assert not [offer for offer in eligible_offers(talker, Facts(faction=talker.faction)) if offer.kind == 'recruit']
        factions.add(action.ref)
    assert factions == set(cast.factions)


def test_game_13_4_ambient_and_graffiti_are_authored_without_emission(cast: ContentTree) -> None:
    asset = cast.text['text-tin-halo-ambient']
    lines = re.findall(r'"(.*?)"', asset.body, re.S)
    assert len(lines) == 10
    assert all(len(' '.join(line.split())) <= 200 for line in lines)
    for asset in ('text-tin-halo-ambient', 'text-graffiti-set-1'):
        assert not cast.active('text', asset)
