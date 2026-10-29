"""Issue 86 / terminal UI 1: edge shapes come from the glyph registry."""

from dataclasses import replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.door.doorinfo import DoorInfo
from blacksite.server.protocol import Frame
from tests.character_helpers import act, create, place
from tests.door.test_lattice_render import draw
from tests.harness import HeadlessServer


@pytest.mark.parametrize('kind', ['open', 'gated', 'hidden'])
@pytest.mark.parametrize('axis', ['h', 'v'])
def test_ui_1_lattice_uses_registry_through_server_view(info: DoorInfo, repo_root: Path,
                                                     kind: str, axis: str) -> None:
    content = load_content(repo_root/'src/blacksite/content')
    # A valid local registry override must reach the terminal, not just load.
    key = f'lattice-edge-{kind}-{axis}'
    content.glyphs.glyphs[key] = '!'
    game = HeadlessServer(content, character_state={})
    client = game.connect()
    create(game, client, card='none')
    place(game, client, 'core-plaza', (30, 5))
    act(game, client, Frame('key', {'k': 'j', 't': 0}))
    lattice = game.core.lattice
    presence = lattice.presences[client.session.player_id]
    body = lattice.view(client.session, presence)
    assert body['edge_glyphs'][kind][axis == 'v'] == '!'
    # Use two disclosed cells to isolate each orientation from other edges.
    a, b = body['cells'][:2]
    body['cells'] = [{**a, 'x': 0, 'y': 0},
                     {**b, 'x': 4 if axis == 'h' else 0, 'y': 4 if axis == 'v' else 0}]
    body['edges'] = [{'a': a['id'], 'b': b['id'], 'kind': 'public' if kind == 'open' else kind}]
    display, terminal = draw(info, content, body, 132, 50, '256')
    area = display.layout.viewport
    x = area.x+3+round((4*(area.width-6)//7)/2) if axis == 'h' else area.x+3
    y = area.y+1+round((4*(area.height-3)//5)/2) if axis == 'v' else area.y+1
    assert terminal.cell(x, y) == '!'


def test_ui_1_edge_columns_use_presentation_leads_choices(repo_root: Path) -> None:
    tree = load_content(repo_root/'src/blacksite/content')
    assert validate(tree) == []
    assert tree.glyphs.glyphs['lattice-edge-hidden-v'] == ':'
    assert tree.glyphs.glyphs['lattice-edge-hidden-h'] == '\u00b7'
    assert tree.glyphs.modern['lattice-edge-hidden-v'] == '\u2506'
    assert tree.glyphs.modern['lattice-edge-hidden-h'] == '\u2504'


@pytest.mark.parametrize('modern,fragment', [
    ({'missing': '\u2506'}, 'no CP437 fallback'),
    ({'lattice-edge-hidden-v': '\u754c'}, 'one printable cell'),
    ({'lattice-edge-hidden-v': '\x1b'}, 'one printable cell'),
])
def test_ui_1_modern_edges_require_safe_width_and_fallback(repo_root: Path,
                                                        modern: dict[str, str], fragment: str) -> None:
    tree = load_content(repo_root/'src/blacksite/content')
    tree.glyphs = replace(tree.glyphs, modern=modern)
    assert any(fragment in problem.message for problem in validate(tree))


def test_ui_1_missing_edge_fails_validation_before_a_caller_renders(repo_root: Path) -> None:
    tree = load_content(repo_root/'src/blacksite/content')
    del tree.glyphs.glyphs['lattice-edge-hidden-v']
    assert any('required Lattice edge glyph' in problem.message for problem in validate(tree))
