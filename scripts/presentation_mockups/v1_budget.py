"""V1 (issue #68): the lit picture against the budgets of plan section 13.5.

Run from the repository root:

    python scripts/presentation_mockups/v1_budget.py [out_dir] [--quick] [--frames]

A headless server with the trial on loads the candidate Tin Halo, and the
real door walks a fixed route through it, in each tier at 132x50 and
80x24, in the street view (your eyes) and the scene view (a fixed camera
per place). It reports, per case:

1. Step picture time: the lit renderer's share of a step, p95 and max, on
   a cold cache (first visit) and a warm one (the same route again).
2. Input latency while a picture is painted in the background: how late
   the door's loop wakes for a key, p95 and max, beside the same paint done
   on the loop (V0's way).
3. Bytes per step while moving, and for the sharp frame once you stop,
   against the 16 KiB per-delta ceiling.
4. Peak cache memory per caller, against the LRU cap.
5. The walk in real time: steps every 200 ms with the background painter,
   how many of them showed a picture of where you stood, and how far the
   picture lagged.

Numbers go to stdout, `v1-budget.json` and `v1-budget.md` in the output
directory. `--frames` also writes PNGs of a step while walking and of the
sharp frame after stopping. Pass `--quick` for one tier at 132x50.
"""

import asyncio
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path

os.environ["BLACKSITE_PRESENTATION_TRIAL"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(Path(__file__).parent)]

from build import Caller  # noqa: E402
from tests.character_helpers import place  # noqa: E402
from tests.fake_terminal import FakeTerminal  # noqa: E402

from blacksite.door.present import lit  # noqa: E402
from blacksite.door.present import screen as present_screen  # noqa: E402

CANDIDATE = ROOT / "docs/design/proposals/68-presentation/candidates/sodium-row"
OUT = ROOT / "docs/design/proposals/68-presentation/target/v1"
TIERS = [("modern", "truecolor"), ("cp437", "256"), ("cp437", "16")]
SIZES = [(132, 50), (80, 24)]
START = (4, 10)
STREET = ["up"] * 8 + ["right"] + ["up"] * 3 + ["left", "left"] + ["up"] * 4 + ["right"] + ["up"] * 6
"""Your eyes: up steps ahead, left and right turn."""
SCENE = [(14, 12), (14, 13), (30, 13), (34, 13), (31, 18), (20, 9), (20, 4), (4, 5)]
"""Through the places: the room, the bar, the quiet end, the back room, the
booths, under the halo."""
CEILING = 16 * 1024
STEP = 0.2


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


SPENT = [0.0]
_render = lit.render


def _timed(*args, **kwargs):  # type: ignore[no-untyped-def]
    started = time.perf_counter()
    try:
        return _render(*args, **kwargs)
    finally:
        SPENT[0] += time.perf_counter() - started


lit.render = _timed


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


def setup(width: int, height: int, glyphs: str, tier: str, view: str) -> tuple[Caller, Clock]:
    caller = Caller(width, height, tier, local=CANDIDATE)
    place(caller.game, caller.client, "sodium-tin-halo", START)
    caller.pump(60)  # the regulars and the bouncer arrive
    display = caller.display
    display.present, display.view_mode, display.glyphs, display.heading = True, view, glyphs, "right"
    caller.pump(2)
    clock = Clock()
    lit.CLOCK = clock
    return caller, clock


def draw(caller: Caller, clock: "Clock | RealClock", full: bool = False) -> tuple[bytes, float]:
    """One door render at the clock's time: (bytes, seconds in the lit renderer)."""
    display = caller.display
    display.toast, display.hit_flash, display.card_until = None, False, 0.0
    display.update(10.0, clock.now)
    display.dirty = True
    display.force_full = display.force_full or full
    display.last_render = -1.0
    SPENT[0] = 0.0
    out, ack = display.render(clock.now)
    if ack:
        caller.client.send(ack)
    term = TERMS.get((caller.info.width, caller.info.height))
    if term is not None:
        term.write(out)
    return out, SPENT[0]


