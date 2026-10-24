from __future__ import annotations
import re
from collections import Counter

C9='THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]'

def short(name):
    return 'C-NINE' if name==C9 else (name or 'Unknown')

def clean_effects(text):
    return [x.strip() for x in re.split(r'[;\n]+', text or '') if x.strip()]

def gang_record(name,battles):
    bs=[b for b in battles if name in (b.get('attacker'),b.get('defender')) or name==b.get('winner') or name==b.get('territory_claimer')]
    wins=sum(1 for b in bs if b.get('winner')==name)
    losses=sum(1 for b in bs if b.get('winner') and b.get('winner')!=name and name in (b.get('attacker'),b.get('defender')))
    foes=Counter()
    for b in bs:
        for x in (b.get('attacker'),b.get('defender')):
            if x and x!=name: foes[x]+=1
    rival=foes.most_common(1)[0][0] if foes else None
    return bs,wins,losses,rival

def generated_gang_backstory(g,battles,territories):
    name=g['name']; bs,w,l,rival=gang_record(name,battles)
    holds=[t['territory'] for t in territories if t['gang_name']==name]
    arche={
      'House Orlock':'an Orlock road crew whose authority has grown out of hard travel, salvage, violence and the practical loyalty of people who expect machinery and comrades to survive together',
      'Palanite Enforcers':'a Palanite precinct detail trying to convert legal authority into actual control over a district where warrants matter less than who still has boots on the ground',
      'House Van Saar':'a Van Saar technical enclave whose expansion is built on superior equipment, information control and the quiet assumption that every useful system can eventually be made theirs',
      'Ironhead Squat Prospectors':'an Ironhead prospecting charter treating the underhive as both claim and inheritance, measuring success in recoverable assets, grudges honoured and ground held',
      'Genestealer Cults':'an old hereditary deep-work detail whose industrial identity conceals a far older and stranger solidarity'
    }.get(g.get('gang_type'),'an underhive gang whose identity is being written by the territory it holds and the enemies it survives')
    trend='has so far won more recorded engagements than it has lost' if w>l else ('has absorbed more defeats than victories without disappearing' if l>w else 'has an even recorded history of victories and reversals')
    rival_txt=f" Repeated contact with {short(rival)} is beginning to look less like coincidence and more like a relationship." if rival else ''
    hold_txt=', '.join(holds[:4]) if holds else 'no stable holdings beyond its base'
    return f"{short(name)} is {arche}. Across {len(bs)} recorded engagements it {trend}. Its current footprint includes {hold_txt}.{rival_txt} This biography is inferred from campaign state and will be rewritten as new events accumulate."

def territory_backstory(t,battles):
    name=t['territory']; owner=t['gang_name']
    flavor={
      'Toll Crossing':'A choke point made valuable by movement rather than shelter. Whoever controls it can tax, delay, search or simply remember who passed through.',
      'Old Ruins':'A dead layer of the hive whose useful contents have been picked over so many times that every new discovery implies somebody missed something important.',
      'Promethium Cache':'A fuel reserve is never merely storage in the underhive. It is heat, light, leverage and the promise of a very large fire.',
      'Sludge Sea':'An industrial basin where the surface shifts, the air burns the throat and routes exist only as long as somebody remembers them.',
      'Mine Workings':'Worked ground threaded with extraction routes, abandoned cuts and machinery whose ownership is easier to contest than its purpose.',
      'Settlement':'A pocket of civilian life surviving because enough armed people currently agree that it should.',
      'Generatorium':'Power means bargaining power. Every cable leaving this place is a dependency somebody can threaten.',
      'Refuse Drift':'Generations of industrial waste have become geography, economy and cover in equal measure.',
      'Smelting Works':'Heat, metal and labour turn salvage into useful material here, making the works valuable to anyone planning to remain in the district.',
      'Collapsed Dome':'A failed civic space turned into a maze of broken structure, unstable routes and defensible pockets.',
      'Wastes':'Ground defined less by what it contains than by what it separates. Crossing it safely is its own resource.',
      'Needle Ways':'Vertical routes and narrow connections make the Ways a network of ambush points disguised as infrastructure.',
      'Bone Shrine':'A place where memory, superstition and territorial ownership have become difficult to separate.',
      'Synth Still':'A production site whose output buys loyalty one measure at a time.',
      'Drinking Hole':'Neutral ground only until somebody decides it is not.',
      'Stinger Mould Sprawl':'A living industrial nuisance turned resource field, dangerous enough to discourage casual trespass.',
      'Corpse Farm':'A grimly efficient recycling site where the hive converts its dead back into inputs.'
    }.get(name, f'{name} is one of the district assets around which local movement, income and violence have accumulated.')
    related=[b for b in battles if b.get('territory')==name]
    hist=''
    if related:
        last=related[-1]
        hist=f" Recorded fighting has directly decided its ownership {len(related)} time(s); the latest claim in the ledger belongs to {short(last.get('territory_claimer') or owner)}."
    return f"{flavor}{hist} Current holder: {short(owner)}."

