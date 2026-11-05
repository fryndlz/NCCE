from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json,re
from store import Store
from baseline_data import GANGS,TERRITORIES,BATTLES
from narrative import *
ROOT=Path(__file__).resolve().parents[1]

def main(path):
    p=Path(path)
    if p.exists():
        raise FileExistsError(f"Refusing to replace existing campaign database: {p}. Use the existing app database or choose a new path.")
    s=Store(p)
    # Current individual-tab values override stale baseline where known.
    for g in GANGS:
        if g['name']=='Patrol do spraw alkoholu i broni': g.update(credits=325,rating=1115,wealth=1440,updated_at='2026-09-30T18:34:33.926+00:00')
    battles=[{'source_row':i+2,'date':r[0],'scenario':r[1],'attacker':r[2],'defender':r[3],'winner':r[4],'territory':r[5],'territory_claimer':r[6],'notes':None} for i,r in enumerate(BATTLES)]
    territories=[dict(zip(['gang_id','gang_name','territory','card','is_default','ruined'],r)) for r in TERRITORIES]
    lore_text=(ROOT/'data'/'lore'/'C-NINE Story.txt').read_text(encoding='utf-8-sig')
    gang_by_name={g['name']:g for g in GANGS}
    for g in GANGS:
        g['backstory']=''
        g['backstory_source']='not-provided'
    s.db.executemany('''INSERT INTO gangs(gang_id,name,gang_type,player,rating,wealth,credits,reputation,territories,alignment,colour,updated_at,backstory,backstory_source) VALUES(:gang_id,:name,:gang_type,:player,:rating,:wealth,:credits,:reputation,:territories,:alignment,:colour,:updated_at,:backstory,:backstory_source)''',GANGS)
    for t in territories: t['backstory']=territory_backstory(t,battles)
    s.db.executemany('''INSERT INTO territories(gang_id,gang_name,territory,card,is_default,ruined,backstory) VALUES(:gang_id,:gang_name,:territory,:card,:is_default,:ruined,:backstory)''',territories)
    for b in battles: b['chronicle']=battle_chronicle(b)
    s.db.executemany('''INSERT INTO battles(source_row,date,scenario,attacker,defender,winner,territory,territory_claimer,notes,chronicle) VALUES(:source_row,:date,:scenario,:attacker,:defender,:winner,:territory,:territory_claimer,:notes,:chronicle)''',battles)
    fighter_data=json.loads((ROOT/'data'/'fighters.json').read_text(encoding='utf-8'))
    for gang_name,rows in fighter_data.items():
        g=gang_by_name[gang_name]
        for row in rows:
            name,typ,cls,cost,xp,kills,adv,effects,status,notes=row
            f={'gang_id':g['gang_id'],'gang_name':gang_name,'name':name,'type':typ,'class':cls,'cost':cost,'xp':xp,'kills':kills,'advancements':adv,'effects':effects,'status':status,'notes':notes,'backstory':None,'backstory_source':None}
            back,source=fighter_backstory(f,g,battles); f['backstory']=back; f['backstory_source']=source
            cur=s.db.execute('''INSERT INTO fighters(gang_id,gang_name,name,type,class,cost,xp,kills,advancements,effects,status,notes,backstory,backstory_source) VALUES(:gang_id,:gang_name,:name,:type,:class,:cost,:xp,:kills,:advancements,:effects,:status,:notes,:backstory,:backstory_source)''',f); fid=cur.lastrowid
            events=[]
            events.append(('baseline','Baseline imported',f"Campaign baseline: {xp} XP, {kills} kills, status {status}.",'authoritative sheet',1.0))
            if adv: events.append(('advancement','Recorded advancements',adv,'authoritative sheet',1.0))
            if effects: events.append(('effect','Recorded effects and injuries',effects,'authoritative sheet',1.0))
            if status in ('Killed','Retired','Recovery'): events.append(('status','Status changed before baseline',status,'authoritative sheet',1.0))
            for et,title,detail,src,conf in events:
                e=s.db.execute('INSERT INTO fighter_events(fighter_id,event_type,title,detail,event_date,source,confidence) VALUES(?,?,?,?,?,?,?)',(fid,et,title,detail,None,src,conf)); eid=e.lastrowid
                imp=9 if et=='status' and status=='Killed' else (7 if et in ('effect','advancement') else 4)
                s.db.execute('INSERT INTO memories(fighter_id,memory_type,content,importance,source_event_id,source,confidence) VALUES(?,?,?,?,?,?,?)',(fid,'observation',detail,imp,eid,src,conf))
            moods=moodlets(f,g)
            for m in moods:s.db.execute('INSERT INTO moodlets(fighter_id,name,valence,intensity,thought,source) VALUES(?,?,?,?,?,?)',(fid,m['name'],m['valence'],m['intensity'],m['thought'],m['source']))
            for thought in current_thoughts(f,g,moods): s.db.execute('INSERT INTO memories(fighter_id,memory_type,content,importance,source,confidence) VALUES(?,?,?,?,?,?)',(fid,'reflection',thought,5.5,'generated reflection from baseline',0.65))
    s.db.execute('INSERT INTO regions(name,backstory) VALUES(?,?)',('Krakaumunda Contested Sector',region_backstory(GANGS,territories,battles)))
    now=datetime.now(timezone.utc).isoformat()
    for g in GANGS:
        fs=[dict(r) for r in s.db.execute('SELECT * FROM fighters WHERE gang_id=?',(g['gang_id'],))]
        s.db.execute('INSERT INTO downtime_reports(gang_id,gang_name,period_label,report,generated_at) VALUES(?,?,?,?,?)',(g['gang_id'],g['name'],'Current downtime',downtime_report(g,fs,battles),now))
    s.db.execute('INSERT INTO lore_sources(title,source_type,content,source_url) VALUES(?,?,?,?)',('C-NINE Story — both tabs','canonical player-authored lore',lore_text,'https://docs.google.com/document/d/1vAajSzxjaKXjAQ571gcTeM5ocqSVccUS1pljDR_Ysk4'))
    # Campaign-level narrative threads inferred from repeated encounters.
    pairs={}
    for b in battles:
        a,d=b.get('attacker'),b.get('defender')
        if a and d:
            key=tuple(sorted((a,d))); pairs[key]=pairs.get(key,0)+1
    for (a,d),n in sorted(pairs.items(),key=lambda x:-x[1]):
        if n>=2:
            s.db.execute('INSERT INTO narrative_threads(scope_type,scope_key,title,status,summary,evidence_json,updated_at) VALUES(?,?,?,?,?,?,?)',('relationship',f'{a}|{d}',f'{short(a)} / {short(d)} recurring conflict','active',f'{short(a)} and {short(d)} have met in {n} recorded engagements. Repetition has turned contact into history, whether the participants call it rivalry or not.',json.dumps({'encounters':n}),now))
    s.set_state('campaign_name','Dominion Krakaumunda'); s.set_state('campaign_status','Active'); s.set_state('baseline','Snapshot 0001 + narrative seed'); s.set_state('source_mode','authoritative mechanical baseline + canonical C-NINE story + generated narrative layer'); s.set_state('last_sync',now); s.set_state('engine_version','NCCE v0.3 Prototype')
    s.db.execute('INSERT INTO snapshots(captured_at,source_hash,payload_json) VALUES(?,?,?)',(now,None,json.dumps({'baseline':'Snapshot 0001','gangs':len(GANGS),'territories':len(territories),'battles':len(battles),'fighters':sum(len(x) for x in fighter_data.values())})))
    s.db.commit(); s.close(); print('Seeded story engine',p)
if __name__=='__main__':
 import sys; main(sys.argv[1] if len(sys.argv)>1 else 'data/chronicle.db')