def steps(caller: Caller, view: str) -> list[str | tuple[int, int]]:
    return list(STREET) if view == "street" else list(SCENE)


def take_step(caller: Caller, clock: Clock, move: str | tuple[int, int]) -> None:
    if isinstance(move, str):
        caller.key(move, 4)
    else:
        before = caller.display.heading
        caller.walk(move)
        caller.display.heading = before
    clock.now += STEP


def walk_route(caller: Caller, clock: Clock, view: str, frames: Path | None = None, name: str = "") -> dict:
    """The route once, stopping twice: the picture's time and bytes for
    each step, each stop, and (scene view) each cut to another place."""
    out = {"step_ms": [], "step_bytes": [], "stop_ms": [], "stop_bytes": [], "cut_ms": [], "cut_bytes": []}

    def record(kind: str) -> bytes:
        if caller.display.force_full:
            kind = "cut"  # the door was asked for a whole screen: a full view from the server
        data, spent = draw(caller, clock)
        out[f"{kind}_ms"].append(spent * 1000)
        out[f"{kind}_bytes"].append(len(data))
        return data

    route = steps(caller, view)
    for index, move in enumerate(route):
        if view == "scene":
            target = move  # several steps: each is drawn
            while (caller.avatar.actor.x, caller.avatar.actor.y) != target:
                start = (caller.avatar.actor.x, caller.avatar.actor.y)
                here = screen_state(caller)
                before = caller.display.heading
                caller.walk(next_tile(caller, target))
                caller.display.heading = before
                clock.now += STEP
                record("step" if screen_state(caller) == here else "cut")
                if (caller.avatar.actor.x, caller.avatar.actor.y) == start:
                    break
        else:
            take_step(caller, clock, move)
            data = record("step")
            if frames is not None and index == 3:
                shot(frames, f"{name}-walking", data, caller)
        if index in (7, len(route) - 1):  # stop for a moment
            clock.now += lit.SETTLE + 0.05
            data = record("stop")
            if frames is not None and index == 7:
                shot(frames, f"{name}-stopped", data, caller)
    return out


def screen_state(caller: Caller) -> tuple:
    """What decides the whole picture in the scene view: the place you are
    in (its camera) and whether danger has handed the screen to the map."""
    body = caller.display.body
    return body.get("place", {}).get("here"), present_screen.threatened(body)


def next_tile(caller: Caller, target: tuple[int, int]) -> tuple[int, int]:
    from build import first_step
    zone = caller.game.core.world.zones[caller.avatar.actor.zone]
    grid = ["".join(".#"[not caller.game.core.world.content.tiles[t].passable] for t in row) for row in zone.template.grid]
    people = {(a.x, a.y) for a in zone.actors.values() if a is not caller.avatar.actor}
    start = (caller.avatar.actor.x, caller.avatar.actor.y)
    return first_step(grid, start, target, people - {target}) or start


TERMS: dict[tuple[int, int], FakeTerminal] = {}


def shot(out: Path, name: str, data: bytes, caller: Caller) -> None:
    """A PNG of the screen as it stands (every frame of the case has been
    written to its terminal: frames are deltas)."""
    try:
        import screenshot
    except ImportError:
        return
    screenshot.png(TERMS[(caller.info.width, caller.info.height)], out / f"{name}.png", (12, 24))


