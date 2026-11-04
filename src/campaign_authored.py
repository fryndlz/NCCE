"""Reviewed, source-bounded C-NINE import. No remote writes or generation.

Exact battle keys plus mechanical identity guards prevent prose being attached
to another engagement. Source Notes remain primary; document reports backfill
missing accounts and remain available as separately attributed alternatives.
"""
from functools import lru_cache
from pathlib import Path
import hashlib
import json
from authored_battles import report

PATH=Path(__file__).resolve().parents[1]/'data/imports/c-nine-engagement-dossiers.json'


@lru_cache(maxsize=1)
def catalog():
    value=json.loads(PATH.read_text(encoding='utf-8'))
    for entry in value['engagements']:
        for part in ('report','addenda'):
            if hashlib.sha256(entry[part].encode()).hexdigest()!=entry[part+'_sha256']:
                raise ValueError('Authored dossier import hash mismatch')
    return value


def match(battle):
    for entry in catalog()['engagements']:
        if battle.get('source_battle_key')!=entry['battle_key']:continue
        if all(battle.get(k)==v for k,v in entry['guards'].items()):return entry
    return None


def document(battle,part='report'):
    entry=match(battle)
    if not entry:return None
    source=catalog()['source']
    doc=report({**battle,'notes':entry[part]})
    doc.update(provenance_class='canon_authored',source_ids=['canon:c-nine-engagement-dossiers'],
               source_url=source['url'],source_label='C-NINE Google Doc · authored campaign canon',
               source_locator=f"HOSTILE ENGAGEMENT #{entry['engagement']} · {'Post-Engagement Record' if part=='addenda' else 'Incident record'}",
               source_revision=source['export_sha256'],source_captured_at=source['captured_at'],
               source_excerpt_sha256=entry[part+'_sha256'],engagement=entry['engagement'])
    if part=='addenda':
        doc.update(title='Post-battle addenda · '+doc['title'],document_type='post_battle_addendum',attachment_count=entry['attachment_count'])
    return doc


def attach(battle):
    battle['post_battle_addendum']=document(battle,'addenda')
    alternate=document(battle)
    battle['alternate_report_document']=alternate if str(battle.get('notes') or '').strip() else None


def register(store):
    source=catalog()['source']
    store.record_source('canon:c-nine-engagement-dossiers','authored_campaign_import','canon_authored',source['title'],
                        source_uri=source['url'],retrieved_at=source['captured_at'],content_hash=source['export_sha256'],
                        metadata={'engagements':[e['engagement'] for e in catalog()['engagements']],
                                  'import_mode':'reviewed source-bounded snapshot; no automatic remote writing'})
