from __future__ import annotations
import json, mimetypes, os, sys, threading, webbrowser, hmac
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs
import uuid
from store import Store
from sync import sync_live_sheet
from access import configured_bool, effective_session_key, make_session_token, valid_session_token

ROOT=Path(__file__).resolve().parents[1]; WEB=ROOT/'web'
APP_VERSION='0.12.1'
DB=Path(os.environ.get('NCCE_DB_PATH',str(ROOT/'data'/'chronicle.db'))).expanduser()
AUTH_REQUIRED=configured_bool(os.environ.get('NCCE_REQUIRE_AUTH'))
ACCESS_PASSWORD=os.environ.get('NCCE_ACCESS_PASSWORD','')
SESSION_SECRET=os.environ.get('NCCE_SESSION_SECRET','')
if AUTH_REQUIRED and len(ACCESS_PASSWORD)<12:
 raise RuntimeError('NCCE_ACCESS_PASSWORD must be set to at least 12 characters when NCCE_REQUIRE_AUTH is enabled')
if AUTH_REQUIRED and len(SESSION_SECRET)<32:
 raise RuntimeError('NCCE_SESSION_SECRET must be set to at least 32 characters when NCCE_REQUIRE_AUTH is enabled')
SESSION_KEY=effective_session_key(ACCESS_PASSWORD,SESSION_SECRET) if AUTH_REQUIRED else b''
COOKIE_SECURE=configured_bool(os.environ.get('NCCE_SECURE_COOKIES'))
if not DB.exists():
 from seed import main as seed_database
 seed_database(str(DB))
store=Store(DB)
from story_engine import regenerate
import llm_writer
# Keep service startup/health responsive. Configured writing begins on the first scheduled/manual refresh.
regenerate(store,writer_enabled=not bool(llm_writer.API_KEY))
AUTO_WRITE_ENABLED=configured_bool(os.environ.get('NCCE_AUTO_WRITE_ENABLED','0'))
try: SYNC_INTERVAL_SECONDS=max(60,int(os.environ.get('NCCE_SYNC_INTERVAL_SECONDS','900')))
except ValueError: SYNC_INTERVAL_SECONDS=900
_worker_guard=threading.Lock(); _worker_active=False
_writer_pipeline_guard=threading.Lock()
with store._lock,store.db:
 store.db.execute("UPDATE workshop_trials SET status='error',error='Server restarted during this trial. Inspect retained usage; no automatic retry was made.' WHERE status IN ('queued','running')")

def _run_workshop(trial_id):
 try:
  import writer_workshop
  with store._lock:writer_workshop.execute(store,trial_id)
 finally:_writer_pipeline_guard.release()
_writer_check_guard=threading.Lock(); _writer_check_active=False; _writer_check_used=store.get_state('mara_writer_check_used')=='1'; _writer_check_review_used=store.get_state('mara_writer_check_review_used')=='1'; _writer_check_final_used=store.get_state('mara_writer_check_final_used')=='1'; _writer_check_medium_used=store.get_state('mara_writer_check_medium_used')=='1'
_writer_checks={}
_territory_writer_guard=threading.Lock(); _territory_writer_active=False
if store.get_state('territory_writer_run_status') in {'queued','running'}:
 store.set_state('territory_writer_run_status','error'); store.set_state('territory_writer_run_error','The server restarted before this territory writing run finished.')

def _run_fighter_writer_check(run_id,fighter_id,call_budget=13,reasoning_effort=None,run_kind='initial_check'):
 global _writer_check_active
 _writer_checks[run_id]={'run_id':run_id,'status':'running','fighter_id':fighter_id,'call_limit':call_budget,'reasoning_effort':reasoning_effort,'run_kind':run_kind}
 try:
  with _writer_pipeline_guard:
   old_effort=llm_writer.DEFAULT_REASONING_EFFORT
   try:
    if reasoning_effort:llm_writer.DEFAULT_REASONING_EFFORT=reasoning_effort
    with store._lock:
     from story_engine import regenerate
     result=regenerate(store,force=True,fighter_ids=[fighter_id],call_budget=call_budget,writer_run_id=run_id)
   finally:llm_writer.DEFAULT_REASONING_EFFORT=old_effort
  _writer_checks[run_id]={'run_id':run_id,'status':'complete','fighter_id':fighter_id,'call_limit':call_budget,'reasoning_effort':reasoning_effort,'run_kind':run_kind,**result}
  with store._lock:
   store.set_state('mara_writer_check_status','complete'); store.set_state('mara_writer_check_summary',json.dumps(result.get('writer',{}),sort_keys=True))
 except Exception as exc:
  _writer_checks[run_id]={'run_id':run_id,'status':'error','fighter_id':fighter_id,'error':str(exc)[:240]}
  with store._lock:
   store.set_state('mara_writer_check_status','error'); store.set_state('mara_writer_check_summary',json.dumps({'error':str(exc)[:240]},sort_keys=True))
 finally:
  with _writer_check_guard: _writer_check_active=False

