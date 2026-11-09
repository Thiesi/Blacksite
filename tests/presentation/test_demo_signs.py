"""Demo only (demo/sodium-row-evening): public signs read from a distance."""

from pathlib import Path

from scripts.demo_sodium.content import load_demo_content as load_content
from karst41.server.views import looks

ROOT = Path(__file__).resolve().parents[2]


def _upstairs(result):
    return [sign for sign in result['signs'] if 'UPSTAIRS' in sign['text']]


def test_unseen_public_sign_is_sent_only_with_the_toggle(monkeypatch):
    content = load_content(ROOT/'src/karst41/content')
    zone = content.zones['sodium-row']
    arrival = {(2, 12)}  # nothing of the bar fronts is known yet
    monkeypatch.setattr(looks, 'DEMO_SIGNS', False)
    assert not _upstairs(looks.masked(content, zone, arrival, arrival))
    monkeypatch.setattr(looks, 'DEMO_SIGNS', True)
    signs = _upstairs(looks.masked(content, zone, arrival, arrival))
    assert signs and tuple(signs[0]['at']) == (5, 8)


def test_toggle_sends_only_signs_on_public_wall_faces(monkeypatch):
    content = load_content(ROOT/'src/karst41/content')
    zone = content.zones['sodium-row']
    monkeypatch.setattr(looks, 'DEMO_SIGNS', True)
    result = looks.masked(content, zone, {(2, 12)}, {(2, 12)})
    public = {t for region in zone.meta.public for t in region.tiles()}
    for sign in result['signs']:
        for i in range(len(sign['text'])):
            x, y = sign['at'][0] + i, sign['at'][1]
            assert any((x + dx, y + dy) in public for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))
    # Regions, marks and names stay masked to what the caller knows.
    assert not result['marks'] and not result['names']
