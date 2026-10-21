"""Exact terminal UI §2 geometry; the sketch is not a sizing algorithm."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Layout:
    width: int
    height: int
    viewport: Rect
    side: Rect
    separator: int
    log: Rect
    hint: int


def compute(width: int, height: int) -> Layout:
    if width < 80 or height < 24:
        raise ValueError("Blacksite needs an ANSI UTF-8 terminal of at least 80x24.")
    logs = min(8, 3 + (height - 24) * 5 // 16)
    view_width, view_height = width - 25, height - 4 - logs
    return Layout(width, height, Rect(1, 1, view_width, view_height),
                  Rect(width - 23, 1, 22, view_height), view_height + 1,
                  Rect(1, view_height + 2, width - 2, logs), height - 2)
