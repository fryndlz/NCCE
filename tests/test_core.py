import json, sqlite3, sys, tempfile
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from store import Store, SCHEMA
from access import SESSION_MAX_AGE, configured_bool, effective_session_key, make_session_token, valid_session_token
from snapshot import build_snapshot_from_sheets, parse_battles, parse_gang_tab, read_xlsx_sheets
from sync import ingest_snapshot

def test_store():
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'data') as d:
        s=Store(Path(d)/'x.db')
        try:
            s.set_state('a','b'); assert s.get_state('a')=='b'
        finally:
            s.close()

def test_read_only_snapshot_remains_available_during_writer_transaction():
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'data') as d:
        s=Store(Path(d)/'reader.db')
        try:
            s.db.execute("INSERT INTO gangs(gang_id,name) VALUES('old','Committed gang')"); s.db.commit()
            with s._lock,s.db:
                s.db.execute("INSERT INTO gangs(gang_id,name) VALUES('new','Uncommitted gang')")
                with s.reader() as reader:
                    names=[row[0] for row in reader.db.execute('SELECT name FROM gangs ORDER BY gang_id')]
                    assert names==['Committed gang']
                    try:
                        reader.db.execute("INSERT INTO gangs(gang_id,name) VALUES('bad','Forbidden')")
                        raise AssertionError('Reader connection must remain query-only')
                    except sqlite3.OperationalError:
                        pass
            with s.reader() as reader:
                assert reader.db.execute("SELECT name FROM gangs WHERE gang_id='new'").fetchone()[0]=='Uncommitted gang'
        finally: s.close()

def test_invite_sessions():
    key=effective_session_key('invited-friends-passphrase','a'*48)
    token=make_session_token(key,now=1000)
    assert valid_session_token(token,key,now=1001)
    assert not valid_session_token(token,key,now=1000+SESSION_MAX_AGE)
    assert not valid_session_token(token,key+b'wrong',now=1001)
    assert not valid_session_token(token[:-1]+'0',key,now=1001)
    assert effective_session_key('rotated-passphrase','a'*48)!=key
    assert configured_bool('true') and configured_bool('1') and not configured_bool('false')

def test_gang_parser():
    rows=[['Gang'],[],['Gang ID','1'],['Gang Type','House Orlock'],['Credits','5'],['Reputation','2'],['Rating','100'],['Alignment','Law Abiding'],[],['FIGHTERS'],['Name','Type','Class'],['A','Gunner','Ganger']]
    g=parse_gang_tab(rows); assert g['gang_id']=='1' and g['fighters']['A']['Class']=='Ganger'

def test_live_sheet_snapshot_shape():
    tabs={
        'Campaign':[['Field','Value'],['Name','Krakaumunda']],
        'Gangs':[['Gang ID','Gang','Type','Player'],['g1','Iron Dogs','Orlock','Player']],
        'Territories':[['Gang ID','Gang','Territory','Card','Default','Ruined'],['g1','Iron Dogs','Old Pump','8♠',False,False]],
        'Battles':[['Date','Scenario','Attacker','Defender','Winner','Territory','Territory Claimer','Notes'],['2026-01-01','Skirmish','Iron Dogs','Ash Walkers','Iron Dogs','Old Pump','Iron Dogs','context']],
        'MAIN':[['Connection Status',200],['Data Dump',json.dumps({'campaign':{'id':'c1'},'members':[{'gangs':[{'id':'g1','territories':[{'id':'t1','name':'Old Pump'}]}]}]})]],
        'Iron Dogs':[['Iron Dogs'],[],['Gang ID','g1'],['Gang Type','Orlock'],['Credits',5],['Reputation',1],['Rating',100],['Alignment','Law Abiding'],[],[],[],[],[],['FIGHTERS'],['Name','Type','Class'],['Rook','Gunner','Ganger']],
    }
    snapshot=build_snapshot_from_sheets(tabs,captured_at='2026-01-02T00:00:00+00:00')
    assert snapshot['gangs']['Iron Dogs']['fighters']['Rook']['Class']=='Ganger'
    assert snapshot['territories'][0]['territory_id']=='t1'
    assert snapshot['battles'][0]['winner']=='Iron Dogs'
    assert snapshot['battles'][0]['source_row']==2
    assert snapshot['source_metadata']['campaign_id']=='c1'
    assert parse_battles(tabs['Battles'])[0]['date']=='2026-01-01'

