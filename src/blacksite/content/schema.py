"""Typed records for every content file (01-entities.md section 1).

Every record is a frozen dataclass. JSON keys equal the field names,
except where a field's metadata names a `key` (`class` is a Python
keyword). Closed sets are `Literal` types, so the decoder in
`formats.py` rejects any value outside them. Optional fields have
defaults; required ones do not.

These are content records only. Persistent state (01-entities.md
section 2) and live simulation state (section 3) belong to the server.
"""

from dataclasses import dataclass, field
from typing import Literal

from blacksite.version import CONTENT_SCHEMA

Tile = tuple[int, int]
"""A tile position `[x, y]`, zero-based from the top-left of the map."""

Number = int | float

# --- shared enums --------------------------------------------------------

Safety = Literal["safe", "pocket", "contested", "open"]
Relation = Literal["H", "N", "A"]
Tier = Literal["truecolor", "256", "16"]
PaletteVariant = Literal["default", "deutan", "protan"]
VoiceTag = Literal["CUST", "TEN"]
DamageType = Literal["kinetic", "energy", "chemical", "dissonance"]
TimerBasis = Literal["wall", "uptime"]
BundleStatus = Literal["active", "authoring"]

TIERS: tuple[Tier, ...] = ("truecolor", "256", "16")
VARIANTS: tuple[PaletteVariant, ...] = ("default", "deutan", "protan")


def _key(name: str) -> dict[str, str]:
    return {"key": name}


# --- terminal tables (03-terminal-ui.md sections 1 and 5) -----------------


@dataclass(frozen=True)
class GlyphTable:
    """`glyphs.json`: the fixed glyph registry, glyph id to character."""

    glyphs: dict[str, str]
    schema: int = CONTENT_SCHEMA


@dataclass(frozen=True)
class Palette:
    """`palette.json`: role to tier to variant to colour value.

    Values are `#rrggbb` for truecolor, 0-255 for 256, 0-15 for 16
    (8-15 are drawn as bold-bright). Content never names a colour
    directly, only a role.
    """

    roles: dict[str, dict[Tier, dict[PaletteVariant, str | int]]]
    schema: int = CONTENT_SCHEMA


KeyContext = Literal["any", "zone", "lattice"]


@dataclass(frozen=True)
class KeyAction:
    context: KeyContext
    label: str


@dataclass(frozen=True)
class Keymap:
    id: str
    label: str
    bindings: dict[str, tuple[str, ...]]
    """Action id to normalised key names."""


@dataclass(frozen=True)
class KeymapTable:
    """`keymaps.json`: the action catalogue and the shipped keymaps."""

    actions: dict[str, KeyAction]
    keymaps: tuple[Keymap, ...]
    schema: int = CONTENT_SCHEMA


# --- tiles and zones (01-entities.md sections 1.1 and 1.2) ----------------

ObjectKind = Literal[
    "door", "terminal", "vendor", "vat", "relay", "cache", "tram_stop",
    "apartment_door", "light", "hardware", "descent_console", "workshop",
    "bank",
]


@dataclass(frozen=True)
class Hazard:
    damage_per_second: Number
    type: DamageType


@dataclass(frozen=True)
class TileType:
    id: str
    char: str
    """The single character that stands for this tile in `.map` files."""
    glyph: str
    """Glyph id in `glyphs.json` used to draw it."""
    colour: str
    """Palette role."""
    passable: bool
    cover: int = 0
    opaque: bool = False
    hazard: Hazard | None = None
    interaction: ObjectKind | None = None
    sound_line: str | None = None
    schema: int = CONTENT_SCHEMA


@dataclass(frozen=True)
class TileTable:
    """`tiles.json`."""

    tiles: tuple[TileType, ...]
    schema: int = CONTENT_SCHEMA


ExitKind = Literal["street", "tram", "ladder", "lift", "gate", "cable"]
RequirementKind = Literal["pass", "key", "faction"]


@dataclass(frozen=True)
class Requirement:
    kind: RequirementKind
    ref: str
    """Item id for pass and key, faction id for faction."""
    standing: int | None = None


