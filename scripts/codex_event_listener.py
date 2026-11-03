"""Wait cheaply for review work; wake the actual desktop chat once per queued job."""
import argparse
import json
import os
import re
import subprocess
import time
from codex_review_bridge import Companion, DEFAULT_CONFIG, single_instance, BridgeRequestError
from urllib.error import URLError

class DispatchUncertain(RuntimeError):pass


def open_chat(thread_id):
    """Load the existing desktop chat so its already queued message can run."""
    if not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',thread_id):
        raise ValueError('Invalid native chat identity')
    if os.name!='nt':raise RuntimeError('Automatic native chat opening is configured for Windows only')
    os.startfile('codex://threads/'+thread_id)


class EventListener:
    def __init__(self, config=DEFAULT_CONFIG, opener=None):
        self.client = Companion(config)
        self.opener=opener or open_chat
        self.client.worker_id += '-listener'
        self.folder = self.client.folder / 'notifications'
        self.folder.mkdir(exist_ok=True)

    def post(self, action, body=None):
        return self.client.post(action, {'transport':'queue_listener','poll_interval':0, **(body or {})})

    def wake(self,journal,target):
        value=json.loads(journal.read_text(encoding='utf-8'))
        if value.get('chat_open_requested') or self.client.config.get('open_chat_on_job',True) is False:return
        # Persist intent before requesting UI navigation. Neither an uncertain
        # launch nor a restarted listener sends another message or reopens it.
        value.update(chat_open_requested=True,chat_open_at=time.time())
        journal.write_text(json.dumps(value),encoding='utf-8')
        try:self.opener(target)
        except Exception as exc:
            raise DispatchUncertain('Native chat opening failed; the queued message is retained. Open the agent chat manually; no message was resent.') from exc

    def tick(self):
        reply = self.post('events', {'wait_seconds':15})
        job = reply.get('job_id')
        if not job: return False  # No CLI or model invocation on empty checks.
        if not isinstance(job,str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,100}',job): raise ValueError('Invalid event identifier')
        kind=reply.get('kind','review')
        technical=kind in ('technical_investigation','technical_repair','technical_release')
        target=self.client.config.get('storytech_thread_id') if technical else self.client.thread_id
        if not target or reply.get('thread_id',target)!=target:raise ValueError('Event agent identity does not match local configuration')
        journal = self.folder / (job + '.json')
        if journal.exists():
            value = json.loads(journal.read_text(encoding='utf-8'))
            if value['status'] != 'sent': raise DispatchUncertain('Uncertain event dispatch; human inspection required')
            self.wake(journal,target)
            value=json.loads(journal.read_text(encoding='utf-8'))
            if not value.get('acknowledged'):
                self.post('notified', {'job_id':job,'thread_id':target})
                journal.write_text(json.dumps({**value,'acknowledged':True}),encoding='utf-8')
            time.sleep(2)
            return False
        # An uncertain CLI response is never automatically re-dispatched.
        journal.write_text(json.dumps({'job_id':job,'status':'dispatching'}),encoding='utf-8')
        message = ('NCCE REVIEW READY '+job+'. The owner authorized event-driven Workshop review. '
            'Follow C:\\Codex\\NCCE\\writing-quality-dev\\docs\\CODEX_CHAT_REVIEWER.md. '
            'Read your actual current native turn ID, then use codex_chat_worker.py claim --job-id '+job+' --turn-id ACTUAL_ID. '
            'Review this job yourself using this chat and saved owner standards; save validated JSON and complete --file. '
            'Process ONLY this job, then stop. If cancelled/missing, stop quietly. No timer, idle checks, new diagnostics, '
            'writer calls, policy/canon changes, other models or messages to other chats. Never display credentials or leases.')
        if technical:
            message=('NCCE TECH JOB '+job+'. Kind: '+kind+'. The owner connected THIS StoryTechMan chat to Workshop. '
                'Follow C:\\Codex\\NCCE\\writing-quality-dev\\docs\\CODEX_STORYTECH_WORKER.md. '
                'Read your actual current native turn ID and claim ONLY this job using codex_chat_worker.py --role storytech claim --job-id '+job+' --turn-id ACTUAL_ID. '
                'Inspect the actual packet, source and approval record. Investigations are READ ONLY. Repair/release jobs need their exact human approval in the packet. '
                'Return the required report with complete --role storytech --file. No writer calls, writing-policy activation, authoritative campaign/canon edits, timers, other models or messages to other chats. Never display credentials or leases. Stop after this job.')
        elif kind=='production_review':
            message=('NCCE PRODUCTION REVIEW '+job+'. The owner enabled bounded production reviews in this JKSimmons chat. '
                'Follow C:\\Codex\\NCCE\\writing-quality-dev\\docs\\CODEX_CHAT_REVIEWER.md, especially kind=production_review. '
                'Read your actual native turn ID and claim ONLY this job using codex_chat_worker.py claim --job-id '+job+' --turn-id ACTUAL_ID. '
                'Read the complete saved packet with the bounded packet reader. Review this SINGLE draft against its exact source and instructions. '
                'Return the exact production schema using complete --file. The app controls rewrites and the five-attempt cap. '
                'No writer calls, guideline activation, source edits, other models, timers or messages to other chats. End after this job.')
        elif kind=='editorial_consolidation':
            message=('NCCE FEEDBACK UPDATE '+job+'. The owner authorized one post-study standards update from sealed app feedback. '
                'Follow C:\\Codex\\NCCE\\writing-quality-dev\\docs\\CODEX_CHAT_REVIEWER.md. '
                'Read your actual native turn ID, claim ONLY this job with codex_chat_worker.py claim --job-id '+job+' --turn-id ACTUAL_ID. '
                'This is feedback consolidation, not a blind draft review. Return the exact claimed schema and complete --file. '
                'The helper mirrors confirmed standards to durable reviewer memory. No writer calls, activation, source edits, '
                'spending grants, timers, other models or messages to other chats. End after this job.')
        try:
            result = subprocess.run([self.client.executable,'queue','--thread',target,'--message',message],
                capture_output=True,text=True,encoding='utf-8',timeout=30,
                creationflags=0x08000000 if os.name=='nt' else 0)
            if result.returncode != 0: raise RuntimeError('Codex queue delivery failed; inspect the reviewer before retrying')
            journal.write_text(json.dumps({'job_id':job,'status':'sent'}),encoding='utf-8')
        except Exception as exc:
            try:self.post('heartbeat',{'state':'error'})
            except Exception:pass
            raise DispatchUncertain('Queue delivery is uncertain; inspect the native chat before any retry') from exc
        # Persist sent before the server acknowledgement: reconnecting may retry
        # metadata, never the CLI notification or a model turn.
        self.wake(journal,target)
        self.post('notified', {'job_id':job,'thread_id':target})
        value=json.loads(journal.read_text(encoding='utf-8'))
        journal.write_text(json.dumps({**value,'acknowledged':True}),encoding='utf-8')
        return True


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',default=str(DEFAULT_CONFIG));parser.add_argument('--once',action='store_true')
    args=parser.parse_args();listener=EventListener(args.config)
    with single_instance(listener.folder):
        while True:
            try:listener.tick()
            except Exception as exc:
                # Bounded metadata only; no tokens, prompts, model output or leases.
                message=str(exc).replace(listener.client.config['token'],'[redacted]')[:240]
                with open(listener.folder/'listener.log','a',encoding='utf-8') as out:
                    out.write(json.dumps({'at':time.time(),'error':type(exc).__name__,'message':message})+'\n')
                try:listener.post('heartbeat',{'state':'error'})
                except Exception:pass
                # Only a read/heartbeat transport failure can reconnect without a model call.
                transient=isinstance(exc,(TimeoutError,URLError)) or (isinstance(exc,BridgeRequestError) and exc.status in (408,429,500,502,503,504))
                if not transient or isinstance(exc,DispatchUncertain):return
                time.sleep(10)
            if args.once:break


if __name__=='__main__':main()
