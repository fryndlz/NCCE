"""Private append-only authoring journal. No network or campaign database access."""
import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

KINDS = {'batch', 'packet', 'draft', 'feedback', 'standard', 'decision', 'exception'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def append(root, event):
    if not isinstance(event, dict) or event.get('kind') not in KINDS:
        raise ValueError('Expected an event object with a supported kind')
    if not isinstance(event.get('id'), str) or not 1 <= len(event['id']) <= 160:
        raise ValueError('Event needs a stable id of 1–160 characters')
    if any(key in event for key in ('stored_at', 'sha256')):
        raise ValueError('Storage timestamps and hashes are assigned by the journal')
    body = canonical(event)
    if len(body.encode('utf-8')) > 2_000_000:
        raise ValueError('Split large source packets into linked events below 2 MB')
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(root / 'journal.sqlite3', timeout=10)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, stored_at TEXT NOT NULL, sha256 TEXT NOT NULL, body TEXT NOT NULL)')
        digest = hashlib.sha256(body.encode('utf-8')).hexdigest()
        old = db.execute('SELECT body FROM events WHERE id=?', (event['id'],)).fetchone()
        if old:
            if old[0] != body:
                raise ValueError('Event id already exists with different content; append a revision with a new id')
            return {'id': event['id'], 'created': False}
        db.execute('INSERT INTO events VALUES(?,?,?,?)',
                   (event['id'], datetime.now(timezone.utc).isoformat(), digest, body))
    return {'id': event['id'], 'created': True}


def read(root):
    path = Path(root) / 'journal.sqlite3'
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        rows = db.execute('SELECT stored_at,sha256,body FROM events ORDER BY rowid DESC').fetchall()
    result = []
    for at, digest, body in rows:
        if hashlib.sha256(body.encode('utf-8')).hexdigest() != digest:
            raise ValueError('Journal integrity check failed')
        result.append({**json.loads(body), 'stored_at': at, 'sha256': digest})
    return result


def markdown(events):
    lines = ['# NCCE native writing · newest first', '']
    for item in events:
        lines += ['## ' + item['kind'].title() + ' · ' + item['id'], '',
                  item['stored_at'] + ' · ' + str(item.get('form', '')) + ' · ' + str(item.get('subject_key', '')), '']
        if item.get('text'):
            lines += [str(item['text']), '']
        details = {k: v for k, v in item.items() if k not in ('kind', 'id', 'stored_at', 'form', 'subject_key', 'text')}
        if details:
            lines += ['<details><summary>Source, checks and revision details</summary>', '',
                      '```json', json.dumps(details, ensure_ascii=False, indent=2), '```', '', '</details>', '']
    return '\n'.join(lines)


def standards(root, form=None):
    events = read(root)
    rules = [e for e in events if e['kind'] == 'standard']
    superseded = set()
    for rule in rules:
        prior = rule.get('supersedes', [])
        if isinstance(prior, str):
            prior = [prior]
        if isinstance(prior, list):
            superseded.update(x for x in prior if isinstance(x, str))
    return [r for r in rules if r['id'] not in superseded and
            (form is None or r.get('form') in (None, 'all', 'shared', form))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('timeline')
    active = sub.add_parser('standards')
    active.add_argument('--form')
    writer = sub.add_parser('append')
    writer.add_argument('--file', type=Path, required=True)
    export = sub.add_parser('export')
    export.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'append':
            result = append(args.root, json.loads(args.file.read_text(encoding='utf-8-sig')))
        elif args.command == 'timeline':
            result = read(args.root)
        elif args.command == 'standards':
            result = standards(args.root, args.form)
        else:
            target = args.output.resolve()
            journal = (args.root / 'journal.sqlite3').resolve()
            if target == journal:
                raise ValueError('Export cannot replace the journal')
            # Refuse overwriting existing material; use a fresh export name.
            with target.open('x', encoding='utf-8') as handle:
                handle.write(markdown(read(args.root)))
            result = {'exported': str(target)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
