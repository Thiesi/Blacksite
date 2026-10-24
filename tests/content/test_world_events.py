"""Game 12: shipped schedules, bounded sources and explicit activation."""

from pathlib import Path

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.server.event_effects import compatible
from blacksite.server.rules.events import SCHEDULES


def test_game_12_all_five_authored_events_match_canon_and_activation_boundaries(repo_root: Path) -> None:
    tree = load_content(repo_root/'src/blacksite/content')
    assert not validate(tree)
    assert set(tree.events) == set(SCHEDULES)
    for eid, expected in SCHEDULES.items():
        event = tree.events[eid]
        assert (event.duration_seconds,event.cooldown_seconds,event.weight) == expected
        assert tree.active('events',eid)
        for asset in (event.announce.start,event.announce.mid,event.announce.end):
            text = tree.text[asset].body.format(name=event.name,where='the site',plan='p',remaining=10,route='the road',time='now')
            assert '{' not in text and '}' not in text
    for variant in tree.events['choir-surge'].variants:
        for effect in variant.effects:
            if effect.type == 'ice_variant':
                assert compatible(tree.ice[effect.params['from']],tree.ice[effect.params['to']])
                assert effect.warning_seconds >= 5


def test_game_12_authored_source_caps_and_public_convoy_terms_match_canon(repo_root: Path) -> None:
    tree = load_content(repo_root/'src/blacksite/content')
    for effect in tree.events['ring-fall'].effects:
        if effect.type == 'salvage':
            assert (effect.params['count'],effect.params['cap']) == (10,40)
        elif effect.type == 'hazard':
            assert (effect.params['radius'],effect.params['seconds'],effect.warning_seconds) == (1,5,5)
    for effect in tree.events['exhale'].effects:
        if effect.type == 'spawn_multiplier':
            assert (effect.params['multiplier'],effect.params['cap']) == (3,6)
        elif effect.type == 'key_drop':
            assert (effect.params['item'],effect.params['count']) == ('key_undercity',1)
    assert tree.items['key_undercity'].class_ == 'key' and tree.items['key_undercity'].no_vendor_sale
    convoy = tree.events['convoy']
    assert tree.routes[convoy.route].speed == 2
    for effect in convoy.effects:
        if effect.type == 'event_contract':
            job = tree.contracts[effect.params['contract']]
            assert job.event_only and not job.crew_scaling
            assert (job.reward.chits,job.reward.xp) == ((200,200),100)
