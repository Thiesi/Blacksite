"""Server-owned Wake screens and input state; game design 4 / UI 7."""

from copy import deepcopy
from dataclasses import dataclass, field
import textwrap
from typing import Any

from karst41.layout import compute as screen_layout
from karst41.content.loader import ContentTree
from karst41.server.rules.character import ARCHETYPES, default_name, gurney_name


def wrapped(text: str, width: int) -> list[str]:
    return [line for paragraph in text.split("\n\n") for line in [*textwrap.wrap(paragraph.replace("\n", " "), max(12, width)), ""]]


def pages(lines: list[str], count: int) -> list[list[str]]:
    """Pages of at most `count` rows, filled by whole paragraphs (#216).

    A paragraph moves to the next page rather than break mid-sentence,
    unless it alone is longer than a page. No page starts with, ends with
    or is only blank lines.
    """
    paragraphs: list[list[str]] = [[]]
    for line in lines:
        if line.strip():
            paragraphs[-1].append(line)
        elif paragraphs[-1]:
            paragraphs.append([])
    result: list[list[str]] = [[]]
    for paragraph in (p for p in paragraphs if p):
        need = len(paragraph) + (1 if result[-1] else 0)
        if result[-1] and len(result[-1]) + need > count:
            result.append([])
        if result[-1]:
            result[-1].append("")
        for line in paragraph:
            if len(result[-1]) == count:
                result.append([])
            result[-1].append(line)
    return result


def briefing(content: ContentTree, screen: int, width: int, height: int) -> list[list[str]]:
    layout = screen_layout(width, height)
    return pages(wrapped(content.text[f"wake-briefing-{screen}"].body, layout.briefing.width), layout.briefing.rows)


def cards(content: ContentTree, cursor: int, width: int, height: int) -> dict[str, Any]:
    """The recruiter cards at the Wake Hall table (S48: taken at the table)."""
    detail_width = screen_layout(width, height).wake_detail_width
    deck = list(content.wake_cards.values())
    rows = [{"id": card.id, "cells": [card.name]} for card in deck] + [{"id": "none", "cells": ["Take no card"]}]
    cursor = min(cursor, len(rows) - 1)
    detail = content.text[deck[cursor].pitch].body if cursor < len(deck) else "You leave the cards. No standing changes."
    return menu("THE WAKE - Recruiter cards", rows, cursor, "\n".join(wrapped(detail, detail_width)),
                "Enter takes card  Esc/B puts them down")


# S48 (#220): the stages that show a menu over the hall; `hall` is play.
MENU_STAGES = ("record", "name", "saving")
SAVED = ("stage", "archetype", "name", "cursor", "screen", "page", "serial", "card", "lessons", "met", "tile", "source")


def menu(title: str, rows: list[dict[str, Any]], cursor: int, detail: str, hint: str = "Enter selects") -> dict[str, Any]:
    return {"title": title, "kind": "select", "columns": ["Choice"], "rows": rows,
            "cursor": cursor, "actions": [{"key": "enter", "label": "select"}],
            "page": 1, "pages": 1, "detail": detail, "hint": hint, "clear_prompt": True}


@dataclass
class Wake:
    stage: str = "hall"
    archetype: str = "hardline"
    name: str = ""
    cursor: int = 0
    screen: int = 1
    page: int = 0
    error: str = ""
    dirty: bool = True
    prompt_id: str = ""

    serial: int = 0
    card: str | None = None
    lessons: dict[str, Any] = field(default_factory=dict)
    met: list[str] = field(default_factory=list)
    tile: list[int] | None = None
    source: str = ""

    @classmethod
    def restore(cls, value: dict[str, Any]) -> "Wake":
        wake = cls(**{key: deepcopy(value[key]) for key in SAVED if key in value})
        # A Wake saved in a menu resumes in the hall; the record only opens
        # on a key the caller presses (technical lead, S48c1).
        if wake.stage != "hall":
            wake.stage = "hall"
        return wake

    def saved(self) -> dict[str, Any]:
        return {key: deepcopy(getattr(self, key)) for key in SAVED}

    def body(self, content: ContentTree, handle: str, width: int, height: int) -> dict[str, Any]:
        layout = screen_layout(width, height)
        detail_width = layout.wake_detail_width
        if self.stage == "record":
            # The decant record: the caller reads their own template (#220 beat 9).
            rows = [{"id": slug, "cells": [slug.title()]} for slug, _ in ARCHETYPES]
            slug = rows[self.cursor]["id"]
            detail = "\n".join(wrapped(content.text["wake-archetype-" + slug].body, detail_width))
            body = menu(f"DECANT RECORD - {gurney_name(self.serial)} - Template", rows, self.cursor, detail,
                        "Enter reads this one  Esc/B closes the record")
            kind = "menu"
        else:
            kind = "text"
            if self.stage == "name":
                lines = ["Your name is yours. Your BBS handle stays visible.", "",
                         "2-24 display columns: letters, digits, space, - _ '",
                         "Enter keeps: " + default_name(handle), self.error]
                title, hint = "THE WAKE - Choose your name", "Enter keeps default  Esc returns"
            elif self.stage == "briefing":
                book = briefing(content, self.screen, width, height)
                self.page = min(self.page, len(book) - 1)
                lines = book[self.page]
                title = f"VANTONGEREN - Briefing {self.screen}/3 ({self.page + 1}/{len(book)})"
                hint = "Any key continues  S skips to cards  Esc/B leaves"
            else:
                title, lines, hint = "THE WAKE", ["You wait for the record to settle."], "Saving your place."
            body = {"title": title, "lines": lines, "page": 1, "pages": 1, "hint": hint, "clear_prompt": self.stage != "name"}
            if self.stage == "briefing":
                body["flow"] = True  # Prose: a renderer may re-wrap each paragraph to its own width.
        if self.error and self.stage != "name":
            body["hint"] = self.error
        return {"kind": kind, "body": body, "stage": self.stage, "hint": body["hint"]}

    def advance_briefing(self, content: ContentTree, width: int, height: int, key: str) -> None:
        if key.lower() == "s":
            self.stage, self.cursor = "card", len(content.wake_cards)
            return
        self.page += 1
        if self.page >= len(briefing(content, self.screen, width, height)):
            self.screen, self.page = self.screen + 1, 0
            if self.screen > 3:
                self.stage, self.cursor = "card", len(content.wake_cards)
