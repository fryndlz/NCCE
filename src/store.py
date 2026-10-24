from __future__ import annotations
import hashlib, json, re, sqlite3, threading, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from migrations import PROVENANCE_CLASSES, migrate
SCHEMA='''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,captured_at TEXT NOT NULL,source_hash TEXT,payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS gangs(gang_id TEXT PRIMARY KEY,name TEXT NOT NULL,gang_type TEXT,player TEXT,rating INTEGER,wealth INTEGER,credits INTEGER,reputation INTEGER,territories INTEGER,alignment TEXT,colour TEXT,updated_at TEXT,backstory TEXT,backstory_source TEXT);
CREATE TABLE IF NOT EXISTS territories(id INTEGER PRIMARY KEY AUTOINCREMENT,gang_id TEXT,gang_name TEXT,territory TEXT NOT NULL,card TEXT,is_default INTEGER DEFAULT 0,ruined INTEGER DEFAULT 0,backstory TEXT);
CREATE TABLE IF NOT EXISTS battles(id INTEGER PRIMARY KEY AUTOINCREMENT,source_row INTEGER UNIQUE,date TEXT,scenario TEXT,attacker TEXT,defender TEXT,winner TEXT,territory TEXT,territory_claimer TEXT,notes TEXT,chronicle TEXT);
CREATE TABLE IF NOT EXISTS fighters(id INTEGER PRIMARY KEY AUTOINCREMENT,gang_id TEXT,gang_name TEXT,name TEXT,type TEXT,class TEXT,cost INTEGER,xp INTEGER,kills INTEGER,advancements TEXT,effects TEXT,status TEXT,notes TEXT,backstory TEXT,backstory_source TEXT);
CREATE TABLE IF NOT EXISTS fighter_events(id INTEGER PRIMARY KEY AUTOINCREMENT,fighter_id INTEGER,event_type TEXT,title TEXT,detail TEXT,event_date TEXT,source TEXT,confidence REAL DEFAULT 1.0);
CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY AUTOINCREMENT,fighter_id INTEGER,memory_type TEXT,content TEXT,importance REAL,source_event_id INTEGER,source TEXT,confidence REAL DEFAULT 1.0);
CREATE TABLE IF NOT EXISTS moodlets(id INTEGER PRIMARY KEY AUTOINCREMENT,fighter_id INTEGER,name TEXT,valence REAL,intensity INTEGER,thought TEXT,source TEXT);
CREATE TABLE IF NOT EXISTS narrative_threads(id INTEGER PRIMARY KEY AUTOINCREMENT,scope_type TEXT NOT NULL,scope_key TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',summary TEXT,evidence_json TEXT NOT NULL DEFAULT '[]',updated_at TEXT);
CREATE TABLE IF NOT EXISTS regions(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,backstory TEXT);
CREATE TABLE IF NOT EXISTS downtime_reports(id INTEGER PRIMARY KEY AUTOINCREMENT,gang_id TEXT,gang_name TEXT,period_label TEXT,report TEXT,generated_at TEXT);
CREATE TABLE IF NOT EXISTS lore_sources(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,source_type TEXT,content TEXT,source_url TEXT);
CREATE TABLE IF NOT EXISTS system_state(key TEXT PRIMARY KEY,value TEXT);
'''
class Store:
 def __init__(self,path):
  self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._lock=threading.RLock(); self.db=sqlite3.connect(self.path,check_same_thread=False); self.db.row_factory=sqlite3.Row
  try:
   self.db.executescript(SCHEMA); self.schema_version=migrate(self.db); self.db.commit()
  except Exception:
   self.db.close(); raise
 def close(self):
  with self._lock: self.db.close()
 def set_state(self,k,v):
  with self._lock: self.db.execute('INSERT INTO system_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v))); self.db.commit()
 def get_state(self,k,d=None):
  r=self.db.execute('SELECT value FROM system_state WHERE key=?',(k,)).fetchone(); return r['value'] if r else d
 def record_source(self,source_id,source_type,authority_class,title,source_uri=None,source_locator=None,retrieved_at=None,content_hash=None,metadata=None):
  if authority_class not in PROVENANCE_CLASSES: raise ValueError(f'Unknown provenance class: {authority_class}')
  if not source_id or not source_type or not title: raise ValueError('source_id, source_type, and title are required')
  with self._lock, self.db:
   self.db.execute('''INSERT OR IGNORE INTO provenance_sources(source_id,source_type,authority_class,title,source_uri,source_locator,retrieved_at,content_hash,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',(source_id,source_type,authority_class,title,source_uri,source_locator,retrieved_at,content_hash,json.dumps(metadata or {},ensure_ascii=False,sort_keys=True),datetime.now(timezone.utc).isoformat()))
   row=self.db.execute('SELECT source_type,authority_class,title,source_uri,source_locator,content_hash FROM provenance_sources WHERE source_id=?',(source_id,)).fetchone()
   if (row['source_type'],row['authority_class'],row['title'],row['source_uri'],row['source_locator'],row['content_hash'])!=(source_type,authority_class,title,source_uri,source_locator,content_hash): raise ValueError(f'Provenance source identity collision: {source_id}')
  return source_id
 def register_entity(self,entity_type,entity_key,display_name,provenance_class,source_id=None):
  if provenance_class not in PROVENANCE_CLASSES: raise ValueError(f'Unknown provenance class: {provenance_class}')
  if entity_type not in {'gang','fighter','territory','region','campaign'}: raise ValueError(f'Unknown entity type: {entity_type}')
  if not entity_key or not display_name or not source_id: raise ValueError('entity_key, display_name, and source_id are required')
  entity_id=hashlib.sha256(f'{entity_type}:{entity_key}'.encode('utf-8')).hexdigest()[:32]
  with self._lock, self.db:
   self.db.execute('''INSERT OR IGNORE INTO entities(entity_id,entity_type,entity_key,display_name,provenance_class,source_id,created_at) VALUES(?,?,?,?,?,?,?)''',(entity_id,entity_type,entity_key,display_name,provenance_class,source_id,datetime.now(timezone.utc).isoformat()))
   row=self.db.execute('SELECT entity_id,display_name,provenance_class,source_id FROM entities WHERE entity_type=? AND entity_key=?',(entity_type,entity_key)).fetchone()
   if (row['provenance_class'],row['source_id'])!=(provenance_class,source_id): raise ValueError(f'Entity identity collision: {entity_type}:{entity_key}')
   entity_id=row['entity_id']
  return entity_id
 def save_snapshot(self,payload):
  if not isinstance(payload,dict): raise ValueError('Snapshot payload must be an object')
  source_id=payload.get('source_id')
  provenance_class=payload.get('provenance_class','mechanical_fact')
  if not source_id: raise ValueError('Snapshot source_id is required')
  if provenance_class not in PROVENANCE_CLASSES: raise ValueError(f'Unknown provenance class: {provenance_class}')
  captured_at=payload.get('captured_at') or datetime.now(timezone.utc).isoformat()
  body=dict(payload); body['captured_at']=captured_at
  hashed={key:value for key,value in body.items() if key!='captured_at'}
  canonical=json.dumps({'payload':hashed,'source_id':source_id,'provenance_class':provenance_class},ensure_ascii=False,sort_keys=True,separators=(',',':'))
  payload_json=json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':'))
  digest=hashlib.sha256(canonical.encode('utf-8')).hexdigest()
  with self._lock, self.db:
   row=self.db.execute('SELECT id FROM snapshots WHERE payload_hash=?',(digest,)).fetchone()
   if row: return row['id'],False
   cur=self.db.execute('INSERT INTO snapshots(captured_at,source_hash,payload_json,payload_hash,source_id,provenance_class) VALUES(?,?,?,?,?,?)',(captured_at,digest,payload_json,digest,source_id,provenance_class))
   return cur.lastrowid,True
 def latest_snapshot(self):
  row=self.db.execute('SELECT * FROM snapshots ORDER BY id DESC LIMIT 1').fetchone()
  if not row: return None
  result=dict(row); result['payload']=json.loads(result.pop('payload_json')); return result
 def snapshot(self,snapshot_id):
  row=self.db.execute('SELECT * FROM snapshots WHERE id=?',(snapshot_id,)).fetchone()
  if not row: return None
  result=dict(row); result['payload']=json.loads(result.pop('payload_json')); return result
 def snapshot_before(self,snapshot_id):
  row=self.db.execute('SELECT * FROM snapshots WHERE id<? ORDER BY id DESC LIMIT 1',(snapshot_id,)).fetchone()
  if not row: return None
  result=dict(row); result['payload']=json.loads(result.pop('payload_json')); return result
 def event_by_key(self,event_key):
  row=self.db.execute('SELECT * FROM campaign_events WHERE event_key=?',(event_key,)).fetchone()
  return dict(row) if row else None
 def latest_event_by_source_locator(self,source_locator):
  row=self.db.execute('SELECT event_id FROM campaign_events WHERE source_locator=? ORDER BY observed_at DESC,created_at DESC LIMIT 1',(source_locator,)).fetchone()
  return row['event_id'] if row else None
 def record_event(self,event_key,event_type,payload,provenance_class,source_id=None,source_locator=None,occurred_at=None,observed_at=None,confidence=1.0,from_snapshot_id=None,to_snapshot_id=None,subjects=None,supersedes_event_id=None,correction_reason=None):
  if provenance_class not in PROVENANCE_CLASSES: raise ValueError(f'Unknown provenance class: {provenance_class}')
  if not event_key or not event_type: raise ValueError('event_key and event_type are required')
  if not source_id: raise ValueError('Every campaign event must cite a provenance source')
  if not isinstance(payload,dict): raise ValueError('Event payload must be an object')
  if not 0.0<=float(confidence)<=1.0: raise ValueError('confidence must be between 0 and 1')
  event_id=hashlib.sha256(f'campaign-event:{event_key}'.encode('utf-8')).hexdigest()[:32]
  payload_json=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))
  observed_at=observed_at or datetime.now(timezone.utc).isoformat()
  with self._lock, self.db:
   prior=self.db.execute('SELECT event_id,event_type,provenance_class,payload_json,source_id,source_locator,occurred_at,confidence,from_snapshot_id,to_snapshot_id,supersedes_event_id,correction_reason FROM campaign_events WHERE event_key=?',(event_key,)).fetchone()
   if prior:
    if (prior['event_type'],prior['provenance_class'],prior['payload_json'],prior['source_id'],prior['source_locator'],prior['occurred_at'],prior['confidence'],prior['from_snapshot_id'],prior['to_snapshot_id'],prior['supersedes_event_id'],prior['correction_reason'])!=(event_type,provenance_class,payload_json,source_id,source_locator,occurred_at,float(confidence),from_snapshot_id,to_snapshot_id,supersedes_event_id,correction_reason):
     raise ValueError(f'Immutable event key reused with different data: {event_key}')
    event_id=prior['event_id']; created=False
   else:
    self.db.execute('''INSERT INTO campaign_events(event_id,event_key,event_type,occurred_at,observed_at,created_at,provenance_class,source_id,source_locator,from_snapshot_id,to_snapshot_id,payload_json,confidence,supersedes_event_id,correction_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(event_id,event_key,event_type,occurred_at,observed_at,datetime.now(timezone.utc).isoformat(),provenance_class,source_id,source_locator,from_snapshot_id,to_snapshot_id,payload_json,float(confidence),supersedes_event_id,correction_reason))
    created=not bool(prior)
   for subject in subjects or []:
    entity_id=subject['entity_id']; role=subject['role']
    if not self.db.execute('SELECT 1 FROM entities WHERE entity_id=?',(entity_id,)).fetchone(): raise ValueError(f'Unknown event subject entity: {entity_id}')
    self.db.execute('INSERT OR IGNORE INTO event_subjects(event_id,entity_id,role) VALUES(?,?,?)',(event_id,entity_id,role))
  return event_id,created
 def link_narrative_evidence(self,artifact_type,artifact_key,evidence_role,event_id=None,source_id=None):
  if not event_id and not source_id: raise ValueError('Narrative evidence requires an event or source pointer')
  with self._lock, self.db:
   self.db.execute('''INSERT INTO narrative_evidence(artifact_type,artifact_key,event_id,source_id,evidence_role,created_at) SELECT ?,?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM narrative_evidence WHERE artifact_type=? AND artifact_key=? AND ifnull(event_id,'')=ifnull(?,'') AND ifnull(source_id,'')=ifnull(?,'') AND evidence_role=?)''',(artifact_type,artifact_key,event_id,source_id,evidence_role,datetime.now(timezone.utc).isoformat(),artifact_type,artifact_key,event_id,source_id,evidence_role))
 def events(self,limit=100,entity_id=None):
  limit=max(1,min(int(limit),500))
  if entity_id:
   rows=self.db.execute('''SELECT DISTINCT ce.* FROM campaign_events ce JOIN event_subjects es USING(event_id) WHERE es.entity_id=? ORDER BY coalesce(ce.occurred_at,ce.observed_at) DESC,ce.created_at DESC LIMIT ?''',(entity_id,limit)).fetchall()
  else:
   rows=self.db.execute('''SELECT * FROM campaign_events ORDER BY coalesce(occurred_at,observed_at) DESC,created_at DESC LIMIT ?''',(limit,)).fetchall()
  out=[]
  for row in rows:
   item=dict(row); item['payload']=json.loads(item.pop('payload_json'))
   item['subjects']=[dict(subject) for subject in self.db.execute('''SELECT e.entity_id,e.entity_type,e.entity_key,e.display_name,es.role FROM event_subjects es JOIN entities e USING(entity_id) WHERE es.event_id=? ORDER BY es.role,e.display_name''',(item['event_id'],))]
   out.append(item)
  return out
 def dashboard(self):
  q=lambda sql,args=():[dict(r) for r in self.db.execute(sql,args)]
  return {'gangs':q('SELECT * FROM gangs ORDER BY reputation DESC,rating DESC'),'battles':q('SELECT * FROM battles ORDER BY date DESC,source_row DESC'),'territories':q('SELECT * FROM territories ORDER BY gang_name,territory'),'regions':q('SELECT * FROM regions'),'downtime':q('SELECT * FROM downtime_reports ORDER BY id DESC'),'state':{r['key']:r['value'] for r in self.db.execute('SELECT * FROM system_state')}}
 def gang(self,gid):
  r=self.db.execute('SELECT * FROM gangs WHERE gang_id=?',(gid,)).fetchone()
  if not r:return None
  g=dict(r); name=g['name']; q=lambda sql,args=():[dict(x) for x in self.db.execute(sql,args)]
  g['territory_list']=q('SELECT * FROM territories WHERE gang_id=? ORDER BY territory',(gid,)); g['fighters']=q('SELECT * FROM fighters WHERE gang_id=? ORDER BY status,name',(gid,)); g['battles']=q('SELECT * FROM battles WHERE attacker=? OR defender=? OR winner=? OR territory_claimer=? ORDER BY date DESC',(name,name,name,name)); g['downtime']=q('SELECT * FROM downtime_reports WHERE gang_id=? ORDER BY id DESC',(gid,)); return g
 def fighter(self,fid):
  r=self.db.execute('SELECT * FROM fighters WHERE id=?',(fid,)).fetchone()
  if not r:return None
  f=dict(r); q=lambda sql,args=():[dict(x) for x in self.db.execute(sql,args)]
  f['events']=q('SELECT * FROM fighter_events WHERE fighter_id=? ORDER BY id DESC',(fid,)); f['memories']=q('SELECT * FROM memories WHERE fighter_id=? ORDER BY importance DESC,id DESC',(fid,)); f['moodlets']=q('SELECT * FROM moodlets WHERE fighter_id=? ORDER BY intensity DESC',(fid,))
  fighter_name=unicodedata.normalize('NFKC',str(f['name'] or '')).strip().casefold(); fighter_name=re.sub(r'\s+',' ',fighter_name)
  entity_key=f"{f['gang_id']}/{fighter_name}"
  entity=self.db.execute('SELECT entity_id FROM entities WHERE entity_type=\'fighter\' AND entity_key=?',(entity_key,)).fetchone()
  f['campaign_events']=self.events(limit=500,entity_id=entity['entity_id']) if entity else []
  return f
 def territory(self,tid):
  r=self.db.execute('SELECT * FROM territories WHERE id=?',(tid,)).fetchone(); return dict(r) if r else None
 def lore(self): return [dict(r) for r in self.db.execute('SELECT id,title,source_type,source_url,length(content) AS chars FROM lore_sources')]
 def lore_source(self,lid):
  r=self.db.execute('SELECT * FROM lore_sources WHERE id=?',(lid,)).fetchone(); return dict(r) if r else None
