"""Disposable authenticated browser smoke. Fake drafts, no external requests."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]


def main():
    from test_editorial_quality import request, review, fake_generator
    from test_workshop_optimizer import ready_bridge
    from access import make_session_token
    import workshop_optimizer as opt
    import llm_writer as writer
    artifacts=ROOT.parent/'tmp/editorial-ui-smoke'
    artifacts.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        os.environ.update(NCCE_DB_PATH=str(Path(folder)/'preview.db'),NCCE_REQUIRE_AUTH='1',
            NCCE_ACCESS_PASSWORD=secrets.token_urlsafe(24),NCCE_SESSION_SECRET=secrets.token_urlsafe(40),
            NCCE_OPENAI_API_KEY='',OPENAI_API_KEY='',
            NCCE_REVIEW_BRIDGE_TOKEN_SHA256=hashlib.sha256(b'disposable-editorial-smoke-token-only').hexdigest())
        import server
        ready_bridge(server.store)
        fixture_request=request(server.store,1)
        with patch.object(writer,'API_KEY','mock'), patch.object(writer,'_call',side_effect=AssertionError('No provider calls in browser smoke')) as forbidden:
            state,_=opt.queue(server.store,fixture_request)
            state=opt.execute(server.store,state['run_id'],generator=fake_generator,reviewer=lambda s,t,p,h:review(p))
            assert state['status']=='awaiting_owner'
            forbidden.assert_not_called()
        initial_requests=server.store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.H)
        threading.Thread(target=http.serve_forever,daemon=True).start()
        try:
            runtime=Path(r'C:\Users\Blazej\.cache\codex-runtimes\codex-primary-runtime\dependencies\node')
            script=artifacts/'smoke.cjs'
            script.write_text(r'''
const assert=require('node:assert/strict');
const {chromium}=require(process.env.NCCE_PLAYWRIGHT);
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try {
  const context=await browser.newContext({viewport:{width:1440,height:1100}});
  await context.addCookies([{name:'ncce_session',value:process.env.NCCE_PREVIEW_COOKIE,url:process.env.NCCE_PREVIEW_URL,httpOnly:true,sameSite:'Strict'}]);
  await context.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.NCCE_PREVIEW_URL+'/#workshop');
  await page.getByRole('heading',{name:'Writer Workshop',exact:true}).waitFor();
  await page.getByRole('heading',{name:'Your blind verdicts are needed',exact:true}).waitFor();
  assert.equal(await page.locator('.ws-blind-verdict').count(),2);
  assert.equal(await page.locator('.ws-assessment').count(),0);
  assert.equal(await page.locator('button[data-ws="opt-approve"]').count(),0);
  const overflow=()=>page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  assert.equal(await overflow(),false,'desktop overflow');
  await page.screenshot({path:process.env.NCCE_PREVIEW_ARTIFACTS+'/desktop.png',fullPage:true});
  await page.locator('[data-ws-detail="editorial-contract"] > summary').click();
  await page.getByText('Page-referenced tone anchors',{exact:true}).click();
  assert.equal(await page.locator('.ws-quality-reference blockquote').count(),3);
  await page.screenshot({path:process.env.NCCE_PREVIEW_ARTIFACTS+'/standards.png',fullPage:true});
  await page.locator('[data-ws-verdict-choice]').first().selectOption('A-only');
  await page.getByRole('button',{name:'Seal verdict and reveal comparison',exact:true}).first().click();
  await page.locator('.ws-owner-reveal').waitFor();
  assert.equal(await page.locator('.ws-assessment').count(),1);
  assert.equal(await page.locator('.ws-blind-verdict').count(),1);
  await page.screenshot({path:process.env.NCCE_PREVIEW_ARTIFACTS+'/revealed.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await overflow(),false,'mobile overflow');
  await page.screenshot({path:process.env.NCCE_PREVIEW_ARTIFACTS+'/mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS real authenticated browser: blind controls, standards, reveal, desktop/mobile bounds, no JS errors.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
''',encoding='utf-8')
            env={**os.environ,'NCCE_PREVIEW_COOKIE':make_session_token(server.SESSION_KEY),
                'NCCE_PREVIEW_URL':'http://127.0.0.1:'+str(http.server_address[1]),
                'NCCE_PREVIEW_ARTIFACTS':str(artifacts),'NCCE_PLAYWRIGHT':str(runtime/'node_modules/playwright')}
            result=subprocess.run([str(runtime/'bin/node.exe'),str(script)],env=env,capture_output=True,text=True,
                                  timeout=80,creationflags=0x08000000 if os.name=='nt' else 0)
            print(result.stdout)
            if result.returncode:
                print(result.stderr);raise AssertionError('Browser smoke failed')
            assert server.store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]==initial_requests
        finally:
            http.shutdown();http.server_close();server.store.close()


if __name__=='__main__':main()
