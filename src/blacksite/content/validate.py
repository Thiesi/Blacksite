"""The content validator (01-entities.md section 5, 04-assets.md section 3).

`validate(tree)` returns every problem in a loaded tree: the loader's
parse problems first, then the cross-file invariants that need no
persistent state. An empty list means the tree may be served.

Run it from a shell::

    python -m blacksite.content.validate DIR [--local DIR]

which prints `ok, 3 zones, 1 sector, 2 cores, hash ...` and exits 0, or
prints one `path:line: message` per problem and exits 1.

Bundles (02-architecture.md section 15.3): content that no bundle lists
is base content and always active. A record in an `authoring` bundle is
checked for shape but its references may dangle; a record that is
active may reference only content that exists and is itself active.
"""

import argparse
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

from blacksite.content import schema as s
from blacksite.content.cp437 import round_trips
from blacksite.content.formats import Problem, find_line, id_needles
from blacksite.content.ids import display_width
from blacksite.content.loader import ContentTree, load_content

__all__ = ["Problem", "validate", "main"]

# 00-game-design.md section 5.1: zone width 40-200, height 20-100.
ZONE_WIDTH = (40, 200)
ZONE_HEIGHT = (20, 100)
# 00-game-design.md section 6.2: a core has 3 to 12 rooms, tier 1 to 5;
# 01-entities.md section 1.4: tier 0 only for the Wake training core.
CORE_ROOMS = (3, 12)
CORE_TIER = (1, 5)
TRAINING_TIER = 0
# 00-game-design.md section 17: item tiers 1-3, program and ICE 1-5.
ITEM_TIER = (1, 3)
LATTICE_TIER = (1, 5)
# 00-game-design.md section 6.4: ordinary controls reset in 5-30 minutes.
CONTROL_RESET_SECONDS = (300, 1800)
# 00-game-design.md sections 7.5 and 12: hazards warn at least 5 s ahead.
HAZARD_WARNING_SECONDS = 5
# 00-game-design.md section 13.2: balance is clamped to -3..+3.
BALANCE_RANGE = (-3, 3)
# 04-dramatis-personae.md Part III: no line exceeds 200 characters.
DIALOGUE_LINE_MAX = 200
# 01-gazetteer.md content notes: lat-shaft is the only core with two
# hardware locations, and the loader asserts it.
SHARED_HARDWARE_CORES = frozenset({"lat-shaft"})

# 03-terminal-ui.md section 1: the roles every palette must define.
REQUIRED_ROLES = frozenset({
    "wall", "floor", "cover", "water", "hazard",
    "player_self", "player_crew", "player_neutral", "player_hostile", "player_marked",
    "hp_ok", "hp_low", "hp_critical",
})

_CLOSING_ACTIONS = frozenset({"close", "disable", "toggle"})


def validate(tree: ContentTree) -> list[Problem]:
    """Every problem in `tree`, load problems first."""
    v = _Validator(tree)
    v.run()
    return list(tree.load_problems) + v.problems


