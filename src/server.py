from __future__ import annotations
import json, mimetypes, os, sys, threading, webbrowser, hmac
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs
from store import Store
from sync import sync_live_sheet
from access import configured_bool, effective_session_key, make_session_token, valid_session_token

ROOT=Path(__file__).resolve().parents[1]; WEB=ROOT/'web'
APP_VERSION='0.28.19'
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
from migrations import backup_before_upgrade
upgrade_backup=backup_before_upgrade(DB)
if upgrade_backup:print('Verified pre-upgrade database backup: '+str(upgrade_backup),flush=True)
store=Store(DB)
from story_engine import regenerate
import llm_writer
# Retire execution paths before preparing derived campaign state.
from writing_retirement import retire
retirement=retire(store)
from campaign_authored import register as register_authored_dossiers
register_authored_dossiers(store)
print('Writing system removed; verified backup: '+retirement['backup']+'; terminal audit labels restored: '+str(retirement.get('restored_terminal_audits',0)),flush=True)
regenerate(store,writer_enabled=False)
from writing_exchange import import_accepted_files
EXTERNAL_DELIVERIES=ROOT/'data'/'writing-exchange'/'accepted'
import_accepted_files(store,EXTERNAL_DELIVERIES)
import exchange_automation
exchange_automation.restore(store)
# Optional one-shot editorial QA correction requests. Exact imported receipts and
# source continuity are checked by the existing canonical revision backend.
from editorial_revision_seed import apply_from_environment as seed_editorial_revisions
try:
 editorial_seed_result=seed_editorial_revisions(store)
 if editorial_seed_result is not None:
  print('Editorial revision seed: '+json.dumps(editorial_seed_result,ensure_ascii=False),flush=True)
except (ValueError,TypeError,KeyError) as exc:
 print('Editorial revision seed rejected: '+str(exc)[:500],flush=True)
# Deliver only the finite, exact owner-approved revision manifest when present.
# All writes pass through the existing guarded exchange_automation.deliver path.
from editorial_approved_delivery import apply_from_environment as deliver_approved_corrections
try:
 approved_result=deliver_approved_corrections(store)
 if approved_result is not None:
  print('Editorial approved delivery: '+json.dumps(approved_result,ensure_ascii=False),flush=True)
except (ValueError,TypeError,KeyError) as exc:
 print('Editorial approved delivery rejected: '+str(exc)[:400],flush=True)
# One-shot owner-approved recovery for Emil's earlier overlength HOLD.
# Exact source/target checks and the canonical delivery path remain mandatory.
from emil_approved_biography import apply_from_environment as publish_approved_emil
try:
 emil_publication=publish_approved_emil(store)
 if emil_publication is not None:
  print('Emil approved biography delivery: '+json.dumps(emil_publication,ensure_ascii=False),flush=True)
except (ValueError,TypeError,KeyError) as exc:
 print('Emil approved biography delivery rejected: '+str(exc)[:400],flush=True)
import voice_proposals
voice_proposals.ensure(store)
try: SYNC_INTERVAL_SECONDS=max(60,int(os.environ.get('NCCE_SYNC_INTERVAL_SECONDS','900')))
except ValueError: SYNC_INTERVAL_SECONDS=900
_worker_guard=threading.Lock(); _worker_active=False
def _run_sync():
 global _worker_active
 try:
  started=datetime.now(timezone.utc).isoformat()
  with store._lock: store.set_state('sync_status','syncing'); store.set_state('sync_last_attempt',started); store.set_state('sync_last_error','')
  result=sync_live_sheet(store,writer_enabled=False)
  import_accepted_files(store,EXTERNAL_DELIVERIES)
  exchange_automation.restore(store)
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