def region_backstory(gangs,territories,battles):
    top=max(gangs,key=lambda g:g.get('reputation') or 0)
    contested=Counter(b.get('territory') for b in battles if b.get('territory'))
    hot=contested.most_common(3)
    hot_txt=', '.join(x for x,_ in hot) if hot else 'the principal transit routes'
    return (f"The Krakaumunda campaign sector is not a coherent district so much as a web of claims around salvage, transit, fuel, habitation and old industrial infrastructure. "
            f"The strongest public reputation currently belongs to {short(top['name'])}, but reputation does not map cleanly to safety or legitimacy. "
            f"The most repeatedly consequential ground includes {hot_txt}. Every battle changes more than ownership: it changes who is feared, who is owed, which routes feel safe, and which stories the inhabitants tell about the gangs moving through them.")

def fighter_backstory(f, gang, battles):
    if f.get('backstory'): return f['backstory'], f.get('backstory_source','player-authored')
    bs,w,l,rival=gang_record(gang['name'],battles)
    cls=f.get('class') or 'fighter'; typ=f.get('type') or 'fighter'; kills=f.get('kills') or 0; xp=f.get('xp') or 0
    effects=clean_effects(f.get('effects'))
    status=f.get('status') or 'Active'
    role={'Leader':'carries the burden of decisions that other people get to call orders','Champion':'has survived long enough to be watched by both juniors and rivals','Ganger':'is one of the bodies on which the gang actually depends','Juve':'is still close enough to the bottom that every survival changes how the others see them','Prospect':'has made risk part of the job description','Specialist':'has become useful for something the gang cannot easily replace','Brute':'is treated as an asset until the moment an asset starts acquiring a reputation','Hanger-on':'lives beside the gang rather than fully inside it','Exotic Beast':'is recorded as equipment by people who have never had to live beside it'}.get(cls,'has found a place in the gang that campaign bookkeeping only partially explains')
    combat='has not yet been credited with a kill' if kills==0 else (f'has {kills} confirmed kill in the ledger' if kills==1 else f'has {kills} confirmed kills in the ledger')
    scar=''
    if effects: scar=f" The record already carries consequences: {', '.join(effects[:4])}."
    end=' Their story is currently closed.' if status=='Killed' else (' They are no longer active, but remain part of the gang\'s history.' if status=='Retired' else '')
    return (f"{f['name']} serves as a {typ} and {role}. At the current baseline they have {xp} XP and {combat}.{scar} "
            f"Nothing more personal was supplied by the player, so this origin is intentionally inferred from role, scars and campaign context rather than treated as hidden canon.{end}"), 'mechanically-inferred'

