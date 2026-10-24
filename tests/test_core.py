import json, sqlite3, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from store import Store, SCHEMA
from snapshot import parse_gang_tab
from sync import ingest_snapshot

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

def test_snapshot_ingest_diff_and_retry():
    def snapshot(captured_at, xp, territory_owner, battles):
        return {
            'snapshot_version': 1,
            'captured_at': captured_at,
            'gangs': {
                'Iron Dogs': {
                    'gang_id': 'g1', 'name': 'Iron Dogs', 'gang_type': 'Orlock',
                    'credits': 10, 'reputation': 2, 'rating': 100,
                    'fighters': {
                        'Rook': {'Name': 'Rook', 'XP': xp, 'Status': 'Active'},
                        **({'Ash': {'Name': 'Ash', 'XP': 0}} if xp > 0 else {}),
                    },
                },
                'Ash Walkers': {
                    'gang_id': 'g2', 'name': 'Ash Walkers', 'fighters': {},
                },
            },
            'territories': [{'Territory ID': 't1', 'Territory': 'Old Pump', 'Gang ID': territory_owner}],
            'battles': battles,
        }

    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.tmp-test') as d:
        s=Store(Path(d)/'sync.db')
        try:
            initial=snapshot('2026-01-01T00:00:00+00:00', 0, 'g1', [
                {'source_row': 2, 'date': '2026-01-01', 'scenario': 'Skirmish', 'attacker': 'Iron Dogs', 'defender': 'Ash Walkers', 'winner': 'Iron Dogs', 'territory': 'Old Pump'}
            ])
            baseline=ingest_snapshot(s,initial)
            assert baseline['snapshot_created'] and baseline['events_considered']==0
            changed=snapshot('2026-01-02T00:00:00+00:00', 2, 'g2', [
                {'source_row': 2, 'date': '2026-01-01', 'scenario': 'Skirmish', 'attacker': 'Iron Dogs', 'defender': 'Ash Walkers', 'winner': 'Ash Walkers', 'territory': 'Old Pump'},
                {'source_row': 3, 'date': '2026-01-02', 'scenario': 'Ambush', 'attacker': 'Ash Walkers', 'defender': 'Iron Dogs', 'winner': 'Ash Walkers', 'territory': 'Old Pump'},
            ])
            result=ingest_snapshot(s,changed)
            types={row['event_type'] for row in s.events(limit=100)}
            assert {'fighter_xp_changed','fighter_recruited','territory_holder_changed','battle_result','battle_record_corrected'} <= types
            correction=s.db.execute("SELECT supersedes_event_id,occurred_at,observed_at FROM campaign_events WHERE event_type='battle_record_corrected'").fetchone()
            assert correction['occurred_at'] is None and correction['observed_at']=='2026-01-02T00:00:00+00:00'
            assert correction['supersedes_event_id'] is None  # first observed by this ledger; no invented prior event
            repeated=ingest_snapshot(s,changed)
            assert repeated['snapshot_id']==result['snapshot_id'] and not repeated['snapshot_created']
            assert not repeated['events_created'] and repeated['events_considered']==result['events_considered']
            assert s.db.execute('SELECT count(*) FROM campaign_events').fetchone()[0]==result['events_considered']
            assert s.db.execute('PRAGMA foreign_key_check').fetchall()==[]
        finally:
            s.close()

if __name__=='__main__': test_store(); test_gang_parser(); test_durable_ledger_and_snapshot_deduplication(); test_legacy_database_provenance_migration(); test_snapshot_ingest_diff_and_retry(); print('ok')
