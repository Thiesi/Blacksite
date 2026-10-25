"""Build the issue #68 terminal mockups from real game state.

Run from the repository root:

    python scripts/presentation_mockups/build.py [out_dir]

A headless server (the test harness, production simulation) creates a
character, walks it through Clinic Row and Meridian Plaza, and jacks in.
Each scene is drawn twice from the same ZoneView/LatticeView body: once by
the shipped door renderer ("before") and once by proto.py ("proposal").
Outputs per scene and tier: .ans (the exact bytes a terminal receives),
.txt (cell text) and, when Pillow is installed, .png (a screenshot of the
.ans replayed through tests/fake_terminal.py).
"""

import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(Path(__file__).parent)]

from blacksite.content.loader import load_content  # noqa: E402
from blacksite.door.cells import CellBuffer  # noqa: E402
from blacksite.door.doorinfo import DoorInfo  # noqa: E402
from blacksite.door.layout import compute  # noqa: E402
from blacksite.door.model import Display  # noqa: E402
from blacksite.server.protocol import Frame  # noqa: E402
from tests.character_helpers import place  # noqa: E402
from tests.fake_terminal import FakeTerminal  # noqa: E402
from tests.harness import HeadlessServer  # noqa: E402

import proto  # noqa: E402

CONTENT = ROOT / "src/blacksite/content"
DATA = json.loads((Path(__file__).parent / "presentation.json").read_text(encoding="utf-8"))


class Caller:
    """One caller driven through the real door Display, keys in, frames out."""

    def __init__(self, width: int, height: int, tier: str = "256", local: Path | None = None) -> None:
        self.game = HeadlessServer(load_content(CONTENT, local), character_state={})
        self.local = local
        scratch = Path(tempfile.mkdtemp())
        self.info = DoorInfo(scratch / "door_info.json", scratch, {"user_id": 1, "handle": "Kale_9", "node_name": "mock"},
                             width, height, tier, 3600)
        self.client = self.game.connect(width=width, height=height)
        self.display = Display(self.info, "mock")
        self.t = 0.0
        self.pump(4)
        for key in ("down", "enter", *"Ash", "enter", "s", "enter"):  # Ghost, named Ash, first card
            self.key(key, 2)
        self.pump(5)

    def pump(self, ticks: int = 2) -> None:
        for _ in range(ticks):
            self.game.step()
            self.game.commit_characters()
            self.game.commit_commerce()
            for frame in self.game.frames_for(self.client):
                for out in self.display.receive(frame, self.t):
                    self.client.send(out)
        self.t += 0.1 * ticks

    def key(self, key: str, ticks: int = 4) -> None:
        for frame in self.display.key(key, self.t):
            self.client.send(frame)
        self.pump(ticks)

    @property
    def avatar(self):
        return self.game.core.characters.sim.avatars[self.client.session.user_id]

    def walk(self, *targets: tuple[int, int]) -> None:
        """Arrow keys along a shortest path that steps around people."""
        for target in targets:
            stuck = 0
            while (self.avatar.actor.x, self.avatar.actor.y) != target:
                zone = self.game.core.world.zones[self.avatar.actor.zone]
                grid = ["".join(".#"[not self.game.core.world.content.tiles[t].passable] for t in row)
                        for row in zone.template.grid]
                people = {(a.x, a.y) for a in zone.actors.values() if a is not self.avatar.actor}
                start = (self.avatar.actor.x, self.avatar.actor.y)
                step = first_step(grid, start, target, people - {target})
                if step is None:
                    raise RuntimeError(f"no path from {start} to {target}")
                key = {(1, 0): "right", (-1, 0): "left", (0, 1): "down", (0, -1): "up"}[(step[0] - start[0], step[1] - start[1])]
                self.key(key, 4)
                stuck = stuck + 1 if (self.avatar.actor.x, self.avatar.actor.y) == start else 0
                if stuck > 20:
                    raise RuntimeError(f"blocked at {start} walking to {target}")

    def before(self) -> bytes:
        self.display.toast = None
        self.display.hit_flash = False
        self.display.force_full = True
        out, ack = self.display.render(self.t + 1)
        if ack:
            self.client.send(ack)
        return out


