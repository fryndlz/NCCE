'use strict';

const app = document.querySelector('#app');
const health = document.querySelector('#health');
const syncNow = document.querySelector('#syncNow');
const logout = document.querySelector('#logout');
let data = null, activeView = 'chronicle', currentDetail = null, fightersCache = null;
let renderToken = 0, lastStatusFingerprint = null, refreshing = false;
const defaults = {fighters: {q: '', gang: '', status: '', role: '', listing: ''}, gangs: {q: '', faction: ''}, places: {q: '', owner: ''}, battles: {q: '', gang: ''}};
let filters = JSON.parse(JSON.stringify(defaults));

const esc = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
const short = value => String(value || 'Unknown').replace('THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]', 'C-NINE');
const human = value => String(value || '').replaceAll('_', ' ').replace(/\b\w/g, character => character.toUpperCase());
const cut = (value, limit) => { const text = String(value || ''); return text.length > limit ? text.slice(0, limit).trimEnd() + '…' : text; };
const list = value => Array.isArray(value) ? value : [];
const textMatch = (values, query) => !query.trim() || values.some(value => String(value || '').toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
const authored = source => /author|canon|C-NINE story/i.test(String(source || '')) && !/infer|generat|mechanic/i.test(String(source || ''));
const fighterStatus = fighter => fighter.status || 'Unknown';

function date(value, includeTime = false) {
  return value ? NCCEWriting.formatDate(value, includeTime).realDisplay : '';
}
function dateStamp(record) {
  const display = NCCEWriting.recordDate(record);
  return `<span class="chronicle-date"><strong>${esc(display.imperialDisplay)}</strong><small>${esc(display.realDisplay)}</small></span>`;
}
function when(record) {
  if (record.occurred_at || record.event_date) return date(record.occurred_at || record.event_date);
  if (record.is_baseline || record.baseline || /baseline/i.test(String(record.source || '') + ' ' + String(record.event_type || ''))) return 'Known at baseline · date unknown';
  return record.observed_at ? 'Observed ' + date(record.observed_at) : 'Known at baseline · date unknown';
}
function inline(value) {
  // Escape source text before accepting these two deliberately limited marks.
  const readable = String(value ?? '').replace(/\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?\b/g, raw => NCCEWriting.formatDate(raw).realDisplay);
  return esc(readable).replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>').replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
}
function prose(value) {
  return String(value || '').trim().split(/\n\s*\n/).filter(Boolean).map(paragraph => `<p>${inline(paragraph).replaceAll('\n', '<br>')}</p>`).join('');
}
function blocks(document, fallback = '') {
  const content = list(document?.blocks);
  if (!content.length) {
    if (document?.writer_status && document.writer_status !== 'ready') return `<p class="writer-pending" role="status">${esc(document.writer_message || (document.writer_status === 'unconfigured' ? 'Narrative pending · configure the server-side writing provider.' : `Narrative ${document.writer_status} · retry on the next refresh.`))}</p>`;
    return prose(fallback);
  }
  const rich = content => list(content).map(run => {
    let text = inline(typeof run === 'string' ? run : run.text);
    for (const mark of list(run?.marks)) {
      const type = typeof mark === 'string' ? mark : mark.type;
      if (['admin_label','important_entity','secondary_text','critical_status','error_or_missing','doctrine','redacted','speaker','machine_error'].includes(type)) text = `<span class="mark-${type}">${type === 'redacted' ? '████' : text}</span>`;
      if (type === 'source_anchor' && mark.target) text = `<a class="annotation-anchor" href="#note-${esc(mark.target)}">${text}</a>`;
    }
    return text;
  }).join('');
  const node = (block, inSolid = false) => {
    const text = block.content ? rich(block.content) : inline(block.text);
    const children = () => list(block.blocks).map(child => node(child, inSolid || ['disposition_panel','addendum_panel','internal_note'].includes(block.type))).join('');
    const anchor = block.id ? ` id="block-${esc(block.id)}"` : '';
    if (block.type === 'heading') return `<h4>${inline(block.text)}</h4>`;
    if (block.type === 'quote') return `<blockquote>${prose(block.text)}</blockquote>`;
    if (block.type === 'list') return `<ul>${list(block.items).map(item => `<li>${inline(typeof item === 'object' ? item.text : item)}</li>`).join('')}</ul>`;
    if (block.type === 'record') return `<div class="record-fragment">${prose(block.text)}</div>`;
    if (block.type === 'metadata_group') return `<dl class="metadata-group">${list(block.fields).map(field => `<div><dt>${inline(field.label)}</dt><dd>${inline(field.value)}</dd></div>`).join('')}</dl>`;
    if (['section_label','engagement_header','chronicle_section'].includes(block.type)) return `<h4 class="section-label"${anchor}>${text}</h4>${children()}`;
    if (['disposition_panel','addendum_panel','internal_note'].includes(block.type)) return `<aside class="${inSolid ? 'nested-record' : 'processing-panel'}"${anchor}>${text ? `<div class="section-label">${text}</div>` : ''}${children()}</aside>`;
    if (block.type === 'testimony_note') return `<aside class="testimony-note" id="note-${esc(block.id || '')}">${block.author ? `<div class="mark-speaker">${inline(block.author)}</div>` : ''}${prose(block.text)}${children()}${block.anchor ? `<a href="#block-${esc(block.anchor)}">Return to source passage</a>` : ''}</aside>`;
    if (block.type === 'evidence_excerpt') return `<blockquote class="evidence-excerpt"${anchor}>${block.source ? `<cite>${inline(block.source)}</cite>` : ''}${prose(block.text)}${children()}</blockquote>`;
    if (block.type === 'transcript') return `<div class="transcript"${anchor}>${list(block.turns).map(turn => `<p><strong class="mark-speaker">${inline(turn.speaker)}:</strong> ${inline(turn.text)}</p>`).join('')}</div>`;
    if (block.type === 'attachment') return `<section class="attachment"${anchor}><div class="attachment-marker">// ATTACHMENT ${inline(block.index || '')} //</div>${text ? `<h4>${text}</h4>` : ''}${children()}</section>`;
    if (['record_termination','scene_divider','system_output'].includes(block.type)) return `<div class="${esc(block.type)}"${anchor}>${text}</div>`;
    if (['incident_record','personnel_dossier'].includes(block.type)) return `<section class="${esc(block.type)}"${anchor}>${text ? `<h4>${text}</h4>` : ''}${children()}</section>`;
    return text ? `<p${anchor}>${text}</p>` : children();
  };
  const header = document.document_type ? `<header class="record-header"><div class="eyebrow">${esc(human(document.document_type))}</div>${document.date_display && !document.suppress_date ? dateStamp(document) : ''}<dl class="metadata-group">${list(document.metadata).map(field => `<div><dt>${inline(field.label)}</dt><dd>${inline(field.value)}</dd></div>`).join('')}</dl></header>` : '';
  const status = document?.writer_status && document.writer_status !== 'ready' ? `<p class="writer-pending" role="status">${esc(document.writer_message || (document.writer_status === 'unconfigured' ? 'Narrative pending · configure the server-side writing provider.' : `Narrative ${document.writer_status} · retry on the next refresh.`))}</p>` : '';
  return `${header}${status}<div class="record-body">${content.map(block => node(block)).join('')}</div>${document.termination ? node(document.termination) : ''}`;
}
function markedParagraphs(paragraphs) {
  const supported = new Set(['critical_status','error_or_missing','machine_error','redacted']);
  return list(paragraphs).map(runs => `<p>${list(runs).map(run => {
    let text = inline(run?.text);
    for (const mark of list(run?.marks).filter(value => supported.has(value))) text = `<span class="mark-${mark}">${mark === 'redacted' ? '████' : text}</span>`;
    return text;
  }).join('')}</p>`).join('');
}
function writtenProse(content, runs) { return markedParagraphs(runs) || prose(content); }
function displayValue(value) {
  if (value === null || value === undefined || value === '') return 'None recorded';
  if (Array.isArray(value)) return value.map(displayValue).join('; ');
  if (typeof value === 'object') return Object.entries(value).filter(([, item]) => item !== null && typeof item !== 'object').map(([key, item]) => `${human(key)}: ${item}`).join(' · ') || 'Recorded in the source';
  return String(value);
}
function evidenceText(item) {
  if (typeof item !== 'object' || item === null) return String(item || '');
  if (item.text || item.detail || item.summary || item.description) return String(item.text || item.detail || item.summary || item.description);
  if (Object.hasOwn(item, 'before') || Object.hasOwn(item, 'after')) return `${item.label || item.field || item.title || 'Recorded change'}: ${displayValue(item.before)} → ${displayValue(item.after)}`;
  if (item.label && Object.hasOwn(item, 'value')) return `${item.label}: ${displayValue(item.value)}`;
  return displayValue(item);
}
function evidence(items, metadata = {}, compact = false, previewLimit = 0) {
  const entries = list(items).map(evidenceText).filter(Boolean);
  const refs = list(metadata.source_event_ids || metadata.event_ids).filter(Boolean);
  const observations = list(metadata.source_observation_ids).filter(Boolean);
  const sourceLabel = metadata.source_label || metadata.source || [...new Set([metadata.source_id,...list(metadata.source_ids)].filter(Boolean))].join(' · ');
  const locator = metadata.source_locator;
  const fold = previewLimit > 0 && entries.length > 8;
  const visible = fold ? entries.slice(0, previewLimit) : entries;
  const additional = fold ? entries.slice(previewLimit) : [];
  if (!entries.length && !refs.length && !observations.length && !sourceLabel && !locator) return '';
  return `<div class="evidence ${compact ? 'evidence-compact' : ''}"><div class="evidence-label">${compact ? 'Recorded basis' : 'Mechanical evidence'}</div>${visible.length ? `<ul>${visible.map(item => `<li>${inline(item)}</li>`).join('')}</ul>` : ''}${additional.length ? `<details class="evidence-more"${locator ? ` data-key="evidence-${esc(locator)}"` : ''}><summary>Show ${additional.length} additional mechanical records</summary><ul>${additional.map(item => `<li>${inline(item)}</li>`).join('')}</ul></details>` : ''}${sourceLabel ? `<div class="evidence-source">${esc(sourceLabel)}</div>` : ''}${refs.length || observations.length || locator ? `<details class="source-details"><summary>Source references${metadata.provenance_class ? ' · ' + esc(human(metadata.provenance_class)) : ''}</summary>${locator ? `<p>${esc(locator)}</p>` : ''}${refs.length ? `<p>Campaign events</p><ul>${refs.map(ref => `<li><code>${esc(ref)}</code></li>`).join('')}</ul>` : ''}${observations.length ? `<p>Source memories: ${observations.map(esc).join(', ')}</p>` : ''}</details>` : ''}</div>`;
}
function eventSummary(event) {
  const p = event.payload || {};
  if (event.evidence) return list(event.evidence).map(evidenceText).filter(Boolean);
  if (p.field && (Object.hasOwn(p, 'before') || Object.hasOwn(p, 'after'))) return [`${p.field}: ${displayValue(p.before)} → ${displayValue(p.after)}`];
  if (/battle/.test(event.event_type || '') && p.scenario) return [`${short(p.attacker)} vs ${short(p.defender)}`, `${p.scenario}${p.winner ? ' · Winner: ' + short(p.winner) : ''}${p.territory ? ' · Territory: ' + p.territory : ''}`];
  if (p.changes) return Object.entries(p.changes).map(([key, value]) => `${human(key)}: ${displayValue(value.before)} → ${displayValue(value.after)}`);
  if (/unlisted|removed/.test(event.event_type || '')) return ['No longer listed in the current source. Previous records remain in the chronicle.'];
  if (/recruit|joined/.test(event.event_type || '')) return ['Newly listed in the campaign source.'];
  if (p.territory && (p.before_owner || p.after_owner)) return [`${p.territory}: ${short(p.before_owner)} → ${short(p.after_owner)}`];
  const values = Object.entries(p).filter(([key, value]) => !['source_row', 'present_before', 'present_after'].includes(key) && value !== null && typeof value !== 'object');
  return values.length ? values.map(([key, value]) => `${human(key)}: ${displayValue(value)}`) : [event.title || human(event.event_type) || 'Campaign record updated'];
}
function campaignEvent(event) {
  const subjects = list(event.subjects).map(subject => subject.display_name).filter(Boolean);
  return `<article class="ledger-entry"><div class="entry-top"><span class="eyebrow">${esc(event.title || human(event.event_type))}</span><time>${dateStamp(event)}</time></div>${subjects.length ? `<div class="muted compact">${esc([...new Set(subjects)].map(short).join(' · '))}</div>` : ''}${evidence(eventSummary(event), {...event, source_event_ids: event.event_id ? [event.event_id] : []}, true)}</article>`;
}
const storySource = source => authored(source) ? 'Authored campaign record' : 'Generated inference';
function narrative(value, source, items = [], meta = {}) {
  const document = meta.biography_document || meta.history_document;
  const isAuthored = authored(source || document?.provenance_class || meta.provenance_class);
  const basis = document?.evidence?.length ? document.evidence : items;
  return `<div class="narrative"><div class="eyebrow">${isAuthored ? 'Authored campaign record' : 'Generated inference'}</div>${isAuthored ? prose(value) : blocks(document, value)}</div>${isAuthored ? `<div class="authored-source">${esc(source || 'Authored campaign canon')}</div>` : evidence(basis, {...meta, ...document})}`;
}
const empty = message => `<div class="empty-state"><p>${esc(message)}</p></div>`;
async function api(url, options) {
  const response = await fetch(url, {cache: 'no-store', ...options});
  if (response.status === 401) { location.replace('/login'); throw new Error('Please sign in to continue.'); }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The chronicle could not complete that request.');
  return result;
}
function captureUi() {
  const focused = document.activeElement;
  return {key: focused?.dataset?.filter, selection: typeof focused?.selectionStart === 'number' ? [focused.selectionStart, focused.selectionEnd] : null, open: [...app.querySelectorAll('details[data-key][open]')].map(element => element.dataset.key), scroll: window.scrollY};
}
function restoreUi(saved) {
  if (!saved) return;
  for (const element of app.querySelectorAll('details[data-key]')) if (saved.open.includes(element.dataset.key)) element.open = true;
  const input = [...app.querySelectorAll('[data-filter]')].find(element => element.dataset.filter === saved.key);
  if (input) { input.focus({preventScroll: true}); if (saved.selection && input.setSelectionRange) input.setSelectionRange(...saved.selection); }
  window.scrollTo(0, saved.scroll);
}
function syncLabel(status) {
  if (status.sync_status === 'syncing') return 'Krakamunda · refreshing the chronicle…';
  if (status.sync_status === 'error') return `Refresh failed${status.sync_last_success ? ' · last checked ' + date(status.sync_last_success, true) : ''}`;
  if (status.sync_last_success) return `Krakamunda checked ${date(status.sync_last_success, true)} · every ${Math.round((status.sync_interval_seconds || 900) / 60)} min`;
  return 'Krakamunda · waiting for the first refresh';
}
const statusFingerprint = status => [status.sync_last_snapshot_id || '', status.story_revision || status.narrative_revision || status.story_generated_at || '', status.sync_last_success || status.last_sync || ''].join('|');
async function refreshDashboard(preserve = true) {
  if (refreshing) return;
  refreshing = true;
  const saved = preserve ? captureUi() : null;
  try {
    const [dashboard, ledger] = await Promise.all([api('/api/dashboard'), api('/api/events?limit=12')]);
    data = dashboard;
    for (const field of ['gangs', 'regions', 'downtime', 'battles', 'territories']) data[field] = list(data[field]);
    data.state = data.state || {};
    data.campaignEvents = list(ledger.events);
    fightersCache = Array.isArray(data.fighters) ? data.fighters : null;
    if (currentDetail) await openDetail(currentDetail.type, currentDetail.id, true);
    else await render(activeView, true);
    restoreUi(saved);
  } finally { refreshing = false; }
}
async function refreshStatus() {
  const status = await api('/api/health');
  health.textContent = syncLabel(status);
  health.classList.toggle('has-error', status.sync_status === 'error');
  syncNow.disabled = status.sync_status === 'syncing';
  syncNow.textContent = status.sync_status === 'syncing' ? 'Refreshing…' : 'Refresh from Sheet';
  const fingerprint = statusFingerprint(status);
  if (lastStatusFingerprint !== null && fingerprint !== lastStatusFingerprint && status.sync_status !== 'syncing') await refreshDashboard();
  lastStatusFingerprint = fingerprint;
}
function battleEvidence(b) {
  return [`${b.scenario || 'Engagement'} · ${date(b.date) || 'Date not recorded'}`, `Gangs: ${short(b.attacker)} / ${short(b.defender)}`, `Winner: ${short(b.winner)}`, ...(b.territory ? [`Territory: ${b.territory}${b.territory_claimer ? ' · Claim recorded for ' + short(b.territory_claimer) : ''}`] : [])];
}
function battle(b, expanded = false) {
  const document = b.report_document || b.document;
  const outcome = b.winner ? short(b.winner) + ' won' : 'Outcome not recorded';
  const notes = document?.recorded_notes;
  return `<article class="battle-report"><div class="entry-top"><span class="eyebrow">${esc(b.scenario || 'Engagement')}</span><time>${dateStamp({date:b.date})}</time></div><h3>${esc(document?.title || (b.territory ? 'The struggle for ' + b.territory : short(b.attacker) + ' / ' + short(b.defender)))}</h3><div class="battle-parties">${esc(short(b.attacker))}<span>against</span>${esc(short(b.defender))}</div><div class="battle-outcome">${esc(outcome)}${b.territory ? `<span class="tag">${esc(b.territory)}</span>` : ''}</div><details class="report-fold" data-key="battle-${esc(b.id || b.source_row)}"${expanded ? ' open' : ''}><summary>Battle account</summary>${b.chronicle_stale ? '<p class="warning">This account is awaiting regeneration after a corrected source record.</p>' : ''}<div class="report-body"><div class="eyebrow">Generated inference · battle chronicle</div>${blocks(document ? {...document, suppress_date:true} : document, b.chronicle || '')}</div>${notes?.text ? `<aside class="recorded-note"><div class="eyebrow">${esc(notes.label || 'Recorded battle notes')} · authored source</div>${prose(notes.text)}${notes.source_id ? `<div class="authored-source">${esc(notes.source_id)}</div>` : ''}</aside>` : ''}${evidence(document?.evidence?.length ? document.evidence : battleEvidence(b), {...document, source_label: 'Authoritative campaign Sheet · Battles', source_locator: b.source_row ? 'Battles!row ' + b.source_row : null}, false, 6)}</details></article>`;
}
function downtime(report) {
  const document = report.document || report.report_document;
  return `<section class="card downtime"><div class="eyebrow">${esc(short(report.gang_name))} · generated inference</div><h3>${esc(document?.title || report.period_label || 'Between engagements')}</h3><div class="report-body">${blocks(document, report.report)}</div>${evidence(document?.evidence || report.evidence || [], document || report, true)}</section>`;
}
function chronicle() {
  const region = data.regions[0];
  const current = new Map();
  for (const report of data.downtime) if (!current.has(report.gang_id || report.gang_name)) current.set(report.gang_id || report.gang_name, report);
  const latestDowntime = [...current.values()].slice(0, 3);
  return `<div class="sectionhead"><div><div class="eyebrow">Dominion Krakamunda</div><h2>Campaign Chronicle</h2></div><span class="quiet-label">Lives · claims · consequences</span></div>${region ? `<section class="region-intro">${narrative(region.backstory, region.backstory_source || 'inference', region.evidence || [`${data.gangs.length} active gang records`, `${data.territories.length} territory records`, `${data.battles.length} recorded battles`], region)}</section>` : ''}<div class="split chronicle-layout"><section><h3 class="section-title">Recent battle accounts</h3>${data.battles.slice(0, 3).map((record, index) => battle(record, index === 0)).join('') || empty('No battle records have been imported yet.')}<details class="ledger-fold" data-key="campaign-ledger"><summary>Latest mechanical campaign records <span>${data.campaignEvents.length}</span></summary><div class="timeline">${data.campaignEvents.map(campaignEvent).join('') || empty('No changes recorded since the baseline.')}</div></details></section><aside><h3 class="section-title">Between games</h3>${latestDowntime.map(downtime).join('') || empty('Downtime accounts will appear as the campaign develops.')}</aside></div>`;
}
function selectControl(view, key, label, options) {
  return `<label>${esc(label)}<select data-filter="${esc(key)}" data-filter-view="${esc(view)}">${options.map(option => `<option value="${esc(option.value)}"${option.value === filters[view][key] ? ' selected' : ''}>${esc(option.label)}</option>`).join('')}</select></label>`;
}
function searchControl(view, placeholder) {
  return `<label class="search-control">Search<input type="search" data-filter="q" data-filter-view="${esc(view)}" value="${esc(filters[view].q)}" placeholder="${esc(placeholder)}" autocomplete="off"></label>`;
}
const uniqueOptions = (values, allLabel) => [{value: '', label: allLabel}, ...[...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b)).map(value => ({value, label: short(value)}))];
const gangOptions = allLabel => [{value: '', label: allLabel}, ...data.gangs.map(gang => ({value: String(gang.gang_id), label: short(gang.name)})).sort((a, b) => a.label.localeCompare(b.label))];
function listShell(view, title, description, controls) {
  return `<div class="sectionhead"><div><div class="eyebrow">Campaign archive</div><h2>${esc(title)}</h2></div><span class="result-count" id="resultCount" aria-live="polite"></span></div><p class="view-intro">${esc(description)}</p><form class="filters" data-filter-form="${esc(view)}" role="search">${controls}<button class="clear-filters" type="button" data-clear="${esc(view)}">Clear filters</button></form><div id="listResults"></div>`;
}
function fighterCard(f) {
  return `<article class="card fighter-card ${f.status === 'Killed' ? 'dead' : ''}"><div class="eyebrow">${esc(short(f.gang_name))}</div><h3><button class="card-title" data-fighter="${esc(f.id)}">${esc(f.name)}</button></h3><div class="card-subtitle">${esc(f.type)} · ${esc(f.class)}</div><div class="status-line"><span class="status-pill">${esc(fighterStatus(f))}</span>${f.listed_in_source === 0 ? '<span class="tag">Not currently listed</span>' : ''}</div><div class="card-excerpt">${prose(cut(f.backstory, 280))}</div>${authored(f.backstory_source) ? '' : evidence([`${f.class || 'Fighter'} · ${f.xp ?? 0} XP · ${f.kills ?? 0} recorded kills${f.effects ? ' · ' + f.effects : ''}`], {}, true)}<div class="card-foot">${esc(storySource(f.backstory_source))}</div></article>`;
}
function gangCard(g) {
  return `<article class="card gang-card"><div class="eyebrow">${esc(g.gang_type)}</div><h3><button class="card-title" data-gang="${esc(g.gang_id)}">${esc(short(g.name))}</button></h3><div class="card-excerpt">${prose(cut(g.backstory, 400))}</div>${authored(g.backstory_source) ? '' : evidence([`Faction: ${g.gang_type || 'Unknown'}`, `${g.territories ?? 0} territories recorded`], {}, true)}<div class="card-foot">${esc(storySource(g.backstory_source))} · open history and evidence →</div></article>`;
}
async function ensureFighters() {
  if (fightersCache) return fightersCache;
  const gangs = await Promise.all(data.gangs.map(g => api('/api/gangs/' + encodeURIComponent(g.gang_id))));
  fightersCache = gangs.flatMap(g => list(g.fighters).map(f => ({...f, gang_type: g.gang_type})));
  return fightersCache;
}
function listResults(view) {
  let rows = [];
  const state = filters[view];
  if (view === 'fighters') {
    rows = list(fightersCache).filter(f => (!state.gang || String(f.gang_id) === state.gang) && (!state.status || fighterStatus(f) === state.status) && (!state.role || f.class === state.role) && (!state.listing || (state.listing === 'listed' ? f.listed_in_source !== 0 : f.listed_in_source === 0)) && textMatch([f.name, f.type, f.class, f.gang_name, f.backstory, f.effects], state.q));
    rows.sort((a, b) => a.name.localeCompare(b.name));
  } else if (view === 'gangs') rows = data.gangs.filter(g => (!state.faction || g.gang_type === state.faction) && textMatch([short(g.name), g.gang_type, g.player, g.backstory], state.q));
  else if (view === 'places') rows = data.territories.filter(t => (!state.owner || String(t.gang_id) === state.owner) && textMatch([t.territory, t.gang_name, t.backstory], state.q));
  else if (view === 'battles') {
    const gang = data.gangs.find(g => String(g.gang_id) === state.gang);
    rows = data.battles.filter(b => (!gang || [b.attacker, b.defender, b.winner, b.territory_claimer].includes(gang.name)) && textMatch([b.scenario, b.attacker, b.defender, b.winner, b.territory, b.report_document?.title, b.chronicle], state.q));
  }
  const names = {fighters: ['fighter', 'fighters'], gangs: ['gang', 'gangs'], places: ['territory', 'territories'], battles: ['battle', 'battles']};
  const noun = names[view][rows.length === 1 ? 0 : 1];
  const total = view === 'fighters' ? list(fightersCache).length : rows.length;
  document.querySelector('#resultCount').textContent = view === 'fighters' && total !== rows.length
    ? `${rows.length} of ${total} fighters shown`
    : `${rows.length} ${noun}`;
  const results = document.querySelector('#listResults');
  if (!rows.length) { results.innerHTML = empty('No records match these filters. Try a different name, gang, or status.'); return; }
  if (view === 'fighters') results.innerHTML = `<div class="grid">${rows.map(fighterCard).join('')}</div>`;
  if (view === 'gangs') results.innerHTML = `<div class="grid">${rows.map(gangCard).join('')}</div>`;
  if (view === 'places') results.innerHTML = `${placeAssociationNotes()}<div class="grid">${rows.map(t => `<article class="card place-card"><div class="eyebrow">Held by ${esc(short(t.gang_name))}</div><h3><button class="card-title" data-territory="${esc(t.id)}">${esc(t.territory)}</button></h3><div class="card-excerpt">${prose(t.backstory)}</div>${evidence([`Holder: ${short(t.gang_name)}`, `Card: ${t.card || 'Not recorded'}`], {}, true)}<div class="card-foot">Generated inference · territory record</div></article>`).join('')}</div>`;
  if (view === 'battles') results.innerHTML = rows.map((record, index) => battle(record, index === 0)).join('');
}
async function render(view, preserveScroll = false) {
  const token = ++renderToken;
  activeView = view === 'people' ? 'fighters' : view;
  currentDetail = null;
  document.querySelectorAll('nav button').forEach(button => button.classList.toggle('active', button.dataset.view === activeView));
  if (activeView === 'fighters') {
    if (!fightersCache) app.innerHTML = '<div class="loading-state" role="status">Opening fighter records…</div>';
    await ensureFighters();
    if (token !== renderToken) return;
    app.innerHTML = listShell('fighters', 'Fighters', 'Find a fighter and follow the life accumulating behind their campaign record.', searchControl('fighters', 'Name, type, story, injury…') + selectControl('fighters', 'gang', 'Gang', gangOptions('All gangs')) + selectControl('fighters', 'status', 'Status', uniqueOptions(fightersCache.map(fighterStatus), 'All statuses')) + selectControl('fighters', 'role', 'Role', uniqueOptions(fightersCache.map(f => f.class), 'All roles')) + selectControl('fighters', 'listing', 'Source', [{value: '', label: 'All records'}, {value: 'listed', label: 'Currently listed'}, {value: 'unlisted', label: 'Not currently listed'}]));
    listResults('fighters');
  } else if (activeView === 'gangs') {
    app.innerHTML = listShell('gangs', 'Gang histories', 'Authored histories and the identities taking shape through the campaign.', searchControl('gangs', 'Gang, player, history…') + selectControl('gangs', 'faction', 'Faction', uniqueOptions(data.gangs.map(g => g.gang_type), 'All factions')));
    listResults('gangs');
  } else if (activeView === 'places') {
    app.innerHTML = listShell('places', 'Places', 'Claims become places through the lives and conflicts that gather around them.', searchControl('places', 'Territory, history…') + selectControl('places', 'owner', 'Held by', gangOptions('All holders')));
    listResults('places');
  } else if (activeView === 'battles') {
    app.innerHTML = listShell('battles', 'Battle chronicle', 'Accounts inferred from recorded outcomes and their campaign consequences.', searchControl('battles', 'Scenario, territory, gang…') + selectControl('battles', 'gang', 'Gang', gangOptions('All gangs')));
    listResults('battles');
  } else if (activeView === 'chronicle') app.innerHTML = chronicle();
  else if (activeView === 'archive') app.innerHTML = '<div class="eyebrow">Authored canon</div><h2>Archive</h2><p class="view-intro">The campaign’s authored records remain available in their own voice.</p><article class="card"><div class="eyebrow">C-NINE · campaign log and personnel files</div><h3><button class="card-title" data-lore="1">C-NINE Story</button></h3><p>Open the canonical story export and personnel dossiers.</p></article>';
  else if (activeView === 'system') app.innerHTML = `<div class="eyebrow">Engine record</div><h2>System</h2><section class="card system-state"><div class="row"><span>Writing provider</span><span class="muted">${esc(data.writer?.status || 'unknown')}${data.writer?.model ? ' · '+esc(data.writer.model) : ''}</span></div>${data.writer?.configured ? `<div class="row"><span>Model calls this refresh</span><span class="muted">${esc(data.writer.calls_used)} / ${esc(data.writer.call_budget)}</span></div>` : ''}${Object.entries(data.state).map(([key, value]) => `<div class="row"><span>${esc(human(key))}</span><span class="muted">${esc(value)}</span></div>`).join('')}</section>`;
  if (!preserveScroll) window.scrollTo(0, 0);
}
function fighterEvidence(f) {
  return [`Role: ${f.class || 'Not recorded'} · ${f.type || 'Type not recorded'}`, `XP: ${f.xp ?? 0} · Recorded kills: ${f.kills ?? 0}`, `Status: ${fighterStatus(f)}`, ...(f.advancements ? ['Advancements: ' + f.advancements] : []), ...(f.effects ? ['Effects: ' + f.effects] : [])];
}
function memoryCard(memory) {
  const type = memory.memory_type === 'reflection' ? 'Reflection' : 'Observation';
  const status = memory.writer_status && memory.writer_status !== 'ready' ? `<p class="writer-pending" role="status">Narrative ${esc(memory.writer_status)} · ${memory.writer_status === 'unconfigured' ? 'configure the server-side writing provider.' : 'retry on the next refresh.'}</p>` : '';
  return `<article class="memory-card ${type.toLowerCase()}" id="memory-${esc(memory.id)}"><div class="entry-top"><span class="memory-kind">${type}</span><time>${dateStamp(memory)}</time></div>${memory.title ? `<div class="memory-trigger">${esc(memory.title)}</div>` : ''}${status}<div class="memory-voice">${writtenProse(memory.content,memory.content_runs)}</div>${evidence(memory.evidence || memory.mechanical_evidence || [], memory)}${memory.importance != null ? `<div class="memory-footer"><details class="memory-scoring"><summary>Salience ${esc(memory.importance)}</summary><p>Importance is the event’s narrative weight. It is not a game statistic.</p>${list(memory.tags).length ? `<p>Topics: ${list(memory.tags).map(esc).join(', ')}</p>` : ''}</details></div>` : ''}</article>`;
}
function mindCard(thought) {
  const memoryId = thought.memory_id || thought.id;
  const label = thought.label || thought.title || thought.name || list(thought.tags)[0] || 'Current concern';
  const status = thought.writer_status && thought.writer_status !== 'ready' ? `<p class="writer-pending" role="status">Narrative ${esc(thought.writer_status)} · ${thought.writer_status === 'unconfigured' ? 'configure the server-side writing provider.' : 'retry on the next refresh.'}</p>` : '';
  return `<article class="mind-card"><div class="eyebrow">${esc(human(label))}</div>${status}<div class="thought">${writtenProse(thought.content || thought.thought,thought.content_runs)}</div>${evidence(thought.evidence || [], thought, true)}${memoryId ? `<a class="memory-link" href="#memory-${esc(memoryId)}">Trace this thought to memory ↓</a>` : ''}${thought.score_details ? `<details class="mind-retrieval"><summary>Why this is on their mind</summary><dl>${Object.entries(thought.score_details).map(([key, value]) => `<div><dt>${esc(human(key))}</dt><dd>${esc(typeof value === 'number' ? Math.round(value * 100) / 100 : displayValue(value))}</dd></div>`).join('')}</dl></details>` : ''}</article>`;
}
function voiceDetails(profile) {
  if (!profile || !Object.keys(profile).length) return '';
  const traits = Array.isArray(profile.traits) ? profile.traits.map(evidenceText) : typeof profile.traits === 'object' ? Object.entries(profile.traits).map(([key, value]) => `${human(key)}: ${displayValue(value)}`) : [profile.traits].filter(Boolean);
  return `<details class="voice-profile" data-key="voice-profile"><summary>Inferred voice profile</summary>${profile.name ? `<p>${esc(profile.name)}</p>` : ''}${traits.length ? `<ul>${traits.map(trait => `<li>${esc(trait)}</li>`).join('')}</ul>` : ''}${evidence(profile.evidence || [], {source_label: 'Voice inferred from biography, role, characteristics, and recorded history'}, true)}</details>`;
}
function mechanicsPanel(f) {
  let mechanics = f.mechanics || {};
  if (!Object.keys(mechanics).length && f.mechanics_json) { try { mechanics = JSON.parse(f.mechanics_json); } catch (_) { mechanics = {}; } }
  const stats = ['M', 'WS', 'BS', 'S', 'T', 'W', 'I', 'A', 'Ld', 'Cl', 'Wil', 'Int'];
  return `<details class="mechanics-fold" data-key="fighter-mechanics"><summary>Current mechanical evidence</summary>${evidence(fighterEvidence(f), {source_label: 'Authoritative campaign Sheet'})}${stats.some(key => mechanics[key] != null) ? `<div class="stats-grid">${stats.filter(key => mechanics[key] != null).map(key => `<div><span>${esc(key)}</span><strong>${esc(mechanics[key])}</strong></div>`).join('')}</div>` : ''}${['Weapons', 'Wargear', 'Skills'].filter(key => mechanics[key]).map(key => `<div class="mechanical-field"><strong>${esc(key)}</strong><p>${esc(mechanics[key])}</p></div>`).join('')}${f.notes ? `<p class="source-note">${esc(f.notes)}</p>` : ''}</details>`;
}
function storyStream(entries, scope) {
  const visible = new Set(list(entries).map(entry => entry.entry_id));
  return `<section class="progressing-story"><h3 class="section-title">${scope === 'territory' ? 'Life and events here' : 'The gang’s unfolding story'}</h3><div class="scope-stream">${list(entries).map(entry => `<article class="scope-entry ${entry.provenance_class === 'connective_fiction' ? 'fiction-entry' : ''}" id="entry-${esc(entry.entry_id)}"><h4>${esc(entry.title)}</h4><div class="eyebrow">${entry.provenance_class === 'connective_fiction' ? 'Invented local report · connective fiction' : 'Generated reconstruction · sourced event'}</div>${blocks(entry.document)}${evidence(entry.document?.evidence || [], entry.document || entry)}${list(entry.continuity?.previous_entry_ids).length ? `<details class="source-details"><summary>Earlier local accounts</summary>${entry.continuity.previous_entry_ids.map(id => visible.has(id) ? `<a class="memory-link" href="#entry-${esc(id)}">Earlier record ${esc(id.slice(0,8))} ↑</a>` : `<span class="muted">Archived earlier version ${esc(id.slice(0,8))}</span>`).join('')}</details>` : ''}</article>`).join('') || empty('New campaign events will accumulate here after a source refresh.')}</div></section>`;
}
function placeAssociationNotes() {
  const notes = list(data.place_association_notes);
  return notes.length ? `<details class="evidence place-association-notes"><summary>${notes.length} battle location reference${notes.length === 1 ? '' : 's'} awaiting a unique place identity</summary>${notes.map(note => `<p><strong>${esc(note.territory)}</strong> · ${esc(date(note.date))}<br>${esc(note.text)}</p>`).join('')}</details>` : '';
}
function identityEditor(fighter) {
  const identity = fighter.writer_identity || {};
  const fields = [['being','Kind of being'],['lineage','Lineage'],['culture','Culture'],['institution','Institution'],['place','Upbringing / place'],['work','Occupation / craft'],['training','Training'],['condition','Relevant conditions'],['life_history','Personal history cues'],['voice','Individual voice cues'],['gender','Gender'],['pronouns','Pronouns'],['writer_tags','Additional tags']];
  const mode = identity.narration_mode || '';
  return `<details class="identity-editor"><summary>Writer identity</summary><p class="muted compact">Add known character context. Separate multiple values with semicolons. Leave unknown fields empty. These notes guide writing and preserve the campaign source.</p><form data-identity-form="${esc(fighter.id)}">${fields.map(([key,label]) => `<label>${esc(label)}<input name="${key}" value="${esc(Array.isArray(identity[key]) ? identity[key].join('; ') : identity[key] || '')}"></label>`).join('')}<label>Perspective<select name="narration_mode">${[['','From recorded identity'],['sapient','Language and personal thought'],['sensory','Sensation and learned association'],['task_log','Task and instruction log']].map(([value,label]) => `<option value="${value}"${value === mode ? ' selected' : ''}>${label}</option>`).join('')}</select></label><button type="submit">Save writing context</button><p role="status" class="identity-status"></p></form></details>`;
}
async function showFighter(id, preserveScroll = false) {
  const token = ++renderToken, f = await api('/api/fighters/' + encodeURIComponent(id));
  if (token !== renderToken) return;
  currentDetail = {type: 'fighter', id};
  const memories = list(f.memories).slice().sort((a, b) => Number(Boolean(a.is_baseline || a.baseline)) - Number(Boolean(b.is_baseline || b.baseline)) || (b.occurred_at || b.observed_at || '').localeCompare(a.occurred_at || a.observed_at || '') || Number(b.id) - Number(a.id));
  const mind = Array.isArray(f.mind) ? f.mind : list(f.moodlets).filter(m => m.name !== 'Dead').slice(0, 4);
  const deceased = /killed|dead/i.test(f.status || '');
  app.innerHTML = `<button class="back" data-back="fighters">← Fighters</button><div class="eyebrow">${esc(short(f.gang_name))} · fighter record</div><div class="fighter-title"><h2>${esc(f.name)}</h2><span class="status-pill">${esc(fighterStatus(f))}</span></div><p class="record-subtitle">${esc(f.type)} · ${esc(f.class)}${f.listed_in_source === 0 ? ' · Not currently listed in source' : ''}</p><div class="fighter-layout"><section class="fighter-history"><section class="biography"><h3>Backstory</h3>${narrative(f.backstory, f.backstory_source, fighterEvidence(f), {...f, source_label: 'Current mechanics and campaign context'})}</section><div class="sectionhead memory-heading"><div><h3>Memory stream</h3><p class="muted compact">Their recorded history · most recent first</p></div><span class="quiet-label">${memories.length} entries</span></div><div class="memory-stream">${memories.map(memoryCard).join('') || empty('No sourced memories have been generated for this fighter yet.')}</div><details class="ledger-fold" data-key="fighter-ledger"><summary>Mechanical change tracker <span>${list(f.campaign_events).length}</span></summary><div class="timeline">${list(f.campaign_events).map(campaignEvent).join('') || empty('No changes have been recorded after the baseline.')}</div></details>${list(f.events).length ? `<details class="ledger-fold" data-key="baseline-records"><summary>Baseline source records</summary>${list(f.events).map(e => `<div class="baseline-record"><strong>${esc(e.title || human(e.event_type))}</strong><p>${esc(e.detail)}</p><small>Known at baseline · date unknown · ${esc(e.source)}</small></div>`).join('')}</details>` : ''}</section><aside class="fighter-mind"><div class="mind-heading"><div class="eyebrow">Current preoccupations</div><h3>Mind</h3><p>What weighs on them now.</p></div>${deceased ? empty('This fighter has died. Their remembered history remains.') : mind.length ? mind.map(mindCard).join('') : empty('There are not enough supported memories to select a current thought.')}${voiceDetails(f.voice_profile)}${identityEditor(f)}${mechanicsPanel(f)}</aside></div>`;
  if (!preserveScroll) window.scrollTo(0, 0);
}
async function showGang(id, preserveScroll = false) {
  const token = ++renderToken, g = await api('/api/gangs/' + encodeURIComponent(id));
  if (token !== renderToken) return;
  currentDetail = {type: 'gang', id};
  const holdings = list(g.territory_list);
  app.innerHTML = `<button class="back" data-back="gangs">← Gangs</button><div class="eyebrow">${esc(g.gang_type)} · gang record</div><h2>${esc(short(g.name))}</h2><section class="region-intro">${narrative(g.backstory, g.backstory_source, g.evidence || [`Faction: ${g.gang_type}`, `${list(g.fighters).length} fighter records`, `Holdings: ${holdings.map(t => t.territory).join(', ') || 'None recorded'}`, `${list(g.battles).length} recorded battles`], g)}</section>${storyStream(g.narrative_stream, 'gang')}<h3 class="section-title">Between engagements</h3>${list(g.downtime).slice(0, 1).map(downtime).join('') || empty('No downtime account is available.')}<div class="sectionhead"><h3>Fighters</h3><button class="text-button" data-gang-filter="${esc(g.gang_id)}">Find this gang’s fighters →</button></div><div class="grid">${list(g.fighters).map(fighterCard).join('') || empty('No fighter records are available for this gang.')}</div><h3 class="section-title">Holdings</h3><div class="holdings">${holdings.map(t => `<button class="holding" data-territory="${esc(t.id)}">${esc(t.territory)} <span>→</span></button>`).join('') || '<p class="muted">No current holdings are recorded.</p>'}</div><h3 class="section-title">Campaign record</h3>${list(g.battles).map(b => battle(b)).join('')}<details class="mechanics-fold" data-key="gang-mechanics"><summary>Current mechanical evidence</summary><div class="card system-state">${[['Reputation', g.reputation], ['Rating', g.rating], ['Credits', g.credits], ['Territories recorded', g.territories], ['Source updated', g.updated_at]].map(([label, value]) => `<div class="row"><span>${esc(label)}</span><span>${label === 'Source updated' ? esc(date(value,true) || 'Not recorded') : esc(value ?? 'Not recorded')}</span></div>`).join('')}</div></details>`;
  if (!preserveScroll) window.scrollTo(0, 0);
}
async function showTerritory(id, preserveScroll = false) {
  const token = ++renderToken, t = await api('/api/territories/' + encodeURIComponent(id));
  if (token !== renderToken) return;
  currentDetail = {type: 'territory', id};
  const related = data.battles.filter(b => b.territory === t.territory);
  app.innerHTML = `<button class="back" data-back="places">← Places</button><div class="eyebrow">Territory · held by ${esc(short(t.gang_name))}</div><h2>${esc(t.territory)}</h2><section class="region-intro">${narrative(t.backstory, t.backstory_source || 'inference', t.evidence || [`Current holder: ${short(t.gang_name)}`, `Card: ${t.card || 'Not recorded'}`, `Default holding: ${t.is_default ? 'Yes' : 'No'}`, `${related.length} related battle records`], t)}</section>${storyStream(t.narrative_stream, 'territory')}<h3 class="section-title">Fighting over this ground</h3>${related.map(b => battle(b)).join('') || empty('No battle over this territory is recorded.')}`;
  if (!preserveScroll) window.scrollTo(0, 0);
}
async function showLore(id, preserveScroll = false) {
  const token = ++renderToken, record = await api('/api/lore/' + encodeURIComponent(id));
  if (token !== renderToken) return;
  currentDetail = {type: 'lore', id};
  app.innerHTML = `<button class="back" data-back="archive">← Archive</button><div class="eyebrow">${esc(record.source_type)} · authored source</div><h2>${esc(record.title)}</h2><section class="archive-document">${prose(record.content)}</section>`;
  if (!preserveScroll) window.scrollTo(0, 0);
}
async function openDetail(type, id, preserveScroll = false) {
  if (type === 'gang') return showGang(id, preserveScroll);
  if (type === 'fighter') return showFighter(id, preserveScroll);
  if (type === 'territory') return showTerritory(id, preserveScroll);
  if (type === 'lore') return showLore(id, preserveScroll);
}
function handleError(error) {
  console.error(error);
  app.innerHTML = `<section class="empty-state error-state" role="alert"><h2>The chronicle could not be opened</h2><p>${esc(error.message || 'Please try again.')}</p><button data-retry>Try again</button></section>`;
}
function updateFilter(event) {
  const element = event.target.closest('[data-filter]');
  if (!element) return;
  filters[element.dataset.filterView][element.dataset.filter] = element.value;
  listResults(element.dataset.filterView);
}
app.addEventListener('input', updateFilter);
app.addEventListener('change', event => { if (event.target.matches('select[data-filter]')) updateFilter(event); });
app.addEventListener('submit', event => { if (event.target.matches('[data-filter-form]')) event.preventDefault(); });
app.addEventListener('submit', async event => {
  const form = event.target;
  if (!form.matches('[data-identity-form]')) return;
  event.preventDefault();
  const status = form.querySelector('.identity-status'), button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  const identity = {};
  for (const [key,value] of new FormData(form)) {
    const text = String(value).trim();
    if (text) identity[key] = key === 'narration_mode' ? text : text.split(';').map(x => x.trim()).filter(Boolean);
  }
  try {
    await api('/api/fighters/' + encodeURIComponent(form.dataset.identityForm) + '/identity', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({identity})});
    fightersCache = null;
    await showFighter(form.dataset.identityForm, true);
  } catch (error) { status.textContent = error.message; button.disabled = false; }
});
app.addEventListener('click', event => {
  const target = event.target.closest('button');
  if (!target) return;
  let task;
  if (target.dataset.fighter) task = showFighter(target.dataset.fighter);
  if (target.dataset.gang) task = showGang(target.dataset.gang);
  if (target.dataset.territory) task = showTerritory(target.dataset.territory);
  if (target.dataset.lore) task = showLore(target.dataset.lore);
  if (target.dataset.back) task = render(target.dataset.back);
  if (target.dataset.clear) { filters[target.dataset.clear] = {...defaults[target.dataset.clear]}; task = render(target.dataset.clear); }
  if (target.dataset.gangFilter) { filters.fighters.gang = target.dataset.gangFilter; task = render('fighters'); }
  if (target.hasAttribute('data-retry')) task = refreshDashboard(false);
  if (task?.catch) task.catch(handleError);
});
document.querySelectorAll('nav button').forEach(button => button.addEventListener('click', () => render(button.dataset.view).catch(handleError)));
syncNow.addEventListener('click', async () => {
  syncNow.disabled = true; syncNow.textContent = 'Requesting…';
  try { await api('/api/sync', {method: 'POST'}); await refreshStatus(); }
  catch (error) { health.textContent = error.message; health.classList.add('has-error'); syncNow.disabled = false; syncNow.textContent = 'Refresh from Sheet'; }
});
if (logout) logout.addEventListener('click', async () => { await api('/api/logout', {method: 'POST'}); location.replace('/login'); });
async function startApp() {
  const session = await api('/api/session');
  if (session.auth_required && !session.authenticated) { location.replace('/login'); return; }
  if (logout) logout.hidden = !session.auth_required;
  await refreshDashboard(false); await refreshStatus();
  setInterval(() => refreshStatus().catch(error => { health.textContent = 'Could not check the latest Sheet refresh'; health.classList.add('has-error'); console.error(error); }), 15000);
}
startApp().catch(handleError);
