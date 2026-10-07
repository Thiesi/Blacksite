"""Load a content tree from disk (02-architecture.md sections 2.4, 6.3).

`load_content(root, local)` reads the shipped tree and, if given, the
operator's `content.local/` tree, which wins on ID collision. Loading
never raises for bad content: unreadable or ill-typed records are
skipped and reported in `ContentTree.load_problems`, and `validate`
reports them with everything else. The loader is pure: no logging, no
globals, no clock.

Override rules:

- Table records (`items.json` and the like) merge by `id`.
- One-record files (`sectors/<id>.json`, `cores/<id>.json`, ...) and
  assets replace by file name. A zone is its `.map` and `.json` as a
  pair; a local zone must supply both.
- `glyphs.json` and `palette.json` merge by glyph id and role;
  `keymaps.json` merges actions by id and keymaps by id.
- A local `factions.json` that has an `asymmetries` list replaces the
  shipped list, since the declared set describes the merged matrix.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from blacksite.content import schema as s
from blacksite.content.formats import (
    RECORD_DIRS,
    SINGLETON_FILES,
    TABLE_FILES,
    Problem,
    find_line,
    id_needles,
    parse_map,
    read_record,
    read_table,
    read_text_asset,
)
from blacksite.content.ids import valid_id

# Files in a content tree that are not content (the shipped tree is
# also a Python package).
_IGNORED_NAMES = frozenset({"README.md", "__init__.py"})
_IGNORED_DIRS = frozenset({"__pycache__"})
_IGNORED_SUFFIXES = frozenset({".py", ".pyc"})

# Record kinds whose ids follow the catalog rule (ids.CATALOG_KINDS).
_ID_KIND = {
    "items": "item",
    "programs": "program",
    "ice": "ice",
    "hymns": "hymn",
}


@dataclass
class ContentTree:
    """Everything loaded from one shipped tree plus optional overrides.

    `sources` maps `(kind, id)` to the relative path the winning record
    came from (`content/zones/fx-safe.json`), and `texts` maps that
    path to its text, so the validator can name files and lines.
    """

    root: Path
    local: Path | None
    hash: str = ""
    glyphs: s.GlyphTable | None = None
    palette: s.Palette | None = None
    keymaps: s.KeymapTable | None = None
    tiles: dict[str, s.TileType] = field(default_factory=dict)
    zones: dict[str, s.Zone] = field(default_factory=dict)
    sectors: dict[str, s.Sector] = field(default_factory=dict)
    cores: dict[str, s.Core] = field(default_factory=dict)
    items: dict[str, s.ItemTemplate] = field(default_factory=dict)
    programs: dict[str, s.ProgramTemplate] = field(default_factory=dict)
    ice: dict[str, s.IceTemplate] = field(default_factory=dict)
    npcs: dict[str, s.NpcTemplate] = field(default_factory=dict)
    factions: dict[str, s.Faction] = field(default_factory=dict)
    asymmetries: tuple[tuple[str, str], ...] = ()
    contracts: dict[str, s.ContractTemplate] = field(default_factory=dict)
    events: dict[str, s.EventTemplate] = field(default_factory=dict)
    routes: dict[str, s.Route] = field(default_factory=dict)
    vendors: dict[str, s.Vendor] = field(default_factory=dict)
    hymns: dict[str, s.HymnTemplate] = field(default_factory=dict)
    evidence: dict[str, s.EvidenceRecord] = field(default_factory=dict)
    services: dict[str, s.ServiceNodeTemplate] = field(default_factory=dict)
    dialogue: dict[str, s.DialogueNode] = field(default_factory=dict)
    seasons: dict[str, s.SeasonDefinition] = field(default_factory=dict)
    """Keyed by the season number as a string, the file name."""
    bundles: dict[str, s.Bundle] = field(default_factory=dict)
    text: dict[str, s.TextAsset] = field(default_factory=dict)
    art: dict[str, s.ArtAsset] = field(default_factory=dict)
    sources: dict[tuple[str, str], str] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)
    load_problems: list[Problem] = field(default_factory=list)

    def source(self, kind: str, record_id: str) -> str:
        """The relative path a record came from, or a placeholder."""
        return self.sources.get((kind, record_id), f"<{kind}:{record_id}>")


def content_files(root: Path) -> list[Path]:
    """Every content file under `root`, sorted by relative POSIX path."""
    found = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in _IGNORED_DIRS for part in rel.parts):
            continue
        if path.name in _IGNORED_NAMES or path.suffix in _IGNORED_SUFFIXES:
            continue
        found.append(path)
    return sorted(found, key=lambda p: p.relative_to(root).as_posix())


def content_hash(root: Path, local: Path | None = None) -> str:
    """SHA-256 over every content file's layer, relative path, and bytes.

    Files are taken in sorted path order, so the hash does not depend on
    the order the filesystem lists them in.
    """
    digest = hashlib.sha256()
    for layer, base in (("content", root), ("content.local", local)):
        if base is None or not base.is_dir():
            continue
        for path in content_files(base):
            rel = f"{layer}/{path.relative_to(base).as_posix()}".encode("utf-8")
            data = path.read_bytes()
            digest.update(len(rel).to_bytes(4, "big") + rel)
            digest.update(len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


class _Layer:
    """One directory of content and the label its paths are shown with."""

    def __init__(self, base: Path, label: str) -> None:
        self.base = base
        self.label = label

    def rel(self, path: Path) -> str:
        return f"{self.label}/{path.relative_to(self.base).as_posix()}"

    def file(self, name: str) -> Path | None:
        path = self.base / name
        return path if path.is_file() else None

    def dir(self, name: str, suffixes: tuple[str, ...]) -> list[Path]:
        path = self.base / name
        if not path.is_dir():
            return []
        return sorted(p for p in path.iterdir() if p.is_file() and p.suffix in suffixes)


def _read(path: Path) -> str:
    # Explicit encoding, and newline="" so a map's line endings and
    # trailing whitespace reach the parser untouched.
    with path.open("r", encoding="utf-8", newline="") as f:
        return f.read()


def load_content(root: Path, local: Path | None = None) -> ContentTree:
    """Load the content tree at `root`, overlaid by `local` if given."""
    tree = ContentTree(root=root, local=local)
    layers = [_Layer(root, "content")]
    if not root.is_dir():
        tree.load_problems.append(Problem(str(root), None, "content directory does not exist"))
        return tree
    if local is not None:
        if local.is_dir():
            layers.append(_Layer(local, "content.local"))
        else:
            # A mistyped override path must not validate as "ok".
            tree.load_problems.append(Problem(str(local), None, "local override directory does not exist"))
    for layer in layers:
        _check_unclaimed(tree, layer)
        _load_singletons(tree, layer)
        _load_tables(tree, layer)
        _load_record_dirs(tree, layer)
        _load_assets(tree, layer)
    _load_zones(tree, layers)
    tree.hash = content_hash(root, local)
    return tree


def _claimed(rel: Path) -> bool:
    """Whether a file at this relative path is one the loader reads."""
    parts = rel.parts
    if len(parts) == 1:
        return parts[0] in TABLE_FILES or parts[0] in SINGLETON_FILES
    if len(parts) != 2:
        return False
    folder, suffix = parts[0], rel.suffix
    if folder in RECORD_DIRS:
        return suffix == ".json"
    return (folder, suffix) in {
        ("zones", ".json"), ("zones", ".map"), ("text", ".md"), ("text", ".txt"),
        ("art", ".ans"), ("art", ".json"),
    }


def _check_unclaimed(tree: ContentTree, layer: _Layer) -> None:
    # A misnamed file (`item.json`, `zones/x.txt`) would otherwise be
    # skipped silently and the tree would validate without it.
    for path in content_files(layer.base):
        if not _claimed(path.relative_to(layer.base)):
            tree.load_problems.append(Problem(layer.rel(path), None, "not a content file (unknown name or location)"))


def _remember(tree: ContentTree, rel: str, text: str) -> None:
    tree.texts[rel] = text


def _load_singletons(tree: ContentTree, layer: _Layer) -> None:
    for name, cls in SINGLETON_FILES.items():
        path = layer.file(name)
        if path is None:
            continue
        rel = layer.rel(path)
        text = _read(path)
        _remember(tree, rel, text)
        record, problems = read_record(text, rel, cls)
        tree.load_problems.extend(problems)
        if record is None:
            continue
        key = name.removesuffix(".json")
        tree.sources[(key, key)] = rel
        if isinstance(record, s.GlyphTable):
            merged = dict(tree.glyphs.glyphs) if tree.glyphs else {}
            merged.update(record.glyphs)
            tree.glyphs = s.GlyphTable(glyphs=merged)
        elif isinstance(record, s.Palette):
            roles = dict(tree.palette.roles) if tree.palette else {}
            roles.update(record.roles)
            tree.palette = s.Palette(roles=roles)
        elif isinstance(record, s.KeymapTable):
            if tree.keymaps is None:
                tree.keymaps = record
            else:
                actions = {**tree.keymaps.actions, **record.actions}
                maps = {k.id: k for k in tree.keymaps.keymaps}
                maps.update({k.id: k for k in record.keymaps})
                tree.keymaps = s.KeymapTable(actions=actions, keymaps=tuple(maps.values()))


def _check_id(tree: ContentTree, kind: str, record_id: str, rel: str, text: str) -> bool:
    if valid_id(_ID_KIND.get(kind, kind), record_id):
        return True
    tree.load_problems.append(
        Problem(rel, find_line(text, *id_needles(record_id)), f"{kind} id {record_id!r} is not a valid id")
    )
    return False


def _load_tables(tree: ContentTree, layer: _Layer) -> None:
    for name, (kind, cls) in TABLE_FILES.items():
        path = layer.file(name)
        if path is None:
            continue
        rel = layer.rel(path)
        text = _read(path)
        _remember(tree, rel, text)
        records, top, problems = read_table(text, rel, kind, cls)
        tree.load_problems.extend(problems)
        target: dict[str, Any] = getattr(tree, kind)
        seen: set[str] = set()
        for record in records:
            if not _check_id(tree, kind, record.id, rel, text):
                continue
            if record.id in seen:
                tree.load_problems.append(
                    Problem(rel, find_line(text, *id_needles(record.id)), f"duplicate {kind} id {record.id!r}")
                )
                continue
            seen.add(record.id)
            target[record.id] = record
            tree.sources[(kind, record.id)] = rel
        if kind == "factions" and "asymmetries" in top:
            raw = top["asymmetries"]
            pairs = []
            if isinstance(raw, list):
                for pair in raw:
                    if isinstance(pair, list) and len(pair) == 2 and all(isinstance(p, str) for p in pair):
                        pairs.append((pair[0], pair[1]))
                    else:
                        tree.load_problems.append(Problem(rel, None, f"asymmetry {pair!r} must be a pair of faction ids"))
            else:
                tree.load_problems.append(Problem(rel, None, "asymmetries must be a list of pairs"))
            tree.asymmetries = tuple(pairs)


def _record_id(record: Any) -> str:
    if isinstance(record, s.SeasonDefinition):
        return str(record.number)
    return record.id


def _load_record_dirs(tree: ContentTree, layer: _Layer) -> None:
    for dirname, cls in RECORD_DIRS.items():
        for path in layer.dir(dirname, (".json",)):
            rel = layer.rel(path)
            text = _read(path)
            _remember(tree, rel, text)
            record, problems = read_record(text, rel, cls)
            tree.load_problems.extend(problems)
            if record is None:
                continue
            rid = _record_id(record)
            if rid != path.stem:
                tree.load_problems.append(Problem(rel, None, f"file name must be {rid}.json"))
                continue
            if dirname != "seasons" and not _check_id(tree, dirname, rid, rel, text):
                continue
            getattr(tree, dirname)[rid] = record
            tree.sources[(dirname, rid)] = rel


def _load_assets(tree: ContentTree, layer: _Layer) -> None:
    seen_text: set[str] = set()
    for path in layer.dir("text", (".md", ".txt")):
        rel = layer.rel(path)
        if not _check_id(tree, "text", path.stem, rel, ""):
            continue
        if path.stem in seen_text:
            tree.load_problems.append(Problem(rel, None, f"text asset {path.stem!r} exists as both .md and .txt"))
            continue
        seen_text.add(path.stem)
        tree.text[path.stem] = read_text_asset(path.stem, _read(path), path.suffix)
        tree.sources[("text", path.stem)] = rel
    for path in layer.dir("art", (".ans",)):
        rel = layer.rel(path)
        side = path.with_suffix(".json")
        if not side.is_file():
            tree.load_problems.append(Problem(rel, None, f"art needs a sidecar {side.name}"))
            continue
        side_rel = layer.rel(side)
        side_text = _read(side)
        _remember(tree, side_rel, side_text)
        meta, problems = read_record(side_text, side_rel, s.ArtMeta)
        tree.load_problems.extend(problems)
        if meta is None or not _check_id(tree, "art", path.stem, rel, ""):
            continue
        tree.art[path.stem] = s.ArtAsset(id=path.stem, meta=meta, data=path.read_bytes())
        tree.sources[("art", path.stem)] = side_rel
    for path in layer.dir("art", (".json",)):
        if not path.with_suffix(".ans").is_file():
            tree.load_problems.append(Problem(layer.rel(path), None, f"sidecar without {path.stem}.ans"))


def _load_zones(tree: ContentTree, layers: list[_Layer]) -> None:
    # The winning layer for each zone id supplies both of its files.
    chosen: dict[str, _Layer] = {}
    for layer in layers:
        for path in layer.dir("zones", (".json", ".map")):
            chosen[path.stem] = layer
    legend = {t.char: t.id for t in tree.tiles.values()}
    for zone_id in sorted(chosen):
        layer = chosen[zone_id]
        meta_path = layer.base / "zones" / f"{zone_id}.json"
        map_path = layer.base / "zones" / f"{zone_id}.map"
        missing = [p for p in (meta_path, map_path) if not p.is_file()]
        if missing:
            for p in missing:
                tree.load_problems.append(Problem(layer.rel(p), None, f"zone {zone_id} needs both .json and .map"))
            continue
        meta_rel, map_rel = layer.rel(meta_path), layer.rel(map_path)
        meta_text, map_text = _read(meta_path), _read(map_path)
        _remember(tree, meta_rel, meta_text)
        _remember(tree, map_rel, map_text)
        meta, problems = read_record(meta_text, meta_rel, s.ZoneMeta)
        tree.load_problems.extend(problems)
        grid, map_problems = parse_map(map_text, map_rel, legend)
        tree.load_problems.extend(map_problems)
        if meta is None or grid is None:
            continue
        if meta.id != zone_id:
            tree.load_problems.append(Problem(meta_rel, None, f"file name must be {meta.id}.json"))
            continue
        if not _check_id(tree, "zones", zone_id, meta_rel, meta_text):
            continue
        tree.zones[zone_id] = s.Zone(meta=meta, grid=grid)
        tree.sources[("zones", zone_id)] = meta_rel
        tree.sources[("maps", zone_id)] = map_rel
