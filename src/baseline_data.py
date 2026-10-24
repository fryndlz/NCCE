from datetime import datetime, timezone
from store import Store

GANGS = [
 {'gang_id':'54c12f10-d265-4ab7-9aba-0f904ef87cc7','name':'Patrol do spraw alkoholu i broni','gang_type':'Palanite Enforcers','player':'Krowen','rating':1590,'wealth':1755,'credits':165,'reputation':2,'territories':2,'alignment':'Law Abiding','colour':None,'updated_at':None},
 {'gang_id':'148e09b0-08d7-4118-affe-d9aac580fb44','name':'The Slag Eaters','gang_type':'House Orlock','player':'Fr4gtastic','rating':2910,'wealth':2931,'credits':11,'reputation':6,'territories':4,'alignment':'Law Abiding','colour':'#0000cc','updated_at':'2026-10-20T19:45:00.069+00:00'},
 {'gang_id':'b5a33a07-6010-4eb1-a983-4a8ecf16c64f','name':'THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','gang_type':'Genestealer Cults','player':'Baruch','rating':2630,'wealth':2630,'credits':0,'reputation':9,'territories':5,'alignment':'Outlaw','colour':'#d337ff','updated_at':'2026-09-25T19:23:39.527+00:00'},
 {'gang_id':'e1779be9-8505-4604-ad61-b7c3d2020d6c','name':'Kły Sprawiedliwości','gang_type':'Palanite Enforcers','player':'Logan_Grey_One','rating':2725,'wealth':2961,'credits':231,'reputation':3,'territories':1,'alignment':'Law Abiding','colour':None,'updated_at':'2026-10-20T18:57:34.569+00:00'},
 {'gang_id':'d3b71b68-8f5e-41bb-a147-b89984ca3061','name':'Ethernetans 2.0','gang_type':'House Van Saar','player':'Necromundziarz','rating':3745,'wealth':4302,'credits':197,'reputation':21,'territories':9,'alignment':'Law Abiding','colour':'#50e6fa','updated_at':'2026-10-19T08:29:23.963+00:00'},
 {'gang_id':'f63248ad-3b78-45d7-b3c2-817eea55f4b6','name':'Helmaeth Expeditionary Force','gang_type':'Ironhead Squat Prospectors','player':'Zakarin','rating':3010,'wealth':3110,'credits':100,'reputation':4,'territories':3,'alignment':'Law Abiding','colour':'#00c524','updated_at':'2026-10-14T08:18:20.321+00:00'},
]
TERRITORIES = [
 ('54c12f10-d265-4ab7-9aba-0f904ef87cc7','Patrol do spraw alkoholu i broni','Palanite Precinct','',1,0),('54c12f10-d265-4ab7-9aba-0f904ef87cc7','Patrol do spraw alkoholu i broni','Smelting Works','7♠️',0,0),
 ('148e09b0-08d7-4118-affe-d9aac580fb44','The Slag Eaters','Generatorium','J♠️',0,0),('148e09b0-08d7-4118-affe-d9aac580fb44','The Slag Eaters','Refuse Drift','9♦️',0,0),('148e09b0-08d7-4118-affe-d9aac580fb44','The Slag Eaters','Settlement','A♦️',1,0),('148e09b0-08d7-4118-affe-d9aac580fb44','The Slag Eaters','Settlement','A♦️',0,0),
 ('b5a33a07-6010-4eb1-a983-4a8ecf16c64f','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Old Ruins','2♦️',0,0),('b5a33a07-6010-4eb1-a983-4a8ecf16c64f','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Toll Crossing','10♠️',0,0),('b5a33a07-6010-4eb1-a983-4a8ecf16c64f','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Settlement','A♦️',1,0),('b5a33a07-6010-4eb1-a983-4a8ecf16c64f','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Promethium Cache','4♦️',0,0),('b5a33a07-6010-4eb1-a983-4a8ecf16c64f','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Sludge Sea','6♦️',0,0),
 ('e1779be9-8505-4604-ad61-b7c3d2020d6c','Kły Sprawiedliwości','Palanite Precinct','',1,0),
 ('d3b71b68-8f5e-41bb-a147-b89984ca3061','Ethernetans 2.0','Settlement','A♠️',1,0),('d3b71b68-8f5e-41bb-a147-b89984ca3061','Ethernetans 2.0','Mine Workings','8♠️',0,0),('d3b71b68-8f5e-41bb-a147-b89984ca3061','Ethernetans 2.0','Settlement','A♦️',0,0),('d3b71b68-8f5e-41bb-a147-b89984ca3061','Ethernetans 2.0','Collapsed Dome','8♦️',0,0),('d3b71b68-8f5e-41bb-a147-b89984ca3061','Ethernetans 2.0','Wastes','5♦️',0,0),('d3b71b68-8f5e-41bb-a147-b89984ca3061','Ethernetans 2.0','Needle Ways','A♠️',0,0),('d3b71b68-8f5e-41bb-a147-b89984ca3061','Ethernetans 2.0','Bone Shrine','J♦️',0,0),('d3b71b68-8f5e-41bb-a147-b89984ca3061','Ethernetans 2.0','Synth Still','2♠️',0,0),('d3b71b68-8f5e-41bb-a147-b89984ca3061','Ethernetans 2.0','Drinking Hole','Q♦️',0,0),
 ('f63248ad-3b78-45d7-b3c2-817eea55f4b6','Helmaeth Expeditionary Force','Stinger Mould Sprawl','3♠️',0,0),('f63248ad-3b78-45d7-b3c2-817eea55f4b6','Helmaeth Expeditionary Force','Corpse Farm','10♦️',0,0),('f63248ad-3b78-45d7-b3c2-817eea55f4b6','Helmaeth Expeditionary Force','Settlement','A♦️',1,0),
]
BATTLES = [
 ('2026-10-20T17:05:47.940573+00:00','The Trap','The Slag Eaters','Kły Sprawiedliwości','The Slag Eaters','Settlement','The Slag Eaters'),
 ('2026-10-17T15:14:28.010779+00:00','Asset Seizure',None,'Kły Sprawiedliwości','Ethernetans 2.0','Drinking Hole','Ethernetans 2.0'),
 ('2026-10-13T16:55:58.79772+00:00','Road Block','Helmaeth Expeditionary Force','The Slag Eaters','The Slag Eaters',None,'The Slag Eaters'),
 ('2026-10-11T17:11:34.881763+00:00','Murder Cyborg','Patrol do spraw alkoholu i broni','Ethernetans 2.0','Ethernetans 2.0',None,'Ethernetans 2.0'),
 ('2026-09-29T22:00:00+00:00','Pit Fight','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Patrol do spraw alkoholu i broni','Helmaeth Expeditionary Force',None,'Helmaeth Expeditionary Force'),
 ('2026-09-29T22:00:00+00:00','Shootout','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Patrol do spraw alkoholu i broni','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]',None,'THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]'),
 ('2026-09-22T16:45:27.005819+00:00','Pit Fight',None,None,'Helmaeth Expeditionary Force',None,'Helmaeth Expeditionary Force'),
 ('2026-09-21T16:21:58.943905+00:00','Border Dispute','Helmaeth Expeditionary Force',None,'Ethernetans 2.0','Synth Still','Ethernetans 2.0'),
 ('2026-09-19T15:47:57.015023+00:00','Takeover','The Slag Eaters','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Sludge Sea','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]'),
 ('2026-09-16T16:54:31.87042+00:00','Takeover','Kły Sprawiedliwości','Helmaeth Expeditionary Force','Helmaeth Expeditionary Force','Corpse Farm','Helmaeth Expeditionary Force'),
 ('2026-09-13T22:00:00+00:00','Escort Mission','Helmaeth Expeditionary Force','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Old Ruins','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]'),
 ('2026-09-11T17:21:42.879906+00:00','Border Dispute','The Slag Eaters','Patrol do spraw alkoholu i broni','The Slag Eaters','Refuse Drift','The Slag Eaters'),
 ('2026-09-08T17:11:26.561398+00:00','Asset Seizure','Patrol do spraw alkoholu i broni','Kły Sprawiedliwości','Patrol do spraw alkoholu i broni','Smelting Works','Patrol do spraw alkoholu i broni'),
 ('2026-09-07T16:59:59.900716+00:00','Smash & Grab','Ethernetans 2.0','The Slag Eaters','Ethernetans 2.0','Wastes','Ethernetans 2.0'),
 ('2026-08-31T22:00:00+00:00','The Trap','Patrol do spraw alkoholu i broni','Ethernetans 2.0','Ethernetans 2.0','Collapsed Dome','Ethernetans 2.0'),
 ('2026-08-30T22:00:00+00:00','Takeover','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Kły Sprawiedliwości','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Promethium Cache','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]'),
 ('2026-08-30T11:51:58.814843+00:00','Smash & Grab','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Ethernetans 2.0','Ethernetans 2.0','Mine Workings','Ethernetans 2.0'),
 ('2026-08-19T16:38:08.773425+00:00','Smash & Grab','Kły Sprawiedliwości','The Slag Eaters','Kły Sprawiedliwości','Drinking Hole','Kły Sprawiedliwości'),
 ('2026-08-17T17:29:26.011185+00:00','The Trap','Ethernetans 2.0','Kły Sprawiedliwości','Ethernetans 2.0','Needle Ways','Ethernetans 2.0'),
 ('2026-08-10T16:16:37.936655+00:00','Smash & Grab','The Slag Eaters','Helmaeth Expeditionary Force','Helmaeth Expeditionary Force','Stinger Mould Sprawl','Helmaeth Expeditionary Force'),
 ('2026-08-07T09:18:39.789998+00:00','Border Dispute','Helmaeth Expeditionary Force','Kły Sprawiedliwości','Kły Sprawiedliwości','Settlement','Kły Sprawiedliwości'),
 ('2026-08-03T16:23:54.872785+00:00','Smash & Grab','Kły Sprawiedliwości','The Slag Eaters','The Slag Eaters','Generatorium','The Slag Eaters'),
 ('2026-07-29T22:00:00+00:00','Smash & Grab','Helmaeth Expeditionary Force','Ethernetans 2.0','Ethernetans 2.0','Settlement','Ethernetans 2.0'),
 ('2026-07-26T22:00:00+00:00','The Trap','The Slag Eaters','Ethernetans 2.0','Ethernetans 2.0','Bone Shrine','Ethernetans 2.0'),
 ('2026-07-22T22:00:00+00:00','Border Dispute','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Kły Sprawiedliwości','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','Toll Crossing','THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]'),
]

def main(path):
    s=Store(path)
    s.replace_gangs(GANGS)
    s.replace_territories([dict(zip(['gang_id','gang_name','territory','card','is_default','ruined'],r)) for r in TERRITORIES])
    s.replace_battles([{'source_row':i+2,'date':r[0],'scenario':r[1],'attacker':r[2],'defender':r[3],'winner':r[4],'territory':r[5],'territory_claimer':r[6],'notes':None} for i,r in enumerate(BATTLES)])
    s.set_state('campaign_name','Dominion Krakaumunda')
    s.set_state('campaign_status','Active')
    s.set_state('baseline','Snapshot 0001')
    s.set_state('source_mode','seeded from authoritative Google Sheet; live adapter pending authorization')
    s.set_state('last_sync',datetime.now(timezone.utc).isoformat())
    s.save_snapshot(datetime.now(timezone.utc).isoformat(), {'baseline':'Snapshot 0001','gangs':GANGS,'territories':len(TERRITORIES),'battles':len(BATTLES)})
    print(f'Seeded {len(GANGS)} gangs, {len(TERRITORIES)} territories, {len(BATTLES)} battles into {path}')

if __name__=='__main__':
    import sys; main(sys.argv[1] if len(sys.argv)>1 else 'data/chronicle.db')
