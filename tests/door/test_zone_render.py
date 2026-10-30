"""UI 2/6: replay actual zone frames at both supported acceptance sizes."""

from dataclasses import replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from blacksite.server.protocol import Frame
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer


@pytest.mark.parametrize("width,height", [(80, 24), (132, 50)])
@pytest.mark.parametrize("tier", ["16", "256", "truecolor"])
def test_golden_zone_and_wide_name(info: DoorInfo, repo_root: Path, width: int, height: int, tier: str, golden) -> None:
    content = load_content(repo_root / "src/blacksite/content")
    game = HeadlessServer(content, "vatside-wake-hall")
    client = game.connect(width=width, height=height)
    info = replace(info, width=width, height=height, color_depth=tier)
    model, terminal = Display(info), FakeTerminal(width, height)
    game.step()
    for frame in game.frames_for(client):
        model.receive(frame, 0)
    # Settle transient UI. S25b's arrival paragraph remains in the log.
    model.update(9, 9)
    terminal.write(model.render(9)[0])
    text = terminal.screen_text()
    assert "Wake Hall" in text and "POCKET" in text and "Wide界" in text
    assert "HP " in text and "STA " in text and "@" in text
    golden(f'wake_hall_{width}x{height}', terminal, tier, trim=True)
    # A local help overlay and resuming the zone still use the same buffer.
    model.key("?", 10)
    terminal.write(model.render(10)[0])
    assert "HELP" in terminal.screen_text()
    model.key("escape", 11)
    terminal.write(model.render(11)[0])
    assert "Wake Hall" in terminal.screen_text()
