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
                              headers={'Content-Type':'application/json'})
            with client.open(request,timeout=5) as response:
                return json.load(response)

        try:
            deadline = time.monotonic()+45
            while True:
                try:
                    assert read('/healthz') == {'ok':True,'version':'0.8.0'}
                    break
                except (URLError,TimeoutError):
                    if process.poll() is not None or time.monotonic()>deadline:
                        raise RuntimeError('App failed to start')
                    time.sleep(0.25)
            for path,body in [('/api/dashboard',None),('/api/login',{'password':'wrong'})]:
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
            assert health['schema_version'] == 6 and health['story_revision'] and health['writer']['status'] in ('ready','unconfigured')
            dashboard = read('/api/dashboard')
            assert dashboard['writing_policy']['date']['year'] == 998
            assert dashboard['battles'] and dashboard['battles'][0]['report_document']
            if health['writer']['configured']:
                assert dashboard['battles'][0]['report_document']['blocks']
            else:
                assert dashboard['battles'][0]['report_document']['writer_status']=='unconfigured'
            fighters = [f for gang in dashboard['gangs'] for f in read('/api/gangs/'+gang['gang_id'])['fighters']]
            for name in ('Mara Kel','Maex'):
                fighter = next(f for f in fighters if f['name'] == name)
                detail = read('/api/fighters/'+str(fighter['id']))
                assert detail['memories'] and all(m['writer_status'] in ('ready','unconfigured','error','pending') for m in detail['memories'])
                assert all(m['evidence'] for m in detail['memories'])
                assert all(m['date_display']['imperialDisplay'] for m in detail['memories'])
                if name == 'Mara Kel' and 'Critical Injury' in str(detail.get('effects')):
                    assert any('critical' in m['tags'] for m in detail['mind'])
            gang_details=[read('/api/gangs/'+gang['gang_id']) for gang in dashboard['gangs']]
            assert any(gang['narrative_stream'] for gang in gang_details)
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
