import sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from store import Store
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

if __name__=='__main__': test_store(); test_gang_parser(); print('ok')
