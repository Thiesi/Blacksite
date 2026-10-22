"""Pure player records and compact remembered terrain (entity 2.1)."""

import base64
from dataclasses import dataclass, field
from datetime import datetime
import json
import struct
from typing import Any
import zlib

from blacksite.content.schema import Tile
from blacksite.server.rules import character as rules
from blacksite.server.world.actors import Actor


def pack_memory(memory: dict[Tile, str], width: int, height: int) -> str:
    legend = sorted(set(memory.values()))
    indices = {key: index for index, key in enumerate(legend)}
    bits = bytearray((width * height + 7) // 8)
    terrain = bytearray()
    for y in range(height):
        for x in range(width):
            if (x, y) in memory:
                index = y * width + x
                bits[index // 8] |= 1 << (index % 8)
                terrain.extend(struct.pack(">H", indices[memory[x, y]]))
    value = [width, height, legend, base64.b64encode(bits).decode(), base64.b64encode(terrain).decode()]
    return base64.b64encode(zlib.compress(json.dumps(value, separators=(",", ":")).encode())).decode()


def unpack_memory(blob: str, width: int, height: int) -> dict[Tile, str]:
    w, h, legend, bitmap, cells = json.loads(zlib.decompress(base64.b64decode(blob)))
    if (w, h) != (width, height):
        return {}
    bits, terrain = base64.b64decode(bitmap), iter(struct.iter_unpack(">H", base64.b64decode(cells)))
    return {(x, y): legend[next(terrain)[0]] for y in range(h) for x in range(w)
            if bits[(y * w + x) // 8] & (1 << ((y * w + x) % 8))}


@dataclass
class Player:
    id: str
    origin: str
    bbs_user_id: str
    bbs_handle: str
    name: str
    archetype: str
    created_at: str
    zone: str = "vatside-wake-hall"
    tile: tuple[int, int] = (6, 5)
    attributes: dict[str, int] = field(default_factory=dict)
    skills: dict[str, float] = field(default_factory=dict)
    grade: int = 1
    xp: int = 0
    health: int = 0
    stamina: float = 0
    shock: float = 0
    chits_hand: int = rules.START_CHITS
    chits_bank: int = 0
    faction: str | None = None
    standing: dict[str, int] = field(default_factory=dict)
    equipment: dict[str, str] = field(default_factory=dict)
    implants: dict[str, str] = field(default_factory=dict)
    inventory: list[str] = field(default_factory=list)
    rig: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=lambda: {"keymap": "arrows"})
    progress: dict[str, Any] = field(default_factory=dict)
    legal_at: str | None = None
    clone_debt: int = 0
    last_seen_at: str | None = None
    facing: str = "down"
    marked_until: str | None = None
    warden_heat_until: str | None = None
    drugs_active: list[Any] = field(default_factory=list)
    dependencies: list[Any] = field(default_factory=list)
    apartment_id: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    recovery_kit_id: str | None = None
    listened_enabled: bool = False

    def __post_init__(self) -> None:
        self.tile = tuple(self.tile)
        if not self.skills:
            self.skills = {line: 0 for _, lines in rules.SKILL_GROUPS for line in lines}
        if not self.attributes:
            self.attributes = rules.attributes(self.archetype, self.skills, self.grade)

    @classmethod
    def from_record(cls, row: dict[str, Any]) -> "Player":
        return cls(**{key: value for key, value in row.items() if key in cls.__dataclass_fields__ and value is not None or key in ("legal_at",)})

    def record(self) -> dict[str, Any]:
        from dataclasses import asdict
        return {**asdict(self), "name_key": rules.name_key(self.name)}

    def actor(self) -> Actor:
        return Actor(self.id, self.name, self.bbs_handle, health=self.health,
                     health_max=rules.health_max(self.attributes["vitals"]), stamina=self.stamina,
                     stamina_max=rules.stamina_max(self.attributes["nerve"], self.attributes["frame"]),
                     shock=self.shock, faction=self.faction, facing=self.facing)

    def summary(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "handle": self.bbs_handle, "archetype": self.archetype,
                "grade": self.grade, "faction": self.faction, "settings": self.settings}

    def update_progression(self, xp: int) -> None:
        """Apply grade benefits once; S16 owns eligible XP and use receipts."""
        grade = rules.grade_for(xp, self.grade)
        self.progress["points"] = self.progress.get("points", 0) + (grade - self.grade) * rules.POINTS_PER_GRADE
        self.grade, self.xp = grade, xp
        self.attributes = rules.attributes(self.archetype, self.skills, grade)

    def update_personhood(self, identity: dict[str, Any], now: datetime) -> None:
        identity["legal_at"] = rules.legal_at(datetime.fromisoformat(identity["first_decanted_at"]), self.grade, now, identity.get("legal_at"))
        self.legal_at = identity["legal_at"]
