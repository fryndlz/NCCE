from __future__ import annotations
from contextlib import contextmanager
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
 @contextmanager
 def reader(self):
  """Open a read-only WAL snapshot that stays available during long writer calls."""
  connection=sqlite3.connect(self.path,check_same_thread=False,timeout=10)
  connection.row_factory=sqlite3.Row
  connection.execute('PRAGMA query_only=ON')
  view=object.__new__(Store); view.path=self.path; view.db=connection; view._lock=threading.RLock(); view.schema_version=self.schema_version
  try: yield view
  finally: connection.close()
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
   if row['provenance_class']!=provenance_class: raise ValueError(f'Entity provenance collision: {entity_type}:{entity_key}')
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
 def import_history_archives(self,bundle,observed_at=None):
  """Idempotently retain read-only archive rows and flag key collisions."""
  from campaign_history import ARCHIVE_TABS
  if not isinstance(bundle,dict):
   return {'available':False,'inserted':0,'conflicts':0,'missing_tabs':list(ARCHIVE_TABS)}
  observed_at=observed_at or datetime.now(timezone.utc).isoformat()
  parsed_observed=datetime.fromisoformat(observed_at.replace('Z','+00:00'))
  if parsed_observed.tzinfo is None: parsed_observed=parsed_observed.replace(tzinfo=timezone.utc)
  observed_utc=parsed_observed.astimezone(timezone.utc).isoformat()
  source_id='live:munda-manager-archives'
  self.record_source(source_id,'campaign_archive','mechanical_fact','Munda Manager historical archive tabs',source_uri='https://docs.google.com/spreadsheets/d/1Ofh1kDys_xp4a-idPc1NA2I1GCqndbVGjxenatezh00/edit')
  inserted=0; conflicts=0; seen=0
  records=bundle.get('records') or []
  if not isinstance(records,list): raise ValueError('Campaign archive records must be a list')
  with self._lock,self.db:
   for item in records:
    if not isinstance(item,dict) or not item.get('source_table') or not item.get('record_id'):
     continue
    source_table=str(item['source_table']); record_id=str(item['record_id'])
    version_hash=str(item.get('version_hash') or 'append-only')
    payload_hash=str(item.get('payload_hash') or hashlib.sha256(json.dumps(item.get('record') or {},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    if source_table not in {'gang_logs','campaign_battles','battle_sessions'}:
     continue
    seen+=1
    existing=self.db.execute('SELECT payload_hash FROM campaign_archive_records WHERE source_table=? AND record_id=? AND version_hash=?',(source_table,record_id,version_hash)).fetchone()
    row_json=item.get('source_row_json') or json.dumps({},ensure_ascii=False)
    raw_json=item.get('raw_record_json') or json.dumps(item.get('record') or {},ensure_ascii=False,sort_keys=True)
    if existing:
     if existing['payload_hash']!=payload_hash:
      self.db.execute('''INSERT OR IGNORE INTO campaign_archive_conflicts(
       source_table,record_id,version_hash,existing_payload_hash,conflicting_payload_hash,observed_at_utc,source_tab,source_row,source_row_json,raw_record_json)
       VALUES(?,?,?,?,?,?,?,?,?,?)''',(source_table,record_id,version_hash,existing['payload_hash'],payload_hash,observed_utc,item.get('source_tab') or '',item.get('source_row'),row_json,raw_json))
      if self.db.execute('SELECT changes()').fetchone()[0]: conflicts+=1
     continue
    self.db.execute('''INSERT INTO campaign_archive_records(
      source_table,record_id,version_hash,payload_hash,created_at_raw,created_at_utc,updated_at_raw,updated_at_utc,
      archived_at_raw,archived_at_utc,imported_at_utc,source_tab,source_row,source_row_json,raw_record_json,normalized_json)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
       source_table,record_id,version_hash,payload_hash,item.get('created_at_raw'),item.get('created_at_utc'),
       item.get('updated_at_raw'),item.get('updated_at_utc'),item.get('archived_at_raw'),item.get('archived_at_utc'),
       observed_utc,item.get('source_tab') or '',item.get('source_row'),row_json,raw_json,
       json.dumps(item,ensure_ascii=False,sort_keys=True,separators=(',',':'))))
    inserted+=1
   missing_tabs=bundle.get('missing_tabs') or []
   result={'available':len(missing_tabs)<len(ARCHIVE_TABS),'records_seen':seen,'inserted':inserted,'conflicts':conflicts,
           'missing_tabs':missing_tabs,'tab_counts':bundle.get('tab_counts') or {},
           'row_errors':bundle.get('row_errors') or []}
   self.db.execute('INSERT INTO campaign_archive_import_runs(imported_at_utc,result_json) VALUES(?,?)',(observed_utc,json.dumps(result,ensure_ascii=False,sort_keys=True)))
   self.db.execute("INSERT INTO system_state(key,value) VALUES('campaign_history_last_import',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(observed_utc,))
   self.db.execute("INSERT INTO system_state(key,value) VALUES('campaign_history_import_result',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(result,ensure_ascii=False,sort_keys=True),))
  return result
 def history_timeline(self):
  """Return the reconstructed campaign timeline with its source/conflict warnings."""
  from campaign_history import build_timeline
  records=[]
  for row in self.db.execute('SELECT normalized_json FROM campaign_archive_records ORDER BY source_table,record_id,archived_at_utc,version_hash'):
   try: records.append(json.loads(row['normalized_json']))
   except (TypeError,ValueError): continue
  gang_names={str(row['gang_id']):row['name'] for row in self.db.execute('SELECT gang_id,name FROM gangs')}
  fighter_names={}
  roster={}
  for row in self.db.execute('SELECT gang_id,name FROM fighters'):
   key=(str(row['gang_id'] or ''),re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(row['name'] or '')).strip().casefold()))
   roster.setdefault(key,[]).append(row['name'])
  for record in records:
   gang_id=record.get('gang_id'); fighter_id=record.get('fighter_id'); name=record.get('fighter_name_hint')
   if gang_id and fighter_id and name:
    normalized=re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(name)).strip().casefold())
    matches=roster.get((str(gang_id),normalized),[])
    fighter_names[(str(gang_id),str(fighter_id))]=matches[0] if len(matches)==1 else name
  territories={}
  for row in self.db.execute('SELECT mechanics_json,territory FROM territories'):
   try: mechanics=json.loads(row['mechanics_json'] or '{}')
   except (TypeError,ValueError): mechanics={}
   territory_id=mechanics.get('territory_id') or mechanics.get('territoryId')
   if territory_id: territories[str(territory_id)]=row['territory']
  timeline=build_timeline(records,gang_names,fighter_names,territories)
  fighter_rows={}
  for row in self.db.execute('SELECT id,gang_id,name FROM fighters'):
   name_key=re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(row['name'] or '')).strip().casefold())
   fighter_rows.setdefault((str(row['gang_id'] or ''),name_key),[]).append(row['id'])
  for event in timeline['events']:
   if event.get('fighter_name') and event.get('gang_id'):
    name_key=re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(event['fighter_name'])).strip().casefold())
    matches=fighter_rows.get((str(event['gang_id']),name_key),[])
    event['local_fighter_id']=matches[0] if len(matches)==1 else None
  conflict_count=self.db.execute('SELECT count(*) FROM campaign_archive_conflicts').fetchone()[0]
  conflicts=[dict(row) for row in self.db.execute('''SELECT source_table,record_id,version_hash,existing_payload_hash,conflicting_payload_hash,observed_at_utc,source_tab,source_row FROM campaign_archive_conflicts ORDER BY conflict_id DESC LIMIT 100''')]
  run=self.db.execute('SELECT imported_at_utc,result_json FROM campaign_archive_import_runs ORDER BY run_id DESC LIMIT 1').fetchone()
  import_result=json.loads(run['result_json']) if run else {'available':False,'missing_tabs':['MUNDA_ACTIVITY_RAW','MUNDA_BATTLES_RAW','MUNDA_SESSIONS_RAW']}
  timeline['warnings'].extend({'kind':'conflicting_archive_version',**item} for item in conflicts)
  for issue in import_result.get('row_errors',[]):
   timeline['warnings'].append({'kind':'archive_row_issue',**issue})
  for missing in import_result.get('missing_tabs',[]):
   timeline['warnings'].append({'kind':'missing_archive_tab','source_tab':missing,'message':'archive sheet tab was unavailable during the latest import'})
  timeline['import']={**import_result,'last_imported_at':run['imported_at_utc'] if run else None}
  timeline['stats']['conflicts']=conflict_count
  if conflict_count>len(conflicts):
   timeline['warnings'].append({'kind':'conflict_warning_limit','message':f'{conflict_count-len(conflicts)} older conflicts are not expanded in this response'})
  return timeline
 def fighter_history(self,fighter_id):
  fighter=self.db.execute('SELECT id,gang_id,name FROM fighters WHERE id=?',(fighter_id,)).fetchone()
  if not fighter:return {'events':[],'battles':[]}
  timeline=self.history_timeline()
  events=[event for event in timeline['events'] if event.get('local_fighter_id')==fighter_id]
  battle_ids={event.get('battle_id') or event.get('preceding_battle_id') or event.get('next_battle_id') for event in events}
  battles=[battle for battle in timeline['battles'] if battle['battle_id'] in battle_ids or str(fighter['gang_id']) in battle.get('gang_ids',[])]
  return {'events':events,'battles':battles,'warnings':timeline['warnings'],'import':timeline['import']}
 def gang_history(self,gang_id):
  timeline=self.history_timeline()
  return {'events':[event for event in timeline['events'] if str(event.get('gang_id') or '')==str(gang_id)],
          'battles':[battle for battle in timeline['battles'] if str(gang_id) in battle.get('gang_ids',[])],
          'warnings':timeline['warnings'],'import':timeline['import']}
 def project_snapshot(self,payload):
  """Refresh the app's current-state tables while preserving narrative/history fields."""
  gangs=payload.get('gangs') or {}; gang_index=payload.get('gang_index') or {}
  if any(record.get('Backstory') for gang in gangs.values() for record in (gang.get('fighters') or {}).values()):
   self.record_source('player:campaign-sheet-lore','authored_fighter_backstory','player_authored','Player-authored fighter backstories in the campaign Sheet',source_uri='https://docs.google.com/spreadsheets/d/1Ofh1kDys_xp4a-idPc1NA2I1GCqndbVGjxenatezh00/edit')
  with self._lock, self.db:
   self.db.execute('UPDATE gangs SET active=0')
   for tab_name,gang in gangs.items():
    gang_id=str(gang.get('gang_id') or '')
    if not gang_id: continue
    index=gang_index.get(gang_id,{})
    name=gang.get('name') or tab_name
    self.db.execute('''INSERT INTO gangs(gang_id,name,gang_type,player,rating,wealth,credits,reputation,territories,alignment,colour,updated_at,active)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1) ON CONFLICT(gang_id) DO UPDATE SET name=excluded.name,gang_type=excluded.gang_type,player=excluded.player,rating=excluded.rating,wealth=excluded.wealth,credits=excluded.credits,reputation=excluded.reputation,territories=excluded.territories,alignment=excluded.alignment,colour=excluded.colour,updated_at=excluded.updated_at,active=1''',
      (gang_id,name,gang.get('gang_type') or index.get('Type'),index.get('Player'),index.get('Rating',gang.get('rating')),index.get('Wealth'),gang.get('credits'),gang.get('reputation'),index.get('Territories'),gang.get('alignment'),gang.get('colour'),gang.get('last_updated')))
    self.db.execute('UPDATE fighters SET listed_in_source=0 WHERE gang_id=?',(gang_id,))
    fighter_rows=self.db.execute('SELECT id,name FROM fighters WHERE gang_id=?',(gang_id,)).fetchall()
    existing={re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(row['name'] or '')).strip().casefold()):row['id'] for row in fighter_rows}
    for source_name,record in (gang.get('fighters') or {}).items():
     normalized=unicodedata.normalize('NFKC',str(source_name or '')).strip().casefold()
     normalized=re.sub(r'\s+',' ',normalized)
     fighter_id=existing.get(normalized)
     values=(name,record.get('Type'),record.get('Class'),record.get('Cost'),record.get('XP'),record.get('Kills'),record.get('Advancements'),record.get('Effects'),record.get('Status'))
     if fighter_id:
      self.db.execute('''UPDATE fighters SET gang_name=?,name=?,type=?,class=?,cost=?,xp=?,kills=?,advancements=?,effects=?,status=?,listed_in_source=1 WHERE id=?''',(name,source_name,*values[1:],fighter_id))
     else:
      self.db.execute('''INSERT INTO fighters(gang_id,gang_name,name,type,class,cost,xp,kills,advancements,effects,status,backstory,backstory_source,listed_in_source)
       VALUES(?,?,?,?,?,?,?,?,?,?,?,'','not-yet-written',1)''',(gang_id,name,source_name,*values[1:]))
     self.db.execute('UPDATE fighters SET mechanics_json=?,notes=coalesce(?,notes) WHERE gang_id=? AND name=?',
                     (json.dumps(record,ensure_ascii=False,sort_keys=True),record.get('Fighter Notes') or record.get('Notes'),gang_id,source_name))
     if record.get('Backstory'):
      self.db.execute("""UPDATE fighters SET backstory=?,backstory_source='player-authored / campaign Sheet',provenance_class='player_authored'
       WHERE gang_id=? AND name=? AND lower(coalesce(backstory_source,'')) NOT LIKE '%c-nine story%' AND lower(coalesce(backstory_source,'')) NOT LIKE '%canon%'""",(record['Backstory'],gang_id,source_name))

   self.db.execute('UPDATE territories SET active=0')
   for territory in payload.get('territories') or []:
    territory_name=territory.get('Territory') or territory.get('territory') or territory.get('Name') or territory.get('name')
    if not territory_name: continue
    gang_id=territory.get('Gang ID') or territory.get('gang_id')
    gang_name=territory.get('Gang') or territory.get('gang') or territory.get('Gang Name') or territory.get('gang_name')
    source_territory_id=territory.get('source_territory_key') or territory.get('Territory ID') or territory.get('territory_id') or territory.get('Record ID')
    card=territory.get('Card') or territory.get('card')
    default=territory.get('Default',territory.get('is_default',False))
    ruined=territory.get('Ruined',territory.get('ruined',False))
    if source_territory_id:
     prior=self.db.execute('SELECT id FROM territories WHERE source_territory_id=?',(str(source_territory_id),)).fetchone()
     if not prior:
      prior=self.db.execute('SELECT id FROM territories WHERE ifnull(gang_id,\'\')=ifnull(?,\'\') AND territory=? AND ifnull(card,\'\')=ifnull(?,\'\') AND is_default=? AND ruined=? ORDER BY id DESC LIMIT 1',(gang_id,territory_name,card,int(bool(default)),int(bool(ruined)))).fetchone()
    else:
      prior=self.db.execute('SELECT id FROM territories WHERE ifnull(gang_id,\'\')=ifnull(?,\'\') AND territory=? AND ifnull(card,\'\')=ifnull(?,\'\') AND is_default=? AND ruined=? ORDER BY id DESC LIMIT 1',(gang_id,territory_name,card,int(bool(default)),int(bool(ruined)))).fetchone()
    if not prior and card:
     matches=self.db.execute('SELECT id FROM territories WHERE card=?',(card,)).fetchall()
     if len(matches)==1: prior=matches[0]
    if not prior and not source_territory_id:
     matches=self.db.execute('SELECT id FROM territories WHERE territory=? AND is_default=?',(territory_name,int(bool(default)))).fetchall()
     if len(matches)==1: prior=matches[0]
    if prior:
     self.db.execute('''UPDATE territories SET gang_id=?,gang_name=?,territory=?,card=?,is_default=?,ruined=?,active=1,source_territory_id=coalesce(?,source_territory_id) WHERE id=?''',(gang_id,gang_name,territory_name,card,int(bool(default)),int(bool(ruined)),str(source_territory_id) if source_territory_id else None,prior['id']))
    else:
     self.db.execute('''INSERT INTO territories(gang_id,gang_name,territory,card,is_default,ruined,active,source_territory_id) VALUES(?,?,?,?,?,?,1,?)''',(gang_id,gang_name,territory_name,card,int(bool(default)),int(bool(ruined)),str(source_territory_id) if source_territory_id else None))
    territory_row_id=prior['id'] if prior else self.db.execute('SELECT last_insert_rowid()').fetchone()[0]
    self.db.execute('UPDATE territories SET mechanics_json=? WHERE id=?',(json.dumps(territory,ensure_ascii=False,sort_keys=True),territory_row_id))

   from snapshot import battle_identity, battle_records
   prior_battles={}
   for row in self.db.execute('SELECT * FROM battles ORDER BY active DESC,id DESC'):
    old=dict(row); key=old.get('source_battle_key') or battle_identity(old)
    prior_battles.setdefault(key,old['id'])
   self.db.execute('UPDATE battles SET active=0,source_row=-id')
   for battle in battle_records(payload.get('battles') or []):
    source_row=battle.get('source_row')
    if source_row is None: continue
    key=battle.get('battle_key') or battle_identity(battle)
    values=(source_row,battle.get('date'),battle.get('scenario'),battle.get('attacker'),battle.get('defender'),battle.get('winner'),battle.get('territory'),battle.get('territory_claimer'),battle.get('notes'),key)
    if key in prior_battles:
     self.db.execute('''UPDATE battles SET source_row=?,date=?,scenario=?,attacker=?,defender=?,winner=?,territory=?,territory_claimer=?,notes=?,source_battle_key=?,active=1 WHERE id=?''',(*values,prior_battles[key]))
    else:
     self.db.execute('''INSERT INTO battles(source_row,date,scenario,attacker,defender,winner,territory,territory_claimer,notes,source_battle_key,active) VALUES(?,?,?,?,?,?,?,?,?,?,1)''',values)

  return {'gangs':len(gangs),'fighters_listed':sum(len(g.get('fighters') or {}) for g in gangs.values()),'territories':len(payload.get('territories') or []),'battles':len(payload.get('battles') or [])}
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
  from story_engine import document_for
  from writing_director import public_policy
  q=lambda sql,args=():[dict(r) for r in self.db.execute(sql,args)]
  battle_sql='''SELECT b.*,EXISTS(SELECT 1 FROM campaign_events ce WHERE (ce.source_locator=\'Battles!row \'||b.source_row OR ce.source_locator=\'Battles!battle \'||b.source_battle_key) AND ce.event_type IN (\'battle_record_corrected\',\'battle_record_removed\')) AS chronicle_stale FROM battles b WHERE b.active=1 ORDER BY b.date DESC,b.source_row DESC'''
  result={'gangs':q('SELECT * FROM gangs WHERE active=1 ORDER BY reputation DESC,rating DESC'),'battles':q(battle_sql),'territories':q('SELECT * FROM territories WHERE active=1 ORDER BY gang_name,territory'),'regions':q('SELECT * FROM regions'),'downtime':q('SELECT * FROM downtime_reports WHERE id IN (SELECT max(id) FROM downtime_reports GROUP BY gang_id) ORDER BY generated_at DESC'),'state':{r['key']:r['value'] for r in self.db.execute('SELECT * FROM system_state')}}
  result['writing_policy']=public_policy()
  import llm_writer
  result['writer']=llm_writer.availability()
  from world_streams import association_notes
  result['place_association_notes']=association_notes(self,result['battles'])
  for g in result['gangs']: g['history_document']=document_for(self,'gang_origin',g['gang_id']) or document_for(self,'gang_history',g['gang_id'])
  for b in result['battles']:
   b['report_document']=document_for(self,'battle_report',b['id'])
   if b['report_document']: b['chronicle_stale']=False
  for t in result['territories']: t['history_document']=document_for(self,'territory_origin',t['id']) or document_for(self,'territory_history',t['id'])
  for r in result['regions']: r['history_document']=document_for(self,'region_history','campaign')
  for d in result['downtime']: d['document']=document_for(self,'downtime',d['gang_id'])
  return result
 def gang(self,gid):
  from story_engine import document_for
  r=self.db.execute('SELECT * FROM gangs WHERE gang_id=?',(gid,)).fetchone()
  if not r:return None
  g=dict(r); name=g['name']; q=lambda sql,args=():[dict(x) for x in self.db.execute(sql,args)]
  g['territory_list']=q('SELECT * FROM territories WHERE gang_id=? AND active=1 ORDER BY territory',(gid,)); g['fighters']=q('SELECT * FROM fighters WHERE gang_id=? ORDER BY listed_in_source DESC,status,name',(gid,)); g['battles']=q('''SELECT b.*,EXISTS(SELECT 1 FROM campaign_events ce WHERE (ce.source_locator=\'Battles!row \'||b.source_row OR ce.source_locator=\'Battles!battle \'||b.source_battle_key) AND ce.event_type IN (\'battle_record_corrected\',\'battle_record_removed\')) AS chronicle_stale FROM battles b WHERE b.active=1 AND (b.attacker=? OR b.defender=? OR b.winner=? OR b.territory_claimer=?) ORDER BY b.date DESC''',(name,name,name,name)); g['downtime']=q('SELECT * FROM downtime_reports WHERE gang_id=? ORDER BY id DESC',(gid,))
  from world_streams import read_stream
  g['history_document']=document_for(self,'gang_origin',gid) or document_for(self,'gang_history',gid)
  g['campaign_account_document']=document_for(self,'gang_history',gid)
  g['campaign_history']=self.gang_history(gid)
  g['narrative_stream']=read_stream(self,'gang',gid)
  for b in g['battles']:
   b['report_document']=document_for(self,'battle_report',b['id'])
   if b['report_document']: b['chronicle_stale']=False
  for d in g['downtime']: d['document']=document_for(self,'downtime',gid)
  return g
 def fighter(self,fid):
  r=self.db.execute('SELECT * FROM fighters WHERE id=?',(fid,)).fetchone()
  if not r:return None
  f=dict(r); q=lambda sql,args=():[dict(x) for x in self.db.execute(sql,args)]
  f['events']=q('SELECT * FROM fighter_events WHERE fighter_id=? ORDER BY id DESC',(fid,)); f['memories']=q('SELECT * FROM memories WHERE fighter_id=? ORDER BY importance DESC,id DESC',(fid,)); f['moodlets']=q('SELECT * FROM moodlets WHERE fighter_id=? ORDER BY intensity DESC',(fid,))
  fighter_name=unicodedata.normalize('NFKC',str(f['name'] or '')).strip().casefold(); fighter_name=re.sub(r'\s+',' ',fighter_name)
  entity_key=f"{f['gang_id']}/{fighter_name}"
  entity=self.db.execute('SELECT entity_id FROM entities WHERE entity_type=\'fighter\' AND entity_key=?',(entity_key,)).fetchone()
  f['campaign_events']=self.events(limit=500,entity_id=entity['entity_id']) if entity else []
  from story_engine import fighter_story
  f.update(fighter_story(self,f))
  f['campaign_history']=self.fighter_history(fid)
  f['mechanics']=json.loads(f.get('mechanics_json') or '{}')
  f['writer_identity']=json.loads(f.get('writer_identity_json') or '{}')
  return f
 def territory(self,tid):
  from story_engine import document_for
  r=self.db.execute('SELECT * FROM territories WHERE id=?',(tid,)).fetchone()
  if not r:return None
  from world_streams import read_stream
  t=dict(r); t['history_document']=document_for(self,'territory_origin',tid) or document_for(self,'territory_history',tid)
  t['campaign_account_document']=document_for(self,'territory_history',tid)
  t['narrative_stream']=read_stream(self,'territory',tid)
  t['mechanics']=json.loads(t.get('mechanics_json') or '{}')
  return t
 def set_writer_identity(self,fid,identity):
  from writing_director import validate_identity
  identity=validate_identity(identity)
  self.record_source('player:writer-identities','authored_identity_context','player_authored','Character writing context entered in the app')
  with self._lock,self.db:
   if not self.db.execute('SELECT 1 FROM fighters WHERE id=?',(fid,)).fetchone(): raise ValueError('Fighter not found')
   self.db.execute('UPDATE fighters SET writer_identity_json=? WHERE id=?',(json.dumps(identity,ensure_ascii=False,sort_keys=True),fid))
   identity_text=json.dumps(identity,ensure_ascii=False,sort_keys=True)
   written_at=datetime.now(timezone.utc).isoformat()
   revision=hashlib.sha256(f'{fid}:{written_at}:{identity_text}'.encode()).hexdigest()[:32]
   self.db.execute('INSERT INTO writer_identity_revisions(revision_id,fighter_id,identity_json,created_at) VALUES(?,?,?,?)',(revision,fid,identity_text,written_at))
  from story_engine import regenerate
  regenerate(self)
  return self.fighter(fid)
 def lore(self): return [dict(r) for r in self.db.execute('SELECT id,title,source_type,source_url,length(content) AS chars FROM lore_sources')]
 def lore_source(self,lid):
  r=self.db.execute('SELECT * FROM lore_sources WHERE id=?',(lid,)).fetchone(); return dict(r) if r else None
