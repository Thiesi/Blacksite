"""V1 (#68): the lit picture within budget.

What the review checks: the fixed camera's viewpoint is content on public
ground and reaches the door only over known ground; the door's own pick
uses only what the view shows; pictures are kept by eye and known ground,
painted in slices that give way to keys, and prepared only on known
ground; walking draws the cheap class and stopping the sharp one.
"""

import json
import shutil
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.door.cells import CellBuffer
from blacksite.door.layout import Rect
from blacksite.door.palette import Palette
from blacksite.door.present import lit, street
from blacksite.door.present.paint import Paint
from blacksite.server.views import looks
from tests.door.test_lit import CANDIDATE, CONTENT, SPOT, halo
from tests.server.test_looks import move

LOOK = "looks/sodium-tin-halo.json"


@pytest.fixture(scope="module")
def content():
    return load_content(CONTENT, CANDIDATE)


@pytest.fixture
def trial(monkeypatch):
    monkeypatch.setattr(looks, "TRIAL", True)


@pytest.fixture(autouse=True)
def painter(monkeypatch):
    """Each test paints on the spot with a fresh cache and a still clock."""
    monkeypatch.setattr(lit, "PAINTER", lit.Painter())
    clock = [100.0]
    monkeypatch.setattr(lit, "CLOCK", lambda: clock[0])
    return clock


def edited(tmp_path: Path, change) -> Path:
    local = tmp_path / "local"
    shutil.copytree(CANDIDATE, local)
    path = local / LOOK
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")
    return local


def place_named(data: dict, name: str) -> dict:
    return next(p for p in data["places"] if p["name"] == name)


def paint(display, glyphs: str = "modern", tier: str = "truecolor") -> Paint:
    return Paint(Palette({"roles": display.palette.roles}, tier), glyphs)


# --- the viewpoint is content --------------------------------------------------


def test_every_place_in_the_candidate_has_a_viewpoint_and_validates(content) -> None:
    assert validate(content) == []
    assert all(place.view is not None for place in content.looks["sodium-tin-halo"].places)


@pytest.mark.parametrize("at", [[0, 0], [12, 1]])  # a wall, a booth (cover)
def test_a_viewpoint_must_stand_on_open_ground(tmp_path, at) -> None:
    local = edited(tmp_path, lambda d: place_named(d, "The bar").update(view={"at": at, "facing": "down"}))
    problems = [p.message for p in validate(load_content(CONTENT, local))]
    assert any(f"view {at} is not public open ground" in p for p in problems), problems


def test_the_server_sends_a_viewpoint_only_over_known_ground(info, tmp_path, trial) -> None:
    def far(data: dict) -> None:
        data["charted"] = False  # only what you have seen is known
        place_named(data, "The bar")["view"] = {"at": [41, 1], "facing": "left"}
    game, client, display = halo(info, load_content(CONTENT, edited(tmp_path, far)), ticks=2)

    def bar_place(tile: tuple[int, int]) -> dict:
        move(game, client, "sodium-tin-halo", tile)
        for _ in range(2):
            game.step()
            for frame in game.frames_for(client):
                for out in display.receive(frame, 1):
                    client.send(out)
        return next(p for p in display.body["place"]["places"] if p["name"] == "The bar")

    assert "view" not in bar_place((12, 13))  # its tile is beyond what you have seen
    bar_place((38, 3))
    assert bar_place((12, 13))["view"] == {"at": [41, 1], "facing": "left"}  # remembered now


# --- the door's own pick -------------------------------------------------------


def test_the_door_picks_a_viewpoint_from_known_ground_only(info, content, trial) -> None:
    _, _, display = halo(info, content, ticks=6)
    body = json.loads(json.dumps(display.body))
    for spot in body["place"]["places"]:
        spot.pop("view", None)
    world = street.World(body)
    here = body["place"]["here"]
    chosen = lit.viewpoint(body, world)
    assert chosen is not None
    x, y, facing = chosen
    tile = world.at(x, y)[0]
    assert tile is not None and tile not in street.OPAQUE and facing in street.HEADINGS
    # Nothing known: nothing to pick from.
    blind = {**body, "tiles": [[-1] * len(row) for row in body["tiles"]]}
    assert lit.choose_view(street.World(blind), tuple(next(p["rect"] for p in body["place"]["places"]
                                                            if p["name"] == here))) is None


def test_an_authored_viewpoint_wins(info, content, trial) -> None:
    _, _, display = halo(info, content, ticks=6)
    body = display.body
    here = next(p for p in body["place"]["places"] if p["name"] == body["place"]["here"])
    assert lit.viewpoint(body, street.World(body)) == (*here["view"]["at"], here["view"]["facing"])