class _Validator:
    def __init__(self, tree: ContentTree) -> None:
        self.t = tree
        self.problems: list[Problem] = []
        self.status: dict[tuple[str, str], str] = {}
        self.current_active = True

    # --- reporting -------------------------------------------------------

    def report(self, kind: str, record_id: str, message: str, needle: str | None = None) -> None:
        path = self.t.source(kind, record_id)
        text = self.t.texts.get(path, "")
        needles = (*(id_needles(needle) if needle else ()), *id_needles(record_id))
        self.problems.append(Problem(path, find_line(text, *needles) if text else None, message))

    # --- bundles and references -------------------------------------------

    def is_active(self, kind: str, record_id: str) -> bool:
        return self.status.get((kind, record_id), "active") == "active"

    def exists(self, kind: str, record_id: str) -> bool:
        return record_id in getattr(self.t, kind)

    def ref(self, kind: str, target: str | None, owner: tuple[str, str], what: str,
            needle: str | None = None) -> bool:
        """Check a reference from `owner` to `kind:target`.

        Returns whether the target exists. From active content a missing
        or authoring-only target is a problem; from authoring content
        neither is.
        """
        if target is None:
            return True
        found = self.exists(kind, target)
        if not self.current_active:
            return found
        if not found:
            self.report(*owner, f"{what}: {_KIND_NAMES.get(kind, kind)} {target!r} does not exist", needle)
        elif not self.is_active(kind, target):
            self.report(*owner, f"{what}: {_KIND_NAMES.get(kind, kind)} {target!r} is in an authoring bundle", needle)
        return found

    def each(self, kind: str) -> Iterator[tuple[str, object]]:
        for record_id, record in sorted(getattr(self.t, kind).items()):
            self.current_active = self.is_active(kind, record_id)
            yield record_id, record
        self.current_active = True

    # --- run ----------------------------------------------------------------

    def run(self) -> None:
        self.check_bundles()
        self.check_unique_catalog_ids()
        self.check_glyphs()
        self.check_palette()
        self.check_keymaps()
        self.check_tiles()
        self.check_zones()
        self.check_sectors()
        self.check_cores()
        self.check_ice()
        self.check_programs()
        self.check_items()
        self.check_hymns()
        self.check_vendors()
        self.check_npcs()
        self.check_factions()
        self.check_evidence()
        self.check_contracts()
        self.check_routes()
        self.check_events()
        self.check_services()
        self.check_dialogue()
        self.check_seasons()
        self.check_art()
        self.check_route_variants()

    # --- bundles -----------------------------------------------------------

    def check_bundles(self) -> None:
        owner_of: dict[tuple[str, str], str] = {}
        for bid, bundle in sorted(self.t.bundles.items()):
            for kind, ids in sorted(bundle.members.items()):
                if kind not in s.BUNDLE_KINDS:
                    self.report("bundles", bid, f"unknown member kind {kind!r}", kind)
                    continue
                for member in ids:
                    if not self.exists(kind, member):
                        if bundle.status == "active":
                            self.report("bundles", bid, f"member {kind} {member!r} does not exist", member)
                        continue
                    key = (kind, member)
                    if key in owner_of:
                        self.report("bundles", bid, f"{kind} {member!r} is already in bundle {owner_of[key]!r}", member)
                        continue
                    owner_of[key] = bid
                    self.status[key] = bundle.status
            for dep in bundle.depends:
                if dep not in self.t.bundles:
                    self.report("bundles", bid, f"depends on missing bundle {dep!r}", dep)
                elif bundle.status == "active" and self.t.bundles[dep].status != "active":
                    self.report("bundles", bid, f"active bundle depends on authoring bundle {dep!r}", dep)
        for bid in sorted(self.t.bundles):
            if self._bundle_cycle(bid):
                self.report("bundles", bid, "bundle dependencies form a cycle")

    def _bundle_cycle(self, start: str) -> bool:
        stack = list(self.t.bundles[start].depends)
        seen: set[str] = set()
        while stack:
            dep = stack.pop()
            if dep == start:
                return True
            if dep in seen or dep not in self.t.bundles:
                continue
            seen.add(dep)
            stack.extend(self.t.bundles[dep].depends)
        return False

    def check_unique_catalog_ids(self) -> None:
        # Item, program, ICE and hymn ids share the catalog namespace.
        seen: dict[str, str] = {}
        for kind in ("items", "programs", "ice", "hymns"):
            for record_id in sorted(getattr(self.t, kind)):
                if record_id in seen:
                    self.report(kind, record_id, f"id {record_id!r} is also used by {seen[record_id]}")
                else:
                    seen[record_id] = kind

    # --- terminal tables --------------------------------------------------

    def glyph_chars(self) -> set[str]:
        return set(self.t.glyphs.glyphs.values()) if self.t.glyphs else set()

    def check_glyphs(self) -> None:
        if self.t.glyphs is None:
            return
        for gid, char in sorted(self.t.glyphs.glyphs.items()):
            if len(char) != 1:
                self.report("glyphs", "glyphs", f"glyph {gid!r} must be one character, got {char!r}", gid)
            elif display_width(char) != 1:
                self.report("glyphs", "glyphs", f"glyph {gid!r} ({char!r}) is not one cell wide", gid)
            elif not round_trips(char):
                self.report("glyphs", "glyphs", f"glyph {gid!r} ({char!r}) is not in CP437", gid)

    def check_palette(self) -> None:
        if self.t.palette is None:
            return
        roles = self.t.palette.roles
        for role in sorted(REQUIRED_ROLES - roles.keys()):
            self.report("palette", "palette", f"required role {role!r} is missing")
        for role, tiers in sorted(roles.items()):
            for tier in s.TIERS:
                variants = tiers.get(tier)
                if variants is None:
                    self.report("palette", "palette", f"role {role!r} has no {tier} values", role)
                    continue
                for variant in s.VARIANTS:
                    if variant not in variants:
                        self.report("palette", "palette", f"role {role!r} tier {tier} has no {variant} value", role)
                    elif not _colour_ok(tier, variants[variant]):
                        self.report("palette", "palette",
                                    f"role {role!r} tier {tier} {variant}: {variants[variant]!r} is not a {tier} colour", role)

    def role(self, role: str, owner: tuple[str, str], what: str) -> None:
        if self.t.palette is not None and role not in self.t.palette.roles:
            self.report(*owner, f"{what}: palette role {role!r} does not exist", role)

    def check_keymaps(self) -> None:
        km = self.t.keymaps
        if km is None:
            return
        for keymap in km.keymaps:
            for action in sorted(set(km.actions) - keymap.bindings.keys()):
                self.report("keymaps", "keymaps", f"keymap {keymap.id!r} does not bind {action!r}", keymap.id)
            used: dict[tuple[str, str], str] = {}
            for action, keys in sorted(keymap.bindings.items()):
                info = km.actions.get(action)
                if info is None:
                    self.report("keymaps", "keymaps", f"keymap {keymap.id!r} binds unknown action {action!r}", action)
                    continue
                if not keys:
                    self.report("keymaps", "keymaps", f"keymap {keymap.id!r} action {action!r} has no keys", action)
                contexts = ("zone", "lattice") if info.context == "any" else (info.context,)
                for key in keys:
                    for ctx in contexts:
                        other = used.get((ctx, key))
                        if other is not None and other != action:
                            self.report("keymaps", "keymaps",
                                        f"keymap {keymap.id!r}: key {key!r} is bound to both {other!r} and {action!r}", key)
                        used[(ctx, key)] = action

    def check_tiles(self) -> None:
        chars = self.glyph_chars()
        seen: dict[str, str] = {}
        for tid, tile in sorted(self.t.tiles.items()):
            owner = ("tiles", tid)
            if len(tile.char) != 1 or display_width(tile.char) != 1:
                self.report(*owner, f"tile {tid!r}: map char {tile.char!r} must be one single-width character")
            elif self.t.glyphs is not None and tile.char not in chars:
                self.report(*owner, f"tile {tid!r}: map char {tile.char!r} is not in glyphs.json")
            if tile.char in seen:
                self.report(*owner, f"tile {tid!r}: map char {tile.char!r} is also used by {seen[tile.char]!r}")
            seen[tile.char] = tid
            if self.t.glyphs is not None and tile.glyph not in self.t.glyphs.glyphs:
                self.report(*owner, f"tile {tid!r}: glyph {tile.glyph!r} is not in glyphs.json")
            self.role(tile.colour, owner, f"tile {tid!r}")
            if not 0 <= tile.cover <= 3:
                self.report(*owner, f"tile {tid!r}: cover {tile.cover} is outside 0-3")
            if tile.hazard is not None and tile.hazard.damage_per_second <= 0:
                self.report(*owner, f"tile {tid!r}: hazard damage must be positive")

    # --- zones -------------------------------------------------------------

    def passable(self, zone: s.Zone, tile: s.Tile) -> bool:
        tid = zone.tile_at(tile)
        return tid is not None and tid in self.t.tiles and self.t.tiles[tid].passable

    def in_pocket(self, zone: s.Zone, tile: s.Tile) -> bool:
        return any(tile in p.tiles() for p in zone.meta.pockets)

    def protected(self, zone: s.Zone, tile: s.Tile | None = None) -> bool:
        """Safe zones and pocket regions cannot hold hazards."""
        if zone.meta.safety in ("safe", "pocket"):
            return True
        return tile is not None and self.in_pocket(zone, tile)

    def check_zones(self) -> None:
        for zid, zone in self.each("zones"):
            assert isinstance(zone, s.Zone)
            owner = ("zones", zid)
            meta = zone.meta
            if not (ZONE_WIDTH[0] <= zone.width <= ZONE_WIDTH[1] and ZONE_HEIGHT[0] <= zone.height <= ZONE_HEIGHT[1]):
                self.problems.append(Problem(
                    self.t.source("maps", zid), None,
                    f"zone {zid} is {zone.width}x{zone.height}; zones are "
                    f"{ZONE_WIDTH[0]}-{ZONE_WIDTH[1]} wide and {ZONE_HEIGHT[0]}-{ZONE_HEIGHT[1]} high"))
            if meta.sight_radius <= 0:
                self.report(*owner, "sight_radius must be positive", "sight_radius")
            if meta.lean is not None:
                self.ref("factions", meta.lean, owner, "lean")
            for asset in meta.lore:
                self.ref("text", asset, owner, "lore", asset)
            self._check_zone_hazards(zone)
            self._check_exits(zone)
            self._check_objects(zone)
            self._check_spawners(zone)
            for i, pocket in enumerate(meta.pockets):
                if meta.safety != "contested":
                    self.report(*owner, f"pocket {i}: only contested zones have pockets", "pockets")
                if not self._region_in_bounds(zone, pocket):
                    self.report(*owner, f"pocket {i} is outside the map", "pockets")

    def _check_zone_hazards(self, zone: s.Zone) -> None:
        for y, row in enumerate(zone.grid):
            for x, tid in enumerate(row):
                tile = self.t.tiles.get(tid)
                if tile is not None and tile.hazard is not None and self.protected(zone, (x, y)):
                    self.problems.append(Problem(
                        self.t.source("maps", zone.id), y + 1,
                        f"column {x + 1}: hazard tile {tid!r} in a safe zone or pocket"))

    def _check_exits(self, zone: s.Zone) -> None:
        owner = ("zones", zone.id)
        seen: set[str] = set()
        for ex in zone.meta.exits:
            label = f"exit {ex.id}"
            if ex.id in seen:
                self.report(*owner, f"{label}: duplicate exit id", ex.id)
            seen.add(ex.id)
            if not self.passable(zone, ex.tile):
                self.report(*owner, f"{label}: tile {list(ex.tile)} is not a passable tile in {zone.id}", ex.id)
            if self.ref("zones", ex.target_zone, owner, f"{label}: target", ex.id):
                target = self.t.zones[ex.target_zone]
                if not self.passable(target, ex.target_tile):
                    self.report(*owner, f"{label}: target tile {list(ex.target_tile)} "
                                f"is not a passable tile in {ex.target_zone}", ex.id)
            if ex.requirement is not None:
                kind = "factions" if ex.requirement.kind == "faction" else "items"
                self.ref(kind, ex.requirement.ref, owner, f"{label}: requirement", ex.id)

    def _check_objects(self, zone: s.Zone) -> None:
        owner = ("zones", zone.id)
        seen: set[str] = set()
        for obj in zone.meta.objects:
            if obj.id in seen:
                self.report(*owner, f"object {obj.id}: duplicate object id", obj.id)
            seen.add(obj.id)
            if not self.passable(zone, obj.tile):
                self.report(*owner, f"object {obj.id}: tile {list(obj.tile)} is not a passable tile", obj.id)

    def _region_in_bounds(self, zone: s.Zone, region: s.Region) -> bool:
        return (region.w > 0 and region.h > 0 and region.x >= 0 and region.y >= 0
                and region.x + region.w <= zone.width and region.y + region.h <= zone.height)

    def _check_spawners(self, zone: s.Zone) -> None:
        owner = ("zones", zone.id)
        for sp in zone.meta.spawners:
            label = f"spawner {sp.id}"
            self.ref("npcs", sp.npc, owner, label, sp.id)
            if sp.count < 1:
                self.report(*owner, f"{label}: count must be at least 1", sp.id)
            if (sp.tile is None) == (sp.region is None):
                self.report(*owner, f"{label}: give exactly one of tile and region", sp.id)
            elif sp.tile is not None and not self.passable(zone, sp.tile):
                self.report(*owner, f"{label}: tile {list(sp.tile)} is not passable", sp.id)
            elif sp.region is not None and not (
                self._region_in_bounds(zone, sp.region)
                and any(self.passable(zone, t) for t in sp.region.tiles())
            ):
                self.report(*owner, f"{label}: region is empty (no passable tile inside the map)", sp.id)

    def object_at(self, zone_id: str, object_id: str) -> s.ObjectSpec | None:
        zone = self.t.zones.get(zone_id)
        if zone is None:
            return None
        return next((o for o in zone.meta.objects if o.id == object_id), None)

    # --- the Lattice -------------------------------------------------------

    def check_sectors(self) -> None:
        for sid, sector in self.each("sectors"):
            assert isinstance(sector, s.Sector)
            owner = ("sectors", sid)
            cells = {c.id: c for c in sector.cells}
            if len(cells) != len(sector.cells):
                self.report(*owner, "cell ids are not unique")
            positions: dict[s.Tile, str] = {}
            for cell in sector.cells:
                label = f"cell {cell.id}"
                if cell.pos in positions:
                    self.report(*owner, f"{label}: position {list(cell.pos)} is also {positions[cell.pos]}", cell.id)
                positions[cell.pos] = cell.id
                for n in cell.neighbours:
                    if n not in cells:
                        self.report(*owner, f"{label}: neighbour {n!r} does not exist", cell.id)
                    elif cell.id not in cells[n].neighbours:
                        self.report(*owner, f"{label}: neighbour {n!r} does not list it back", cell.id)
                if cell.kind == "core_entrance":
                    if cell.core_id is None:
                        self.report(*owner, f"{label}: a core entrance needs core_id", cell.id)
                    else:
                        self.ref("cores", cell.core_id, owner, label, cell.id)
                elif cell.core_id is not None:
                    self.report(*owner, f"{label}: only a core entrance has core_id", cell.id)
                for asset in cell.lore:
                    self.ref("text", asset, owner, f"{label}: lore", cell.id)

    def check_cores(self) -> None:
        hardware_owner: dict[tuple[str, s.Tile], str] = {}
        for cid, core in self.each("cores"):
            assert isinstance(core, s.Core)
            owner = ("cores", cid)
            if core.training:
                if core.tier != TRAINING_TIER:
                    self.report(*owner, f"the training core must be tier {TRAINING_TIER}", "tier")
            elif not CORE_TIER[0] <= core.tier <= CORE_TIER[1]:
                self.report(*owner, f"tier {core.tier} is outside {CORE_TIER[0]}-{CORE_TIER[1]} "
                            "(tier 0 is only for the training core)", "tier")
            if core.owner != "private":
                self.ref("factions", core.owner, owner, "owner")
            self._check_hardware(core, hardware_owner)
            self._check_rooms(core)

    def _check_hardware(self, core: s.Core, hardware_owner: dict[tuple[str, s.Tile], str]) -> None:
        owner = ("cores", core.id)
        n = len(core.hardware)
        if n == 0:
            self.report(*owner, "a core needs a hardware location", "hardware")
        elif n == 2:
            if core.id not in SHARED_HARDWARE_CORES:
                self.report(*owner, "only lat-shaft may have two hardware locations", "hardware")
            elif core.hardware[0].zone == core.hardware[1].zone:
                self.report(*owner, "the two hardware locations must be in different zones", "hardware")
        elif n > 2:
            self.report(*owner, f"{n} hardware locations; a core has one, lat-shaft two", "hardware")
        for hw in core.hardware:
            key = (hw.zone, hw.tile)
            if key in hardware_owner:
                self.report(*owner, f"hardware {hw.zone} {list(hw.tile)} is also core {hardware_owner[key]!r}", "hardware")
            hardware_owner[key] = core.id
            if not self.ref("zones", hw.zone, owner, "hardware", "hardware"):
                continue
            zone = self.t.zones[hw.zone]
            if not any(o.kind == "hardware" and o.tile == hw.tile for o in zone.meta.objects):
                self.report(*owner, f"hardware tile {hw.zone} {list(hw.tile)} is not a hardware object", "hardware")

    def _check_rooms(self, core: s.Core) -> None:
        owner = ("cores", core.id)
        rooms = {r.id: r for r in core.rooms}
        if len(rooms) != len(core.rooms):
            self.report(*owner, "room ids are not unique", "rooms")
        if not CORE_ROOMS[0] <= len(core.rooms) <= CORE_ROOMS[1]:
            self.report(*owner, f"{len(core.rooms)} rooms; a core has {CORE_ROOMS[0]}-{CORE_ROOMS[1]}", "rooms")
        control_ids: set[str] = set()
        for room in core.rooms:
            label = f"room {room.id}"
            for n in room.neighbours:
                if n not in rooms:
                    self.report(*owner, f"{label}: neighbour {n!r} does not exist", room.id)
                elif room.id not in rooms[n].neighbours:
                    self.report(*owner, f"{label}: neighbour {n!r} does not list it back", room.id)
            for ice in room.ice:
                self.ref("ice", ice, owner, label, room.id)
            for asset in room.lore:
                self.ref("text", asset, owner, f"{label}: lore", room.id)
            for data in room.data:
                if data.kind == "text":
                    if data.asset is None:
                        self.report(*owner, f"{label}: data {data.id} of kind text needs an asset", data.id)
                    self.ref("text", data.asset, owner, f"{label}: data {data.id}", data.id)
                elif data.amount is None or data.amount <= 0:
                    self.report(*owner, f"{label}: data {data.id} needs a positive amount", data.id)
            for control in room.controls:
                if control.id in control_ids:
                    self.report(*owner, f"control {control.id}: duplicate control id", control.id)
                control_ids.add(control.id)
                self._check_control(core, control)

    def _check_control(self, core: s.Core, c: s.ControlSpec) -> None:
        owner = ("cores", core.id)
        label = f"control {c.id}"
        lo, hi = CONTROL_RESET_SECONDS
        if not lo <= c.reset_seconds <= hi:
            self.report(*owner, f"{label}: reset_seconds {c.reset_seconds} is outside {lo}-{hi}", c.id)
        if c.revision < 1:
            self.report(*owner, f"{label}: revision must be at least 1", c.id)
        if c.owner_policy and c.safety_policy != "none":
            self.report(*owner, f"{label}: travel and hazard controls always expire; "
                        "owner_policy is not allowed", c.id)
        if not self.ref("zones", c.target.zone, owner, f"{label}: target zone", c.id):
            return
        obj = self.object_at(c.target.zone, c.target.object)
        if obj is None:
            if self.current_active:
                self.report(*owner, f"{label}: object {c.target.object!r} does not exist in {c.target.zone}", c.id)
            return
        zone = self.t.zones[c.target.zone]
        if c.safety_policy == "hazard":
            if self.protected(zone, obj.tile):
                self.report(*owner, f"{label}: a hazard control cannot target a safe zone or pocket", c.id)
            if c.warning_seconds < HAZARD_WARNING_SECONDS:
                self.report(*owner, f"{label}: a hazard needs at least {HAZARD_WARNING_SECONDS} s warning", c.id)
        if obj.essential and c.action in _CLOSING_ACTIONS:
            self.report(*owner, f"{label}: cannot {c.action} essential object {obj.id!r}", c.id)
        if obj.kind == "apartment_door" and (c.scope != "private_vestibule" or c.action != "open"):
            self.report(*owner, f"{label}: an apartment door control may only open the private vestibule", c.id)
        exit_here = next((e for e in zone.meta.exits if e.tile == obj.tile), None)
        if exit_here is not None and c.action in _CLOSING_ACTIONS and c.safety_policy != "route":
            self.report(*owner, f"{label}: closes exit {exit_here.id!r} but safety_policy is not 'route'", c.id)
        if c.safety_policy == "route":
            alt = next((e for e in zone.meta.exits if e.id == c.alternate_route), None)
            if c.alternate_route is None:
                self.report(*owner, f"{label}: a route control must name an alternate_route", c.id)
            elif alt is None:
                self.report(*owner, f"{label}: alternate_route {c.alternate_route!r} is not an exit in {zone.id}", c.id)
            elif alt.tile == obj.tile:
                self.report(*owner, f"{label}: alternate_route {alt.id!r} is behind the same door", c.id)

    def check_ice(self) -> None:
        for iid, ice in self.each("ice"):
            assert isinstance(ice, s.IceTemplate)
            owner = ("ice", iid)
            if not LATTICE_TIER[0] <= ice.tier <= LATTICE_TIER[1]:
                self.report(*owner, f"tier {ice.tier} is outside {LATTICE_TIER[0]}-{LATTICE_TIER[1]}")
            if ice.integrity <= 0:
                self.report(*owner, "integrity must be positive")
            if (ice.trigger == "trace") != (ice.trigger_trace is not None):
                self.report(*owner, "trigger_trace is set exactly when trigger is 'trace'")
            if ice.black != (ice.meat_damage > 0):
                self.report(*owner, "black ICE deals meat damage and only black ICE does")
            for var in ice.variants:
                if var == iid:
                    self.report(*owner, "an ICE cannot be its own variant")
                elif self.ref("ice", var, owner, "variant"):
                    other = self.t.ice[var]
                    if other.black:
                        self.report(*owner, f"variant {var!r} is black ICE; Surge never adds black ICE")
                    if other.tier > ice.tier:
                        self.report(*owner, f"variant {var!r} is tier {other.tier}, above tier {ice.tier}")
            for asset in ice.lore:
                self.ref("text", asset, owner, "lore", asset)

    def check_programs(self) -> None:
        names: dict[str, str] = {}
        for pid, prg in self.each("programs"):
            assert isinstance(prg, s.ProgramTemplate)
            owner = ("programs", pid)
            if not LATTICE_TIER[0] <= prg.tier <= LATTICE_TIER[1]:
                self.report(*owner, f"tier {prg.tier} is outside {LATTICE_TIER[0]}-{LATTICE_TIER[1]}")
            if prg.slots < 1:
                self.report(*owner, "slots must be at least 1")
            if prg.name in names:
                self.report(*owner, f"name {prg.name!r} is also {names[prg.name]!r}; programs have no aliases")
            names[prg.name] = pid

    # --- items --------------------------------------------------------------

    def check_items(self) -> None:
        for iid, item in self.each("items"):
            assert isinstance(item, s.ItemTemplate)
            owner = ("items", iid)
            if not ITEM_TIER[0] <= item.tier <= ITEM_TIER[1]:
                self.report(*owner, f"tier {item.tier} is outside {ITEM_TIER[0]}-{ITEM_TIER[1]}")
            if item.stack_max < 1:
                self.report(*owner, "stack_max must be at least 1")
            if item.weight < 0 or item.base_price < 0:
                self.report(*owner, "weight and base_price cannot be negative")
            wanted = s.ITEM_BLOCKS.get(item.class_)
            for block in sorted(set(s.ITEM_BLOCKS.values())):
                present = getattr(item, block) is not None
                if block == wanted and not present:
                    self.report(*owner, f"class {item.class_} needs a {block!r} block")
                elif block != wanted and present:
                    self.report(*owner, f"class {item.class_} cannot have a {block!r} block")
            if item.weapon is not None:
                self._check_weapon(item)
            if item.schematic is not None:
                self.ref("items", item.schematic.output, owner, "schematic output")
            if item.drone is not None:
                self.ref("items", item.drone.weapon, owner, "drone weapon")

    def _check_weapon(self, item: s.ItemTemplate) -> None:
        owner = ("items", item.id)
        w = item.weapon
        assert w is not None
        if w.melee:
            if w.range is not None or w.stamina is None:
                self.report(*owner, "a melee weapon has stamina and no range")
        elif w.range is None or w.range <= 0:
            self.report(*owner, "a ranged weapon needs a positive range")
        if w.ammo is not None and self.ref("items", w.ammo, owner, "ammo"):
            if self.t.items[w.ammo].class_ != "ammo":
                self.report(*owner, f"ammo {w.ammo!r} is not an ammo item")

    def check_hymns(self) -> None:
        for hid, hymn in self.each("hymns"):
            assert isinstance(hymn, s.HymnTemplate)
            if not ITEM_TIER[0] <= hymn.tier <= ITEM_TIER[1]:
                self.report("hymns", hid, f"tier {hymn.tier} is outside {ITEM_TIER[0]}-{ITEM_TIER[1]}")

    def check_vendors(self) -> None:
        for vid, vendor in self.each("vendors"):
            assert isinstance(vendor, s.Vendor)
            owner = ("vendors", vid)
            self.ref("factions", vendor.faction, owner, "faction")
            self.ref("zones", vendor.zone, owner, "zone")
            for entry in vendor.stock:
                self.ref("items", entry.item, owner, "stock", entry.item)

    # --- NPCs and factions --------------------------------------------------

    def check_npcs(self) -> None:
        for nid, npc in self.each("npcs"):
            assert isinstance(npc, s.NpcTemplate)
            owner = ("npcs", nid)
            self.ref("factions", npc.faction, owner, "faction")
            if npc.weapon is not None and self.ref("items", npc.weapon, owner, "weapon"):
                if self.t.items[npc.weapon].class_ != "weapon":
                    self.report(*owner, f"weapon {npc.weapon!r} is not a weapon")
            if npc.armour is not None and self.ref("items", npc.armour, owner, "armour"):
                if self.t.items[npc.armour].class_ != "armour":
                    self.report(*owner, f"armour {npc.armour!r} is not armour")
            self.ref("dialogue", npc.dialogue, owner, "dialogue")
            self.ref("vendors", npc.vendor, owner, "vendor")
            for loot in npc.loot:
                self.ref("items", loot.item, owner, "loot", loot.item)
                if not 0 < loot.chance <= 1:
                    self.report(*owner, f"loot {loot.item!r}: chance must be in (0, 1]", loot.item)
            for asset in npc.lore:
                self.ref("text", asset, owner, "lore", asset)

    def check_factions(self) -> None:
        ids = sorted(self.t.factions)
        actual: set[frozenset[str]] = set()
        for fid, fac in self.each("factions"):
            assert isinstance(fac, s.Faction)
            owner = ("factions", fid)
            self.role(fac.colour, owner, "colour")
            if fid in fac.relations:
                self.report(*owner, "a faction has no relation to itself")
            for other in ids:
                if other == fid:
                    continue
                mine = fac.relations.get(other)
                if mine is None:
                    self.report(*owner, f"relation to {other!r} is not defined")
                    continue
                theirs = self.t.factions[other].relations.get(fid)
                if theirs is not None and theirs != mine:
                    actual.add(frozenset((fid, other)))
            for other in sorted(set(fac.relations) - set(ids)):
                self.report(*owner, f"relation to unknown faction {other!r}", other)
            self.ref("zones", fac.hall, owner, "hall")
            if fac.vat is not None and self.ref("zones", fac.vat.zone, owner, "vat"):
                zone = self.t.zones[fac.vat.zone]
                if not any(o.kind == "vat" and o.tile == fac.vat.tile for o in zone.meta.objects):
                    self.report(*owner, f"vat {fac.vat.zone} {list(fac.vat.tile)} is not a vat object")
            self.ref("npcs", fac.recruiter, owner, "recruiter")
            self.ref("vendors", fac.vendor, owner, "vendor")
            for contract in fac.contracts:
                self.ref("contracts", contract, owner, "contract", contract)
            thresholds = [r.standing for r in fac.ranks]
            if thresholds != sorted(thresholds):
                self.report(*owner, "ranks must be in ascending standing order")
        declared: set[frozenset[str]] = set()
        for a, b in self.t.asymmetries:
            for f in (a, b):
                if f not in self.t.factions:
                    self.problems.append(Problem(self.t.source("factions", a if a in self.t.factions else b),
                                                 None, f"asymmetry names unknown faction {f!r}"))
            declared.add(frozenset((a, b)))
        if not self.t.factions:
            return
        path = self.t.sources.get(("factions", ids[0]), "factions.json")
        for pair in sorted(actual - declared, key=sorted):
            a, b = sorted(pair)
            self.problems.append(Problem(path, None, f"relations {a}/{b} differ by direction but are not declared in asymmetries"))
        for pair in sorted(declared - actual, key=sorted):
            a, b = sorted(pair)
            if a in self.t.factions and b in self.t.factions:
                self.problems.append(Problem(path, None, f"asymmetry {a}/{b} is declared but the relations are symmetric"))

    # --- contracts, evidence -------------------------------------------------

    def check_evidence(self) -> None:
        for eid, ev in self.each("evidence"):
            assert isinstance(ev, s.EvidenceRecord)
            owner = ("evidence", eid)
            self.ref("text", ev.asset, owner, "asset")
            self.ref("contracts", ev.related_objective, owner, "related_objective")
            for name in ("observation", "source", "claim"):
                if not getattr(ev, name).strip():
                    self.report(*owner, f"{name} must not be empty")

    def check_contracts(self) -> None:
        receipt_owner: dict[str, str] = {}
        branch_owner: dict[tuple[str, str], str] = {}
        for cid, con in self.each("contracts"):
            assert isinstance(con, s.ContractTemplate)
            owner = ("contracts", cid)
            if con.giver != "vesper":
                self.ref("factions", con.giver, owner, "faction")
            if not con.stages:
                self.report(*owner, "a contract needs at least one stage")
            stage_ids: set[str] = set()
            for stage in con.stages:
                label = f"stage {stage.id}"
                if stage.id in stage_ids:
                    self.report(*owner, f"{label}: duplicate stage id", stage.id)
                stage_ids.add(stage.id)
                if stage.receipt_key in receipt_owner:
                    self.report(*owner, f"{label}: receipt key {stage.receipt_key!r} "
                                f"is also used by {receipt_owner[stage.receipt_key]}", stage.id)
                receipt_owner[stage.receipt_key] = f"{cid}/{stage.id}"
                if stage.verb == "clear" and stage.resolution is None:
                    self.report(*owner, f"{label}: a clear stage declares lethal or subdue", stage.id)
                self._check_target(owner, label, stage.target, stage.id)
            self._check_reward(owner, con.reward, "reward")
            for opt in con.publication_options:
                self._check_reward(owner, opt.reward, f"publication {opt.id}")
            if len({o.id for o in con.publication_options}) != len(con.publication_options):
                self.report(*owner, "publication option ids are not unique")
            for ev in con.evidence_assets:
                self.ref("evidence", ev, owner, "evidence", ev)
            self.ref("contracts", con.chain, owner, "chain")
            if (con.branch_group is None) != (con.branch is None):
                self.report(*owner, "branch_group and branch are set together")
            elif con.branch_group is not None and con.branch is not None:
                key = (con.branch_group, con.branch)
                if key in branch_owner:
                    self.report(*owner, f"branch {con.branch_group}/{con.branch} is also {branch_owner[key]!r}")
                branch_owner[key] = cid
            if con.season is not None and str(con.season) not in self.t.seasons and self.current_active and con.story:
                self.report(*owner, f"season {con.season} is not defined")
            for cond in con.unlock_conditions:
                self.condition(cond, owner, "unlock condition")

    def _check_target(self, owner: tuple[str, str], label: str, t: s.StageTarget, needle: str) -> None:
        what = f"{label}: target"
        if t.kind in ("zone_object", "zone_tile"):
            if t.zone is None or not self.ref("zones", t.zone, owner, what, needle):
                if t.zone is None:
                    self.report(*owner, f"{what} needs a zone", needle)
                return
            if t.kind == "zone_object" and self.object_at(t.zone, t.object or "") is None and self.current_active:
                self.report(*owner, f"{what}: object {t.object!r} does not exist in {t.zone}", needle)
            if t.kind == "zone_tile" and (t.tile is None or not self.passable(self.t.zones[t.zone], t.tile)):
                self.report(*owner, f"{what}: tile is not passable in {t.zone}", needle)
        elif t.kind in ("core_room", "core_control"):
            if t.core is None or not self.ref("cores", t.core, owner, what, needle):
                if t.core is None:
                    self.report(*owner, f"{what} needs a core", needle)
                return
            core = self.t.cores[t.core]
            if t.kind == "core_room" and not any(r.id == t.room for r in core.rooms):
                self.report(*owner, f"{what}: room {t.room!r} does not exist in {t.core}", needle)
            if t.kind == "core_control" and not any(c.id == t.control for r in core.rooms for c in r.controls):
                self.report(*owner, f"{what}: control {t.control!r} does not exist in {t.core}", needle)
        elif t.kind == "npc":
            if t.npc is None:
                self.report(*owner, f"{what} needs an npc", needle)
            self.ref("npcs", t.npc, owner, what, needle)
        elif t.kind == "item":
            if t.item is None:
                self.report(*owner, f"{what} needs an item", needle)
            self.ref("items", t.item, owner, what, needle)
        elif t.kind == "cell":
            if t.sector is None or not self.ref("sectors", t.sector, owner, what, needle):
                if t.sector is None:
                    self.report(*owner, f"{what} needs a sector", needle)
                return
            if not any(c.id == t.cell for c in self.t.sectors[t.sector].cells):
                self.report(*owner, f"{what}: cell {t.cell!r} does not exist in {t.sector}", needle)

    def _check_reward(self, owner: tuple[str, str], r: s.Reward, label: str) -> None:
        if r.chits[0] > r.chits[1] or r.chits[0] < 0:
            self.report(*owner, f"{label}: chits range {list(r.chits)} is not a valid range")
        for fid in r.standing:
            self.ref("factions", fid, owner, f"{label}: standing", fid)
        for item in r.items:
            self.ref("items", item, owner, f"{label}: item", item)

    def condition(self, text: str, owner: tuple[str, str], what: str) -> None:
        """Check one condition string from the closed set (04-dramatis-
        personae.md Part III) and resolve its arguments."""
        parts = text.split()
        name, args = (parts[0], parts[1:]) if parts else ("", [])
        kinds = s.DIALOGUE_CONDITIONS.get(name)
        if kinds is None:
            self.report(*owner, f"{what}: unknown condition {name!r}", name or None)
            return
        if len(args) != len(kinds):
            self.report(*owner, f"{what}: {name} takes {len(kinds)} argument(s), got {len(args)}", name)
            return
        for kind, arg in zip(kinds, args):
            label = f"{what} {name}"
            if kind == "N":
                if not arg.lstrip("-").isdigit():
                    self.report(*owner, f"{label}: {arg!r} is not a number", name)
            elif kind == "FACTION":
                self.ref("factions", arg, owner, label, name)
            elif kind == "CONTRACT":
                self.ref("contracts", arg, owner, label, name)
            elif kind == "ITEM":
                self.ref("items", arg, owner, label, name)
            elif kind == "EVENT":
                self.ref("events", arg, owner, label, name)
            elif kind == "EVIDENCE":
                self.ref("evidence", arg, owner, label, name)
            elif kind == "SERVICE":
                self.ref("services", arg, owner, label, name)
            elif kind == "STAGE" and arg not in s.SEASON_STAGES:
                self.report(*owner, f"{label}: {arg!r} is not one of {', '.join(s.SEASON_STAGES)}", name)
            elif kind == "BALANCE" and arg not in s.BALANCES:
                self.report(*owner, f"{label}: {arg!r} is not one of {', '.join(s.BALANCES)}", name)
            elif kind == "STATE" and arg not in s.SERVICE_STATES:
                self.report(*owner, f"{label}: {arg!r} is not one of {', '.join(s.SERVICE_STATES)}", name)
            elif kind == "ARCH" and arg not in s.ARCHETYPES:
                self.report(*owner, f"{label}: {arg!r} is not an archetype", name)

    # --- events, routes, services ------------------------------------------

    def check_routes(self) -> None:
        for rid, route in self.each("routes"):
            assert isinstance(route, s.Route)
            owner = ("routes", rid)
            if route.speed <= 0:
                self.report(*owner, "speed must be positive")
            if len(route.waypoints) < 2:
                self.report(*owner, "a route needs at least two waypoints")
            for i, wp in enumerate(route.waypoints):
                if self.ref("zones", wp.zone, owner, f"waypoint {i}") and not self.passable(self.t.zones[wp.zone], wp.tile):
                    self.report(*owner, f"waypoint {i}: tile {list(wp.tile)} is not passable in {wp.zone}")

    def _check_effect(self, owner: tuple[str, str], label: str, e: s.Effect) -> None:
        zone = None
        if e.zone is not None and self.ref("zones", e.zone, owner, label):
            zone = self.t.zones[e.zone]
        self.ref("sectors", e.sector, owner, label)
        if zone is not None and e.region is not None and not self._region_in_bounds(zone, e.region):
            self.report(*owner, f"{label}: region is outside {zone.id}")
        if e.type == "hazard":
            if zone is None:
                if e.zone is None:
                    self.report(*owner, f"{label}: a hazard needs a zone")
            elif zone.meta.safety in ("safe", "pocket") or (
                e.region is not None and any(self.in_pocket(zone, t) for t in e.region.tiles())
            ) or (e.region is None and zone.meta.pockets):
                self.report(*owner, f"{label}: a hazard cannot touch a safe zone or pocket")
            if e.warning_seconds < HAZARD_WARNING_SECONDS:
                self.report(*owner, f"{label}: a hazard needs at least {HAZARD_WARNING_SECONDS} s warning")
        for ref in e.exits_closed:
            zone_id, _, exit_id = ref.partition("/")
            if self.ref("zones", zone_id, owner, f"{label}: exit {ref}"):
                if not any(x.id == exit_id for x in self.t.zones[zone_id].meta.exits):
                    self.report(*owner, f"{label}: exit {ref!r} does not exist")
        if e.type == "ice_variant":
            base, new = e.params.get("from"), e.params.get("to")
            if not isinstance(base, str) or not isinstance(new, str):
                self.report(*owner, f"{label}: an ice_variant effect names 'from' and 'to' ICE")
            elif self.ref("ice", base, owner, label) and self.ref("ice", new, owner, label):
                if new not in self.t.ice[base].variants:
                    self.report(*owner, f"{label}: {new!r} is not a declared variant of {base!r}")

    def check_events(self) -> None:
        for eid, ev in self.each("events"):
            assert isinstance(ev, s.EventTemplate)
            owner = ("events", eid)
            if ev.duration_seconds <= 0 or ev.cooldown_seconds < 0 or ev.weight < 1:
                self.report(*owner, "duration must be positive, cooldown non-negative, weight at least 1")
            if not ev.where:
                self.report(*owner, "where must name at least one zone or sector")
            for place in ev.where:
                if place not in self.t.zones and place not in self.t.sectors and self.current_active:
                    self.report(*owner, f"where: {place!r} is not a zone or sector", place)
            for i, e in enumerate(ev.effects):
                self._check_effect(owner, f"effect {i}", e)
            if len({v.id for v in ev.variants}) != len(ev.variants):
                self.report(*owner, "variant ids are not unique")
            for var in ev.variants:
                for i, e in enumerate(var.effects):
                    self._check_effect(owner, f"variant {var.id} effect {i}", e)
            for asset in (ev.announce.start, ev.announce.mid, ev.announce.end):
                self.ref("text", asset, owner, "announce", asset)
            self.ref("routes", ev.route, owner, "route")

    def check_services(self) -> None:
        for sid, svc in self.each("services"):
            assert isinstance(svc, s.ServiceNodeTemplate)
            owner = ("services", sid)
            if self.ref("zones", svc.zone, owner, "zone"):
                for obj in svc.target_objects:
                    if self.object_at(svc.zone, obj) is None:
                        self.report(*owner, f"target object {obj!r} does not exist in {svc.zone}", obj)
            self.ref("cores", svc.core, owner, "core")
            if sorted(a.id for a in svc.allocations) != ["common", "reserve"]:
                self.report(*owner, "a service has exactly one common and one reserve allocation")
            for alloc in svc.allocations:
                for i, e in enumerate(alloc.effects):
                    self._check_effect(owner, f"allocation {alloc.id} effect {i}", e)

    # --- dialogue and seasons -----------------------------------------------

    def check_dialogue(self) -> None:
        for did, node in self.each("dialogue"):
            assert isinstance(node, s.DialogueNode)
            owner = ("dialogue", did)
            self.ref("factions", node.faction, owner, "faction")
            if not node.lines:
                self.report(*owner, "a talker needs at least one line")
            elif node.lines[-1].when:
                self.report(*owner, "the last line is the fallback and has no conditions", node.lines[-1].id)
            if len({ln.id for ln in node.lines}) != len(node.lines):
                self.report(*owner, "line ids are not unique")
            for ln in node.lines:
                if len(ln.text) > DIALOGUE_LINE_MAX:
                    self.report(*owner, f"line {ln.id}: longer than {DIALOGUE_LINE_MAX} characters", ln.id)
                for cond in ln.when:
                    self.condition(cond, owner, f"line {ln.id}")
            if node.machine_mind:
                tags = {ln.tag for ln in node.lines}
                for tag in ("CUST", "TEN"):
                    if tag not in tags:
                        self.report(*owner, f"a machine-mind talker needs a {tag} line")
            hotkeys: set[str] = set()
            for offer in node.offers:
                if len(offer.hotkey) != 1 or offer.hotkey.lower() in hotkeys:
                    self.report(*owner, f"offer {offer.label!r}: hotkey {offer.hotkey!r} is not a unique single key")
                hotkeys.add(offer.hotkey.lower())
                kind = {"contract": "contracts", "vendor": "vendors", "service": "services",
                        "recruit": "factions", "travel": "zones"}[offer.kind]
                self.ref(kind, offer.ref, owner, f"offer {offer.label!r}")
                for cond in offer.when:
                    self.condition(cond, owner, f"offer {offer.label!r}")

    def check_seasons(self) -> None:
        for sid, season in self.each("seasons"):
            assert isinstance(season, s.SeasonDefinition)
            owner = ("seasons", sid)
            self.ref("zones", season.level.zone, owner, "level zone")
            self.ref("sectors", season.level.sector, owner, "level sector")
            if season.depth_target <= 0:
                self.report(*owner, "depth_target must be positive")
            if len(set(season.phases)) != len(season.phases):
                self.report(*owner, "phase (checkpoint) ids are not unique")
            choice_ids = [c.id for c in season.finale_choices]
            if len(set(choice_ids)) != len(choice_ids):
                self.report(*owner, "finale choice (ballot) ids are not unique")
            lo, hi = BALANCE_RANGE
            for choice in season.finale_choices:
                if not lo <= choice.balance_delta <= hi:
                    self.report(*owner, f"choice {choice.id}: balance_delta outside {lo}..{hi}", choice.id)
                self.ref("text", choice.chronicle, owner, f"choice {choice.id}: chronicle", choice.id)
                for fid in choice.standing:
                    self.ref("factions", fid, owner, f"choice {choice.id}: standing", choice.id)
                if choice.condition is not None:
                    self.condition(choice.condition, owner, f"choice {choice.id}")
            for tag in ("CUST", "TEN"):
                if not any(ln.tag == tag and ln.guaranteed for ln in season.finale_lines):
                    self.report(*owner, f"the finale needs a guaranteed {tag} line")
            for ln in season.finale_lines:
                self.ref("text", ln.text, owner, "finale line", ln.text)
            for ov in season.relations_override:
                self.ref("factions", ov.a, owner, "relations_override")
                self.ref("factions", ov.b, owner, "relations_override")
            for chain in season.story_chains:
                self.ref("contracts", chain, owner, "story chain", chain)

    def check_art(self) -> None:
        for aid, art in self.each("art"):
            assert isinstance(art, s.ArtAsset)
            owner = ("art", aid)
            if art.meta.width <= 0 or art.meta.height <= 0:
                self.report(*owner, "width and height must be positive")
            for var in art.meta.variants:
                self.ref("art", var, owner, "variant", var)

    # --- routes under every control, service and event state ----------------

    def check_route_variants(self) -> None:
        """Essential services and outward travel survive every variant.

        For the baseline and for each state that can close exits (every
        route control shut, each control shut alone, each event effect
        or variant, each service allocation), every zone that can reach
        an essential object at baseline must still reach one, and every
        zone with an open way out must keep one. Hidden and gated exits
        do not count as public routes.
        """
        zones = {z: v for z, v in self.t.zones.items() if self.is_active("zones", z)}
        if not zones:
            return
        baseline = self._reach(zones, frozenset())
        for label, owner, closed in self._variants(zones):
            reach = self._reach(zones, closed)
            for zid in sorted(zones):
                if baseline[zid][0] and not reach[zid][0]:
                    self.report(*owner, f"{label}: {zid} can no longer reach an essential service")
                if baseline[zid][1] and not reach[zid][1]:
                    self.report(*owner, f"{label}: {zid} has no way out")

    def _public_exits(self, zone: s.Zone) -> Iterable[s.Exit]:
        return (e for e in zone.meta.exits if e.requirement is None and not e.hidden)

    def _reach(self, zones: dict[str, s.Zone], closed: frozenset[str]) -> dict[str, tuple[bool, bool]]:
        """Per zone: (reaches an essential object, has an open way out)."""
        edges = {
            zid: {e.target_zone for e in self._public_exits(z)
                  if f"{zid}/{e.id}" not in closed and e.target_zone in zones}
            for zid, z in zones.items()
        }
        essential = {zid for zid, z in zones.items() if any(o.essential for o in z.meta.objects)}
        out = {}
        for zid in zones:
            seen, stack = {zid}, [zid]
            while stack:
                for nxt in edges[stack.pop()]:
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            out[zid] = (bool(seen & essential), bool(edges[zid]))
        return out

    def _variants(self, zones: dict[str, s.Zone]) -> Iterator[tuple[str, tuple[str, str], frozenset[str]]]:
        all_controls: set[str] = set()
        first_core: tuple[str, str] | None = None
        for cid, core in sorted(self.t.cores.items()):
            if not self.is_active("cores", cid):
                continue
            for room in core.rooms:
                for c in room.controls:
                    closed = self._control_closes(zones, c)
                    if closed:
                        first_core = first_core or ("cores", cid)
                        all_controls |= closed
                        yield f"control {c.id} shut", ("cores", cid), frozenset(closed)
        if first_core is not None:
            yield "every control shut", first_core, frozenset(all_controls)
        for eid, ev in sorted(self.t.events.items()):
            if not self.is_active("events", eid):
                continue
            base = frozenset(x for e in ev.effects for x in e.exits_closed)
            yield f"event {eid}", ("events", eid), base
            for var in ev.variants:
                yield f"event {eid} variant {var.id}", ("events", eid), base | {x for e in var.effects for x in e.exits_closed}
        for sid, svc in sorted(self.t.services.items()):
            if not self.is_active("services", sid):
                continue
            for alloc in svc.allocations:
                yield f"service {sid} {alloc.id}", ("services", sid), frozenset(x for e in alloc.effects for x in e.exits_closed)

    def _control_closes(self, zones: dict[str, s.Zone], c: s.ControlSpec) -> set[str]:
        if c.action not in _CLOSING_ACTIONS or c.target.zone not in zones:
            return set()
        obj = self.object_at(c.target.zone, c.target.object)
        if obj is None:
            return set()
        zone = zones[c.target.zone]
        return {f"{zone.id}/{e.id}" for e in zone.meta.exits if e.tile == obj.tile}