@dataclass(frozen=True)
class Exit:
    id: str
    tile: Tile
    target_zone: str
    target_tile: Tile
    kind: ExitKind
    requirement: Requirement | None = None
    hidden: bool = False
    """Revealed by Listening, a program or dialogue (01-gazetteer.md)."""


@dataclass(frozen=True)
class Region:
    """An inclusive rectangle of tiles."""

    x: int
    y: int
    w: int
    h: int

    def tiles(self) -> list[Tile]:
        return [
            (x, y)
            for y in range(self.y, self.y + self.h)
            for x in range(self.x, self.x + self.w)
        ]


@dataclass(frozen=True)
class Spawner:
    id: str
    npc: str
    count: int
    respawn_seconds: int
    tile: Tile | None = None
    region: Region | None = None
    condition: str | None = None


@dataclass(frozen=True)
class ObjectSpec:
    id: str
    tile: Tile
    kind: ObjectKind
    params: dict[str, object] = field(default_factory=dict)
    essential: bool = False
    """Clinics, public vats, public uplinks: no control or event may
    deny them (01-entities.md section 5)."""


@dataclass(frozen=True)
class ZoneMeta:
    """The `.json` sidecar of a zone, everything except the grid."""

    id: str
    name: str
    district: str
    safety: Safety
    sight_radius: int
    lean: str | None = None
    sight_radius_night: int | None = None
    exits: tuple[Exit, ...] = ()
    spawners: tuple[Spawner, ...] = ()
    objects: tuple[ObjectSpec, ...] = ()
    pockets: tuple[Region, ...] = ()
    lore: tuple[str, ...] = ()
    instanced: bool = False
    schema: int = CONTENT_SCHEMA


@dataclass(frozen=True)
class Zone:
    """A loaded zone: sidecar plus the grid of tile ids from its `.map`."""

    meta: ZoneMeta
    grid: tuple[tuple[str, ...], ...]

    @property
    def id(self) -> str:
        return self.meta.id

    @property
    def width(self) -> int:
        return len(self.grid[0]) if self.grid else 0

    @property
    def height(self) -> int:
        return len(self.grid)

    def tile_at(self, tile: Tile) -> str | None:
        x, y = tile
        if 0 <= y < self.height and 0 <= x < self.width:
            return self.grid[y][x]
        return None


# --- the Lattice (sections 1.3 to 1.6) -------------------------------------

CellKind = Literal["public", "gated", "hidden", "core_entrance", "descent"]


@dataclass(frozen=True)
class Cell:
    id: str
    kind: CellKind
    pos: Tile
    """Grid position on the sector view (03-terminal-ui.md section 3)."""
    neighbours: tuple[str, ...]
    label: str
    requirement: str | None = None
    core_id: str | None = None
    lore: tuple[str, ...] = ()


@dataclass(frozen=True)
class Sector:
    id: str
    district: str
    cells: tuple[Cell, ...]
    schema: int = CONTENT_SCHEMA


DataKind = Literal[
    "chits", "salvage_data", "contribution", "contract_key", "schematic", "text",
]


@dataclass(frozen=True)
class DataSpec:
    id: str
    kind: DataKind
    respawn_seconds: int
    amount: int | None = None
    asset: str | None = None


ControlAction = Literal["open", "close", "disable", "enable", "toggle", "call"]
ControlScope = Literal["public", "mission", "private_vestibule", "expedition"]
ControlPermission = Literal["public", "contract", "member", "owner", "resident"]
SafetyPolicy = Literal["none", "route", "hazard"]
"""`route`: the control can close travel and must name an alternate
route. `hazard`: the control can create a hazard and may not target a
safe zone or pocket."""


@dataclass(frozen=True)
class ControlTarget:
    zone: str
    object: str


@dataclass(frozen=True)
class ControlSpec:
    id: str
    label: str
    target: ControlTarget
    action: ControlAction
    reset_seconds: int
    scope: ControlScope = "public"
    permission: ControlPermission = "public"
    safety_policy: SafetyPolicy = "none"
    owner_policy: bool = False
    warning_seconds: int = 0
    alternate_route: str | None = None
    """Exit id in the target zone that stays open while this one is shut."""
    revision: int = 1


