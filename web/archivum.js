'use strict';
// Presentation only. No provider calls, source mutations or timeline hooks.
window.NCCEArchive = (() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels = {chronicle:'Campaign Chronicle',gangs:'Gang records',fighters:'Fighter records',places:'Territorial archive',battles:'Engagement records',archive:'Authored archive',system:'System records'};
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
    if(meta.sections)return presentEntity(outlet,meta);
    const stamp = meta.date ? NCCEWriting.formatDate(meta.date) : {imperialDisplay:'Undated record',realDisplay:''};
    const id=String(meta.id);
    outlet.innerHTML=`<div class="document-toolbar"><span>DOCUMENT PREVIEW</span><code>NCCE / ${escape(meta.kind.toUpperCase())} / ${escape(id)}</code></div><div class="document-tabs" role="tablist" aria-label="Record layers"><button id="recordNarrativeTab" type="button" role="tab" aria-selected="true" aria-controls="recordNarrative" data-record-layer="narrative">Narrative record</button><button id="recordSourceTab" type="button" role="tab" aria-selected="false" aria-controls="recordSources" data-record-layer="sources" tabindex="-1">Data &amp; sources</button></div><section id="recordNarrative" role="tabpanel" aria-labelledby="recordNarrativeTab"><div class="document-notices" role="status"></div><div class="archive-paper"><div class="paper-metadata"><span>CAMPAIGN ARCHIVE · ${escape(meta.kind.toUpperCase())}</span><span>${escape(stamp.imperialDisplay)}</span></div><div class="paper-content">${body}</div><div class="paper-end"><span class="document-stamp">NCCE<br><small>ARCHIVE COPY</small></span><span>// RECORD ENDS //</span></div></div></section><section id="recordSources" role="tabpanel" aria-labelledby="recordSourceTab" class="record-source-panel" hidden><h3>Data &amp; sources</h3><p class="muted">Source information and application metadata. These are separate from the narrative.</p><dl class="source-register">${[['Record',id],['Source',meta.source||'Campaign record'],...(meta.fields||[]),...(stamp.realDisplay?[['Real-world date',stamp.realDisplay]]:[])].map(([k,v])=>`<div><dt>${escape(k)}</dt><dd>${escape(v ?? 'Not recorded')}</dd></div>`).join('')}</dl><div class="source-evidence"></div></section><div class="document-caption"><span>${escape(meta.title)}</span><span>${escape(meta.source||'Campaign record')}</span></div>`;
    // Move existing rendered evidence, never alter its wording or source data.
    const evidence=outlet.querySelector('.source-evidence');
    outlet.querySelectorAll('.paper-content .voice-profile, .paper-content .identity-editor').forEach(el=>evidence.append(el));
    outlet.querySelectorAll('.paper-content .evidence, .paper-content .mechanics-fold, .paper-content .authored-source, .paper-content .narrative > .eyebrow').forEach(el=>evidence.append(el));
    outlet.querySelectorAll('.paper-content .writer-pending').forEach(el=>outlet.querySelector('.document-notices').append(el));
    const app=document.querySelector('#app');
    app.querySelectorAll('.record-index-entry').forEach(button=>{
      const selected=button.dataset[meta.kind]===id;
      button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));
    });
  }
  function setLayer(root, id, focus=false) {
    root.querySelectorAll('[data-record-layer]').forEach(tab=>{
      const selected=tab.dataset.recordLayer===id;
      tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;
      if(selected && focus)tab.focus();
      const panel=root.querySelector('#'+tab.getAttribute('aria-controls'));
      if(panel)panel.hidden=!selected;
    });
    root.dataset.activeSection=id;
  }
  function presentEntity(outlet,meta) {
    outlet.dataset.recordKind=meta.kind;
    const identity=meta.kind+':'+meta.id;
    const selected=outlet.dataset.recordIdentity===identity?outlet.dataset.activeSection:'baseline';
    const sections=[...meta.sections,{id:'sources',label:'Data & sources',description:'Mechanical state, provenance, identity tools and source references.',body:`<dl class="source-register">${[['Record',meta.id],['Source',meta.source || 'Campaign record'],...(meta.fields || [])].map(([k,v])=>`<div><dt>${escape(k)}</dt><dd>${escape(v ?? 'Not recorded')}</dd></div>`).join('')}</dl>${meta.sourceBody || ''}<div class="source-evidence"></div>`}];
    const paper=section=>`<div class="document-notices" role="status"></div><div class="archive-paper"><div class="paper-metadata"><span>CAMPAIGN ARCHIVE · ${escape(meta.kind.toUpperCase())}</span><span>${escape(section.paperLabel || 'BASELINE RECORD')}</span></div><div class="paper-content">${section.body}</div><div class="paper-end"><span class="document-stamp">NCCE<br><small>ARCHIVE COPY</small></span><span>// RECORD ENDS //</span></div></div>`;
    outlet.dataset.recordIdentity=identity;
    outlet.innerHTML=`<div class="entity-record-heading"><div><small>${escape(meta.subtitle || meta.kind)}</small><h2>${escape(meta.title)}</h2></div>${meta.status?`<span class="status-pill">${escape(meta.status)}</span>`:''}</div><div class="document-toolbar"><span>RECORD SECTIONS</span><code>NCCE / ${escape(meta.kind.toUpperCase())} / ${escape(meta.id)}</code></div><div class="document-tabs entity-section-tabs" role="tablist" aria-label="Record sections">${sections.map(section=>`<button type="button" id="recordTab-${section.id}" role="tab" aria-selected="false" aria-controls="recordPanel-${section.id}" tabindex="-1" data-record-layer="${section.id}">${escape(section.label)}${section.count!=null?`<span class="section-count">${section.count}</span>`:''}</button>`).join('')}</div>${sections.map(section=>`<section id="recordPanel-${section.id}" role="tabpanel" aria-labelledby="recordTab-${section.id}" class="entity-section-panel${section.paper?' baseline-section':''}${section.id==='sources'?' record-source-panel':''}" hidden><p class="entity-section-description">${escape(section.description || '')}</p>${section.paper?paper(section):`<div class="entity-section-content">${section.body}</div>`}</section>`).join('')}<div class="document-caption"><span>${escape(meta.title)}</span><span>${escape(meta.source || 'Campaign record')}</span></div>`;
    // Baseline provenance belongs to the source layer; per-event evidence stays
    // with its event in an explicit disclosure outside the prose surface.
    const source=outlet.querySelector('.source-evidence');
    outlet.querySelectorAll('.baseline-section .evidence,.baseline-section .authored-source,.baseline-section .narrative > .eyebrow').forEach(el=>source.append(el));
    // Obsolete writer notices are not part of any territory record layer.
    if(meta.kind==='territory') {
      outlet.querySelectorAll('.writer-pending,.document-notices').forEach(el=>el.remove());
      // Imported Markdown uses authored-record; legacy blocks use record-body.
      outlet.querySelectorAll('.archive-paper p').forEach(el=>{
        if(/^(?:Local designation|Classification)\s*:/i.test(el.textContent.trim()))el.classList.add('authored-field','section-label');
      });
    }
    else outlet.querySelectorAll('.baseline-section .writer-pending').forEach(el=>outlet.querySelector('.document-notices').append(el));
    outlet.querySelectorAll('.entity-section-content .evidence').forEach((el,i)=>{
      if(el.closest('.event-basis'))return;
      const disclosure=document.createElement('details');disclosure.className='event-basis';
      const summary=document.createElement('summary');summary.textContent='Recorded basis & sources';
      disclosure.append(summary);el.before(disclosure);disclosure.append(el);
    });
    setLayer(outlet,sections.some(s=>s.id===selected)?selected:'baseline');
    document.querySelector('#app').querySelectorAll('.record-index-entry').forEach(button=>{
      const active=button.dataset[meta.kind]===String(meta.id);button.classList.toggle('selected',active);button.setAttribute('aria-pressed',String(active));if(active && meta.status && button.querySelector('em'))button.querySelector('em').textContent=meta.status;
    });
  }
  function layer(button) {
    const root=button.closest('.record-preview') || button.closest('.standalone-record');
    if(root)setLayer(root,button.dataset.recordLayer);
  }
  document.addEventListener('click',e=>{const tab=e.target.closest('[data-record-layer]');if(tab)layer(tab);});
  document.addEventListener('keydown',e=>{
    const tab=e.target.closest('[data-record-layer]');if(!tab||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
    e.preventDefault();const tabs=[...tab.parentElement.querySelectorAll('[data-record-layer]')];
    const next=e.key==='Home'?tabs[0]:e.key==='End'?tabs.at(-1):tabs[(tabs.indexOf(tab)+(e.key==='ArrowLeft'?-1:1)+tabs.length)%tabs.length];layer(next);next.focus();
  });
  document.addEventListener('click',e=>{
    const anchor=e.target.closest('a[href^="#memory-"],a[href^="#entry-"]');if(!anchor)return;
    const root=anchor.closest('.record-preview') || anchor.closest('.standalone-record');
    const target=root?.querySelector(anchor.getAttribute('href'));if(!target)return;
    const panel=target.closest('[role="tabpanel"]');
    const tab=panel && root.querySelector('[aria-controls="'+panel.id+'"]');
    if(tab){setLayer(root,tab.dataset.recordLayer);let ancestor=target.parentElement;while(ancestor && ancestor!==root){if(ancestor.tagName==='DETAILS')ancestor.open=true;ancestor=ancestor.parentElement;}target.scrollIntoView({block:'center'});}
  });
  const toggle=document.querySelector('.section-toggle'),sidebar=document.querySelector('.archive-sidebar');
  toggle.addEventListener('click',()=>{const open=toggle.getAttribute('aria-expanded')!=='true';toggle.setAttribute('aria-expanded',String(open));sidebar.classList.toggle('sections-open',open);});
  document.querySelectorAll('#sectionNav [data-view]').forEach(button=>button.addEventListener('click',()=>{toggle.setAttribute('aria-expanded','false');sidebar.classList.remove('sections-open');}));
  const app=document.querySelector('#app');
  new MutationObserver(()=>{
    const view=app.dataset.view || 'chronicle';
    document.querySelector('.site-header h1').textContent=labels[view]||'Campaign Chronicle';
    document.querySelectorAll('#sectionNav [data-view]').forEach(button=>{if(button.dataset.view===view)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});
  }).observe(app,{attributes:true,attributeFilter:['data-view'],childList:true,subtree:true});
  return {browser,present};
})();
