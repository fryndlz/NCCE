'use strict';
window.NCCEWritingActivity = (() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const people = [
    {name:'JuniorWriter',role:'Drafts the prose',kind:'writer'},
    {name:'JKSimmons',role:'Reviews and improves guidance',kind:'critic'},
    {name:'StoryTechMan',role:'Investigates and repairs the environment',kind:'tech'}
  ];
  function portrait(kind,expression) {
    const tech=kind==='tech', critic=kind==='critic';
    const eyes=expression==='sad'?'<path d="M39 55Q45 52 51 55M63 55Q69 52 75 55" fill="none" stroke="#35383d" stroke-width="2"/>':'<circle cx="45" cy="54" r="3"/><circle cx="69" cy="54" r="3"/>';
    const brows=expression==='angry'?'M37 43L51 49M63 49L77 42':expression==='sad'?'M37 46L51 41M63 41L77 46':critic?'M37 45L51 48M63 48L77 44':'M37 45L51 43M63 43L77 46';
    const mouth=expression==='talking'?'<ellipse class="agent-mouth" cx="57" cy="76" rx="7" ry="6" fill="#68443e"/>':`<path class="agent-mouth" d="${expression==='happy'?'M44 73Q57 88 70 73':expression==='sad'?'M45 82Q57 71 69 82':expression==='angry'?'M44 80Q57 73 70 80':expression==='working'?'M46 77H68':'M47 76Q57 80 67 76'}" fill="none" stroke="#765851" stroke-width="3" stroke-linecap="round"/>`;
    const hair=critic?'<path d="M33 40Q31 16 56 15Q83 17 81 42" fill="#c6aa8e"/>':tech?'':'<path d="M31 47Q26 14 48 18Q72 5 84 45L72 32L62 40L54 28L39 41Z" fill="#4e403b"/>';
    const hood=tech?'<path d="M20 103L24 38Q28 7 56 9Q87 6 91 38L94 111L79 98L78 42Q57 17 35 41L35 96Z" fill="#7c282c"/><path d="M19 106L10 120H104L92 106L74 94H39Z" fill="#7c282c"/>':'';
    const cyber=tech?'<path d="M57 24Q83 25 80 59L74 82L57 87Z" fill="#73817b"/><circle cx="69" cy="51" r="10" fill="#1b2828"/><circle cx="69" cy="51" r="5" fill="#f16e5c"/><path d="M38 72H74V87H38Z" fill="#344642"/><path d="M43 74V84M49 74V84M55 74V84M61 74V84M67 74V84" stroke="#acb4a4" stroke-width="2"/><path d="M35 79Q16 88 28 111M78 79Q98 90 86 114" fill="none" stroke="#b08f5a" stroke-width="5"/>':'';
    return `<svg viewBox="0 0 112 120" class="agent-portrait expression-${expression}" aria-hidden="true"><circle cx="56" cy="56" r="50" class="agent-halo"/><path d="M14 120Q18 91 44 87H70Q96 91 99 120" fill="${tech?'#653033':critic?'#171b21':'#596f85'}"/><path d="M45 77V94L56 104L68 94V77" fill="#bfa088"/>${hood}<ellipse cx="57" cy="54" rx="${critic?27:24}" ry="35" fill="#d7b99b"/>${hair}${eyes}<path d="${brows}" fill="none" stroke="#4c3c36" stroke-width="${critic?4:2}"/><path d="M57 56L54 67H61" fill="none" stroke="#a8836c" stroke-width="2"/>${mouth}${cyber}${kind==='writer'?'<path d="M79 98L91 77L95 80L83 101" fill="#e5c272"/><path d="M37 95L56 112L76 94" fill="none" stroke="#b6bac5" stroke-width="3"/>':''}</svg>`;
  }
  function model(run,options={}) {
    let a=run?.activity || {phase:run?.status==='queued'?'queued':'idle',actor:null,message:''};
    const status=run?.status || 'idle', technicalWorking=['investigating','repairing','releasing'].includes(run?.tech?.status), working=(status==='running' && ['draft','review'].includes(a.phase)) || technicalWorking;
    if(technicalWorking)a={...a,phase:'technical_review',actor:'StoryTechMan',message:run.tech.status==='investigating'?'Inspecting exact saved requests and the generation environment. I will return a proposal before any repair.':run.tech.status==='repairing'?'Implementing and testing the repair you approved. Deployment needs a separate decision.':'Deploying and checking the exact tested repair you approved.'};
    const attention=!technicalWorking && ['escalated','stopped'].includes(status) && !['queued','repair_queued','release_queued'].includes(run?.tech?.status);
    if(['awaiting_next_round','budget_exhausted','awaiting_samples'].includes(status))a={...a,phase:'decision'};
    const messages={
      JuniorWriter:!run?'I’m ready to draft from NCCE’s context once you authorize a run.':run.writer_reserved?'My drafts and exact instructions are saved below. I’m waiting for the next writing step.':'I’m waiting for the checked source context.',
      JKSimmons:!run?'I’ll review both alternatives, score them and distinguish writing issues from missing context.':status==='awaiting_approval'?'All tested drafts passed the target. You decide whether this setup is good enough.':a.phase==='awaiting_reviewer'?'The packet is queued for my actual Codex chat. I am not reviewing until Codex accepts the turn.':run.reviewer_reserved?'The reviews and reusable guidance are saved below.':'I’m waiting for both drafts before reviewing.',
      StoryTechMan:!run?'I check the context and execution. If something is wrong, I stop the loop and bring it to you.':attention || a.phase==='awaiting_reviewer'?a.message:status==='approved'?'The setup you approved is active for future NCCE writing.':status==='awaiting_approval'?'The run has finished. Existing campaign prose is unchanged.':status==='rejected'?'Active instructions are unchanged. We can investigate before another run.':'Context checks and the authorized call limits are in place.'
    };
    const reviews=(run?.rounds || []).flatMap(r=>r.pairs || []).flatMap(p=>p.review?.candidates || []);
    const disappointed=reviews.some(c=>c.overall<8 || Object.values(c.scores || {}).some(s=>s<8));
    const mood=p=>status==='approved' || status==='awaiting_approval'?'happy':p.name==='JuniorWriter' && (attention || a.phase==='revise' || status==='rejected')?'sad':p.name==='JKSimmons' && (a.phase==='revise' || (a.phase==='evaluate' && disappointed) || status==='rejected')?'angry':p.name==='JKSimmons' && a.phase==='evaluate'?'talking':attention && p.name==='StoryTechMan'?'angry':working && a.actor===p.name?'working':'neutral';
    const banter=p=>options.personas===false?'':p.name==='JuniorWriter'?(a.phase==='awaiting_reviewer'?'Uh… both drafts are here, sir. Please go easy.':mood(p)==='sad'?'Right. Okay. I’ll take another pass.':p.active?'Yes. Absolutely. Writing now. I can do this.':'I’ve sharpened the pencil. Twice.'):
      p.name==='JKSimmons'?(mood(p)==='angry'?'Enough fog. Show me a consequence.':p.active?'Evidence first. Adjectives later.':mood(p)==='happy'?'Better. Now let the owner judge it.':'Bring me the pages, not excuses.'):
      attention?'++ ANOMALY DETECTED. Human authorisation required. ++':p.active?'++ Context litany engaged. Verifying the sacred packet. ++':a.phase==='awaiting_reviewer'?'++ Review offering queued. Awaiting the Codex cogitator. ++':'++ Machine-spirit attentive. Awaiting the next rite. ++';
    const view={phase:a.phase,status,working,attention,activity:a,people:people.map(p=>({...p,
      active:working && a.actor===p.name,
      attention:attention && p.name==='StoryTechMan',
      expression:mood(p),message:status==='running' && a.actor===p.name && a.phase!=='context' || technicalWorking && p.name==='StoryTechMan'?a.message:messages[p.name]}))};
    view.people=view.people.map(p=>({...p,banter:banter(p)}));return view;
  }
  function workflow(run) {
    const status=run?.status, phase=run?.activity?.phase, tech=run?.tech?.status;
    const round=run?.rounds?.at(-1), next=status==='queued';
    const validation=next?!!run.validation_pending:round?round.kind==='validation':!!run?.validation_pending;
    const mode=validation?'Validation':'Learning';
    const technical={queued:['investigate','StoryTechMan investigation queued'],investigating:['investigate','StoryTechMan is investigating'],proposal_ready:['proposal','Your decision on the repair proposal'],repair_queued:['repair','Approved development repair queued'],repairing:['repair','StoryTechMan is implementing and testing'],repair_ready:['release-decision','Your decision on deployment'],release_queued:['release','Approved deployment queued'],releasing:['release','StoryTechMan is deploying and verifying'],released:['new-study','Repair released; a new study is required'],needs_input:['halt','StoryTechMan needs your input']};
    let node='',label='No study selected';
    if(technical[tech])[node,label]=technical[tech];
    else if(status==='approved'){node='activate';label='Tested instructions activated';}
    else if(status==='awaiting_approval'){node='approval';label='Validation passed; your activation decision';}
    else if(['awaiting_next_round','budget_exhausted'].includes(status)){node='allowance';label=run.validation_pending?'Your decision: authorize validation or finish':'Your decision: another learning round or finish';}
    else if(['escalated','stopped','awaiting_samples','finished','rejected'].includes(status)){node='halt';label=({escalated:'Writing paused; investigation or input needed',stopped:'Stopped by you',awaiting_samples:'Waiting for fresh source entries',finished:'Study finished; findings saved',rejected:'Setup rejected; active instructions unchanged'})[status];}
    else if(next){node='allowance';label='Authorized round queued';}
    else if(status==='running'){
      const steps={context:['context','NCCE is checking context'],draft:['draft','JuniorWriter is drafting'],awaiting_reviewer:['review','Waiting for JKSimmons'],review:['review','JKSimmons is reviewing'],evaluate:['pair','Checking this pair’s review'],revise:['revise','Saving revised category instructions']};
      [node,label]=steps[phase] || ['', 'Reading saved study status'];
    }
    return {node,label,mode,round:next?(run?.rounds?.length || 0)+1:round?.number || run?.activity?.round,sample:status==='running'?run?.activity?.sample:null};
  }
  function graph(run) {
    const f=workflow(run), technical=['investigate','proposal','repair','release-decision','release','new-study'].includes(f.node);
    const conditions={revise:'Writing falls short',validation:'Learning passes',approval:'Validation passes',allowance:'Before more tests',activate:'If approved'};
    const node=(id,title,text,position='')=>`<div class="flow-step flow-node${f.node===id?' is-current':''}" data-flow-node="${id}"${f.node===id?' aria-current="step"':''}${position?` style="${position}"`:''}><button class="flow-node-button" type="button" aria-describedby="flow-tip-${id}">${conditions[id]?`<span class="flow-mobile-condition">${conditions[id]}</span>`:''}${title}</button><span class="flow-tip" role="tooltip" id="flow-tip-${id}">${text}</span></div>`;
    const paths=['M220 58H273','M473 58H527','M727 58H780','M880 86V116H120V160','M500 116V160','M880 116V160','M120 216V280','M500 216V248H220V280','M120 280H8V58H20','M880 216V280','M880 30V8H120V30'];
    return `<figure class="writing-flow flow-compact" aria-label="Category study workflow"><figcaption>How the loop works <span role="status">${esc(f.label)}</span></figcaption>
      <div class="flow-toolbar"><span class="flow-mode" data-flow-mode="${f.mode.toLowerCase()}">${run?esc(f.mode)+(f.round?' · round '+esc(f.round):''):'Learning / validation'}${f.sample?' · entry '+esc(f.sample)+'/2':''}</span><span>Hover or focus a node for details · tap on mobile</span></div>
      <div class="flow-map">
        <svg class="flow-connectors" viewBox="0 0 1000 356" preserveAspectRatio="none" aria-hidden="true"><defs><marker id="compact-flow-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z"/></marker></defs>${paths.map(d=>`<path class="flow-link" d="${d}" marker-end="url(#compact-flow-arrow)"/>`).join('')}<text x="490" y="18" text-anchor="middle">Repeat for entry 2</text><text x="120" y="146" text-anchor="middle">Writing falls short</text><text x="500" y="146" text-anchor="middle">Learning passes</text><text x="880" y="146" text-anchor="middle">Validation passes</text><text x="880" y="260" text-anchor="middle">If approved</text><text x="340" y="265" text-anchor="middle">Next round</text></svg>
        ${node('context','NCCE context','Application code checks evidence, sources and configuration. Routine checks do not call the StoryTechMan model.','left:2%;top:30px')}
        ${node('draft','JuniorWriter · A/B','Generate two fresh drafts for this entry from the same category prompt. A complete round uses 4 writing calls + 2 pair reviews across two independent entries.','left:27.3%;top:30px')}
        ${node('review','JKSimmons','One Codex review scores both drafts and proposes reusable category guidance. A context, technical or permission issue stops writing immediately, even on entry 1.','left:52.7%;top:30px')}
        ${node('pair','Review gate','Entry 1: repeat context → fresh A/B → review for entry 2. After both entries, all four drafts need every score ≥ 8/10 and no blocking issues. Choose the outcome below.','left:78%;top:30px')}
        ${node('revise','Revise prompt','Writing falls short: save reusable category instructions, then run new learning tests on fresh entries. Validation falls short: return here too. Earlier drafts are not rewritten.','left:2%;top:160px')}
        ${node('validation','Validate on fresh entries','Learning passes: repeat the entire context → drafts → reviews cycle on two fresh entries. Keep the prompt and editorial reminders unchanged. Passing learning alone cannot activate instructions.','left:40%;top:160px')}
        ${node('approval','You approve activation','Validation passes: you may activate or reject the exact tested setup. No model can activate instructions for you.','left:78%;top:160px')}
        ${node('allowance','Authorize next round','Before another round: continue automatically only while authorized rounds remain. Otherwise pause for your choice to authorize a complete round, finish, or investigate. Missing fresh entries also pauses. Authorized learning or validation returns to NCCE context.','left:2%;top:280px')}
        ${node('activate','Future NCCE writing','Use the setup you approved for future writing. Existing prose stays unchanged.','left:78%;top:280px')}
      </div>
      <div class="flow-bottom">${node('halt','Paused / finished','A failure, missing input or your stop decision prevents further writing. Findings stay saved. Resolve the cause before authorizing more work.')}<details class="flow-repair" data-ws-detail="flow-repair"${technical?' open':''}><summary${technical?' class="has-current-stage"':''}>Context / technical issue → StoryTechMan${technical?' · current branch':''}</summary><div class="flow-repair-map">
        ${node('investigate','1 · Investigate','Context, technical or permission issue: stop writing. StoryTechMan inspects saved requests and code read-only, then returns an evidence-backed proposal.')}
        ${node('proposal','2 · Approve proposal','You approve the exact proposal for development and tests, request changes, or reject it. Approval does not authorize deployment.')}
        ${node('repair','3 · Repair &amp; test','StoryTechMan implements your approved repair and returns a tested report. No writer calls or instruction activation.')}
        ${node('release-decision','4 · Approve deployment','Separate approval of the exact tested repair is required before publishing it.')}
        ${node('release','5 · Deploy &amp; verify','StoryTechMan deploys only the approved tested repair and verifies it.')}
        ${node('new-study','6 · New study','Authorize a new study after a systemic repair. Return to context, learning tests and fresh-entry validation. Repair does not activate writing instructions.')}
      </div></details></div>
    </figure>`;
  }
  function handoffText(text,limit=220) {
    text=String(text || '');
    if(text.length<=limit)return `<p>${esc(text)}</p>`;
    return `<details class="ws-disclosure"><summary><span class="ws-closed-title">Read this update</span><span class="ws-open-title">Current update</span></summary><div class="handoff-full">${esc(text)}</div></details>`;
  }
  function handoffs(dialogue) {
    const labels={context:'Checking context',draft:'Generating fresh drafts',awaiting_reviewer:'Draft pair ready for review',review:'Reviewing category results',evaluate:'Review result',revise:'Reusable category prompt updated',escalated:'Generation setup needs investigation',decision:'Choose the next step',approval:'Validation passed · your approval',complete:'Complete',budget_exhausted:'Test batch complete'};
    return `<details class="agent-dialogue" open><summary>Team handoffs <span>${dialogue.length} recent updates</span></summary><ol class="handoff-list">${dialogue.map(d=>`<li class="handoff-card${d.phase==='escalated'?' needs-human':''}"><header><strong>${esc(d.from)} <span aria-hidden="true">→</span> ${esc(d.to)}</strong></header>${d.text.length>180?`<details class="ws-disclosure" data-ws-detail="${esc('handoff-'+d.at+'-'+d.phase)}"><summary><span class="ws-closed-title">${esc(labels[d.phase] || 'Team update')}</span><span class="ws-open-title">Full handoff</span><small class="ws-disclosure-hint">Show details</small></summary><div class="handoff-full">${esc(d.text)}</div></details>`:`<span class="handoff-phase">${esc(labels[d.phase] || 'Update')}</span><p>${esc(d.text)}</p>`}</li>`).join('')}</ol></details>`;
  }
  function eventWindow(run,m,dialogue) {
    const actor=m.people.find(p=>p.active && ['JKSimmons','StoryTechMan'].includes(p.name));
    const queuedTech=['queued','repair_queued','release_queued'].includes(run?.tech?.status);
    const waiting=(run?.status==='running' && m.phase==='awaiting_reviewer') || queuedTech;
    let current='';
    if(actor){
      const action=actor.name==='JKSimmons'?'Reviewing the drafts and category setup':run?.tech?.status==='investigating'?'Investigating the generation environment':run?.tech?.status==='repairing'?'Implementing and testing your approved repair':run?.tech?.status==='releasing'?'Deploying and verifying your approved repair':'Checking NCCE context';
      current=`<div class="agent-live-event" role="status" aria-live="polite" data-working-agent="${actor.name}"><span class="agent-work-spinner" aria-hidden="true"></span><div><strong>${actor.name} is working</strong><p>${action}. Please wait…</p></div></div>`;
    }else if(waiting){current=`<div class="agent-queued-event" role="status"><span aria-hidden="true">◷</span><p>Waiting for ${queuedTech?'StoryTechMan':'JKSimmons'} to begin. This view updates automatically.</p></div>`;}
    if(!current && !dialogue.length)return '';
    return `<section class="agent-event-window" aria-label="Agent activity">${current}${dialogue.length?handoffs(dialogue):''}</section>`;
  }
  function render(run,options={}) {
    const m=model(run,options), dialogue=(run?.dialogue || []).slice(-6);
    return `<section class="writing-control-room" aria-label="Live writing team"><div class="writing-team">${m.people.map(p=>`<article class="writing-agent agent-${p.kind}${p.active?' is-working is-talking':''}${p.attention?' needs-human':''}" data-expression="${p.expression}"><div class="agent-head">${portrait(p.kind,p.expression)}<span class="agent-status-dot" aria-hidden="true"></span></div><div class="agent-identity"><h4>${p.name}</h4><span>${p.active?'Working':p.attention?'Needs you':m.phase==='awaiting_reviewer' && p.name==='JKSimmons'?'Waiting for Codex':'Standing by'} · ${p.role}</span></div><div class="agent-bubble"${p.active || p.attention?' role="status"':''}>${p.banter?`<span class="agent-banter">${esc(p.banter)}</span>`:''}<div class="agent-facts">${handoffText(p.message,260)}</div></div></article>`).join('')}</div>${eventWindow(run,m,dialogue)}${graph(run,m)}</section>`;
  }
  return {render,model,workflow};
})();
