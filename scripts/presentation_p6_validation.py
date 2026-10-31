"""A6: pair original, cache-only and final validation on pinned data.

Uses local Git objects only. Never executes code from the content input.
Baseline Python comes from merged A5; the snapshot copies JSON/map data.
"""

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import shutil
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import process_time
from types import ModuleType
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]

from blacksite.content import place_validation
from blacksite.content.loader import ContentTree, load_content
from blacksite.content.validate import validate
from blacksite.door.present.paint import Paint

Reporter = Callable[[str, str, str], None]
PlaceValidator = Callable[[ContentTree, Reporter], None]

BASE = 'c2f990312d1c6cf88200f56dc4722fe83f9f7321'
INPUT = '3e585c71eebf8c8cd19a591016dfe78a788c5b9b'
PREFIX = 'src/blacksite/content/'
VALIDATION_CPU_SECONDS = 3.0  # Existing S25b TR-8 / test_hub_maps gate.


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', *args], cwd=ROOT)


def module(name: str, source: bytes) -> ModuleType:
    # Dataclasses resolve their defining module while trusted Git code loads.
    result = ModuleType(name)
    sys.modules[name] = result
    exec(compile(source, name, 'exec'), result.__dict__)
    return result


def validator(name: str, source: bytes, paint: type[Paint]) -> tuple[PlaceValidator, dict[str, int]]:
    result = module(name, source)
    counts = {'palette_conversions': 0, 'paints': 0}

    def convert(value: Any) -> dict[str, Any]:
        counts['palette_conversions'] += 1
        return asdict(value)

    def construct(palette: Any) -> Any:
        counts['paints'] += 1
        return paint(palette)

    result.asdict, result.Paint = convert, construct
    return result.validate_places, counts


def measure(tree: ContentTree, function: PlaceValidator, counts: dict[str, int],
            repeats: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    original = place_validation.validate_places
    samples, operations, expected = [], [], None
    try:
        place_validation.validate_places = function
        for _ in range(repeats):
            for key in counts:
                counts[key] = 0
            start = process_time()
            problems = validate(tree)
            samples.append(process_time() - start)
            messages = [asdict(problem) for problem in problems]
            if expected is not None and messages != expected:
                raise ValueError('diagnostics changed between identical validations')
            expected = messages
            operations.append(dict(counts))
    finally:
        place_validation.validate_places = original
    digest = sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
    if any(item != operations[0] for item in operations):
        raise ValueError('operation counts changed between identical validations')
    return {'cpu_seconds': samples, 'median_cpu_seconds': median(samples),
            'operations_per_validation': operations[0], 'diagnostics': len(expected),
            'ordered_diagnostics_sha256': digest}, expected


def snapshot(destination: Path, input_ref: str) -> dict[str, str]:
    shutil.copytree(ROOT/PREFIX, destination,
                    ignore=shutil.ignore_patterns('*.py', '__pycache__'))
    names = {name for name in git('diff', '--name-only', BASE, input_ref, '--', PREFIX).decode().splitlines()
             if name.endswith(('.json', '.map'))}
    names.update(str(Path(name).with_suffix('.map')).replace('\\','/')
                 for name in tuple(names) if name.startswith(PREFIX+'zones/') and name.endswith('.json'))
    hashes = {}
    for name in sorted(names):
        data = git('show', f'{input_ref}:{name}')
        target = destination/Path(name).relative_to(PREFIX)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        hashes[name] = sha256(data).hexdigest()
    return hashes


def run(input_ref: str, repeats: int) -> dict[str, Any]:
    if not re.fullmatch('[0-9a-f]{40}', input_ref) or repeats < 1:
        raise ValueError('input-ref must be a full Git id; repeats must be positive')
    paint_path = 'src/blacksite/door/present/paint.py'
    validation_path = PREFIX+'place_validation.py'
    before_paint = module('_a6_before_paint', git('show', f'{BASE}:{paint_path}')).Paint
    old_source = git('show', f'{BASE}:{validation_path}')
    new_source = (ROOT/validation_path).read_bytes()
    phases = [('before', *validator('_a6_before_validation', old_source, before_paint)),
              ('cache_only', *validator('_a6_cache_validation', new_source, before_paint)),
              ('after', *validator('_a6_after_validation', new_source, Paint))]
    report = {'head': git('rev-parse', 'HEAD').decode().strip(),
              'baseline': BASE, 'input_ref': input_ref, 'python': platform.python_version(),
              'platform': platform.platform(), 'boundary': 'full validate(tree), CPU only; load/I/O excluded',
              'source_sha256': {path:sha256((ROOT/path).read_bytes()).hexdigest()
                                for path in (paint_path, validation_path)}, 'cases': []}
    with TemporaryDirectory(prefix='blacksite-a6-') as temporary:
        content = Path(temporary)/'p6b'
        report['input_files_sha256'] = snapshot(content, input_ref)
        trees = [('shipped', load_content(ROOT/PREFIX)),
                 ('shipped_plus_p6b', load_content(content)),
                 ('p6b_plus_light_fixture', load_content(content, ROOT/'tests/fixtures/p6'))]
        for label, tree in trees:
            result, diagnostics = {'case': label}, {}
            for name, function, counts in phases:
                result[name], diagnostics[name] = measure(tree, function, counts, repeats)
                print(json.dumps({'case': label, 'phase': name,
                                  'median_cpu_seconds': result[name]['median_cpu_seconds']}), flush=True)
            if diagnostics['before'] != diagnostics['cache_only']:
                raise ValueError(f'{label}: caching changed diagnostics or their order')
            before = Counter(json.dumps(item, sort_keys=True) for item in diagnostics['before'])
            after = Counter(json.dumps(item, sort_keys=True) for item in diagnostics['after'])
            removed = before - after
            if after - before or any('structure/things contrast fails against theme ground' not in item
                                     for item in removed):
                raise ValueError(f'{label}: unexpected sign-policy diagnostic change')
            if diagnostics['after'] or max(result['after']['cpu_seconds']) >= VALIDATION_CPU_SECONDS:
                raise ValueError(f'{label}: {len(diagnostics["after"])} final errors; '
                                 f'max CPU {max(result["after"]["cpu_seconds"]):.3f}s fails S25 gate')
            result.update(cache_diagnostics_identical_in_order=True,
                          sign_floor_diagnostics_removed=sum(removed.values()))
            report['cases'].append(result)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-ref', default=INPUT)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('preserve existing evidence; choose a new output path')
    result = run(args.input_ref, args.repeats)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
