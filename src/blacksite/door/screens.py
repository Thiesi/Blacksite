"""Local connection/help screens; no game state or game rules."""

from typing import Any


def title(motd: str = "") -> dict[str, Any]:
    return {"title": "BLACKSITE", "lines": ["", "The city was built to keep something in.",
        "Nobody remembers what.", "", "a real-time door for NetBBS   .   Karst, Year 41", "", motd,
        "", "? help    Ctrl-X leave"], "page": 1, "pages": 1}


def first_run() -> dict[str, Any]:
    return {"title": "WHAT THIS IS", "lines": [
        "You wake in Karst with a lease and no memories.",
        "Ninety days end the lease. Paid work can end it sooner.",
        "Other callers move through the same streets in real time.", "",
        "Fix a pump. Sell the record. Open a route for someone else.",
        "Street hardware and the Lattice control the same city.",
        "Read the safety label before you cross a boundary.",
        "Safe streets protect you. The outer rings do not.", "",
        "Death keeps your identity, skills and secured gear.",
        "Loose gear and carried chits can be lost. Debt can follow.",
        "Open your journal for objectives, costs and escape routes.",
        "You need no special words to use a terminal."], "page": 1, "pages": 1}


def help_pages(keymap: dict[str, Any]) -> list[str]:
    lines = ["Ctrl-X then Y leaves. Ctrl-L redraws. Esc/B returns.",
             "Menus show actions first. Select a row, then its action key.",
             "A menu never pauses the city.", "",
             "Arrows move; vi hjkl/yubn moves with the vi keymap.",
             "Vi j moves down. Ctrl-O jacks. Ctrl-F opens faction chat.",
             "Ctrl-P opens scrollback. Printable vi keys type in prompts.", ""]
    for mapping in keymap.get("keymaps", []):
        lines.append(str(mapping.get("label", mapping.get("id", "Keys"))))
        for action, keys in mapping.get("bindings", {}).items():
            label = keymap.get("actions", {}).get(action, {}).get("label", action)
            lines.append(f"{', '.join(keys)}  {label}")
        lines.append("")
    return lines


class SessionWarnings:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.sent: set[int] = set()

    def update(self, elapsed: float) -> list[str]:
        result = []
        for remaining in (300, 60):  # Architecture §8.2.
            if self.limit >= remaining and elapsed >= self.limit - remaining and remaining not in self.sent:
                self.sent.add(remaining)
                result.append(f"Your BBS session ends in {remaining // 60} minute(s).")
        return result
