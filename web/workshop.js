'use strict';
window.NCCEWorkshop = (() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const S = {home:null, message:'', busy:false};
  let root, request, drawDocument;
  const post = (path, body) => request('/api/workshop/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const optimizing = () => ['queued','running'].includes(S.optimization?.status);
  const visible = () => root?.querySelector('.writer-workshop');
  const formNames={fighter_mind:'Fighter current thoughts',fighter_memory:'Fighter memories',fighter_reflection:'Fighter reflections',fighter_biography:'Fighter biographies',gang_history:'Gang histories',gang_event:'Gang events',gang_origin:'Gang origins',place_event:'Territory events',place_ambient:'Territory scenes',territory_history:'Territory histories',territory_origin:'Territory origins',region_history:'Region histories',battle_report:'Battle reports',downtime:'Downtime reports',relationship:'Relationships'};
  const formName=form=>formNames[form] || String(form || '').replaceAll('_',' ');
  const paragraphs=text=>String(text || '').split(/\n\s*\n/).map(p=>`<p>${esc(p)}</p>`).join('');
  function disclosure(title,text,key='',label='Full explanation') {
    return `<details class="ws-disclosure"${key?` data-ws-detail="${esc(key)}"`:''}><summary><span class="ws-closed-title">${esc(title)}</span><span class="ws-open-title">${esc(label)}</span><small class="ws-disclosure-hint">Show details</small></summary><div class="ws-full-text">${paragraphs(text)}</div></details>`;
  }
  function guidelineChanges(change) {
    if(!change)return '<p class="muted">No earlier comparison is recorded.</p>';
    return `<p>${esc(change.summary)}</p>${change.edits.map(edit=>`<div class="ws-guideline-diff">${edit.before?`<div><strong>Removed / replaced</strong><pre class="is-removed">${esc(edit.before)}</pre></div>`:''}${edit.after?`<div><strong>Added</strong><pre class="is-added">${esc(edit.after)}</pre></div>`:''}</div>`).join('')}`;
  }
  function guidelineTime(value) {
    if(!value || !Number.isFinite(new Date(value).getTime()))return 'Time not recorded';
    return new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',timeZone:'Europe/Warsaw',timeZoneName:'short'}).format(new Date(value));
  }
  function guidelineText(text) {
    const inline=t=>esc(t).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>');
    const out=[];let paragraph=[],list=[],type='';
    const flush=()=>{if(paragraph.length){out.push('<p>'+inline(paragraph.join(' '))+'</p>');paragraph=[];}if(list.length){out.push('<'+type+'>'+list.map(t=>'<li>'+inline(t)+'</li>').join('')+'</'+type+'>');list=[];type='';}};
    for(const line of String(text || '').split(/\r?\n/)){
      const heading=line.match(/^#{1,6}\s+(.+)$/), item=line.match(/^\s*(?:([-*])|\d+[.)])\s+(.+)$/);
      if(!line.trim()){flush();continue;}
      if(heading){flush();out.push('<h5>'+inline(heading[1])+'</h5>');}
      else if(item){const next=item[1]?'ul':'ol';if(paragraph.length || type && type!==next)flush();type=next;list.push(item[2]);}
      else {if(list.length)flush();paragraph.push(line);}
    }
    flush();return '<div class="ws-guideline-document">'+out.join('')+'</div>';
  }
  function guidelinesPanel() {
    const g=S.guidelines;
    const entries=g?.timeline || [];
    const timeline=entries.map(e=>{
      const proposal=e.kind==='proposal', source=e.source, run=e.run_id || source?.run_id;
      const title=proposal?'JKSimmons proposed a change':source?.author==='JKSimmons'?'JKSimmons saved candidate guidelines':'Guidelines saved';
      const pending=S.guidelineActivation?.event_id===e.event_id && S.guidelineActivation.scope===g.scope;
      const badge=e.is_active?(proposal?'Active proposal ✓':'Active version ✓'):pending?'Activating…':proposal?'Activate proposal':'Activate version';
      const reason=e.reason || source?.reason;
      return `<details class="ws-guideline-event${e.is_active?' is-active-version':''}" data-ws-detail="${esc(e.event_id)}"><summary><time datetime="${esc(e.created_at || '')}">${esc(guidelineTime(e.created_at))}</time><span class="ws-guideline-event-title">${esc(title)}<small>${esc(e.time_basis || 'Version saved')}${run?' · Study '+esc(run.slice(-8))+' · '+esc(e.round_kind || 'learning')+' round '+esc(e.round || source?.round)+(e.entry_number?' · entry '+e.entry_number:''):''}</small></span><button type="button" class="ws-guideline-badge ws-guideline-activate${proposal?' is-proposal':''}" data-ws="guidelines-activate" data-event-id="${esc(e.event_id)}"${e.is_active || S.guidelineActivation || watching()?' disabled':''} aria-label="${esc(badge)} · ${esc(guidelineTime(e.created_at))}"${pending?' aria-busy="true"':''}>${pending?'<span class="ws-activation-spinner" aria-hidden="true"></span>':''}${badge}</button></summary><div class="ws-guideline-event-body">${e.entry?`<p><strong>Test entry:</strong> ${esc(e.entry)}</p>`:''}
      <p class="ws-guideline-status-note">${proposal && e.is_active?'You activated this proposal for future writing. Its original review comparison is shown below.':proposal && e.activation?.revision_id?'You activated this proposal previously, but a different version is active now.':proposal?'Suggested changes only. This comparison is against the instructions tested in that study. It did not replace saved guidelines or activate anything.':e.is_active?'This saved version is still active. Newer proposals in this timeline have not replaced it.':'This is a saved historical or test version. Saving a version does not activate it.'}</p>
      ${e.change?`<h5>${proposal?(e.is_active?'Changes in this activated proposal':'Suggested changes · not applied'):'Changes saved in this version'}</h5>${guidelineChanges(e.change)}`:''}
      ${reason?`<details><summary>Reviewer’s reasoning</summary>${paragraphs(reason)}</details>`:''}
      ${e.is_active?'<p class="muted">Read the full text once in “Active instructions” below.</p>':`<details data-ws-detail="full-${esc(e.event_id)}"><summary>${proposal?'Full proposed guidelines':'Full saved guidelines'}</summary>${guidelineText(e.instructions)}</details>`}
      ${e.examples?`<details><summary>Style examples for this version</summary>${guidelineText(e.examples)}</details>`:''}</div></details>`;
    }).join('');
    return `<details class="ws-guidelines" data-ws-detail="guidelines-library"><summary data-ws="guidelines-refresh">Writing guidelines · reference &amp; history</summary><div class="ws-guideline-content"><div class="ws-guideline-controls"><label>Guidelines for<select data-ws-guide-scope${S.guidelineActivation?' disabled':''}>${['shared',...(S.home.forms || [])].map(f=>`<option value="${esc(f)}"${f===(S.guidelineScope || 'shared')?' selected':''}>${esc(f==='shared'?'Shared craft · all prose':formName(f))}</option>`).join('')}</select></label><button data-ws="guidelines-refresh">Refresh guidelines</button></div>${S.guidelineActivationMessage?`<p class="ws-guideline-activation-message" role="status">${esc(S.guidelineActivationMessage)}</p>`:''}${S.guidelineError?`<p role="status">${esc(S.guidelineError)}</p>`:''}
      ${g?`<p class="ws-guideline-status-note">Click Activate on a proposal or saved version to use it for future writing. This is your manual approval, separate from passing a study’s validation. Existing prose stays unchanged.${watching()?' Finish the current writing study before switching versions.':''}</p>
      <h4>Guideline timeline · newest first</h4><p class="muted">Times are shown in Warsaw time. Study IDs distinguish separate runs; round numbering restarts in each study.</p><div class="ws-guideline-timeline">${timeline || '<p>No saved guideline changes or review proposals yet.</p>'}</div>
      <details class="ws-guidelines-active" data-ws-detail="guidelines-active"><summary>Active instructions · full reference</summary><p class="muted">${g.active.created_at?'Version saved '+esc(guidelineTime(g.active.created_at)):'Built-in instructions. No saved version is activated.'}</p>${guidelineText(g.active.instructions)}${g.active.examples?`<details><summary>Active style examples</summary>${guidelineText(g.active.examples)}</details>`:''}</details>
      <p class="muted">History: up to ${g.history_limit} saved versions and 10 recent distinct review proposals. Older stored records are preserved.</p>`:'<p>Choose a category to read its guideline history.</p>'}</div></details>`;
  }
  async function loadGuidelines() {
    const scope=S.guidelineScope || 'shared', ticket=(S.guidelineLoad || 0)+1;S.guidelineLoad=ticket;
    try {
      const result=await request('/api/workshop/guidelines?scope='+encodeURIComponent(scope));
      if(ticket===S.guidelineLoad){S.guidelines=result;S.guidelineError='';}
    } catch(error) {if(ticket===S.guidelineLoad)S.guidelineError='Guidelines could not refresh. Use Refresh guidelines to try again. Previously loaded text may be out of date.';}
  }
  const guidelineStamp=run=>JSON.stringify([run?.specific?.revision_id,run?.shared?.revision_id,run?.status,run?.tech?.status,(run?.rounds || []).map(r=>r.pairs.filter(p=>p.review).length)]);
  function reviewPair(pair,pairKey='entry') {
    const review=pair.review;
    const issueNames={writing:'Writing needs revision',context:'Source context needs attention',technical:'The generation setup needs attention',permission:'Your authorization is needed'};
    const hasSystem=review?.candidates?.some(c=>c.issues?.some(i=>i.category!=='writing'));
    const passed=review?.candidates?.every(c=>c.overall>=8 && Object.values(c.scores || {}).every(v=>v>=8) && !c.issues?.some(i=>i.blocking));
    const drafts=(pair.candidates || []).map((candidate,index)=>`<article class="ws-prose-draft"><h5>Draft ${index?'B':'A'}</h5><div class="ws-prose-body">${candidate.document?drawDocument(candidate.document):'<p class="muted">'+esc(candidate.status==='error'?'This draft could not be generated.':candidate.status==='running'?'Writing this draft...':'Waiting for this draft...')+'</p>'}</div></article>`).join('');
    return `<section class="ws-result-entry"><h4>${esc(pair.label)}</h4><section class="ws-drafts-reading" aria-label="Generated drafts"><h5 class="ws-section-heading">Read the drafts</h5><div class="ws-draft-grid">${drafts || '<p class="muted">Drafts will appear here as they are generated.</p>'}</div></section><section class="ws-assessment" aria-label="Draft assessment"><h5 class="ws-section-heading">Assessment</h5>${review?`<div class="ws-review-verdict"><span class="ws-kicker">JKSimmons’s assessment</span>${disclosure(review.headline || (hasSystem?'The writing setup needs investigation':passed?'Both drafts meet the target':'The category setup still needs improvement'),review.summary,'','Full assessment')}</div><div class="ws-draft-grid">${(pair.candidates || []).map((candidate,index)=>{
      const c=review.candidates?.find(c=>c.index===index), issues=c?.issues || [], pass=c && c.overall>=8 && Object.values(c.scores || {}).every(v=>v>=8) && !issues.some(i=>i.blocking);
      return `<article class="ws-draft-card"><header><h5>Draft ${index?'B':'A'} assessment</h5>${c?`<strong class="ws-score ${pass?'is-pass':'is-below'}">${esc(c.overall)}<small> / 10</small></strong>`:''}</header>${c?`<p class="ws-score-caption">${pass?'Meets the target':'Below the target'}${issues.some(i=>i.blocking)?' · blocking issue':''}</p><dl class="ws-score-list">${Object.entries(c.scores || {}).map(([k,v])=>`<div><dt>${esc(k.replaceAll('_',' '))}</dt><dd>${esc(v)}<small> / 10</small></dd></div>`).join('')}</dl>`:''}${issues.length?`<h6>${issues.length} ${issues.length===1?'issue':'issues'} to address</h6><div class="ws-issue-list">${issues.map((issue,i)=>`<details class="ws-review-issue ws-disclosure${issue.blocking?' is-blocking':''}" data-ws-detail="${esc('issue-'+pairKey+'-'+index+'-'+i)}"><summary><span class="ws-closed-title"><span class="ws-issue-category">${esc(issue.category)}${issue.blocking?' · blocking':''}</span> <span class="ws-issue-title">${esc(issue.title || issueNames[issue.category] || 'Review issue')}${issue.title?'':' '+(i+1)}</span></span><span class="ws-open-title">${esc(issue.category)} · explanation and evidence</span><small class="ws-disclosure-hint">Show details</small></summary>${paragraphs(issue.explanation)}<blockquote><span>Evidence</span>${esc(issue.evidence)}</blockquote></details>`).join('')}</div>`:c?'<p class="muted">No issues reported.</p>':''}</article>`;
    }).join('')}</div>`:'<p class="muted">The assessment will appear after JKSimmons reviews the draft pair.</p>'}</section></section>`;
  }
  const techWorking=()=>['queued','investigating','repair_queued','repairing','release_queued','releasing'].includes(S.optimization?.tech?.status);
  const watching=()=>optimizing() || techWorking();
  const techBlocking=()=>techWorking() || ['proposal_ready','repair_ready','released','needs_input'].includes(S.optimization?.tech?.status);
  function techPanel(run) {
    const t=run.tech || {}, proposal=t.proposal, report=t.report, release=t.release_report;
    const list=(title,items)=>items?.length?`<h5>${title}</h5><ul>${items.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'';
    return `<section class="ws-tech-panel"><h4>StoryTechMan · generation setup</h4><p><a href="codex://threads/${esc(t.thread_id || '01a17ff0-9029-7a13-935f-d0a86dcdc2b2')}">Open StoryTechMan in Codex</a></p>${techWorking()?`<p role="status">${({queued:'Investigation queued',investigating:'Investigating the saved requests and generation code',repair_queued:'Approved development repair queued',repairing:'Implementing and testing the approved repair',release_queued:'Approved release queued',releasing:'Deploying and verifying the tested repair'})[t.status]}.</p><p>The writing loop remains paused. ${t.status==='queued' || t.status==='investigating'?'This investigation is read-only.':'This follows your explicit approval.'}</p>`:''}${t.error?`<p role="alert">${esc(t.error)}</p>`:''}
      ${proposal?`<h5>${esc(proposal.headline)}</h5>${disclosure('Read findings and evidence',proposal.summary,'','Investigation summary')}<div class="ws-findings">${proposal.findings.map((f,i)=>`<details class="ws-disclosure"><summary><span class="ws-closed-title">Finding ${i+1}: ${esc(f.problem)}</span><span class="ws-open-title">Finding ${i+1} · evidence</span></summary><blockquote>${esc(f.evidence)}</blockquote><p>${esc(f.uncertainty)}</p></details>`).join('')}</div>${list('Proposed repair',proposal.proposed_changes)}${list('How it will be checked',proposal.validation_plan)}${list('Risks and limits',proposal.risks)}${list('Questions for you',proposal.questions)}`:''}
      ${t.status==='proposal_ready'?`<p>No repair has been made. Approval below authorizes development and tests; deployment needs a separate decision.</p><div class="workshop-actions"><button data-ws="tech-approve"${proposal?.questions?.length?' disabled':''}>Approve development repair</button><button data-ws="tech-reject">Reject proposal</button></div>`:''}
      ${report?`<h5>${esc(report.headline)}</h5>${paragraphs(report.summary)}${list('Changes',report.changes)}${list('Checks',report.tests)}${list('Files changed',report.files)}${report.proposed_shared_instructions?disclosure('Proposed shared guidance',report.proposed_shared_instructions,'','Full proposed shared guidance'):''}${report.proposed_form_instructions?disclosure('Proposed category guidance',report.proposed_form_instructions,'','Full proposed category guidance'):''}${list('Limitations',report.limitations)}<details><summary>Tested development commit</summary><code>${esc(report.commit_id)}</code></details>`:''}
      ${t.status==='repair_ready'?'<p>The repair is tested in development. It is not deployed and no writing instructions have been activated.</p><button data-ws="tech-release">Deploy this tested repair</button>':''}
      ${release?`<h5>${esc(release.headline)}</h5>${paragraphs(release.summary)}${list('Release checks',release.tests)}<p>Run a new category study before approving any new writing setup.</p>${t.status==='released'?'<button data-ws="tech-test-repair">Test the repaired category setup</button>':''}`:''}
      ${!techWorking() && t.status!=='repair_ready'?`<label>What should StoryTechMan investigate?<textarea data-ws-tech-note rows="3" maxlength="6000" placeholder="For example: inspect why the category keeps repeating the same ending.">${esc(S.techNote || '')}</textarea></label><button data-ws="tech-investigate"${S.busy?' disabled':''}>${t.status==='proposal_ready'?'Send guidance and revise proposal':t.status?'Request another investigation':'Ask StoryTechMan to investigate'}</button><p class="muted">Uses Codex for a read-only investigation. No JuniorWriter calls and no automatic repair.</p>`:''}</section>`;
  }
  function decisionPanel(run) {
    const waiting=['awaiting_next_round','budget_exhausted'].includes(run.status), paused=['escalated','awaiting_samples','stopped'].includes(run.status);
    if(!waiting && !paused && !run.tech)return '';
    return `<section class="ws-decision${waiting?' is-batch-complete':''}"><h4>${waiting?(run.validation_pending?'Promising setup · validate on fresh entries':'This test batch is complete'):run.status==='awaiting_samples'?'Fresh source entries are needed':'The writing loop is paused'}</h4>${waiting?`<p>${run.validation_pending?'The current category prompt passed its learning test. The same prompt must now pass on fresh entries before activation.':'The rounds you authorized have finished. Drafts and reviews are saved. Choose whether to continue testing or finish here.'}</p>${!run.validation_pending?`<p>The setup has not yet met the approval requirements.${run.status==='budget_exhausted'?' Continuing saves the proposed category instructions from the reviews and tests fresh entries.':' The latest reusable category instructions are saved.'}</p>`:''}<p>One more complete round includes up to <strong>4 fresh writing calls + 2 pair reviews</strong>. Each review covers A and B for one entry.</p><div class="workshop-actions"><button data-ws="opt-continue"${S.busy || techBlocking()?' disabled':''}>${S.continueBody?'Check submitted next round':run.validation_pending?'Authorize validation round':'Authorize another test round'}</button><button data-ws="opt-finish"${techWorking()?' disabled':''}>Finish and keep findings</button></div>`:paused?`<p>${esc(run.message)}</p><p>No further writer calls will start. Use the investigation below to diagnose the environment before another study.</p>`:''}${techPanel(run)}</section>`;
  }
  function optimizationPanel() {
    const config=S.optimizations?.configuration || {}, run=S.optimization;
    const bridge=S.optimizations?.bridge, available=!bridge || bridge.online;
    const forms=S.home.forms || [...new Set(S.home.samples.map(s=>s.form))], form=S.optForm;
    const hasSample=S.home.samples.some(s=>s.form===form);
    return `<section class="workshop-optimization" data-ws-run="${esc(run?.run_id || '')}"><h3>Improve a whole prose category</h3>
      <p class="ws-purpose">Improve the reusable prompt, guardrails and context so future entries become stronger. Every test generates fresh prose; it does not rewrite the previous drafts.</p>
      <div class="ws-connection-row"><span class="codex-connection ${available?'is-online':'is-offline'}">${available?'● Agents connected':'○ Local connection unavailable'}</span><button data-ws="opt-connection">Check connection</button><button data-ws="opt-personas">${S.personas===false?'Enable':'Disable'} character banter</button></div>
      ${!available?`<p class="workshop-error">Start START JKSIMMONS.vbs and keep Codex open before authorizing writing. ${esc(bridge?.connection_error || '')}</p>`:''}
      <details class="ws-agent-info"><summary>Models and connection</summary><dl><div><dt>JuniorWriter</dt><dd>${esc(config.writer_model || S.home.model)} · ${esc(config.writer_effort || S.home.effort)} effort · external writing provider</dd></div><div><dt>JKSimmons</dt><dd>Your persistent Codex reviewer chat; reviews category guidance and fresh results. <a href="codex://threads/01a17f57-f5bb-7782-bce0-8b3b43dd367f">Open JKSimmons in Codex</a></dd></div><div><dt>StoryTechMan</dt><dd>Your persistent Codex engineer chat; investigates the environment and proposes repairs.</dd></div></dl><p>The local listener wakes an agent only for an actual job. Empty waiting uses no Codex allowance. Agent expressions and banter do not affect scores or prompts.</p></details>
      ${window.NCCEWritingActivity?.render(run,{personas:S.personas!==false}) || ''}
      ${!watching()?`<h4>Start a new category study</h4><label>Complete rounds allowed<select data-ws-opt-rounds>${[1,2,3].map(n=>`<option value="${n}"${n===(S.optRounds || 1)?' selected':''}>${n} complete ${n===1?'round':'rounds'} · up to ${n*4} fresh drafts + ${n*2} pair reviews</option>`).join('')}</select></label><div class="workshop-actions ws-improve-controls"><label>Prose type to improve<select data-ws-opt-form${S.busy || S.optBody?' disabled':''}>${forms.map(f=>`<option value="${esc(f)}"${f===form?' selected':''}${!S.home.samples.some(s=>s.form===f)?' disabled':''}>${esc(formName(f))}</option>`).join('')}</select></label><button data-ws="opt-start"${!available || !hasSample || !S.home.configured || S.busy?' disabled':''}>${S.optBody?'Check submitted study':'Start '+esc(formName(form).toLowerCase())+' study'}</button></div><p class="ws-control-help">One round = two new drafts for each of two entries + one review per pair. Passing learning rounds require fresh-entry validation; nothing is activated without your approval.</p><label>Previous studies<select data-ws-opt-history><option value="">Choose study…</option>${(S.optimizations?.runs || []).map(r=>`<option value="${esc(r.run_id)}"${r.run_id===run?.run_id?' selected':''}>${esc(formName(r.form))} · ${esc(({budget_exhausted:'Awaiting your decision',awaiting_next_round:'Awaiting your decision',escalated:'Setup investigation needed'})[r.status] || r.status.replaceAll('_',' '))} · ${esc(r.created_at)}</option>`).join('')}</select></label>`:`<div class="ws-running"><p role="status">${optimizing()?'Category study in progress':'StoryTechMan is working on this study'}. Your authorized writing limit does not increase automatically.</p>${optimizing()?'<button data-ws="opt-stop">Stop after the current request</button>':''}</div>`}
      ${run?`${decisionPanel(run)}<div class="ws-results">${(run.rounds || []).map(round=>`<details class="ws-round"${round===run.rounds.at(-1)?' open':''}><summary>${round.kind==='validation'?'Validation':'Learning'} round ${round.number} · ${round.pairs.length} test ${round.pairs.length===1?'entry':'entries'}</summary>${round.pairs.map((pair,i)=>reviewPair(pair,round.number+'-'+i)).join('')}</details>`).join('')}</div>
      ${run.status==='awaiting_approval'?`<section class="ws-decision"><h4>The category setup passed validation</h4><p>The unchanged prompt passed on fresh entries. Your approval activates the tested setup for future writing; existing prose stays unchanged.</p><details><summary>Review the exact instructions to activate</summary><h5>Shared craft</h5><pre>${esc(run.shared.instructions)}</pre><h5>Category brief</h5><pre>${esc(run.specific.instructions)}</pre></details><div class="workshop-actions"><button data-ws="opt-approve">Approve tested setup for future NCCE writing</button><button data-ws="opt-reject">Reject this setup</button></div></section>`:''}
      ${run.prompt_history?.length?`<details class="ws-prompt-changes"><summary>Category prompt changes · ${run.prompt_history.length} saved revisions</summary>${run.prompt_history.map(p=>`<details><summary>Proposed after learning round ${p.after_round}</summary><pre>${esc(p.instructions)}</pre></details>`).join('')}</details>`:''}
`:''}</section>`;
  }
  async function pollOptimization() {
    try {
      const previousStamp=guidelineStamp(S.optimization);
      S.optimization=await request('/api/workshop/optimization?run_id='+encodeURIComponent(S.optimization.run_id));
      if(previousStamp!==guidelineStamp(S.optimization))await loadGuidelines();
      paint();
      if(watching()) setTimeout(pollOptimization,1500);
      else {S.optBody=null;S.continueBody=null; S.optimizations=await request('/api/workshop/optimizations'); paint();}
    } catch(error) {S.message=error.message+' Reopen the saved improvement run to check it; no new calls were made.';paint();}
  }
  function detailKey(node) {
    const parts=[];let item=node;
    while(item && item!==root){
      if(item.tagName==='DETAILS')parts.push(item.dataset.wsDetail || item.querySelector(':scope > summary')?.textContent.trim() || 'details');
      else if(['SECTION','ARTICLE','LI'].includes(item.tagName)){const heading=item.querySelector(':scope > h3,:scope > h4,:scope > header > h5,:scope > header > strong');if(heading)parts.push(heading.textContent.trim());}
      item=item.parentElement;
    }
    return (node.closest('.workshop-optimization')?.dataset.wsRun || '')+'|'+parts.reverse().join('|');
  }
  function paint(force=false) {
    if(!force && typeof document!=='undefined' && root?.contains?.(document.activeElement) && document.activeElement?.matches?.('select,textarea,input')){S.pendingPaint=true;return;}
    const focusedFlow=typeof document!=='undefined' && document.activeElement?.matches?.('.flow-node-button')?document.activeElement.closest('.flow-node')?.dataset.flowNode:null;
    const openDetails=new Map([...(root?.querySelectorAll?.('details') || [])].map(d=>[detailKey(d),d.open]));

    if (!visible()) return;
    root.innerHTML=`<section class="writer-workshop"><div class="eyebrow">Category writing lab</div><h2>Writer Workshop</h2><p>Develop the writing setup for a whole prose category. Read the fresh drafts first, then their assessment and your next decision.</p><p class="muted">Opening studies and reading results makes no model calls. Starting or continuing a writing test requires your confirmation.</p><p role="status" id="ws-status">${esc(S.message)}</p>${optimizationPanel()}${guidelinesPanel()}</section>`;
    for(const d of root.querySelectorAll?.('details') || []){const key=detailKey(d);if(openDetails.has(key))d.open=openDetails.get(key);}
    if(focusedFlow && /^[a-z-]+$/.test(focusedFlow))root.querySelector('.flow-node[data-flow-node="'+focusedFlow+'"] .flow-node-button')?.focus({preventScroll:true});
    S.pendingPaint=false;
  }
  async function preparedOptimization() {
    const form=S.optForm, seed=S.repairSeed?.form===form?S.repairSeed:null;
    const entry=S.home.samples.find(s=>s.form===form);
    if(!entry)throw new Error('No sourced entries are available for this prose type.');
    const sample=await request('/api/workshop/sample?key='+encodeURIComponent(entry.key));
    const specificMeta=await request('/api/workshop/policy?scope='+encodeURIComponent(form));
    const sharedMeta=await request('/api/workshop/policy?scope=shared');
    const specific=seed?.specific || specificMeta.draft.revision_id || (await post('save-policy',specificMeta.draft)).revision_id;
    const shared=seed?.shared || sharedMeta.draft.revision_id || (await post('save-policy',sharedMeta.draft)).revision_id;
    return {sample_key:sample.key,packet_hash:sample.packet_hash,shared_revision_id:shared,form_revision_id:specific,focus:'auto',variation:0,plan_key:null};
  }
  async function action(button) {
    switch(button.dataset.ws) {
      case 'guidelines-refresh': if(!S.guidelineActivation)await loadGuidelines();break;
      case 'guidelines-activate': {
        if(S.guidelineActivation || watching())return;
        const scope=S.guidelines.scope, item=S.guidelines.timeline.find(e=>e.event_id===button.dataset.eventId);
        if(!item || item.is_active)return;
        S.guidelineActivation={scope,event_id:item.event_id};S.guidelineActivationMessage='Saving your selection…';S.guidelineLoad=(S.guidelineLoad || 0)+1;paint(true);
        try {
          const updated=await post('guidelines-activate',{scope,event_id:item.event_id,content_hash:item.content_hash,expected_active:S.guidelines.active.revision_id || null,request_key:crypto.randomUUID()});
          S.guidelineLoad=(S.guidelineLoad || 0)+1;S.guidelines=updated;
          S.guidelineActivationMessage=updated.timeline.some(e=>e.event_id===item.event_id && e.is_active)?'Active guidelines updated. Future writing will use this version.':'The server returned a different current selection. Review the active highlight.';
        } catch(error) {
          await loadGuidelines();S.guidelineActivationMessage='Activation was not confirmed: '+error.message+' The highlight shows the last server-confirmed active version.';
        } finally {S.guidelineActivation=null;paint(true);}
        break;
      }
      case 'opt-connection': S.optimizations=await request('/api/workshop/optimizations');S.message=S.optimizations.bridge?.online?'Codex companion is connected.':'Codex companion is offline; no writer calls will start.';break;
      case 'opt-personas': S.personas=S.personas===false;break;
      case 'opt-start': {
        if(S.busy || watching()) return;
        const rounds=S.optRounds || 1;
        if(!S.optBody && !window.confirm(`Test the reusable ${formName(S.optForm).toLowerCase()} setup on fresh entries with up to ${rounds*4} paid JuniorWriter calls and ${rounds*2} reviews in your JKSimmons Codex chat? Codex usage limits apply. There are no external reviewer API calls. The run stops on technical issues and never activates instructions automatically.`)) {paint();return;}
        S.busy=true;paint();
        try {
          if(!S.optBody) S.optBody={...await preparedOptimization(),request_key:crypto.randomUUID(),max_rounds:rounds,allow_paid:true};
          S.optimization=await post('optimize',S.optBody);S.repairSeed=null;
          S.busy=false;if(!optimizing())S.optBody=null;paint();if(watching())setTimeout(pollOptimization,1000);
        } catch(error) {S.busy=false;if(error.status>=400 && error.status<500 && ![408,429].includes(error.status))S.optBody=null;throw error;}
        break;
      }
      case 'tech-test-repair':
        if(S.busy || watching())return;
        S.optForm=S.optimization.form;
        S.repairSeed={form:S.optForm,specific:S.optimization.tech?.repair_candidates?.[S.optForm] || S.optimization.specific.revision_id,shared:S.optimization.tech?.repair_candidates?.shared};
        await action({dataset:{ws:'opt-start'}});break;
      case 'opt-continue': {
        if(S.busy || watching())return;
        if(S.continueBody && S.continueBody.run_id!==S.optimization.run_id)S.continueBody=null;
        if(!S.continueBody && !window.confirm('Authorize one complete round: up to 4 paid fresh writing calls and 2 Codex pair reviews? Existing drafts will not be rewritten and no instructions activate automatically.'))break;
        if(!S.continueBody)S.continueBody={run_id:S.optimization.run_id,additional_rounds:1,allow_paid:true,request_key:crypto.randomUUID()};
        S.busy=true;paint();
        try {S.optimization=await post('optimization-continue',S.continueBody);S.busy=false;paint();if(watching())setTimeout(pollOptimization,1000);}
        catch(error){S.busy=false;if(error.status>=400 && error.status<500 && ![408,429].includes(error.status))S.continueBody=null;throw error;}
        break;
      }
      case 'tech-investigate':
        if(S.busy || techWorking())return;
        S.busy=true;paint();
        try{S.optimization=await post('optimization-investigate',{run_id:S.optimization.run_id,request_key:crypto.randomUUID(),note:S.techNote || ''});S.techNote='';S.busy=false;paint();if(watching())setTimeout(pollOptimization,1000);}catch(error){S.busy=false;throw error;}
        break;
      case 'tech-approve':
      case 'tech-reject':
      case 'tech-release': {
        if(S.busy || techWorking())return;
        const action=button.dataset.ws==='tech-approve'?'approve_repair':button.dataset.ws==='tech-release'?'approve_release':'reject';
        if(action!=='reject' && !window.confirm(action==='approve_repair'?'Approve this exact proposal for development changes and tests? No deployment, writer calls or policy activation is authorized.':'Deploy this exact tested repair to your existing NCCE preview? No writer calls or writing-policy activation is authorized.'))break;
        S.busy=true;paint();
        try{S.optimization=await post('optimization-technical-decision',{run_id:S.optimization.run_id,action,proposal_hash:S.optimization.tech?.proposal_hash,report_hash:S.optimization.tech?.report_hash});S.busy=false;paint();if(watching())setTimeout(pollOptimization,1000);}catch(error){S.busy=false;throw error;}
        break;
      }
      case 'opt-finish':S.optimization=await post('optimization-finish',{run_id:S.optimization.run_id});S.continueBody=null;break;
      case 'opt-stop': await post('optimization-stop',{run_id:S.optimization.run_id});S.message='Stop requested. The current request may finish; no further requests will begin.';break;
      case 'opt-approve':
      case 'opt-reject': {
        const approve=button.dataset.ws==='opt-approve';
        if(approve && !window.confirm('Activate the exact tested shared and form instructions for future NCCE generation? Existing campaign prose stays unchanged.'))break;
        S.optimization=await post('optimization-decide',{run_id:S.optimization.run_id,approve});
        S.optimizations=await request('/api/workshop/optimizations');
        if(approve)S.home=await request('/api/workshop');
        await loadGuidelines();
        S.message=approve?'Tested setup activated for future NCCE writing.':'Candidate rejected. Active setup unchanged.';break;
      }
    }
    paint();
  }
  function bind() {
    if (root.dataset.workshopBound) return;
    root.dataset.workshopBound='1';
    root.addEventListener('focusout',()=>{if(S.pendingPaint)setTimeout(()=>paint(),0);});
    root.addEventListener('click',event=>{const b=event.target.closest('[data-ws]');if(b){if(b.dataset.ws==='guidelines-activate'){event.preventDefault();event.stopPropagation();}b.disabled=true;action(b).catch(error=>{S.message=error.message;paint();});}});
    root.addEventListener('input',event=>{if(event.target.hasAttribute('data-ws-tech-note'))S.techNote=event.target.value;});
    root.addEventListener('change',event=>{
      const t=event.target;
      let task;
      if(t.hasAttribute('data-ws-guide-scope')) {S.guidelineScope=t.value;S.guidelines=null;paint(true);task=loadGuidelines().then(()=>paint(true));}
      if(t.hasAttribute('data-ws-opt-rounds')) {S.optRounds=Number(t.value);paint(true);}
      if(t.hasAttribute('data-ws-opt-form') && !S.optBody && !optimizing()) {S.optForm=t.value;S.repairSeed=null;paint(true);}
      if(t.hasAttribute('data-ws-opt-history') && t.value) task=request('/api/workshop/optimization?run_id='+encodeURIComponent(t.value)).then(run=>{if(S.optimization?.run_id!==run.run_id){S.continueBody=null;S.repairSeed=null;}S.optimization=run;paint();if(watching())setTimeout(pollOptimization,1000);});
      task?.catch(error=>{S.message=error.message;paint();});
    });
  }
  async function open(container,api,blocks) {
    root=container; request=api; drawDocument=blocks; bind();
    root.innerHTML='<section class="writer-workshop"><h2>Writer Workshop</h2><p>Opening the editorial desk…</p></section>';
    try {
      if(!S.home) {
        S.home=await request('/api/workshop');
        S.optimizations=await request('/api/workshop/optimizations');
        const active=S.optimizations.runs.find(r=>['queued','running'].includes(r.status) || ['queued','investigating','repair_queued','repairing','release_queued','releasing'].includes(r.tech?.status));
        const pending=active || S.optimizations.runs.find(r=>['awaiting_next_round','budget_exhausted','awaiting_samples','escalated'].includes(r.status) || ['proposal_ready','repair_ready','released','needs_input'].includes(r.tech?.status));
        if(pending){S.optimization=pending;S.optForm=pending.form;}
        if(active)setTimeout(pollOptimization,1000);
        const initial=S.home.samples.find(s=>s.key==='comparison:1:0') || S.home.samples[0];
        if(!S.optForm)S.optForm=initial?.form || S.home.forms?.[0];
        S.guidelineScope=S.optForm || 'shared';
      }
      await loadGuidelines();
      paint();
    } catch(error) {if(visible())root.innerHTML='<section class="writer-workshop"><h2>Writer Workshop</h2><p role="alert">'+esc(error.message)+'</p></section>';}
  }
  return {open};
})();
