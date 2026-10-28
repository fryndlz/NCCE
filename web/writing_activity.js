'use strict';
window.NCCEWritingActivity = (() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const people = [
    {name:'JuniorWriter',role:'Drafts the prose',kind:'writer'},
    {name:'JKSimmons',role:'Reviews and improves guidance',kind:'critic'},
    {name:'StoryTechMan',role:'Checks context · escalates problems',kind:'tech'}
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
    const status=run?.status || 'idle', technicalWorking=['investigating','repairing','releasing'].includes(run?.tech?.status), working=(status==='running' && a.phase!=='awaiting_reviewer') || technicalWorking;
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
      expression:mood(p),message:working && a.actor===p.name?a.message:messages[p.name]}))};
    view.people=view.people.map(p=>({...p,banter:banter(p)}));return view;
  }
  function graph(run,m) {
    const visited=new Set(run?.visited_steps || []);
    const phase=m.phase;
    const nodes=[['context','NCCE context','Check evidence & sources',20,60],['draft','JuniorWriter','Draft A + draft B',265,60],['review','JKSimmons','Score & diagnose',510,60],['evaluate','Quality gate','Both entries at 8/10?',755,60],['revise','Revise category prompt','Fresh tests; no draft rewrites',265,220],['validation','Fresh-entry validation','Keep the setup unchanged',510,220],['approval','Your decision','Validate, continue or approve',755,220],['escalated','StoryTechMan + you','Pause · investigate context',510,365],['activate','Future NCCE writing','Use the approved setup',755,365]];
    const paths=[['context','draft','M220 95H265'],['draft','review','M465 95H510'],['review','evaluate','M710 95H755'],['evaluate','revise','M855 130V185H365V220'],['revise','context','M265 255H6V95H20'],['evaluate','validation','M855 130V185H610V220'],['validation','approval','M710 255H755'],['review','escalated','M610 130V365'],['approval','activate','M855 290V365']];
    const activeNode=phase==='decision'?'approval':phase==='technical_review'?'escalated':phase==='complete'?(m.status==='approved'?'activate':'approval'):phase==='awaiting_reviewer'?'review':['stopped','budget_exhausted','rejected'].includes(phase)?'escalated':phase;
    const key=run?.run_id?.replace(/[^a-zA-Z0-9]/g,'') || 'idle';
    return `<figure class="writing-flow"><figcaption>How the loop works <span>Current step: ${esc(phase.replaceAll('_',' '))}</span></figcaption><svg viewBox="0 0 980 465" role="img" aria-label="Context flows to two drafts, review and a quality gate. Writing issues loop through revised guidance. Technical issues pause for human input. Passing work needs your approval before activation."><defs><marker id="arrow${key}" markerWidth="9" markerHeight="9" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8"/></marker></defs>
      ${paths.map(([from,to,d])=>`<path d="${d}" class="flow-edge${activeNode===to && (to!=='context' || visited.has('revise'))?' is-current':''}${visited.has(from) && visited.has(to)?' is-visited':''}" marker-end="url(#arrow${key})"/>`).join('')}
      <path d="M855 60V15H120V60" class="flow-edge flow-next${phase==='context' && m.activity.sample===2?' is-current':''}" marker-end="url(#arrow${key})"/>
      <text x="480" y="12" text-anchor="middle" class="flow-label">Next independent entry</text><text x="530" y="176" class="flow-label">Writing needs work · another round</text><text x="873" y="178" class="flow-label">Pass</text><text x="623" y="324" class="flow-label">Context / technical issue</text><text x="28" y="245" class="flow-label">Retest both entries</text>
      ${nodes.map(([id,title,sub,x,y])=>`<g class="flow-node${visited.has(id)?' is-visited':''}${activeNode===id?' is-current':''}${id==='escalated' && m.attention?' needs-human':''}"${activeNode===id?' aria-current="step"':''}><rect x="${x}" y="${y}" width="200" height="70" rx="10"/><text x="${x+100}" y="${y+28}" text-anchor="middle" class="flow-title">${esc(title)}</text><text x="${x+100}" y="${y+50}" text-anchor="middle" class="flow-subtitle">${esc(sub)}</text></g>`).join('')}</svg></figure>`;
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
  function render(run,options={}) {
    const m=model(run,options), dialogue=(run?.dialogue || []).slice(-6);
    return `<section class="writing-control-room" aria-label="Live writing team"><div class="writing-team">${m.people.map(p=>`<article class="writing-agent agent-${p.kind}${p.active?' is-working is-talking':''}${p.attention?' needs-human':''}" data-expression="${p.expression}"><div class="agent-head">${portrait(p.kind,p.expression)}<span class="agent-status-dot" aria-hidden="true"></span></div><div class="agent-identity"><h4>${p.name}</h4><span>${p.active?'Working':p.attention?'Needs you':m.phase==='awaiting_reviewer' && p.name==='JKSimmons'?'Waiting for Codex':'Standing by'} · ${p.role}</span></div><div class="agent-bubble"${p.active || p.attention?' role="status"':''}>${p.banter?`<span class="agent-banter">${esc(p.banter)}</span>`:''}<div class="agent-facts">${handoffText(p.message,260)}</div></div></article>`).join('')}</div>${dialogue.length?handoffs(dialogue):''}${graph(run,m)}</section>`;
  }
  return {render,model};
})();
