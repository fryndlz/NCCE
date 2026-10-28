"""Guideline history, exact changes and explicit owner activation."""
import difflib
import json
import hashlib
import uuid
from datetime import datetime
import writer_workshop as ws


def changes(before, after):
    old, new = before.splitlines(), after.splitlines()
    edits = []
    for kind, a, b, c, d in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if kind != 'equal':
            edits.append({'before':'\n'.join(old[a:b]), 'after':'\n'.join(new[c:d])})
    added = sum(len(x['after'].splitlines()) for x in edits)
    removed = sum(len(x['before'].splitlines()) for x in edits)
    return {'summary':f'Added {added} instruction lines; removed {removed}.' if edits else 'Instructions unchanged.', 'edits':edits}


def announcement(scope, change, proposed=False):
    verb = ('proposed changes to' if proposed else 'updated') if change['edits'] else 'reviewed'
    message = 'I '+verb+' the '+scope.replace('_',' ')+' guidelines. '+change['summary']
    for edit in change['edits'][:2]:
        old, new = edit['before'], edit['after']
        prefix = 0
        if old and new:
            for a, b in zip(old, new):
                if a != b: break
                prefix += 1
        start = max(0, prefix-45)
        def excerpt(text): return ('…' if start else '')+text[start:start+180]+('…' if len(text)>start+180 else '')
        if old: message += '\nRemoved/replaced: '+excerpt(old)
        if new: message += '\nAdded: '+excerpt(new)
    return message+'\nSee Writing guidelines for the full text and exact changes. Active NCCE instructions are unchanged.'


def content_hash(scope, instructions, examples=''):
    return hashlib.sha256(ws.packed({'scope':scope,'instructions':instructions,'examples':examples}).encode()).hexdigest()


def library(store, scope):
    scope = ws.scope_name(scope)
    meta = ws.editor(store, scope)
    # Existing immutable audit is the source of authorship, not revision labels.
    runs = [json.loads(r[0]) for r in store.db.execute(
        "SELECT state_json FROM workshop_optimization_runs WHERE json_extract(state_json, '$.form')=? ORDER BY rowid DESC LIMIT 40", (scope,))]
    sources, proposals, seen_proposals = {}, [], set()
    for run in runs:
        adopted = {h['after_round']:h for h in run.get('prompt_history', [])}
        for h in run.get('prompt_history', []):
            round_ = next((r for r in run.get('rounds', []) if r['number']==h['after_round']), {})
            reason = ((round_.get('pairs') or [{}])[-1].get('review') or {}).get('summary','')
            sources[h['to_revision']] = {'author':'JKSimmons', 'run_id':run['run_id'], 'round':h['after_round'], 'previous_revision_id':h['from_revision'],'reason':reason}
        for round_ in reversed(run.get('rounds', [])):
            for index, pair in reversed(list(enumerate(round_['pairs']))):
                review = pair.get('review')
                if not review: continue
                h = adopted.get(round_['number'])
                instructions = review.get('proposed_form_instructions', '')
                if h and instructions.strip()==h.get('instructions','').strip(): continue
                tested = pair.get('instructions', '').rsplit('\nREQUESTED FORM: '+scope+'\n', 1)[-1]
                change = changes(tested, instructions)
                if not change['edits'] or instructions.strip() in seen_proposals: continue
                seen_proposals.add(instructions.strip())
                job = store.db.execute('SELECT finished_at FROM codex_review_jobs WHERE job_id=? AND run_id=?', (pair.get('codex_job_id'), run['run_id'])).fetchone()
                recorded = [e['at'] for e in run.get('events', []) if e.get('message','').startswith('JKSimmons: '+review.get('summary',''))]
                timestamp = job['finished_at'] if job and job['finished_at'] else recorded[0] if len(recorded)==1 else run.get('created_at')
                basis = 'Review completed' if job and job['finished_at'] else 'Review recorded' if len(recorded)==1 else 'Study started; exact review time unavailable'
                tested_revision = ws.revision(store, round_['revision_id'], scope) if round_.get('revision_id') else run.get('specific', {})
                proposals.append({'examples':tested_revision.get('examples',''),'event_id':'proposal-'+run['run_id']+'-'+str(round_['number'])+'-'+str(index),
                                  'created_at':timestamp,'time_basis':basis,'entry_number':index+1,'round_kind':round_.get('kind','learning'),
                                  'run_id':run['run_id'], 'round':round_['number'], 'entry':pair['label'],
                                  'instructions':instructions, 'reason':review.get('summary', ''),
                                  'change':change})
    history = []
    if meta['active'] and not any(r['revision_id']==meta['active']['revision_id'] for r in meta['history']):
        meta['history'].append(meta['active'])
    for revision in meta['history']:
        source = sources.get(revision['revision_id'])
        previous = None
        if source:
            try: previous = ws.revision(store, source['previous_revision_id'], scope)
            except ValueError: pass
        if previous is None:
            row = store.db.execute('SELECT * FROM workshop_revisions WHERE scope=? AND (created_at<? OR (created_at=? AND revision_id<?)) ORDER BY created_at DESC,revision_id DESC LIMIT 1',
                                   (scope, revision['created_at'], revision['created_at'], revision['revision_id'])).fetchone()
            previous = dict(row) if row else meta['builtin']
        history.append({**revision, 'source':source, 'change':changes(previous['instructions'], revision['instructions']),
                        'comparison': 'Previous instructions tested in this study' if source else 'Previous saved version (built-in if first)'})
    active = meta['active'] or meta['builtin']
    timeline = [{**r, 'event_id':'revision-'+r['revision_id'], 'kind':'saved', 'is_active':r['revision_id']==active.get('revision_id'), 'time_basis':'Version saved'} for r in history]
    linked = set()
    for p in proposals[:10]:
        adopted = json.loads(store.get_state('guideline-proposal:'+p['event_id'], '{}'))
        rid = adopted.get('revision_id')
        if rid: linked.add(rid)
        timeline.append({**p, 'kind':'proposal', 'revision_id':rid, 'activation':adopted,
                         'is_active':bool(rid and rid==active.get('revision_id'))})
    timeline = [e for e in timeline if e['kind']=='proposal' or e['revision_id'] not in linked]
    for e in timeline: e['content_hash'] = content_hash(scope,e['instructions'],e.get('examples',''))
    def order(item):
        try: return datetime.fromisoformat(item['created_at']).timestamp()
        except (TypeError, ValueError, KeyError): return float('-inf')
    timeline.sort(key=order, reverse=True)
    return {'scope':scope, 'active':active, 'latest':history[0] if history else meta['builtin'],
            'history':history, 'proposals':proposals[:10], 'timeline':timeline, 'history_limit':40}