def first_step(grid: list[str], start: tuple[int, int], goal: tuple[int, int],
               blocked: set[tuple[int, int]]) -> tuple[int, int] | None:
    from collections import deque
    came: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        if cell == goal:
            while came[cell] != start and came[cell] is not None:
                cell = came[cell]
            return cell
        x, y = cell
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            nx, ny = nxt
            if nxt in came or not (0 <= ny < len(grid) and 0 <= nx < len(grid[ny])):
                continue
            if grid[ny][nx] in "#=" or nxt in blocked:
                continue
            came[nxt] = cell
            queue.append(nxt)
    return None


def emit(out: Path, name: str, data: bytes, width: int, height: int) -> None:
    term = FakeTerminal(width, height)
    term.write(data)  # also asserts: no control bytes, no bottom-right write
    (out / f"{name}.ans").write_bytes(b"\x1b[0m\x1b[2J\x1b[H" + data + f"\x1b[0m\x1b[{height};1H\r\n".encode())
    (out / f"{name}.txt").write_text(term.screen_text() + "\n", encoding="utf-8")
    try:
        import screenshot
    except ImportError:
        return
    screenshot.png(term, out / f"{name}.png")


def zone_art(zone_id: str) -> proto.ZoneArt:
    grid = (CONTENT / "zones" / f"{zone_id}.map").read_text(encoding="utf-8").splitlines()
    return proto.ZoneArt(DATA, zone_id, grid)


def static_objects(zone_id: str) -> list[dict]:
    return json.loads((CONTENT / "zones" / f"{zone_id}.json").read_text(encoding="utf-8"))["objects"]


def nearby_rows(body: dict) -> list[tuple[str, str, str]]:
    rows = []
    for entry in body.get("nearby", [])[:6]:
        role = proto.actor_role({"role": entry.get("role", "npc_neutral")}, False)
        glyph = "τ" if "drone" in entry["name"].lower() else "☻" if entry.get("role", "").startswith("npc_") else "☺"
        rows.append((glyph, role, f"{entry['name']}"))
    return rows


def zone_scene(caller: Caller, tier: str, zone_id: str, log: list[tuple[str, str]], hint: list[tuple[str, str]],
               header_extra: list[tuple[str, str]], right_extra: list[tuple[str, str]], focus: str | None = None,
               here: list[str] | None = None) -> bytes:
    body = caller.display.body
    lay = compute(caller.info.width, caller.info.height)
    scene = proto.Scene(lay, proto.Paint(DATA, tier), DATA, tier)
    buf = CellBuffer(lay.width, lay.height, scene.paint("text"))
    art = zone_art(zone_id)
    me = body["me"]
    proto.render_zone(buf, scene, body, art, static_objects(zone_id), focus)
    night = me["clock"] < "06:00" or me["clock"] >= "20:00"
    proto.frame(buf, scene, me["safety"],
                [(f" {art.spec['district']} ", "head_district"), ("· ", "rule"), (f"{me['zone_name']} ", "head_zone"),
                 (f" {me['safety'].upper()} ", "word_" + me["safety"]), *header_extra],
                [*right_extra, (f" {me['clock']} ", "head_info"), *([(f"{art.spec['night_line']} ", "head_night")] if night else [])])
    proto.zone_panel(buf, scene, body, here or [], nearby_rows(body), lay.height >= 40)
    proto.log(buf, scene, log)
    proto.hints(buf, scene, hint)
    return buf.full()


