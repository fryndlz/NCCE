"""Explicit local operator interface; no command auto-spends or publishes."""
import argparse
from contextlib import closing, contextmanager
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from store import Store
from writer_quality import Workflow
import writer_contract
import writer_workshop


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def snapshot(source, folder, forms, mapping, max_rounds):
    source = Path(source).resolve(strict=True)
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    # SQLite backup includes committed WAL data and never opens the source Store
    # (whose constructor performs migrations). No raw file copy of a live DB.
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original:
        with closing(sqlite3.connect(folder / 'snapshot.db')) as copied:
            original.backup(copied)
    store = Store(folder / 'snapshot.db')
    try:
        samples = writer_workshop.catalog(store)
        selected = {}
        for form in forms:
            matches = [s for s in samples if s['form'] == form]
            if form in mapping:
                selected[form] = mapping[form]
            elif matches:
                selected[form] = matches[0]['key']
            else:
                raise ValueError('No sourced sample for ' + form + '. Select a narrower --forms scope; missing forms cannot pass.')
        flow = Workflow.create(store, selected, max_rounds)
        return flow.report()
    finally:
        store.close()


@contextmanager
def opened(folder):
    folder = Path(folder).resolve(strict=True)
    db = folder / 'snapshot.db'
    # Check before Store can migrate: ordinary campaign DBs cannot be operated on.
    with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)) as check:
        if not check.execute("SELECT 1 FROM sqlite_master WHERE name='quality_run'").fetchone():
            raise ValueError('Not an initialized quality snapshot')
    lock = folder / 'operator.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('Another operator holds the run lock. After a crash, inspect audit/state before manually removing operator.lock.') from None
    os.close(fd)
    store = None
    try:
        store = Store(db)
        yield Workflow(store)
    finally:
        if store:
            store.close()
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, help='Private local run directory; contains campaign context')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init', help='Read-only backup of a local campaign DB; zero provider calls')
    init.add_argument('--campaign-db', required=True)
    init.add_argument('--forms', default=','.join(writer_contract.BRIEFS))
    init.add_argument('--samples', help='Optional JSON object mapping forms to Workshop sample keys')
    init.add_argument('--max-rounds', type=int, default=3)
    sub.add_parser('status')
    sub.add_parser('catalog')
    for name in ('inspect', 'grant', 'run-pair', 'review-bundle', 'review', 'resolve', 'approve', 'disapprove'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--form', required=True, choices=list(writer_contract.BRIEFS))
        if name in ('grant', 'resolve', 'approve', 'disapprove'):
            cmd.add_argument('--actor', required=True, help='Human operator attribution; local CLI is trusted, not an authentication service')
        if name in ('resolve', 'approve', 'disapprove'):
            cmd.add_argument('--note', required=True)
        if name == 'review':
            cmd.add_argument('--file', required=True)
        if name == 'run-pair':
            cmd.add_argument('--allow-paid', action='store_true', required=True)
    args = parser.parse_args()
    if args.command == 'init':
        result = snapshot(args.campaign_db, args.run_dir, args.forms.split(','),
                          read_json(args.samples) if args.samples else {}, args.max_rounds)
    else:
        with opened(args.run_dir) as flow:
            if args.command == 'status': result = flow.report()
            elif args.command == 'catalog': result = writer_workshop.catalog(flow.store)
            elif args.command == 'inspect': result = flow.inspect(args.form)
            elif args.command == 'review-bundle': result = flow.bundle(args.form)
            else:
                if args.command == 'grant': flow.grant(args.form, args.actor)
                elif args.command == 'run-pair': flow.run_pair(args.form)
                elif args.command == 'review': flow.review(args.form, read_json(args.file))
                elif args.command == 'resolve': flow.resolve(args.form, args.actor, args.note)
                else: flow.decide(args.form, args.actor, args.command == 'approve', args.note)
                result = flow.report()
    print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print('Stopped: ' + str(exc), file=sys.stderr)
        sys.exit(2)
