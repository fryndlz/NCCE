from __future__ import annotations
import json, sqlite3
from pathlib import Path
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
  self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.db=sqlite3.connect(self.path,check_same_thread=False); self.db.row_factory=sqlite3.Row; self.db.executescript(SCHEMA); self.db.commit()
 def close(self): self.db.close()
 def set_state(self,k,v): self.db.execute('INSERT INTO system_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v))); self.db.commit()
 def get_state(self,k,d=None):
  r=self.db.execute('SELECT value FROM system_state WHERE key=?',(k,)).fetchone(); return r['value'] if r else d
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
  f['events']=q('SELECT * FROM fighter_events WHERE fighter_id=? ORDER BY id DESC',(fid,)); f['memories']=q('SELECT * FROM memories WHERE fighter_id=? ORDER BY importance DESC,id DESC',(fid,)); f['moodlets']=q('SELECT * FROM moodlets WHERE fighter_id=? ORDER BY intensity DESC',(fid,)); return f
 def territory(self,tid):
  r=self.db.execute('SELECT * FROM territories WHERE id=?',(tid,)).fetchone(); return dict(r) if r else None
 def lore(self): return [dict(r) for r in self.db.execute('SELECT id,title,source_type,source_url,length(content) AS chars FROM lore_sources')]
 def lore_source(self,lid):
  r=self.db.execute('SELECT * FROM lore_sources WHERE id=?',(lid,)).fetchone(); return dict(r) if r else None
