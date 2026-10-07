"""On-disk content formats: the `.map` grid, JSON records, assets.

Readers are pure: they take bytes or text and a path for messages, and
return records plus a list of `Problem`s. Nothing here logs, caches, or
touches global state, so the server can reload in a background task.

JSON is decoded into the dataclasses of `schema.py` by `decode`, which
checks every field against its type hint: required fields, unknown
keys, closed `Literal` sets, numbers, nested records. A failure names
the field path (`exits[2].kind`) and, where it can be found, the line.
"""

import json
import types
import typing
from dataclasses import MISSING, dataclass, fields, is_dataclass
from typing import Any, Literal, TypeVar, get_args, get_origin, get_type_hints

from blacksite.content import schema as s
from blacksite.content.ids import display_width
from blacksite.version import CONTENT_SCHEMA

T = TypeVar("T")


@dataclass(frozen=True)
class Problem:
    """One content error: the file, the line if known, and what is wrong."""

    path: str
    line: int | None
    message: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line is not None else self.path
        return f"{where}: {self.message}"


class DecodeError(ValueError):
    """A JSON value does not match the record type it is decoded into."""

    def __init__(self, where: str, message: str) -> None:
        super().__init__(f"{where}: {message}" if where else message)
        self.where = where
        self.message = message


# --- JSON decoding -----------------------------------------------------------


def _json_key(f: Any) -> str:
    return f.metadata.get("key", f.name)


def _describe(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 40 else text[:37] + "..."


def decode(cls: type[T], data: Any, where: str = "") -> T:
    """Decode a JSON value into `cls`, raising `DecodeError` on mismatch."""
    return _decode(cls, data, where)


def _decode(tp: Any, value: Any, where: str) -> Any:
    origin = get_origin(tp)
    if tp is Any or tp is object:
        return value
    if origin is Literal:
        if value not in get_args(tp):
            allowed = ", ".join(str(a) for a in get_args(tp))
            raise DecodeError(where, f"{_describe(value)} is not one of: {allowed}")
        return value
    if origin in (typing.Union, types.UnionType):
        arms = get_args(tp)
        if value is None:
            if type(None) in arms:
                return None
            raise DecodeError(where, "must not be null")
        errors: list[DecodeError] = []
        for arm in arms:
            if arm is type(None):
                continue
            try:
                return _decode(arm, value, where)
            except DecodeError as exc:
                errors.append(exc)
        if len(errors) == 1:
            raise errors[0]
        raise DecodeError(where, f"{_describe(value)} has the wrong type")
    if tp is bool:
        if not isinstance(value, bool):
            raise DecodeError(where, f"expected true or false, got {_describe(value)}")
        return value
    if tp is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise DecodeError(where, f"expected an integer, got {_describe(value)}")
        return value
    if tp is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DecodeError(where, f"expected a number, got {_describe(value)}")
        return value
    if tp is str:
        if not isinstance(value, str):
            raise DecodeError(where, f"expected a string, got {_describe(value)}")
        return value
    if tp is bytes:
        raise DecodeError(where, "bytes cannot come from JSON")
    if origin is tuple:
        if not isinstance(value, list):
            raise DecodeError(where, f"expected a list, got {_describe(value)}")
        args = get_args(tp)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode(args[0], v, f"{where}[{i}]") for i, v in enumerate(value))
        if len(value) != len(args):
            raise DecodeError(where, f"expected {len(args)} values, got {len(value)}")
        return tuple(_decode(a, v, f"{where}[{i}]") for i, (a, v) in enumerate(zip(args, value)))
    if origin is dict:
        if not isinstance(value, dict):
            raise DecodeError(where, f"expected an object, got {_describe(value)}")
        key_tp, val_tp = get_args(tp)
        out = {}
        for k, v in value.items():
            _decode(key_tp, k, f"{where}.{k}" if where else k)
            out[k] = _decode(val_tp, v, f"{where}.{k}" if where else k)
        return out
    if is_dataclass(tp):
        return _decode_record(tp, value, where)
    raise DecodeError(where, f"cannot decode type {tp!r}")


def _decode_record(cls: Any, value: Any, where: str) -> Any:
    if not isinstance(value, dict):
        raise DecodeError(where, f"expected an object, got {_describe(value)}")
    hints = get_type_hints(cls)
    known = {_json_key(f): f for f in fields(cls)}
    for key in value:
        if key not in known:
            raise DecodeError(_join(where, key), "unknown field")
    kwargs = {}
    for key, f in known.items():
        sub = _join(where, key)
        if key not in value:
            if f.default is MISSING and f.default_factory is MISSING:
                raise DecodeError(sub, "missing")
            continue
        kwargs[f.name] = _decode(hints[f.name], value[key], sub)
    record = cls(**kwargs)
    if "schema" in kwargs and kwargs["schema"] != CONTENT_SCHEMA:
        raise DecodeError(_join(where, "schema"), f"is {kwargs['schema']}, this build reads {CONTENT_SCHEMA}")
    return record


def _join(where: str, key: str) -> str:
    return f"{where}.{key}" if where else key


def find_line(text: str, *needles: str) -> int | None:
    """The 1-based line of the first needle found, trying them in order.

    JSON carries no positions after decoding, so problems that name a
    record locate it by searching for its `"id": "..."` text.
    """
    for needle in needles:
        index = text.find(needle)
        if index >= 0:
            return text.count("\n", 0, index) + 1
    return None


def id_needles(record_id: str) -> tuple[str, ...]:
    """Search strings that locate a record by its id in JSON text."""
    return (f'"id": "{record_id}"', f'"id":"{record_id}"', f'"{record_id}"')


