"""Read-only guideline library and exact changes; never activates a revision."""
import difflib
import json
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
        if old: message += '\nRemoved/replaced: '+old[:180]+('…' if len(old)>180 else '')
        if new: message += '\nAdded: '+new[:180]+('…' if len(new)>180 else '')
    return message+'\nSee Writing guidelines for the full text and exact changes. Active NCCE instructions are unchanged.'


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
                proposals.append({'run_id':run['run_id'], 'round':round_['number'], 'entry':pair['label'],
                                  'instructions':instructions, 'reason':review.get('summary', ''),
                                  'change':change})
    history = []
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
    return {'scope':scope, 'active':meta['active'] or meta['builtin'], 'latest':history[0] if history else meta['builtin'],
            'history':history, 'proposals':proposals[:10], 'history_limit':40}
