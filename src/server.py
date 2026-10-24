from __future__ import annotations
import json,mimetypes
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse,unquote,parse_qs
from store import Store
ROOT=Path(__file__).resolve().parents[1]; WEB=ROOT/'web'; DB=ROOT/'data'/'chronicle.db'; store=Store(DB)
class H(BaseHTTPRequestHandler):
 def js(self,o,status=200):
  b=json.dumps(o,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_GET(self):
  parsed=urlparse(self.path); p=parsed.path
  if p=='/api/dashboard':return self.js(store.dashboard())
  if p=='/api/health':return self.js({'ok':True,'database':str(DB),'baseline':store.get_state('baseline'),'last_sync':store.get_state('last_sync'),'source_mode':store.get_state('source_mode'),'version':store.get_state('engine_version'),'schema_version':store.schema_version})
  if p=='/api/events':
   query=parse_qs(parsed.query); entity_id=query.get('entity_id',[None])[0]
   try:limit=int(query.get('limit',['100'])[0])
   except (TypeError,ValueError):return self.js({'error':'limit must be an integer'},400)
   return self.js({'events':store.events(limit=limit,entity_id=entity_id)})
  if p.startswith('/api/gangs/'): 
   x=store.gang(unquote(p.split('/api/gangs/',1)[1])); return self.js(x if x else {'error':'not found'},200 if x else 404)
  if p.startswith('/api/fighters/'):
   try:x=store.fighter(int(p.rsplit('/',1)[1]))
   except:x=None
   return self.js(x if x else {'error':'not found'},200 if x else 404)
  if p.startswith('/api/territories/'):
   try:x=store.territory(int(p.rsplit('/',1)[1]))
   except:x=None
   return self.js(x if x else {'error':'not found'},200 if x else 404)
  if p=='/api/lore':return self.js(store.lore())
  if p.startswith('/api/lore/'):
   try:x=store.lore_source(int(p.rsplit('/',1)[1]))
   except:x=None
   return self.js(x if x else {'error':'not found'},200 if x else 404)
  rel='index.html' if p=='/' else p.lstrip('/'); f=(WEB/rel).resolve()
  if WEB.resolve() not in f.parents and f!=WEB.resolve():return self.send_error(403)
  if not f.is_file():return self.send_error(404)
  b=f.read_bytes(); self.send_response(200); self.send_header('Content-Type',mimetypes.guess_type(f.name)[0] or 'application/octet-stream'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def log_message(self,*a):pass
def main(host='127.0.0.1',port=8765): print(f'NCCE Campaign Chronicle running at http://{host}:{port}'); ThreadingHTTPServer((host,port),H).serve_forever()
if __name__=='__main__':main()
