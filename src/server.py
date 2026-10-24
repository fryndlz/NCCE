from __future__ import annotations
import json, mimetypes, os, threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs
from store import Store
from sync import sync_live_sheet

ROOT=Path(__file__).resolve().parents[1]; WEB=ROOT/'web'; DB=ROOT/'data'/'chronicle.db'
store=Store(DB)
store.set_state('engine_version','NCCE v0.4 Live Sync Preview')
try: SYNC_INTERVAL_SECONDS=max(60,int(os.environ.get('NCCE_SYNC_INTERVAL_SECONDS','900')))
except ValueError: SYNC_INTERVAL_SECONDS=900
_worker_guard=threading.Lock(); _worker_active=False

def _run_sync():
 global _worker_active
 try:
  started=datetime.now(timezone.utc).isoformat()
  with store._lock: store.set_state('sync_status','syncing'); store.set_state('sync_last_attempt',started); store.set_state('sync_last_error','')
  result=sync_live_sheet(store)
  finished=datetime.now(timezone.utc).isoformat()
  with store._lock:
   store.set_state('last_sync',finished); store.set_state('sync_last_success',finished); store.set_state('sync_status','ok')
   store.set_state('sync_last_error',''); store.set_state('sync_last_snapshot_id',result['snapshot_id'])
   store.set_state('sync_last_events_created',len(result['events_created']))
   store.set_state('sync_current_counts',json.dumps(result['projection'],sort_keys=True))
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
  b=json.dumps(o,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_GET(self):
  parsed=urlparse(self.path); p=parsed.path
  if p=='/api/dashboard':
   with store._lock: return self.js(store.dashboard())
  if p=='/api/health':
   with store._lock:
    return self.js({'ok':True,'database':str(DB),'baseline':store.get_state('baseline'),'last_sync':store.get_state('last_sync'),'source_mode':store.get_state('source_mode'),'version':store.get_state('engine_version'),'schema_version':store.schema_version,'sync_status':store.get_state('sync_status','starting'),'sync_last_attempt':store.get_state('sync_last_attempt'),'sync_last_success':store.get_state('sync_last_success'),'sync_last_error':store.get_state('sync_last_error'),'sync_interval_seconds':SYNC_INTERVAL_SECONDS,'sync_source':'Krakamunda Fetch-a-Munda LIVE'})
  if p=='/api/events':
   query=parse_qs(parsed.query); entity_id=query.get('entity_id',[None])[0]
   try:limit=int(query.get('limit',['100'])[0])
   except (TypeError,ValueError):return self.js({'error':'limit must be an integer'},400)
   with store._lock: return self.js({'events':store.events(limit=limit,entity_id=entity_id)})
  if p.startswith('/api/gangs/'):
   with store._lock: x=store.gang(unquote(p.split('/api/gangs/',1)[1]))
   return self.js(x if x else {'error':'not found'},200 if x else 404)
  if p.startswith('/api/fighters/'):
   try:
    with store._lock: x=store.fighter(int(p.rsplit('/',1)[1]))
   except (TypeError,ValueError):x=None
   return self.js(x if x else {'error':'not found'},200 if x else 404)
  if p.startswith('/api/territories/'):
   try:
    with store._lock: x=store.territory(int(p.rsplit('/',1)[1]))
   except (TypeError,ValueError):x=None
   return self.js(x if x else {'error':'not found'},200 if x else 404)
  if p=='/api/lore':
   with store._lock: return self.js(store.lore())
  if p.startswith('/api/lore/'):
   try:
    with store._lock: x=store.lore_source(int(p.rsplit('/',1)[1]))
   except (TypeError,ValueError):x=None
   return self.js(x if x else {'error':'not found'},200 if x else 404)
  rel='index.html' if p=='/' else p.lstrip('/'); f=(WEB/rel).resolve()
  if WEB.resolve() not in f.parents and f!=WEB.resolve():return self.send_error(403)
  if not f.is_file():return self.send_error(404)
  b=f.read_bytes(); self.send_response(200); self.send_header('Content-Type',mimetypes.guess_type(f.name)[0] or 'application/octet-stream'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_POST(self):
  if urlparse(self.path).path!='/api/sync': return self.send_error(404)
  queued=_schedule_sync()
  return self.js({'queued':queued,'sync_status':'syncing' if queued else 'already_running'},202)
 def log_message(self,*a):pass

def main(host='127.0.0.1',port=8765):
 print(f'NCCE Campaign Chronicle running at http://{host}:{port}; refreshing Krakamunda every {SYNC_INTERVAL_SECONDS//60} minutes')
 threading.Thread(target=_sync_scheduler,name='ncce-sheet-scheduler',daemon=True).start()
 ThreadingHTTPServer((host,port),H).serve_forever()

if __name__=='__main__':main()
