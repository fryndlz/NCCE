"""Experimental prompt only. Production contract remains unchanged pending review."""
from pathlib import Path
import writer_contract

REVISION='editorial-selection-v1'
PATH=Path(__file__).resolve().parents[1]/'docs/writing_sources/WRITER_EDITORIAL_CANDIDATE.md'

PERSONAL='''ILLUSTRATIVE STYLE DEMONSTRATION — fictional repair worker, not campaign evidence.
Fact: serious injury; no mechanism or anatomical diagnosis known.
I can hear the press from the infirmary. Three strokes, a pause, then the bad bearing starts to scream. Whoever has my shift keeps feeding it anyway. I told the orderly to fetch my apprentice. She brought me another cup of broth.
The work matters to this person. Sound, frustration and the orderly's response develop that concern without inventing a battlefield cause. Do not transplant the press, apprentice or infirmary to another subject.'''

COLLECTIVE='''ILLUSTRATIVE STYLE DEMONSTRATION — fictional gang, not campaign evidence.
Fact: the Brass Widows have lost a toll bridge. No casualties or individual attendance recorded.
Heading: BRASS WIDOWS — HOUSE ACCOUNT
Subject: The river road
The collectors' benches have been brought in from the bridge and set along the supper table. Their boots still carry the white dust of the road. Nobody has asked them to scrape it off.
For twelve years the Widows made travellers uncover their faces before crossing. Now their own families take the long route through the drainage works. At supper, the youngest collector asked whether the rule would still apply when they went home.
Closing label: HOUSE INSTRUCTION
Closing: Bring the children through together.
Ownership loss changes a gang's ordinary life. The familiar rule acquires a consequence, and the closing responds to it. This supplies no invented attack, casualty, game-credit change or formal faction relationship. Do not reuse these objects or incidents.'''

def contract(form):
    original=writer_contract.RUNTIME_PATH.read_text(encoding='utf-8-sig')
    authority=original.split('## Voice and craft')[0]
    presentation='## Context and presentation'+original.split('## Context and presentation',1)[1]
    if form in writer_contract.PERSONAL:
        examples=PERSONAL
    elif form=='fighter_biography':
        examples=writer_contract.PERSONNEL_EXAMPLE
    elif form.startswith('territory') or form.startswith('place_'):
        examples=writer_contract.DOCUMENT_EXAMPLE+'\n\n'+writer_contract.EVENT_EXAMPLE
    else:
        examples=COLLECTIVE
    return authority+'\n'+PATH.read_text(encoding='utf-8-sig')+'\n'+presentation+'\n'+examples+'\nREQUESTED FORM: '+form+'\n'+writer_contract.BRIEFS[form]
