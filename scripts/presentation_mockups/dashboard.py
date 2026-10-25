"""One 132x50 'dashboard' frame of Sodium Row, from real game state.

    python scripts/presentation_mockups/dashboard.py STAND_IN_ART.png [out_dir]

The vignette is a stand-in image converted to half-block cells (two
vertical pixels per cell, `▀` with separate fg/bg). Every other cell comes
from the live ZoneView body, the zone and NPC content, the character
record, and presentation.json. Panels that need view fields the server
does not send yet (activity, direction, standing) read the server's own
state here and are named as proposed fields in the brief.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import build  # noqa: E402  (sets sys.path for the game and tests)
import proto  # noqa: E402
from blacksite.door.cells import CellBuffer, display_width, truncate  # noqa: E402
from blacksite.door.layout import Layout, Rect  # noqa: E402
from blacksite.door.palette import Style  # noqa: E402
from tests.character_helpers import place  # noqa: E402

W, H = 132, 50
SIDE = 44                       # right column width
DIV = W - SIDE - 2              # divider column (86)
LEFT = DIV - 1                  # left content width (85)
ART_ROWS, MAP_TOP, MAP_ROWS = 14, 20, 17
SEP, FEED_TOP, FEED_ROWS, HINT = 37, 38, 10, 48
BASE16 = [(0, 0, 0), (170, 0, 0), (0, 170, 0), (170, 85, 0), (0, 0, 170), (170, 0, 170), (0, 170, 170), (170, 170, 170),
          (85, 85, 85), (255, 85, 85), (85, 255, 85), (255, 255, 85), (85, 85, 255), (255, 85, 255), (85, 255, 255), (255, 255, 255)]


def nearest(rgb, choices, table, cache={}):
    key = (rgb, len(choices))
    if key not in cache:
        cache[key] = min(choices, key=lambda i: sum((a - b) ** 2 for a, b in zip(table[i], rgb)))
    return cache[key]


def pixel_style(top, bottom, tier):
    if tier == "truecolor":
        return "▀", Style(top, bottom, (), tier)
    if tier == "256":
        return "▀", Style(nearest(top, range(16, 256), proto.XTERM), nearest(bottom, range(16, 256), proto.XTERM), (), tier)
    luma = lambda c: 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    hi, lo, glyph = (top, bottom, "▀") if luma(top) >= luma(bottom) else (bottom, top, "▄")
    return glyph, Style(nearest(hi, range(16), BASE16), nearest(lo, range(8), BASE16), (), "16")


def vignette(buf, paint, tier, art_path, overlays):
    from PIL import Image
    img = Image.open(art_path).convert("RGB")
    w, h = img.size
    want = h - int(w * 2 * ART_ROWS / LEFT)          # crop height to the strip's aspect
    img = img.crop((0, want // 2, w, h - want // 2)).resize((LEFT, ART_ROWS * 2), Image.LANCZOS)
    px = img.load()
    for y in range(ART_ROWS):
        for x in range(LEFT):
            glyph, style = pixel_style(px[x, 2 * y], px[x, 2 * y + 1], tier)
            buf.put(1 + x, 1 + y, glyph, style)
    # Words never survive as pixels: signs are real characters over the art.
    for x, y, text, role in overlays:
        for i, ch in enumerate(text):
            r, g, b = px[x + i, 2 * y]
            dark = (r // 3, g // 3, b // 3)
            bg = dark if tier == "truecolor" else nearest(dark, range(16, 256), proto.XTERM) if tier == "256" else 0
            fg = paint.value(role)
            buf.put(1 + x + i, 1 + y, ch, Style(fg, bg, (1,) if tier != "16" else (), tier))
    label = " stand-in art, not canon "
    buf.put(1 + LEFT - len(label) - 1, ART_ROWS, label, paint("art_label"))


def district_map(buf, scene, art, grid, objects, me_xy, top):
    """Schematic of the district, scaled from the zone map: you, anchors, exits, neighbours."""
    paint, x0 = scene.paint, DIV + 2
    title(buf, scene, DIV + 1, top, "DISTRICT", "Sodium Row", "M")
    bx, by, bw, bh = x0 + 1, top + 4, 38, 7            # street box on screen
    zw, zh = len(grid[0]), len(grid)
    sx = lambda zx: bx + 1 + round(zx * (bw - 3) / (zw - 1))
    sy = lambda zy: by + 1 + round(zy * (bh - 3) / (zh - 1))
    buf.put(x0, top + 1, "MERIDIAN PLAZA", paint("text"))
    buf.put(x0 + 15, top + 1, "safe", paint("word_safe"))
    buf.put(x0 + 1, top + 2, "│ the Neon Stair", paint("map_box"))
    buf.put(x0 + 1, top + 3, "│", paint("map_box"))
    buf.put(bx, by, "┌" + "─" * (bw - 2) + "┐", paint("map_box"))
    for row in range(by + 1, by + bh - 1):
        buf.put(bx, row, "│", paint("map_box"))
        buf.put(bx + 1, row, " " * (bw - 2), paint("text", "map_street"))
        buf.put(bx + bw - 1, row, "│", paint("map_box"))
    buf.put(bx, by + bh - 1, "└" + "─" * (bw - 2) + "┘", paint("map_box"))
    buf.put(bx + 2, by, " SODIUM ROW ", paint("strong", bold=True))
    buf.put(bx + 15, by, "contested ", paint("word_contested"))
    buf.put(bx + 1, by - 1, "»", paint("thing_exit", bold=True))
    marks = {"vendor": ("$", "thing_vendor"), "terminal": ("§", "thing_terminal"), "light": ("☼", "thing_light")}
    for o in objects:
        if o["kind"] in marks:
            glyph, role = marks[o["kind"]]
            buf.put(sx(o["tile"][0]), sy(o["tile"][1]), glyph, paint(role, "map_street", bold=True))
    hx, hy = sx(94), sy(26)
    buf.put(hx, hy, "+", paint("thing_door", "map_street", bold=True))
    buf.put(sx(me_xy[0]), sy(me_xy[1]), "@", paint("self_fg", "self_bg", bold=True))
    buf.put(bx + bw - 6, by + bh - 1, "┬", paint("map_box"))
    buf.put(bx + bw - 6, by + bh, "│", paint("map_box"))
    buf.put(bx + bw - 16, by + bh + 1, "THE TIN HALO", paint("text"))
    buf.put(bx + bw - 3, by + bh + 1, "pocket", paint("word_pocket"))
    buf.put(bx + bw - 3, by + 1, "", paint("text"))
    buf.put(x0 + 1, by + bh + 1, "OLD WORKS", paint("dim"))
    buf.put(x0 + 11, by + bh + 1, "closed", paint("dim"))
    buf.put(x0, top + 13, "@ you  $ bar  § terminal  ☼ stage  + door", paint("label"))


def title(buf, scene, x, y, name, sub="", key=""):
    paint = scene.paint
    width = (W - 1 - x) if x > 1 else LEFT
    buf.put(x, y, "─" * width, paint("rule"))
    buf.put(x + 1, y, f" {name} ", paint("panel_title", bold=True))
    if sub:
        buf.put(x + 3 + len(name), y, f"// {sub} ", paint("label"))
    if key:
        buf.put(x + width - len(key) - 4, y, f" [{key}] ", paint("label"))


def compass(dx, dy):
    ns = "N" if dy < -1 else "S" if dy > 1 else ""
    ew = "W" if dx < -1 else "E" if dx > 1 else ""
    return (ns + ew) or "here"


def main() -> None:
    art_path = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else build.ROOT / "docs/design/proposals/68-presentation/mockups"
    out.mkdir(parents=True, exist_ok=True)
    zone_id = "sodium-row"
    grid = (build.CONTENT / "zones" / f"{zone_id}.map").read_text(encoding="utf-8").splitlines()
    objects = build.static_objects(zone_id)
    npcs = {n["name"]: n for n in json.loads((build.CONTENT / "npcs.json").read_text(encoding="utf-8"))["npcs"]}
    for tier in ("256", "truecolor", "16"):
        caller = build.Caller(W, H, tier)
        place(caller.game, caller.client, zone_id, (3, 3))  # the Neon Stair lands at the Row's west end
        caller.pump(4)
        caller.walk((20, 9))
        caller.pump(600)
        caller.walk((26, 8))
        body = caller.display.body
        me = body["me"]
        avatar = caller.avatar
        zone = caller.game.core.world.zones[zone_id]
        player = next(iter(caller.game.core.characters.players.values()))

        lay = Layout(W, H, Rect(1, MAP_TOP, LEFT, MAP_ROWS), Rect(DIV + 1, 1, SIDE, SEP - 1), SEP,
                     Rect(1, FEED_TOP, W - 2, FEED_ROWS), HINT)
        scene = proto.Scene(lay, proto.Paint(build.DATA, tier), build.DATA, tier)
        paint = scene.paint
        buf = CellBuffer(W, H, paint("text"))
        art = build.zone_art(zone_id)

        # Crop the server's viewport (sized for the 80-column layout) to the dashboard's map window.
        vp = body["viewport"]
        cx = max(0, min(vp["w"] - LEFT, avatar.actor.x - vp["x"] - LEFT // 2))
        cy = max(0, min(vp["h"] - MAP_ROWS, avatar.actor.y - vp["y"] - MAP_ROWS // 2))
        view = dict(body, viewport={"x": vp["x"] + cx, "y": vp["y"] + cy, "w": LEFT, "h": MAP_ROWS},
                    tiles=[row[cx:cx + LEFT] for row in body["tiles"][cy:cy + MAP_ROWS]],
                    remembered=[row[cx:cx + LEFT] for row in body["remembered"][cy:cy + MAP_ROWS]])
        actors = []
        for entry in body["actors"]:
            other = zone.actors.get(entry["id"])
            template = npcs.get(getattr(other, "name", ""), {})
            uniformed = any(b["kind"] == "guard" for b in template.get("behaviours", []))
            if entry["role"].startswith("npc_") and not uniformed:
                entry = dict(entry, role="npc_neutral")   # crowd and plainclothes read as crowd
            actors.append(entry)
        view["actors"] = actors
        proto.render_zone(buf, scene, view, art, objects)

        # Frame and column chrome.
        proto.frame(buf, scene, me["safety"],
                    [(" SODIUM ROW ", "head_district"), ("· ", "rule"), ("Sodium Row ", "head_zone"),
                     (" CONTESTED ", "word_contested"), (" PvP G5+ ", "head_info"), (" truce kept by Red Sable ", "label")],
                    [(" KARST ", "label"), (f" {me['clock']} ", "head_info"), ("Ring up ", "head_night")])
        style = paint("frame_contested")
        for y in range(1, SEP):
            buf.put(DIV, y, "│", style)
        buf.put(DIV, 0, "┬", style)
        buf.put(DIV, SEP, "┴", style)

        vignette(buf, paint, tier, art_path,
                 [(6, 3, "DRINKS", "sign_pink"), (37, 1, "LIVE MUSIC", "sign_cyan"), (73, 3, "TIN HAL", "sign_orange")])
        buf.put(73 + 1 + 7, 1 + 3, "O", Style(paint.value("sign_dead"), 0, (), tier))

        # Location block.
        title(buf, scene, 1, ART_ROWS + 1, "LOCATION", "SODIUM ROW » Sodium Row")
        text = (build.CONTENT / "text" / f"zone-{zone_id}.md").read_text(encoding="utf-8").split()
        line, row = "", ART_ROWS + 2
        for word in text:
            if display_width(line + " " + word) > LEFT - 2:
                buf.put(2, row, line, paint("log_place"))
                line, row = word, row + 1
            else:
                line = f"{line} {word}".strip()
        buf.put(2, row, line, paint("log_place"))
        ex = ART_ROWS + 4
        buf.put(2, ex, "Exits", paint("label"))
        buf.put(9, ex, "»", paint("thing_exit", bold=True))
        buf.put(11, ex, "W  the Neon Stair to Meridian Plaza", paint("text"))
        buf.put(49, ex, "+", paint("thing_door", bold=True))
        buf.put(51, ex, "SE  the Tin Halo", paint("text"))
        title(buf, scene, 1, MAP_TOP - 1, "STREET", "you are the white block", "")

        # Right column: district map, nearby, status.
        district_map(buf, scene, art, grid, objects, (avatar.actor.x, avatar.actor.y), 1)
        top = 15
        seen = [e for e in body["actors"] if e["role"] != "player_self"]
        title(buf, scene, DIV + 1, top, "NEARBY", f"{len(seen)} in sight", "Tab")
        rows = []
        for entry in seen:
            other = zone.actors[entry["id"]]
            template = npcs.get(getattr(other, "name", ""), {})
            kinds = [b["kind"] for b in template.get("behaviours", [])]
            uniformed = "guard" in kinds
            name = other.name if other.name != "Plainclothes Warden" else "Drinker"
            doing = "keeping the truce" if uniformed else "talking" if "talker" in kinds else "drifting"
            role = proto.actor_role({"role": entry["role"] if uniformed else "npc_neutral"}, False)
            dist = abs(other.x - avatar.actor.x) + abs(other.y - avatar.actor.y)
            rows.append((dist, name, role, ("Red Sable" if uniformed else ""), doing, compass(other.x - avatar.actor.x, other.y - avatar.actor.y)))
        for i, (dist, name, role, tag, doing, where) in enumerate(sorted(rows)[:7]):
            y = top + 1 + i
            buf.put(DIV + 2, y, "☻", paint(role, bold=True))
            buf.put(DIV + 4, y, truncate(name, 15), paint("text"))
            buf.put(DIV + 20, y, truncate(tag or doing, 17), paint(role if tag else "label"))
            buf.put(W - 6, y, where.rjust(4), paint("label"))
        top = 24
        title(buf, scene, DIV + 1, top, "STATUS", f"{me['name']} · {me['handle']}", "P")
        x = DIV + 2
        proto.bar(buf, scene, x, top + 1, "HP", me["hp"], me["hp_max"], "bar_hp", f"{me['hp']}/{me['hp_max']}", width=20)
        proto.bar(buf, scene, x, top + 2, "STA", me["sta"], me["sta_max"], "bar_sta", f"{me['sta']}/{me['sta_max']}", width=20)
        proto.bar(buf, scene, x, top + 3, "SHK", me["shock"], 100, "bar_shock", f"{me['shock']:g}", width=20)
        buf.put(x, top + 4, "Chits", paint("label"))
        buf.put(x + 7, top + 4, f"{me['chits']}", paint("thing_vendor", bold=True))
        buf.put(x + 14, top + 4, f"Grade {me['grade']}", paint("text"))
        buf.put(x + 24, top + 4, f"Lease {me['lease_days']}/90 d", paint("label"))
        buf.put(x, top + 5, "Standing", paint("label"))
        standing = sorted(player.standing.items(), key=lambda kv: -abs(kv[1]))[:3] or [("freelance", 0)]
        for i, (faction, value) in enumerate(standing):
            y = top + 6 + i
            buf.put(x + 2, y, faction.title(), paint("text"))
            buf.put(x + 14, y, f"{value:+d}", paint("standing_pos" if value >= 0 else "standing_neg"))
            filled = min(16, abs(value) // 5)
            buf.put(x + 20, y, "█" * filled + "░" * (16 - filled), paint("standing_pos" if value >= 0 else "standing_neg"))
        buf.put(x, top + 10, "Lattice", paint("label"))
        buf.put(x + 9, top + 10, "3 public terminals on the Row", paint("thing_terminal"))
        buf.put(x, top + 11, "Lead", paint("label"))
        buf.put(x + 9, top + 11, "Vesper's card: the Tin Halo", paint("text"))

        # World feed: time, channel, line, place.
        buf.put(0, SEP, "├" + "─" * (W - 2) + "┤", style)
        buf.put(DIV, SEP, "┴", style)
        buf.put(2, SEP, " FEED ", paint("panel_title", bold=True))
        buf.put(9, SEP, "// all  local  crew  faction  system ", paint("label"))
        clock = me["clock"]
        feed = [("zone", "place", "Meridian Plaza. The Ring hangs over it like a chandelier nobody turned off.", "Meridian Plaza"),
                ("zone", "ambient", "Tram bells from the hub. The fountain hisses.", "Meridian Plaza"),
                ("zone", "place", "You take the Neon Stair down. The air turns orange.", "Neon Stair"),
                ("zone", "place", "Sodium Row. Orange lamps, wet pavement, music from six doorways at once.", "Sodium Row"),
                ("zone", "ambient", "Somebody at the card table laughs too loudly, then stops.", "Sodium Row"),
                ("say", "speech", "Sodium regular: Nobody draws on the Row. Not even you.", "Sodium Row"),
                ("sys", "system", "Vesper's card is in your pocket. The Tin Halo is at the street's end.", "Sodium Row"),
                ("zone", "danger", "Contested street. Callers of grade 5 and up can fight here. Sable ends fights.", "Sodium Row")]
        for i, (channel, kind, text, where) in enumerate(feed[-FEED_ROWS:]):
            y = FEED_TOP + i
            buf.put(2, y, clock, paint("feed_time"))
            buf.put(8, y, channel.ljust(5), paint("label"))
            if kind == "speech":
                who, said = text.split(": ", 1)
                buf.put(14, y, who + ":", paint("log_speaker"))
                buf.put(16 + len(who), y, said, paint("log_speech"))
            else:
                buf.put(14, y, truncate(text, W - 34), paint("log_" + kind))
            buf.put(W - 2 - len(where), y, where, paint("feed_loc"))
        proto.hints(buf, scene, [("E", "interact"), ("Tab", "target"), ("F", "fire"), ("I", "inventory"), ("P", "character"),
                                  ("M", "map"), ("Q", "contracts"), ("J", "jack in"), ("C", "chat"), ("?", "help")])
        build.emit(out, f"dashboard-sodium-row-{W}x{H}-{tier}", buf.full(), W, H)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
