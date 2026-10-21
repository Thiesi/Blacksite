"""Zone authoring boundaries, typed geometry and operator shutdown receipts."""

from copy import deepcopy
from dataclasses import replace

from blacksite.content.loader import ContentTree
from blacksite.content.schema import TileChange, ZoneLayout
from blacksite.content.validate import validate
from blacksite.server.protocol import Frame
from tests.harness import ADMIN_SECRET, HeadlessServer, hello


def test_shipped_maps_match_gazetteer_and_activate_with_hub(content_tree: ContentTree) -> None:
    assert validate(content_tree) == []
    hall, clinics = content_tree.zones["vatside-wake-hall"], content_tree.zones["vatside-clinics"]
    assert (hall.width, hall.height, hall.meta.sight_radius) == (40, 20, 10)
    assert (clinics.width, clinics.height, clinics.meta.sight_radius) == (80, 34, 12)
    assert {ex.target_zone for ex in hall.meta.exits} == {"vatside-clinics"}
    assert {ex.target_zone for ex in clinics.meta.exits} == {
        "vatside-wake-hall", "core-plaza", "vatside-vat-row", "core-tram-hub"}
    relay = next(obj for obj in clinics.meta.objects if obj.kind == "relay")
    assert not any(pocket.contains(relay.tile) for pocket in clinics.meta.pockets)
    tree = deepcopy(content_tree)
    manifest = tree.bundles["m1-zone-preview"]
    assert manifest.status == "active"
    assert validate(tree) == []


def test_unsafe_geometry_and_night_radius_fail_validation(content_tree: ContentTree) -> None:
    tree = deepcopy(content_tree)
    zone = tree.zones["vatside-clinics"]
    bad = ZoneLayout("bad", (TileChange((10, 8), "hazard"),), (), ("missing-exit",))
    tree.zones[zone.id] = replace(zone, meta=replace(zone.meta, layouts=(bad,), sight_radius_night=0))
    problems = "\n".join(map(str, validate(tree)))
    assert "hazard in safe zone or pocket" in problems
    assert "hazard needs a warning tile" in problems
    assert "unknown alternate route" in problems and "sight_radius_night" in problems


def test_operator_stop_receipt_survives_immediate_shutdown() -> None:
    game = HeadlessServer()
    operator = game.connect(frame=hello(secret=ADMIN_SECRET))
    game.frames_for(operator)
    operator.send(Frame("admin.stop"))
    game.step()
    # This is the real I/O race: shutdown can run before the writer drains.
    game.core.shutdown()
    frames = game.frames_for(operator)
    assert [frame.type for frame in frames] == ["view", "bye"]
    assert frames[0].data["body"]["lines"] == ['{"ok": true}']