def case(width: int, height: int, glyphs: str, tier: str, view: str, frames: Path | None) -> dict:
    lit.PAINTER = lit.Painter()
    caller, clock = setup(width, height, glyphs, tier, view)
    name = f"tin-halo-v1-{view}-{glyphs}-{width}x{height}-{tier}"
    TERMS.clear()
    if frames is not None:
        TERMS[(width, height)] = FakeTerminal(width, height)
    out, _ = draw(caller, clock, full=True)
    if frames is not None:
        shot(frames, f"{name}-start", out, caller)
    cold = walk_route(caller, clock, view, frames, name)
    # Back to the start and the same route again: the cache is warm.
    place(caller.game, caller.client, "sodium-tin-halo", START)
    caller.pump(4)
    caller.display.heading = "right"
    clock.now += 2
    draw(caller, clock, full=True)
    TERMS.clear()
    warm = walk_route(caller, clock, view)
    stat = lambda values, f: round(f(values), 1) if values else None
    row = {"case": name, "view": view, "glyphs": glyphs, "tier": tier, "size": f"{width}x{height}",
           "steps": len(cold["step_ms"]), "cuts": len(cold["cut_ms"]),
           "cache_peak_bytes": lit.PAINTER.peak, "cache_cap_bytes": lit.PAINTER.limit}
    for label, run in (("cold", cold), ("warm", warm)):
        for kind in ("step", "stop", "cut"):
            row[f"{label}_{kind}_ms_p95"] = stat(run[f"{kind}_ms"], p95)
            row[f"{label}_{kind}_ms_max"] = stat(run[f"{kind}_ms"], max)
    for kind in ("step", "stop", "cut"):
        values = cold[f"{kind}_bytes"] + warm[f"{kind}_bytes"]
        row[f"{kind}_bytes_p95"] = int(p95(values)) if values else None
        row[f"{kind}_bytes_max"] = max(values) if values else None
    return row


async def pump(painter: lit.Painter, ready: asyncio.Event, stop: asyncio.Event) -> None:
    """The door's paint pump (client.py), for the harness."""
    while not stop.is_set():
        if painter.busy():
            painter.work()
            await asyncio.sleep(0)
        else:
            ready.clear()
            await asyncio.wait([asyncio.ensure_future(ready.wait()), asyncio.ensure_future(stop.wait())],
                               return_when=asyncio.FIRST_COMPLETED)


async def latency(width: int, height: int, glyphs: str, tier: str) -> dict:
    """How long a key can wait for the door's loop while four sharp
    pictures (and what is prepared around them) are painted: idle, painted
    in slices between keys (V1), and painted on the spot (V0). A key is
    handled the next time the loop gets a turn, so the measure is the time
    the loop is held between turns, sampled continuously."""
    caller, _ = setup(width, height, glyphs, tier, "street")
    lit.CLOCK = time.monotonic
    result = {}
    for mode in ("idle", "in slices (V1)", "on the spot (V0)"):
        ready, stop = asyncio.Event(), asyncio.Event()
        lit.PAINTER = lit.Painter(background=mode != "on the spot (V0)", kick=ready.set)
        painting = asyncio.create_task(pump(lit.PAINTER, ready, stop))
        held: list[float] = []
        watching = True

        async def watch() -> None:
            while watching:
                before = time.perf_counter()
                await asyncio.sleep(0)
                held.append(time.perf_counter() - before)

        watcher = asyncio.create_task(watch())
        await asyncio.sleep(0)
        started = time.perf_counter()
        if mode == "idle":
            await asyncio.sleep(0.3)
        else:
            for heading in ("right", "down", "left", "up"):
                caller.display.heading = heading
                draw(caller, RealClock(), full=True)
                await asyncio.sleep(0)
            while lit.PAINTER.busy():
                await asyncio.sleep(0)
        elapsed = time.perf_counter() - started
        watching = False
        await watcher
        stop.set()
        await painting
        result[mode] = {"key_wait_p95_ms": round(p95(held) * 1000, 1), "key_wait_max_ms": round(max(held) * 1000, 1),
                        "busy_ms": round(elapsed * 1000), "turns": len(held)}
    return result


class RealClock:
    """The door's clock, for the runs in real time."""

    now = property(lambda self: time.monotonic(), lambda self, value: None)

    def __call__(self) -> float:
        return time.monotonic()


