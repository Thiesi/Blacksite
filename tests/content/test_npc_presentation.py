"""Entities 1.8: an authored cover has an ordinary, validated name."""

from dataclasses import replace

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
