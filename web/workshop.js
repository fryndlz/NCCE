'use strict';
window.NCCEWorkshop = (() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const S = {home:null, sample:null, shared:null, specific:null, sharedMeta:null, specificMeta:null, trial:null, message:'', busy:false, requestKey:null, requestBody:null};
  let root, request, drawDocument;
  const post = (path, body) => request('/api/workshop/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const clone = value => JSON.parse(JSON.stringify(value));
  const running = () => ['queued','running'].includes(S.trial?.status);
  const optimizing = () => ['queued','running'].includes(S.optimization?.status);
  const visible = () => root?.querySelector('.writer-workshop');
  function setEditor(trial) {
    S.trial=trial;
    const doc=trial.edits?.[0]?.document || trial.document || {};
    S.edit={body:(doc.blocks || []).filter(b=>b.type==='body_paragraph').map(b=>b.text || '').join('\n\n'),composition:{...(doc.composition || {})}};
    if (!S.edit.body && trial.raw_output) S.edit.body=trial.raw_output;
  }
  function policyEditor(which,title) {
    const item=S[which], meta=S[which+'Meta'];
    if (!item) return '';
    return `<section class="workshop-policy"><h3>${esc(title)}</h3><p class="muted">Active: ${esc(meta.active?.label || 'Built-in instructions')}. ${item.dirty ? 'Unsaved changes.' : 'Draft saved or loaded.'}</p>
      <div class="workshop-actions"><button data-ws="preset" data-which="${which}" data-preset="builtin">Load built-in draft</button><button data-ws="preset" data-which="${which}" data-preset="candidate">Load editorial candidate</button></div>
      <label>Revision name<input data-ws-policy="${which}" data-field="label" maxlength="120" value="${esc(item.label)}"></label>
      <label>Writing instructions<textarea data-ws-policy="${which}" data-field="instructions" rows="12" maxlength="${which==='shared'?12000:4000}">${esc(item.instructions)}</textarea></label>
      <label>${which==='shared'?'Shared examples (optional)':'Style examples for this form'}<textarea data-ws-policy="${which}" data-field="examples" rows="9" maxlength="8000">${esc(item.examples)}</textarea></label>
      <div class="workshop-actions"><button data-ws="save" data-which="${which}">Save draft · free</button><button data-ws="activate" data-which="${which}">Activate this revision for future writing</button>${meta.active?`<button data-ws="builtin" data-which="${which}">Restore built-in instructions</button>`:''}</div>
      <label>Load a saved revision<select data-ws-history="${which}"><option value="">Choose revision…</option>${meta.history.map(r=>`<option value="${esc(r.revision_id)}">${esc(r.label)} · ${esc(r.created_at)}${r.revision_id===meta.active?.revision_id?' · ACTIVE':''}</option>`).join('')}</select></label>
    </section>`;
  }
  function editedDocument() {
    const doc=clone(S.trial?.edits?.[0]?.document || S.trial?.document || {}), fields=S.edit?.composition || {};
    doc.blocks=(S.edit?.body || '').split(/\n\s*\n/).filter(p=>p.trim()).map(text=>({type:'body_paragraph',text:text.trim()}));
    doc.composition=fields; doc.writer_status='ready'; delete doc.writer_message; doc.writer_model=null;
    if (fields.body_heading) doc.blocks.unshift({type:'section_label',text:fields.body_heading});
    if (fields.closing) doc.blocks.push({type:'internal_note',text:fields.closing_label || '',blocks:[{type:'body_paragraph',text:fields.closing}]});
    doc.termination={type:'record_termination',text:fields.signoff || ''};
    return doc;
  }
  function trialPanel() {
    if (!S.trial) return '<p class="muted">Import the selected sample to edit it for free, or generate one new draft.</p>';
    const t=S.trial, u=t.usage || {}, personal=['fighter_memory','fighter_reflection'].includes(t.form);
    return `<section class="workshop-trial"><h3>${esc(t.label)}</h3><p>${esc(t.status)} · ${u.requests_attempted || 0} provider calls · ${u.input_tokens || 0} input / ${u.output_tokens || 0} output tokens · ${u.cached_input_tokens || 0} cached input tokens</p>${t.error?`<p class="workshop-error" role="alert">${esc(t.error)}. Response retained for editing; no retry was made.</p>`:''}
      <details><summary>Original sample · preserved</summary>${drawDocument(t.document)}</details>
      ${running()?'<p role="status">The single request is running. This view will update when it finishes.</p>':`<h4>Edit the sample · free</h4><p class="muted">Edits stay in this workshop. Use a saved edit as a style example when you are satisfied.</p>
      ${personal?'':`<div class="workshop-composition">${[['heading','Heading / author'],['subject','Subject'],['body_heading','Section heading'],['closing_label','Closing label'],['closing','Closing remark'],['signoff','Sign-off']].map(([key,label])=>`<label>${label}<input data-ws-composition="${key}" maxlength="800" value="${esc(S.edit.composition[key] || '')}"></label>`).join('')}</div>`}
      <label>Prose · leave a blank line between paragraphs<textarea data-ws-body rows="13" maxlength="16000">${esc(S.edit.body)}</textarea></label><div class="workshop-actions"><button data-ws="save-edit">Save edited sample · free</button><button data-ws="example">Use saved edit as an example</button><button data-ws="export">Export sample and instructions</button></div>
      <details open><summary>Edited preview</summary><div id="ws-edited-preview">${drawDocument(editedDocument())}</div></details>
      <details><summary>Saved edit history · ${t.edits?.length || 0}</summary>${(t.edits || []).map(e=>`<button data-ws="load-edit" data-edit="${esc(e.edit_id)}">Load edit ${esc(e.created_at)}</button>`).join('') || '<p>No saved edits yet.</p>'}</details>`}
      <details><summary>Exact instructions used for this sample</summary><pre>${esc(t.instructions)}</pre></details></section>`;
  }
  const formNames={fighter_memory:'Fighter memories',fighter_reflection:'Fighter reflections',fighter_biography:'Fighter biographies',gang_history:'Gang histories',gang_event:'Gang events',gang_origin:'Gang origins',place_event:'Territory events',place_ambient:'Territory scenes',territory_history:'Territory histories',territory_origin:'Territory origins',region_history:'Region histories',battle_report:'Battle reports',downtime:'Downtime reports',relationship:'Relationships'};
  const formName=form=>formNames[form] || String(form || '').replaceAll('_',' ');
  const short=(text,limit=230)=>{text=String(text || '');if(text.length<=limit)return text;const cut=text.lastIndexOf(' ',limit);return text.slice(0,cut>limit/2?cut:limit)+'…';};
  const paragraphs=text=>String(text || '').split(/\n\s*\n/).map(p=>`<p>${esc(p)}</p>`).join('');
  function disclosure(title,text,key='',label='Full explanation') {
    return `<details class="ws-disclosure"${key?` data-ws-detail="${esc(key)}"`:''}><summary><span class="ws-closed-title">${esc(title)}</span><span class="ws-open-title">${esc(label)}</span><small class="ws-disclosure-hint">Show details</small></summary><div class="ws-full-text">${paragraphs(text)}</div></details>`;
  }
  function readable(text,label='Full assessment',limit=230) {
    return disclosure(label,text,'',label);
  }
  function reviewPair(pair) {
    const review=pair.review;
    const issueNames={writing:'Writing needs revision',context:'Source context needs attention',technical:'The generation setup needs attention',permission:'Your authorization is needed'};
    const hasSystem=review?.candidates?.some(c=>c.issues?.some(i=>i.category!=='writing'));
    const passed=review?.candidates?.every(c=>c.overall>=8 && Object.values(c.scores || {}).every(v=>v>=8) && !c.issues?.some(i=>i.blocking));
    return `<section class="ws-result-entry"><h4>${esc(pair.label)}</h4>${review?`<div class="ws-review-verdict"><span class="ws-kicker">JKSimmons’s assessment</span>${disclosure(review.headline || (hasSystem?'The writing setup needs investigation':passed?'Both drafts meet the target':'The category setup still needs improvement'),review.summary,'','Full assessment')}</div>`:'<p class="muted">Waiting for review.</p>'}<div class="ws-draft-grid">${(pair.candidates || []).map((candidate,index)=>{
      const c=review?.candidates?.find(c=>c.index===index), issues=c?.issues || [], pass=c && c.overall>=8 && Object.values(c.scores || {}).every(v=>v>=8) && !issues.some(i=>i.blocking);
      return `<article class="ws-draft-card"><header><h5>Draft ${index?'B':'A'}</h5>${c?`<strong class="ws-score ${pass?'is-pass':'is-below'}">${esc(c.overall)}<small> / 10</small></strong>`:`<span>${esc(candidate.status)}</span>`}</header>${c?`<p class="ws-score-caption">${pass?'Meets the target':'Below the target'}${issues.some(i=>i.blocking)?' · blocking issue':''}</p><dl class="ws-score-list">${Object.entries(c.scores || {}).map(([k,v])=>`<div><dt>${esc(k.replaceAll('_',' '))}</dt><dd>${esc(v)}<small> / 10</small></dd></div>`).join('')}</dl>`:''}<details class="ws-read-draft"><summary>Read draft ${index?'B':'A'}</summary>${drawDocument(candidate.document)}</details>${issues.length?`<h6>${issues.length} ${issues.length===1?'issue':'issues'} to address</h6><div class="ws-issue-list">${issues.map((issue,i)=>`<details class="ws-review-issue ws-disclosure${issue.blocking?' is-blocking':''}"><summary><span class="ws-closed-title"><span class="ws-issue-category">${esc(issue.category)}${issue.blocking?' · blocking':''}</span>${esc(issue.title || issueNames[issue.category] || 'Review issue')} ${issue.title?'':i+1}</span><span class="ws-open-title">${esc(issue.category)} · explanation and evidence</span><small class="ws-disclosure-hint">Show details</small></summary>${paragraphs(issue.explanation)}<blockquote><span>Evidence</span>${esc(issue.evidence)}</blockquote></details>`).join('')}</div>`:c?'<p class="muted">No issues reported.</p>':''}</article>`;
    }).join('')}</div></section>`;
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
  function draftFocus() {
    const options=S.home.focus_options?.[S.sample.form] || [];
    if(options.length<=1)return '<p class="ws-focus-fixed"><strong>Draft focus: the recorded event.</strong> The next single draft stays centred on this entry’s event or sequence. There is no extra focus setting for this prose type.</p>';
    return `<details class="ws-focus-options"><summary>Optional focus for the next single draft</summary><p>Choose what the next draft below should emphasise. Automatic selection favours a compatible focus used less recently. This affects “Generate one draft”, not the improvement test or saved writing instructions.</p><label>Emphasis<select data-ws-focus><option value="auto">Choose automatically</option>${options.map(o=>`<option value="${esc(o.value)}"${o.value===S.focus?' selected':''}>${esc(o.label)}</option>`).join('')}</select></label><button data-ws="variation">Choose another automatic focus · free</button></details>`;
  }
  function optimizationPanel() {
    const config=S.optimizations?.configuration || {}, run=S.optimization;
    const bridge=S.optimizations?.bridge, available=!bridge || bridge.online;
    const forms=S.home.forms || [...new Set(S.home.samples.map(s=>s.form))], form=S.optForm || S.sample?.form;
    const hasSample=S.home.samples.some(s=>s.form===form);
    return `<section class="workshop-optimization" data-ws-run="${esc(run?.run_id || '')}"><h3>Improve a whole prose category</h3>
      <p class="ws-purpose">Improve the reusable prompt, guardrails and context so future entries become stronger. Every test generates fresh prose; it does not rewrite the previous drafts.</p>
      <div class="ws-connection-row"><span class="codex-connection ${available?'is-online':'is-offline'}">${available?'● Agents connected':'○ Local connection unavailable'}</span><button data-ws="opt-connection">Check connection</button><button data-ws="opt-personas">${S.personas===false?'Enable':'Disable'} character banter</button></div>
      ${!available?`<p class="workshop-error">Start START JKSIMMONS.vbs and keep Codex open before authorizing writing. ${esc(bridge?.connection_error || '')}</p>`:''}
      <details class="ws-agent-info"><summary>Models and connection</summary><dl><div><dt>JuniorWriter</dt><dd>${esc(config.writer_model || S.home.model)} · ${esc(config.writer_effort || S.home.effort)} effort · external writing provider</dd></div><div><dt>JKSimmons</dt><dd>Your persistent Codex reviewer chat; reviews category guidance and fresh results. <a href="codex://threads/01a17f57-f5bb-7782-bce0-8b3b43dd367f">Open JKSimmons in Codex</a></dd></div><div><dt>StoryTechMan</dt><dd>Your persistent Codex engineer chat; investigates the environment and proposes repairs.</dd></div></dl><p>The local listener wakes an agent only for an actual job. Empty waiting uses no Codex allowance. Agent expressions and banter do not affect scores or prompts.</p></details>
      ${window.NCCEWritingActivity?.render(run,{personas:S.personas!==false}) || ''}
      ${!watching()?`<h4>Start a new category study</h4><label>Complete rounds allowed<select data-ws-opt-rounds>${[1,2,3].map(n=>`<option value="${n}"${n===(S.optRounds || 1)?' selected':''}>${n} complete ${n===1?'round':'rounds'} · up to ${n*4} fresh drafts + ${n*2} pair reviews</option>`).join('')}</select></label><div class="workshop-actions ws-improve-controls"><label>Prose type to improve<select data-ws-opt-form${S.busy || S.optBody?' disabled':''}>${forms.map(f=>`<option value="${esc(f)}"${f===form?' selected':''}${!S.home.samples.some(s=>s.form===f)?' disabled':''}>${esc(formName(f))}</option>`).join('')}</select></label><button data-ws="opt-start"${!available || !hasSample || !S.home.configured || S.busy || running()?' disabled':''}>${S.optBody?'Check submitted study':'Start '+esc(formName(form).toLowerCase())+' study'}</button></div><p class="ws-control-help">One round = two new drafts for each of two entries + one review per pair. Passing learning rounds require fresh-entry validation; nothing is activated without your approval.</p><label>Previous studies<select data-ws-opt-history><option value="">Choose study…</option>${(S.optimizations?.runs || []).map(r=>`<option value="${esc(r.run_id)}"${r.run_id===run?.run_id?' selected':''}>${esc(formName(r.form))} · ${esc(({budget_exhausted:'Awaiting your decision',awaiting_next_round:'Awaiting your decision',escalated:'Setup investigation needed'})[r.status] || r.status.replaceAll('_',' '))} · ${esc(r.created_at)}</option>`).join('')}</select></label>`:`<div class="ws-running"><p role="status">${optimizing()?'Category study in progress':'StoryTechMan is working on this study'}. Your authorized writing limit does not increase automatically.</p>${optimizing()?'<button data-ws="opt-stop">Stop after the current request</button>':''}</div>`}
      ${run?`${decisionPanel(run)}<div class="ws-results">${(run.rounds || []).map(round=>`<details class="ws-round"${round===run.rounds.at(-1)?' open':''}><summary>${round.kind==='validation'?'Validation':'Learning'} round ${round.number} · ${round.pairs.length} test ${round.pairs.length===1?'entry':'entries'}</summary>${round.pairs.map(reviewPair).join('')}</details>`).join('')}</div>
      ${run.status==='awaiting_approval'?`<section class="ws-decision"><h4>The category setup passed validation</h4><p>The unchanged prompt passed on fresh entries. Your approval activates the tested setup for future writing; existing prose stays unchanged.</p><details><summary>Review the exact instructions to activate</summary><h5>Shared craft</h5><pre>${esc(run.shared.instructions)}</pre><h5>Category brief</h5><pre>${esc(run.specific.instructions)}</pre></details><div class="workshop-actions"><button data-ws="opt-approve">Approve tested setup for future NCCE writing</button><button data-ws="opt-reject">Reject this setup</button></div></section>`:''}
      ${run.prompt_history?.length?`<details class="ws-prompt-changes"><summary>Category prompt changes · ${run.prompt_history.length} saved revisions</summary>${run.prompt_history.map(p=>`<details><summary>Proposed after learning round ${p.after_round}</summary><pre>${esc(p.instructions)}</pre></details>`).join('')}</details>`:''}
      <details><summary>Complete study report · instructions, context and audit</summary><pre>${esc(JSON.stringify(run,null,2))}</pre></details>`:''}</section>`;
  }
  async function pollOptimization() {
    try {
      S.optimization=await request('/api/workshop/optimization?run_id='+encodeURIComponent(S.optimization.run_id)); paint();
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
    const openDetails=new Map([...(root?.querySelectorAll?.('details') || [])].map(d=>[detailKey(d),d.open]));

    if (!visible()) return;
    const h=S.home, list=h.samples.filter(item=>!S.search || (item.label+' '+item.form).toLowerCase().includes(S.search.toLowerCase()));
    if (S.sample && !list.some(x=>x.key===S.sample.key)) list.unshift({key:S.sample.key,label:S.sample.label,form:S.sample.form});
    root.innerHTML=`<section class="writer-workshop"><div class="eyebrow">Editorial desk</div><h2>Writer Workshop</h2><p>Shape the writer directly: edit instructions, test one entry, revise the prose and save examples you approve.</p><p class="muted">Saving, importing, editing and inspecting are free. Generate sends one request. Activating a revision affects future writing; it does not rewrite existing entries.</p>
      <p role="status" id="ws-status">${esc(S.message)}</p>
      ${optimizationPanel()}

      <div class="workshop-source"><label>Find an entry<input type="search" data-ws-search value="${esc(S.search || '')}" placeholder="Fighter, gang, place, writing form…"></label><label>Sample<select data-ws-sample>${list.map(item=>`<option value="${esc(item.key)}"${item.key===S.sample?.key?' selected':''}>${esc(item.label)} · ${esc(item.form.replaceAll('_',' '))}</option>`).join('')}</select></label><button data-ws="sources">Refresh source list · free</button></div>
      ${S.sample?`<p><strong>${esc(S.sample.label)}</strong> · ${esc(S.sample.form.replaceAll('_',' '))}</p><details><summary>Read-only evidence and context for the next request</summary><pre>${esc(JSON.stringify(S.sample.packet,null,2))}</pre></details>
      <fieldset class="workshop-policies"${S.busy || running()?' disabled':''}>${policyEditor('shared','Shared writing craft · all forms')}${policyEditor('specific','This writing form')}</fieldset>
      ${draftFocus()}
      <div class="workshop-actions"><button data-ws="inspect">Inspect exact next instructions and plan · free</button><button data-ws="import">Import selected sample for editing · free</button><button data-ws="generate"${!h.configured || S.busy || running()?' disabled':''}>${S.busy || running()?'Generation in progress…':'Generate one draft · 1 API call'}</button></div>
      ${S.inspection?`<details open><summary>Next request · saved draft instructions</summary><p>Approximately ${Math.ceil((S.inspection.instructions.length+JSON.stringify(S.inspection.packet).length)/4)} input tokens before API overhead; estimate only.</p><p><strong>${esc(S.inspection.packet.creative_plan?.focus_label || 'Recorded event')}</strong> · this plan is saved for the next request.</p>${S.inspection.packet.rulebook_context?`<p>Rulebook: ${esc(S.inspection.packet.rulebook_context.source?.title || 'Unverified type')} ${esc(S.inspection.packet.rulebook_context.source?.printed_page ? '· p. '+S.inspection.packet.rulebook_context.source.printed_page : '')}</p>`:''}<pre>${esc(S.inspection.instructions)}</pre><details><summary>Exact context, reference and recent-pattern hints</summary><pre>${esc(JSON.stringify(S.inspection.packet,null,2))}</pre></details></details>`:''}`:'<p>No generated entries are available to test.</p>'}
      <section class="workshop-history"><h3>Workshop samples</h3><label>Open a previous trial or imported sample<select data-ws-trial><option value="">Choose saved sample…</option>${h.trials.map(t=>`<option value="${esc(t.trial_id)}"${t.trial_id===S.trial?.trial_id?' selected':''}>${esc(t.label)} · ${esc(t.status)} · ${esc(t.created_at)}</option>`).join('')}</select></label></section>${trialPanel()}</section>`;
    for(const d of root.querySelectorAll?.('details') || []){const key=detailKey(d);if(openDetails.has(key))d.open=openDetails.get(key);}
    S.pendingPaint=false;
  }
  async function selectSample(key) {
    S.sample=await request('/api/workshop/sample?key='+encodeURIComponent(key));
    if(!S.optForm)S.optForm=S.sample.form;
    const meta=await request('/api/workshop/policy?scope='+encodeURIComponent(S.sample.form));
    S.specificMeta=meta; S.specific=clone(meta.draft); S.inspection=null; S.planKey=null; S.focus='auto'; S.variation=0;
    paint();
  }
  async function savePolicy(which) {
    const item=S[which];
    if (!item.revision_id || item.dirty) {
      const saved=await post('save-policy',item);
      S[which]={...saved,dirty:false}; S[which+'Meta']=await request('/api/workshop/policy?scope='+encodeURIComponent(item.scope));
    }
    return S[which].revision_id;
  }
  async function prepared() {
    return {sample_key:S.sample.key,packet_hash:S.sample.packet_hash,shared_revision_id:await savePolicy('shared'),form_revision_id:await savePolicy('specific'),focus:S.focus || 'auto',variation:S.variation || 0,plan_key:S.planKey || null};
  }
  async function preparedOptimization() {
    const form=S.optForm || S.sample?.form, seed=S.repairSeed?.form===form?S.repairSeed:null;
    const entry=S.home.samples.find(s=>s.form===form);
    if(!entry)throw new Error('No sourced entries are available for this prose type.');
    const sample=form===S.sample?.form?S.sample:await request('/api/workshop/sample?key='+encodeURIComponent(entry.key));
    const specificMeta=await request('/api/workshop/policy?scope='+encodeURIComponent(form));
    const sharedMeta=await request('/api/workshop/policy?scope=shared');
    let specific,shared;
    if(seed?.specific)specific=seed.specific;
    else if(form===S.sample?.form && S.specific?.dirty)specific=await savePolicy('specific');
    else specific=specificMeta.draft.revision_id || (await post('save-policy',specificMeta.draft)).revision_id;
    if(seed?.shared)shared=seed.shared;
    else if(S.shared?.dirty)shared=await savePolicy('shared');
    else shared=sharedMeta.draft.revision_id || (await post('save-policy',sharedMeta.draft)).revision_id;
    return {sample_key:sample.key,packet_hash:sample.packet_hash,shared_revision_id:shared,form_revision_id:specific,focus:'auto',variation:0,plan_key:null};
  }
  async function pollTrial() {
    try {
      const latest=await request('/api/workshop/trial?trial_id='+encodeURIComponent(S.trial.trial_id));
      setEditor(latest); paint();
      if (running()) setTimeout(pollTrial,1800);
      else {S.requestKey=null; S.requestBody=null; S.busy=false; S.home=await request('/api/workshop'); paint();}
    } catch (error) { S.message=error.message+' Reload this saved trial to check its result; no new call was made.'; S.busy=false; paint(); }
  }
  async function action(button) {
    const which=button.dataset.which;
    switch(button.dataset.ws) {
      case 'opt-connection': S.optimizations=await request('/api/workshop/optimizations');S.message=S.optimizations.bridge?.online?'Codex companion is connected.':'Codex companion is offline; no writer calls will start.';break;
      case 'opt-personas': S.personas=S.personas===false;break;
      case 'opt-start': {
        if(S.busy || watching() || running()) return;
        const rounds=S.optRounds || 1;
        if(!S.optBody && !window.confirm(`Test the reusable ${formName(S.optForm || S.sample?.form).toLowerCase()} setup on fresh entries with up to ${rounds*4} paid JuniorWriter calls and ${rounds*2} reviews in your JKSimmons Codex chat? Codex usage limits apply. There are no external reviewer API calls. The run stops on technical issues and never activates instructions automatically.`)) {paint();return;}
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
        if(approve){const specific=S.specific,shared=S.shared;S.sharedMeta=await request('/api/workshop/policy?scope=shared');S.home=await request('/api/workshop');await selectSample(S.sample.key);if(specific?.dirty)S.specific=specific;if(shared?.dirty)S.shared=shared;}
        S.message=approve?'Tested setup activated for future NCCE writing.':'Candidate rejected. Active setup unchanged.';break;
      }
      case 'preset': S[which]={...clone(S[which+'Meta'][button.dataset.preset]),dirty:true}; S.inspection=null; S.message='Preset loaded as a draft. Future writing is unchanged.'; break;
      case 'save': await savePolicy(which); S.message='Draft saved. No API call; active instructions unchanged.'; break;
      case 'activate': {
        const id=await savePolicy(which), meta=S[which+'Meta'];
        S[which+'Meta']=await post('activate',{scope:S[which].scope,revision_id:id,expected_active:meta.active?.revision_id || null});
        S.message='Saved revision activated for future writing. Existing campaign prose was not regenerated.'; break;
      }
      case 'builtin': {
        S[which+'Meta']=await post('activate',{scope:S[which].scope,revision_id:null,expected_active:S[which+'Meta'].active?.revision_id || null});
        S.message='Built-in instructions restored for future writing. Your saved revisions remain available.'; break;
      }
      case 'variation': S.variation=(S.variation || 0)+1; S.planKey=null; // fall through: free inspection
      case 'inspect': S.inspection=await post('preview',await prepared()); S.planKey=S.inspection.plan_key; S.message='Exact instructions, reference and saved creative plan shown below. No provider request.'; break;
      case 'import': setEditor(await post('import',{sample_key:S.sample.key})); S.home=await request('/api/workshop'); S.message='Existing sample imported. Edit it below; no provider request.'; break;
      case 'generate': {
        if (S.busy || running() || optimizing()) return;
        S.busy=true; S.message='Sending one generation request…'; paint();
        try {
          if (!S.requestBody) S.requestBody={...await prepared(),request_key:crypto.randomUUID()};
          setEditor(await post('generate',S.requestBody));
          S.message='One request queued. Closing or reloading this page will not start another.';
          setTimeout(pollTrial,800);
        } catch(error) {
          S.busy=false;
          if (error.status && error.status<500) {S.requestBody=null;S.requestKey=null;}
          else error.message+=' The next Generate click checks this same request rather than sending a duplicate.';
          throw error;
        }
        break;
      }
      case 'save-edit': setEditor(await post('edit',{trial_id:S.trial.trial_id,...S.edit})); S.message='Edited sample saved in workshop history. Campaign canon and prose are unchanged.'; break;
      case 'load-edit': {
        const saved=S.trial.edits.find(e=>e.edit_id===button.dataset.edit);
        S.edit={body:saved.document.blocks.filter(b=>b.type==='body_paragraph').map(b=>b.text).join('\n\n'),composition:{...saved.document.composition}};
        S.message='Earlier edit loaded. Save to create a new edit revision.'; break;
      }
      case 'example': {
        if (!S.trial.edits?.length) throw new Error('Save your edited sample first.');
        if (S.trial.form!==S.sample.form) throw new Error('Select a sample with the same writing form before adding this example.');
        const doc=S.trial.edits[0].document, fact=S.trial.packet.mechanical_evidence || S.trial.packet.evidence || S.trial.packet.event || {};
        const excerpt=(doc.blocks || []).map(b=>b.type==='internal_note'?(b.text+': '+(b.blocks || []).map(c=>c.text).join(' ')):b.text).filter(Boolean).join('\n\n');
        const addition='\n\nOWNER-EDITED STYLE EXAMPLE — illustrate craft only; these facts belong to this example.\nInput: '+JSON.stringify(fact)+'\nOutput:\n'+(doc.composition?.heading || '')+'\n'+excerpt;
        if ((S.specific.examples+addition).length>8000) throw new Error('Examples would exceed 8,000 characters. Remove an older example first.');
        S.specific.examples+=addition; S.specific.dirty=true; await savePolicy('specific');
        S.message='Saved edit added to this form’s draft examples. Activate the revision explicitly when ready.'; break;
      }
      case 'export': {
        const text='# NCCE workshop sample\n\n'+S.trial.label+'\n\n## Instructions used\n\n'+S.trial.instructions+'\n\n## Evidence and context\n\n'+JSON.stringify(S.trial.packet,null,2)+'\n\n## Edited document fields\n\n'+JSON.stringify(S.edit.composition,null,2)+'\n\n## Edited sample\n\n'+(S.edit.body || '');
        const url=URL.createObjectURL(new Blob([text],{type:'text/markdown;charset=utf-8'}));
        const anchor=document.createElement('a'); anchor.href=url; anchor.download=S.trial.trial_id+'.md'; anchor.click(); URL.revokeObjectURL(url); S.message='Sample exported. No provider request.'; break;
      }
      case 'sources': S.home=await request('/api/workshop'); S.message='Source list refreshed. Draft text preserved.'; break;
    }
    paint();
  }
  function bind() {
    if (root.dataset.workshopBound) return;
    root.dataset.workshopBound='1';
    root.addEventListener('focusout',()=>{if(S.pendingPaint)setTimeout(()=>paint(),0);});
    root.addEventListener('click',event=>{const b=event.target.closest('[data-ws]');if(b){b.disabled=true;action(b).catch(error=>{S.message=error.message;paint();});}});
    root.addEventListener('input',event=>{
      const t=event.target;
      if(t.hasAttribute('data-ws-tech-note'))S.techNote=t.value;
      if(t.dataset.wsPolicy) { S[t.dataset.wsPolicy][t.dataset.field]=t.value;S[t.dataset.wsPolicy].dirty=true;S.inspection=null; }
      if(t.hasAttribute('data-ws-body')) S.edit.body=t.value;
      if(t.dataset.wsComposition) S.edit.composition[t.dataset.wsComposition]=t.value;
      if(t.hasAttribute('data-ws-body') || t.dataset.wsComposition) {const p=root.querySelector('#ws-edited-preview');if(p)p.innerHTML=drawDocument(editedDocument());}
      if(t.hasAttribute('data-ws-search')) {
        S.search=t.value;
        const select=root.querySelector('[data-ws-sample]');
        const choices=S.home.samples.filter(x=>(x.label+' '+x.form).toLowerCase().includes(t.value.toLowerCase()));
        select.innerHTML='<option value="">Choose matching entry…</option>'+choices.map(x=>`<option value="${esc(x.key)}">${esc(x.label)} · ${esc(x.form)}</option>`).join('');
      }
    });
    root.addEventListener('change',event=>{
      const t=event.target;
      let task;
      if(t.hasAttribute('data-ws-focus')) {S.focus=t.value;S.planKey=null;S.inspection=null;paint();}
      if(t.hasAttribute('data-ws-opt-form') && !S.optBody && !optimizing()) {S.optForm=t.value;S.repairSeed=null;paint(true);}
      if(t.hasAttribute('data-ws-opt-rounds')) {S.optRounds=Number(t.value);paint(true);}
      if(t.hasAttribute('data-ws-opt-history') && t.value) task=request('/api/workshop/optimization?run_id='+encodeURIComponent(t.value)).then(run=>{if(S.optimization?.run_id!==run.run_id){S.continueBody=null;S.repairSeed=null;}S.optimization=run;paint();if(watching())setTimeout(pollOptimization,1000);});
      if(t.hasAttribute('data-ws-sample') && t.value) task=selectSample(t.value);
      if(t.dataset.wsHistory && t.value) {const which=t.dataset.wsHistory;S[which]=clone(S[which+'Meta'].history.find(r=>r.revision_id===t.value));paint();}
      if(t.hasAttribute('data-ws-trial') && t.value) task=request('/api/workshop/trial?trial_id='+encodeURIComponent(t.value)).then(item=>{setEditor(item);paint();if(running())pollTrial();});
      task?.catch(error=>{S.message=error.message;paint();});
    });
  }
  async function open(container,api,blocks) {
    root=container; request=api; drawDocument=blocks; bind();
    root.innerHTML='<section class="writer-workshop"><h2>Writer Workshop</h2><p>Opening the editorial desk…</p></section>';
    try {
      if(!S.home) {
        S.home=await request('/api/workshop'); S.sharedMeta=await request('/api/workshop/policy?scope=shared');S.shared=clone(S.sharedMeta.draft);
        S.optimizations=await request('/api/workshop/optimizations');
        const active=S.optimizations.runs.find(r=>['queued','running'].includes(r.status) || ['queued','investigating','repair_queued','repairing','release_queued','releasing'].includes(r.tech?.status));
        const pending=active || S.optimizations.runs.find(r=>['awaiting_next_round','budget_exhausted','awaiting_samples','escalated'].includes(r.status) || ['proposal_ready','repair_ready','released','needs_input'].includes(r.tech?.status));
        if(pending){S.optimization=pending;S.optForm=pending.form;}
        if(active)setTimeout(pollOptimization,1000);
        const initial=S.home.samples.find(s=>s.key==='comparison:1:0') || S.home.samples[0];
        if(initial) await selectSample(initial.key);
      }
      paint();
    } catch(error) {if(visible())root.innerHTML='<section class="writer-workshop"><h2>Writer Workshop</h2><p role="alert">'+esc(error.message)+'</p></section>';}
  }
  return {open};
})();
