"""UI 4: progress, costs and permanent/temporary values at both sizes."""

from dataclasses import asdict, replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.door.model import Display
from blacksite.server.items import ItemInstance
from blacksite.server.players import Player
from blacksite.server.progression_views import character_sheet, skill_menu
from blacksite.server.protocol import Frame, encode
from tests.fake_terminal import FakeTerminal


def render(info, content, body, size):
    display = Display(replace(info, width=size[0], height=size[1], color_depth="16"))
    display.receive(Frame("welcome", {"keymap": asdict(content.keymaps), "palette": asdict(content.palette)}), 0)
    frame = Frame("view", {"rev": 1, "kind": "menu", "body": body})
    encode(frame)
    display.receive(frame, 1)
    terminal = FakeTerminal(*size)
    terminal.write(display.render(1)[0])
    return terminal.screen_text()


def records(repo_root: Path):
    content = load_content(repo_root/"src/blacksite/content")
    player = Player("runner", "node", "bbs", "Wide\u754c", "Runner\u754c", "hardline", "2026-01-01T00:00:00+00:00")
    player.update_progression(1500)
    return content, player


@pytest.mark.parametrize("size", [(80,24), (132,50)])
def test_ui_4_skills_show_point_cost_use_cap_and_capped_fraction(info, repo_root, size):
    content, player = records(repo_root)
    player.skills["kinetic"] = 99.8
    body = skill_menu(player, content, 0, 0)
    text = render(info, content, body, size)
    assert "99.8/100" in text and "12 grade points" in text
    assert "Use gain today 0/2" in text and "capped at 100" in text
    assert "+ spend 1 grade point" in text and "Esc/B back" in text


@pytest.mark.parametrize("size", [(80,24), (132,50)])
def test_ui_4_character_sheet_keeps_grade_implant_and_dependency_readable(info, repo_root, size):
    content, player = records(repo_root)
    tid = "imp_sablier_secure_pocket"
    item = ItemInstance("installed", tid, player.id, quality=1.12)
    items = {item.id: item}
    player.inventory.append(item.id)
    player.implants["torso"] = item.id
    player.dependencies = [{"template": "drug_sable_redline", "since": 0}]
    rows = character_sheet(player, content, items, 0, 2)["rows"]
    for rid, expected in [("grade", "5: Ninety-Day"), ("implant:torso", "quality 1.12"),
                           ("dependency:drug_sable_redline", "400 chits, 10 minutes")]:
        cursor = next(i for i, row in enumerate(rows) if row["id"] == rid)
        text = render(info, content, character_sheet(player, content, items, 0, 2, cursor), size)
        assert expected in text and "skills" in text and "Esc/B back" in text