def _run_territory_writer(run_id):
 global _territory_writer_active
 store.set_state('territory_writer_run_status','running')
 try:
  from story_engine import regenerate_territory_writing
  with _writer_pipeline_guard:
   summary=regenerate_territory_writing(store,writer_run_id=run_id)
  store.set_state('territory_writer_run_summary',json.dumps(summary,sort_keys=True))
  store.set_state('territory_writer_run_status','complete')
 except Exception as exc:
  store.set_state('territory_writer_run_error',str(exc)[:300])
  store.set_state('territory_writer_run_summary',json.dumps(llm_writer.run_summary(),sort_keys=True))
  store.set_state('territory_writer_run_status','error')
 finally:
  with _territory_writer_guard: _territory_writer_active=False

def _territory_writer_run_payload():
 run_id=store.get_state('territory_writer_run_id')
 status=store.get_state('territory_writer_run_status','not_started')
 try:summary=json.loads(store.get_state('territory_writer_run_summary','{}'))
 except (TypeError,ValueError):summary={}
 usage={'requests':0,'succeeded':0,'failed':0,'input_tokens':0,'output_tokens':0}
 from story_engine import territory_writing_plan
 with store.reader() as reader:plan=territory_writing_plan(reader)[0]
 if run_id:
  with store.reader() as reader:
   rows=reader.db.execute('SELECT status,input_tokens,output_tokens FROM writer_requests WHERE run_id=?',(run_id,)).fetchall()
  usage.update({'requests':len(rows),'succeeded':sum(row['status']=='succeeded' for row in rows),
                'failed':sum(row['status']=='failed' for row in rows),
                'input_tokens':sum(row['input_tokens'] for row in rows),'output_tokens':sum(row['output_tokens'] for row in rows)})
 return {'run_id':run_id,'status':status,'used':store.get_state('territory_writer_run_used')=='1','plan':plan,
         'summary':summary,'request_usage':usage,'error':store.get_state('territory_writer_run_error','')}

def _run_sync():
 global _worker_active
 try:
  started=datetime.now(timezone.utc).isoformat()
  with store._lock: store.set_state('sync_status','syncing'); store.set_state('sync_last_attempt',started); store.set_state('sync_last_error','')
  with _writer_pipeline_guard:
   result=sync_live_sheet(store,writer_enabled=AUTO_WRITE_ENABLED)
  finished=datetime.now(timezone.utc).isoformat()
  with store._lock:
   store.set_state('last_sync',finished); store.set_state('sync_last_success',finished); store.set_state('sync_status','ok')
   store.set_state('sync_last_error',''); store.set_state('sync_last_snapshot_id',result['snapshot_id'])
   store.set_state('sync_last_events_created',len(result['events_created']))
   store.set_state('sync_current_counts',json.dumps(result['projection'],sort_keys=True))
   store.set_state('campaign_history_sync_result',json.dumps(result['history_import'],ensure_ascii=False,sort_keys=True))
  print(f"Krakamunda Sheet sync succeeded: snapshot {result['snapshot_id']}, {len(result['events_created'])} new events")
 except Exception as exc:
  message=str(exc)[:500]
  with store._lock: store.set_state('sync_status','error'); store.set_state('sync_last_error',message)
  print(f'Krakamunda Sheet sync failed: {message}')
 finally:
  with _worker_guard: _worker_active=False

def _schedule_sync():
 global _worker_active
 with _worker_guard:
  if _worker_active: return False
  _worker_active=True
 threading.Thread(target=_run_sync,name='ncce-sheet-sync',daemon=True).start()
 return True

