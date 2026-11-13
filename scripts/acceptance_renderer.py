"""S48a: name the renderer a NetBBS acceptance run actually used."""

import json
from pathlib import Path


def stamp(root: Path, renderer: str, since: float) -> list[Path]:
    """Add `renderer_ran` to every results file this run wrote in `root`.

    Scripts write `result.json` or `<name>-results.json`. Only files written
    at or after `since` (the probe's start, from `time.time()`) are stamped,
    so a file left by an earlier run is never given this run's renderer. A
    stray or half-written file is skipped, so a cleanup never hides the
    run's own failure. Returns the files stamped.
    """
    stamped = []
    for results in sorted(root.glob('*result*.json')):
        try:
            if results.stat().st_mtime < since:
                continue
            data = json.loads(results.read_text(encoding='utf-8'))
            if isinstance(data, dict) and 'renderer_ran' not in data:
                data['renderer_ran'] = renderer
                results.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8', newline='\n')
                stamped.append(results)
        except (OSError, ValueError):
            continue
    return stamped