def lattice_scene(caller: Caller, tier: str, body_zone: str) -> bytes:
    body = caller.display.body
    lay = compute(caller.info.width, caller.info.height)
    scene = proto.Scene(lay, proto.Paint(DATA, tier), DATA, tier)
    buf = CellBuffer(lay.width, lay.height, scene.paint("text"))
    sector = DATA["sectors"][body["sector"]]
    cores = {c: json.loads((CONTENT / "cores" / f"{c}.json").read_text(encoding="utf-8"))
             for c in sector["core_initials"]}
    proto.render_lattice(buf, scene, body, sector, cores)
    here = next(c for c in body["cells"] if c["id"] == body["me"]["cell"])
    proto.frame(buf, scene, body["body_safety"],
                [(" DOWN ", "head_zone"), ("· ", "rule"), (f"{sector['district']} SECTOR ", "lat_caption"),
                 (f" {sector['trace_policy']} trace ", "head_info")],
                [(" BODY ", "label"), (f"{body_zone} ", "head_info"), (f"{body['body_safety'].upper()} ", "word_" + body["body_safety"])])
    proto.lattice_panel(buf, scene, body, body_zone, cores.get(here.get("core") or ""),
                        "no trace until inside")
    proto.log(buf, scene, [("lattice", "The city goes quiet. Cells resolve under your feet."),
                           ("lattice", "Your body stays upstairs, in a clinic booth. Its shelter still matters."),
                           ("system", "+15 XP  three new cells")])
    proto.hints(buf, scene, [("Arrows", "links"), ("E", "enter"), ("J", "jack out"), ("Tab", "target"),
                             ("1-7", "cast"), ("R", "rig")])
    return buf.full()


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/design/proposals/68-presentation/mockups"
    out.mkdir(parents=True, exist_ok=True)
    plaza_log = [("place", "Meridian Plaza. The Ring hangs over it like a chandelier nobody turned off."),
                 ("ambient", "Tram bells from the hub. The fountain hisses."),
                 ("system", "+25 XP  new street")]
    plaza_log_wide = [("place", "Clinic Row. The street is so clean that dirt looks like an accident."),
                      ("ambient", "A polite overhead voice: your clone insurance premium is due."),
                      ("system", "+25 XP  new street"),
                      ("place", "Meridian Plaza. The Ring hangs over it like a chandelier nobody turned off."),
                      ("ambient", "Tram bells from the hub. The fountain hisses."),
                      ("speech", "Warden patrol: Evening. Keep it moving."),
                      ("ambient", "A courier drone ticks past at head height."),
                      ("system", "Public terminal ahead. E opens it; J jacks in.")]
    clinic_log = [("place", "Clinic Row. The street is so clean that dirt looks like an accident."),
                  ("ambient", "A polite overhead voice: your clone insurance premium is due."),
                  ("danger", "Contested street. Callers of grade 5 and up can fight here.")]

    for tier in ("256", "16", "truecolor"):
        for width, height in ((80, 24), (132, 50)):
            if tier != "256" and width != 80:
                continue
            caller = Caller(width, height, tier)
            # Clinic Row: arrive from the Wake Hall, use a clinic, jack in, come out on the boulevard.
            place(caller.game, caller.client, "vatside-clinics", (3, 2))
            caller.pump(4)
            caller.walk((12, 3), (30, 3), (30, 13), (12, 13), (12, 11), (17, 8))
            caller.key("J", 10)
            caller.pump(30)
            for key in ("right", "right", "right"):
                caller.key(key, 15)
            suffix = f"{width}x{height}-{tier}"
            if width == 80:
                emit(out, f"lattice-vatside-{suffix}", lattice_scene(caller, tier, "Clinic Row"), width, height)
                if tier == "256":
                    emit(out, f"lattice-vatside-{suffix}-before", caller.before(), width, height)
            caller.key("J", 10)
            caller.pump(20)
            caller.walk((12, 11), (12, 13), (47, 13), (47, 9), (47, 13), (62, 13), (62, 4), (46, 3))
            caller.pump(600)
            if width == 80:
                emit(out, f"clinic-row-{suffix}", zone_scene(
                    caller, tier, "vatside-clinics", clinic_log,
                    [("Tab", "target"), ("F", "fire"), ("I", "inventory"), ("M", "map"), ("Q", "jobs"), ("?", "help")],
                    [(" PvP G5+ ", "head_info")], [(" Cold Chain normal ", "head_info")]), width, height)
                if tier == "256":
                    emit(out, f"clinic-row-{suffix}-before", caller.before(), width, height)
            # Meridian Plaza by Sablier Boulevard, then to the first public terminal.
            caller.walk((62, 2), (77, 2), (78, 2))
            caller.key("right", 6)
            caller.pump(10)
            caller.walk((60, 3), (32, 3), (57, 6))  # back east so the camera centres
            caller.pump(600)
            caller.walk((57, 6))
            emit(out, f"meridian-plaza-{suffix}", zone_scene(
                caller, tier, "core-plaza", plaza_log_wide if height >= 40 else plaza_log,
                [("E", "terminal"), ("J", "jack in"), ("Tab", "target"), ("I", "inventory"), ("M", "map"), ("?", "help")],
                [], [], focus="plaza-public-2",
                here=["E Public terminal", "J jack in here", "  Core sector, public"]), width, height)
            if tier == "256":
                emit(out, f"meridian-plaza-{suffix}-before", caller.before(), width, height)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
