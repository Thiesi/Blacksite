"""B3's two merged NPC updates do not unfreeze authored or NPC data."""

from pathlib import Path
import subprocess

import pytest

from scripts import presentation_p6b_changes as b3


@pytest.fixture
def pinned_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    def git(*args: str) -> str:
        return subprocess.check_output(
            ['git', '-c', 'commit.gpgsign=false', '-C', str(tmp_path), *args], text=True).strip()

    git('init', '-q')
    git('config', 'user.name', 'Blacksite test')
    git('config', 'user.email', 'test@example.invalid')
    git('config', 'core.autocrlf', 'false')
    data = tmp_path/'src/blacksite/content'
    (data/'looks').mkdir(parents=True)
    (data/'npcs.json').write_text('{"faction":"sable"}\n', encoding='utf-8')
    (data/'looks/sodium-row.json').write_text('{"theme":"authored"}\n', encoding='utf-8')
    git('add', '.')
    git('commit', '-qm', 'Pin authored content')
    author = git('rev-parse', 'HEAD')
    (data/'dialogue').mkdir()
    (data/'npcs.json').write_text('{"faction":null}\n', encoding='utf-8')
    (data/'dialogue/row-street-regular.json').write_text('{"text":"approved"}\n', encoding='utf-8')
    git('add', '.')
    git('commit', '-qm', 'Merge approved NPC data')
    monkeypatch.setattr(b3, 'ROOT', tmp_path)
    monkeypatch.setattr(b3, 'PREREQUISITE', git('rev-parse', 'HEAD'))
    return data, author


def test_b3_accepts_the_exact_merged_npc_updates(pinned_content: tuple[Path, str]) -> None:
    _, author = pinned_content
    assert {row['path'] for row in b3.check_content(author)} == set(b3.PREREQUISITE_DATA)


@pytest.mark.parametrize('path', ['npcs.json', 'dialogue/row-street-regular.json',
                                 'looks/sodium-row.json'])
def test_b3_rejects_later_npc_dialogue_and_look_edits(
        pinned_content: tuple[Path, str], path: str) -> None:
    data, author = pinned_content
    (data/path).write_text('{"unapproved":true}\n', encoding='utf-8')
    with pytest.raises(ValueError, match='modified|differs from the merged prerequisite'):
        b3.check_content(author)
