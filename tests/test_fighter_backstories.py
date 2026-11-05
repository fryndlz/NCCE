"""Source correction preserves player text, accepted artifacts and audit history."""
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from store import Store
from fighter_backstories import reconcile, SOURCE
from personnel import identity, gang_code


def main():
    with tempfile.TemporaryDirectory() as directory:
        s=Store(Path(directory)/'test.db')
        try:
            dirty='Designation: IT THAT SPOKE\nRETRIEVING GPD-C9\nPrincipal: Marcella Veyne'
            clean='Designation: IT THAT SPOKE\n[ERR:: SUBJECT NOT PRESENT]\n\nOriginal authored wording.\n'
            fid=s.db.execute("INSERT INTO fighters(gang_id,gang_name,name,backstory,backstory_source,provenance_class) VALUES('g','C-NINE','It That Spoke',?,'player-authored / C-NINE story','canon_authored')",(dirty,)).lastrowid
            snapshot={'gangs':{'C-NINE':{'gang_id':'g','name':'C-NINE','fighters':{'It That Spoke':{'Name':'It That Spoke','Backstory':clean}}}}}
            s.project_snapshot(snapshot)
            row=dict(s.db.execute('SELECT * FROM fighters WHERE id=?',(fid,)).fetchone())
            assert row['backstory']==clean and row['backstory_source']==SOURCE
            assert row['provenance_class']=='player_authored'
            audits=s.db.execute("SELECT metadata_json FROM provenance_sources WHERE source_type='retired_biography_projection'").fetchall()
            assert len(audits)==1 and json.loads(audits[0][0])['backstory']==dirty
            assert not reconcile(s) and s.db.execute("SELECT count(*) FROM provenance_sources WHERE source_type='retired_biography_projection'").fetchone()[0]==1
            snapshot['gangs']['C-NINE']['fighters']['It That Spoke'].pop('Backstory')
            s.project_snapshot(snapshot)
            assert s.db.execute('SELECT backstory FROM fighters WHERE id=?',(fid,)).fetchone()[0]==clean
            snapshot['gangs']['C-NINE']['fighters']['It That Spoke']['Backstory']=''
            s.project_snapshot(snapshot)
            assert not s.db.execute('SELECT backstory FROM fighters WHERE id=?',(fid,)).fetchone()[0]
            # Legacy Doc-only fallback is retired even before the next live sync.
            s.db.execute("UPDATE fighters SET backstory=?,backstory_source='player-authored / C-NINE story',mechanics_json='{}' WHERE id=?",(dirty,fid))
            assert reconcile(s)==1
            assert s.db.execute('SELECT backstory_source FROM fighters WHERE id=?',(fid,)).fetchone()[0]=='not-provided'
            # Accepted/generated biography remains intact when no authored MM text exists.
            s.db.execute("UPDATE fighters SET backstory='Accepted external draft',backstory_source='mechanically-inferred' WHERE id=?",(fid,))
            assert not reconcile(s)
            assert s.db.execute('SELECT backstory FROM fighters WHERE id=?',(fid,)).fetchone()[0]=='Accepted external draft'
            # Codes never use local integer IDs or an opaque/redacted legacy code.
            f={'id':37,'name':'Eisen','gang_id':'g','gang_name':'The Slag Eaters','mechanics_json':'{}'}
            assert identity(s,f)['personnel_code'] is None
            source='6f61dddd-6934-45e4-aaa1-0feb4e46bcDE'
            f['mechanics_json']=json.dumps({'Fighter ID':source})
            assert identity(s,f)['personnel_code']=='se-MK/bcDE'
            f['mechanics_json']='{}'
            def archive(key,gang,name,source_id):
                entry=json.dumps({'gang_id':gang,'fighter_name_hint':name,'fighter_id':source_id})
                s.db.execute('''INSERT INTO campaign_archive_records(source_table,record_id,version_hash,payload_hash,
                    imported_at_utc,source_tab,source_row_json,raw_record_json,normalized_json)
                    VALUES('gang_logs',?,'v','hash','2026-11-05','MUNDA_ACTIVITY_RAW','[]','{}',?)''',(key,entry))
            archive('wrong-gang','another','Eisen',source)
            archive('wrong-name','g','Someone else',source)
            assert identity(s,f)['personnel_code'] is None
            archive('correct','g',' Eisen ',source)
            assert identity(s,f)['personnel_code']=='se-MK/bcDE'
            archive('conflicting','g','Eisen','ffffffff-6934-45e4-aaa1-0feb4e46abcd')
            assert identity(s,f)['personnel_code'] is None
            assert [gang_code(n) for n in ('C-NINE','Kły Sprawiedliwości','The Slag Eaters')]==['c9','ks','se']
            print('PASS MM source authority, exact wording, missing/empty fields, retirement audit, generated text and UUID identifiers')
        finally:s.close()


if __name__=='__main__':main()