def moodlets(f, gang):
    out=[]; effects=' '.join(clean_effects(f.get('effects'))).lower(); status=(f.get('status') or '').lower(); kills=f.get('kills') or 0
    def add(name,valence,intensity,thought,source): out.append({'name':name,'valence':valence,'intensity':intensity,'thought':thought,'source':source})
    if status=='killed': return [{'name':'Dead','valence':-1,'intensity':100,'thought':'No current thoughts are generated. The character remains in other people’s memories.','source':'status'}]
    if 'recovery' in status or 'convalescence' in effects: add('Recovering',-1,58,'Time away from the line is safety bought with the knowledge that the gang is moving without me.','status/effects')
    if any(x in effects for x in ['hobbled','spinal','hand injury','eye injury','enfeebled','head injury']): add('Marked by injury',-1,48,'The body remembers the campaign even when the roster reduces it to a line of text.','injury')
    if 'humiliated' in effects: add('Humiliated',-1,62,'Someone saw me fail. The next chance to correct that matters more than it should.','injury')
    if 'bitter enmity' in effects: add('Grudge',-1,72,'There is a name attached to this anger, even if the campaign record has not preserved it cleanly.','injury')
    if 'horrid scars' in effects or 'impressive scars' in effects: add('Scarred reputation',0.2,45,'People look twice now. That can be useful.','injury')
    if kills>=5: add('Proven killer',0.5,min(80,40+kills*3),'I know what happens when the shooting starts, and so do the others.','kills')
    elif kills>0: add('Blooded',0.2,35,'I have crossed the line between carrying a weapon and knowing what it does to someone.','kills')
    if f.get('class')=='Leader': add('Responsibility',-0.1,55,'Every loss becomes an argument about the last order I gave.','class')
    if f.get('class')=='Juve': add('Ambition',0.35,45,'Every veteran started somewhere. Surviving long enough to be noticed is the first promotion.','class')
    if gang['name']==C9: add('Crew',0.65,65,'The Crew is not company. It is the measure by which distance, danger and self are understood.','canonical C-NINE lore')
    if not out: add('Watchful',0,25,'Nothing is settled. That is normal.','baseline')
    return out[:5]

def current_thoughts(f, gang, moods):
    thoughts=[m['thought'] for m in sorted(moods,key=lambda x:x['intensity'],reverse=True)[:3]]
    if f.get('advancements'):
        thoughts.append('I am not the same fighter who entered the campaign; the changes are visible in what I can now do.')
    if gang['name']==C9 and 'Voss' in f['name']:
        thoughts.append('The Prospect is complete. The work beneath it is not.')
    return thoughts[:4]

def battle_chronicle(b):
    a=short(b.get('attacker')); d=short(b.get('defender')); w=short(b.get('winner')); sc=b.get('scenario') or 'engagement'; terr=b.get('territory')
    if a=='Unknown' and d=='Unknown': parties='The surviving records do not preserve both parties cleanly.'
    else: parties=f"{a} and {d} met in a {sc.lower()} that ended in favour of {w}."
    consequence=f" Control of {terr} was part of the consequence." if terr else ''
    return parties+consequence+" The chronicle treats this as a factual anchor; character motives and private moments are generated separately from the people and histories involved."

def downtime_report(g, fighters, battles):
    bs,w,l,rival=gang_record(g['name'],battles)
    latest=bs[-1] if bs else None
    rec=[f['name'] for f in fighters if (f.get('status') or '').lower()=='recovery' or 'convalescence' in (f.get('effects') or '').lower()]
    dead=[f['name'] for f in fighters if (f.get('status') or '').lower()=='killed']
    scarred=[f['name'] for f in fighters if any(k in (f.get('effects') or '').lower() for k in ['injury','hobbled','scar','enmity','enfeebled'])]
    parts=[]
    if latest: parts.append(f"After {latest.get('scenario')}, the gang returned from an engagement recorded as a {'victory' if latest.get('winner')==g['name'] else 'setback'}.")
    if rec: parts.append(f"{', '.join(rec[:4])} spend the interval recovering rather than returning immediately to full duty.")
    if dead: parts.append(f"The names of {', '.join(dead[:4])} remain in the ledger after death; their absence is now part of the gang's internal geography.")
    if scarred: parts.append(f"The campaign has left visible marks across the roster, notably {', '.join(scarred[:5])}.")
    if not parts: parts.append('The interval passes without a major recorded casualty event, which in the underhive is itself a temporary kind of good fortune.')
    if g['name']==C9: parts.append('Within C-NINE, repairs, medical work and survey preparation are treated as one continuous labour cycle. Nobody describes the interval as rest.')
    return ' '.join(parts)
