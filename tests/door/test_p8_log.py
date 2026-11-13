"""P8: barks and ambience in the log never push a danger line out of view."""

from copy import deepcopy
from dataclasses import replace

import pytest

from karst41.content.loader import load_content
from karst41.door.model import Display
from karst41.server import ambience as amb
from karst41.server.clock import TICK_HZ
from karst41.server.npcs.templates import make_actor
from tests.character_helpers import create, place
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer
from tests.presentation.snapshots import assert_golden

DANGER = "A shot cracks off the wall beside you."


def flowing(repo_root, info, width, height, tier, presentation):
    """A real Row: a regular's bark, a Row ambience line, then danger."""
    content = deepcopy(load_content(repo_root/"src/karst41/content"))
    content.zones = {k: replace(z, meta=replace(z.meta, spawners=())) for k, z in content.zones.items()}
    game = HeadlessServer(content, character_state={})
    client = game.connect({"user_id": 1, "handle": "Ear界", "node_name": "P8"}, width=width, height=height)
    create(game, client, card="none")
    place(game, client, "sodium-row", (25, 6))
    actor = make_actor(content.npcs["npc-sodium-regular"], "r1", {"spawner": "r1", "home": (27, 6), "pause": 1 << 40})
    game.core.world.enter(actor, "sodium-row", (27, 6))
    display = Display(replace(info, width=width, height=height, color_depth=tier), presentation=presentation)
    kinds, second = [], 0

    def feed():
        for frame in game.frames_for(client):
            display.receive(frame, second)
            if frame.type == "prompt":
                display.key("enter", second)
            if frame.type == "log":
                kinds.extend((second, line["kind"]) for line in frame.data["lines"])
    feed()
    display.toast = None
    while not any(kind == "ambient" for _, kind in kinds):
        second += 1
        game.step(TICK_HZ)
        feed()
    client.session.emit(DANGER, kind="danger", channel="zone", role="log_danger",
                        at=game.clock.now_utc().isoformat())
    danger_at = second
    feed()
    for _ in range(amb.DANGER_HOLD_SECONDS - 1):
        second += 1
        game.step(TICK_HZ)
        feed()
    display.toast = None
    display.update(second, second)
    terminal = FakeTerminal(width, height)
    terminal.write(display.render(second)[0])
    return terminal, kinds, danger_at


@pytest.mark.parametrize("width,height", [(80, 24), (132, 50)])
@pytest.mark.parametrize("tier", ["16", "256", "truecolor"])
@pytest.mark.parametrize("presentation", [False, True])
def test_p8_bark_and_ambience_with_danger_in_view(repo_root, info, request, width, height, tier, presentation):
    terminal, kinds, danger_at = flowing(repo_root, info, width, height, tier, presentation)
    text = terminal.screen_text()
    assert DANGER in text and (height < 50 or "A tram goes over" in text)  # 80x24's log is two rows.
    assert any(kind == "speech" for _, kind in kinds) and any(kind == "ambient" for _, kind in kinds)
    # Nothing ambient reaches the caller inside the ten-second hold.
    assert not [s for s, kind in kinds if s > danger_at and kind in ("ambient", "speech")]
    assert_golden(repo_root/"tests/presentation/golden/p8-voice",
                  f"p8_voice_{'present' if presentation else 'legacy'}_{width}x{height}_{tier}", terminal, tier,
                  trim=True, update=request.config.getoption("--update-goldens"))
