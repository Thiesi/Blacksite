"""Sodium Row at night, 132x50 truecolor: one real engine frame.

Run from the repository root, with P6b's place content (#126) present.
Writes the cell grid, with resolved colours, to the temp directory for
street_light.py to light and rasterize.

Mockup-only changes, never shipped: every tile counts as seen (so the
whole street shows), and the map origin is A7's fixed one.
"""
import json, sys, tempfile
from pathlib import Path

ROOT = Path.cwd()
HERE = Path(__file__).parent
sys.path[:0] = [str(ROOT / 'src'), str(ROOT), str(HERE)]

from blacksite.content.loader import load_content
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from blacksite.door.present import zone as zmod
from blacksite.server.views import zone_view
from tests.character_helpers import place
from tests.fake_terminal import FakeTerminal
from tests.presentation.mechanics import character_game
import screenshot

W, H = 132, 50
START = tuple(int(v) for v in (sys.argv[1:3] or (52, 17)))
TICKS = int(sys.argv[3]) if len(sys.argv) > 3 else 90


def fixed(body, layout):  # A7: a zone that fits is centred and kept still
    area, vp = layout.viewport, body['viewport']
    x, y = area.x, area.y
    if vp['w'] < area.width:
        x += (area.width - vp['w']) // 2
    if vp['h'] < area.height:
        y += (area.height - vp['h']) // 2
    return x, y


zmod.origin = fixed
zone_view.visible_tiles = lambda actor, zone, radius: {
    (x, y) for y in range(zone.template.height) for x in range(zone.template.width)}

content = load_content(ROOT / 'src/blacksite/content')
game, client = character_game(content, W, H, isolate_npcs=False)
place(game, client, 'sodium-row', START)
for _ in range(TICKS):
    game.step()
    game.commit_commerce()
display = Display(DoorInfo(Path('unused'), Path('.'), {'handle': 'Tallis', 'user_id': 1}, W, H, 'truecolor', 3600),
                  'mock', presentation=True)
now = 1.0
for _ in range(3):
    for frame in game.frames_for(client):
        for out in display.receive(frame, now):
            client.send(out)
    game.step()
    now += 0.1
display.prompt = display.key_prompt = None
for key in sys.argv[4:]:
    for out in display.key(key, now):
        client.send(out)
    game.step()
    for frame in game.frames_for(client):
        for out in display.receive(frame, now):
            client.send(out)
    now += 0.2
display.force_full = True
display.update(10.0, now)
data, _ = display.render(now)
term = FakeTerminal(W, H)
term.write(data)
cells = []
for y in range(H):
    row = []
    for x in range(W):
        sgr = term.styles.get((x, y), '0')
        fg, bg = screenshot.colours(sgr)
        row.append([term.grid[y][x], list(fg), list(bg), ';1;' in f';{sgr};' or sgr.startswith('1;')])
    cells.append(row)
body = display.body
meta = {'viewport': body['viewport'], 'origin': fixed(body, display.layout),
        'actors': body.get('actors', []), 'me': START}
(Path(tempfile.gettempdir()) / 'blacksite-street-frame.json').write_text(json.dumps({'cells': cells, 'meta': meta}), encoding='utf-8')
screenshot.png(term, Path(tempfile.gettempdir()) / 'blacksite-street-raw.png')
print('frame written')
