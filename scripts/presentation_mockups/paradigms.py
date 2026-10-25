"""Capture the two paradigm prototypes (street view, scenes) from live state.

Run from the repository root:

    python scripts/presentation_mockups/paradigms.py [out_dir]

The same headless walk as capture.py, drawn by the real `Display` in each
view mode. In the scene captures the caller chooses a way and the server
walks the body there; frames show the walk in progress and on arrival.
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


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/design/proposals/68-presentation/paradigms"
    out.mkdir(parents=True, exist_ok=True)
    for width, height, tier in ((80, 24, "256"), (132, 50, "256"), (80, 24, "16"), (132, 50, "truecolor")):
        tour(out, width, height, tier)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