@dataclass(frozen=True)
class Room:
    id: str
    neighbours: tuple[str, ...]
    data: tuple[DataSpec, ...] = ()
    controls: tuple[ControlSpec, ...] = ()
    ice: tuple[str, ...] = ()
    lore: tuple[str, ...] = ()


@dataclass(frozen=True)
class HardwareLocation:
    zone: str
    tile: Tile


@dataclass(frozen=True)
class Core:
    id: str
    name: str
    owner: str
    """Faction id or `private`."""
    tier: int
    hardware: tuple[HardwareLocation, ...]
    rooms: tuple[Room, ...]
    training: bool = False
    """The Wake training core: the only core allowed tier 0."""
    schema: int = CONTENT_SCHEMA


IceTrigger = Literal["entry", "data", "trace", "timer", "touch", "passage", "always"]
IceBehaviour = Literal["static", "roaming", "hunter"]
IceRole = Literal["gate", "alarm", "patrol", "deception", "displacement", "feedback"]
"""The readable role Inspect shows (00-game-design.md section 6.6)."""
ProgramClass = Literal["attack", "shield", "decoy", "loader", "key", "stealth", "utility"]


@dataclass(frozen=True)
class IceTemplate:
    id: str
    name: str
    class_: str = field(metadata=_key("class"))
    """Bestiary class, such as `tripwire` (03-lattice.md)."""
    role: IceRole = "alarm"
    tier: int = 1
    integrity: int = 1
    attack: int = 0
    cast_seconds: Number = 0
    cooldown_seconds: Number = 0
    trigger: IceTrigger = "entry"
    trigger_trace: int | None = None
    """Threshold when `trigger` is `trace`."""
    behaviour: IceBehaviour = "static"
    black: bool = False
    meat_damage: int = 0
    counters: tuple[ProgramClass, ...] = ()
    variants: tuple[str, ...] = ()
    """ICE ids a Choir Surge may swap in: non-black, equal or lower tier
    (00-game-design.md section 12)."""
    lore: tuple[str, ...] = ()
    schema: int = CONTENT_SCHEMA


ProgramEffectKind = Literal[
    "damage", "area_damage", "absorb", "trace", "cast_speed", "move_speed",
    "open_gate", "stealth", "reveal", "restore", "immunity", "decoy",
    "passive", "programs_bonus",
]
ProgramTarget = Literal["self", "ice", "room", "runner", "cell", "crew"]


