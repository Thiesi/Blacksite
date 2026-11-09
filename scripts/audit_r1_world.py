"""R1's required offline, read-only audit of an acceptance world.db.

This administrative proof runs only after the acceptance service closes.
It never unpickles a value, migrates a database or writes to the world.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any


def quote(identifier: str) -> str:
    return '"'+identifier.replace('"', '""')+'"'


def audit(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {'database_sha256': sha256(path.read_bytes()).hexdigest(),
        'mode': 'offline, read-only; acceptance service closed', 'tables': 0, 'rows': 0,
        'text_values': 0, 'blob_values': 0, 'json_values': 0, 'canonical_place_values': 0,
        'findings': []}
    package = re.compile(r'(?:blacksite|karst41)[./\\]', re.I)
    # The installation's identifiers remain canon under option A.
    place = re.compile(r'blacksite-(?:l[0-9]+|outworks)\b|\bthe Blacksite\b|Blacksite Outworks')

    def inspect(value: str | bytes, where: str) -> None:
        if isinstance(value, bytes):
            result['blob_values'] += 1
            if value.startswith(b'\x80') or package.search(value.decode('latin-1')):
                result['findings'].append({'where': where, 'kind': 'pickle or package-tagged blob'})
            return
        result['text_values'] += 1
        if package.search(value):
            result['findings'].append({'where': where, 'kind': 'stored Python package path'})
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            decoded = None
        if isinstance(decoded, (dict, list)):
            result['json_values'] += 1
            pending = [decoded]
            while pending:
                node = pending.pop()
                if isinstance(node, dict):
                    for key, child in node.items():
                        if key.lower().startswith(('blacksite', 'karst41')) and not place.match(key):
                            result['findings'].append({'where': where, 'kind': 'package-named JSON schema key'})
                        pending.append(child)
                elif isinstance(node, list):
                    pending.extend(node)
        if re.search('blacksite', value, re.I):
            if place.search(value):
                result['canonical_place_values'] += 1
            else:
                result['findings'].append({'where': where, 'kind': 'unclassified old name'})

    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as database:
        tables = database.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        for table, schema in tables:
            result['tables'] += 1
            inspect(schema or '', 'schema:'+table)
            columns = [row[1] for row in database.execute('PRAGMA table_info('+quote(table)+')')]
            for number, row in enumerate(database.execute('SELECT * FROM '+quote(table))):
                result['rows'] += 1
                for column, value in zip(columns, row):
                    if isinstance(value, (str, bytes)):
                        inspect(value, f'{table}[{number}].{column}')
    result['migration_required'] = bool(result['findings'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    args = parser.parse_args()
    report = audit(args.database)
    print(json.dumps(report, indent=2))
    raise SystemExit(int(report['migration_required']))