async def realtime(width: int, height: int, glyphs: str, tier: str) -> dict:
    """The street route in real time, a step every 200 ms, painting in
    slices and spending the walk's byte budget: bytes and pictures a
    second, and for each step how long until a picture of it (or of a
    later step) was up."""
    caller, _ = setup(width, height, glyphs, tier, "street")
    lit.CLOCK = time.monotonic
    clock = RealClock()
    ready, stop = asyncio.Event(), asyncio.Event()
    lit.PAINTER = lit.Painter(background=True, kick=ready.set)
    painting = asyncio.create_task(pump(lit.PAINTER, ready, stop))
    caller.display.heading = "right"
    draw(caller, clock, full=True)
    area = caller.display.layout.viewport
    slot = (area.width, area.height - 1, False)
    eyes: list[tuple[int, int, str]] = []
    stepped: list[float] = []
    lag: dict[int, float] = {}
    pictures, sent, last = 0, 0, None
    started, picture_cpu = time.perf_counter(), 0.0
    eye = lambda: (caller.avatar.actor.x, caller.avatar.actor.y, caller.display.heading)
    headings = {(0, -1): "up", (1, 0): "right", (0, 1): "down", (-1, 0): "left"}

    def look() -> None:
        nonlocal pictures, last
        shown = lit.PAINTER.shown.get(slot)
        if shown is None or shown[0] is last:
            return
        last = shown[0]
        pictures += 1
        cam = shown[1]
        at = (int(cam.px - 0.5), int(cam.py - 0.5), headings[(cam.dx, cam.dy)])
        now = time.perf_counter()
        matches = [i for i, e in enumerate(eyes) if e == at]
        if matches:
            for i in range(matches[-1] + 1):
                lag.setdefault(i, now - stepped[i])

    for move in STREET:
        caller.key(move, 4)
        eyes.append(eye())
        stepped.append(time.perf_counter())
        deadline = stepped[-1] + STEP
        while time.perf_counter() < deadline:
            data, spent = draw(caller, clock)
            sent += len(data)
            picture_cpu += spent
            look()
            await asyncio.sleep(0.01)
    walked = time.perf_counter() - started
    picture_cpu += sum(seconds for _, seconds in lit.PAINTER.log)  # what the painter did in slices
    # then stand still until the sharp picture is up
    for _ in range(150):
        data, _ = draw(caller, clock)
        sent += 0 * len(data)
        look()
        if not lit.PAINTER.busy() and lit.PAINTER.wake_in(time.monotonic()) is None and shown_sharp(slot):
            break
        await asyncio.sleep(0.02)
    stop.set()
    await painting
    lags = [lag[i] for i in range(len(eyes)) if i in lag]
    return {"steps": len(eyes), "steps_shown_in_time": sum(1 for v in lags if v <= STEP),
            "lag_p95_ms": round(p95(lags) * 1000) if lags else None,
            "lag_max_ms": round(max(lags) * 1000) if lags else None,
            "walk_kib_per_s": round(sent / walked / 1024, 1), "pictures_per_s": round(pictures / walked, 1),
            "cpu_s_per_min": round(picture_cpu / walked * 60, 1),
            "painted": len(lit.PAINTER.log), "prepared": sum(1 for what, _ in lit.PAINTER.log if what == "prepared")}


def shown_sharp(slot: tuple) -> bool:
    shown = lit.PAINTER.shown.get(slot)
    return shown is not None and shown[0].grid != "low"


