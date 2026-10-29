"""Large native handoffs stay complete without relying on console capacity."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import contextlib
import io
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'scripts'), str(ROOT/'tests')]
from codex_job_packet import JobPackets, PAGE_OUTPUT_LIMIT
from codex_chat_worker import ChatWorker
import codex_chat_worker
from test_workshop_optimizer import rejects


def large_job(kind='review'):
    return {'job_id':'large-native-job','kind':kind,'output_schema':{'required':['exact']},
            'comparison_instructions':['Full protected context. '+('Śląsk 🛠️ "\\\n'*5000), 'Second arm. '+('No invented outcomes. '*4000)],
            'candidates':[{'body':'Saved draft A'},{'body':'Saved draft B'}],
            'packet':{'evidence':['fact '+str(i) for i in range(1500)]},
            'preceding_reviews':[{'summary':'Prior judgement. '*2000}],
            'reviewer_standards':{'instructions':'Owner standards. '*3000}}


def reconstruct(store, manifest, pointer=''):
    offset=0;parts=[]
    while True:
        page=store.read(manifest['job']['job_id'],manifest['packet']['sha256'],pointer,offset)
        assert len(json.dumps(page,ensure_ascii=True))<=PAGE_OUTPUT_LIMIT
        assert page['offset']==offset and (page['next_offset']>offset or page['complete'])
        parts.append(page['text']);offset=page['next_offset']
        if page['complete']:return json.loads(''.join(parts))


def test_oversized_unicode_packet_round_trips_and_every_section_is_lossless():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        store=JobPackets(folder,'reviewer');job=large_job();before=copy.deepcopy(job)
        assert len(json.dumps(job))>65536
        manifest=store.save(job,'actual-native-turn',('private-test-lease','private-test-token'))
        assert len(json.dumps(manifest))<PAGE_OUTPUT_LIMIT and manifest['packet']['index_complete']
        assert reconstruct(store,manifest)==job==before
        for section in manifest['packet']['sections']:
            value=reconstruct(store,manifest,section['pointer'])
            key=section['pointer'][1:].replace('~1','/').replace('~0','~')
            assert value==job[key]
        assert reconstruct(store,manifest,'/comparison_instructions/0')==job['comparison_instructions'][0]
        rejects(lambda:store.save(job,'second-turn'))


def test_both_agent_roles_and_consolidation_use_the_same_private_protocol():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        for role in ('reviewer','storytech'):
            for kind in ('review','editorial_consolidation','technical_investigation'):
                store=JobPackets(folder,role);job=large_job(kind);job['job_id']+='-'+kind.replace('_','-')
                manifest=store.save(job,'native-turn')
                assert reconstruct(store,manifest)==job
                assert manifest['packet']['path'].startswith(str(Path(folder)/'packets'))


def test_bad_hash_pointer_offset_or_role_never_returns_partial_unverified_input():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        store=JobPackets(folder,'reviewer');manifest=store.save(large_job(),'native-turn');digest=manifest['packet']['sha256']
        for name in ('../active','..\\config','/absolute','bad/name',''):
            rejects(lambda:store.info(name))
        for pointer,offset,limit in [('/missing',0,4000),('/candidates/99',0,4000),('/candidates/-1',0,4000),('bad',0,4000),('/bad~2',0,4000),('',-1,4000),('',0,4001),('',999999999,10)]:
            rejects(lambda:store.read('large-native-job',digest,pointer,offset,limit))
        rejects(lambda:store.read('large-native-job','0'*64))
        rejects(lambda:JobPackets(folder,'other'))
        try:JobPackets(folder,'storytech').info('large-native-job')
        except FileNotFoundError:pass
        else:raise AssertionError('Another role read this packet')
        path=Path(manifest['packet']['path']);altered=json.loads(path.read_text(encoding='utf-8'))
        original=path.read_text(encoding='utf-8');altered['job']['packet']['evidence'][0]='altered fact'
        path.write_text(json.dumps(altered),encoding='utf-8')
        rejects(lambda:store.info('large-native-job'))
        path.write_text(original,encoding='utf-8')
        Path(manifest['packet']['path']).write_text('{}',encoding='utf-8')
        rejects(lambda:store.read('large-native-job',digest))


def test_packet_secrets_and_partial_writes_fail_closed():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        store=JobPackets(folder,'reviewer');job=large_job()
        rejects(lambda:store.save({**job,'lease':'not-input'},'turn'))
        rejects(lambda:store.save({**job,'packet':{'text':'private-secret'}},'turn',('private-secret',)))
        assert not store.path(job['job_id']).exists()
        with patch('os.fsync',side_effect=OSError('disk error')):
            try:store.save(job,'native-turn')
            except OSError:pass
            else:raise AssertionError('Partial write reported success')
        assert not store.path(job['job_id']).exists()
        store.save(job,'native-turn')


def test_native_claim_persists_before_start_and_lost_output_needs_no_second_claim():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        config=Path(folder)/'config.json'
        config.write_text(json.dumps({'base_url':'http://localhost','worker_id':'packet-test-worker','thread_id':'reviewer-thread','token':'private-transport-token','codex_executable':'codex'}))
        worker=ChatWorker(config);calls=[];job=large_job()
        def post(action,body=None):
            calls.append(action)
            if action=='claim':return {'job':job,'lease':'private-transport-lease'}
            if action=='started':assert worker.packets.load(job['job_id'])[0]['job']==job
            return {'ok':True}
        worker.post=post
        with patch('subprocess.Popen',side_effect=AssertionError('No model allowed')):
            manifest=worker.claim('actual-turn',job['job_id'])
            calls_before=list(calls)
            assert reconstruct(worker.packets,worker.packets.info(job['job_id']))==job
            assert calls==calls_before==['claim','started']
            public=json.dumps(manifest)+Path(manifest['packet']['path']).read_text(encoding='utf-8')
            assert 'private-transport-token' not in public and 'private-transport-lease' not in public
            try:worker.claim('another-turn',job['job_id'])
            except RuntimeError:pass
            else:raise AssertionError('Unfinished claim was replayed')


def test_cli_packet_reads_are_local_and_bounded():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        config=Path(folder)/'config.json'
        config.write_text(json.dumps({'base_url':'http://localhost','worker_id':'packet-test-worker','thread_id':'reviewer-thread','token':'private-transport-token','codex_executable':'codex'}))
        worker=ChatWorker(config);manifest=worker.packets.save(large_job(),'actual-turn')
        for args in (['packet-info','--job-id','large-native-job'],['read-packet','--job-id','large-native-job','--sha256',manifest['packet']['sha256'],'--section','/comparison_instructions/0']):
            out=io.StringIO()
            with patch.object(sys,'argv',['codex_chat_worker.py',*args,'--config',str(config)]), patch.object(ChatWorker,'post',side_effect=AssertionError('Local reads must not use the queue')), contextlib.redirect_stdout(out):
                codex_chat_worker.main()
            text=out.getvalue();assert len(text)<=PAGE_OUTPUT_LIMIT+1
            assert 'private-transport-token' not in text
            json.loads(text)


if __name__=='__main__':
    for name,test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test):test();print('PASS',name)