def retired_route(path):
 return any(path==prefix or path.startswith(prefix+'/') for prefix in ('/api/workshop','/api/reviewer-bridge','/api/native-author','/api/writer-runs','/api/writer-diagnostic','/api/territory-writer-runs')) or (path.startswith('/api/fighters/') and path.endswith('/write-check'))

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
 def do_GET(self):
  parsed=urlparse(self.path); p=parsed.path
  if retired_route(p):return self.js({'error':'This writing service has been removed.','code':'writing_removed'},410)
  if p=='/healthz':return self.js({'ok':True,'version':APP_VERSION})
  if p=='/api/session':return self.js({'auth_required':AUTH_REQUIRED,'authenticated':self._authenticated()})
  if p in ('/login','/login.html'):return self._serve_login()
  if AUTH_REQUIRED and not self._authenticated():
   if p=='/':return self._serve_login()
   if p.startswith('/api/'):return self.js({'error':'authentication required'},401)
   return self.send_error(404)
  if p=='/voice-review.html':
   self.send_response(303);self.send_header('Location','/writing-process.html');self.end_headers();return
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
  if p=='/api/prose-progress':
   from prose_progress import summary
   with store.reader() as reader:return self.js(summary(reader))
  if p=='/api/portable-writing-packet.zip':
   try:
    from portable_packet import build_portable_zip
    blob,manifest=build_portable_zip()
    self.send_response(200)
    self.send_header('Content-Type','application/zip')
    self.send_header('Content-Disposition','attachment; filename="ncce-writing-packet-'+manifest['packet_version']+'.zip"')
    self.send_header('Cache-Control','no-store')
    self.send_header('X-Content-Type-Options','nosniff')
    self.send_header('Content-Length',str(len(blob)))
    self.end_headers();self.wfile.write(blob)
    return
   except (OSError,ValueError) as exc:return self.js({'error':'Portable packet unavailable: '+str(exc)},503)
  if p=='/api/portable-writing-packet/status':
   from literary_policy import load_literary_policy
   from portable_packet import EXPORTED_FILES
   info=load_literary_policy()
   return self.js({'version':info['policy_version'],'files':len(EXPORTED_FILES)+2,
     'scope':'literary policy and cited excerpts; not live campaign snapshot',
     'download':'/api/portable-writing-packet.zip','requires_owner_approval_for_learning':True})
  if p=='/api/voice-proposals':
   return self.js({'error':'Voice proposal review has been retired.'},410)
  if p=='/api/historical-backfill':
   import historical_backfill
   query=parse_qs(parsed.query)
   job_id=query.get('job_id',[None])[0]
   if not job_id:return self.js({'error':'job_id is required'},400)
   try:
    with store.reader() as reader:
     return self.js(historical_backfill.summary(reader,job_id,include_items=True))
   except ValueError as exc:return self.js({'error':str(exc)},404)
  if p=='/api/writing-exchange':
   from writing_exchange import status
   with store.reader() as reader:return self.js({'deliveries':status(reader),'automation':exchange_automation.diagnostics(reader)})
  if p.startswith('/api/gangs/'):
   with store.reader() as reader:x=reader.gang(unquote(p.split('/api/gangs/',1)[1]))
   return self.js(x if x else {'error':'not found'},200 if x else 404)
  if p.startswith('/api/fighters/') and p.endswith('/mind') and p.count('/')==4:
   try:
    with store.reader() as reader:x=reader.fighter_mind_feed(int(p.split('/')[3]))
   except (TypeError,ValueError):x=None
   return self.js(x if x is not None else {'error':'not found'},200 if x is not None else 404)
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
  if p=='/api/archive':
   from authored_archive import stories
   with store.reader() as reader:return self.js({'stories':stories(reader)})
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
  if retired_route(p):return self.js({'error':'This writing service has been removed.','code':'writing_removed'},410)
  if p.startswith('/api/writing-exchange/relay/'):
   if not exchange_automation.authenticated(self.headers.get('Authorization')):
    return self.js({'error':'Writing relay authentication required'},401)
   try:
    length=int(self.headers.get('Content-Length','0'))
    if length<0 or length>100000:return self.js({'error':'Delivery too large'},413)
    payload=json.loads(self.rfile.read(length).decode('utf-8'))
    if not isinstance(payload,dict):raise ValueError('Expected a JSON object')
    if p.startswith('/api/writing-exchange/relay/bulk/'):
     import historical_backfill
     with store._lock:
      if store.get_state('sync_status')=='syncing':
       return self.js({'error':'Campaign refresh in progress; retry later'},409)
      action=p.rsplit('/',1)[-1]
      if action=='create':
       return self.js(historical_backfill.create(
        store,payload.get('gang_ids'),gang_names=payload.get('gang_names'),
        house_types=payload.get('house_types'),owner_authorized=payload.get('owner_authorized')))
      if action=='poll':
       return self.js(historical_backfill.poll(
        store,payload.get('job_id'),payload.get('limit',25)))
      if action=='deliver':
       return self.js(historical_backfill.deliver(
        store,payload.get('job_id'),payload))
      if action=='status':
       return self.js(historical_backfill.summary(
        store,payload.get('job_id'),include_items=True))
      if action=='close':
       return self.js(historical_backfill.close(store,payload.get('job_id'),
        finalize_unresolved=payload.get('finalize_unresolved') is True))
      if action=='cancel':
       return self.js(historical_backfill.cancel(store,payload.get('job_id')))
      if action=='revise-batch':
       # A deliberate owner operation. Never writes or approves replacement prose.
       if payload.get('owner_authorized') is not True:
        raise ValueError('Explicit owner authorization required for batch corrections')
       from editorial_revision_seed import apply as apply_editorial_revision_batch
       batch={key:payload[key] for key in ('job_id','items') if key in payload}
       return self.js(apply_editorial_revision_batch(store,json.dumps(batch)))
      if action=='revise':
       return self.js(historical_backfill.request_manual_revision(
        store,payload.get('job_id'),payload.get('request_id'),
        payload.get('expected_receipt')))
     return self.js({'error':'Unknown bulk endpoint'},404)
    if p.endswith('/poll'):
     with store._lock:
      if store.get_state('sync_status')=='syncing':return self.js({'error':'Campaign refresh in progress; retry saved work later'},409)
      exchange_automation.prepare(store,client_states=payload.get('queue_state') if payload.get('protocol_version')==2 else None)
      store.set_state('exchange_relay_last_seen',exchange_automation.now())
      from writing_waterfall import summary
      from territory_history import amendments
      return self.js({'packets':exchange_automation.outbox(store),'amendments':amendments(store),'holds':exchange_automation.holds(store),'deferred':exchange_automation.deferred(store),'waterfall':summary(store,exchange_automation.candidates(store)),'guidance':exchange_automation.guidance()})
    if p.endswith('/revise'):
     with store._lock:
      from historical_backfill import is_bulk_request
      if is_bulk_request(store,payload.get('request_id')):raise ValueError('Use the bulk revision endpoint for this request')
      if store.get_state('sync_status')=='syncing':return self.js({'error':'Campaign refresh in progress; retry later'},409)
      return self.js(exchange_automation.request_revision(
       store,payload.get('request_id'),payload.get('expected_receipt')))
    if p.endswith('/deliver'):
     with store._lock:
      from historical_backfill import is_bulk_request
      if is_bulk_request(store,payload.get('request_id')):raise ValueError('Use the bulk delivery endpoint for this request')
      if store.get_state('sync_status')=='syncing':return self.js({'error':'Campaign refresh in progress; retry saved work later'},409)
      return self.js(exchange_automation.deliver(store,payload))
    return self.js({'error':'Unknown relay endpoint'},404)
   except (ValueError,KeyError,TypeError,UnicodeDecodeError) as exc:return self.js({'error':str(exc)},400)
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
  if p=='/api/voice-proposals/review':
   return self.js({'error':'Voice proposal review has been retired.'},410)
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
