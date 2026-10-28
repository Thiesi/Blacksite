"""V0 (issue #68): the Tin Halo, live, against the visual target.

Run from the repository root:

    python scripts/presentation_mockups/v0_tin_halo.py [out_dir]

A headless server with the trial on and the candidate geometry loads the
Tin Halo with its look (lights and dressing), puts a Wake under the halo
of cans and lets the regulars arrive. The real door then draws the scene
in three tiers, each from the same game state:

- modern glyphs (sextants) in truecolor at 132x50,
- CP437 (half-blocks) in 256 colours at 132x50,
- CP437 in 16 colours at 80x25.

Also the full-screen look (auto's LOOK) in the modern tier, and the cost
of each: milliseconds to draw (first frame in a place, then a frame with
the place cached), bytes for a full screen, and bytes for one step. The
numbers are printed and written to `v0-costs.json`.
"""

import json
import os
import sys
import time
from pathlib import Path

os.environ["BLACKSITE_PRESENTATION_TRIAL"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(Path(__file__).parent)]

from build import Caller, emit  # noqa: E402
from tests.character_helpers import place  # noqa: E402
from tests.fake_terminal import FakeTerminal  # noqa: E402

from blacksite.door.present import lit  # noqa: E402

CANDIDATE = ROOT / "docs/design/proposals/68-presentation/candidates/sodium-row"
OUT = ROOT / "docs/design/proposals/68-presentation/target/v0"
TIERS = [("modern", 132, 50, "truecolor"), ("cp437", 132, 50, "256"), ("cp437", 80, 25, "16")]
SHOTS = {"room": ((4, 10), "right"),  # down the room: booths left, the bar right, the back far off
         "bar": ((10, 10), "down")}    # "You see Vesper at the end of the bar"


SPENT = {"lit": 0.0}
_lit_render = lit.render


def _timed(*args, **kwargs):  # type: ignore[no-untyped-def]
    started = time.perf_counter()
    try:
        return _lit_render(*args, **kwargs)
    finally:
        SPENT["lit"] += time.perf_counter() - started


lit.render = _timed


def render(caller: Caller, full: bool) -> tuple[bytes, float, float]:
    display = caller.display
    display.toast = None
    display.hit_flash = False
    display.card_until = 0.0
    if full:
        display.force_full = True
    display.dirty = True
    display.last_render = -1.0
    SPENT["lit"] = 0.0
    started = time.perf_counter()
    out, ack = display.render(caller.t + 1)
    took = (time.perf_counter() - started) * 1000
    if ack:
        caller.client.send(ack)
    return out, took, SPENT["lit"] * 1000


def big(out: Path, name: str, data: bytes, width: int, height: int) -> None:
    """The .ans and .txt, and a PNG at the target's cell size (12x24)."""
    emit(out, name, data, width, height)
    try:
        import screenshot
    except ImportError:
        return
    term = FakeTerminal(width, height)
    term.write(data)
    screenshot.png(term, out / f"{name}.png", (12, 24))


def capture(shot: str, glyphs: str, width: int, height: int, tier: str, out: Path) -> dict:
    spot, heading = SHOTS[shot]
    caller = Caller(width, height, tier, local=CANDIDATE)
    place(caller.game, caller.client, "sodium-tin-halo", spot)
    caller.pump(60)  # the regulars and the bouncer arrive
    display = caller.display
    display.present, display.view_mode, display.glyphs = True, "scene", glyphs
    display.heading = heading
    caller.pump(2)
    lit.PAINTER.clear()
    lit._SCENES.clear()
    name = f"tin-halo-v0-{shot}-{glyphs}-{width}x{height}-{tier}"
    first, cold, cold_lit = render(caller, True)
    _, warm, warm_lit = render(caller, True)
    big(out, name, first, width, height)
    caller.key("right", 4)  # one step along the room
    display.heading = heading
    step, step_ms, step_lit = render(caller, False)
    caller.key("left", 4)
    costs = {"frame": name, "first_ms": round(cold), "first_picture_ms": round(cold_lit), "cached_ms": round(warm),
             "cached_picture_ms": round(warm_lit), "full_bytes": len(first), "step_bytes": len(step),
             "step_ms": round(step_ms), "step_picture_ms": round(step_lit)}
    if glyphs == "modern":
        display.view_mode = "street"
        lit.PAINTER.clear()
        look, look_ms, _ = render(caller, True)
        big(out, f"tin-halo-v0-{shot}-look-{width}x{height}-{tier}", look, width, height)
        costs.update(look_first_ms=round(look_ms), look_bytes=len(look))
    return costs


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(args[0]) if args else OUT
    out.mkdir(parents=True, exist_ok=True)
    tiers = TIERS[:1] if "--quick" in sys.argv else TIERS
    costs = [capture(shot, *tier, out) for shot in SHOTS for tier in tiers]
    for row in costs:
        print(row)
    (out / "v0-costs.json").write_text(json.dumps(costs, indent=2) + "\n", encoding="utf-8")
    if len(tiers) == len(TIERS):
        sheet(out)


def sheet(out: Path) -> None:
    """The target above the live frames, glimpses only, for comparing."""
    try:
        import screenshot
        from PIL import Image, ImageDraw
    except ImportError:
        return
    def glimpse(name: str, cols: int, rows: int):  # type: ignore[no-untyped-def]
        return Image.open(out / f"{name}.png").crop((0, 0, cols * 12, rows * 24))
    rows = [("Target, hand-composed", Image.open(OUT.parent / "tin-halo-glimpse.png")),
            ("V0 live, down the room: modern glyphs, truecolor, 132x50",
             glimpse("tin-halo-v0-room-modern-132x50-truecolor", 108, 21)),
            ("V0 live, facing the bar: modern glyphs, truecolor, 132x50",
             glimpse("tin-halo-v0-bar-modern-132x50-truecolor", 108, 21)),
            ("V0 live, down the room: CP437 half-blocks, 256 colours, 132x50",
             glimpse("tin-halo-v0-room-cp437-132x50-256", 108, 21)),
            ("V0 live, down the room: CP437, 16 colours, 80x25", glimpse("tin-halo-v0-room-cp437-80x25-16", 80, 10))]
    font = screenshot._font(screenshot.FONTS, 20)
    width = max(part.size[0] for _, part in rows)
    image = Image.new("RGB", (width, sum(part.size[1] + 36 for _, part in rows)), (12, 12, 14))
    draw, y = ImageDraw.Draw(image), 0
    for label, part in rows:
        draw.text((8, y + 6), label, font=font, fill=(220, 220, 220))
        image.paste(part, (0, y + 36))
        y += part.size[1] + 36
    image.save(out / "tin-halo-v0-comparison.png")


if __name__ == "__main__":
    main()
