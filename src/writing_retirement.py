"""One-time retirement of the removed writing ecosystem; never delete prose.

Old audit tables stay readable offline. Operational queues are cancelled only
after a consistent, integrity-checked backup beside the persistent database.
"""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

MARKER = 'writing_system_retired_v1'
TERMINAL = {'complete', 'completed', 'published', 'stopped', 'cancelled', 'error',
            'failed', 'abandoned', 'interrupted', 'finished', 'closed', 'ready',
            'imported', 'succeeded', 'saved', 'reviewed'}
PRIVATE_PREFIXES = ('category-', 'native-author:', 'reviewer-', 'rag:', 'writing-rag:',
                    'writer_preview:', 'writer_comparison:', 'workshop', 'codex_')


def public_state(values):
    """Do not expose dormant drafts, private review packets or old RAG sources."""
    return {k: v for k, v in values.items() if not k.startswith(PRIVATE_PREFIXES)}


def retire(store):
    prior = store.get_state(MARKER)
    if prior:
        result = json.loads(prior)
        # The first rollout could cancel finished/imported audit rows. Restore
        # only their exact status/error from its own verified preimage; no job
        # is requeued and no prose or draft is touched.
        if result.get('audit_revision') != 2:
            from pathlib import Path
            backup = Path(result['backup']).resolve()
            if backup.parent != store.path.resolve().parent or 'pre-writing-retirement-' not in backup.name:
                raise RuntimeError('Unexpected retirement backup path')
            corrected = 0
            with closing(sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True)) as original:
                if original.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Retirement audit repair backup failed integrity verification')
                with store._lock, store.db:
                    for table in ('workshop_trials','codex_review_jobs','workshop_review_requests'):
                        for rowid,status,error in original.execute(f'SELECT rowid,status,error FROM {table}'):
                            if status in TERMINAL:
                                corrected += store.db.execute(f"UPDATE {table} SET status=?,error=? WHERE rowid=? AND status='cancelled' AND error='Writing system removed by owner'",(status,error,rowid)).rowcount
                    result.update(audit_revision=2, restored_terminal_audits=corrected)
                    store.db.execute('UPDATE system_state SET value=? WHERE key=?',(json.dumps(result),MARKER))
        return result
    at = datetime.now(timezone.utc).isoformat()
    backup = store.path.with_name(store.path.stem + '-pre-writing-retirement-' +
                                  datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.db')
    with store._lock:
        store.db.commit()
        with closing(sqlite3.connect(backup)) as target:
            store.db.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Writing retirement backup failed integrity verification')
        counts = {}
        def stop(value):
            if not isinstance(value, dict) or value.get('status') in TERMINAL:
                return False
            if not value.get('status'):
                return False
            value.update(status='cancelled', retirement_reason='Writing system removed by owner', retired_at=at)
            return True
        with store.db:
            for table in ('workshop_trials', 'codex_review_jobs', 'workshop_review_requests'):
                rows = store.db.execute(f'SELECT rowid,status FROM {table}').fetchall()
                for row in rows:
                    if row['status'] in {'queued', 'running', 'claimed', 'started', 'in_progress'}:
                        store.db.execute(f"UPDATE {table} SET status='cancelled',error=? WHERE rowid=?",
                                         ('Writing system removed by owner', row['rowid']))
                        counts[table] = counts.get(table, 0) + 1
            for row in store.db.execute('SELECT run_id,state_json FROM workshop_optimization_runs').fetchall():
                value = json.loads(row['state_json'])
                if stop(value):
                    store.db.execute('UPDATE workshop_optimization_runs SET state_json=? WHERE run_id=?',
                                     (json.dumps(value, ensure_ascii=False), row['run_id']))
                    counts['studies'] = counts.get('studies', 0) + 1
            rows = store.db.execute('SELECT key,value FROM system_state').fetchall()
            for row in rows:
                key = row['key']
                if not key.startswith(('category-policy:', 'category-item:', 'category-population:', 'native-author:batch-')):
                    continue
                value = json.loads(row['value'])
                if key.startswith('category-policy:'):
                    value.update(enabled=False, retired_at=at)
                else:
                    stop(value)
                store.db.execute('UPDATE system_state SET value=? WHERE key=?',
                                 (json.dumps(value, ensure_ascii=False), key))
            result = {'version': '0.23.0', 'audit_revision': 2, 'retired_at': at, 'backup': str(backup), 'cancelled': counts,
                      'generation_enabled': False, 'campaign_records_preserved': True}
            store.db.execute('INSERT INTO system_state(key,value) VALUES(?,?)', (MARKER, json.dumps(result)))
    return result
