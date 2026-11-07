"""Opt-in HTTP smoke check: starts a disposable authenticated app and reads the live Sheet.

Run from the repository: python tests/smoke_server.py
No campaign source is written and no production credentials are used.
"""
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0))
            port = probe.getsockname()[1]
        env = {**os.environ,'NCCE_OPENAI_API_KEY':'','NCCE_DB_PATH':str(Path(directory)/'smoke.db'),'NCCE_HOST':'127.0.0.1','PORT':str(port),
               'NCCE_REQUIRE_AUTH':'1','NCCE_ACCESS_PASSWORD':'disposable-test-passphrase',
               'NCCE_SESSION_SECRET':'disposable-test-signing-secret-000000000000','NCCE_OPEN_BROWSER':'0','NCCE_SECURE_COOKIES':'0',
               'NCCE_EXCHANGE_TOKEN':'disposable-exchange-token-for-http-smoke-000000'}
        process = subprocess.Popen([sys.executable,'src/server.py'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        base = f'http://127.0.0.1:{port}'
        cookies = CookieJar()
        client = build_opener(ProxyHandler({}),HTTPCookieProcessor(cookies))

        def read(path,body=None):
            request = Request(base+path,data=json.dumps(body).encode() if body is not None else None,
                              headers={'Content-Type':'application/json','Origin':base})
            with client.open(request,timeout=5) as response:
                return json.load(response)

        try:
            deadline = time.monotonic()+45
            while True:
                try:
                    assert read('/healthz') == {'ok':True,'version':'0.28.11'}
                    break
                except (URLError,TimeoutError):
                    if process.poll() is not None or time.monotonic()>deadline:
                        raise RuntimeError('App failed to start')
                    time.sleep(0.25)
            for path,body in [('/api/dashboard',None),('/api/writing-exchange',None),('/api/writing-exchange/relay/poll',{}),('/api/login',{'password':'wrong'})]:
                try:
                    read(path,body)
                    raise AssertionError('Protected request unexpectedly succeeded')
                except HTTPError as error:
                    assert error.code == 401
            assert read('/api/login',{'password':env['NCCE_ACCESS_PASSWORD']})['ok']
            assert isinstance(read('/api/writing-exchange')['deliveries'],list)
            assert any(cookie.name == 'ncce_session' and cookie.has_nonstandard_attr('HttpOnly') for cookie in cookies)
            while True:
                health = read('/api/health')
                if health['sync_status'] == 'ok':
                    break
                if health['sync_status'] == 'error':
                    raise AssertionError(health['sync_last_error'])
                if time.monotonic()>deadline:
                    raise AssertionError('Sheet sync did not finish')
                time.sleep(0.25)
            assert health['schema_version'] == 18 and health['story_revision'] and health['writer']['status']=='removed'
            dashboard = read('/api/dashboard')
            coverage=read('/api/prose-progress')
            assert len(coverage['categories'])==16 and coverage['generation_enabled'] is False
            assert next(r for r in coverage['categories'] if r['key']=='post_battle_addendum')['counts']['authored']==5
            assert sum(bool(b.get('post_battle_addendum')) for b in dashboard['battles'])==5
            assert all(0<=r['completed']<=r['written']<=r['total'] for r in coverage['categories'])
            timeline=read('/api/history')
            assert all('playtime_seconds' in battle and 'local_territory_id' in battle for battle in timeline['battles'])
            assert dashboard['writing_policy']['date']['year'] == 998
            assert dashboard['battles'] and dashboard['battles'][0]['report_document']
            assert dashboard['battles'][0]['report_document']['writer_status']=='paused'
            fighters = [f for gang in dashboard['gangs'] for f in read('/api/gangs/'+gang['gang_id'])['fighters']]
            anomalous=next(f for f in fighters if f['name']=='It That Spoke')
            dossier=read('/api/fighters/'+str(anomalous['id']))
            assert dossier['backstory_source']=='player-authored / campaign Sheet'
            assert dossier['backstory']==dossier['mechanics']['Backstory']
            assert 'Marcella Veyne' not in dossier['backstory'] and 'RETRIEVING GPD-C9' not in dossier['backstory']
            for name in ('Mara Kel','Maex'):
                fighter = next(f for f in fighters if f['name'] == name)
                detail = read('/api/fighters/'+str(fighter['id']))
                feed = read('/api/fighters/'+str(fighter['id'])+'/mind')
                assert feed == {key:detail[key] for key in ('id','status','mind','mind_status')}
                assert len(feed['mind']) <= 3 and all(thought['writer_status']=='ready' for thought in feed['mind'])
                assert detail['event_clock']['basis']=='fighter_relevant_events' and detail['event_clock']['half_life_events']==10
                assert detail['mind_policy']['fixed_expiry'] is False
                assert detail['memories'] and all(m['writer_status'] in ('ready','stale','paused') for m in detail['memories'])
                assert all(m['evidence'] for m in detail['memories'])
                assert all(m['date_display']['imperialDisplay'] for m in detail['memories'])
                if name == 'Mara Kel' and 'Critical Injury' in str(detail.get('effects')):
                    assert detail['mind_status']['separate_prose'] and detail['mind_status']['pending'] >= 1
            deceased=next(f for f in fighters if f['status']=='Killed')
            assert read('/api/fighters/'+str(deceased['id'])+'/mind')['mind']==[]
            gang_details=[read('/api/gangs/'+gang['gang_id']) for gang in dashboard['gangs']]
            assert any(gang['narrative_stream'] for gang in gang_details)
            assert all(g['history_document'] is None for g in gang_details)
            assert all(not g['backstory'] or g['backstory_source']=='player-authored / campaign Sheet' for g in gang_details)
            archive=read('/api/archive')['stories']
            assert [story['title'] for story in archive]==['The Prospect','The Deep Answers']
            assert archive[0]['content'].endswith('Now, at last, the real work could begin.')
            assert archive[1]['content'].endswith('He drew the line anyway.')
            for path in ('/api/workshop','/api/workshop/rag/sources','/api/native-author/catalog','/api/reviewer-bridge/claim'):
                try:read(path);raise AssertionError('Removed writing endpoint is active')
                except HTTPError as error:assert error.code==410
            for place in dashboard['territories']:
                detail=read('/api/territories/'+str(place['id']))
                assert 'narrative_stream' in detail and detail['history_document']['document_type']=='survey_note'
            subject=next(f for f in fighters if f['name']=='Maex')
            edited=read('/api/fighters/'+str(subject['id'])+'/identity',{'identity':{'voice':['patient'],'work':['equipment maintenance']}})
            assert edited['writer_identity']['voice']==['patient']
            assert edited['voice_profile']['writer_context']['identity']['work']==['equipment maintenance']
            def relay(path,payload):
                request=Request(base+'/api/writing-exchange/relay/'+path,data=json.dumps(payload).encode(),
                    headers={'Content-Type':'application/json','Authorization':'Bearer '+env['NCCE_EXCHANGE_TOKEN']})
                with client.open(request,timeout=10) as response:return json.load(response)
            packets=relay('poll',{})['packets']
            assert 0<len(packets)<=5
            request=packets[0]['request']
            payload={'request_id':request['request_id'],'source_revision':request['source_revision'],
                     'status':'READY','writer_text_md':'A disposable HTTP-test account.\n\n**Preserved exactly.**'}
            delivery=relay('deliver',payload)
            assert delivery['status']=='imported',delivery
            assert relay('deliver',payload)['receipt']==delivery['receipt']
            assert any(r['state']=='IMPORTED' for r in read('/api/writing-exchange')['automation']['requests'])
            try:
                read('/api/logout',{})
                read('/api/dashboard')
                raise AssertionError('Logout did not invalidate session access')
            except HTTPError as error:
                assert error.code == 401
            print('HTTP smoke passed: startup, authentication, cookie, live sync, schema, reports, fighter memories/Mind, logout')
        finally:
            process.terminate()
            output,_ = process.communicate(timeout=10)
            if process.returncode not in (0,1,-15):
                print(output[-2000:])


if __name__ == '__main__':
    main()
