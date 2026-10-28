"""Optional PNG of a FakeTerminal grid (needs Pillow and a monospace font)."""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE16 = [(0, 0, 0), (170, 0, 0), (0, 170, 0), (170, 85, 0), (0, 0, 170), (170, 0, 170), (0, 170, 170), (170, 170, 170),
          (85, 85, 85), (255, 85, 85), (85, 255, 85), (255, 255, 85), (85, 85, 255), (255, 85, 255), (85, 255, 255), (255, 255, 255)]
FONTS = [os.environ.get("MOCKUP_FONT", ""), "C:/Windows/Fonts/consola.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/System/Library/Fonts/Menlo.ttc"]
FALLBACK = ["C:/Windows/Fonts/seguisym.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _font(paths: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in paths:
        if path and Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


FONT, SYMBOLS = _font(FONTS, 16), _font(FALLBACK, 15)


def xterm(n: int) -> tuple[int, int, int]:
    if n < 16:
        return BASE16[n]
    if n < 232:
        n -= 16
        steps = [0, 95, 135, 175, 215, 255]
        return steps[n // 36], steps[n // 6 % 6], steps[n % 6]
    grey = 8 + (n - 232) * 10
    return grey, grey, grey


def colours(sgr: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    fg, bg, bold, dim, reverse = BASE16[7], BASE16[0], False, False, False
    codes = [int(c) for c in sgr.split(";") if c.isdigit()] or [0]
    i = 0
    while i < len(codes):
        c = codes[i]
        if c == 0:
            fg, bg, bold, dim, reverse = BASE16[7], BASE16[0], False, False, False
        elif c == 1:
            bold = True
        elif c == 2:
            dim = True
        elif c == 7:
            reverse = True
        elif 30 <= c <= 37:
            fg = BASE16[c - 30]
        elif 40 <= c <= 47:
            bg = BASE16[c - 40]
        elif 100 <= c <= 107:
            bg = BASE16[c - 92]
        elif c in (38, 48):
            if codes[i + 1] == 5:
                value, i = xterm(codes[i + 2]), i + 2
            else:
                value, i = tuple(codes[i + 2:i + 5]), i + 4
            if c == 38:
                fg = value
            else:
                bg = value
        i += 1
    if bold and fg in BASE16[:8]:
        fg = BASE16[BASE16.index(fg) + 8]  # 16-colour tier: bold is bright
    if dim:
        fg = tuple(v // 2 for v in fg)
    return (bg, fg) if reverse else (fg, bg)


def png(term, path: Path, cell: tuple[int, int] = (9, 18)) -> None:
    cw, ch = cell
    font_main, font_symbols = (FONT, SYMBOLS) if cell == (9, 18) else (_font(FONTS, ch * 5 // 6), _font(FALLBACK, ch * 3 // 4))
    image = Image.new("RGB", (term.width * cw, term.height * ch))
    draw = ImageDraw.Draw(image)
    for y in range(term.height):
        for x in range(term.width):
            glyph = term.grid[y][x]
            fg, bg = colours(term.styles.get((x, y), "0"))
            draw.rectangle([x * cw, y * ch, x * cw + cw - 1, y * ch + ch - 1], fill=bg)
            # Terminals draw block elements cell-filling; fonts often leave gaps.
            blocks = {"▀": (0, 0, 1, 0.5), "▄": (0, 0.5, 1, 1), "█": (0, 0, 1, 1), "▌": (0, 0, 0.5, 1), "▐": (0.5, 0, 1, 1)}
            if glyph in blocks:
                l, t, r, b = blocks[glyph]
                draw.rectangle([x * cw + l * cw, y * ch + t * ch, x * cw + r * cw - 1, y * ch + b * ch - 1], fill=fg)
            elif glyph and 0x1FB00 <= ord(glyph) <= 0x1FB3B:  # sextants: 2x3, bit 0 top left
                pattern = ord(glyph) - 0x1FB00 + 1
                pattern += pattern >= 21
                pattern += pattern >= 42
                for bit in range(6):
                    if pattern >> bit & 1:
                        r, c = divmod(bit, 2)
                        draw.rectangle([x * cw + c * cw // 2, y * ch + r * ch // 3,
                                        x * cw + (c + 1) * cw // 2 - 1, y * ch + (r + 1) * ch // 3 - 1], fill=fg)
            elif glyph and glyph != " ":
                font = font_main if font_main.getmask(glyph).getbbox() else font_symbols
                draw.text((x * cw, y * ch), glyph, font=font, fill=fg)
    image.save(path)
