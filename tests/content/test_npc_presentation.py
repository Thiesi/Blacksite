"""Entities 1.8: an authored cover has an ordinary, validated name."""

from dataclasses import replace
from pathlib import Path

from blacksite.content.schema import Behaviour

import pytest

from blacksite.content.loader import load_content
from blacksite.content.validate import validate


@pytest.mark.parametrize('cover_name', [None, '', '   ', 'Sodium\nregular', '\x1b[31mSodium regular'])
def test_entities_1_8_presents_requires_valid_cover_name(repo_root, cover_name):
    content = load_content(repo_root/'src/blacksite/content')
    npc = content.npcs['npc-plainclothes-warden']
    content.npcs[npc.id] = replace(npc, cover_name=cover_name)
    assert any('cover_name' in problem.message for problem in validate(content))


def test_entities_1_8_shipped_cover_is_valid_and_reuses_civilian_name(repo_root):
    content = load_content(repo_root/'src/blacksite/content')
    npc = content.npcs['npc-plainclothes-warden']
    assert npc.presents == 'civilian'
    assert npc.cover_name == content.npcs['npc-sodium-regular'].name
    assert not validate(content)


def test_entities_1_8_legacy_npc_does_not_need_a_cover_name(repo_root):
    content = load_content(repo_root/'src/blacksite/content')
    npc = content.npcs['npc-plainclothes-warden']
    content.npcs[npc.id] = replace(npc, presents=None, cover_name=None)
    assert not validate(content)


@pytest.mark.parametrize('channel', ['name', 'class', 'colour_role', 'behaviour_kinds',
                                    'anchored', 'interactions', 'dialogue', 'loot'])
def test_arch_5_5_4_cover_rejects_each_presented_channel(repo_root: Path, channel: str) -> None:
    content = load_content(repo_root/'src/blacksite/content')
    warden = content.npcs['npc-plainclothes-warden']
    peer = content.npcs['npc-sodium-regular']
    if channel == 'name':
        content.npcs[warden.id] = replace(warden, cover_name='A different regular')
    elif channel == 'class':
        content.npcs[warden.id] = replace(warden, presents='hostile')
    elif channel == 'colour_role':
        content.npcs[peer.id] = replace(peer, faction='sable')
    elif channel == 'behaviour_kinds':
        content.npcs[peer.id] = replace(peer, behaviours=())
    elif channel == 'anchored':
        content.npcs[peer.id] = replace(peer, behaviours=(Behaviour('wander', {'anchor': True}),))
    elif channel == 'interactions':
        content.npcs[peer.id] = replace(peer, vendor=next(iter(content.vendors)))
    elif channel == 'loot':
        content.npcs[peer.id] = replace(peer, loot=())
    else:
        duplicate = replace(content.dialogue[peer.dialogue], id='test-cover-dialogue')
        content.dialogue[duplicate.id] = duplicate
        content.npcs[peer.id] = replace(peer, dialogue=duplicate.id)
    problems = [p.message for p in validate(content) if 'uncovered same-zone match' in p.message]
    assert any(channel in message for message in problems), problems


@pytest.mark.parametrize('kind', ['different_zone', 'zero_count', 'covered_peer'])
def test_arch_5_5_4_cover_needs_a_real_uncovered_local_crowd(repo_root: Path, kind: str) -> None:
    content = load_content(repo_root/'src/blacksite/content')
    zone = content.zones['sodium-row']
    if kind == 'covered_peer':
        peer = content.npcs['npc-sodium-regular']
        content.npcs[peer.id] = replace(peer, faction='wardens', presents='civilian', cover_name=peer.name)
    else:
        spawners = tuple(replace(sp, count=0) if sp.npc == 'npc-sodium-regular' else sp
                         for sp in zone.meta.spawners)
        content.zones[zone.id] = replace(zone, meta=replace(zone.meta, spawners=spawners))
        if kind == 'different_zone':
            other = content.zones['core-plaza']
            peer = next(sp for sp in zone.meta.spawners if sp.npc == 'npc-sodium-regular')
            content.zones[other.id] = replace(other, meta=replace(other.meta,
                spawners=(*other.meta.spawners, replace(peer, id='test-remote-peer'))))
    assert any('uncovered same-zone match' in p.message for p in validate(content))


@pytest.mark.parametrize('complete_peer', [False, True])
def test_arch_5_5_4_cover_requires_one_complete_counterpart(repo_root: Path, complete_peer: bool) -> None:
    content = load_content(repo_root/'src/blacksite/content')
    peer = content.npcs['npc-sodium-regular']
    content.npcs[peer.id] = replace(peer, name='A different regular')
    partial = replace(peer, id='test-partial-peer', faction='sable')
    content.npcs[partial.id] = partial
    zone = content.zones['sodium-row']
    spawner = next(sp for sp in zone.meta.spawners if sp.npc == peer.id)
    spawners = (*zone.meta.spawners, replace(spawner, id='test-partial-peer', npc=partial.id, count=1))
    if complete_peer:
        full = replace(peer, id='test-full-peer')
        content.npcs[full.id] = full
        spawners = (*spawners, replace(spawner, id='test-full-peer', npc=full.id, count=1))
    content.zones[zone.id] = replace(zone, meta=replace(zone.meta, spawners=spawners))
    errors = [p for p in validate(content) if 'uncovered same-zone match' in p.message]
    assert bool(errors) is not complete_peer
