"""Render one demo frame as text and PNG: zone, x, y, width, height, tier.

python scripts/demo_sodium/frame.py sodium-row 2 12 132 50 truecolor [all]
'all' marks every tile seen, to review the whole layout at once.
"""
import sys, tempfile
from pathlib import Path

ROOT = Path.cwd()
sys.path[:0] = [str(ROOT/'src'), str(ROOT), str(ROOT/'scripts/presentation_mockups/website')]

from blacksite.content.loader import load_content
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from blacksite.server.views import zone_view
from tests.character_helpers import place
from tests.fake_terminal import FakeTerminal
from tests.presentation.mechanics import character_game
import screenshot

zone, x, y, W, H, tier = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
if 'all' in sys.argv[7:]:
    zone_view.visible_tiles = lambda actor, z, radius: {
        (i, j) for j in range(z.template.height) for i in range(z.template.width)}

content = load_content(ROOT/'src/blacksite/content')
game, client = character_game(content, W, H, isolate_npcs=False)
place(game, client, zone, (x, y))
for _ in range(60):
    game.step()
    game.commit_commerce()
display = Display(DoorInfo(Path('unused'), Path('.'), {'handle': 'Tallis', 'user_id': 1}, W, H, tier, 3600),
                  'demo', presentation=True)
now = 1.0
for _ in range(3):
    for frame in game.frames_for(client):
        for out in display.receive(frame, now):
            client.send(out)
    game.step()
    now += 0.1
display.prompt = display.key_prompt = None
display.force_full = True
display.update(10.0, now)
data, _ = display.render(now)
term = FakeTerminal(W, H)
term.write(data)
name = f"demo-{zone}-{x}-{y}-{W}x{H}-{tier}"
out = Path(tempfile.gettempdir())
(out/f"{name}.txt").write_text(term.screen_text(), encoding='utf-8')
screenshot.png(term, out/f"{name}.png")
print(term.screen_text())
print(out/f"{name}.png")
