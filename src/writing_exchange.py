"""Import owner-accepted external writing; no provider, scheduler or source writes.

The initial adapter supports an existing fighter observation only. Both the
archive identity and cognitive-ledger target must match an explicit binding.
"""
from copy import deepcopy
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import unicodedata
import re
from uuid import UUID


def packed(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def digest(value):
    return hashlib.sha256(packed(value).encode('utf-8')).hexdigest()


def packet_revision(packet):
    value=deepcopy(packet)
    value['request'].pop('source_revision',None)
    return 'sha256:'+digest(value)


def normal(value):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',value).strip().casefold())


def _time(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)


def _validate(store,bundle):
    packet=bundle['packet']; request=packet['request']; binding=bundle['target_binding']
    if str(UUID(request['request_id']))!=request['request_id']:
        raise ValueError('Request UUID must use canonical form')
    if bundle.get('owner_accepted') is not True:
        raise ValueError('This delivery has not been accepted by the owner')
    if request.get('form')!='fighter_memory' or request.get('entity_type')!='fighter':
        raise ValueError('This adapter only imports existing fighter observation memories')
    if request['source_revision']!=packet_revision(packet):
        raise ValueError('Frozen source packet fingerprint does not match')
    content=bundle['writer_text_md']
    if not isinstance(content,str) or not content.strip() or len(content)>=30000:
        raise ValueError('A complete nonempty delivery below 30000 characters is required')
    source=packet['binding']; event_id=source['source_event_id']
    if request['entity_key']!='munda:fighter:'+source['fighter_source_id'] or request['entry_key']!='munda:'+source['source_table']+':'+event_id:
        raise ValueError('Source identity does not match the request routing fields')
    archive=store.db.execute('SELECT normalized_json FROM campaign_archive_records WHERE source_table=? AND record_id=?',
                             (source['source_table'],event_id)).fetchall()
    if len(archive)!=1:raise ValueError('The exact source archive event is missing or ambiguous')
    actual=json.loads(archive[0][0])
    facts=[b for b in packet['context'] if b['section']=='mechanics' and b['provenance']=='mechanical_fact']
    if len(facts)!=1:raise ValueError('One frozen mechanical source block is required')
    expected=json.loads(facts[0]['text'])
    if any(actual.get(k)!=expected.get(k) for k in ('record_id','action_type','description')):
        raise ValueError('Source event changed since the writing packet was prepared')
    if actual.get('fighter_id')!=source['fighter_source_id'] or actual.get('gang_id')!=source['gang_source_id'] or _time(actual['created_at_utc'])!=_time(request['event_at_utc']):
        raise ValueError('Source subject or event timestamp does not match')
    people=store.db.execute('SELECT * FROM fighters WHERE gang_id=?',(source['gang_source_id'],)).fetchall()
    people=[dict(f) for f in people if normal(f['name'])==normal(source['fighter_name'])]
    if len(people)!=1 or actual.get('fighter_name_hint')!=source['fighter_name']:
        raise ValueError('Exact source fighter mapping is missing or ambiguous')
    fighter=people[0]
    canon=[b['text'] for b in packet['context'] if b['section']=='authored_canon' and b['provenance']=='player_authored']
    sheet_background=json.loads(fighter.get('mechanics_json') or '{}').get('Backstory')
    if canon and (len(canon)!=1 or (sheet_background or fighter['backstory'])!=canon[0]):
        raise ValueError('Authored background changed since the packet was prepared')
    key=binding['memory_key']
    event=store.db.execute('SELECT * FROM campaign_events WHERE event_id=?',(key,)).fetchone()
    if not event or event['event_type']!=binding['event_type'] or json.loads(event['payload_json'])!=binding['payload']:
        raise ValueError('The explicitly bound cognitive event does not match')
    subject=store.db.execute("""SELECT 1 FROM event_subjects s JOIN entities e USING(entity_id)
        WHERE s.event_id=? AND e.entity_type='fighter' AND e.entity_key=?""",
        (key,source['gang_source_id']+'/'+normal(source['fighter_name']))).fetchone()
    if not subject:raise ValueError('The bound memory event belongs to another subject')
    rows=store.db.execute('SELECT * FROM story_memories WHERE fighter_id=? AND memory_key=? AND active=1',
                          (fighter['id'],key)).fetchall()
    if len(rows)!=1:raise ValueError('The existing active memory is missing or ambiguous; no new experience will be invented')
    memory=dict(rows[0])
    if memory['memory_type']!='observation' or memory['provenance_class']!='inference' or json.loads(memory['source_event_ids_json'])!=[key]:
        raise ValueError('The target must be this exact inferred observation, not authored content or a reflection')
    if memory['evidence_json']!=binding['evidence_json']:
        raise ValueError('The bound memory evidence changed')
    return fighter,memory


def _backup(store,request_id):
    target=store.path.with_name('pre-exchange-'+request_id+'.db')
    if not target.exists():
        with closing(sqlite3.connect(target)) as backup:
            store.db.backup(backup)
            if backup.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                raise RuntimeError('External writing import backup failed verification')
    return target


def import_delivery(store,bundle):
    """Preserve every submitted draft, apply one validated revision atomically.

    Only trusted local/startup callers supply owner_accepted; no public writer
    endpoint or Google credentials are added by this adapter.
    """
    received=datetime.now(timezone.utc).isoformat()
    delivery_hash=digest(bundle)
    request=bundle['packet']['request']; rid=request['request_id']
    with store._lock:
        if store.db.in_transaction:
            raise RuntimeError('External prose import requires its own transaction')
        prior=store.db.execute("SELECT * FROM external_prose_deliveries WHERE request_id=? AND disposition='imported'",(rid,)).fetchone()
        if prior and prior['delivery_hash']==delivery_hash:
            return {'status':'imported','receipt':prior['receipt'],'imported_at':prior['imported_at'],
                    'fighter_id':prior['fighter_id'],'memory_key':prior['memory_key'],'memory_id':prior['memory_id'],'reused':True}
        try:
            if prior:raise ValueError('A different delivery already exists for this request; previous text is preserved')
            fighter,memory=_validate(store,bundle)
            conflict=store.db.execute("SELECT 1 FROM external_prose_deliveries WHERE fighter_id=? AND memory_key=? AND disposition='imported'",
                                       (fighter['id'],memory['memory_key'])).fetchone()
            if conflict:raise ValueError('This memory already has an imported external delivery')
            _backup(store,rid)
            from story_engine import _save_memory,read_memories
            source=next(m for m in read_memories(store,fighter['id']) if m['id']==memory['memory_id'])
            source.update(content=bundle['writer_text_md'],writer_status='ready',writer_content_runs=[])
            receipt='exchange:'+rid+':'+delivery_hash[:16]
            with store.db:
                store.db.execute('UPDATE story_memories SET active=0 WHERE fighter_id=? AND memory_key=?',
                                  (fighter['id'],memory['memory_key']))
                saved=_save_memory(store,fighter['id'],source,received)
                store.db.execute('''INSERT OR REPLACE INTO external_prose_deliveries(
                    delivery_hash,request_id,packet_json,binding_json,raw_markdown,received_at,disposition,error,
                    fighter_id,memory_key,memory_id,imported_at,receipt) VALUES(?,?,?,?,?,?,'imported','',?,?,?,?,?)''',
                    (delivery_hash,rid,packed(bundle['packet']),packed(bundle['target_binding']),bundle['writer_text_md'],
                     received,fighter['id'],memory['memory_key'],saved['id'],received,receipt))
            return {'status':'imported','receipt':receipt,'imported_at':received,'fighter_id':fighter['id'],
                    'memory_key':memory['memory_key'],'memory_id':saved['id'],'reused':False}
        except (KeyError,ValueError,TypeError,sqlite3.Error) as error:
            # A rejection is auditable and never turns a completed draft into waste.
            with store.db:
                store.db.execute('''INSERT OR REPLACE INTO external_prose_deliveries(
                    delivery_hash,request_id,packet_json,binding_json,raw_markdown,received_at,disposition,error)
                    VALUES(?,?,?,?,?,?,'held',?)''',(delivery_hash,rid,packed(bundle['packet']),packed(bundle.get('target_binding',{})),
                                                   bundle.get('writer_text_md',''),received,str(error)))
            return {'status':'held','request_id':rid,'error':str(error)}


def retained(store,fighter_id,memory_key):
    """A refresh reuses the accepted text, without a new request or clock tick."""
    row=store.db.execute("""SELECT raw_markdown FROM external_prose_deliveries
        WHERE fighter_id=? AND memory_key=? AND disposition='imported'""",(fighter_id,memory_key)).fetchone()
    return (row['raw_markdown'],[],{'status':'ready'}) if row else None


def status(store):
    return [dict(r) for r in store.db.execute('''SELECT request_id,disposition,error,fighter_id,memory_key,memory_id,
        imported_at,receipt FROM external_prose_deliveries ORDER BY received_at,delivery_hash''')]


def import_accepted_files(store,directory):
    results=[]
    for path in sorted(Path(directory).glob('*.json')):
        with path.open(encoding='utf-8') as stream:bundle=json.load(stream)
        result=import_delivery(store,bundle);results.append(result)
        print('External writing import: '+json.dumps(result,ensure_ascii=True,sort_keys=True),flush=True)
    return results
