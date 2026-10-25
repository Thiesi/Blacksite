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
from math import isfinite
import re
import sys
from collections import deque
from collections.abc import Iterable, Iterator
from pathlib import Path

from blacksite.content import schema as s
from blacksite.content.cp437 import round_trips
from blacksite.content.formats import Problem, find_line, id_needles
from blacksite.content.ids import display_width
from blacksite.content.loader import ContentTree, load_content

__all__ = ["Problem", "validate", "exit_warnings", "main"]

# 00-game-design.md section 5.1: zone width 40-200, height 20-100.
ZONE_WIDTH = (40, 200)
ZONE_HEIGHT = (20, 100)
MAX_CONTRACT_OBJECTIVE_FACTOR = 3  # Game 9.1: a five-person roster.
CONTRACT_PLANT_SECONDS = 3  # Game 9.1: physical and core planting.
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

# Proposal 68: dressing may only use these shapes. Every glyph that means
# a rule (tiles, objects, people) stays reserved for that rule.
DRESSING_TEXT = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 -'&.,«»")
DRESSING_LINES = frozenset("─│")
DRESSING_GRAIN = frozenset("·∙,'` ")

_CLOSING_ACTIONS = frozenset({"close", "disable", "toggle"})
_INTEGER = re.compile(r"-?[0-9]+")


def validate(tree: ContentTree) -> list[Problem]:
    """Every problem in `tree`, load problems first."""
    v = _Validator(tree)
    v.run()
    return list(tree.load_problems) + v.problems


def exit_warnings(tree: ContentTree) -> list[Problem]:
    """S08: report one-way links without rejecting intentional one-way maps."""
    return [Problem(tree.source("zones", zone.id), None,
                    f"exit {ex.id}: no return exit from {ex.target_zone}")
            for zone in tree.zones.values() for ex in zone.meta.exits
            if ex.target_zone in tree.zones and not any(back.target_zone == zone.id
                for back in tree.zones[ex.target_zone].meta.exits)]