def table(rows: list[dict], latencies: dict, walks: dict, host: str) -> str:
    ms = lambda v: "-" if v is None else f"{v} ms"
    kib = lambda v: "-" if v is None else f"{v / 1024:.1f} KiB"
    lines = [f"Host: {host}", "",
             "Picture time per step (the lit renderer's share; p95 / max). Cold: first visit. Warm: the route again. "
             "Full: a whole new screen: the scene view cuts to another place's camera, danger hands the screen to the "
             "map, or the server sends a whole view (at 80x24 when the viewport scrolls; the door then redraws "
             "everything, in every view).", "",
             "| Case | Steps | Step cold | Step warm | Stop cold | Stop warm | Full cold | Full warm |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        pair = lambda k: f"{ms(r[k + '_p95'])} / {ms(r[k + '_max'])}"
        lines.append(f"| {r['view']}, {r['glyphs']}, {r['tier']}, {r['size']} | {r['steps']} | {pair('cold_step_ms')} | "
                     f"{pair('warm_step_ms')} | {pair('cold_stop_ms')} | {pair('warm_stop_ms')} | "
                     f"{pair('cold_cut_ms')} | {pair('warm_cut_ms')} |")
    lines += ["", "Bytes (p95 / max) against 16 KiB per delta, and the cache:", "",
              "| Case | Step | Stop | Full | Cache peak (cap) |", "|---|---|---|---|---|"]
    for r in rows:
        pair = lambda k: f"{kib(r[k + '_p95'])} / {kib(r[k + '_max'])}"
        lines.append(f"| {r['view']}, {r['glyphs']}, {r['tier']}, {r['size']} | {pair('step_bytes')} | "
                     f"{pair('stop_bytes')} | {pair('cut_bytes')} | {r['cache_peak_bytes'] / 1024 / 1024:.1f} MiB "
                     f"({r['cache_cap_bytes'] / 1024 / 1024:.0f} MiB) |")
    lines += ["", "How long a key can wait for the door while four sharp pictures are painted (the loop held between turns):", "",
              "| Case | Painting | Key wait p95 | Key wait max | Busy | Turns |", "|---|---|---|---|---|---|"]
    for name, modes in latencies.items():
        for mode, r in modes.items():
            lines.append(f"| {name} | {mode} | {r['key_wait_p95_ms']} ms | {r['key_wait_max_ms']} ms | "
                         f"{r['busy_ms']} ms | {r['turns']} |")
    lines += ["", "Walking in real time (a step every 200 ms, painting in slices, the walk's budget "
              f"{lit.WALK_RATE // 1024} KiB/s). Lag: from a step until a picture of it, or of a later step, is up.", "",
              "| Case | Steps | Shown within the step | Lag p95 | Lag max | Bytes/s walking | Pictures/s | Picture CPU s per walking minute | Painted (prepared) |",
              "|---|---|---|---|---|---|---|---|---|"]
    for name, r in walks.items():
        lines.append(f"| {name} | {r['steps']} | {r['steps_shown_in_time']} | {ms(r['lag_p95_ms'])} | "
                     f"{ms(r['lag_max_ms'])} | {r['walk_kib_per_s']} KiB/s | {r['pictures_per_s']} | {r['cpu_s_per_min']} | "
                     f"{r['painted']} ({r['prepared']}) |")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(args[0]) if args else OUT
    out.mkdir(parents=True, exist_ok=True)
    frames = out if "--frames" in sys.argv else None
    tiers = TIERS[:1] if "--quick" in sys.argv else TIERS
    sizes = SIZES[:1] if "--quick" in sys.argv else SIZES
    rows = []
    for width, height in sizes:
        for glyphs, tier in tiers:
            for view in ("street", "scene"):
                row = case(width, height, glyphs, tier, view, frames)
                print(row, flush=True)
                rows.append(row)
    latencies, walks = {}, {}
    for width, height in sizes:
        for glyphs, tier in tiers[:2]:
            name = f"{glyphs}, {tier}, {width}x{height}"
            latencies[name] = asyncio.run(latency(width, height, glyphs, tier))
            walks[name] = asyncio.run(realtime(width, height, glyphs, tier))
            print(name, latencies[name], walks[name], flush=True)
    host = f"{platform.system()} {platform.machine()}, Python {platform.python_version()}, {os.cpu_count()} CPUs"
    (out / "v1-budget.json").write_text(json.dumps({"host": host, "cases": rows, "latency": latencies, "walk": walks},
                                                   indent=2) + "\n", encoding="utf-8")
    (out / "v1-budget.md").write_text(table(rows, latencies, walks, host), encoding="utf-8")
    print(table(rows, latencies, walks, host))


if __name__ == "__main__":
    main()
