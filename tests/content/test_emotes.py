"""Data-owned emotes from game design §11, checked in both content trees."""

from dataclasses import replace

from blacksite.content.loader import load_content
from blacksite.content.validate import validate


def test_shipped_emotes_and_fixture_validate(repo_root):
    shipped=load_content(repo_root/'src/blacksite/content')
    assert len(shipped.emotes)==10
    assert validate(shipped)==[]
    assert validate(load_content(repo_root/'tests/fixtures/world'))==[]
    spec=shipped.emotes['wave']
    shipped.emotes['wave']=replace(spec,targeted='{target:1000000000}')
    assert any('emote form' in str(p) for p in validate(shipped))
