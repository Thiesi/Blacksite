"""Capture the paradigm prototypes (street view, scenes, auto) from live state.

Run from the repository root:

    python scripts/presentation_mockups/paradigms.py [out_dir]

The same headless walk as capture.py, drawn by the real `Display` in each
view mode. In the scene captures the caller chooses a way and the server
walks the body there; frames show the walk in progress and on arrival.
The auto tour lets the door choose every view itself (`auto-*`).
"""

import os
import sys
from pathlib import Path

os.environ["BLACKSITE_PRESENTATION_TRIAL"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(Path(__file__).parent)]

from build import Caller, emit  # noqa: E402
from capture import CANDIDATE  # noqa: E402
from tests.character_helpers import place  # noqa: E402


def shot(caller: Caller, out: Path, name: str, mode: str) -> None:
    display = caller.display
    display.present, display.view_mode = True, mode
    caller.client.send(display.shape_frame())  # the deep camera for eye-level views
    caller.pump(2)
    display.toast, display.hit_flash, display.card_until = None, False, 0.0
    display.force_full = display.dirty = True
    display.last_render = -1.0
    data, ack = display.render(caller.t + 1)
    if ack:
        caller.client.send(ack)
    w, h, tier = caller.info.width, caller.info.height, caller.info.color_depth
    emit(out, f"{name}-{mode}-{w}x{h}-{tier}", data, w, h)


def choose(caller: Caller, name: str) -> bool:
    """Scene mode: move the cursor to a way by name and press Enter."""
    from blacksite.door.present import scene
    caller.display.present, caller.display.view_mode = True, "scene"
    options = scene.ways(caller.display.body)
    index = next((i for i, w in enumerate(options) if w["name"] == name), None)
    if index is None:
        return False
    caller.display.scene_cursor = index
    caller.key("enter", 2)
    return True


def tour(out: Path, width: int, height: int, tier: str) -> None:
    caller = Caller(width, height, tier, local=CANDIDATE)
    place(caller.game, caller.client, "core-plaza", (45, 26))
    caller.pump(20)
    caller.display.heading = "up"
    shot(caller, out, "plaza-fountain", "street")
    shot(caller, out, "plaza-fountain", "scene")
    place(caller.game, caller.client, "sodium-row", (31, 12))
    caller.pump(20)
    caller.display.heading = "up"
    shot(caller, out, "sodium-stage", "street")
    caller.display.heading = "right"
    shot(caller, out, "sodium-street-east", "street")
    shot(caller, out, "sodium-street", "scene")
    if choose(caller, "The alley behind"):
        caller.pump(12)
        shot(caller, out, "sodium-walking", "scene")
        caller.pump(400)
        shot(caller, out, "sodium-alley", "scene")
        caller.display.heading = "left"
        shot(caller, out, "sodium-alley-west", "street")
    place(caller.game, caller.client, "vatside-clinics", (13, 13))
    caller.pump(20)
    caller.display.heading = "up"
    shot(caller, out, "clinic-door", "street")
    shot(caller, out, "clinic-door", "scene")


def frame_now(caller: Caller, out: Path, name: str) -> None:
    """Render exactly what the auto view chooses at this moment."""
    display = caller.display
    display.toast, display.hit_flash = None, False
    display.force_full = display.dirty = True
    display.last_render = -1.0
    data, ack = display.render(caller.t)
    if ack:
        caller.client.send(ack)
    w, h, tier = caller.info.width, caller.info.height, caller.info.color_depth
    emit(out, f"auto-{name}-{w}x{h}-{tier}", data, w, h)


def auto_tour(out: Path, width: int, height: int, tier: str) -> None:
    """One journey under the auto view: the door picks every frame's view."""
    from blacksite.door.present import scene
    caller = Caller(width, height, tier, local=CANDIDATE)
    display = caller.display
    display.present, display.view_mode = True, "auto"
    display.card_zone = None
    place(caller.game, caller.client, "core-plaza", (45, 27))
    caller.client.send(display.shape_frame())
    caller.pump(3)
    frame_now(caller, out, "1-plaza-arrival")          # a look on arrival
    caller.pump(45)
    frame_now(caller, out, "2-plaza-scene")            # safe ground: a scene
    options = scene.ways(display.body)
    display.scene_cursor = next(i for i, w in enumerate(options) if w["name"] == "The south promenade")
    caller.key("enter", 2)
    caller.pump(10)
    frame_now(caller, out, "3-walking")
    for _ in range(400):  # until the walk ends and the door looks
        caller.pump(1)
        if display.context.look_until > caller.t:
            break
    frame_now(caller, out, "4-arrived")                # a look where the walk ends
    display.context.look_until = 0.0
    place(caller.game, caller.client, "sodium-row", (31, 12))
    caller.pump(3)
    frame_now(caller, out, "5-sodium-arrival")         # a look into Sodium Row
    caller.pump(45)
    frame_now(caller, out, "6-sodium-map")             # contested: the map
    caller.key("tab", 4)
    caller.pump(2)
    frame_now(caller, out, "7-tactical")               # a target: tactical


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/design/proposals/68-presentation/paradigms"
    out.mkdir(parents=True, exist_ok=True)
    for width, height, tier in ((80, 24, "256"), (132, 50, "256"), (80, 24, "16"), (132, 50, "truecolor")):
        tour(out, width, height, tier)
        auto_tour(out, width, height, tier)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
