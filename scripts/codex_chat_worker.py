"""Queue tools for the actual desktop-owned reviewer chat. Never starts a model."""
import argparse
import json
from pathlib import Path
from codex_review_bridge import Companion, DEFAULT_CONFIG, single_instance, BridgeRequestError


class ChatWorker:
    def __init__(self, config=DEFAULT_CONFIG, role='reviewer'):
        self.client = Companion(config)
        if role=='storytech':self.client.thread_id=self.client.config['storytech_thread_id']
        self.client.worker_id += '-'+role
        self.role=role
        self.active = self.client.folder / ('chat-'+role+'-active.json')
        (self.client.folder / ('chat-'+role+'-lock')).mkdir(exist_ok=True)

    def post(self, action, body=None):
        return self.client.post(action, {'transport': 'codex_chat', 'poll_interval': 0, **(body or {})})

    def save(self, value):
        tmp = self.active.with_suffix('.tmp')
        tmp.write_text(json.dumps(value), encoding='utf-8'); tmp.replace(self.active)

    def mirror_standards(self,export):
        import re
        scope=export['form']
        if not re.fullmatch('[a-z_]{1,50}',scope):raise ValueError('Invalid reviewer memory scope')
        folder=Path(self.client.config['context_dir'])
        folder.mkdir(parents=True,exist_ok=True)
        target=folder/('workshop-standards-'+scope+'.md')
        text='# Workshop reviewer standards · '+scope+'\n\nConfirmed app revision: '+export['revision_id']+'\nUpdated: '+export['at']+'\n\n'+export['reviewer_standards']+'\n'
        text+='\n## Owner corrections\n'+'\n'.join('- '+x for x in export.get('owner_corrections',[]))
        text+='\n\n## Reviewer interpretations (not owner instructions)\n'+'\n'.join('- '+x for x in export.get('reviewer_inferences',[]))+'\n'
        temp=target.with_suffix('.tmp');temp.write_text(text,encoding='utf-8');temp.replace(target)

    def heartbeat(self):
        active = json.loads(self.active.read_text(encoding='utf-8')) if self.active.exists() else {}
        if active.get('memory_pending'):
            self.mirror_standards(active['memory_pending'])
            active.pop('memory_pending');self.save(active)
        pending = active.get('status') in ('claimed', 'reviewing')
        result = self.post('heartbeat', {**(active if pending else {}), 'state': 'reviewing' if pending else 'idle'})
        if pending and result.get('job_status') in ('completed', 'cancelled', 'failed'):
            self.save({**active, 'status': result['job_status']})
        return result

    def claim(self, turn_id, job_id=None):
        if not turn_id.strip(): raise ValueError('Read the actual current Codex turn identity first')
        with single_instance(self.client.folder / ('chat-'+self.role+'-lock')):
            previous = json.loads(self.active.read_text(encoding='utf-8')) if self.active.exists() else {}
            if previous.get('memory_pending'):
                self.mirror_standards(previous.pop('memory_pending'));self.save(previous)
            if previous.get('status') in ('claimed', 'reviewing'):
                raise RuntimeError('Unfinished native review: inspect the chat and job; no automatic replay')
            reply = self.post('claim', {'job_id': job_id} if job_id else None); job = reply.get('job')
            if not job: return {'job': None}
            value = {'job_id': job['job_id'], 'lease': reply['lease'], 'turn_id': turn_id, 'status': 'claimed'}
            self.save(value)  # Persist before acknowledging any model work.
            self.post('started', value)
            self.save({**value, 'status': 'reviewing'})
            # Lease and private transport credential never enter model-visible output.
            return {'job': job}

    def finish(self, review=None, error=None):
        value = json.loads(self.active.read_text(encoding='utf-8'))
        if value.get('status') != 'reviewing': raise RuntimeError('No active native review')
        if error:
            self.post('fail', {**value, 'error': error})
            self.save({**value, 'status': 'failed'})
            self.post('heartbeat', {'state': 'error'})
        else:
            try:
                reply=self.post('complete', {**value, 'review': review})
            except BridgeRequestError as exc:
                # A definitive rejection must stop the app's waiter promptly.
                # Never retry a submission or turn a network uncertainty into
                # a new review. The caller's original JSON file is retained.
                if exc.status==400:
                    try:
                        self.post('fail',{**value,'error':'Reviewer submission rejected: '+str(exc)})
                        self.save({**value,'status':'failed'})
                        self.post('heartbeat',{'state':'error'})
                    except Exception:
                        pass  # Preserve the original rejection and uncertain lease.
                raise
            completed={**value,'status':'completed'}
            if reply.get('standards_export'):
                completed['memory_pending']=reply['standards_export']
                self.save(completed)  # App completion is durable before local file I/O.
                self.mirror_standards(completed['memory_pending'])
                completed.pop('memory_pending')
            self.save(completed)
            self.post('heartbeat', {'state': 'idle'})
        return {'ok': True, 'job_id': value['job_id']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['heartbeat', 'claim', 'complete', 'fail', 'self-test', 'technical-test'])
    parser.add_argument('--config', default=str(DEFAULT_CONFIG))
    parser.add_argument('--role',choices=['reviewer','storytech'],default='reviewer')
    parser.add_argument('--turn-id', default='')
    parser.add_argument('--job-id')
    parser.add_argument('--file')
    parser.add_argument('--message')
    parser.add_argument('--new-attempt', action='store_true')
    args = parser.parse_args(); worker = ChatWorker(args.config,args.role)
    (worker.client.folder / ('chat-'+args.role+'-lock')).mkdir(exist_ok=True)
    if args.action == 'claim': result = worker.claim(args.turn_id, args.job_id)
    elif args.action == 'complete': result = worker.finish(review=json.loads(Path(args.file).read_text(encoding='utf-8-sig')))
    elif args.action == 'fail': result = worker.finish(error=args.message or 'Human attention required')
    elif args.action == 'technical-test': result=worker.post('technical-test')
    elif args.action == 'self-test': result = worker.post('self-test', {'new_attempt': args.new_attempt})
    else: result = worker.heartbeat()
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))


if __name__ == '__main__': main()
