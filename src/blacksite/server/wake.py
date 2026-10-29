"""Server-owned Wake screens and input state; game design 4 / UI 7."""

from dataclasses import dataclass
import textwrap
from typing import Any

from blacksite.layout import compute as screen_layout
from blacksite.content.loader import ContentTree
from blacksite.server.rules.character import ARCHETYPES, default_name


def wrapped(text: str, width: int) -> list[str]:
    return [line for paragraph in text.split("\n\n") for line in [*textwrap.wrap(paragraph.replace("\n", " "), max(12, width)), ""]]


def menu(title: str, rows: list[dict[str, Any]], cursor: int, detail: str, hint: str = "Enter selects") -> dict[str, Any]:
    return {"title": title, "kind": "select", "columns": ["Choice"], "rows": rows,
            "cursor": cursor, "actions": [{"key": "enter", "label": "select"}],
            "page": 1, "pages": 1, "detail": detail, "hint": hint, "clear_prompt": True}


@dataclass
class Wake:
    stage: str = "archetype"
    archetype: str = "hardline"
    name: str = ""
    cursor: int = 0
    screen: int = 1
    page: int = 0
    error: str = ""
    dirty: bool = True
    prompt_id: str = ""

    @classmethod
    def restore(cls, value: dict[str, Any]) -> "Wake":
        return cls(**{key: value[key] for key in ("stage", "archetype", "name", "cursor", "screen", "page") if key in value})

    def saved(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in ("stage", "archetype", "name", "cursor", "screen", "page")}

    def body(self, content: ContentTree, handle: str, width: int, height: int) -> dict[str, Any]:
        layout = screen_layout(width, height)
        detail_width = layout.wake_detail_width
        if self.stage == "archetype":
            rows = [{"id": slug, "cells": [slug.title()]} for slug, _ in ARCHETYPES]
            slug = rows[self.cursor]["id"]
            detail = "\n".join(wrapped(content.text["wake-archetype-" + slug].body, detail_width))
            body = menu("THE WAKE - Choose your archetype", rows, self.cursor, detail, "Enter selects  Esc/B leaves")
            kind = "menu"
        elif self.stage == "card":
            cards = list(content.wake_cards.values())
            rows = [{"id": card.id, "cells": [card.name]} for card in cards] + [{"id": "none", "cells": ["Take no card"]}]
            cursor = min(self.cursor, len(rows) - 1)
            detail = content.text[cards[cursor].pitch].body if cursor < len(cards) else "You leave the cards. No standing changes."
            body = menu("THE WAKE - Recruiter cards", rows, cursor, "\n".join(wrapped(detail, detail_width)), "Enter takes card  Esc/B takes none")
            kind = "menu"
        else:
            kind = "text"
            if self.stage == "name":
                lines = ["Your name is yours. Your BBS handle stays visible.", "",
                         "2-24 display columns: letters, digits, space, - _ '",
                         "Enter keeps: " + default_name(handle), self.error]
                title, hint = "THE WAKE - Choose your name", "Enter keeps default  Esc returns"
            elif self.stage == "briefing":
                all_lines = wrapped(content.text[f"wake-briefing-{self.screen}"].body, layout.briefing.width)
                count = layout.briefing.rows
                pages = max(1, (len(all_lines) + count - 1) // count)
                self.page = min(self.page, pages - 1)
                lines = all_lines[self.page * count:(self.page + 1) * count]
                title = f"VANTONGEREN - Briefing {self.screen}/3 ({self.page + 1}/{pages})"
                hint = "Any key continues  S skips to cards  Esc/B leaves"
            else:
                title, lines, hint = "THE WAKE", ["You wait for the record to settle."], "Saving your place."
            body = {"title": title, "lines": lines, "page": 1, "pages": 1, "hint": hint, "clear_prompt": self.stage != "name"}
        if self.error and self.stage != "name":
            body["hint"] = self.error
        return {"kind": kind, "body": body, "stage": self.stage, "hint": body["hint"]}

    def advance_briefing(self, content: ContentTree, width: int, height: int, key: str) -> None:
        if key.lower() == "s":
            self.stage, self.cursor = "card", len(content.wake_cards)
            return
        layout = screen_layout(width, height)
        all_lines = wrapped(content.text[f"wake-briefing-{self.screen}"].body, layout.briefing.width)
        count = layout.briefing.rows
        self.page += 1
        if self.page * count >= len(all_lines):
            self.screen, self.page = self.screen + 1, 0
            if self.screen > 3:
                self.stage, self.cursor = "card", len(content.wake_cards)