def activate(store, body):
    """Owner click only. Resolve stored content, compare pointers, commit atomically."""
    scope = ws.scope_name(body.get('scope'))
    key = body.get('request_key')
    if not isinstance(key,str) or not 16<=len(key)<=100: raise ValueError('Activation identity is required')
    if 'expected_active' not in body: raise ValueError('Current active version is required')
    request_hash = hashlib.sha256(ws.packed(body).encode()).hexdigest()
    audit_key = 'guideline-activation:'+key
    with store._lock, store.db:
        store.db.execute('BEGIN IMMEDIATE')
        previous = json.loads(store.get_state(audit_key,'{}'))
        if previous:
            if previous['request_hash']!=request_hash: raise ValueError('Activation identity belongs to another selection')
            return library(store,scope)
        current = ws.active(store,scope)
        if (current or {}).get('revision_id')!=body['expected_active']: raise ValueError('Active guidelines changed in another session. Refresh and choose again.')
        item = next((e for e in library(store,scope)['timeline'] if e['event_id']==body.get('event_id')),None)
        if not item or item['content_hash']!=body.get('content_hash'): raise ValueError('The selected guideline text changed or is unavailable. Refresh before activating.')
        rid = item.get('revision_id')
        timestamp = ws.now()
        if not rid:
            rid = uuid.uuid4().hex
            instructions, examples = item['instructions'], item.get('examples','')
            if not 1<=len(instructions)<= (12000 if scope=='shared' else 4000) or len(examples)>8000: raise ValueError('Selected guidelines exceed the supported limits')
            store.db.execute('INSERT INTO workshop_revisions VALUES(?,?,?,?,?,?)', (rid,scope,'Owner approved reviewer proposal',instructions,examples,timestamp))
        store.db.execute('INSERT INTO workshop_active VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET revision_id=excluded.revision_id',(scope,rid))
        audit = {'revision_id':rid,'event_id':item['event_id'],'scope':scope,'at':timestamp,'actor':'owner','request_hash':request_hash,'previous_active':body['expected_active'],'content_hash':item['content_hash']}
        store.db.execute('INSERT INTO system_state(key,value) VALUES(?,?)',(audit_key,ws.packed(audit)))
        if item['kind']=='proposal':
            store.db.execute('INSERT INTO system_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('guideline-proposal:'+item['event_id'],ws.packed(audit)))
    return library(store,scope)