def _sync_scheduler():
 while True:
  _schedule_sync()
  threading.Event().wait(SYNC_INTERVAL_SECONDS)

class H(BaseHTTPRequestHandler):
 def js(self,o,status=200):
  b=json.dumps(o,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def _authenticated(self):
  if not AUTH_REQUIRED:return True
  for item in self.headers.get('Cookie','').split(';'):
   if '=' in item:
    key,value=item.strip().split('=',1)
    if key=='ncce_session':return valid_session_token(value,SESSION_KEY)
  return False
 def _serve_login(self):
  page=(WEB/'login.html').read_bytes(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(page))); self.end_headers(); self.wfile.write(page)
 def _workshop_allowed(self,mutating=False):
  # These editing/spending routes are unavailable when application auth is disabled.
  if not AUTH_REQUIRED:self.js({'error':'Writer Workshop requires passphrase-protected access.'},403); return False
  if not self._authenticated():self.js({'error':'authentication required'},401); return False
  if mutating:
   origin=urlparse(self.headers.get('Origin',''))
   if origin.scheme not in ('http','https') or origin.netloc!=self.headers.get('Host') or self.headers.get('Sec-Fetch-Site')=='cross-site':
    self.js({'error':'Use the workshop from this application origin.'},403); return False
   if self.headers.get('Content-Type','').split(';')[0]!='application/json':
    self.js({'error':'Expected a JSON request'},415); return False
  return True
 def do_GET(self):
  parsed=urlparse(self.path); p=parsed.path
  if p=='/healthz':return self.js({'ok':True,'version':APP_VERSION})
  if p=='/api/session':return self.js({'auth_required':AUTH_REQUIRED,'authenticated':self._authenticated()})
  if p in ('/login','/login.html'):return self._serve_login()
  if AUTH_REQUIRED and not self._authenticated():
   if p=='/':return self._serve_login()
   if p.startswith('/api/'):return self.js({'error':'authentication required'},401)
   return self.send_error(404)
  if p.startswith('/api/workshop'):
   if not self._workshop_allowed():return
   import writer_workshop as workshop
   query=parse_qs(parsed.query)
   try:
    with store.reader() as reader:
     if p=='/api/workshop':result=workshop.home(reader)
     elif p=='/api/workshop/policy':result=workshop.editor(reader,query.get('scope',['shared'])[0])
     elif p=='/api/workshop/sample':
      result=workshop.sample(reader,query.get('key',[''])[0])
      result['packet_hash']=workshop.hashlib.sha256(workshop.packed(result['packet']).encode()).hexdigest()
     elif p=='/api/workshop/trial':result=workshop.trial(reader,query.get('trial_id',[''])[0])
     else:return self.send_error(404)
    return self.js(result)
   except ValueError as exc:return self.js({'error':str(exc)},400)
  if p=='/api/dashboard':
   with store.reader() as reader:return self.js(reader.dashboard())
  if p=='/api/health':
   with store.reader() as reader:
    return self.js({'ok':True,'database':str(DB),'baseline':reader.get_state('baseline'),'last_sync':reader.get_state('last_sync'),'source_mode':reader.get_state('source_mode'),'version':reader.get_state('engine_version'),'app_version':APP_VERSION,'schema_version':reader.schema_version,'sync_status':reader.get_state('sync_status','starting'),'sync_last_attempt':reader.get_state('sync_last_attempt'),'sync_last_success':reader.get_state('sync_last_success'),'sync_last_error':reader.get_state('sync_last_error'),'sync_interval_seconds':SYNC_INTERVAL_SECONDS,'sync_source':'Krakamunda Fetch-a-Munda LIVE','sync_last_snapshot_id':reader.get_state('sync_last_snapshot_id'),'campaign_history_sync_result':reader.get_state('campaign_history_sync_result'),'story_revision':reader.get_state('story_revision'),'story_generated_at':reader.get_state('story_generated_at'),'writer':llm_writer.availability()})
  if p=='/api/events':
   query=parse_qs(parsed.query); entity_id=query.get('entity_id',[None])[0]
   try:limit=int(query.get('limit',['100'])[0])
   except (TypeError,ValueError):return self.js({'error':'limit must be an integer'},400)
   with store.reader() as reader:return self.js({'events':reader.events(limit=limit,entity_id=entity_id)})
  if p=='/api/history':
   with store.reader() as reader:return self.js(reader.history_timeline())
  if p=='/api/writer-runs/mara-latest':
   run_id=store.get_state('mara_writer_check_run_id')
   if not run_id:return self.js({'error':'No Mara writer run has been recorded'},404)
   p='/api/writer-runs/'+run_id
  if p=='/api/territory-writer-runs/latest':return self.js(_territory_writer_run_payload())
  if p.startswith('/api/writer-runs/'):
   run_id=p.rsplit('/',1)[1]
   item=_writer_checks.get(run_id)
   if item is None and store.get_state('mara_writer_check_run_id')==run_id:
    try: saved_summary=json.loads(store.get_state('mara_writer_check_summary','{}'))
    except (TypeError,ValueError): saved_summary={}
    item={'run_id':run_id,'status':store.get_state('mara_writer_check_status','queued'),
          'fighter_id':store.get_state('mara_writer_check_fighter_id'),'writer':saved_summary}
   if item is None:return self.js({'error':'writer run not found'},404)
   live_writer=llm_writer.run_summary()
   if item.get('status') in {'queued','running'} and live_writer.get('run_id')==run_id:
    item={**item,'writer':live_writer}
   with store.reader() as reader:
    rows=reader.db.execute('SELECT request_id,response_id,form,subject_name,model,requested_at,finished_at,status,input_tokens,output_tokens,error_text FROM writer_requests WHERE run_id=? ORDER BY request_row_id',(run_id,)).fetchall()
   requests=[dict(row) for row in rows]
   usage={'requests':len(requests),'succeeded':sum(r['status']=='succeeded' for r in requests),'failed':sum(r['status']=='failed' for r in requests),
          'input_tokens':sum(r['input_tokens'] for r in requests),'output_tokens':sum(r['output_tokens'] for r in requests),'records':requests}
   if item.get('status') in {'queued','running'} and item.get('writer',{}).get('run_id')==run_id:
    stats=item['writer']
    usage.update({'requests':stats.get('requests_attempted',usage['requests']),
                  'succeeded':stats.get('requests_succeeded',usage['succeeded']),
                  'failed':stats.get('requests_failed',usage['failed']),
                  'input_tokens':stats.get('input_tokens',usage['input_tokens']),
                  'output_tokens':stats.get('output_tokens',usage['output_tokens'])})
   terminal=item.get('status') in {'complete','error'}
   can_retry=_writer_check_used and not _writer_check_review_used and terminal
   can_final_run=_writer_check_review_used and not _writer_check_final_used and terminal
   can_medium_run=_writer_check_final_used and not _writer_check_medium_used and terminal
   return self.js({**item,'request_usage':usage,'can_retry':can_retry,'can_final_run':can_final_run,'can_medium_run':can_medium_run})
  if p=='/api/writer-diagnostic':
   try:result=json.loads(store.get_state('writer_diagnostic_result','{}'))
   except (TypeError,ValueError):result={}
   return self.js({'used':store.get_state('writer_diagnostic_used')=='1',**result})
  if p.startswith('/api/gangs/'):
   with store.reader() as reader:x=reader.gang(unquote(p.split('/api/gangs/',1)[1]))
   return self.js(x if x else {'error':'not found'},200 if x else 404)
  if p.startswith('/api/fighters/'):
   try:
    with store.reader() as reader:x=reader.fighter(int(p.rsplit('/',1)[1]))
   except (TypeError,ValueError):x=None
   return self.js(x if x else {'error':'not found'},200 if x else 404)
  if p.startswith('/api/territories/'):
   try:
    with store.reader() as reader:x=reader.territory(int(p.rsplit('/',1)[1]))
   except (TypeError,ValueError):x=None
   return self.js(x if x else {'error':'not found'},200 if x else 404)
  if p=='/api/lore':
   with store.reader() as reader:return self.js(reader.lore())
  if p.startswith('/api/lore/'):
   try:
    with store.reader() as reader:x=reader.lore_source(int(p.rsplit('/',1)[1]))
   except (TypeError,ValueError):x=None
   return self.js(x if x else {'error':'not found'},200 if x else 404)
  rel='index.html' if p=='/' else p.lstrip('/'); f=(WEB/rel).resolve()
  if WEB.resolve() not in f.parents and f!=WEB.resolve():return self.send_error(403)
  if not f.is_file():return self.send_error(404)
  b=f.read_bytes(); self.send_response(200); self.send_header('Content-Type',mimetypes.guess_type(f.name)[0] or 'application/octet-stream'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer');
  if f.suffix.lower()=='.html':self.send_header('Cache-Control','no-store')
  self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_POST(self):
  p=urlparse(self.path).path
  if p=='/api/login':
   if not AUTH_REQUIRED:return self.js({'ok':True,'auth_required':False})
   try:
    length=int(self.headers.get('Content-Length','0'))
    if length<0 or length>4096:return self.js({'error':'invalid request'},413)
    body=json.loads(self.rfile.read(length).decode('utf-8'))
   except (ValueError,UnicodeDecodeError):return self.js({'error':'invalid request'},400)
   supplied=body.get('password','') if isinstance(body,dict) else ''
   if not isinstance(supplied,str) or not hmac.compare_digest(supplied.encode('utf-8'),ACCESS_PASSWORD.encode('utf-8')):return self.js({'error':'That passphrase is not correct.'},401)
   token=make_session_token(SESSION_KEY)
   secure=COOKIE_SECURE or self.headers.get('X-Forwarded-Proto','').split(',')[0].strip().lower()=='https'
   cookie=f'ncce_session={token}; Path=/; Max-Age=604800; HttpOnly; SameSite=Strict'+('; Secure' if secure else '')
   payload=b'{"ok":true}'; self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Set-Cookie',cookie); self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
   return
  if p=='/api/logout':
   secure=COOKIE_SECURE or self.headers.get('X-Forwarded-Proto','').split(',')[0].strip().lower()=='https'
   cookie='ncce_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict'+('; Secure' if secure else '')
   payload=b'{"ok":true}'; self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Set-Cookie',cookie); self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
   return
  if AUTH_REQUIRED and not self._authenticated():return self.js({'error':'authentication required'},401)
  if p.startswith('/api/workshop/'):
   if not self._workshop_allowed(mutating=True):return
   import writer_workshop as workshop
   try:
    length=int(self.headers.get('Content-Length','0'))
    if length<1 or length>128000:return self.js({'error':'Workshop request is too long'},413)
    body=json.loads(self.rfile.read(length).decode('utf-8'))
    if not isinstance(body,dict):raise ValueError('Expected an object')
    if p=='/api/workshop/generate':
     with store.reader() as reader:
      old=reader.db.execute('SELECT trial_id FROM workshop_trials WHERE request_key=?',(body.get('request_key'),)).fetchone()
      if old:return self.js(workshop.trial(reader,old[0]))
     if not _writer_pipeline_guard.acquire(blocking=False):return self.js({'error':'The writer is busy. No workshop call was made.'},409)
     try:
      item,fresh=workshop.queue(store,body)
      if fresh:threading.Thread(target=_run_workshop,args=(item['trial_id'],),name='ncce-workshop-writer',daemon=True).start()
      else:_writer_pipeline_guard.release()
     except Exception:
      _writer_pipeline_guard.release(); raise
     return self.js(item,202 if fresh else 200)
    with store._lock:
     if p=='/api/workshop/save-policy':result=workshop.save_revision(store,body)
     elif p=='/api/workshop/activate':result=workshop.activate(store,body)
     elif p=='/api/workshop/preview':result=workshop.preview(store,body)
     elif p=='/api/workshop/import':result=workshop.import_sample(store,body)
     elif p=='/api/workshop/edit':result=workshop.save_edit(store,body)
     else:return self.send_error(404)
    return self.js(result)
   except (ValueError,TypeError,UnicodeDecodeError) as exc:return self.js({'error':str(exc)},400)
  if p=='/api/writer-diagnostic':
   origin=self.headers.get('Origin')
   if origin and urlparse(origin).netloc!=self.headers.get('Host'):return self.js({'error':'Cross-origin edits are not allowed'},403)
   if not llm_writer.API_KEY:return self.js({'error':'Writing provider is not configured; no request was made.'},503)
   with _writer_check_guard:
    if store.get_state('writer_diagnostic_used')=='1':return self.js({'error':'The one-call writer diagnostic has already been used.'},409)
    if not _writer_pipeline_guard.acquire(blocking=False):return self.js({'error':'The writer is busy. No diagnostic call was made.'},409)
    store.set_state('writer_diagnostic_used','1')
   run_id='writer-diagnostic-'+uuid.uuid4().hex
   packet={'subject':'Mara Kel','event_title':'Lasting injury: Critical Injury',
           'mechanical_evidence':['Effects changed from none recorded to Critical Injury','Status changed from Active to Recovery'],
           'identity':{'occupation_or_craft':'Maintenance fitter','voice_cues':['practical','composed'],
                       'source':'player-authored C-NINE dossier and supported current profile'},
           'event_boundary':'Write only about this recorded injury and recovery status. Do not merge other events or repeat the authored biography.',
           'knowledge_boundary':'No unrecorded battle actions, causes, or private thoughts are known.'}
   old_enabled=llm_writer.WRITER_ENABLED
   llm_writer.reset_budget(1,run_id); llm_writer.set_enabled(True)
   result={'used':True,'status':'failed','model':llm_writer.MODEL}
   try:
    paragraphs=llm_writer._call('fighter_memory',packet,output_token_limit=650,reasoning_effort='low')
    result.update({'status':'succeeded','text':'\n\n'.join(''.join(run.get('text','') for run in p.get('runs',[])) for p in paragraphs)})
   except Exception as exc:
    result['error']=str(exc)[:240]
   finally:
    result['response']=dict(llm_writer._last_response)
    llm_writer.set_enabled(old_enabled)
    _writer_pipeline_guard.release()
   store.set_state('writer_diagnostic_result',json.dumps(result,ensure_ascii=False,sort_keys=True))
   return self.js(result)
  if p.startswith('/api/fighters/') and p.endswith('/write-check'):
   origin=self.headers.get('Origin')
   if origin and urlparse(origin).netloc!=self.headers.get('Host'):return self.js({'error':'Cross-origin edits are not allowed'},403)
   try:fighter_id=int(p.split('/')[3])
   except (TypeError,ValueError):return self.js({'error':'invalid fighter id'},400)
   global _writer_check_active,_writer_check_used,_writer_check_review_used,_writer_check_final_used,_writer_check_medium_used
   with _writer_check_guard:
    if _writer_check_active:return self.js({'error':'A Mara writer check is already running.'},409)
    if not llm_writer.API_KEY:return self.js({'error':'Writing provider is not configured; no request was made.'},503)
    is_review=_writer_check_used and not _writer_check_review_used
    is_final_run=_writer_check_used and _writer_check_review_used and not _writer_check_final_used
    is_medium_run=_writer_check_final_used and not _writer_check_medium_used
    prior_status=store.get_state('mara_writer_check_status','')
    if is_review and prior_status not in {'complete','error'}:
     return self.js({'error':'The previous Mara writer run is not finished.'},409)
    if is_final_run and (_writer_check_final_used or prior_status not in {'complete','error'}):
     return self.js({'error':'The one authorized Mara regeneration has already been used or the previous run is not finished.'},409)
    if is_medium_run and (_writer_check_medium_used or prior_status not in {'complete','error'}):
     return self.js({'error':'The one authorized medium-effort Mara sample has already been used or the previous run is not finished.'},409)
    with store._lock:
     fighter=store.db.execute('SELECT id,name,gang_name,backstory_source FROM fighters WHERE id=?',(fighter_id,)).fetchone()
    if not fighter or fighter['name']!='Mara Kel' or 'C-NINE' not in str(fighter['gang_name'] or '').upper() or 'c-nine story' not in str(fighter['backstory_source'] or '').lower():
     return self.js({'error':'This bounded check is currently restricted to Mara Kel’s authored C-NINE record.'},403)
    run_id=uuid.uuid4().hex; _writer_check_active=True; _writer_check_used=True
    if is_review:_writer_check_review_used=True
    if is_final_run:_writer_check_final_used=True
    if is_medium_run:_writer_check_medium_used=True
    call_limit=5 if is_medium_run else 13
    reasoning_effort='medium' if is_medium_run else None
    with store._lock:
     store.set_state('mara_writer_check_used','1'); store.set_state('mara_writer_check_run_id',run_id)
     store.set_state('mara_writer_check_fighter_id',str(fighter_id)); store.set_state('mara_writer_check_status','queued')
     store.set_state('mara_writer_check_summary','{}')
    if is_review:store.set_state('mara_writer_check_review_used','1')
    if is_final_run:store.set_state('mara_writer_check_final_used','1')
    if is_medium_run:store.set_state('mara_writer_check_medium_used','1')
    run_kind='medium_effort_sample' if is_medium_run else 'authorized_mara_regeneration' if is_final_run else 'revised_review' if is_review else 'initial_check'
    _writers={'run_id':run_id,'status':'queued','fighter_id':fighter_id,'fighter_name':'Mara Kel','call_limit':call_limit,'reasoning_effort':reasoning_effort,'run_kind':run_kind}
    _writer_checks[run_id]=_writers
    threading.Thread(target=_run_fighter_writer_check,args=(run_id,fighter_id,call_limit,reasoning_effort,run_kind),name='ncce-mara-writer-check',daemon=True).start()
   return self.js({'run_id':run_id,'status':'queued','fighter_name':'Mara Kel','call_limit':call_limit,'reasoning_effort':reasoning_effort,'run_kind':run_kind},202)
  if p.startswith('/api/fighters/') and p.endswith('/identity'):
   origin=self.headers.get('Origin')
   if origin and urlparse(origin).netloc!=self.headers.get('Host'):return self.js({'error':'Cross-origin edits are not allowed'},403)
   try:
    length=int(self.headers.get('Content-Length','0'))
    if length<0 or length>16384:return self.js({'error':'Identity context is too long'},413)
    body=json.loads(self.rfile.read(length).decode('utf-8'))
    if not isinstance(body,dict):raise ValueError('Expected an identity object')
    with store._lock: result=store.set_writer_identity(int(p.split('/')[3]),body.get('identity'))
    return self.js(result)
   except (ValueError,TypeError,UnicodeDecodeError) as exc:return self.js({'error':str(exc)},400)
  if p=='/api/territory-writer-runs':
   origin=self.headers.get('Origin')
   if origin and urlparse(origin).netloc!=self.headers.get('Host'):return self.js({'error':'Cross-origin edits are not allowed'},403)
   global _territory_writer_active
   with _territory_writer_guard:
    if _territory_writer_active:return self.js({'error':'A territory writer run is already active.'},409)
    if not llm_writer.API_KEY:return self.js({'error':'Writing provider is not configured; no request was made.'},503)
    if store.get_state('territory_writer_run_used')=='1':return self.js({'error':'The one-time territory writing pass has already been used.'},409)
    run_id=uuid.uuid4().hex; _territory_writer_active=True
    store.set_state('territory_writer_run_used','1'); store.set_state('territory_writer_run_id',run_id)
    store.set_state('territory_writer_run_status','queued'); store.set_state('territory_writer_run_summary','{}'); store.set_state('territory_writer_run_error','')
    threading.Thread(target=_run_territory_writer,args=(run_id,),name='ncce-territory-writer-run',daemon=True).start()
   return self.js({'run_id':run_id,'status':'queued'},202)
  if p!='/api/sync': return self.send_error(404)
  queued=_schedule_sync()
  return self.js({'queued':queued,'sync_status':'syncing' if queued else 'already_running'},202)
 def log_message(self,*a):pass

def main(host=None,port=None):
 if host is None:host=os.environ.get('NCCE_HOST','0.0.0.0' if os.environ.get('PORT') else '127.0.0.1')
 if port is None:port=int(os.environ.get('PORT','8765'))
 server=ThreadingHTTPServer((host,port),H)
 url=f'http://{host}:{port}'
 print(f'NCCE Campaign Chronicle running at {url}; Python {sys.executable}; refreshing Krakamunda every {SYNC_INTERVAL_SECONDS//60} minutes',flush=True)
 if os.environ.get('NCCE_OPEN_BROWSER')=='1':
  threading.Timer(0.25,webbrowser.open_new_tab,args=(url,)).start()
 threading.Thread(target=_sync_scheduler,name='ncce-sheet-scheduler',daemon=True).start()
 server.serve_forever()

if __name__=='__main__':main()
