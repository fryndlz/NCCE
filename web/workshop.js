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
  function optimizationPanel() {
    const config=S.optimizations?.configuration || {}, run=S.optimization;
    const bridge=S.optimizations?.bridge, available=!bridge || bridge.online;
    return `<section class="workshop-optimization"><h3>Improve NCCE's writing setup</h3>
      <p class="codex-connection ${available?'is-online':'is-offline'}">${available?'● Codex reviewer connected':'○ Codex reviewer offline'} · JKSimmons — NCCE Writing Reviewer</p><p class="muted">${available?'Reviews go to your actual Codex chat, using its context and saved standards. When the chat worker is enabled, it checks the queue about every five minutes; keep Codex open.':'Automated writing is paused until the actual reviewer connection passes its test. Your computer must remain on for Codex reviews.'} No reviewer API fallback.</p>${!available && bridge?.connection_error?`<p class="muted">Connection check: ${esc(bridge.connection_error)}</p>`:''}
      <div class="workshop-actions"><button data-ws="opt-connection">Check Codex connection</button><button data-ws="opt-personas">${S.personas===false?'Enable':'Disable'} character banter</button></div>
      ${window.NCCEWritingActivity?.render(run,{personas:S.personas!==false}) || ''}
      <p>JuniorWriter tries two drafts on each of two independent entries. JKSimmons reviews both pairs and revises the form guidance between rounds. Context or pipeline problems stop the run for you and StoryTechMan.</p>
      <p>Writer: ${esc(config.writer_model || S.home.model)} · Reviewer: ${esc(config.reviewer_model || S.home.model)}. Candidate instructions remain inactive until you approve the tested setup.</p>
      <label>Maximum rounds<select data-ws-opt-rounds${optimizing()?' disabled':''}>${[1,2,3].map(n=>`<option value="${n}"${n===(S.optRounds || 1)?' selected':''}>${n} · up to ${n*4} writing calls + ${n*2} Codex reviews</option>`).join('')}</select></label>
      <div class="workshop-actions"><button data-ws="opt-start"${!available || !S.sample || !S.home.configured || S.busy || running() || optimizing()?' disabled':''}>${S.optBody?'Check submitted run':'Improve this prose form'}</button>${optimizing()?'<button data-ws="opt-stop">Stop after current request</button>':''}</div>
      <label>Previous improvement runs<select data-ws-opt-history><option value="">Choose run…</option>${(S.optimizations?.runs || []).map(r=>`<option value="${esc(r.run_id)}">${esc(r.form.replaceAll('_',' '))} · ${esc(r.status)} · ${esc(r.created_at)}</option>`).join('')}</select></label>
      ${run?`<p role="status"><strong>${esc(run.status.replaceAll('_',' '))}</strong> · ${esc(run.form.replaceAll('_',' '))}<br>${esc(run.message)}</p><p>Reserved request slots: ${run.writer_reserved}/${run.writer_limit} writer, ${run.reviewer_reserved}/${run.reviewer_limit} reviewer.</p>
      <details><summary>Tested form instructions</summary><pre>${esc(run.specific.instructions)}</pre><p>Shared revision: ${esc(run.shared.label)}</p><pre>${esc(run.shared.instructions)}</pre></details>
      ${(run.rounds || []).map(round=>`<details${round===run.rounds.at(-1)?' open':''}><summary>Round ${round.number}</summary>${round.pairs.map(pair=>`<h4>${esc(pair.label)}</h4>${pair.candidates.map((candidate,i)=>`<details><summary>Draft ${i?'B':'A'} · ${esc(candidate.status)}</summary>${drawDocument(candidate.document)}</details>`).join('')}${pair.review?`<p><strong>JKSimmons:</strong> ${esc(pair.review.summary)}</p>${pair.review.candidates.map(c=>`<p>Draft ${c.index?'B':'A'}: ${esc(c.overall)}/10 · ${Object.entries(c.scores).map(([k,v])=>`${esc(k.replaceAll('_',' '))}: ${esc(v)}`).join(' · ')}</p>${c.issues.map(issue=>`<p role="alert"><strong>${esc(issue.category)}:</strong> ${esc(issue.explanation)}<br>Evidence: ${esc(issue.evidence)}</p>`).join('')}`).join('')}`:''}`).join('')}</details>`).join('')}
      ${run.status==='awaiting_approval'?'<div class="workshop-actions"><button data-ws="opt-approve">Approve tested setup for future NCCE writing</button><button data-ws="opt-reject">Reject this setup</button></div>':''}
      <details><summary>StoryTechMan handoff and run history</summary><p>${esc(run.coverage)}</p><p>${esc(run.reviewer_context)}</p>${run.events.map(e=>`<p>${esc(e.at)} · ${esc(e.message)}</p>`).join('')}</details><details><summary>Complete run report · exact prompts, context and results</summary><pre>${esc(JSON.stringify(run,null,2))}</pre></details>`:''}</section>`;
  }
  async function pollOptimization() {
    try {
      S.optimization=await request('/api/workshop/optimization?run_id='+encodeURIComponent(S.optimization.run_id)); paint();
      if(optimizing()) setTimeout(pollOptimization,1500);
      else {S.optBody=null; S.optimizations=await request('/api/workshop/optimizations'); paint();}
    } catch(error) {S.message=error.message+' Reopen the saved improvement run to check it; no new calls were made.';paint();}
  }
  function paint() {
    if (!visible()) return;
    const h=S.home, list=h.samples.filter(item=>!S.search || (item.label+' '+item.form).toLowerCase().includes(S.search.toLowerCase()));
    if (S.sample && !list.some(x=>x.key===S.sample.key)) list.unshift({key:S.sample.key,label:S.sample.label,form:S.sample.form});
    root.innerHTML=`<section class="writer-workshop"><div class="eyebrow">Editorial desk</div><h2>Writer Workshop</h2><p>Shape the writer directly: edit instructions, test one entry, revise the prose and save examples you approve.</p><p class="muted">Saving, importing, editing and inspecting are free. Generate sends one request. Activating a revision affects future writing; it does not rewrite existing entries.</p>
      <p role="status" id="ws-status">${esc(S.message)}</p><p>${esc(h.model)} · ${esc(h.effort)} effort · one-call limit per generation</p>
      ${optimizationPanel()}
      <details><summary>Your comparison feedback and prompt identities</summary>${h.review.map(r=>`<p><strong>${esc(r.label)}</strong>: ${esc(r.note)}<br>A: ${esc(r.versions.A)}; B: ${esc(r.versions.B)}. ${r.verdict==='neither'?'Neither approved.':'A preferred; not automatically added as an example.'}</p>`).join('')}</details>
      <div class="workshop-source"><label>Find an entry<input type="search" data-ws-search value="${esc(S.search || '')}" placeholder="Fighter, gang, place, writing form…"></label><label>Sample<select data-ws-sample>${list.map(item=>`<option value="${esc(item.key)}"${item.key===S.sample?.key?' selected':''}>${esc(item.label)} · ${esc(item.form.replaceAll('_',' '))}</option>`).join('')}</select></label><button data-ws="sources">Refresh source list · free</button></div>
      ${S.sample?`<p><strong>${esc(S.sample.label)}</strong> · ${esc(S.sample.form.replaceAll('_',' '))}</p><details><summary>Read-only evidence and context for the next request</summary><pre>${esc(JSON.stringify(S.sample.packet,null,2))}</pre></details>
      <fieldset class="workshop-policies"${S.busy || running()?' disabled':''}>${policyEditor('shared','Shared writing craft · all forms')}${policyEditor('specific','This writing form')}</fieldset>
      <fieldset${S.busy || running()?' disabled':''}><legend>Creative plan · free</legend><label>Focus for this entry<select data-ws-focus><option value="auto">${(h.focus_options?.[S.sample.form] || []).length>1?'Choose a less-used compatible focus':'Keep the recorded event or sequence central'}</option>${(h.focus_options?.[S.sample.form] || []).map(o=>`<option value="${esc(o.value)}"${o.value===S.focus?' selected':''}>${esc(o.label)} · pin for this entry</option>`).join('')}</select></label><p class="muted">A focus is inspiration. Recorded events stay central. It changes no facts or saved writing instructions.</p>${(h.focus_options?.[S.sample.form] || []).length>1?'<button data-ws="variation">Try another plan · free</button>':''}</fieldset>
      <div class="workshop-actions"><button data-ws="inspect">Inspect exact next instructions and plan · free</button><button data-ws="import">Import selected sample for editing · free</button><button data-ws="generate"${!h.configured || S.busy || running()?' disabled':''}>${S.busy || running()?'Generation in progress…':'Generate one draft · 1 API call'}</button></div>
      ${S.inspection?`<details open><summary>Next request · saved draft instructions</summary><p>Approximately ${Math.ceil((S.inspection.instructions.length+JSON.stringify(S.inspection.packet).length)/4)} input tokens before API overhead; estimate only.</p><p><strong>${esc(S.inspection.packet.creative_plan?.focus_label || 'Recorded event')}</strong> · this plan is saved for the next request.</p>${S.inspection.packet.rulebook_context?`<p>Rulebook: ${esc(S.inspection.packet.rulebook_context.source?.title || 'Unverified type')} ${esc(S.inspection.packet.rulebook_context.source?.printed_page ? '· p. '+S.inspection.packet.rulebook_context.source.printed_page : '')}</p>`:''}<pre>${esc(S.inspection.instructions)}</pre><details><summary>Exact context, reference and recent-pattern hints</summary><pre>${esc(JSON.stringify(S.inspection.packet,null,2))}</pre></details></details>`:''}`:'<p>No generated entries are available to test.</p>'}
      <section class="workshop-history"><h3>Workshop samples</h3><label>Open a previous trial or imported sample<select data-ws-trial><option value="">Choose saved sample…</option>${h.trials.map(t=>`<option value="${esc(t.trial_id)}"${t.trial_id===S.trial?.trial_id?' selected':''}>${esc(t.label)} · ${esc(t.status)} · ${esc(t.created_at)}</option>`).join('')}</select></label></section>${trialPanel()}</section>`;
  }
  async function selectSample(key) {
    S.sample=await request('/api/workshop/sample?key='+encodeURIComponent(key));
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
        if(S.busy || optimizing() || running()) return;
        const rounds=S.optRounds || 1;
        if(!S.optBody && !window.confirm(`Improve this prose form with up to ${rounds*4} paid JuniorWriter calls and ${rounds*2} reviews in your JKSimmons Codex chat? Codex usage limits apply. There are no external reviewer API calls. The run stops on technical issues and never activates instructions automatically.`)) {paint();return;}
        S.busy=true;paint();
        try {
          if(!S.optBody) S.optBody={...await prepared(),request_key:crypto.randomUUID(),max_rounds:rounds,allow_paid:true};
          S.optimization=await post('optimize',S.optBody);
          S.busy=false;if(!optimizing())S.optBody=null;paint();if(optimizing())setTimeout(pollOptimization,1000);
        } catch(error) {S.busy=false;if(error.status>=400 && error.status<500 && ![408,429].includes(error.status))S.optBody=null;throw error;}
        break;
      }
      case 'opt-stop': await post('optimization-stop',{run_id:S.optimization.run_id});S.message='Stop requested. The current request may finish; no further requests will begin.';break;
      case 'opt-approve':
      case 'opt-reject': {
        const approve=button.dataset.ws==='opt-approve';
        if(approve && !window.confirm('Activate the exact tested shared and form instructions for future NCCE generation? Existing campaign prose stays unchanged.'))break;
        S.optimization=await post('optimization-decide',{run_id:S.optimization.run_id,approve});
        S.optimizations=await request('/api/workshop/optimizations');
        if(approve){S.sharedMeta=await request('/api/workshop/policy?scope=shared');S.home=await request('/api/workshop');await selectSample(S.sample.key);}
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
    root.addEventListener('click',event=>{const b=event.target.closest('[data-ws]');if(b){b.disabled=true;action(b).catch(error=>{S.message=error.message;paint();});}});
    root.addEventListener('input',event=>{
      const t=event.target;
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
      if(t.hasAttribute('data-ws-opt-rounds')) {S.optRounds=Number(t.value);paint();}
      if(t.hasAttribute('data-ws-opt-history') && t.value) task=request('/api/workshop/optimization?run_id='+encodeURIComponent(t.value)).then(run=>{S.optimization=run;paint();if(optimizing())setTimeout(pollOptimization,1000);});
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
        const active=S.optimizations.runs.find(r=>['queued','running'].includes(r.status));
        if(active){S.optimization=active;setTimeout(pollOptimization,1000);}
        const initial=S.home.samples.find(s=>s.key==='comparison:1:0') || S.home.samples[0];
        if(initial) await selectSample(initial.key);
      }
      paint();
    } catch(error) {if(visible())root.innerHTML='<section class="writer-workshop"><h2>Writer Workshop</h2><p role="alert">'+esc(error.message)+'</p></section>';}
  }
  return {open};
})();
