"""Pure shared geometry: architecture 5.5.1 and terminal UI 2.

Page metrics preserve existing wrapping and page counts. They describe
legacy pagination policies, separately from drawable rectangles.
"""

from dataclasses import dataclass
from typing import Literal

LayoutTier = Literal["current"]
MIN_LOG_WIDTH = 4  # Terminal UI 6: two continuation cells plus a two-cell glyph.


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class Page:
    width: int
    rows: int


@dataclass(frozen=True)
class MenuLayout:
    columns: Rect
    listing: Rect
    detail: Rect
    actions: Rect
    cursor_page: int


@dataclass(frozen=True)
class HeaderLayout:
    zone_title: Rect
    lattice_title: Rect
    clock: Rect
    heat: Rect
    safety_right: int
    heat_safety_right: int
    service_right: int
    handle_width: int


@dataclass(frozen=True)
class Layout:
    width: int
    height: int
    tier: LayoutTier
    frame: Rect
    header: Rect
    header_slots: HeaderLayout
    viewport: Rect
    side: Rect
    divider: Rect
    separator: Rect
    log: Rect
    hint: Rect
    text_area: Rect
    overlay: Rect
    wide: bool
    menu: MenuLayout
    contract_menu: MenuLayout
    briefing: Page
    city: Page
    contracts: Page
    wake_detail_width: int
    encounter_width: int
    private_core_width: int

    def menu_for(self, contracts: bool = False) -> MenuLayout:
        return self.contract_menu if contracts else self.menu


def compute(width: int, height: int, tier: LayoutTier = "current") -> Layout:
    if tier != "current":
        raise ValueError("unknown layout tier")
    if width < 80 or height < 24:
        raise ValueError("Blacksite needs an ANSI UTF-8 terminal of at least 80x24.")
    logs = min(8, 3 + (height - 24) * 5 // 16)
    viewport = Rect(1, 1, width - 25, height - 4 - logs)
    side = Rect(width - 23, 1, 22, viewport.height)
    wide = width >= 100
    menu_width = min(width - 6, 110 if wide else 70)
    menu_height = min(20 if height == 24 else height - 6, viewport.height)
    overlay = Rect((width - menu_width) // 2,
                   1 + (viewport.height - menu_height) // 2, menu_width, menu_height)
    list_width = (menu_width - 5) // 2 if wide else menu_width - 4
    detail_x = overlay.x + list_width + 3 if wide else overlay.x + 2
    detail_y = overlay.y + 1 if wide else overlay.y + max(3, menu_height - 6)
    detail_width = menu_width - list_width - 5 if wide else menu_width - 4
    detail = Rect(detail_x, detail_y, detail_width, max(0, overlay.bottom - 2 - detail_y))
    columns = Rect(overlay.x + 2, overlay.y + 1, list_width, 1)
    actions = Rect(overlay.x + 2, overlay.bottom - 2, menu_width - 4, 1)
    cursor_page = max(1, menu_height - (5 if wide else 9))
    menu = MenuLayout(columns, Rect(overlay.x + 2, overlay.y + 2, list_width,
                                   menu_height - (5 if wide else 8)),
                      detail, actions, cursor_page)
    contract_menu = menu if wide else MenuLayout(columns,
        Rect(overlay.x + 2, overlay.y + 2, list_width, 1),
        Rect(overlay.x + 2, overlay.y + 4, detail_width, max(0, menu_height - 6)),
        actions, cursor_page)
    return Layout(
        width=width, height=height, tier=tier, frame=Rect(0, 0, width, height),
        header=Rect(2, 0, width - 8, 1),
        header_slots=HeaderLayout(Rect(2, 0, width - 18, 1), Rect(2, 0, width - 6, 1),
            Rect(width - 8, 0, 5, 1), Rect(width - 14, 0, 4, 1),
            width - 10, width - 16, width - 16, width - 20),
        viewport=viewport, side=side, divider=Rect(side.x - 1, 1, 1, viewport.height),
        separator=Rect(0, viewport.bottom, width, 1),
        log=Rect(1, viewport.bottom + 1, width - 2, logs),
        hint=Rect(1, height - 2, width - 2, 1),
        text_area=Rect(viewport.x + 1, viewport.y + 1, viewport.width - 2, viewport.height - 2),
        overlay=overlay, wide=wide, menu=menu, contract_menu=contract_menu,
        briefing=Page(width - 29, max(1, viewport.height - 3)),
        city=Page(width - 28, max(1, height - 10)),
        contracts=Page(50 if wide else 66, max(1, menu_height - 6) + (3 if wide else 0)),
        wake_detail_width=(min(width - 6, 110) - 5) // 2 if wide else min(width - 10, 66),
        encounter_width=max(20, width // 2 - 12 if wide else width - 16),
        private_core_width=52 if wide else 66)
