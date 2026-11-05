"""Munda Manager (read-only Sheet export) is the sole authored biography source.

Retired projections are retained in provenance audit metadata, never written back
to either source. Missing export fields do not erase a previously imported MM bio.
"""
import hashlib
import json

SOURCE = 'player-authored / campaign Sheet'


def reconcile(store):
    changed = 0
    with store._lock, store.db:
        for row in store.db.execute('SELECT id,backstory,backstory_source,provenance_class,mechanics_json FROM fighters').fetchall():
            fighter = dict(row)
            mechanics = json.loads(fighter.get('mechanics_json') or '{}')
            previous = fighter.get('backstory_source') or ''
            legacy = any(token in previous.casefold() for token in ('c-nine story', 'canon'))
            supplied = 'Backstory' in mechanics
            text = str(mechanics.get('Backstory') or '').strip() if supplied else None
            if text:
                # Store the exact authored text, including its original whitespace.
                text = str(mechanics['Backstory'])
                source, provenance = SOURCE, 'player_authored'
            elif legacy or (supplied and previous == SOURCE):
                text, source, provenance = '', 'not-provided', 'inference'
            else:
                continue
            if (fighter['backstory'], previous, fighter['provenance_class']) == (text, source, provenance):
                continue
            if fighter.get('backstory'):
                digest = hashlib.sha256(json.dumps([fighter['id'], fighter['backstory'], previous], ensure_ascii=False).encode()).hexdigest()
                store.record_source('retired:fighter-backstory:'+digest, 'retired_biography_projection',
                                    'canon_authored' if legacy else fighter['provenance_class'] or 'inference',
                                    'Superseded fighter biography source', content_hash=digest,
                                    metadata={'fighter_id':fighter['id'], 'backstory':fighter['backstory'],
                                              'backstory_source':previous, 'reason':'Munda Manager biography authority'})
            store.db.execute('UPDATE fighters SET backstory=?,backstory_source=?,provenance_class=? WHERE id=?',
                             (text,source,provenance,fighter['id']))
            changed += 1
    return changed
