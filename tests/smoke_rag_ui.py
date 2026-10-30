"""Disposable authenticated RAG GUI and HTTP checks. Fake provider only."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]


def main():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        os.environ.update(NCCE_DB_PATH=str(Path(folder)/'rag.db'),NCCE_REQUIRE_AUTH='1',
            NCCE_ACCESS_PASSWORD=secrets.token_urlsafe(24),NCCE_SESSION_SECRET=secrets.token_urlsafe(40),
            NCCE_OPENAI_API_KEY='',OPENAI_API_KEY='',NCCE_AUTO_WRITE_ENABLED='0')
        import server
        import writing_rag as rag
        import llm_writer as writer
        from test_writing_rag import add
        from test_writer_pipeline import draft
        from access import make_session_token
        with server.store.db:add(server.store,'Recorded fuel reference','Promethium fuel tanks and storage. This is a general reference, not a campaign event.',kind='reference')
        class Response:
            headers={}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return json.dumps({'id':'fake-rag-response','output':[{'content':[{'type':'output_text','text':json.dumps(draft())}]}],'usage':{}}).encode()
        writer.reset_budget(1,'rag-smoke-only')
        with patch.object(writer,'API_KEY','disposable-fake-key'),patch.object(writer,'urlopen',return_value=Response()):
            _,status=writer.write(server.store,'territory_origin',{'subject':'Promethium Cache'},trace={'subject_name':'Saved fuel draft'})
        assert status['status']=='ready'
        server.store.db.execute("INSERT INTO writer_requests(run_id,form,subject_name,model,requested_at,finished_at,status) VALUES('missing-audit-fixture','territory_origin','Missing retained inputs','fake','2026-10-29','2026-10-29','failed')")
        server.store.db.commit()
        initial_request_count=server.store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]
        forbidden=patch.object(writer,'_call',side_effect=AssertionError('GUI must not call the writer'));forbidden.start()
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.H);threading.Thread(target=http.serve_forever,daemon=True).start()
        base='http://127.0.0.1:'+str(http.server_address[1]);cookie=make_session_token(server.SESSION_KEY)
        client=build_opener(ProxyHandler({}))
        def call(path,body=None,authenticated=True,origin=base):
            headers={'Content-Type':'application/json','Origin':origin}
            if authenticated:headers['Cookie']='ncce_session='+cookie
            request=Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
            try:
                with client.open(request,timeout=10) as response:return response.status,json.load(response)
            except HTTPError as e:return e.code,json.load(e)
        try:
            assert call('/api/workshop/rag/home',authenticated=False)[0]==401
            assert call('/api/workshop/rag/source',{'source':{}},origin='https://foreign.invalid')[0]==403
            assert call('/api/workshop/rag/source',{'source':{}})[0]==400
            server._writer_pipeline_guard.acquire()
            try:assert call('/api/workshop/rag/sync',{})[0]==409
            finally:server._writer_pipeline_guard.release()
            corpus_before=rag.corpus(server.store)[3]
            with server.store.db:server.store.db.execute("INSERT INTO lore_sources(title,source_type,content) VALUES('Invalid import fixture','canonical player-authored lore','')")
            assert call('/api/workshop/rag/sync',{})[0]==400
            assert rag.corpus(server.store)[3]==corpus_before and not server.store.db.in_transaction
            with server.store.db:server.store.db.execute("DELETE FROM lore_sources WHERE title='Invalid import fixture'")
            before=server.store.db.execute('SELECT count(*) FROM system_state').fetchone()[0]
            assert call('/api/workshop/rag/preview?form=territory_origin&query=Promethium')[0]==200
            assert call('/api/workshop/rag/history')[0]==200
            assert server.store.db.execute('SELECT count(*) FROM system_state').fetchone()[0]==before
            runtime=Path(r'C:\Users\Blazej\.cache\codex-runtimes\codex-primary-runtime\dependencies\node')
            artifacts=ROOT.parent/'tmp/rag-ui-smoke';artifacts.mkdir(parents=True,exist_ok=True)
            script=artifacts/'rag-smoke.cjs'
            script.write_text(r'''
const assert=require('node:assert/strict');
const {chromium}=require(process.env.NCCE_PLAYWRIGHT);
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1100}});
  await context.addCookies([{name:'ncce_session',value:process.env.NCCE_COOKIE,url:process.env.NCCE_URL,httpOnly:true,sameSite:'Strict'}]);
  await context.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());
  const page=await context.newPage(),errors=[],posts=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST')posts.push(r.url());});
  await page.goto(process.env.NCCE_URL+'/#retrieval');
  await page.getByRole('heading',{name:'Writing context · RAG',exact:true}).waitFor();
  await page.screenshot({path:process.env.NCCE_ARTIFACTS+'/overview.png'});
  await page.getByText(/Source library ·/).click();
  await page.getByRole('button',{name:'Refresh imports',exact:true}).waitFor();
  assert.equal(posts.length,0,'Opening is read-only');
  assert.ok(await page.locator('[data-rag-sample] option').count()>1,'Real subjects are available');
  await page.getByLabel('Preview a real subject',{exact:true}).selectOption({index:1});
  await page.getByRole('button',{name:'Preview context',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Context preview ready.'}).waitFor();
  await page.getByText('Current subject packet used for this preview',{exact:true}).waitFor();
  await page.getByLabel('Preview a real subject',{exact:true}).selectOption('');
  await page.getByRole('button',{name:'Add owner source',exact:true}).click();
  const title='Copper lantern <script>window.bad=1</script>';
  await page.getByLabel('Title',{exact:true}).fill(title);
  await page.getByLabel('Complete source text',{exact:true}).fill('Copper lanterns identify the fuel store. An illustrative custom, not an established campaign fact.');
  await page.getByRole('button',{name:'Save source',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Source saved.'}).waitFor();
  assert.equal(await page.evaluate(()=>window.bad),undefined);
  const originalText='Copper lanterns identify the fuel store. An illustrative custom, not an established campaign fact.';
  await page.getByLabel('Complete source text',{exact:true}).fill(originalText+' Updated owner explanation.');
  await page.getByRole('button',{name:'Save source',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Source saved.'}).waitFor();
  await page.getByText('Source version and indexed passages',{exact:true}).click();
  assert.equal(await page.locator('.rag-editor [data-rag="version"]').count(),2);
  await page.locator('.rag-editor [data-rag="version"]').last().click();
  await page.waitForFunction(expected=>document.querySelector('[data-rag-field="text"]').value===expected,originalText);
  await page.getByRole('button',{name:'Save source',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Source saved.'}).waitFor();

  await page.getByLabel('Subject and search terms',{exact:true}).fill('copper lantern fuel');
  await page.getByRole('button',{name:'Preview context',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Context preview ready.'}).waitFor();
  assert.ok(await page.locator('.rag-passage').filter({hasText:title}).count()>0);
  let card=page.locator('.rag-source-list article').filter({has:page.getByRole('heading',{name:title,exact:true})});
  await card.getByLabel('Include this source',{exact:true}).uncheck();
  await card.getByRole('button',{name:'Save selection',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Source selection saved'}).waitFor();
  await page.getByRole('button',{name:'Preview context',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Context preview ready.'}).waitFor();
  assert.equal(await page.locator('.rag-passage').filter({hasText:title}).count(),0);
  await page.getByText('Pipeline settings',{exact:true}).click();
  await page.getByLabel('Retrieve supporting material for future writing',{exact:true}).uncheck();
  await page.getByRole('button',{name:'Save pipeline settings',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Pipeline settings saved.'}).waitFor();
  await page.getByRole('button',{name:'Preview context',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Context preview ready.'}).waitFor();
  assert.equal(await page.locator('.rag-passage').count(),0);
  await page.getByRole('button',{name:'Recent pipeline changes',exact:true}).click();
  await page.getByText('Recent source and setting changes',{exact:true}).waitFor();
  await page.getByRole('button',{name:/Missing retained inputs · failed/}).click();
  await page.getByRole('button',{name:'Download available input record',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Download exact inputs as JSON',exact:true}).count(),0);
  await page.getByText('The complete provider request was not retained for this historical attempt. Available fragments are shown; missing inputs are not reconstructed.',{exact:true}).waitFor();
  await page.getByRole('button',{name:/Saved fuel draft · succeeded/}).click();
  await page.getByRole('button',{name:'Download exact inputs as JSON',exact:true}).waitFor();
  assert.ok(await page.locator('.rag-passage').count()>0,'Past selected passages survive disabling retrieval');
  await page.getByText('Exact writing instructions',{exact:true}).click();
  assert.ok(await page.getByText('Retrieved reference authority',{exact:false}).count()>0);
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('button',{name:'Download exact inputs as JSON',exact:true}).click();
  const download=await downloadPromise;await download.saveAs(process.env.NCCE_ARTIFACTS+'/exact-inputs.json');
  assert.equal(posts.filter(u=>!u.includes('/rag/')).length,0,'All writes are local library controls only');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:process.env.NCCE_ARTIFACTS+'/desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'mobile overflow');
  await page.screenshot({path:process.env.NCCE_ARTIFACTS+'/mobile.png',fullPage:true});
  await page.getByRole('button',{name:'Writer Workshop',exact:true}).click();
  await page.getByRole('heading',{name:'Writer Workshop',exact:true}).waitFor();
  assert.notEqual(await page.evaluate(()=>location.hash),'#retrieval');
  assert.deepEqual(errors,[]);
  console.log('PASS RAG browser: source create/escape/exclude, dry-run, settings, disable, immutable request inspection, JSON export, navigation, desktop/mobile bounds.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
''',encoding='utf-8')
            result=subprocess.run([str(runtime/'bin/node.exe'),str(script)],env={**os.environ,'NCCE_URL':base,'NCCE_COOKIE':cookie,
                'NCCE_ARTIFACTS':str(artifacts),'NCCE_PLAYWRIGHT':str(runtime/'node_modules/playwright')},capture_output=True,text=True,timeout=100,creationflags=0x08000000 if os.name=='nt' else 0)
            print(result.stdout)
            if result.returncode:print(result.stderr);raise AssertionError('RAG browser smoke failed')
            exported=json.loads((artifacts/'exact-inputs.json').read_text())
            assert exported['retrieval']['selected'] and 'instructions' in exported['prompt']
            assert server.store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]==initial_request_count
            print('PASS RAG HTTP: authentication, origin, busy protection, validation, read-only previews, no GUI model calls.')
        finally:
            forbidden.stop();http.shutdown();http.server_close();server.store.close()


if __name__=='__main__':main()
