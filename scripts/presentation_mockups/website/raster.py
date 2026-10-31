"""Rasterize a cell grid [[ch, fg, bg, bold], ...] the way a good terminal
draws it: box lines joined edge to edge, block and sextant cells filled,
text in a monospace font. From the #68 target script, scaled for the web."""
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

EIGHTHS = " ▏▎▍▌▋▊▉█"
BOX = set("─│┌┐└┘═║╔╗╚╝╟╢╤┴┬├┤╧╪")


def _font(paths, size):
    for path in paths:
        if path and Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def clamp(c):
    return tuple(max(0, min(255, int(round(v)))) for v in c)


def render(grid, path, cw=16, ch=32, glow=None):
    """glow: optional list of (x, y, colour, radius_cells, strength) bloom
    sources, drawn under the text as a soft additive light."""
    h, w = len(grid), len(grid[0])
    mono = _font([os.environ.get("MOCKUP_FONT", ""), "C:/Windows/Fonts/consola.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"], int(ch * 0.82))
    monob = _font(["C:/Windows/Fonts/consolab.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"],
                  int(ch * 0.82))
    sym = _font(["C:/Windows/Fonts/seguisym.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"], int(ch * 0.74))
    img = Image.new("RGB", (w * cw, h * ch), (0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = max(2, cw // 6)
    off = max(3, cw // 4)

    def block(x0, y0, c, fg):
        o = ord(c)
        if c == "█":
            d.rectangle([x0, y0, x0 + cw - 1, y0 + ch - 1], fill=fg)
        elif c == "▌":
            d.rectangle([x0, y0, x0 + cw // 2 - 1, y0 + ch - 1], fill=fg)
        elif c == "▐":
            d.rectangle([x0 + cw // 2, y0, x0 + cw - 1, y0 + ch - 1], fill=fg)
        elif c == "▀":
            d.rectangle([x0, y0, x0 + cw - 1, y0 + ch // 2 - 1], fill=fg)
        elif c == "▄":
            d.rectangle([x0, y0 + ch // 2, x0 + cw - 1, y0 + ch - 1], fill=fg)
        elif c in EIGHTHS[1:8]:
            d.rectangle([x0, y0, x0 + int(round(cw * EIGHTHS.index(c) / 8)) - 1, y0 + ch - 1], fill=fg)
        elif c in "░▒▓":
            k = {"░": 4, "▒": 2, "▓": 1}[c]
            step = max(2, cw // 6)
            for yy in range(y0, y0 + ch, step):
                for xx in range(x0 + ((yy - y0) // step % 2) * step, x0 + cw, step * (2 if k > 1 else 1)):
                    if k == 4 and (xx // step + yy // step) % 2:
                        continue
                    d.rectangle([xx, yy, xx + step - 1, yy + step - 1], fill=fg)
        elif 0x1FB00 <= o <= 0x1FB3B:
            n = o - 0x1FB00 + 1
            n += (n >= 21) + (n + (n >= 21) >= 42)
            for bit in range(6):
                if n >> bit & 1:
                    r, cc = divmod(bit, 2)
                    d.rectangle([x0 + cc * cw // 2, y0 + r * ch // 3, x0 + (cc + 1) * cw // 2 - 1,
                                 y0 + (r + 1) * ch // 3 - 1], fill=fg)
        else:
            return False
        return True

    def line(x0, y0, c, fg):
        mx, my = x0 + cw // 2, y0 + ch // 2
        double = c in "═║╔╗╚╝"
        spec = {"─": "lr", "│": "ud", "┌": "rd", "┐": "ld", "└": "ru", "┘": "lu", "═": "lr", "║": "ud",
                "╔": "rd", "╗": "ld", "╚": "ru", "╝": "lu", "╟": "udr", "╢": "udl", "╤": "lrd", "┴": "lru",
                "┬": "lrd", "├": "udr", "┤": "udl", "╧": "lru", "╪": "lrud"}[c]
        for o in ((-off, off) if double else (0,)):
            if "l" in spec:
                d.line([x0, my + o, mx, my + o], fill=fg, width=lw)
            if "r" in spec:
                d.line([mx, my + o, x0 + cw - 1, my + o], fill=fg, width=lw)
            if "u" in spec:
                d.line([mx + o, y0, mx + o, my], fill=fg, width=lw)
            if "d" in spec:
                d.line([mx + o, my, mx + o, y0 + ch - 1], fill=fg, width=lw)
        if c in "╟╢":
            d.line([mx - off, y0, mx - off, y0 + ch - 1], fill=fg, width=lw)
            d.line([mx + off, y0, mx + off, y0 + ch - 1], fill=fg, width=lw)
            side = (mx + off, x0 + cw - 1) if c == "╟" else (x0, mx - off)
            d.line([side[0], my, side[1], my], fill=fg, width=lw)
        if c in "╤╧":
            d.line([x0, my - off, x0 + cw - 1, my - off], fill=fg, width=lw)
            d.line([x0, my + off, x0 + cw - 1, my + off], fill=fg, width=lw)
            d.line([mx, my + off if c == "╤" else y0, mx, y0 + ch - 1 if c == "╤" else my - off], fill=fg, width=lw)

    for y in range(h):
        for x in range(w):
            d.rectangle([x * cw, y * ch, x * cw + cw - 1, y * ch + ch - 1], fill=clamp(grid[y][x][2]))
    if glow:
        from PIL import ImageFilter, ImageChops
        layer = Image.new("RGB", img.size, (0, 0, 0))
        gd = ImageDraw.Draw(layer)
        for gx, gy, col, rad, k in glow:
            cx, cy, r = (gx + 0.5) * cw, (gy + 0.5) * ch, rad * cw
            gd.ellipse([cx - r, cy - r * 0.8, cx + r, cy + r * 0.8], fill=clamp(tuple(v * k for v in col)))
        layer = layer.filter(ImageFilter.GaussianBlur(cw * 1.2))
        img = ImageChops.add(img, layer)
        d = ImageDraw.Draw(img)
    for y in range(h):
        for x in range(w):
            c, fg, bg, bold = grid[y][x]
            x0, y0 = x * cw, y * ch
            fg = clamp(fg)
            if c in ("", " ") or block(x0, y0, c, fg):
                continue
            if c in BOX:
                line(x0, y0, c, fg)
                continue
            f = monob if bold else mono
            if ord(c) > 0x2000 and c not in "·":
                f = sym if not mono.getmask(c).getbbox() or c in "→↑↓←↗↘↙↖◆♦☻☺‼√" else f
            d.text((x0 + cw / 2, y0 + ch / 2), c, font=f, fill=fg, anchor="mm")
    img.save(path)
    return img.size
