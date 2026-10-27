'use strict';
window.NCCEWritingActivity = (() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const people = [
    {name:'JuniorWriter',role:'Drafts the prose',kind:'writer'},
    {name:'JKSimmons',role:'Reviews and improves guidance',kind:'critic'},
    {name:'StoryTechMan',role:'Checks context · escalates problems',kind:'tech'}
  ];
  function portrait(kind) {
    const hair = kind==='writer'?'<path d="M34 46Q27 15 49 18Q72 8 81 44L70 34L62 39L54 29L40 40Z" fill="#434b56"/>':kind==='critic'?'<path d="M35 42Q34 17 57 18Q78 19 79 43" fill="#c8ae92"/><path d="M43 80L56 87L68 80L63 94L50 94Z" fill="#61616b"/>':'<path d="M31 45V24L45 17H73L82 28V45Z" fill="#67756b"/><path d="M39 22V15M73 22V15" stroke="#b4d8ae" stroke-width="4"/>';
    const eyes = kind==='tech'?'<rect x="34" y="42" width="45" height="18" rx="7" fill="#24332e"/><circle cx="45" cy="51" r="4" fill="#b5edb2"/><circle cx="68" cy="51" r="4" fill="#b5edb2"/>':kind==='critic'?'<path d="M38 47L50 49M63 49L75 46" stroke="#3c3942" stroke-width="3"/><circle cx="45" cy="56" r="3"/><circle cx="68" cy="56" r="3"/>':'<circle cx="44" cy="52" r="3"/><circle cx="68" cy="52" r="3"/><path d="M36 44L48 43M63 43L75 46" stroke="#434b56" stroke-width="3"/>';
    return `<svg viewBox="0 0 112 120" class="agent-portrait" aria-hidden="true"><circle cx="56" cy="56" r="50" class="agent-halo"/><path d="M18 120Q18 91 45 88H68Q94 91 94 120" fill="${kind==='writer'?'#59728a':kind==='critic'?'#635a70':'#526951'}"/><path d="M46 77V93L56 102L67 93V77" fill="#c0a48b"/><ellipse cx="56" cy="54" rx="25" ry="34" fill="#dac1a5"/>${hair}${eyes}<path d="M57 56L54 67H61" fill="none" stroke="#ae8e74" stroke-width="2"/><path class="agent-mouth" d="M47 76Q56 80 66 75" fill="none" stroke="#765851" stroke-width="3" stroke-linecap="round"/>${kind==='writer'?'<path d="M79 98L91 77L95 80L83 101" fill="#e5c272"/>':''}</svg>`;
  }
  function model(run) {
    const a=run?.activity || {phase:run?.status==='queued'?'queued':'idle',actor:null,message:''};
    const status=run?.status || 'idle', working=status==='running';
    const attention=['escalated','budget_exhausted','stopped'].includes(status);
    const messages={
      JuniorWriter:!run?'I’m ready to draft from NCCE’s context once you authorize a run.':run.writer_reserved?'My drafts and exact instructions are saved below. I’m waiting for the next writing step.':'I’m waiting for the checked source context.',
      JKSimmons:!run?'I’ll review both alternatives, score them and distinguish writing issues from missing context.':status==='awaiting_approval'?'All tested drafts passed the target. You decide whether this setup is good enough.':run.reviewer_reserved?'The reviews and reusable guidance are saved below.':'I’m waiting for both drafts before reviewing.',
      StoryTechMan:!run?'I check the context and execution. If something is wrong, I stop the loop and bring it to you.':attention?a.message:status==='approved'?'The setup you approved is active for future NCCE writing.':status==='awaiting_approval'?'The run has finished. Existing campaign prose is unchanged.':status==='rejected'?'Active instructions are unchanged. We can investigate before another run.':'Context checks and the authorized call limits are in place.'
    };
    return {phase:a.phase,status,working,attention,activity:a,people:people.map(p=>({...p,
      active:working && a.actor===p.name,
      attention:attention && p.name==='StoryTechMan',
      message:working && a.actor===p.name?a.message:messages[p.name]}))};
  }
  function graph(run,m) {
    const visited=new Set(run?.visited_steps || []);
    const phase=m.phase;
    const nodes=[['context','NCCE context','Check evidence & sources',20,60],['draft','JuniorWriter','Draft A + draft B',265,60],['review','JKSimmons','Score & diagnose',510,60],['evaluate','Quality gate','Both entries at 8/10?',755,60],['revise','Revise guidance','Save an inactive candidate',265,220],['approval','Your approval','Inspect results & prompts',755,220],['escalated','StoryTechMan + you','Pause · investigate context',510,365],['activate','Future NCCE writing','Use the approved setup',755,365]];
    const paths=[['context','draft','M220 95H265'],['draft','review','M465 95H510'],['review','evaluate','M710 95H755'],['evaluate','revise','M855 130V185H365V220'],['revise','context','M265 255H6V95H20'],['evaluate','approval','M855 130V220'],['review','escalated','M610 130V365'],['approval','activate','M855 290V365']];
    const activeNode=phase==='complete'?'activate':['stopped','budget_exhausted','rejected'].includes(phase)?'escalated':phase;
    const key=run?.run_id?.replace(/[^a-zA-Z0-9]/g,'') || 'idle';
    return `<figure class="writing-flow"><figcaption>How the loop works <span>Current step: ${esc(phase.replaceAll('_',' '))}</span></figcaption><svg viewBox="0 0 980 465" role="img" aria-label="Context flows to two drafts, review and a quality gate. Writing issues loop through revised guidance. Technical issues pause for human input. Passing work needs your approval before activation."><defs><marker id="arrow${key}" markerWidth="9" markerHeight="9" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8"/></marker></defs>
      ${paths.map(([from,to,d])=>`<path d="${d}" class="flow-edge${activeNode===to && (to!=='context' || visited.has('revise'))?' is-current':''}${visited.has(from) && visited.has(to)?' is-visited':''}" marker-end="url(#arrow${key})"/>`).join('')}
      <path d="M855 60V15H120V60" class="flow-edge flow-next${phase==='context' && m.activity.sample===2?' is-current':''}" marker-end="url(#arrow${key})"/>
      <text x="480" y="12" text-anchor="middle" class="flow-label">Next independent entry</text><text x="530" y="176" class="flow-label">Writing needs work · another round</text><text x="873" y="178" class="flow-label">Pass</text><text x="623" y="324" class="flow-label">Context / technical issue</text><text x="28" y="245" class="flow-label">Retest both entries</text>
      ${nodes.map(([id,title,sub,x,y])=>`<g class="flow-node${visited.has(id)?' is-visited':''}${activeNode===id?' is-current':''}${id==='escalated' && m.attention?' needs-human':''}"${activeNode===id?' aria-current="step"':''}><rect x="${x}" y="${y}" width="200" height="70" rx="10"/><text x="${x+100}" y="${y+28}" text-anchor="middle" class="flow-title">${esc(title)}</text><text x="${x+100}" y="${y+50}" text-anchor="middle" class="flow-subtitle">${esc(sub)}</text></g>`).join('')}</svg><p>Each entry gets two drafts. Writing fixes loop back within your budget. Context problems stop for human input. A passing setup still needs your approval.</p></figure>`;
  }
  function render(run) {
    const m=model(run);
    return `<section class="writing-control-room" aria-label="Live writing team"><div class="writing-team">${m.people.map(p=>`<article class="writing-agent agent-${p.kind}${p.active?' is-working':''}${p.attention?' needs-human':''}"><div class="agent-head">${portrait(p.kind)}<span class="agent-status-dot" aria-hidden="true"></span></div><div class="agent-identity"><h4>${p.name}</h4><span>${p.active?'Working':p.attention?'Needs you':'Standing by'} · ${p.role}</span></div><div class="agent-bubble"${p.active || p.attention?' role="status"':''}>${esc(p.message)}</div></article>`).join('')}</div>${graph(run,m)}<p class="activity-source">Live status comes from the saved run. StoryTechMan is the technical supervisor and escalation gate; repairs pause for your input.</p></section>`;
  }
  return {render,model};
})();
