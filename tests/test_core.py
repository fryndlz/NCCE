import json, sqlite3, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from store import Store, SCHEMA
from snapshot import parse_gang_tab

def test_store():
    with tempfile.TemporaryDirectory() as d:
        s=Store(Path(d)/'x.db')
        try:
            s.set_state('a','b'); assert s.get_state('a')=='b'
        finally:
            s.close()

def test_gang_parser():
    rows=[['Gang'],[],['Gang ID','1'],['Gang Type','House Orlock'],['Credits','5'],['Reputation','2'],['Rating','100'],['Alignment','Law Abiding'],[],['FIGHTERS'],['Name','Type','Class'],['A','Gunner','Ganger']]
    g=parse_gang_tab(rows); assert g['gang_id']=='1' and g['fighters']['A']['Class']=='Ganger'

def test_durable_ledger_and_snapshot_deduplication():
    with tempfile.TemporaryDirectory() as d:
        s=Store(Path(d)/'ledger.db')
        try:
            source=s.record_source('test:sheet','campaign_sheet','mechanical_fact','Test Sheet')
            fighter=s.register_entity('fighter','g1/subject alpha','Subject Alpha','mechanical_fact',source)
            first_snapshot,created=s.save_snapshot({'captured_at':'2026-01-01T00:00:00+00:00','source_id':source,'gangs':[]})
            assert created
            same_snapshot,created=s.save_snapshot({'captured_at':'2026-01-02T00:00:00+00:00','source_id':source,'gangs':[]})
            assert first_snapshot==same_snapshot and not created
            event,created=s.record_event('sheet:g1:xp:subject-alpha:0001','xp_change',{'before':0,'after':1},'mechanical_fact',source_id=source,from_snapshot_id=first_snapshot,to_snapshot_id=first_snapshot,subjects=[{'entity_id':fighter,'role':'affected'}])
            assert created
            same_event,created=s.record_event('sheet:g1:xp:subject-alpha:0001','xp_change',{'before':0,'after':1},'mechanical_fact',source_id=source,from_snapshot_id=first_snapshot,to_snapshot_id=first_snapshot,subjects=[{'entity_id':fighter,'role':'affected'}])
            assert same_event==event and not created
            assert s.events(entity_id=fighter)[0]['payload']=={'after':1,'before':0}
            try:
                s.db.execute('UPDATE campaign_events SET payload_json=? WHERE event_id=?',('{}',event))
                raise AssertionError('Campaign event update should be rejected')
            except sqlite3.IntegrityError:
                pass
            try:
                s.db.execute('UPDATE snapshots SET payload_json=? WHERE id=?',('{}',first_snapshot))
                raise AssertionError('Snapshot update should be rejected')
            except sqlite3.IntegrityError:
                pass
            assert s.db.execute('PRAGMA user_version').fetchone()[0]==1
        finally:
            s.close()

def test_legacy_database_provenance_migration():
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'legacy.db'
        db=sqlite3.connect(path); db.row_factory=sqlite3.Row; db.executescript(SCHEMA)
        db.execute("INSERT INTO system_state(key,value) VALUES('last_sync','2026-10-01T12:00:00+00:00')")
        db.execute("INSERT INTO gangs(gang_id,name,gang_type,backstory,backstory_source) VALUES('g1','Test Gang','House Orlock','Inferred account.','mechanically-inferred')")
        fighter=db.execute("INSERT INTO fighters(gang_id,gang_name,name,type,class,xp,kills,status,backstory,backstory_source) VALUES('g1','Test Gang','Subject Alpha','Gunner','Ganger',0,0,'Active','Inferred origin.','mechanically-inferred')").lastrowid
        old_event=db.execute("INSERT INTO fighter_events(fighter_id,event_type,title,detail,source,confidence) VALUES(?,?,?,?,?,?)",(fighter,'baseline','Baseline imported','0 XP at baseline','authoritative sheet',1.0)).lastrowid
        db.execute("INSERT INTO memories(fighter_id,memory_type,content,importance,source_event_id,source,confidence) VALUES(?,?,?,?,?,?,?)",(fighter,'observation','0 XP at baseline',4,old_event,'authoritative sheet',1.0))
        db.execute("INSERT INTO territories(gang_id,gang_name,territory,backstory) VALUES('g1','Test Gang','Settlement','Inferred place history.')")
        db.execute("INSERT INTO battles(source_row,date,scenario,attacker,defender,winner,territory,territory_claimer) VALUES(2,'2026-10-01','Skirmish','Test Gang','Rival Gang','Test Gang','Settlement','Test Gang')")
        db.execute("INSERT INTO regions(name,backstory) VALUES('Test Region','Inferred regional account.')")
        db.execute("INSERT INTO snapshots(captured_at,payload_json) VALUES(?,?)",('2026-10-01T12:00:00+00:00',json.dumps({'baseline':'legacy'})))
        db.commit(); db.close()
        s=Store(path)
        try:
            assert s.schema_version==1
            assert s.db.execute('SELECT count(*) FROM campaign_events').fetchone()[0]==2
            assert s.db.execute("SELECT provenance_class FROM memories").fetchone()[0]=='mechanical_fact'
            assert s.db.execute("SELECT count(*) FROM event_subjects").fetchone()[0]>=5
            assert s.db.execute("SELECT count(*) FROM narrative_evidence").fetchone()[0]>0
            assert s.db.execute("SELECT payload_hash FROM snapshots").fetchone()[0]
        finally:
            s.close()

if __name__=='__main__': test_store(); test_gang_parser(); test_durable_ledger_and_snapshot_deduplication(); test_legacy_database_provenance_migration(); print('ok')