def parse_json(text: str, path: str) -> tuple[Any, list[Problem]]:
    """Parse JSON text, turning a syntax error into a located Problem."""
    try:
        return json.loads(text), []
    except json.JSONDecodeError as exc:
        return None, [Problem(path, exc.lineno, f"invalid JSON: {exc.msg}")]


def _locate(text: str, where: str) -> int | None:
    """Best-effort line for a decode error path like `items[3].weapon.ammo`."""
    parts = [p for p in where.replace("]", "").replace("[", ".").split(".") if p]
    leaf = next((p for p in reversed(parts) if not p.isdigit()), None)
    return find_line(text, f'"{leaf}"') if leaf else None


def read_table(
    text: str, path: str, list_key: str, cls: type[T]
) -> tuple[list[T], dict[str, Any], list[Problem]]:
    """Read a table file `{"schema": 1, "<list_key>": [...]}`.

    Returns the decoded records (bad ones skipped), the other top-level
    keys, and problems.
    """
    data, problems = parse_json(text, path)
    if problems:
        return [], {}, problems
    if not isinstance(data, dict):
        return [], {}, [Problem(path, 1, "top level must be an object")]
    if data.get("schema") != CONTENT_SCHEMA:
        problems.append(Problem(path, find_line(text, '"schema"'), f"schema must be {CONTENT_SCHEMA}"))
    raw = data.get(list_key)
    if not isinstance(raw, list):
        problems.append(Problem(path, None, f'missing list "{list_key}"'))
        return [], data, problems
    records: list[T] = []
    for i, item in enumerate(raw):
        try:
            records.append(decode(cls, item, f"{list_key}[{i}]"))
        except DecodeError as exc:
            rid = item.get("id") if isinstance(item, dict) else None
            line = find_line(text, *id_needles(rid)) if isinstance(rid, str) else None
            problems.append(Problem(path, line or _locate(text, exc.where), str(exc)))
    return records, data, problems


def read_record(text: str, path: str, cls: type[T]) -> tuple[T | None, list[Problem]]:
    """Read a file that holds exactly one record."""
    data, problems = parse_json(text, path)
    if problems:
        return None, problems
    try:
        return decode(cls, data), []
    except DecodeError as exc:
        return None, [Problem(path, _locate(text, exc.where), str(exc))]


# --- the .map grid -----------------------------------------------------------


def split_map_lines(text: str) -> list[str]:
    """Split a map into rows. One final newline is allowed; `\\r\\n` line
    endings are accepted. Every other character, trailing spaces
    included, is part of the grid."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def parse_map(
    text: str, path: str, legend: dict[str, str]
) -> tuple[tuple[tuple[str, ...], ...] | None, list[Problem]]:
    """Parse a `.map` grid into rows of tile ids using `legend` (char to id).

    Every row must have the same width; every character must be a
    single-width glyph in the legend.
    """
    rows = split_map_lines(text)
    problems: list[Problem] = []
    if not rows:
        return None, [Problem(path, 1, "map is empty")]
    width = len(rows[0])
    grid: list[tuple[str, ...]] = []
    for n, row in enumerate(rows, start=1):
        if len(row) != width:
            problems.append(Problem(path, n, f"row is {len(row)} wide, the first row is {width}"))
        cells: list[str] = []
        for col, char in enumerate(row, start=1):
            if display_width(char) != 1:
                problems.append(Problem(path, n, f"column {col}: {char!r} is not one cell wide"))
                cells.append("")
            elif char not in legend:
                problems.append(Problem(path, n, f"column {col}: unknown glyph {char!r}"))
                cells.append("")
            else:
                cells.append(legend[char])
        grid.append(tuple(cells))
    if problems:
        return None, problems
    return tuple(grid), []


def dump_map(grid: tuple[tuple[str, ...], ...] | list[list[str]], chars: dict[str, str]) -> str:
    """Write a grid of tile ids back to `.map` text (tile id to char)."""
    return "".join("".join(chars[t] for t in row) + "\n" for row in grid)


# --- assets ----------------------------------------------------------------


def read_text_asset(asset_id: str, text: str, suffix: str) -> s.TextAsset:
    fmt: Literal["md", "txt"] = "md" if suffix == ".md" else "txt"
    return s.TextAsset(id=asset_id, body=text, format=fmt)


# File layout: table files at the root, one-record files in directories.
TABLE_FILES: dict[str, tuple[str, type]] = {
    "tiles.json": ("tiles", s.TileType),
    "items.json": ("items", s.ItemTemplate),
    "programs.json": ("programs", s.ProgramTemplate),
    "ice.json": ("ice", s.IceTemplate),
    "npcs.json": ("npcs", s.NpcTemplate),
    "factions.json": ("factions", s.Faction),
    "contracts.json": ("contracts", s.ContractTemplate),
    "events.json": ("events", s.EventTemplate),
    "routes.json": ("routes", s.Route),
    "vendors.json": ("vendors", s.Vendor),
    "hymns.json": ("hymns", s.HymnTemplate),
    "evidence.json": ("evidence", s.EvidenceRecord),
    "services.json": ("services", s.ServiceNodeTemplate),
}
"""Table file name to (list key and record kind, record type)."""

RECORD_DIRS: dict[str, type] = {
    "sectors": s.Sector,
    "cores": s.Core,
    "dialogue": s.DialogueNode,
    "seasons": s.SeasonDefinition,
    "bundles": s.Bundle,
}
"""Directories of one-record JSON files, named `<id>.json`."""

SINGLETON_FILES: dict[str, type] = {
    "glyphs.json": s.GlyphTable,
    "palette.json": s.Palette,
    "keymaps.json": s.KeymapTable,
}
