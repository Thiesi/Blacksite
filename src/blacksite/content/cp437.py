"""The CP437 glyph table, graphic form.

Python's `cp437` codec maps bytes 0x01-0x1F and 0x7F to control
characters, but terminals in CP437 mode (SyncTERM and its kin) draw them
as the familiar smileys, card suits, and arrows. The glyph registry
(03-terminal-ui.md section 1) is restricted to characters that exist in
CP437 as drawn, so this module rebuilds that table: the codec for
0x20-0x7E and 0x80-0xFF, the graphic set for the rest.
"""

from typing import Final

# Graphic forms of 0x00-0x1F, in byte order (0x00 has no glyph).
_LOW: Final[str] = (
    "\u0000☺☻♥♦♣♠•◘○◙♂♀♪♫☼"
    "►◄↕‼¶§▬↨↑↓→←∟↔▲▼"
)
_DEL: Final[str] = "⌂"


def _build() -> dict[str, int]:
    table: dict[str, int] = {}
    for code, char in enumerate(_LOW):
        if code:
            table[char] = code
    for code in range(0x20, 0x7F):
        table[chr(code)] = code
    table[_DEL] = 0x7F
    for code in range(0x80, 0x100):
        table[bytes([code]).decode("cp437")] = code
    return table


CP437_GRAPHIC: Final[dict[str, int]] = _build()


def in_cp437(char: str) -> bool:
    """Whether a single character has a CP437 glyph."""
    return char in CP437_GRAPHIC


def round_trips(char: str) -> bool:
    """Whether a character encodes to one CP437 byte and decodes back."""
    code = CP437_GRAPHIC.get(char)
    if code is None:
        return False
    if code < 0x20:
        return _LOW[code] == char
    if code == 0x7F:
        return char == _DEL
    return bytes([code]).decode("cp437") == char