def test_stdlib_xlsx_reader():
    buffer=BytesIO()
    with ZipFile(buffer,'w') as archive:
        archive.writestr('xl/workbook.xml','''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Campaign" sheetId="1" r:id="rId1"/></sheets></workbook>''')
        archive.writestr('xl/_rels/workbook.xml.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/></Relationships>''')
        archive.writestr('xl/worksheets/sheet1.xml','''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Field</t></is></c><c r="B1" t="inlineStr"><is><t>Value</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>Name</t></is></c><c r="B2" t="inlineStr"><is><t>Krakaumunda</t></is></c></row></sheetData></worksheet>''')
    sheets=read_xlsx_sheets(buffer.getvalue())
    assert sheets['Campaign']==[['Field','Value'],['Name','Krakaumunda']]

def test_durable_ledger_and_snapshot_deduplication():
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'data') as d:
        s=Store(Path(d)/'ledger.db')
        try:
            source=s.record_source('test:sheet','campaign_sheet','mechanical_fact','Test Sheet')
            fighter=s.register_entity('fighter','g1/subject alpha','Subject Alpha','mechanical_fact',source)
            live_source=s.record_source('test:live-sheet','campaign_sheet','mechanical_fact','Live Test Sheet')
            assert s.register_entity('fighter','g1/subject alpha','Subject Alpha','mechanical_fact',live_source)==fighter
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
            assert s.db.execute('PRAGMA user_version').fetchone()[0]==15
        finally:
            s.close()

def test_legacy_database_provenance_migration():
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'data') as d:
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
            assert s.schema_version==15
            assert {'request_id','response_id','subject_name','input_tokens','output_tokens'} <= {row['name'] for row in s.db.execute('PRAGMA table_info(writer_requests)')}
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

    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as d:
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
            removed=snapshot('2026-01-03T00:00:00+00:00', 2, 'g2', [changed['battles'][0]])
            removal=ingest_snapshot(s,removed)
            assert s.db.execute("SELECT count(*) FROM campaign_events WHERE event_type='battle_record_removed'").fetchone()[0]==1
            superseded=s.db.execute("SELECT supersedes_event_id FROM campaign_events WHERE event_type='battle_record_removed'").fetchone()[0]
            assert superseded is not None
            projection=s.project_snapshot(removed)
            assert projection['battles']==1 and s.db.execute('SELECT count(*) FROM battles WHERE active=1').fetchone()[0]==1
            assert s.dashboard()['battles'][0]['chronicle_stale']==1
            departed=dict(removed); departed['captured_at']='2026-01-04T00:00:00+00:00'; departed['gangs']=dict(removed['gangs']); departed['gangs'].pop('Ash Walkers')
            ingest_snapshot(s,departed)
            assert s.db.execute("SELECT count(*) FROM campaign_events WHERE event_type='gang_unlisted'").fetchone()[0]==1
            s.project_snapshot(departed)
            assert len(s.dashboard()['gangs'])==1
        finally:
            s.close()

if __name__=='__main__': test_store(); test_read_only_snapshot_remains_available_during_writer_transaction(); test_invite_sessions(); test_gang_parser(); test_live_sheet_snapshot_shape(); test_stdlib_xlsx_reader(); test_durable_ledger_and_snapshot_deduplication(); test_legacy_database_provenance_migration(); test_snapshot_ingest_diff_and_retry(); print('ok')
