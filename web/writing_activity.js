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
  function graph(run,m) {
    const f=workflow(run);
    const card=(id,title,text)=>`<div class="flow-step${f.node===id?' is-current':''}" data-flow-node="${id}"${f.node===id?' aria-current="step"':''}><strong>${title}</strong><p>${text}</p></div>`;
    const arrow='<span class="flow-route-arrow" aria-hidden="true">→</span>';
    const cycle=(items)=>`<div class="flow-sequence">${items.join(arrow)}</div>`;
    return `<figure class="writing-flow" aria-label="Category study workflow"><figcaption>How the loop works <span role="status">${esc(f.label)}</span></figcaption>
      <div class="flow-mode${run?.status==='running'?' is-running':''}" data-flow-mode="${f.mode.toLowerCase()}"><strong>${run?esc(f.mode)+(f.round?' round '+esc(f.round):''):'Learning and validation'}</strong>${f.sample?`<span>Entry ${esc(f.sample)} of 2${run?.activity?.draft?' · draft '+(run.activity.draft===1?'A':'B'):''}</span>`:''}<p>${f.mode==='Validation'?'Validation repeats the full cycle below on fresh entries, with the prompt and editorial reminders unchanged.':'Each learning round tests the same category prompt on two independent entries.'}</p></div>
      ${cycle([card('context','NCCE context','Application checks evidence, sources and configuration.'),card('draft','JuniorWriter','Generate fresh draft A and draft B for this entry.'),card('review','JKSimmons','One Codex review scores both drafts and proposes reusable guidance.'),card('pair','Pair result','After entry 1, repeat for entry 2. Then assess the whole round.')])}
      <p class="flow-repeat">↶ Next independent entry: context → fresh A/B → pair review. A complete round uses <strong>4 writing calls + 2 pair reviews</strong>.</p>
      <p class="flow-technical-exit">A context, technical or permission issue stops the cycle immediately, even on entry 1. Follow the StoryTechMan branch below.</p>
      <h5 class="flow-section-title">After both entries: all four drafts need every score ≥ 8/10 and no blocking issues</h5>
      <div class="flow-outcomes">
        <section><h6>Writing falls short</h6>${card('revise','Revise category prompt','Save JKSimmons’s reusable category instructions. Generate new prose on fresh entries in the next learning round; do not rewrite these drafts.')}<p>↓ Check authorization for another round.</p></section>
        <section><h6>Learning round passes</h6>${card('validation','Prepare fresh-entry validation','Keep the tested prompt and editorial reminders unchanged. Repeat the entire context → drafts → reviews cycle on two fresh entries.')}<p>↓ Check authorization for the validation round.</p></section>
        <section><h6>Validation round passes</h6>${card('approval','You decide: activate or reject','Only your approval activates the exact tested instructions.')}<p class="flow-inline-arrow">↓ If approved</p>${card('activate','Future NCCE writing','Use the approved setup. Existing prose stays unchanged.')}</section>
      </div>
      <p class="flow-validation-failure">Validation falls short → revise the category prompt → learning tests again. Context issues during validation → pause for investigation.</p>
      ${card('allowance','Before another round: check authorization','Rounds remain: continue automatically within your approved limit. None remain: pause for your decision to authorize a complete round, finish with saved findings, or ask StoryTechMan. Missing fresh entries also pauses the study.')}
      <p class="flow-return">↶ Authorized learning or validation returns to the full cycle above. Passing learning alone cannot activate instructions.</p>
      <section class="flow-technical"><h5 class="flow-section-title">Context / technical / permission issue → stop writing</h5>
      ${cycle([card('investigate','1. StoryTechMan investigates','Read-only investigation of saved requests and code; returns an evidence-backed proposal.'),card('proposal','2. You approve the proposal','Approve this exact repair for development and tests, request changes, or reject it.'),card('repair','3. Development and tests','StoryTechMan implements the approved repair and returns a tested report.'),card('release-decision','4. You approve deployment','Separate approval of the exact tested repair is required.'),card('release','5. Deploy and verify','StoryTechMan releases the approved repair and checks it.'),card('new-study','6. Start a new study','Your authorization is required for new writing tests. Repair does not activate writing instructions.')])}
      <p class="flow-return">↶ A new study starts at NCCE context. It must pass learning and fresh-entry validation before your activation decision.</p></section>
      ${card('halt','Paused, stopped or finished','A failure, missing input or your stop decision prevents further writing. Findings remain saved; resolve the reason before starting more work.')}
      <p class="flow-legend">The highlighted box shows the current saved stage. Arrows describe possible routes, not a history of completed transitions. Routine context checks are application code; they do not call the StoryTechMan model.</p>
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