# --- the fixed camera ----------------------------------------------------------


def test_the_fixed_camera_paints_once_per_place(info, content, trial) -> None:
    game, client, display = halo(info, content, ticks=6)
    area = Rect(0, 0, 100, 18)
    lit.render(CellBuffer(100, 18), display.body, area, paint(display), "right", hud=False, fixed=True)
    painted = len(lit.PAINTER.log)
    assert painted == 1
    for tile in ((5, 10), (6, 10), (6, 11)):  # still in the room: the same camera
        move(game, client, "sodium-tin-halo", tile)
        for frame in game.frames_for(client):
            display.receive(frame, 1)
        lit.render(CellBuffer(100, 18), display.body, area, paint(display), "right", hud=False, fixed=True)
    assert len(lit.PAINTER.log) == painted


def test_the_fixed_camera_draws_you(info, content, trial) -> None:
    _, _, display = halo(info, content, ticks=6)
    body = json.loads(json.dumps(display.body))
    assert lit.viewpoint(body, street.World(body)) == (4, 10, "right")
    others = [a for a in body["actors"] if a.get("role") != "player_self"]
    me = next(a for a in body["actors"] if a.get("role") == "player_self")
    area = Rect(0, 0, 100, 18)
    seen, unseen = CellBuffer(100, 18), CellBuffer(100, 18)
    for buffer, (x, y) in ((seen, (12, 10)), (unseen, (1, 1))):  # before the camera, behind it
        lit.render(buffer, {**body, "actors": [*others, {**me, "x": x, "y": y}]}, area, paint(display), "right",
                   hud=False, fixed=True)
    assert seen.cells != unseen.cells


# --- the walk and the stop -----------------------------------------------------


def test_walking_draws_the_cheap_class_and_stopping_the_sharp_one(info, content, trial, painter) -> None:
    game, client, display = halo(info, content, ticks=6)
    area = Rect(0, 0, 100, 18)
    draw = lambda: lit.render(CellBuffer(100, 18), display.body, area, paint(display), "right", hud=False)
    draw()
    move(game, client, "sodium-tin-halo", (SPOT[0] + 1, SPOT[1]))
    for frame in game.frames_for(client):
        display.receive(frame, 1)
    painter[0] += 0.2
    buffer = CellBuffer(100, 18)
    lit.render(buffer, display.body, area, paint(display), "right", hud=False)
    walking = {cell.glyph for row in buffer.cells for cell in row}
    assert walking <= {"▀", " "}  # half-blocks, two cells to a pixel
    pairs = sum(row[i] == row[i + 1] for row in buffer.cells for i in range(0, 98, 2))
    assert pairs > 0.9 * 18 * 49
    styles = {cell.style for row in buffer.cells for cell in row if cell.glyph == "▀"}
    assert all(c in lit._STEPS.table for s in styles for c in s.fg + s.bg)  # truecolor, in steps
    painter[0] += lit.SETTLE + 0.01
    assert lit.PAINTER.settled(painter[0])
    buffer = CellBuffer(100, 18)
    lit.render(buffer, display.body, area, paint(display), "right", hud=False)
    assert any(0x1FB00 <= ord(cell.glyph) <= 0x1FB3B for row in buffer.cells for cell in row if cell.glyph)


def test_16_colours_has_no_walking_class(info, content, trial, painter) -> None:
    game, client, display = halo(info, content, tier="16", glyphs="cp437", ticks=6)
    area = Rect(0, 0, 80, 10)
    lit.render(CellBuffer(80, 10), display.body, area, paint(display, "cp437", "16"), "right", hud=False)
    move(game, client, "sodium-tin-halo", (SPOT[0] + 1, SPOT[1]))
    for frame in game.frames_for(client):
        display.receive(frame, 1)
    painter[0] += 0.2
    lit.render(CellBuffer(80, 10), display.body, area, paint(display, "cp437", "16"), "right", hud=False)
    assert all(frame.grid == "half" for frame in lit.PAINTER.cache.values())


# --- painting in the background ------------------------------------------------


def job(cost: int, out: list[str], name: str):
    def columns():
        for _ in range(cost):
            yield
        out.append(name)
        return lit.Frame(1, 1, bytearray(3), lit.array("f", [1.0]), [], "half")
    return columns


def test_the_latest_wanted_picture_replaces_an_older_one() -> None:
    woke: list[bool] = []
    painter = lit.Painter(background=True, wake=lambda: woke.append(True))
    done: list[str] = []
    assert painter.frame("a", job(5, done, "a")) is None
    assert painter.frame("b", job(5, done, "b")) is None  # before "a" started: "a" is dropped
    while painter.busy():
        painter.work(0.001)
    assert done == ["b"] and woke == [True] and painter.take_fresh()
    assert painter.frame("b", job(5, done, "b")) is not None and not painter.take_fresh()


