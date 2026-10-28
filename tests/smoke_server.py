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
        env = {**os.environ,'NCCE_DB_PATH':str(Path(directory)/'smoke.db'),'NCCE_HOST':'127.0.0.1','PORT':str(port),
               'NCCE_REQUIRE_AUTH':'1','NCCE_ACCESS_PASSWORD':'disposable-test-passphrase',
               'NCCE_SESSION_SECRET':'disposable-test-signing-secret-000000000000','NCCE_OPEN_BROWSER':'0','NCCE_SECURE_COOKIES':'0'}
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
                    assert read('/healthz') == {'ok':True,'version':'0.17.0'}
                    break
                except (URLError,TimeoutError):
                    if process.poll() is not None or time.monotonic()>deadline:
                        raise RuntimeError('App failed to start')
                    time.sleep(0.25)
            for path,body in [('/api/dashboard',None),('/api/workshop',None),('/api/workshop/generate',{'request_key':'no-auth-000000000000'}),('/api/login',{'password':'wrong'})]:
                try:
                    read(path,body)
                    raise AssertionError('Protected request unexpectedly succeeded')
                except HTTPError as error:
                    assert error.code == 401
            assert read('/api/login',{'password':env['NCCE_ACCESS_PASSWORD']})['ok']
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
            assert health['schema_version'] == 15 and health['story_revision'] and health['writer']['status'] in ('ready','unconfigured')
            dashboard = read('/api/dashboard')
            timeline=read('/api/history')
            assert all('playtime_seconds' in battle and 'local_territory_id' in battle for battle in timeline['battles'])
            assert dashboard['writing_policy']['date']['year'] == 998
            assert dashboard['battles'] and dashboard['battles'][0]['report_document']
            assert dashboard['battles'][0]['report_document']['writer_status'] in ('pending','unconfigured')
            fighters = [f for gang in dashboard['gangs'] for f in read('/api/gangs/'+gang['gang_id'])['fighters']]
            for name in ('Mara Kel','Maex'):
                fighter = next(f for f in fighters if f['name'] == name)
                detail = read('/api/fighters/'+str(fighter['id']))
                assert detail['event_clock']['basis']=='fighter_relevant_events' and detail['event_clock']['half_life_events']==10
                assert detail['mind_policy']['fixed_expiry'] is False
                assert detail['memories'] and all(m['writer_status'] in ('ready','unconfigured','error','pending') for m in detail['memories'])
                assert all(m['evidence'] for m in detail['memories'])
                assert all(m['date_display']['imperialDisplay'] for m in detail['memories'])
                if name == 'Mara Kel' and 'Critical Injury' in str(detail.get('effects')):
                    assert detail['mind_status']['separate_prose'] and detail['mind_status']['pending'] >= 1
            gang_details=[read('/api/gangs/'+gang['gang_id']) for gang in dashboard['gangs']]
            assert any(gang['narrative_stream'] for gang in gang_details)
            assert all(g['history_document'] is None for g in gang_details)
            assert all(not g['backstory'] or g['backstory_source']=='player-authored / campaign Sheet' for g in gang_details)
            archive=read('/api/archive')['stories']
            assert [story['title'] for story in archive]==['The Prospect','The Deep Answers']
            assert archive[0]['content'].endswith('Now, at last, the real work could begin.')
            assert archive[1]['content'].endswith('He drew the line anyway.')
            workshop=read('/api/workshop')
            assert workshop['samples'] and len(workshop['forms'])==15
            mind_sample=next(s for s in workshop['samples'] if s['form']=='fighter_mind')
            thought_context=read('/api/workshop/sample?key='+mind_sample['key'])
            assert thought_context['packet']['causes'] and thought_context['packet']['source_memory_ids']
            source=next(s for s in workshop['samples'] if s['form']=='fighter_memory')
            selected=read('/api/workshop/sample?key='+source['key'])
            policy=read('/api/workshop/policy?scope=fighter_memory')
            saved=read('/api/workshop/save-policy',{**policy['draft'],'label':'Disposable smoke revision'})
            assert read('/api/workshop/policy?scope=fighter_memory')['active'] is None
            read('/api/workshop/activate',{'scope':'fighter_memory','revision_id':saved['revision_id'],'expected_active':None})
            assert read('/api/workshop/policy?scope=fighter_memory')['active']['revision_id']==saved['revision_id']
            read('/api/workshop/activate',{'scope':'fighter_memory','revision_id':None,'expected_active':saved['revision_id']})
            imported=read('/api/workshop/import',{'sample_key':source['key']})
            inspected=read('/api/workshop/preview',{'sample_key':source['key']})
            assert inspected['packet']['creative_plan']['focus']=='recorded_event'
            reinspected=read('/api/workshop/preview',{'sample_key':source['key'],'plan_key':inspected['plan_key']})
            assert reinspected['packet']==inspected['packet']
            edited=read('/api/workshop/edit',{'trial_id':imported['trial_id'],'body':'I left the spanner beside the lamp.','composition':{}})
            assert edited['edits'][0]['document']['workshop_provenance']=='owner_edited_style_sample'
            assert edited['usage']['requests_attempted']==0
            hostile=Request(base+'/api/workshop/generate',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://foreign.invalid'})
            try: client.open(hostile); raise AssertionError('Cross-origin workshop mutation succeeded')
            except HTTPError as error: assert error.code==403
            for place in dashboard['territories']:
                detail=read('/api/territories/'+str(place['id']))
                assert 'narrative_stream' in detail and detail['history_document']['document_type']=='survey_note'
            subject=next(f for f in fighters if f['name']=='Maex')
            edited=read('/api/fighters/'+str(subject['id'])+'/identity',{'identity':{'voice':['patient'],'work':['equipment maintenance']}})
            assert edited['writer_identity']['voice']==['patient']
            assert edited['voice_profile']['writer_context']['identity']['work']==['equipment maintenance']
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
