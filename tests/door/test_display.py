"""Terminal UI §1/§2/§4/§5/§6 and architecture §5 view flow."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from blacksite.door.cells import display_width
from blacksite.door.doorinfo import DoorInfo, read
from blacksite.door.layout import compute
from blacksite.door.model import Display
from blacksite.door.palette import Palette, Style, resolve_tier
from blacksite.door.screens import SessionWarnings
from blacksite.server.protocol import Frame
from tests.fake_terminal import FakeTerminal


def welcome(repo_root: Path) -> Frame:
    root = repo_root / "src" / "blacksite" / "content"
    return Frame("welcome", {"proto": 1, "server_version": "0.0.1", "player": None,
        "palette": json.loads((root / "palette.json").read_text(encoding="utf-8")),
        "keymap": json.loads((root / "keymaps.json").read_text(encoding="utf-8")), "motd": "You hear the vents."})


@pytest.mark.parametrize("width,height,viewport,logs", [(80, 24, (55, 17), 3), (132, 50, (107, 38), 8)])
def test_exact_layout(width: int, height: int, viewport: tuple[int, int], logs: int) -> None:
    layout = compute(width, height)
    assert (layout.viewport.width, layout.viewport.height) == viewport
    assert layout.log.height == logs
    assert layout.hint.y == height - 2


def test_log_rows_scale() -> None:
    assert [compute(80, h).log.height for h in (24, 28, 32, 36, 40, 50)] == [3, 4, 5, 6, 8, 8]


def test_roles_every_tier_and_variants(repo_root: Path) -> None:
    data = welcome(repo_root).data["palette"]
    for tier in ("16", "256", "truecolor"):
        for variant in ("default", "deutan", "protan"):
            palette = Palette(data, tier, variant)
            for role in data["roles"]:
                assert palette.style(role).sgr().startswith(b"\x1b[")
    assert Style(12, tier="16").sgr().startswith(b"\x1b[0;1;34")
    role = next(role for role, values in data["roles"].items() if values["256"]["default"] != values["256"]["deutan"])
    assert Palette(data, "256").style(role) != Palette(data, "256", "deutan").style(role)
    assert resolve_tier("16", "truecolor") == "16"


@pytest.mark.parametrize("width,height", [(80, 24), (132, 50)])
def test_title_help_and_wide_handle(info: DoorInfo, repo_root: Path, width: int, height: int) -> None:
    model = Display(replace(info, width=width, height=height, raw={**info.raw, "handle": "界" * 100}))
    model.receive(welcome(repo_root), 0)
    terminal = FakeTerminal(width, height)
    data, ack = model.render(0)
    terminal.write(data)
    assert "BLACKSITE" in terminal.screen_text() and "You hear the vents." in terminal.screen_text()
    assert "..." in terminal.screen_text().splitlines()[0]
    assert ack.data["rev"] == 0
    model.key("?", .2)
    terminal.write(model.render(.2)[0])
    assert "HELP" in terminal.screen_text() and "Page 1/" in terminal.screen_text()
    model.key("pagedown", .4)
    terminal.write(model.render(.4)[0])
    assert "Page 2/" in terminal.screen_text()
    model.key("escape", .6)
    terminal.write(model.render(.6)[0])
    assert "BLACKSITE" in terminal.screen_text()


@pytest.mark.parametrize("width,height", [(80, 24), (132, 50)])
def test_menu_detail_layout_and_authoritative_cursor(info: DoorInfo, width: int, height: int) -> None:
    model = Display(replace(info, width=width, height=height))
    model.connected = True
    body = {"title": "INVENTORY", "columns": ["Item"], "rows": [{"id": "sidearm", "cells": ["Sidearm"]}],
            "cursor": 0, "actions": [{"key": "e", "label": "equip"}], "detail": "DETAIL: starter sidearm"}
    model.receive(Frame("view", {"rev": 4, "kind": "menu", "body": body}), 0)
    terminal = FakeTerminal(width, height)
    terminal.write(model.render(0)[0])
    screen = terminal.screen_text().splitlines()
    item_row = next(i for i, line in enumerate(screen) if "Sidearm" in line)
    detail_row = next(i for i, line in enumerate(screen) if "DETAIL:" in line)
    assert detail_row < item_row if width >= 100 else detail_row > item_row
    frames = model.key("down", .1)
    assert frames[0].data["name"] == "menu_cursor" and model.body["cursor"] == 0
    selected = model.key("e", .2)[0]
    assert selected.data["args"]["row"] == "sidearm"
    assert selected.data["expected_revision"] == 4 and selected.data["request_id"]
    assert model.key("b", .3)[0].data["name"] == "menu_close"


def test_prompt_echo_and_cancel_suspend_vi_movement(info: DoorInfo) -> None:
    model = Display(info)
    model.connected = True
    model.receive(Frame("prompt", {"id": "chat", "kind": "line", "label": "Say", "max_len": 5}), 0)
    for key in ("j", "界", "k", "界", "up"):
        assert model.key(key, 0) == []
    assert model.prompt.text == "j界k"
    model.key("backspace", 0)
    assert model.prompt.text == "j界"
    frame = model.key("enter", 0)[0]
    assert frame.data == {"id": "chat", "text": "j界"}
    model.receive(Frame("prompt", {"id": "chat", "kind": "line", "label": "Say", "max_len": 200}), 0)
    model.key("j", 0)
    assert model.key("escape", 0)[0].data == {"name": "prompt_cancel", "args": {"id": "chat"}}
    assert model.prompt is None
    assert model.key("j", 0)[0].data["k"] == "j"
    assert model.key("ctrl-o", 0)[0].data["k"] == "ctrl-o"


def test_render_rate_bound_coalesce_and_ack(info: DoorInfo) -> None:
    model = Display(info)
    model.connected = True
    terminal = FakeTerminal()
    terminal.write(model.render(0)[0])
    for rev in range(1, 10):
        model.receive(Frame("view", {"rev": rev, "kind": "text", "body": {"title": f"View {rev}", "lines": []}}), .01)
    assert model.render(.05) == (b"", None)
    data, ack = model.render(.1)
    terminal.write(data)
    assert ack.data["rev"] == 9
    assert "View 9" in terminal.screen_text()
    assert model.render(.2) == (b"", None)


def test_delta_base_mismatch_resync_and_atomic_apply(info: DoorInfo) -> None:
    model = Display(info)
    model.receive(Frame("view", {"rev": 1, "kind": "text", "body": {"title": "First", "lines": ["one"]}}), 0)
    assert model.receive(Frame("delta", {"rev": 2, "base": 1, "ops": [{"op": "replace", "path": "/body/title", "value": "Second"}]}), 0) == []
    assert model.body["title"] == "Second"
    requests = model.receive(Frame("delta", {"rev": 4, "base": 3, "ops": []}), 0)
    assert requests[0].data["name"] == "resync"
    assert model.receive(Frame("delta", {"rev": 5, "base": 4, "ops": []}), 0) == []
    model.receive(Frame("view", {"rev": 5, "kind": "text", "body": {"title": "Fresh", "lines": []}}), 0)
    model.receive(Frame("delta", {"rev": 6, "base": 5, "ops": [
        {"op": "replace", "path": "/body/title", "value": "Must roll back"}, {"op": "remove", "path": "/missing"}]}), 0)
    assert model.body["title"] == "Fresh" and model.revision == 5


def test_exit_confirmation_and_session_limit(info: DoorInfo) -> None:
    model = Display(info)
    model.connected = True
    model.key("ctrl-x", 0)
    model.key("escape", 0)
    assert not model.leaving
    model.key("ctrl-x", 0)
    assert model.key("y", 0)[0].type == "bye" and model.leaving
    warnings = SessionWarnings(3600)
    assert warnings.update(3299) == []
    assert "5 minute" in warnings.update(3300)[0]
    assert warnings.update(3301) == []
    assert "1 minute" in warnings.update(3540)[0]


def test_doorinfo_optional_fields_and_limits(scratch_dir: Path) -> None:
    path = scratch_dir / "door_info.json"
    raw = {"handle": "Wide界", "user_id": 1, "terminal_width": 80, "terminal_height": 24,
           "color_depth": "16", "node_name": "test", "session_limit_seconds": 120, "door_api": 5}
    path.write_text(json.dumps(raw), encoding="utf-8")
    info = read({"NETBBS_DOOR_INFO": str(path), "BLACKSITE_INSTALL_DIR": str(scratch_dir)})
    assert info.raw == raw and info.session_limit == 120
    assert read({"NETBBS_DOOR_INFO": str(path), "BLACKSITE_INSTALL_DIR": str(scratch_dir), "BLACKSITE_SESSION_LIMIT": "60"}).session_limit == 60
    aliased = read({"NETBBS_DOOR_INFO": str(path), "DOOR_BLACKSITE_INSTALL_DIR": str(scratch_dir), "DOOR_BLACKSITE_SESSION_LIMIT": "3600"})
    assert aliased.install == scratch_dir and aliased.session_limit == 120
    raw["outbound"] = {"credential": "must-not-cross-the-game-link"}
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert "outbound" not in read({"NETBBS_DOOR_INFO": str(path), "BLACKSITE_INSTALL_DIR": str(scratch_dir)}).raw
    with pytest.raises(ValueError):
        read({})


@pytest.mark.parametrize('tier', ['16', '256', 'truecolor'])
def test_golden_screens(info: DoorInfo, repo_root: Path, golden, tier: str) -> None:
    root = repo_root / "tests" / "door" / "golden"
    for width, height in ((80, 24), (132, 50)):
        model = Display(replace(info, width=width, height=height, color_depth=tier))
        model.receive(welcome(repo_root), 0)
        terminal = FakeTerminal(width, height)
        terminal.write(model.render(0)[0])
        golden(f'title_{width}x{height}', terminal, tier, trim=True)
        if width == 80:
            model.receive(Frame("view", {"rev": 1, "kind": "menu", "body": {
                "title": "INVENTORY", "columns": ["Item"], "rows": [{"id": "sidearm", "cells": ["Sidearm"]}],
                "cursor": 0, "actions": [{"key": "e", "label": "equip"}], "detail": "DETAIL: starter sidearm"}}), .2)
            terminal.write(model.render(.2)[0])
            golden('menu_80x24', terminal, tier, trim=True)