def test_a_prepared_picture_gives_way_and_is_resumed() -> None:
    painter = lit.Painter(background=True)
    done: list[str] = []
    painter.prepare("ahead", job(50, done, "ahead"))
    painter.work(0)  # one column of it
    assert painter.current is not None and painter.current[0] == "ahead"
    painter.frame("here", job(3, done, "here"))
    while painter.busy():
        painter.work(0)
    assert done == ["here", "ahead"]
    assert [what for what, _ in painter.log] == ["wanted", "prepared"]


def test_work_returns_between_columns() -> None:
    painter = lit.Painter(background=True)
    done: list[str] = []
    painter.frame("slow", job(10_000, done, "slow"))
    painter.work(0)
    assert painter.busy() and not done  # one slice, then the loop has its turn


def test_the_cache_is_bounded_in_bytes() -> None:
    painter = lit.Painter(limit=100)
    for i in range(10):
        painter.frame(i, lambda: (yield from ()) or lit.Frame(4, 4, bytearray(48), lit.array("f", [1.0] * 16), []))
    assert painter.size <= 100 + 400 and len(painter.cache) < 10 and painter.peak >= painter.size


def test_prepared_pictures_stand_only_on_known_ground(info, content, trial) -> None:
    _, _, display = halo(info, content, ticks=6)
    body = display.body
    world = street.World(body)
    asked: list[tuple] = []
    lit.PAINTER = lit.Painter(background=True)
    lit.PAINTER.prepare = lambda key, job: asked.append(key)  # type: ignore[method-assign]
    for x, y in ((SPOT[0], SPOT[1]), (1, 1), (42, 20)):  # middle of the room, two corners
        for heading in street.HEADINGS:
            lit.prepare_around((x, y, heading), False, "sextant", world, lambda *k: k, lambda *k: (lambda: None))
    assert asked
    for nx, ny, *_ in asked:
        tile = world.at(nx, ny)[0]
        assert tile is not None and tile not in street.OPAQUE


def test_a_picture_is_kept_by_known_ground(info, content, trial) -> None:
    """Ground learned since a picture was painted makes a new picture, so a
    kept one never stands in for a view that knows more or less."""
    _, _, display = halo(info, content, ticks=6)
    body = json.loads(json.dumps(display.body))
    less = json.loads(json.dumps(body))
    row = next(i for i, r in enumerate(less["tiles"]) if any(v != -1 for v in r))
    less["tiles"][row] = [-1] * len(less["tiles"][row])
    assert lit.signature(street.World(body)) != lit.signature(street.World(less))


def test_other_places_are_prepared_only_from_viewpoints_the_server_sent(info, content, trial) -> None:
    _, _, display = halo(info, content, ticks=6)
    body = json.loads(json.dumps(display.body))
    body["place"]["places"][0].pop("view")  # as if its tile were unknown
    sent = [tuple(p["view"]["at"]) for p in body["place"]["places"] if "view" in p]
    asked: list[tuple] = []
    lit.PAINTER = lit.Painter(background=True)
    lit.PAINTER.prepare = lambda key, job: asked.append(key)  # type: ignore[method-assign]
    here = lit.viewpoint(body, street.World(body))
    lit.prepare_places(body, here, "sextant", lambda *k: k, lambda *k: (lambda: None))
    assert asked and all(key[:2] in sent and key[:3] != here for key in asked)


def test_in_the_door_a_picture_lands_between_keys_and_is_drawn(info, content, trial, painter) -> None:
    """The door's wiring (client.py): the display asks, the pump paints in
    slices, a landed picture marks the display dirty and is drawn."""
    import asyncio

    _, _, display = halo(info, content, ticks=6)
    display.present, display.view_mode, display.glyphs, display.heading = True, "street", "modern", "right"

    async def scenario() -> None:
        ready = asyncio.Event()
        lit.PAINTER = lit.Painter(background=True, kick=ready.set)
        display.dirty, display.last_render = True, -1.0
        first, _ = display.render(painter[0])
        assert lit.PAINTER.busy()  # nothing painted yet: the screen went out without the picture
        slices = 0
        while lit.PAINTER.busy():
            lit.PAINTER.work()
            slices += 1
            await asyncio.sleep(0)
        assert slices > 1
        display.update(10.0, painter[0])
        assert display.dirty  # the picture landed
        display.last_render = -1.0
        second, _ = display.render(painter[0])
        assert any(0x1FB00 <= ord(ch) <= 0x1FB3B for ch in second.decode("utf-8"))

    asyncio.run(scenario())