@dataclass(frozen=True)
class ProgramEffect:
    kind: ProgramEffectKind
    amount: Number = 0
    params: dict[str, Number | str | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class ProgramTemplate:
    id: str
    name: str
    class_: ProgramClass = field(metadata=_key("class"))
    tier: int = 1
    slots: int = 1
    cast_seconds: Number | None = 0
    """None for passive programs (Ledger)."""
    cooldown_seconds: Number | None = 0
    """None for passive or single-use programs."""
    effect: ProgramEffect = field(default_factory=lambda: ProgramEffect("passive"))
    source: str = ""
    price: int = 0
    acquisition_requires: tuple[str, ...] = ()
    cast_requires: tuple[str, ...] = ()
    trace_cost: int = 0
    target_class: ProgramTarget = "self"
    duration: Number = 0
    stacking_group: str | None = None
    schema: int = CONTENT_SCHEMA


# --- items (section 1.7) ---------------------------------------------------

ItemClass = Literal[
    "weapon", "armour", "ammo", "implant", "resonance", "rig", "drug",
    "consumable", "drone", "salvage", "schematic", "key", "pass", "data",
    "misc",
]
ArmourSlot = Literal["body", "head", "legs", "hands"]
ImplantSlot = Literal["eyes", "arms", "legs", "spine", "skin", "cortex", "ears", "throat", "rig"]


@dataclass(frozen=True)
class DamageOverTime:
    per_second: int
    seconds: Number


@dataclass(frozen=True)
class WeaponBlock:
    damage: int
    cooldown: Number
    accuracy: int
    damage_type: DamageType
    range: int | None = None
    """None for melee."""
    ammo: str | None = None
    melee: bool = False
    heavy: bool = False
    stamina: int | None = None
    """Stamina per swing, melee only."""
    dot: DamageOverTime | None = None
    shock: int = 0


@dataclass(frozen=True)
class ArmourValues:
    kinetic: int = 0
    energy: int = 0
    chemical: int = 0
    dissonance: int = 0


@dataclass(frozen=True)
class ArmourBlock:
    slot: ArmourSlot
    armour: ArmourValues
    evasion: int = 0
    heavy: bool = False


@dataclass(frozen=True)
class AmmoBlock:
    recharge_price: int | None = None
    """Chits to recharge at a terminal, energy cells only."""


@dataclass(frozen=True)
class ImplantRequires:
    archetype: str | None = None
    faction: str | None = None
    standing: int | None = None


@dataclass(frozen=True)
class ImplantBlock:
    slot: ImplantSlot
    tolerance: int
    effects: dict[str, Number] = field(default_factory=dict)
    requires: ImplantRequires | None = None
    rig_slots: int | None = None


@dataclass(frozen=True)
class DrugBlock:
    effects: dict[str, Number]
    duration: Number
    crash: dict[str, Number]
    addiction_window: Number
    addiction_doses: int = 3


@dataclass(frozen=True)
class ConsumableBlock:
    effects: dict[str, Number]
    cooldown_class: str
    use_seconds: Number = 0
    uses: int = 1


@dataclass(frozen=True)
class DroneBlock:
    health: int
    speed: Number
    sight: int
    weapon: str | None = None
    tool: str | None = None


@dataclass(frozen=True)
class SalvageBlock:
    grade: str


@dataclass(frozen=True)
class SchematicBlock:
    output: str
    inputs: dict[str, int]
    skill_min: int = 0


@dataclass(frozen=True)
class ItemTemplate:
    id: str
    name: str
    class_: ItemClass = field(metadata=_key("class"))
    tier: int = 1
    weight: Number = 0
    base_price: int = 0
    secured_default: bool = False
    description: str = ""
    """Inline catalog line (04-assets.md section 1)."""
    stack_max: int = 1
    maker: str | None = None
    weapon: WeaponBlock | None = None
    armour: ArmourBlock | None = None
    ammo: AmmoBlock | None = None
    implant: ImplantBlock | None = None
    drug: DrugBlock | None = None
    consumable: ConsumableBlock | None = None
    drone: DroneBlock | None = None
    salvage: SalvageBlock | None = None
    schematic: SchematicBlock | None = None
    schema: int = CONTENT_SCHEMA


ITEM_BLOCKS: dict[str, str] = {
    "weapon": "weapon",
    "armour": "armour",
    "ammo": "ammo",
    "implant": "implant",
    "resonance": "implant",
    "rig": "implant",
    "drug": "drug",
    "consumable": "consumable",
    "drone": "drone",
    "salvage": "salvage",
    "schematic": "schematic",
}
"""Item class to the name of the block it must carry. Classes not listed
(key, pass, data, misc) carry no block."""


@dataclass(frozen=True)
class HymnTemplate:
    id: str
    name: str
    kind: Literal["hymn", "dissonance"]
    tier: int
    cast_seconds: Number
    cooldown_seconds: Number
    effect: dict[str, Number | str] = field(default_factory=dict)
    description: str = ""
    schema: int = CONTENT_SCHEMA


VendorTier = Literal["list", "member", "restricted"]


@dataclass(frozen=True)
class VendorStock:
    item: str
    standing: int | None = None


@dataclass(frozen=True)
class Vendor:
    id: str
    name: str
    tier: VendorTier
    stock: tuple[VendorStock, ...]
    faction: str | None = None
    zone: str | None = None
    schema: int = CONTENT_SCHEMA


# --- NPCs and factions (sections 1.8 and 1.9) ------------------------------

BehaviourKind = Literal["idle", "patrol", "guard", "aggro", "flee", "vendor", "talker", "warden"]


@dataclass(frozen=True)
class Attributes:
    frame: int
    nerve: int
    cortex: int
    resonance: int
    vitals: int


@dataclass(frozen=True)
class Behaviour:
    kind: BehaviourKind
    params: dict[str, Number | str | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class LootEntry:
    item: str
    chance: Number
    count: int = 1


@dataclass(frozen=True)
class NpcTemplate:
    id: str
    name: str
    grade: int
    attributes: Attributes
    faction: str | None = None
    weapon: str | None = None
    armour: str | None = None
    behaviours: tuple[Behaviour, ...] = ()
    dialogue: str | None = None
    vendor: str | None = None
    loot: tuple[LootEntry, ...] = ()
    xp: int = 0
    lore: tuple[str, ...] = ()
    schema: int = CONTENT_SCHEMA


@dataclass(frozen=True)
class Rank:
    standing: int
    title: str


@dataclass(frozen=True)
class VatLocation:
    zone: str
    tile: Tile


@dataclass(frozen=True)
class Faction:
    id: str
    name: str
    short: str
    colour: str
    """Palette role."""
    relations: dict[str, Relation]
    hall: str | None = None
    vat: VatLocation | None = None
    recruiter: str | None = None
    ranks: tuple[Rank, ...] = ()
    vendor: str | None = None
    contracts: tuple[str, ...] = ()
    schema: int = CONTENT_SCHEMA


@dataclass(frozen=True)
class FactionTable:
    """`factions.json`: the factions and the declared asymmetries.

    `asymmetries` lists the unordered pairs whose relation differs by
    direction; the validator requires it to be exactly the set the
    matrix contains (00-game-design.md section 7.2).
    """

    factions: tuple[Faction, ...]
    asymmetries: tuple[tuple[str, str], ...] = ()
    schema: int = CONTENT_SCHEMA


# --- contracts, evidence, services (sections 1.10, 2.12, 2.13) -------------

ContractVerb = Literal["fetch", "hack", "escort", "clear", "plant", "survey"]
InputAction = Literal["inspect", "carry", "interact", "wait", "channel", "lift", "flip", "enter"]
TargetKind = Literal["zone_object", "zone_tile", "core_room", "core_control", "npc", "item", "cell"]
StandingMode = Literal["propagate", "explicit"]
PermitKind = Literal["patrol_window", "maintenance_credential", "route", "recipient"]


@dataclass(frozen=True)
class StageTarget:
    kind: TargetKind
    zone: str | None = None
    object: str | None = None
    tile: Tile | None = None
    core: str | None = None
    room: str | None = None
    control: str | None = None
    npc: str | None = None
    item: str | None = None
    sector: str | None = None
    cell: str | None = None


@dataclass(frozen=True)
class Stage:
    id: str
    verb: ContractVerb
    target: StageTarget
    input: InputAction
    completion: str
    receipt_key: str
    retry: bool = True
    resolution: Literal["lethal", "subdue"] | None = None
    """Required for `clear` stages."""


@dataclass(frozen=True)
class Reward:
    chits: tuple[int, int] = (0, 0)
    standing: dict[str, int] = field(default_factory=dict)
    standing_mode: StandingMode = "propagate"
    xp: int = 0
    items: tuple[str, ...] = ()


@dataclass(frozen=True)
class Permit:
    kind: PermitKind
    target: str
    expiry_seconds: int


@dataclass(frozen=True)
class PublicationOption:
    id: str
    label: str
    audience: Literal["handler", "faction", "public"]
    reward: Reward = field(default_factory=Reward)


@dataclass(frozen=True)
class ContractTemplate:
    id: str
    giver: str = field(metadata=_key("faction"))
    """Faction id or `vesper`."""
    type: ContractVerb = "fetch"
    stages: tuple[Stage, ...] = ()
    params: dict[str, object] = field(default_factory=dict)
    reward: Reward = field(default_factory=Reward)
    min_grade: int = 0
    crew_scaling: bool = True
    story: bool = False
    season: int | None = None
    chain: str | None = None
    branch_group: str | None = None
    branch: str | None = None
    """This contract's outcome key within `branch_group`."""
    permit_scope: Permit | None = None
    publication_options: tuple[PublicationOption, ...] = ()
    evidence_assets: tuple[str, ...] = ()
    unlock_conditions: tuple[str, ...] = ()
    schema: int = CONTENT_SCHEMA


@dataclass(frozen=True)
class EvidenceRecord:
    """`evidence.json`: what a journal record shows when acquired.

    Observation, source and claim are separate fields (04-assets.md
    section 9); the source's claim is never presented as the finding.
    """

    id: str
    asset: str
    observation: str
    source: str
    claim: str
    related_objective: str | None = None
    schema: int = CONTENT_SCHEMA


EffectType = Literal[
    "hazard", "spawn_multiplier", "entry_restriction", "ice_variant",
    "salvage", "route_hold", "price_modifier", "reveal", "cache",
]


@dataclass(frozen=True)
class Effect:
    """A typed event or service effect. `zone` plus optional `region`
    scope physical effects; `sector` scopes Lattice ones."""

    type: EffectType
    zone: str | None = None
    region: Region | None = None
    sector: str | None = None
    warning_seconds: int = 0
    exits_closed: tuple[str, ...] = ()
    """For `entry_restriction` and `route_hold`: exit ids, as
    `zone/exit`, that the effect closes."""
    params: dict[str, Number | str | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class Allocation:
    id: Literal["common", "reserve"]
    label: str
    effects: tuple[Effect, ...] = ()


@dataclass(frozen=True)
class ServiceNodeTemplate:
    """`services.json`: an authored public service (00-game-design.md
    section 7.5). Live state is the server's `ServiceNode`."""

    id: str
    name: str
    zone: str
    core: str
    target_objects: tuple[str, ...]
    allocations: tuple[Allocation, ...]
    schema: int = CONTENT_SCHEMA


# --- dialogue (section 1.11, 04-dramatis-personae.md Part III) -------------

DIALOGUE_CONDITIONS: dict[str, tuple[str, ...]] = {
    "first_meeting": (),
    "grade_below": ("N",),
    "grade_at_least": ("N",),
    "is_wake": (),
    "standing_below": ("FACTION", "N"),
    "standing_at_least": ("FACTION", "N"),
    "member_of": ("FACTION",),
    "not_member_of": ("FACTION",),
    "enemy_of_me": (),
    "marked": (),
    "not_marked": (),
    "has_contract": ("CONTRACT",),
    "contract_stage": ("CONTRACT", "N"),
    "completed_contract": ("CONTRACT",),
    "has_item": ("ITEM",),
    "season_stage": ("STAGE",),
    "chronicle_choice": ("N", "OPTION"),
    "event_active": ("EVENT",),
    "archetype": ("ARCH",),
    "balance": ("BALANCE",),
    "has_evidence": ("EVIDENCE",),
    "receipt": ("RECEIPT",),
    "service_state": ("SERVICE", "STATE"),
    "legal": (),
    "not_legal": (),
}
"""The closed condition set and each condition's argument kinds."""

SEASON_STAGES = ("open", "level_open", "finale_done")
BALANCES = ("CUST", "TEN", "EVEN")
SERVICE_STATES = ("normal", "fault", "repairing", "allocated")
ARCHETYPES = ("hardline", "ghost", "cantor", "operator")

OfferKind = Literal["contract", "vendor", "service", "recruit", "travel"]


@dataclass(frozen=True)
class DialogueLine:
    id: str
    text: str
    when: tuple[str, ...] = ()
    tag: VoiceTag | None = None
    required: bool = False
    """Never skipped by the balance weighting (00-game-design.md 13.4)."""


@dataclass(frozen=True)
class Offer:
    kind: OfferKind
    label: str
    hotkey: str
    ref: str
    when: tuple[str, ...] = ()


@dataclass(frozen=True)
class Bark:
    text: str
    weight: int = 1
    min_interval_seconds: int = 90


@dataclass(frozen=True)
class DialogueNode:
    """`dialogue/<id>.json`: one talker."""

    id: str
    name: str
    lines: tuple[DialogueLine, ...]
    faction: str | None = None
    title: str = ""
    offers: tuple[Offer, ...] = ()
    barks: tuple[Bark, ...] = ()
    terminal: bool = False
    machine_mind: bool = False
    """Scripted machine-mind encounters need a line in each voice."""
    schema: int = CONTENT_SCHEMA


# --- events, routes, seasons (sections 1.12, 1.13, 2.14, 2.15) -------------


@dataclass(frozen=True)
class Announce:
    start: str | None = None
    mid: str | None = None
    end: str | None = None


@dataclass(frozen=True)
class EventVariant:
    id: str
    effects: tuple[Effect, ...]


@dataclass(frozen=True)
class EventTemplate:
    id: str
    name: str
    where: tuple[str, ...]
    """Zone or sector ids."""
    duration_seconds: int
    cooldown_seconds: int
    weight: int
    basis: TimerBasis = "wall"
    effects: tuple[Effect, ...] = ()
    variants: tuple[EventVariant, ...] = ()
    announce: Announce = field(default_factory=Announce)
    route: str | None = None
    schema: int = CONTENT_SCHEMA


@dataclass(frozen=True)
class Waypoint:
    zone: str
    tile: Tile


@dataclass(frozen=True)
class Route:
    id: str
    waypoints: tuple[Waypoint, ...]
    speed: Number
    schema: int = CONTENT_SCHEMA


@dataclass(frozen=True)
class FinaleChoice:
    id: str
    label: str
    chronicle: str
    """Text asset id."""
    balance_delta: int
    standing: dict[str, int] = field(default_factory=dict)
    condition: str | None = None


@dataclass(frozen=True)
class FinaleLine:
    text: str
    """Text asset id."""
    tag: VoiceTag
    guaranteed: bool = True


@dataclass(frozen=True)
class SeasonLevel:
    zone: str
    sector: str


@dataclass(frozen=True)
class RelationOverride:
    a: str
    b: str
    value: Relation


@dataclass(frozen=True)
class SeasonDefinition:
    number: int
    title: str
    depth_target: int
    contribution_weights: dict[str, int]
    level: SeasonLevel
    phases: tuple[str, ...]
    """Expedition checkpoint ids, in order."""
    finale_choices: tuple[FinaleChoice, ...]
    finale_lines: tuple[FinaleLine, ...] = ()
    relations_override: tuple[RelationOverride, ...] = ()
    story_chains: tuple[str, ...] = ()
    schema: int = CONTENT_SCHEMA


# --- assets (sections 1.14 and 1.15) ----------------------------------------


@dataclass(frozen=True)
class TextAsset:
    id: str
    body: str
    format: Literal["md", "txt"]


@dataclass(frozen=True)
class ArtMeta:
    """The JSON sidecar of an `.ans` art block."""

    width: int
    height: int
    min_tier: Tier = "16"
    variants: tuple[str, ...] = ()
    """Art asset ids of the tier or width variants."""
    schema: int = CONTENT_SCHEMA


@dataclass(frozen=True)
class ArtAsset:
    id: str
    meta: ArtMeta
    data: bytes


# --- bundles (02-architecture.md section 15.3) ------------------------------

BUNDLE_KINDS = (
    "zones", "sectors", "cores", "items", "programs", "ice", "npcs",
    "factions", "contracts", "events", "routes", "seasons", "dialogue",
    "text", "art", "evidence", "services", "vendors", "hymns",
)


@dataclass(frozen=True)
class Bundle:
    """`bundles/<id>.json`: a named set of content with a status.

    Content no bundle lists is base content and always active. An
    `authoring` bundle may hold unresolved references; nothing active
    may reference into it, and an active bundle may depend only on
    active bundles.
    """

    id: str
    status: BundleStatus
    members: dict[str, tuple[str, ...]]
    depends: tuple[str, ...] = ()
    schema: int = CONTENT_SCHEMA