_KIND_NAMES = {
    "zones": "zone", "sectors": "sector", "cores": "core", "items": "item",
    "programs": "program", "ice": "ICE", "npcs": "NPC", "factions": "faction",
    "contracts": "contract", "events": "event", "routes": "route",
    "vendors": "vendor", "hymns": "hymn", "evidence": "evidence record",
    "services": "service", "dialogue": "dialogue", "seasons": "season",
    "text": "text asset", "art": "art asset", "bundles": "bundle",
}


def _colour_ok(tier: str, value: object) -> bool:
    if tier == "truecolor":
        return (isinstance(value, str) and len(value) == 7 and value[0] == "#"
                and all(c in "0123456789abcdefABCDEF" for c in value[1:]))
    if isinstance(value, bool) or not isinstance(value, int):
        return False
    return 0 <= value <= (255 if tier == "256" else 15)


def _summary(tree: ContentTree) -> str:
    def n(count: int, word: str) -> str:
        return f"{count} {word}" + ("" if count == 1 else "s")

    return (f"ok, {n(len(tree.zones), 'zone')}, {n(len(tree.sectors), 'sector')}, "
            f"{n(len(tree.cores), 'core')}, hash {tree.hash}")


def main(argv: list[str] | None = None) -> int:
    """`python -m blacksite.content.validate DIR [--local DIR]`."""
    parser = argparse.ArgumentParser(prog="python -m blacksite.content.validate",
                                     description="Validate a Blacksite content tree.")
    parser.add_argument("content", type=Path, help="content directory")
    parser.add_argument("--local", type=Path, default=None, help="operator override directory")
    args = parser.parse_args(argv)
    tree = load_content(args.content, args.local)
    problems = validate(tree)
    if problems:
        for problem in problems:
            print(problem)
        print(f"{len(problems)} problem" + ("" if len(problems) == 1 else "s"))
        return 1
    print(_summary(tree))
    return 0


if __name__ == "__main__":
    sys.exit(main())
