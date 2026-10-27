"""Queue tools for the actual desktop-owned reviewer chat. Never starts a model."""
import argparse
import json
from pathlib import Path
from codex_review_bridge import Companion, DEFAULT_CONFIG, single_instance


class ChatWorker:
    def __init__(self, config=DEFAULT_CONFIG):
        self.client = Companion(config)
        self.client.worker_id += '-chat'
        self.active = self.client.folder / 'chat-active.json'
        (self.client.folder / 'chat-lock').mkdir(exist_ok=True)

    def post(self, action, body=None):
        return self.client.post(action, {'transport': 'codex_chat', 'poll_interval': 300, **(body or {})})

    def save(self, value):
        tmp = self.active.with_suffix('.tmp')
        tmp.write_text(json.dumps(value), encoding='utf-8'); tmp.replace(self.active)

    def heartbeat(self):
        active = json.loads(self.active.read_text(encoding='utf-8')) if self.active.exists() else {}
        pending = active.get('status') in ('claimed', 'reviewing')
        result = self.post('heartbeat', {**(active if pending else {}), 'state': 'reviewing' if pending else 'idle'})
        if pending and result.get('job_status') in ('completed', 'cancelled', 'failed'):
            self.save({**active, 'status': result['job_status']})
        return result

    def claim(self, turn_id):
        if not turn_id.strip(): raise ValueError('Read the actual current Codex turn identity first')
        with single_instance(self.client.folder / 'chat-lock'):
            previous = json.loads(self.active.read_text(encoding='utf-8')) if self.active.exists() else {}
            if previous.get('status') in ('claimed', 'reviewing'):
                raise RuntimeError('Unfinished native review: inspect the chat and job; no automatic replay')
            reply = self.post('claim'); job = reply.get('job')
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
            self.post('complete', {**value, 'review': review})
            self.save({**value, 'status': 'completed'})
            self.post('heartbeat', {'state': 'idle'})
        return {'ok': True, 'job_id': value['job_id']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['heartbeat', 'claim', 'complete', 'fail', 'self-test'])
    parser.add_argument('--config', default=str(DEFAULT_CONFIG))
    parser.add_argument('--turn-id', default='')
    parser.add_argument('--file')
    parser.add_argument('--message')
    parser.add_argument('--new-attempt', action='store_true')
    args = parser.parse_args(); worker = ChatWorker(args.config)
    (worker.client.folder / 'chat-lock').mkdir(exist_ok=True)
    if args.action == 'claim': result = worker.claim(args.turn_id)
    elif args.action == 'complete': result = worker.finish(review=json.loads(Path(args.file).read_text(encoding='utf-8-sig')))
    elif args.action == 'fail': result = worker.finish(error=args.message or 'Human attention required')
    elif args.action == 'self-test': result = worker.post('self-test', {'new_attempt': args.new_attempt})
    else: result = worker.heartbeat()
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))


if __name__ == '__main__': main()
