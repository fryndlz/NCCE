"""Read NCCE context from an explicitly supplied existing SQLite snapshot. No models."""
import argparse
import json
import sqlite3
import sys
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def inspect(repo, database, key=None):
    repo, database = Path(repo).resolve(), Path(database).resolve(strict=True)
    if not (repo / 'src/writing_rag.py').is_file():
        raise ValueError('Choose the actual NCCE repository')
    sys.path.insert(0, str(repo / 'src'))
    from store import Store
    import writer_workshop as ws
    import writing_rag as rag
    # Never call Store(): its initializer writes schema and runs migrations.
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        view = object.__new__(Store)
        view.path, view.db, view._lock = database, db, threading.RLock()
        if key is None:
            result = {'subjects': [s for s in ws.catalog(view) if not s['key'].startswith('comparison:')]}
        else:
            if key.startswith('comparison:'):
                raise ValueError('Comparison samples are outside this authoring helper')
            sample = ws.sample(view, key)
            result = {'sample': sample, 'context': rag.read(view, 'preview', {'form': [sample['form']], 'sample_key': [key]})}
    return {'snapshot': str(database), 'snapshot_mtime_utc': datetime.fromtimestamp(
        database.stat().st_mtime, timezone.utc).isoformat(),
        'notice': 'Local snapshot only; not verified against the hosted campaign. No changes or model calls.', **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--db', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('catalog')
    packet = sub.add_parser('packet')
    packet.add_argument('--key', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.repo, args.db, getattr(args, 'key', None)), ensure_ascii=False, indent=2))
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
