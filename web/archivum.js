'use strict';
// Presentation only. No provider calls, source mutations or timeline hooks.
window.NCCEArchive = (() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels = {chronicle:'Campaign Chronicle',gangs:'Gang records',fighters:'Fighter records',places:'Territorial archive',battles:'Engagement records',archive:'Authored archive',workshop:'Writer Workshop',retrieval:'Writing context',system:'System records'};
  function browser(view, rows) {
    const kind = {gangs:'gang',fighters:'fighter',places:'territory',battles:'battle',archive:'archive'}[view];
    return `<div class="record-browser"><section class="record-index" aria-label="${escape(labels[view])} index"><div class="index-heading">RECORD INDEX <span>${rows.length}</span></div>${rows.map((r,i)=> {
      const id=r.gang_id && view==='gangs'?r.gang_id:r.id;
      const title=view==='gangs'?r.name:view==='places'?r.territory:view==='battles'?(r.scenario || 'Engagement')+(r.territory?' — '+r.territory:''):r.name || r.title;
      const sub=view==='gangs'?r.gang_type:view==='fighters'?[r.gang_name,r.class].filter(Boolean).join(' · '):view==='places'?r.gang_name:view==='battles'?[r.attacker,r.defender].filter(Boolean).join(' / '):'Authored campaign story';
      return `<button class="record-index-entry" data-${kind}="${escape(id)}" aria-pressed="false"><span class="index-number">${String(i+1).padStart(2,'0')}</span><span><strong>${escape(String(title||'Record').replace('THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','C-NINE'))}</strong><small>${escape(String(sub||'').replace('THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]','C-NINE'))}</small>${view==='fighters'?`<em>${escape(r.status||'Unknown')}</em>`:view==='battles'&&r.date?`<em>${escape(NCCEWriting.formatDate(r.date).imperialDisplay)}</em>`:''}</span><span class="index-arrow" aria-hidden="true">↗</span></button>`;
    }).join('')}</section><section class="record-preview" aria-label="Document preview"><div class="preview-placeholder"><span class="archive-monogram" aria-hidden="true">N / C</span><h3>Select a record</h3><p>Open a dossier from the index.</p></div></section></div>`;
  }
  function present(outlet, body, meta) {
    const stamp = meta.date ? NCCEWriting.formatDate(meta.date) : {imperialDisplay:'Undated record',realDisplay:''};
    const id=String(meta.id);
    outlet.innerHTML=`<div class="document-toolbar"><span>DOCUMENT PREVIEW</span><code>NCCE / ${escape(meta.kind.toUpperCase())} / ${escape(id)}</code></div><div class="document-tabs" role="tablist" aria-label="Record layers"><button id="recordNarrativeTab" type="button" role="tab" aria-selected="true" aria-controls="recordNarrative" data-record-layer="narrative">Narrative record</button><button id="recordSourceTab" type="button" role="tab" aria-selected="false" aria-controls="recordSources" data-record-layer="sources" tabindex="-1">Data &amp; sources</button></div><section id="recordNarrative" role="tabpanel" aria-labelledby="recordNarrativeTab"><div class="document-notices" role="status"></div><div class="archive-paper"><div class="paper-metadata"><span>CAMPAIGN ARCHIVE · ${escape(meta.kind.toUpperCase())}</span><span>${escape(stamp.imperialDisplay)}</span></div><div class="paper-content">${body}</div><div class="paper-end"><span class="document-stamp">NCCE<br><small>ARCHIVE COPY</small></span><span>// RECORD ENDS //</span></div></div></section><section id="recordSources" role="tabpanel" aria-labelledby="recordSourceTab" class="record-source-panel" hidden><h3>Data &amp; sources</h3><p class="muted">Source information and application metadata. These are separate from the narrative.</p><dl class="source-register">${[['Record',id],['Source',meta.source||'Campaign record'],...(meta.fields||[]),...(stamp.realDisplay?[['Real-world date',stamp.realDisplay]]:[])].map(([k,v])=>`<div><dt>${escape(k)}</dt><dd>${escape(v ?? 'Not recorded')}</dd></div>`).join('')}</dl><div class="source-evidence"></div></section><div class="document-caption"><span>${escape(meta.title)}</span><span>${escape(meta.source||'Campaign record')}</span></div>`;
    // Move existing rendered evidence, never alter its wording or source data.
    const evidence=outlet.querySelector('.source-evidence');
    outlet.querySelectorAll('.paper-content .voice-profile, .paper-content .identity-editor').forEach(el=>evidence.append(el));
    outlet.querySelectorAll('.paper-content .evidence, .paper-content .mechanics-fold, .paper-content .authored-source, .paper-content .writer-check, .paper-content .narrative > .eyebrow').forEach(el=>evidence.append(el));
    outlet.querySelectorAll('.paper-content .writer-pending').forEach(el=>outlet.querySelector('.document-notices').append(el));
    const app=document.querySelector('#app');
    app.querySelectorAll('.record-index-entry').forEach(button=>{
      const selected=button.dataset[meta.kind]===id;
      button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));
    });
  }
  function layer(button) {
    const root=button.closest('.record-preview') || button.closest('.standalone-record');
    if(!root)return;
    root.querySelectorAll('[data-record-layer]').forEach(tab=>{const selected=tab===button;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;});
    root.querySelector('#recordNarrative').hidden=button.dataset.recordLayer!=='narrative';
    root.querySelector('#recordSources').hidden=button.dataset.recordLayer!=='sources';
  }
  document.addEventListener('click',e=>{const tab=e.target.closest('[data-record-layer]');if(tab)layer(tab);});
  document.addEventListener('keydown',e=>{
    const tab=e.target.closest('[data-record-layer]');if(!tab||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
    e.preventDefault();const tabs=[...tab.parentElement.querySelectorAll('[data-record-layer]')];
    const next=e.key==='Home'?tabs[0]:e.key==='End'?tabs.at(-1):tabs[1-tabs.indexOf(tab)];layer(next);next.focus();
  });
  const toggle=document.querySelector('.section-toggle'),sidebar=document.querySelector('.archive-sidebar');
  toggle.addEventListener('click',()=>{const open=toggle.getAttribute('aria-expanded')!=='true';toggle.setAttribute('aria-expanded',String(open));sidebar.classList.toggle('sections-open',open);});
  document.querySelectorAll('#sectionNav [data-view]').forEach(button=>button.addEventListener('click',()=>{toggle.setAttribute('aria-expanded','false');sidebar.classList.remove('sections-open');}));
  const app=document.querySelector('#app');
  function deskNavigation() {
    if(!['workshop','retrieval'].includes(app.dataset.view))return;
    const desk=app.querySelector('.writer-workshop');
    if(!desk || desk.querySelector('.desk-navigation'))return;
    const headings=[...desk.querySelectorAll('h3')].filter(h=>!h.closest('details')).slice(0,8);
    if(!headings.length)return;
    const nav=document.createElement('nav');nav.className='desk-navigation';nav.setAttribute('aria-label','Desk sections');
    nav.innerHTML='<span>DESK INDEX</span>'+headings.map((h,i)=>{h.id='desk-section-'+i;return `<button type="button" data-desk-target="${h.id}">${String(i+1).padStart(2,'0')} / ${escape(h.textContent)}</button>`;}).join('');
    const title=desk.querySelector('h2');
    (title || desk.firstElementChild).after(nav);
  }
  document.addEventListener('click',e=>{const b=e.target.closest('[data-desk-target]');if(b){const target=document.getElementById(b.dataset.deskTarget);target?.scrollIntoView({block:'start'});target?.setAttribute('tabindex','-1');target?.focus({preventScroll:true});}});
  new MutationObserver(()=>{
    const view=app.dataset.view || 'chronicle';
    document.querySelector('.site-header h1').textContent=labels[view]||'Campaign Chronicle';
    document.querySelectorAll('#sectionNav [data-view]').forEach(button=>{if(button.dataset.view===view)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});
    deskNavigation();
  }).observe(app,{attributes:true,attributeFilter:['data-view'],childList:true,subtree:true});
  return {browser,present};
})();
