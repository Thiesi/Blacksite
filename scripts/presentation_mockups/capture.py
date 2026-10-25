"""Capture proposal 68 frames from the real door renderer and real game state.

Run from the repository root:

    python scripts/presentation_mockups/capture.py [out_dir]

A headless server (the production simulation through the test harness)
creates a Wake, fires on a Warden in the Wake Hall (heat), then visits Clinic Row, the
Vatside Lattice, Meridian Plaza and Sodium Row, the last with both the
shipped map and the geometry candidate. Every scene is rendered twice from
the same view by the same `Display`: `-before` with the shipped renderer,
then with `door/present` (F7). Charted geography and ambient lines are on
(BLACKSITE_PRESENTATION_TRIAL=1), as in the playtest build.

Outputs per frame: .ans (the bytes a terminal receives), .txt and, with
Pillow, .png (the .ans replayed through tests/fake_terminal.py).
"""

import os
import sys
from pathlib import Path

os.environ["BLACKSITE_PRESENTATION_TRIAL"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(Path(__file__).parent)]

from build import Caller, emit  # noqa: E402
from tests.character_helpers import place  # noqa: E402

CANDIDATE = ROOT / "docs/design/proposals/68-presentation/candidates/sodium-row"


def frame(caller: Caller, present: bool, card: bool = False) -> bytes:
    display = caller.display
    display.present = present
    display.toast = None
    display.hit_flash = False
    display.card_until = 1e9 if card else 0.0
    display.force_full = display.dirty = True
    display.last_render = -1.0
    out, ack = display.render(caller.t + 1)
    if ack:
        caller.client.send(ack)
    return out


def both(caller: Caller, out: Path, name: str, before: bool = True) -> None:
    w, h, tier = caller.info.width, caller.info.height, caller.info.color_depth
    suffix = f"{w}x{h}-{tier}"
    emit(out, f"{name}-{suffix}", frame(caller, True), w, h)
    if before and tier == "256":
        emit(out, f"{name}-{suffix}-before", frame(caller, False), w, h)


def tour(out: Path, width: int, height: int, tier: str) -> None:
    caller = Caller(width, height, tier)
    caller.pump(20)
    for _ in range(3):  # Tab picks the nearest body; firing on a Warden earns heat
        caller.key("tab", 4)
        caller.key("f", 8)
    caller.pump(6)
    both(caller, out, "wake-hall-heat")
    place(caller.game, caller.client, "vatside-clinics", (46, 3))
    caller.pump(30)
    both(caller, out, "clinic-row")
    caller.walk((17, 8))
    caller.key("J", 10)
    caller.pump(30)
    for key in ("right", "right"):
        caller.key(key, 15)
    both(caller, out, "lattice-vatside")
    caller.key("J", 10)
    caller.pump(20)
    place(caller.game, caller.client, "core-plaza", (57, 6))
    caller.pump(20)
    w, h = caller.info.width, caller.info.height
    emit(out, f"meridian-plaza-card-{w}x{h}-{tier}", frame(caller, True, card=True), w, h)
    caller.key("left", 4)
    caller.pump(10)
    both(caller, out, "meridian-plaza")
    place(caller.game, caller.client, "sodium-row", (34, 12))
    caller.pump(30)
    both(caller, out, "sodium-row-shipped-map", before=False)


def candidate(out: Path, width: int, height: int, tier: str) -> None:
    caller = Caller(width, height, tier, local=CANDIDATE)
    place(caller.game, caller.client, "sodium-row", (34, 12))
    caller.pump(30)
    w, h = caller.info.width, caller.info.height
    emit(out, f"sodium-row-card-{w}x{h}-{tier}", frame(caller, True, card=True), w, h)
    caller.key("left", 4)
    caller.pump(10)
    both(caller, out, "sodium-row")
    caller.walk((47, 12), (47, 25))  # through an alley mouth into the alley behind
    caller.pump(10)
    both(caller, out, "sodium-alley")


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/design/proposals/68-presentation/frames"
    out.mkdir(parents=True, exist_ok=True)
    for width, height, tier in ((80, 24, "256"), (132, 50, "256"), (80, 24, "16"), (80, 24, "truecolor")):
        tour(out, width, height, tier)
        candidate(out, width, height, tier)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
