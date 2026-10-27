"""Source isolation, refresh/removal, and exact archive story boundaries."""
import sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from snapshot import parse_gang_tab
from store import Store
from authored_archive import stories

def main():
    raw='+++ OFFICE +++\n\nOriginal authored words.\nReference: A/1'
    gang=parse_gang_tab([['A'],['Gang ID','g1'],['GANG NOTES'],['Tactics and bookkeeping'],
                         ['GANG BACKSTORY'],[raw],['FIGHTERS'],['Name','Type']])
    assert gang['backstory']==raw and gang['notes']=='Tactics and bookkeeping'
    assert parse_gang_tab([['B'],['Gang ID','g2'],['GANG NOTES'],['Not fiction']])['backstory'] is None
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        store=Store(Path(directory)/'test.db')
        try:
            store.db.execute('INSERT INTO snapshots(captured_at,payload_json) VALUES(?,?)',('2026-10-24','{"gangs":6}'))
            store.db.execute("INSERT INTO gangs(gang_id,name,backstory,backstory_source) VALUES('g1','A','THE PROSPECT old prose','player-authored / C-NINE story')")
            assert not store.gang('g1')['backstory']
            store.project_snapshot({'gangs':{'A':gang,'B':{'gang_id':'g2','name':'B'}}})
            assert store.gang('g1')['backstory']==raw
            assert store.gang('g1')['backstory_source']=='player-authored / campaign Sheet'
            assert store.gang('g1')['history_document'] is None
            assert not store.gang('g2')['backstory']
            assert next(g for g in store.dashboard()['gangs'] if g['gang_id']=='g1')['backstory']==raw
            changed={**gang,'backstory':'Revised by player.'}
            store.project_snapshot({'gangs':{'A':changed}})
            assert store.gang('g1')['backstory']=='Revised by player.'
            # Missing section in a rebuilt export preserves the last authored text.
            store.project_snapshot({'gangs':{'A':{**gang,'backstory':None,'backstory_available':False}}})
            assert store.gang('g1')['backstory']=='Revised by player.'
            # An explicitly present empty section clears it.
            store.project_snapshot({'gangs':{'A':{**gang,'backstory':None,'backstory_available':True}}})
            assert not store.gang('g1')['backstory']
            # Recover a lost projection after restart from the immutable Sheet snapshot.
            store.db.execute('INSERT INTO snapshots(captured_at,payload_json) VALUES(?,?)',
                             ('2026-10-27',__import__('json').dumps({'gangs':{'A':gang}})))
            store.project_snapshot({'gangs':{'A':{**gang,'backstory':None,'backstory_available':False}}})
            assert store.gang('g1')['backstory']==raw
            text=(ROOT/'data/lore/C-NINE Story - canonical export.txt').read_text(encoding='utf-8-sig')
            store.db.execute('INSERT INTO lore_sources(title,content,source_type,source_url) VALUES(?,?,?,?)',
                             ('C-NINE Story',text,'authored','https://example.com/source'))
            entries=stories(store)
            assert [e['title'] for e in entries]==['The Prospect','The Deep Answers']
            assert entries[0]['content'].startswith('Daven Holt had been Foreman')
            assert entries[0]['content'].endswith('Now, at last, the real work could begin.')
            assert entries[1]['content'].startswith('The Sludge Sea concealed')
            assert entries[1]['content'].endswith('He drew the line anyway.')
            assert all('INCIDENT REVIEW' not in e['content'] and 'PERSONNEL FILES' not in e['content'] for e in entries)
            assert store.db.execute('SELECT content FROM lore_sources').fetchone()[0]==text
        finally: store.close()
    print('ok (authored gang projection, empty/removal handling, archive boundaries and source preservation)')

if __name__=='__main__':main()