class _Validator:
    def __init__(self, tree: ContentTree) -> None:
        self.t = tree
        self.problems: list[Problem] = []
        self.status: dict[tuple[str, str], str] = {}
        self.bundle_of: dict[tuple[str, str], str] = {}
        self.current_active = True
        self.current_bundle: str | None = None
        self.passable_tiles = {zid: {(x, y) for y, row in enumerate(zone.grid) for x, key in enumerate(row)
                                     if key in tree.tiles and tree.tiles[key].passable}
                               for zid, zone in tree.zones.items()}

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
        name = _KIND_NAMES.get(kind, kind)
        if not found:
            self.report(*owner, f"{what}: {name} {target!r} does not exist", needle)
        elif not self.is_active(kind, target):
            self.report(*owner, f"{what}: {name} {target!r} is in an authoring bundle", needle)
        else:
            # A bundle declares the bundles it uses. Base content has no
            # manifest; it may use active bundles, and the authoring rule
            # above catches it if one is ever withdrawn.
            home = self.bundle_of.get((kind, target))
            mine = self.current_bundle
            if mine is not None and home is not None and home != mine and home not in self.depends_on(mine):
                self.report(*owner, f"{what}: {name} {target!r} is in bundle {home!r}, "
                            f"which bundle {mine!r} does not depend on", needle)
        return found

    def depends_on(self, bundle: str | None) -> set[str]:
        """Every bundle `bundle` depends on, directly or through others."""
        if bundle is None or bundle not in self.t.bundles:
            return set()
        seen: set[str] = set()
        stack = list(self.t.bundles[bundle].depends)
        while stack:
            dep = stack.pop()
            if dep not in seen and dep in self.t.bundles:
                seen.add(dep)
                stack.extend(self.t.bundles[dep].depends)
        return seen

    def each(self, kind: str) -> Iterator[tuple[str, object]]:
        for record_id, record in sorted(getattr(self.t, kind).items()):
            self.current_active = self.is_active(kind, record_id)
            self.current_bundle = self.bundle_of.get((kind, record_id))
            yield record_id, record
        self.current_active = True
        self.current_bundle = None

    # --- run ----------------------------------------------------------------

    def run(self) -> None:
        self.check_bundles()
        self.check_emotes()
        self.check_unique_catalog_ids()
        self.check_glyphs()
        self.check_palette()
        self.check_keymaps()
        self.check_tiles()
        self.check_zones()
        self.check_housing()
        self.check_sectors()
        self.check_cores()
        self.check_ice()
        self.check_programs()
        self.check_silt()
        self.check_items()
        self.check_salvage()
        self.check_progression()
        self.check_starts()
        self.check_hymns()
        self.check_vendors()
        self.check_relays()
        self.check_npcs()
        self.check_factions()
        self.check_faction_sites()
        self.check_evidence()
        self.check_contracts()
        self.check_routes()
        self.check_events()
        self.check_services()
        self.check_dialogue()
        self.check_seasons()
        self.check_art()
        self.check_themes()
        self.check_looks()
        self.check_route_variants()

    def check_emotes(self) -> None:
        from string import Formatter
        for eid, emote in self.t.emotes.items():
            for form in (emote.first, emote.third, emote.targeted, emote.first_targeted):
                try:
                    parts = list(Formatter().parse(form))
                    fields = [field for _, field, _, _ in parts if field is not None]
                    valid = (bool(form) and set(fields) <= {"name", "target"} and form.isprintable()
                             and all(not spec and conversion is None for _, _, spec, conversion in parts))
                    if valid:
                        form.format(name="Name", target="you")
                except (ValueError, KeyError, IndexError, AttributeError):
                    valid = False
                if not valid:
                    self.report("emotes", eid, "emote form must be printable with only name/target placeholders")

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
                    self.bundle_of[key] = bid
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
        return tile in self.passable_tiles[zone.id]

    def in_pocket(self, zone: s.Zone, tile: s.Tile) -> bool:
        return any(p.contains(tile) for p in zone.meta.pockets)

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
            if meta.sector is not None:
                self.ref("sectors", meta.sector, owner, "sector")
            if not (ZONE_WIDTH[0] <= zone.width <= ZONE_WIDTH[1] and ZONE_HEIGHT[0] <= zone.height <= ZONE_HEIGHT[1]):
                self.problems.append(Problem(
                    self.t.source("maps", zid), None,
                    f"zone {zid} is {zone.width}x{zone.height}; zones are "
                    f"{ZONE_WIDTH[0]}-{ZONE_WIDTH[1]} wide and {ZONE_HEIGHT[0]}-{ZONE_HEIGHT[1]} high"))
            if meta.sight_radius <= 0:
                self.report(*owner, "sight_radius must be positive", "sight_radius")
            if meta.sight_radius_night is not None and meta.sight_radius_night <= 0:
                self.report(*owner, "sight_radius_night must be positive", "sight_radius_night")
            if meta.spawn is not None and not self.passable(zone, meta.spawn):
                self.report(*owner, "spawn is not a passable tile", "spawn")
            if meta.lean is not None:
                self.ref("factions", meta.lean, owner, "lean")
            for asset in meta.lore:
                self.ref("text", asset, owner, "lore", asset)
            self._check_zone_hazards(zone)
            self._check_exits(zone)
            self._check_objects(zone)
            self._check_spawners(zone)
            self._check_layouts(zone)
            for i, pocket in enumerate(meta.pockets):
                if meta.safety != "contested":
                    self.report(*owner, f"pocket {i}: only contested zones have pockets", "pockets")
                if not self._region_in_bounds(zone, pocket):
                    self.report(*owner, f"pocket {i} is outside the map", "pockets")

    def _check_layouts(self, zone: s.Zone) -> None:
        owner = ("zones", zone.id)
        ids: set[str] = set()
        exits = {ex.id for ex in zone.meta.exits if not ex.hidden and ex.requirement is None}
        variants = [s.ZoneLayout("base"), *zone.meta.layouts]
        for layout in variants:
            if layout.id in ids:
                self.report(*owner, f"duplicate layout {layout.id!r}", "layouts")
            ids.add(layout.id)
            grid: dict[s.Tile, str] = {}
            for change in layout.changes:
                if change.tile in grid or zone.tile_at(change.tile) is None or change.tile_id not in self.t.tiles:
                    self.report(*owner, f"layout {layout.id}: invalid or repeated tile change", "layouts")
                    continue
                grid[change.tile] = change.tile_id
                tile = self.t.tiles[change.tile_id]
                if tile.hazard and (zone.meta.safety in ("safe", "pocket") or any(p.contains(change.tile) for p in zone.meta.pockets)):
                    self.report(*owner, f"layout {layout.id}: hazard in safe zone or pocket", "layouts")
                if tile.hazard and change.tile not in layout.warning_tiles:
                    self.report(*owner, f"layout {layout.id}: hazard needs a warning tile", "layouts")
            if any(zone.tile_at(tile) is None for tile in layout.warning_tiles):
                self.report(*owner, f"layout {layout.id}: warning tile outside map", "layouts")
            if not set(layout.alternate_routes) <= exits:
                self.report(*owner, f"layout {layout.id}: unknown alternate route", "layouts")
            if zone.meta.spawn is None:
                continue
            def safe(tile: s.Tile) -> bool:
                key = grid.get(tile, zone.tile_at(tile))
                return key in self.t.tiles and self.t.tiles[key].passable and self.t.tiles[key].hazard is None
            if not safe(zone.meta.spawn):
                self.report(*owner, f"layout {layout.id}: unsafe spawn", "layouts")
                continue
            seen = {zone.meta.spawn}
            pending = deque(seen)
            while pending:
                x, y = pending.popleft()
                for tile in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if tile not in seen and safe(tile):
                        seen.add(tile)
                        pending.append(tile)
            required = {obj.tile for obj in zone.meta.objects if obj.essential}
            required.update(ex.tile for ex in zone.meta.exits if not ex.hidden and ex.requirement is None)
            if not required <= seen:
                self.report(*owner, f"layout {layout.id}: essential service or outward exit unreachable", "layouts")

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
            if ex.relay and self.ref('relays', ex.relay, owner, f'{label}: relay', ex.id):
                relay = self.t.relays[ex.relay]
                expected = {'fast_gate': 'gate', 'cable_ride': 'cable'}.get(relay.benefit.kind)
                if ex.kind != expected or ex.hidden or ex.requirement is not None:
                    self.report(*owner, f'{label}: relay passage must be the declared public gate or cable route', ex.id)
                if ex.kind == 'gate' and zone.id != relay.zone:
                    self.report(*owner, f'{label}: fast gate is outbound from its relay zone only', ex.id)
                if ex.kind == 'cable':
                    if relay.zone not in (zone.id, ex.target_zone):
                        self.report(*owner, f'{label}: cable must join its relay zone', ex.id)
                    if not any(not alt.relay and not alt.hidden and alt.requirement is None
                            and alt.target_zone == ex.target_zone and alt.kind in ('ladder', 'street', 'door')
                            for alt in zone.meta.exits):
                        self.report(*owner, f'{label}: cable needs a free public alternative to the same zone', ex.id)

    def _check_objects(self, zone: s.Zone) -> None:
        owner = ("zones", zone.id)
        seen: set[str] = set()
        fields = 0
        for obj in zone.meta.objects:
            if obj.kind == "salvage_field":
                fields += 1
                if type(obj.params.get("ring")) is not int or obj.params["ring"] not in (1, 2, 3, 4):
                    self.report(*owner, "salvage field needs a numbered ring 1-4", obj.id)
                if self.t.salvage is None:
                    self.report(*owner, "salvage field needs salvage.json", obj.id)
            if obj.kind == "workshop" and obj.params.get("makes", "any") not in ("any", "rigs_programs", "chemical_melee"):
                self.report(*owner, "workshop makes must name a supported filter", obj.id)
            if obj.kind == "terminal" and obj.params.get("sector") is not None:
                self.ref("sectors", obj.params["sector"], owner, obj.id)
                if obj.params.get("cell") is not None:
                    sector = self.t.sectors.get(obj.params["sector"])
                    cell = next((c for c in sector.cells if c.id == obj.params["cell"]), None) if sector else None
                    if cell is None or cell.access_kind != "public":
                        self.report(*owner, "terminal cell must name an existing public district entry", obj.id)
            if obj.params.get("training_npc"):
                self.ref("npcs",str(obj.params["training_npc"]),owner,"training NPC")
                tile = obj.params.get("training_tile")
                if not isinstance(tile,(list,tuple)) or len(tile)!=2 or any(type(n) is not int for n in tile) or not self.passable(zone,tuple(tile)):
                    self.report(*owner,"training NPC needs a passable authored training tile",obj.id)
            if obj.id in seen:
                self.report(*owner, f"object {obj.id}: duplicate object id", obj.id)
            seen.add(obj.id)
            if not self.passable(zone, obj.tile):
                self.report(*owner, f"object {obj.id}: tile {list(obj.tile)} is not a passable tile", obj.id)
        if fields > 1:
            self.report(*owner, "a zone can commission only one salvage field")

    def check_housing(self) -> None:
        for aid, definition in self.each("apartments"):
            if self.ref("items", definition.key_item, ("apartments", aid), "door key"):
                key = self.t.items[definition.key_item]
                if not key.door_key or key.stack_max != 1 or key.class_ != "key" or key.quality.kind != "none":
                    self.report("apartments", aid, "apartment key must be a single fixed key item")
            if (definition.storage_slots < 2 or definition.storage_slots % 2 or definition.rent <= 0
                    or not 1 <= definition.core_tier <= 3 or not 1 <= definition.lock_tier <= 3
                    or definition.core_upgrade_to not in (None, 3) or definition.core_upgrade_price < 0
                    or definition.lock_upgrade_to != 3 or definition.lock_upgrade_price <= 0):
                self.report("apartments", aid, "invalid apartment capacity, rent or upgrade")
        for rid, room in self.each("rooms"):
            if len(room.grid) != 4 or any(len(row) != 6 for row in room.grid):
                self.report("rooms", rid, "game 8.7 apartment rooms must be 6x4")
            positions = {obj.id: obj for obj in room.meta.objects}
            required = {"storage": "storage", "safe": "apartment_safe", "bed": "bed",
                        "terminal": "terminal", "hardware": "hardware", "light": "light"}
            if not required.keys() <= positions.keys():
                self.report("rooms", rid, "room needs storage, safe, bed, terminal, hardware and light")
            for oid, kind in required.items():
                if oid in positions and positions[oid].kind != kind:
                    self.report("rooms", rid, f"room {oid} must have kind {kind}")
            if len(positions) != len(room.meta.objects) or len({o.tile for o in room.meta.objects}) != len(positions):
                self.report("rooms", rid, "room object IDs and tiles must be unique")
            for tile in [room.meta.spawn, *(obj.tile for obj in room.meta.objects)]:
                x, y = tile
                if not (0 <= y < len(room.grid) and 0 <= x < len(room.grid[y])
                        and self.t.tiles[room.grid[y][x]].passable and not self.t.tiles[room.grid[y][x]].hazard):
                    self.report("rooms", rid, "room spawn and objects must be on a safe floor")
        used: set[tuple[str, str]] = set()
        for zid, zone in self.each("zones"):
            regions: list[s.Region] = []
            for obj in zone.meta.objects:
                anchor = obj.housing
                if anchor is None:
                    continue
                owner = ("zones", zid)
                if obj.kind != "apartment_door":
                    self.report(*owner, "only an apartment door can anchor housing", obj.id)
                self.ref("apartments", anchor.class_id, owner, "housing class", obj.id)
                self.ref("rooms", anchor.room, owner, "housing room", obj.id)
                if self.ref("sectors", anchor.sector, owner, "housing sector", obj.id):
                    cell = next((cell for cell in self.t.sectors[anchor.sector].cells if cell.id == anchor.cell), None)
                    if cell is None or cell.core_id or cell.core_placeholder or cell.access_kind != "public":
                        self.report(*owner, "housing needs an unallocated public sector cell", obj.id)
                key = anchor.sector, anchor.cell
                if key in used:
                    self.report(*owner, "housing sector cell is already allocated", obj.id)
                used.add(key)
                region = s.Region(*anchor.origin, 6, 4)
                if (not self._region_in_bounds(zone, region) or any(region.overlaps(other) for other in regions)
                        or not all(self.passable(zone, tile) and not self.t.tiles[zone.tile_at(tile)].hazard for tile in region.tiles())):
                    self.report(*owner, "housing rooms must have distinct safe 6x4 floors", obj.id)
                regions.append(region)
                public_tiles = {other.tile for other in zone.meta.objects if other is not obj}
                public_tiles.update(ex.tile for ex in zone.meta.exits)
                if zone.meta.spawn is not None:
                    public_tiles.add(zone.meta.spawn)
                if any(region.contains(tile) for tile in public_tiles):
                    self.report(*owner, "housing cannot occupy public objects, exits or spawn", obj.id)
                room = self.t.rooms.get(anchor.room)
                if room and self._region_in_bounds(zone, region):
                    if any(zone.tile_at((anchor.origin[0]+x, anchor.origin[1]+y)) != tile
                           for y, row in enumerate(room.grid) for x, tile in enumerate(row)):
                        self.report(*owner, "housing floor must match its room blueprint", obj.id)
                if region.contains(anchor.doorstep) or not self.passable(zone, anchor.doorstep):
                    self.report(*owner, "housing doorstep must be a public passable tile", obj.id)
                vestibule = anchor.origin[0]+anchor.vestibule[0], anchor.origin[1]+anchor.vestibule[1]
                if (max(abs(a-b) for a, b in zip(obj.tile, anchor.doorstep)) > 1
                        or max(abs(a-b) for a, b in zip(obj.tile, vestibule)) > 1):
                    self.report(*owner, "doorstep and vestibule must be adjacent to the housing door", obj.id)
                if not (0 <= anchor.vestibule[0] < 6 and 0 <= anchor.vestibule[1] < 4):
                    self.report(*owner, "housing vestibule must be a local room tile", obj.id)

    def _region_in_bounds(self, zone: s.Zone, region: s.Region) -> bool:
        return (region.w > 0 and region.h > 0 and region.x >= 0 and region.y >= 0
                and region.x + region.w <= zone.width and region.y + region.h <= zone.height)

    def _check_spawners(self, zone: s.Zone) -> None:
        owner = ("zones", zone.id)
        for sp in zone.meta.spawners:
            label = f"spawner {sp.id}"
            self.ref("npcs", sp.npc, owner, label, sp.id)
            if sp.respawn_seconds < 0:
                self.report(*owner, f"{label}: respawn seconds must be nonnegative", sp.id)
            if sp.condition and sp.condition not in ("always", "per_player"):
                if not sp.condition.startswith("event:") or not sp.condition[6:]:
                    self.report(*owner, f"{label}: unknown condition", sp.id)
            npc = self.t.npcs.get(sp.npc)
            if sp.condition == "per_player" and npc and not npc.training:
                self.report(*owner, f"{label}: per_player requires private training", sp.id)
            if npc:
                for behaviour in npc.behaviours:
                    if behaviour.kind == "patrol":
                        points = behaviour.params.get("waypoints")
                        if not isinstance(points, list) or not points or any(not isinstance(p, list) or len(p) != 2 or any(type(n) is not int for n in p) or not self.passable(zone, tuple(p)) for p in points):
                            self.report(*owner, f"{label}: patrol needs passable waypoints", sp.id)
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
            if sector.trace_owner:
                self.ref("factions", sector.trace_owner, owner, "trace owner")
            cells = {c.id: c for c in sector.cells}
            width,height = sector.layout_size
            if not (1 <= width <= 8 and 1 <= height <= 6):
                self.report(*owner, "sector layout must fit eight columns by six rows")
            if len(cells) != len(sector.cells):
                self.report(*owner, "cell ids are not unique")
            if sector.entry is not None and (sector.entry not in cells or cells[sector.entry].access_kind != "public"):
                self.report(*owner, "entry must name a public cell")
            if not any(c.access_kind == "public" for c in sector.cells):
                self.report(*owner, "sector needs a public entrance")
            if sum(c.kind == "descent" for c in sector.cells) > 1:
                self.report(*owner, "sector has more than one descent cell")
            positions: dict[s.Tile, str] = {}
            for cell in sector.cells:
                label = f"cell {cell.id}"
                if not (0 <= cell.pos[0] < width and 0 <= cell.pos[1] < height):
                    self.report(*owner, f"{label}: position is outside layout bounds", cell.id)
                if cell.access is not None and cell.kind in ("public", "gated", "hidden") and cell.access != cell.kind:
                    self.report(*owner, f"{label}: access conflicts with cell kind", cell.id)
                if cell.access_kind == "gated" and not cell.requirement:
                    self.report(*owner, f"{label}: gated access needs a credential", cell.id)
                self.check_credential(cell.requirement, owner, label)
                if cell.pos in positions:
                    self.report(*owner, f"{label}: position {list(cell.pos)} is also {positions[cell.pos]}", cell.id)
                positions[cell.pos] = cell.id
                for n in cell.neighbours:
                    if n not in cells:
                        self.report(*owner, f"{label}: neighbour {n!r} does not exist", cell.id)
                    elif cell.id not in cells[n].neighbours:
                        self.report(*owner, f"{label}: neighbour {n!r} does not list it back", cell.id)
                if cell.kind == "core_entrance":
                    if cell.core_placeholder:
                        if cell.core_id is not None:
                            self.report(*owner, f"{label}: placeholder cannot name an active core", cell.id)
                        if not cell.planned_core or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*",cell.planned_core):
                            self.report(*owner, f"{label}: placeholder needs a planned core slug", cell.id)
                        elif cell.planned_core in self.t.cores and self.t.active("cores",cell.planned_core):
                            self.report(*owner, f"{label}: active core must replace its placeholder", cell.id)
                    elif cell.core_id is None:
                        self.report(*owner, f"{label}: a core entrance needs core_id", cell.id)
                    else:
                        self.ref("cores", cell.core_id, owner, label, cell.id)
                elif cell.core_id is not None:
                    self.report(*owner, f"{label}: only a core entrance has core_id", cell.id)
                if cell.core_placeholder and cell.kind != "core_entrance":
                    self.report(*owner, f"{label}: only a core entrance can be a placeholder", cell.id)
                if cell.planned_core and not cell.core_placeholder:
                    self.report(*owner, f"{label}: planned_core is only for an unavailable placeholder", cell.id)
                if cell.gate_owner:
                    self.ref("factions", cell.gate_owner, owner, f"{label}: gate owner", cell.id)
                if cell.uplink:
                    self.check_credential(cell.uplink.requirement, owner, label)
                    if self.ref("sectors",cell.uplink.sector,owner,label,cell.id):
                        destination = next((c for c in self.t.sectors[cell.uplink.sector].cells if c.id == cell.uplink.cell), None)
                        if destination is None:
                            self.report(*owner, f"{label}: uplink cell does not exist", cell.id)
                        elif not destination.uplink or (destination.uplink.sector,destination.uplink.cell) != (sid,cell.id):
                            self.report(*owner, f"{label}: uplink is not reciprocal", cell.id)
                for asset in cell.lore:
                    self.ref("text", asset, owner, f"{label}: lore", cell.id)

    def check_credential(self, value: str | None, owner: tuple[str,str], label: str) -> None:
        if not value:
            return
        parts = value.split(":")
        if len(parts) == 1:
            self.ref("programs" if value.startswith("prg_") else "items", value, owner, label)
        elif len(parts) == 2 and parts[0] in ("item", "program", "faction"):
            self.ref({"item":"items","program":"programs","faction":"factions"}[parts[0]],parts[1],owner,label)
        elif len(parts) == 2 and parts[0] == "event" and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*",parts[1]):
            # S24 supplies active event credentials; S13 declares the gate.
            pass
        elif len(parts) == 3 and parts[0] == "program" and parts[1] in ("attack","shield","decoy","loader","key","stealth","utility") and parts[2].isdigit() and 1 <= int(parts[2]) <= 5:
            pass
        elif len(parts) == 3 and parts[0] == "standing" and parts[2].isdigit() and 0 <= int(parts[2]) <= 100:
            self.ref("factions", parts[1], owner, label)
        else:
            self.report(*owner,f"{label}: invalid access credential {value!r}")

    def check_cores(self) -> None:
        hardware_owner: dict[tuple[str, s.Tile], str] = {}
        for cid, core in self.each("cores"):
            assert isinstance(core, s.Core)
            owner = ("cores", cid)
            if core.training:
                if core.tier != TRAINING_TIER:
                    self.report(*owner, f"the training core must be tier {TRAINING_TIER}", "tier")
                if core.id != "lat-wake-hall" or core.template:
                    self.report(*owner, "only the Wake is a training core", "training")
            elif not CORE_TIER[0] <= core.tier <= CORE_TIER[1]:
                self.report(*owner, f"tier {core.tier} is outside {CORE_TIER[0]}-{CORE_TIER[1]} "
                            "(tier 0 is only for the training core)", "tier")
            if core.template and self.current_active:
                self.report(*owner, "a core template must remain in an authoring bundle", "template")
            if core.owner != "private" and core.owner_kind == "faction":
                self.ref("factions", core.owner, owner, "owner")
            if core.affiliation:
                self.ref("factions", core.affiliation, owner, "affiliation")
            if (core.owner == "private" or core.owner_kind == "private") and any(self.t.ice[i].black or any(v.meat_damage and v.tier <= core.tier for v in self.t.ice[i].tier_stats)
                    for r in core.rooms for i in r.ice if i in self.t.ice):
                self.report(*owner, "private ICE cannot cause black feedback", "owner_kind")
            if (core.owner == "private" or core.owner_kind == "private") and not 1 <= core.tier <= 3:
                self.report(*owner, "private core tier must be 1-3", "tier")
            self._check_hardware(core, hardware_owner)
            self._check_rooms(core)

    def _check_hardware(self, core: s.Core, hardware_owner: dict[tuple[str, s.Tile], str]) -> None:
        owner = ("cores", core.id)
        n = len(core.hardware)
        if core.training or core.template:
            if n:
                self.report(*owner, "training and templates have no cuttable hardware", "hardware")
            return
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
            if hw.tile is None:
                if self.current_active:
                    self.report(*owner, "active hardware needs a resolved tile", "hardware")
                continue
            key = (hw.zone, hw.tile)
            if key in hardware_owner:
                self.report(*owner, f"hardware {hw.zone} {list(hw.tile)} is also core {hardware_owner[key]!r}", "hardware")
            hardware_owner[key] = core.id
            if not self.ref("zones", hw.zone, owner, "hardware", "hardware"):
                continue
            zone = self.t.zones[hw.zone]
            if not any(o.kind == "hardware" and o.tile == hw.tile and (hw.object_id is None or o.id == hw.object_id)
                       for o in zone.meta.objects):
                self.report(*owner, f"hardware tile {hw.zone} {list(hw.tile)} is not a hardware object", "hardware")

    def _check_rooms(self, core: s.Core) -> None:
        owner = ("cores", core.id)
        rooms = {r.id: r for r in core.rooms}
        if len(rooms) != len(core.rooms):
            self.report(*owner, "room ids are not unique", "rooms")
        if core.training and len(core.rooms) != 1:
            self.report(*owner, "the training core has exactly one room", "rooms")
        elif not core.training and not CORE_ROOMS[0] <= len(core.rooms) <= CORE_ROOMS[1]:
            self.report(*owner, f"{len(core.rooms)} rooms; a core has {CORE_ROOMS[0]}-{CORE_ROOMS[1]}", "rooms")
        entry = core.entry or (core.rooms[0].id if core.rooms else "")
        if entry not in rooms:
            self.report(*owner, "core entry must name an existing room", "entry")
        seen, pending = set(), [entry]
        while pending:
            rid = pending.pop()
            if rid in seen or rid not in rooms:
                continue
            seen.add(rid)
            pending.extend(rooms[rid].neighbours)
        if set(rooms) - seen:
            self.report(*owner, "every room must be reachable from the entry", "rooms")
        if len({r.pos for r in core.rooms}) != len(core.rooms) or any(not (0 <= r.pos[0] < 8 and 0 <= r.pos[1] < 4) for r in core.rooms):
            self.report(*owner, "rooms need unique authored positions in an 8x4 layout", "rooms")
        control_ids: set[str] = set()
        data_ids: set[str] = set()
        for room in core.rooms:
            label = f"room {room.id}"
            for n in room.neighbours:
                if n not in rooms:
                    self.report(*owner, f"{label}: neighbour {n!r} does not exist", room.id)
                elif room.id not in rooms[n].neighbours:
                    self.report(*owner, f"{label}: neighbour {n!r} does not list it back", room.id)
            for ice in room.ice:
                self.ref("ice", ice, owner, label, room.id)
            for ice, event in room.ice_events.items():
                if ice not in room.ice:
                    self.report(*owner, f"{label}: conditional ICE is not in this room", ice)
                self.ref("events", event, owner, f"{label}: ICE event", room.id)
            for ice, route in room.ice_patrols.items():
                if ice not in room.ice or room.id not in route or len(route) < 2:
                    self.report(*owner, f"{label}: patrol needs its defender, origin and linked loop", room.id)
                elif any(a not in rooms or b not in rooms or b not in rooms[a].neighbours
                         for a, b in zip(route, (*route[1:], route[0]))):
                    self.report(*owner, f"{label}: patrol cannot jump a room link", room.id)
            for asset in room.lore:
                self.ref("text", asset, owner, f"{label}: lore", room.id)
            for data in room.data:
                if data.id in data_ids:
                    self.report(*owner, f"duplicate data id {data.id}", data.id)
                data_ids.add(data.id)
                self._check_data(owner, data, label)
                if core.training and (data.kind != "text" or data.scope != "identity"):
                    self.report(*owner, "training data is a personal nonrewarding record", data.id)
            if core.training:
                if room.controls or len(room.ice) != 1:
                    self.report(*owner, "training has one weak ICE and no live controls", room.id)
                for iid in room.ice:
                    ice = self.t.ice.get(iid)
                    if ice and (ice.class_ != "tripwire" or ice.integrity != 10 or ice.attack != 5 or ice.black):
                        self.report(*owner, "training Tripwire must be nonblack integrity 10 / damage 5", iid)
            for control in room.controls:
                if control.id in control_ids:
                    self.report(*owner, f"control {control.id}: duplicate control id", control.id)
                control_ids.add(control.id)
                self._check_control(core, control)

    def _check_data(self, owner: tuple[str, str], data: s.DataSpec, label: str) -> None:
        if data.scope == 'mission' and (data.kind in ('chits', 'program', 'schematic') or data.programs):
            self.report(*owner, 'mission data cannot grant unbound cash or permanent unlocks; use the contract reward', data.id)
        if data.respawn_seconds < 0 or not 0 < data.chance <= 1:
            self.report(*owner, f"{label}: data respawn/chance is invalid", data.id)
        refs = {"text": "text", "item": "items", "salvage_data": "items", "schematic": "items",
                "program": "programs", "evidence": "evidence"}
        if data.kind in refs:
            if data.asset is None:
                self.report(*owner, f"{label}: data {data.id} of kind {data.kind} needs an asset", data.id)
            self.ref(refs[data.kind], data.asset, owner, f"{label}: data {data.id}", data.id)
        if data.kind not in ("text", "evidence") and (data.amount is None or data.amount <= 0):
            self.report(*owner, f"{label}: data {data.id} needs a positive amount", data.id)
        if data.kind == "contribution" and data.respawn_seconds < 3600:
            self.report(*owner, "contribution sources need at least 3600 seconds uptime", data.id)
        for pid in data.programs:
            self.ref("programs", pid, owner, f"{label}: stored program", data.id)
        if data.programs and data.kind != "item":
            self.report(*owner, "stored program payload requires an item source", data.id)

    def _check_control(self, core: s.Core, c: s.ControlSpec) -> None:
        owner = ("cores", core.id)
        label = f"control {c.id}"
        lo, hi = CONTROL_RESET_SECONDS
        # Game 6.4's named exceptions never weaken ordinary controls.
        short = ((c.scope == "mission" and c.permission == "contract" and c.reset_seconds == 120)
                 or (c.scope == "private_vestibule" and c.action == "open" and c.reset_seconds == 30)
                 or (core.id == "lat-house-lights" and c.target.zone == "sodium-row" and c.reset_seconds in (30, 60))
                 or (core.id == "lat-nave" and c.target.zone == "chapel-towers" and c.reset_seconds == 60)
                 or (core.id == "lat-tram-signal" and c.action == "call" and 0 < c.reset_seconds <= 30))
        short = short or (core.id == "lat-foundry" and c.id == "gantry" and c.target.zone == "oldworks-yards"
                          and c.action == "call" and c.safety_policy == "hazard" and c.reset_seconds == 30)
        if not short and not lo <= c.reset_seconds <= hi:
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
        if obj.essential and c.action in _CLOSING_ACTIONS:
            self.report(*owner, f"{label}: cannot {c.action} essential object {obj.id!r}", c.id)
            return
        if obj.kind in ("pump", "gantry"):
            layouts = {layout.id for layout in zone.meta.layouts}
            commissioned = obj.params.get("layout")
            choices = obj.params.get("work_order_layouts", [])
            if (not isinstance(choices, (list, tuple))
                    or not commissioned and not choices
                    or commissioned and (not isinstance(commissioned, str) or commissioned not in layouts)
                    or isinstance(choices, (list, tuple)) and any(not isinstance(choice, str) or choice not in layouts for choice in choices)):
                self.report(*owner, f"{label}: machine needs authored work-order layouts", c.id)
            if c.warning_seconds < HAZARD_WARNING_SECONDS:
                self.report(*owner, f"{label}: machine needs five seconds warning", c.id)
        if obj.kind in ("turret", "patrol_beacon"):
            spawners = {sp.id for sp in zone.meta.spawners}
            linked = obj.params.get("spawners", [])
            if not isinstance(linked, (list, tuple)) or not linked or any(not isinstance(sid, str) or sid not in spawners for sid in linked):
                self.report(*owner, f"{label}: machine needs local spawner bindings", c.id)
        if c.owner_policy and (obj.kind in ("pump", "gantry", "tram_stop", "cable_car", "lift", "gate", "shutter", "vat") or c.scope != "public"):
            self.report(*owner, f"{label}: travel, hazard and service effects cannot persist for an owner", c.id)
        if obj.kind == "vat" and (c.scope != "mission" or c.permission != "contract"):
            self.report(*owner, f"{label}: only a scoped mission test vat is controllable", c.id)
        if c.safety_policy == "hazard":
            if self.protected(zone, obj.tile):
                self.report(*owner, f"{label}: a hazard control cannot target a safe zone or pocket", c.id)
            if c.warning_seconds < HAZARD_WARNING_SECONDS:
                self.report(*owner, f"{label}: a hazard needs at least {HAZARD_WARNING_SECONDS} s warning", c.id)
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
            if ice.attack < 0 or ice.cast_seconds < 0 or ice.cooldown_seconds < 0 or (ice.attack and not ice.cooldown_seconds):
                self.report(*owner, "ICE damage and timing must be nonnegative, with cadence for attacks")
            if len({v.tier for v in ice.tier_stats}) != len(ice.tier_stats) or any(
                    not 1 <= v.tier <= 5 or v.integrity <= 0 or v.attack < 0 or v.meat_damage < 0 for v in ice.tier_stats):
                self.report(*owner, "ICE tier stats need distinct tiers and positive integrity")
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
            if not 1 <= prg.slots <= 7:
                self.report(*owner, "slots must be at least 1")
            if prg.price < 0 or prg.trace_cost < 0 or prg.duration < 0:
                self.report(*owner, "program price, trace and duration must be nonnegative")
            if (prg.cast_seconds is not None and prg.cast_seconds < 0
                    or prg.cooldown_seconds is not None and prg.cooldown_seconds < 0):
                self.report(*owner, "program timing must be nonnegative")
            if prg.cast_seconds is None and prg.effect.kind != "passive":
                self.report(*owner, "only a passive program omits cast timing")
            if prg.cooldown_seconds is None and prg.effect.kind != "passive" and not prg.effect.params.get("single_use"):
                self.report(*owner, "only passive or single-use programs omit cooldown timing")
            target = prg.target_class
            if ((prg.effect.kind == "area_damage" and target != "room")
                    or (prg.effect.kind == "damage" and target not in ("ice", "runner"))
                    or (prg.effect.kind == "open_gate" and target != "cell")):
                self.report(*owner, "program effect and target class disagree")
            for requirement in (*prg.acquisition_requires, *prg.cast_requires):
                parts = requirement.split(":")
                if requirement in ("once_per_season", "bound_loan", "bound_charge"):
                    continue
                if len(parts) == 2 and parts[0] == "archetype" and parts[1] in ("hardline", "ghost", "cantor", "operator"):
                    continue
                if len(parts) == 3 and parts[0] == "standing" and _INTEGER.fullmatch(parts[2]) and -100 <= int(parts[2]) <= 100:
                    self.ref("factions", parts[1], owner, "program standing")
                    continue
                self.report(*owner, f"invalid program requirement {requirement!r}")
            if prg.name in names:
                self.report(*owner, f"name {prg.name!r} is also {names[prg.name]!r}; programs have no aliases")
            names[prg.name] = pid

    def check_silt(self) -> None:
        rules = self.t.silt
        if rules is None:
            return
        owner = ("silt", "silt")
        if not 8 <= rules.minimum_cells <= rules.maximum_cells <= 20:
            self.report(*owner, "Silt bands need 8-20 cells")
        if not 1 <= rules.minimum_sinks <= rules.maximum_sinks <= 3 or not 0 <= rules.hidden_fraction <= .2:
            self.report(*owner, "Silt needs 1-3 sinks and at most one fifth hidden cells")
        if len(rules.bands) != 5 or [b.depth for b in rules.bands] != list(range(5)) or len({b.id for b in rules.bands}) != 5:
            self.report(*owner, "Silt needs five distinct ordered bands")
        for band in rules.bands:
            if len({d.id for d in band.data}) != len(band.data):
                self.report(*owner, f"{band.id}: duplicate data ids")
            for spawn in band.ice:
                self.ref("ice", spawn.template, owner, band.id)
                if not 0 <= spawn.minimum <= spawn.maximum <= rules.minimum_cells:
                    self.report(*owner, f"{band.id}: invalid ICE population")
            for data in band.data:
                self._check_data(owner, data, band.id)

    # --- items --------------------------------------------------------------

    def check_items(self) -> None:
        from blacksite.server.quality import validate_policy
        for iid, item in self.each("items"):
            assert isinstance(item, s.ItemTemplate)
            owner = ("items", iid)
            if problem := validate_policy(item):
                self.report(*owner, problem)
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
                kind = "programs" if item.schematic.output.startswith("prg_") else "items"
                self.ref(kind, item.schematic.output, owner, "schematic output")
                if (not item.schematic.inputs or any(grade not in ("hull", "optics", "power", "compute", "intact")
                        or amount < 1 for grade, amount in item.schematic.inputs.items())
                        or not 0 <= item.schematic.skill_min <= 100):
                    self.report(*owner, "schematic needs positive salvage inputs and skill 0-100")
            if item.drone is not None:
                self.ref("items", item.drone.weapon, owner, "drone weapon")
                drone = item.drone
                if drone.health < 1 or drone.move_ms < 100 or (drone.control_range is not None and drone.control_range < 1):
                    self.report(*owner, "a drone needs positive health/range and movement of at least one tick")
                if drone.attack is not None:
                    self._weapon_block(drone.attack, owner)
            if item.implant is not None:
                block = item.implant
                if block.tolerance < 0:
                    self.report(*owner, "implant tolerance cannot be negative")
                if block.portable and (item.class_ != "rig" or block.tolerance != 0
                                       or block.effects or not block.rig_slots):
                    self.report(*owner, "a portable rig has zero tolerance, slots and no implanted effects")
            if item.drug is not None:
                drug = item.drug
                if drug.duration <= 0 or drug.addiction_window <= 0 or drug.addiction_doses < 1:
                    self.report(*owner, "drug duration, addiction window and dose threshold must be positive")

    def check_salvage(self) -> None:
        rules = self.t.salvage
        if rules is None:
            return  # Older/local fixture worlds need not commission salvage.
        grades = {"hull", "optics", "power", "compute", "intact"}
        valid = (set(rules.weights) == {"1", "2", "3", "4"}
            and 1 <= rules.minimum_nodes <= rules.maximum_nodes <= 100
            and 1 <= rules.minimum_units <= rules.maximum_units <= 100
            and min(rules.respawn_seconds, rules.harvest_seconds, rules.craft_seconds) > 0)
        for ring, weights in rules.weights.items():
            valid = valid and bool(weights) and set(weights) <= grades and sum(weights.values()) == 100
            valid = valid and all(weight > 0 for weight in weights.values())
            valid = valid and (ring == "4" or not weights.get("intact"))
            valid = valid and all(any(item.salvage and item.salvage.grade == grade
                for item in self.t.items.values()) for grade in weights)
        if not valid:
            self.report("salvage", "salvage", "invalid salvage bounds, ring weights or grade templates")

    def check_progression(self) -> None:
        grades = list(self.each("grades"))
        if grades and sorted(row.grade for _, row in grades) != list(range(1, 31)):
            self.report("grades", grades[0][0], "grade titles must cover grades 1-30 exactly once")
        for gid, grade in grades:
            if not grade.title.strip() or not grade.promotion.strip():
                self.report("grades", gid, "a grade needs a title and promotion line")
            if grade.grade == 5 and grade.title != "Ninety-Day":
                self.report("grades", gid, "grade 5 is the Ninety-Day milestone")
        skills = list(self.each("skills"))
        expected = {"kinetic", "melee", "armour", "energy", "stealth", "drones",
                    "lattice", "programs", "fabrication", "hymns", "dissonance", "listening"}
        if skills and {sid for sid, _ in skills} != expected:
            self.report("skills", skills[0][0], "skills must define the twelve game 3.3 lines")
        for sid, skill in skills:
            if not skill.name.strip() or not skill.uses or any(rate <= 0 for rate in skill.uses.values()):
                self.report("skills", sid, "a skill needs a name and positive use rates")
            if skill.maximum != 100 or skill.daily_cap != 2:
                self.report("skills", sid, "game 3.5 fixes the maximum at 100 and daily use cap at 2")

    def _check_weapon(self, item: s.ItemTemplate) -> None:
        owner = ("items", item.id)
        w = item.weapon
        assert w is not None
        self._weapon_block(w,owner)

    def _weapon_block(self, w: s.WeaponBlock, owner: tuple[str,str]) -> None:
        if w.melee:
            if w.range is not None or w.stamina is None:
                self.report(*owner, "a melee weapon has stamina and no range")
        elif w.range is None or w.range <= 0:
            self.report(*owner, "a ranged weapon needs a positive range")
        if not w.melee and w.accuracy is None:
            self.report(*owner, "a ranged weapon needs accuracy")
        if w.ammo is not None and self.ref("items", w.ammo, owner, "ammo"):
            if self.t.items[w.ammo].class_ != "ammo":
                self.report(*owner, f"ammo {w.ammo!r} is not an ammo item")

    def check_starts(self) -> None:
        for sid, start in self.each("starts"):
            for item,count in start.recovery_items.items():
                self.ref("items",item,("starts",sid),"recovery item")
                if count < 1: self.report("starts",sid,"recovery quantity must be positive")
            for item, count in start.items.items():
                self.ref("items", item, ("starts", sid), "starter item")
                if count < 1:
                    self.report("starts", sid, "starter quantity must be positive")
            for item in (*start.equipment.values(), *start.implants.values()):
                if item not in start.items:
                    self.report("starts", sid, "equipped starter item was not granted")
            for kind in ("programs", "hymns"):
                for target in getattr(start, kind):
                    self.ref(kind, target, ("starts", sid), "starter ability")
            if start.rig_slots < 0:
                self.report("starts", sid, "rig slots cannot be negative")
        for cid, card in self.each("wake_cards"):
            self.ref("text", card.pitch, ("wake_cards", cid), "recruiter pitch")
            if card.faction:
                self.ref("factions", card.faction, ("wake_cards", cid), "recruiter faction")

    def check_hymns(self) -> None:
        for hid, hymn in self.each("hymns"):
            assert isinstance(hymn, s.HymnTemplate)
            if not ITEM_TIER[0] <= hymn.tier <= ITEM_TIER[1]:
                self.report("hymns", hid, f"tier {hymn.tier} is outside {ITEM_TIER[0]}-{ITEM_TIER[1]}")
            if hymn.cast_seconds < 0 or hymn.cooldown_seconds <= 0:
                self.report("hymns",hid,"cast must be nonnegative and cooldown positive")
            for iid in hymn.requires_one_of: self.ref("items",iid,("hymns",hid),"required resonance implant")

    def check_vendors(self) -> None:
        for vid, vendor in self.each("vendors"):
            assert isinstance(vendor, s.Vendor)
            owner = ("vendors", vid)
            self.ref("factions", vendor.faction, owner, "faction")
            self.ref("zones", vendor.zone, owner, "zone")
            self.ref("relays", vendor.relay, owner, "relay")
            for entry in vendor.stock:
                kind = "programs" if entry.item.startswith("prg_") else "items"
                self.ref(kind, entry.item, owner, "stock", entry.item)
                if entry.price_multiplier <= 0:
                    self.report(*owner, "stock price multiplier must be positive")
            if vendor.price_multiplier <= 0 or vendor.salvage_multiplier <= 0:
                self.report(*owner, "vendor price multipliers must be positive")
            if self.current_active and vendor.object_id:
                zone = self.t.zones.get(vendor.zone)
                if zone and not any(o.id == vendor.object_id and
                        (o.kind == "vendor" or vendor.relay and o.kind == "relay") for o in zone.meta.objects):
                    self.report(*owner, "vendor object anchor is missing")
            if self.current_active and vendor.clinic == "sablier":
                for zid, zone in self.t.zones.items():
                    if not self.t.active("zones",zid):
                        continue
                    for obj in zone.meta.objects:
                        if obj.params.get("vendor") == vid and zone.meta.safety != "safe" and not any(
                                pocket.contains(obj.tile) for pocket in zone.meta.pockets):
                            self.report(*owner,"Sablier clinic requires an existing safe pocket",obj.id)

    def check_relays(self) -> None:
        for rid, relay in self.each("relays"):
            owner = ("relays", rid)
            self.ref("zones", relay.zone, owner, "zone")
            self.ref("cores", relay.core, owner, "core")
            self.ref("vendors", relay.vendor, owner, "vendor")
            if relay.tier not in range(1, 6) or relay.rate <= 0:
                self.report(*owner, "relay needs tier 1-5 and positive influence rate")
            amount, kind = relay.benefit.amount, relay.benefit.kind
            if not isfinite(amount):
                self.report(*owner, 'relay benefit amount must be finite')
            elif kind in ('vendor_refresh', 'hymn_radius', 'salvage_grade', 'impact_forecast'):
                if type(amount) is not int or amount <= 0:
                    self.report(*owner, 'relay benefit period, range or step must be a positive integer')
            elif kind in ('surgery_fee', 'rent_and_ice', 'trace_gain') and not 0 < amount <= 1:
                self.report(*owner, 'relay discount multiplier must be above zero and at most one')
            elif kind == 'depth_contribution' and amount < 1 or kind == 'fabrication_quality' and amount < 0:
                self.report(*owner, 'relay benefit amount is below its allowed minimum')
            core = self.t.cores.get(relay.core)
            if core and (core.owner_kind != "relay" or core.template or core.tier != relay.tier):
                self.report(*owner, "relay core must be a matching-tier relay instance")
            vendor = self.t.vendors.get(relay.vendor)
            if vendor and (vendor.relay != rid or vendor.zone != relay.zone or vendor.object_id != relay.terminal):
                self.report(*owner, "relay counter must bind this relay and its terminal")
            if not self.current_active:
                continue
            zone = self.t.zones.get(relay.zone)
            terminal = self.object_at(relay.zone, relay.terminal)
            if not terminal or terminal.kind != "relay" or terminal.params.get("relay") != rid:
                self.report(*owner, "active relay requires its real relay terminal")
            elif zone and (zone.meta.safety in ("safe", "pocket") or
                    any(pocket.contains(terminal.tile) for pocket in zone.meta.pockets)):
                self.report(*owner, "relay terminal must stand outside protected service pockets")
            if core and (len(core.hardware) != 1 or core.hardware[0].zone != relay.zone):
                self.report(*owner, "relay hardware must be in its terminal's actual zone")
            if core and not any(control.id == 'relay_open' for room in core.rooms for control in room.controls):
                self.report(*owner, "relay core requires its relay_open control")

    # --- NPCs and factions --------------------------------------------------

    def check_npcs(self) -> None:
        for nid, npc in self.each("npcs"):
            assert isinstance(npc, s.NpcTemplate)
            owner = ("npcs", nid)
            if npc.health is not None and npc.health <= 0: self.report(*owner,"health must be positive")
            if npc.attack: self._weapon_block(npc.attack,owner)
            if npc.training and (npc.health is None or npc.attack is None):
                self.report(*owner,"a private training actor requires explicit health and attack")
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
            if ev.related_stage:
                job = self.t.contracts.get(ev.related_objective)
                if job is None or ev.related_stage not in {
                        stage.id for stage in (*job.stages, *(st for a in job.approaches for st in a.stages))}:
                    self.report(*owner, "related_stage must name a stage of related_objective")
            for name in ("observation", "source", "claim"):
                if not getattr(ev, name).strip():
                    self.report(*owner, f"{name} must not be empty")

    def check_faction_sites(self) -> None:
        seen: set[str] = set()
        for sid, site in self.each("faction_sites"):
            owner = ("faction_sites", sid)
            self.ref("factions", site.faction, owner, "faction")
            hall_exists = self.ref("zones", site.hall, owner, "hall")
            self.ref("zones", site.recruiter_zone, owner, "public recruiter")
            self.ref("vendors", site.vendor, owner, "hall vendor")
            if site.faction in seen:
                self.report(*owner, "a faction may have only one physical site")
            seen.add(site.faction)
            faction = self.t.factions.get(site.faction)
            if faction and any((faction.hall, faction.vat, faction.vendor)):
                self.report(*owner, "physical site duplicates direct faction bindings")
            if not self.current_active:
                continue  # S25 supplies real anchors before commissioning.
            if site.vat is None:
                self.report(*owner, "an active faction site needs its actual protected vat")
            elif self.ref("zones", site.vat.zone, owner, "vat"):
                zone = self.t.zones[site.vat.zone]
                obj = next((o for o in zone.meta.objects if o.kind == "vat" and o.tile == site.vat.tile), None)
                if obj is None or not self.protected(zone, site.vat.tile):
                    self.report(*owner, "faction vat must be an actual protected vat object")
            if not site.vendor:
                self.report(*owner, "an active faction site needs its actual counter")
            elif hall_exists and not any(o.kind == "vendor" and o.params.get("vendor") == site.vendor
                                        for o in self.t.zones[site.hall].meta.objects):
                self.report(*owner, "faction vendor must have an actual hall counter")

    def check_contracts(self) -> None:
        receipt_owner: dict[str, str] = {}
        branch_owner: dict[tuple[str, str], str] = {}
        mission_owner: dict[str, str] = {}
        for cid, con in self.each("contracts"):
            assert isinstance(con, s.ContractTemplate)
            owner = ("contracts", cid)
            for data in con.mission_data:
                self._check_data(owner, data, 'mission data')
                if data.scope != 'mission':
                    self.report(*owner, 'contract mission_data must be mission scoped', data.id)
                if data.id in mission_owner:
                    self.report(*owner, f'mission data id is also used by {mission_owner[data.id]}', data.id)
                mission_owner[data.id] = cid
                if self.t.silt and any(d.id == data.id for b in self.t.silt.bands for d in b.data):
                    self.report(*owner, 'contract mission data cannot replace an ordinary Silt source', data.id)
            if con.service and (con.story or con.crew_scaling):
                self.report(*owner, "a service contract is repeatable and never crew-scaled")
            if con.service and (con.reward.chits != (200, 200) or con.reward.xp != 100
                    or con.reward.standing != {con.giver: 5} or con.reward.items or con.reward.programs):
                self.report(*owner, "a service contract uses the standard Game 7.5 worker reward")
            if con.giver != "vesper":
                self.ref("factions", con.giver, owner, "faction")
            if not con.stages:
                self.report(*owner, "a contract needs at least one stage")
            if len({a.id for a in con.approaches}) != len(con.approaches) or any(a.id == 'default' for a in con.approaches):
                self.report(*owner, "approach ids must be unique and cannot be default")
            stage_ids: set[str] = set()
            stages = (*con.stages, *(stage for a in con.approaches for stage in a.stages))
            for approach in con.approaches:
                if not approach.stages or not approach.label:
                    self.report(*owner, "an approach needs a label and stages", approach.id)
            for stage in stages:
                label = f"stage {stage.id}"
                if stage.seconds < 0:
                    self.report(*owner, f"{label}: action seconds cannot be negative", stage.id)
                if stage.window_seconds < 0:
                    self.report(*owner, f'{label}: field window cannot be negative', stage.id)
                sequence = next((a.stages for a in con.approaches if stage in a.stages), con.stages)
                if stage.retry_from and stage.retry_from not in [s.id for s in sequence[:sequence.index(stage)+1]]:
                    self.report(*owner, f'{label}: retry checkpoint must be this or an earlier stage', stage.id)
                if stage.verb == 'plant':
                    if not stage.requires_item and not stage.target.item:
                        self.report(*owner, f'{label}: a plant declares its supplied item', stage.id)
                    if stage.seconds not in (0, CONTRACT_PLANT_SECONDS):
                        self.report(*owner, f'{label}: planting takes {CONTRACT_PLANT_SECONDS} seconds', stage.id)
                if stage.verb == 'fetch' and stage.completion == 'carried' and not stage.target.item:
                    self.report(*owner, f'{label}: a pickup declares its supplied item', stage.id)
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
                if stage.linked_control:
                    self._check_target(owner, label+' linked control', stage.linked_control, stage.id)
                    if stage.linked_control.kind != 'core_control' or stage.target.kind != 'zone_object':
                        self.report(*owner, f"{label}: a linked control pairs a physical object with a core control", stage.id)
                    core = self.t.cores.get(stage.linked_control.core)
                    control = next((c for r in core.rooms for c in r.controls
                        if c.id == stage.linked_control.control), None) if core else None
                    if control and (control.target.zone, control.target.object) != (stage.target.zone, stage.target.object):
                        self.report(*owner, f"{label}: linked control targets another physical object", stage.id)
                    if control and (control.scope != 'mission' or control.permission != 'contract'
                            or control.action != 'open' or control.safety_policy != 'none'):
                        self.report(*owner, f'{label}: a linked manual release is a benign mission-scoped open', stage.id)
                if stage.completion == 'lifted' and stage.target.kind == 'core_room' and stage.target.data is None:
                    self.report(*owner, f"{label}: a lift names its exact room data", stage.id)
                if stage.requires_item:
                    self.ref('items', stage.requires_item, owner, label+' supplied item', stage.id)
                if stage.destination:
                    self._check_target(owner, label+' destination', stage.destination, stage.id)
                elif stage.verb == 'escort':
                    self.report(*owner, f"{label}: escort needs a typed destination", stage.id)
                if stage.quantity < 1:
                    self.report(*owner, f"{label}: quantity must be positive", stage.id)
                for target in stage.target_pool:
                    self._check_target(owner, label, target, stage.id)
                    if target.kind != stage.target.kind:
                        self.report(*owner, f"{label}: pool target kinds must match", stage.id)
                maximum = stage.quantity * (MAX_CONTRACT_OBJECTIVE_FACTOR
                                           if con.crew_scaling and not con.story else 1)
                if stage.target.kind not in ('npc', 'item') and len(stage.target_pool) + 1 < maximum:
                    self.report(*owner, f"{label}: target pool is too small for the accepted roster", stage.id)
                tags = dict((
                    ('fetch', ('carried', 'delivered')), ('hack', ('lifted', 'flipped', 'entered')),
                    ('escort', ('arrived',)), ('clear', ('defeated', 'subdued')),
                    ('plant', ('planted',)), ('survey', ('observed', 'compared', 'recorded')),
                ))
                if stage.completion not in tags[stage.verb]:
                    self.report(*owner, f"{label}: completion is not a {stage.verb} server fact", stage.id)
            self._check_reward(owner, con.reward, "reward")
            self._check_permit(owner, con.permit_scope, "permit")
            for opt in con.publication_options:
                self._check_reward(owner, opt.reward, f"publication {opt.id}")
                self._check_permit(owner, opt.permit, f"publication {opt.id}")
            if len({o.id for o in con.publication_options}) != len(con.publication_options):
                self.report(*owner, "publication option ids are not unique")
            if con.publication_options and (con.branch_group is None or con.branch is not None):
                self.report(*owner, "publication choices need a branch group without a fixed branch")
            for ev in con.evidence_assets:
                self.ref("evidence", ev, owner, "evidence", ev)
            self.ref("contracts", con.chain, owner, "chain")
            if (con.branch_group is None and con.branch is not None
                    or con.branch_group is not None and con.branch is None and not con.publication_options):
                self.report(*owner, "branch_group and branch are set together")
            elif con.branch_group is not None and con.branch is not None:
                key = (con.branch_group, con.branch)
                if key in branch_owner:
                    self.report(*owner, f"branch {con.branch_group}/{con.branch} is also {branch_owner[key]!r}")
                branch_owner[key] = cid
            elif con.branch_group is not None:
                for option in con.publication_options:
                    key = (con.branch_group, option.id)
                    if key in branch_owner:
                        self.report(*owner, f"branch {key[0]}/{key[1]} is also {branch_owner[key]!r}")
                    branch_owner[key] = cid
            if con.season is not None and str(con.season) not in self.t.seasons and self.current_active and con.story:
                self.report(*owner, f"season {con.season} is not defined")
            for cond in con.unlock_conditions:
                self.condition(cond, owner, "unlock condition")

    def _check_target(self, owner: tuple[str, str], label: str, t: s.StageTarget, needle: str) -> None:
        what = f"{label}: target"
        if t.item is not None and t.kind != 'item':
            self.ref('items', t.item, owner, what+' supplied item', needle)
        if t.kind in ('item', 'npc') and t.zone is not None and self.ref('zones', t.zone, owner, what, needle):
            if t.object is not None and self.object_at(t.zone, t.object) is None and self.current_active:
                self.report(*owner, f"{what}: object {t.object!r} does not exist in {t.zone}", needle)
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
            if t.kind == 'core_room' and t.data is not None and not any(
                    r.id == t.room and any(d.id == t.data for d in r.data) for r in core.rooms):
                self.report(*owner, f"{what}: data {t.data!r} does not exist in {t.core}/{t.room}", needle)
            if t.kind == "core_control" and not any(c.id == t.control for r in core.rooms for c in r.controls):
                self.report(*owner, f"{what}: control {t.control!r} does not exist in {t.core}", needle)
        elif t.kind == 'silt_data':
            if t.sector is None or not self.ref('sectors', t.sector, owner, what, needle):
                if t.sector is None:
                    self.report(*owner, f'{what} needs a sector', needle)
            if not self.t.silt or t.band not in {b.id for b in self.t.silt.bands}:
                self.report(*owner, f'{what} needs an authored Silt band', needle)
            con = self.t.contracts.get(owner[1]) if owner[0] == 'contracts' else None
            if con is None or t.data not in {d.id for d in con.mission_data}:
                self.report(*owner, f'{what} needs this contract\'s exact mission data', needle)
            if t.core is not None or t.room is not None or t.cell is not None or t.tile is not None:
                self.report(*owner, f'{what}: Silt data uses a band, never coordinates from a different seed', needle)
        elif t.kind == "npc":
            if t.npc is None:
                self.report(*owner, f"{what} needs an npc", needle)
            self.ref("npcs", t.npc, owner, what, needle)
            if t.zone is not None and self.ref('zones', t.zone, owner, what, needle) and t.tile is not None:
                if not self.passable(self.t.zones[t.zone], t.tile):
                    self.report(*owner, f"{what}: NPC spawn tile is not passable", needle)
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
        for program in r.programs:
            self.ref("programs", program, owner, f"{label}: program", program)
        if r.xp < 0:
            self.report(*owner, f"{label}: XP must not be negative")

    def _check_permit(self, owner: tuple[str, str], permit: s.Permit | None, label: str) -> None:
        if permit is None:
            return
        if permit.expiry_seconds <= 0:
            self.report(*owner, f"{label}: expiry must be positive")
        if permit.binding:
            self._check_target(owner, label, permit.binding, permit.target)
        elif self.current_active and not any(permit.target in getattr(self.t, kind)
                for kind in ('zones', 'cores', 'npcs', 'routes')):
            self.report(*owner, f"{label}: target needs a resolved binding", permit.target)

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
                if not _INTEGER.fullmatch(arg):
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
            elif kind == 'RECEIPT' and owner[0] == 'contracts' and self.current_active:
                if not any(job.branch_group == arg for job in self.t.contracts.values()):
                    self.report(*owner, f'{label}: no branch group {arg!r} can supply this receipt', name)
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
        if e.binding:
            self._check_target(owner, label+' binding', e.binding, e.binding.control or e.binding.object or e.binding.npc or '')
        if e.zone is not None and self.ref("zones", e.zone, owner, label):
            zone = self.t.zones[e.zone]
        self.ref("sectors", e.sector, owner, label)
        layout = e.params.get('layout')
        if layout is not None and zone is not None and self.current_active:
            if not any(item.id == layout for item in zone.meta.layouts):
                self.report(*owner, f"{label}: layout {layout!r} does not exist in {zone.id}")
        service = e.params.get('service')
        vendor = e.params.get('vendor')
        if vendor is not None:
            if isinstance(vendor, str):
                self.ref('vendors', vendor, owner, label+' vendor')
            else:
                self.report(*owner, f'{label}: vendor must be an id')
        object_id = e.params.get('object')
        if object_id is not None and self.current_active and (
                not isinstance(object_id, str) or zone is None or self.object_at(zone.id, object_id) is None):
            self.report(*owner, f'{label}: effect object needs a resolved zone/object binding', str(object_id))
        if service in ('surgery', 'buyback_budget'):
            multiplier = e.params.get('multiplier')
            valid = isinstance(multiplier, (int, float)) and not isinstance(multiplier, bool)
            valid = valid and (.8 <= multiplier <= 1 if service == 'surgery' else multiplier == 2)
            if e.type != 'price_modifier' or e.zone is None or not valid:
                self.report(*owner, f"{label}: invalid scoped {service} multiplier")
        if e.params.get('what') == 'credential' and (
                e.binding is None or e.binding.kind != 'core_control'):
            self.report(*owner, f"{label}: a service credential needs an exact core-control binding")
        region_ok = True
        if zone is not None and e.region is not None and not self._region_in_bounds(zone, e.region):
            self.report(*owner, f"{label}: region is outside {zone.id}")
            region_ok = False
        if e.type == "hazard":
            if zone is None:
                if e.zone is None:
                    self.report(*owner, f"{label}: a hazard needs a zone")
            elif region_ok and (zone.meta.safety in ("safe", "pocket") or (
                e.region is not None and any(e.region.overlaps(p) for p in zone.meta.pockets)
            ) or (e.region is None and zone.meta.pockets)):
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
                old, target = self.t.ice[base], self.t.ice[new]
                if (old.black or target.black or target.tier > old.tier or any(
                        getattr(old, key) != getattr(target, key) for key in
                        ('class_', 'role', 'trigger', 'behaviour', 'counters'))):
                    self.report(*owner, f'{label}: ICE variants must preserve role and counters at equal/lower tier without black ICE')
                if e.warning_seconds < HAZARD_WARNING_SECONDS:
                    self.report(*owner, f'{label}: ICE variants need a five second warning')
        if owner[0] == 'events':
            if e.type in ('hazard', 'npc_spawn', 'key_drop', 'salvage', 'spawn_multiplier') and not e.zone:
                self.report(*owner, f'{label}: physical event sources need a zone')
            if e.type == 'hazard' and e.region is None:
                self.report(*owner, f'{label}: event impact needs a bounded region')
            for key in ('count', 'cap', 'respawn_seconds', 'seconds'):
                if key in e.params and (type(e.params[key]) not in (int, float) or e.params[key] <= 0):
                    self.report(*owner, f'{label}: {key} must be positive')
            if 'radius' in e.params and (type(e.params['radius']) is not int or not 0 <= e.params['radius'] <= 3):
                self.report(*owner, f'{label}: impact radius must be an integer from zero to three')
            required = {'spawn_multiplier': ('multiplier', 'cap'), 'npc_spawn': ('npc', 'count', 'respawn_seconds'),
                'key_drop': ('item',), 'salvage': ('count', 'cap'), 'event_contract': ('contract',),
                'convoy_route': ('npc',), 'heat_multiplier': ('multiplier',), 'ability_magnitude': ('multiplier',)}
            if any(key not in e.params for key in required.get(e.type, ())):
                self.report(*owner, f'{label}: missing parameters for {e.type}')
            for key, kind in (('npc', 'npcs'), ('item', 'items'), ('contract', 'contracts')):
                if key in e.params:
                    self.ref(kind, e.params[key], owner, label+' '+key)
            if e.type == 'spawn_multiplier' and e.params.get('multiplier') not in (2, 3):
                self.report(*owner, f'{label}: Exhale spawn multiplier is two or three')
            if e.type == 'heat_multiplier' and e.params.get('multiplier') != 2:
                self.report(*owner, f'{label}: Curfew doubles new heat')
            if e.type == 'ability_magnitude' and e.params.get('multiplier') != 1.3:
                self.report(*owner, f'{label}: Surge beneficial magnitude is 1.3')
            if e.type == 'event_contract' and e.params.get('contract') in self.t.contracts:
                job = self.t.contracts[e.params['contract']]
                if (not job.event_only or job.story or job.service or job.crew_scaling or
                        len(job.stages) != 1 or job.stages[0].verb not in ('escort', 'clear')):
                    self.report(*owner, f'{label}: shared event job needs one fixed escort/clear source stage')

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
                if asset in self.t.text:
                    from string import Formatter
                    try:
                        fields = [(name, spec, conversion) for _, name, spec, conversion in Formatter().parse(self.t.text[asset].body)
                                  if name is not None]
                        if any(name not in ('name', 'where', 'plan', 'remaining', 'route', 'time')
                               or spec or conversion for name, spec, conversion in fields):
                            self.report(*owner, 'announce contains an unsupported placeholder')
                    except ValueError:
                        self.report(*owner, 'announce contains invalid placeholder braces')
            self.ref("routes", ev.route, owner, "route")
            if any(e.type == 'convoy_route' for e in ev.effects) and not ev.route:
                self.report(*owner, 'convoy_route needs a committed route')

    def check_services(self) -> None:
        for sid, svc in self.each("services"):
            assert isinstance(svc, s.ServiceNodeTemplate)
            owner = ("services", sid)
            if self.ref("zones", svc.zone, owner, "zone"):
                for obj in svc.target_objects:
                    if self.object_at(svc.zone, obj) is None:
                        self.report(*owner, f"target object {obj!r} does not exist in {svc.zone}", obj)
            self.ref("cores", svc.core, owner, "core")
            if svc.contract is not None and self.ref("contracts", svc.contract, owner, "contract"):
                job = self.t.contracts[svc.contract]
                if not job.service or job.story or job.crew_scaling:
                    self.report(*owner, "a work order must be a fixed, repeatable service contract")
            for label, effects in (("normal", svc.normal_effects), ("fault", svc.fault_effects)):
                for i, effect in enumerate(effects):
                    self._check_effect(owner, f"{label} effect {i}", effect)
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

    # --- presentation (proposal 68) ----------------------------------------

    def background(self, role: str | None, owner: tuple[str, str], what: str) -> None:
        if role is None:
            return
        self.role(role, owner, what)
        values = self.t.palette.roles.get(role, {}).get("16", {}) if self.t.palette else {}
        if any(type(v) is int and not 0 <= v <= 7 for v in values.values()):
            # Bright 16-colour backgrounds need blink or iCE colour; use reverse instead.
            self.report(*owner, f"{what}: background role {role!r} needs 16-colour values 0-7", role)

    def check_themes(self) -> None:
        if self.t.themes is None:
            return
        for tid, theme in sorted(self.t.themes.themes.items()):
            owner = ("themes", "themes")
            self.background(theme.ground_bg, owner, f"theme {tid} ground_bg")
            self.background(theme.wall_bg, owner, f"theme {tid} wall_bg")
            for role in (theme.ground_fg, theme.wall_fg):
                if role is not None:
                    self.role(role, owner, f"theme {tid}")
            if not theme.texture or set(theme.texture) - DRESSING_GRAIN:
                self.report(*owner, f"theme {tid}: texture may use only {''.join(sorted(DRESSING_GRAIN))!r}", tid)

    def check_looks(self) -> None:
        themes = self.t.themes.themes if self.t.themes else {}
        for lid, look in self.each("looks"):
            assert isinstance(look, s.Look)
            owner = ("looks", lid)
            zone = self.t.zones.get(lid)
            if zone is None:
                self.report(*owner, f"no zone {lid!r} to dress")
                continue
            tile = lambda x, y: zone.tile_at((x, y))
            for theme in (look.theme, *(r.theme for r in look.regions)):
                if theme not in themes:
                    self.report(*owner, f"theme {theme!r} does not exist", theme)
            for region in look.regions:
                if (region.rect is None) == (region.circle is None):
                    self.report(*owner, f"region {region.theme}: give exactly one of rect or circle", region.theme)
            for sign in look.signs:
                self.role(sign.role, owner, "sign")
                for i, char in enumerate(sign.text):
                    if char not in DRESSING_TEXT:
                        self.report(*owner, f"sign {sign.text.strip()!r}: {char!r} is not a dressing letter", sign.text)
                    elif tile(sign.at[0] + i, sign.at[1]) != "wall":
                        self.report(*owner, f"sign {sign.text.strip()!r} leaves the wall at {[sign.at[0] + i, sign.at[1]]}", sign.text)
                        break
            for mark in look.marks:
                self.role(mark.role, owner, "mark")
                if mark.line is not None:
                    (ax, ay), (bx, by) = mark.line
                    if (ax != bx and ay != by) or mark.glyph not in DRESSING_LINES:
                        self.report(*owner, f"mark line {list(mark.line)}: straight runs of ─ or │ only", mark.glyph)
                        continue
                    cells = [(x, ay) for x in range(min(ax, bx), max(ax, bx) + 1)] if ay == by else                             [(ax, y) for y in range(min(ay, by), max(ay, by) + 1)]
                elif mark.at is not None and mark.text:
                    if set(mark.text) - DRESSING_TEXT:
                        self.report(*owner, f"mark {mark.text!r}: dressing letters only", mark.text)
                    cells = [(mark.at[0] + i, mark.at[1]) for i in range(len(mark.text))]
                else:
                    self.report(*owner, "mark needs `at` and `text`, or `line` and `glyph`")
                    continue
                # Paint that covers a door, a terminal or cover would hide a rule.
                if any(tile(*cell) not in ("floor", "wall") for cell in cells):
                    self.report(*owner, f"mark {mark.text or mark.glyph!r} covers a tile that is not plain floor",
                                mark.text or None)
            if look.glint_role:
                self.role(look.glint_role, owner, "glint")
            for glint in look.glints:
                if tile(*glint) != "water":
                    self.report(*owner, f"glint {list(glint)} is not on water")
            for tid in look.names:
                if tid not in self.t.tiles:
                    self.report(*owner, f"name for unknown tile {tid!r}", tid)
            for place in look.places:
                x, y, w, h = place.rect
                anchor = place.at or (x + w // 2, y + h // 2)
                if zone.tile_at(anchor) in (None, "wall", "locked-door"):
                    self.report(*owner, f"place {place.name!r}: anchor {list(anchor)} is not open ground", place.name)
            for line in [*look.ambient, *(p.text for p in look.places)]:
                if "—" in line or len(line) > DIALOGUE_LINE_MAX:
                    self.report(*owner, f"ambient line {line[:30]!r}: no em-dash, at most {DIALOGUE_LINE_MAX} characters")

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
            for label, effects in (("normal", svc.normal_effects), ("fault", svc.fault_effects)):
                yield f"service {sid} {label}", ("services", sid), frozenset(
                    x for e in effects for x in e.exits_closed)
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
    for warning in exit_warnings(tree):
        print("warning: " + str(warning), file=sys.stderr)
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
