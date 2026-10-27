'use strict';

const app = document.querySelector('#app');
const health = document.querySelector('#health');
const syncNow = document.querySelector('#syncNow');
const logout = document.querySelector('#logout');
let data = null, activeView = 'chronicle', currentDetail = null, fightersCache = null, historyTimeline = null, historyLoading = false;
let renderToken = 0, lastStatusFingerprint = null, refreshing = false;
const defaults = {fighters: {q: '', gang: '', status: '', role: '', listing: ''}, gangs: {q: '', faction: ''}, places: {q: '', owner: ''}, battles: {q: '', gang: ''}};
let filters = JSON.parse(JSON.stringify(defaults));
const historyFilters = {q: '', gang: '', fighter: '', place: '', action: '', phase: '', battle: '', from: '', to: ''};
let selectedHistoryEvent = null, selectedHistoryBattle = null;

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
function authoredDossier(value) {
  const lines = String(value || '').replace(/\r/g, '').split('\n');
  const output = [], fields = [], paragraph = [];
  let sawBody = false;
  const flushParagraph = () => { if (paragraph.length) output.push(`<p>${inline(paragraph.join('\n')).replaceAll('\n','<br>')}</p>`); paragraph.length = 0; };
  const flushFields = () => { if (fields.length) output.push(`<dl class="personnel-fields">${fields.map(([label,text]) => `<div><dt>${inline(label)}</dt><dd>${inline(text)}</dd></div>`).join('')}</dl>`); fields.length = 0; };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { flushParagraph(); continue; }
    if (/^[A-Z][A-Z '-]+,\s*[A-Z][\w '-]+$/.test(line) && !sawBody && !output.length) {
      flushParagraph(); output.push(`<div class="personnel-designation">${inline(line)}</div>`); continue;
    }
    const field = line.match(/^([^:\n]{2,48}):\s*(.+)$/);
    if (field && !/^\[ERR::/i.test(line)) { flushParagraph(); fields.push([field[1],field[2]]); continue; }
    if (/^(Workshop Audit|ATTACHED INCIDENT LOG|SURGICAL RECORD|PERSONNEL TRANSFER|MEDICAL PROCUREMENT AUTHORISATION)\b/i.test(line)) {
      flushParagraph(); flushFields(); sawBody = true; output.push(`<h4 class="personnel-section-label">${inline(line)}</h4>`); continue;
    }
    if (/^C9-(?:MK|AUX|ASSOC)\//i.test(line)) {
      flushParagraph(); flushFields(); output.push(`<div class="personnel-watermark">${inline(line)}</div>`); continue;
    }
    if (/^\[SYS\.|^\[ERR::|^[├└│]/.test(line)) {
      flushParagraph(); flushFields(); output.push(`<div class="personnel-system">${inline(line)}</div>`); continue;
    }
    if (/^[“"‘].*[”"’]$/.test(line)) {
      flushParagraph(); flushFields(); output.push(`<blockquote class="personnel-quote">${inline(line)}</blockquote>`); sawBody = true; continue;
    }
    flushFields(); paragraph.push(line); sawBody = true;
  }
  flushParagraph(); flushFields();
  return `<div class="authored-dossier">${output.join('')}</div>`;
}
function blocks(document, fallback = '') {
  const content = list(document?.blocks);
  const statusMessage = document?.writer_status === 'stale'
    ? (document.writer_message || 'Earlier narrative retained; it has not been regenerated with the current writing rules.')
    : document?.writer_message || (document?.writer_status === 'unconfigured' ? 'Narrative pending · configure the server-side writing provider.' : `Narrative ${document?.writer_status} · an explicit writing run is required.`);
  if (!content.length) {
    if (document?.writer_status && document.writer_status !== 'ready') return `<p class="writer-pending" role="status">${esc(statusMessage)}</p>`;
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
  const composition = document.composition;
  const wrapperDate = composition && document.date_display && !document.suppress_date
    ? `<div class="record-ui-date">${esc(document.date_display.realDisplay || '')}</div>` : '';
  const header = composition
    ? `<header class="record-header composed-record">${composition.heading ? `<div class="archive-heading">+++ ${inline(composition.heading)} +++</div>` : ''}<dl class="metadata-group">${document.reference ? `<div><dt>RECORD</dt><dd>${esc(document.reference)}</dd></div>` : ''}${document.date_display?.imperialDisplay?.endsWith('.M41') && !document.suppress_date ? `<div><dt>DATE</dt><dd>${esc(document.date_display.imperialDisplay)}</dd></div>` : ''}${composition.subject ? `<div><dt>SUBJECT</dt><dd>${inline(composition.subject)}</dd></div>` : ''}</dl></header>`
    : document.document_type ? `<header class="record-header"><div class="eyebrow">${esc(human(document.document_type))}</div>${document.date_display && !document.suppress_date ? dateStamp(document) : ''}<dl class="metadata-group">${list(document.metadata).map(field => `<div><dt>${inline(field.label)}</dt><dd>${inline(field.value)}</dd></div>`).join('')}</dl></header>` : '';
  const status = document?.writer_status && document.writer_status !== 'ready' ? `<p class="writer-pending" role="status">${esc(statusMessage)}</p>` : '';
  return `${wrapperDate}${status}${header}<div class="record-body">${content.map(block => node(block)).join('')}</div>${document.termination ? node(document.termination) : ''}`;
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
  const authoredBody = isAuthored ? (/C-NINE story/i.test(String(source || '')) ? authoredDossier(value) : prose(value)) : blocks(document, value);
  return `<div class="narrative"><div class="eyebrow">${isAuthored ? 'Authored campaign record' : 'Generated inference'}</div>${authoredBody}</div>${isAuthored ? `<div class="authored-source">${esc(source || 'Authored campaign canon')}</div>` : evidence(basis, {...meta, ...document})}`;
}
const empty = message => `<div class="empty-state"><p>${esc(message)}</p></div>`;
async function api(url, options) {
  const response = await fetch(url, {cache: 'no-store', ...options});
  if (response.status === 401) { location.replace('/login'); throw new Error('Please sign in to continue.'); }
  const result = await response.json();
  if (!response.ok) { const error=new Error(result.error || 'The chronicle could not complete that request.'); error.status=response.status; throw error; }
  return result;
}
function editorialPreview(state) {
  const saved = Object.entries(state || {}).find(([key]) => key.startsWith('writer_preview:') && !key.endsWith(':claimed'));
  if (!saved) return '';
  let preview;
  try { preview = JSON.parse(saved[1]); } catch { return ''; }
  const usage = preview.usage || {};
  return `<section class="editorial-preview"><h3>Writing preview</h3><p class="muted">Editorial test only. These entries have not been added to campaign history.</p><p>${esc(preview.model || '')} · ${esc(preview.effort || '')} · ${esc(preview.status)} · ${Number(usage.requests_attempted) || 0} requests · ${Number(usage.input_tokens) || 0} input / ${Number(usage.output_tokens) || 0} output tokens · ${Number(usage.cached_input_tokens) || 0} cached input tokens</p>${preview.message ? `<p>${esc(preview.message)}</p>` : ''}${list(preview.entries).map(entry => `<article class="biography"><h4>${esc(entry.label)}</h4>${blocks(entry.document)}</article>`).join('')}</section>`;
}

function editorialComparison(state) {
  const saved = Object.entries(state || {}).find(([key]) => key.startsWith('writer_comparison:') && !key.endsWith(':claimed'));
  if (!saved) return '';
  let comparison;
  try { comparison = JSON.parse(saved[1]); } catch { return ''; }
  const usage = comparison.usage || {};
  return `<section class="editorial-comparison"><h3>Writing comparison</h3><p class="muted">Three matched cases, two versions each. These are editorial samples, outside campaign history. A/B order is independently shuffled for each case. Judge each pair on its own.</p><p>${esc(comparison.model)} · ${esc(comparison.effort)} · ${esc(comparison.status)} · ${Number(usage.requests_attempted) || 0} requests · ${Number(usage.input_tokens) || 0} input / ${Number(usage.output_tokens) || 0} output tokens · ${Number(usage.cached_input_tokens) || 0} cached input tokens</p><p>Look for an evocative picture, meaningful detail, the subject's identity, natural voice and a developed consequence. Both versions receive the same evidence.</p>${list(comparison.cases).map(item => `<section class="comparison-case"><h4>${esc(item.label)}</h4><details class="evidence"><summary>Shared evidence</summary><pre>${esc(JSON.stringify(item.evidence,null,2))}</pre></details><div class="comparison-pair">${list(item.entries).map(entry => `<article class="biography"><h4>${esc(entry.label)}</h4>${blocks(entry.document)}</article>`).join('')}</div></section>`).join('')}</section>`;
}

function campaignAccount(document) {
  return document?.writer_status === 'ready' ? `<section class="biography"><h3>Campaign account</h3><div class="eyebrow">Generated inference</div>${blocks(document)}${evidence(document.evidence,document)}</section>` : '';
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
    else if (activeView !== 'workshop') await render(activeView, true);
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
  return `<div class="sectionhead"><div><div class="eyebrow">Dominion Krakamunda</div><h2>Campaign Chronicle</h2></div><span class="quiet-label">Lives · claims · consequences</span></div>${region ? `<section class="region-intro">${narrative(region.backstory, region.backstory_source || 'inference', region.evidence || [`${data.gangs.length} active gang records`, `${data.territories.length} territory records`, `${data.battles.length} recorded battles`], region)}</section>` : ''}<section class="campaign-timeline"><div class="timeline-heading"><div><div class="eyebrow">Recorded campaign history</div><h3>Battle and downtime timeline</h3><p>Campaign engagements and the downtime between them.</p></div><span class="timeline-refresh-state" id="historyImportLabel">Loading archive…</span></div><div id="campaignTimeline" class="loading-state" role="status">Reading the campaign history archive…</div></section><div class="split chronicle-layout"><section><h3 class="section-title">Recent battle accounts</h3>${data.battles.slice(0, 3).map((record, index) => battle(record, index === 0)).join('') || empty('No battle records have been imported yet.')}<details class="ledger-fold" data-key="campaign-ledger"><summary>Latest mechanical campaign records <span>${data.campaignEvents.length}</span></summary><div class="timeline">${data.campaignEvents.map(campaignEvent).join('') || empty('No changes have been recorded since the baseline.')}</div></details></section><aside><h3 class="section-title">Between games</h3>${latestDowntime.map(downtime).join('') || empty('Downtime accounts will appear as the campaign develops.')}</aside></div>`;
}

function historyDate(value, time = true) {
  if (value === null || value === undefined || value === '') return 'Time unrecorded';
  return NCCEWriting.formatDate(typeof value === 'number' ? new Date(value).toISOString() : value, time).realDisplay;
}
function historyImperial(value) {
  return value === null || value === undefined || value === '' ? 'Datestamp unavailable' : NCCEWriting.formatDate(typeof value === 'number' ? new Date(value).toISOString() : value, true).imperialDisplay;
}
function historyStamp(value) {
  return `<time class="history-date"><span class="timeline-diegetic">${esc(historyImperial(value))}</span><small class="timeline-mechanical">${esc(historyDate(value))}</small></time>`;
}
function historyDuration(seconds) {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return 'Unrecorded';
  const minutes = Math.round(seconds / 60);
  return minutes >= 60 ? `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2,'0')}m` : `${minutes}m`;
}
const historyPhaseLabel = phase => ({during_battle:'Battle',downtime:'Downtime',current_downtime:'Downtime',pre_first_battle:'Before first battle',pre_battle:'Before first battle',inter_session_gap:'Intermission',unassigned:'Unassigned',unavailable:'Undated',ambiguous_overlap:'Overlapping engagements',open_battle_window:'Battle in progress'}[phase] || human(phase));
let historyViewport = null, selectedHistoryCluster = null, historyDrag = null, historySuppressDragClick = false;
const historyPalette = ['#80d8be','#ecba6a','#bf9ff4','#ed8fa8','#7ec5f0','#d3dc80','#f19b6d','#a6b8f2','#77ced4','#d3a1cb'];
function timelineFilterOptions() {
  const gangs = new Map((data?.gangs || []).map(gang => [String(gang.gang_id), short(gang.name)]));
  for (const event of list(historyTimeline?.events)) if (event.gang_id && !gangs.has(String(event.gang_id))) gangs.set(String(event.gang_id), event.gang_name || 'Gang ' + String(event.gang_id).slice(0,8));
  for (const battle of list(historyTimeline?.battles)) for (const gang of list(battle.gangs)) if (gang.gang_id && !gangs.has(String(gang.gang_id))) gangs.set(String(gang.gang_id), gang.name || 'Gang ' + String(gang.gang_id).slice(0,8));
  return [...gangs.entries()].sort((a,b)=>a[1].localeCompare(b[1]));
}
function historyGangColor(id) {
  const index = timelineFilterOptions().findIndex(([key]) => String(id)===key);
  return historyPalette[Math.max(0,index) % historyPalette.length];
}
function historyIntervals(battle) {
  const sessions = list(battle.sessions).filter(s=>s.start_at && s.end_at && Date.parse(s.end_at)>=Date.parse(s.start_at));
  return sessions.length ? sessions : battle.start_at && battle.end_at ? [{start_at:battle.start_at,end_at:battle.end_at}] : [];
}
function historyPlaytime(battle) {
  if (Number.isFinite(battle.playtime_seconds)) return battle.playtime_seconds;
  const intervals = historyIntervals(battle).map(s=>[Date.parse(s.start_at),Date.parse(s.end_at)]).sort((a,b)=>a[0]-b[0]), merged=[];
  for (const [a,b] of intervals) {
    if (merged.length && a<=merged[merged.length-1][1]) merged[merged.length-1][1]=Math.max(b,merged[merged.length-1][1]);
    else merged.push([a,b]);
  }
  return merged.length ? merged.reduce((sum,[a,b])=>sum+(b-a)/1000,0) : null;
}
function historyEventPeriod(event, battle) {
  const gang=String(event.gang_id || ''), t=Date.parse(event.recorded_at);
  if (!Number.isFinite(t) || !list(battle.gang_ids).map(String).includes(gang)) return null;
  if (historyIntervals(battle).some(s=>t>=Date.parse(s.start_at) && t<=Date.parse(s.end_at))) return 'battle';
  const end=Date.parse(battle.end_at), start=Date.parse(battle.start_at);
  if (!Number.isFinite(end) || t<=end) return null;
  const next=list(historyTimeline?.battles).filter(b=>b.battle_id!==battle.battle_id && list(b.gang_ids).map(String).includes(gang) && Date.parse(b.start_at)>start).map(b=>Date.parse(b.start_at));
  return !next.length || t<Math.min(...next) ? 'downtime' : null;
}
function timelineRows() {
  const query = historyFilters.q.trim().toLocaleLowerCase();
  const selected=historyFilters.battle && list(historyTimeline?.battles).find(b=>String(b.battle_id)===historyFilters.battle);
  const localDay = value => value && Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Warsaw',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value)) : '';
  return list(historyTimeline?.events).filter(event =>
    (!historyFilters.gang || String(event.gang_id || '') === historyFilters.gang) &&
    (!historyFilters.fighter || String(event.fighter_id || '') === historyFilters.fighter) &&
    (!historyFilters.place || String(event.territory_id || '') === historyFilters.place) &&
    (!historyFilters.action || String(event.action_type || '') === historyFilters.action) &&
    (!historyFilters.phase || event.phase === historyFilters.phase || (historyFilters.phase==='downtime' && event.phase==='current_downtime')) &&
    (!historyFilters.battle || (selected && historyEventPeriod(event,selected))) &&
    (!historyFilters.from || localDay(event.recorded_at)>=historyFilters.from) &&
    (!historyFilters.to || (localDay(event.recorded_at) && localDay(event.recorded_at)<=historyFilters.to)) &&
    (!query || [event.entity_label,event.gang_name,event.action_type,event.description,event.event_id].some(v=>String(v || '').toLocaleLowerCase().includes(query)))
  );
}
function historyIcon(event) {
  const type=event.action_type || '';
  return /kill|death|dead/.test(type)?'☠':/injur|recover|heal/.test(type)?'✚':/xp|experien/.test(type)?'✦':/advance|skill|promot/.test(type)?'↑':/credit|wealth|income/.test(type)?'¤':/equip|weapon|stash|item/.test(type)?'⚒':/recruit|added|hire/.test(type)?'+':/territor|claim/.test(type)?'⚑':/reputation/.test(type)?'★':/battle/.test(type)?'⚔':'◆';
}
function historyEventItem(event) {
  return `<li><button type="button" class="history-activity-entry" data-history-event="${esc(event.event_id)}"><span class="history-event-icon" aria-label="${esc(human(event.action_type))}">${historyIcon(event)}</span><span>${historyStamp(event.recorded_at)}<span class="timeline-mechanical history-event-description">${esc(event.description || human(event.action_type) || 'Change recorded')}</span></span></button></li>`;
}
function historyEntityLink(kind,id,name) {
  return id ? `<button class="text-button history-entity-link" data-${kind}="${esc(id)}">${esc(name)}</button>` : esc(name || 'Unrecorded');
}
function historyActivityGroup(rows, period) {
  const groups=new Map();
  for (const event of rows) {
    const gang=String(event.gang_id || ''), key=event.local_fighter_id ? 'local:'+event.local_fighter_id : event.fighter_id ? 'fighter:'+event.fighter_id : 'gang';
    if (!groups.has(gang)) groups.set(gang,{name:event.gang_name || 'Campaign', fighters:new Map()});
    const group=groups.get(gang);
    if (!group.fighters.has(key)) group.fighters.set(key,{name:event.fighter_name || (event.fighter_id ? event.entity_label : 'Gang affairs'),events:[]});
    group.fighters.get(key).events.push(event);
  }
  return `<details class="history-period" data-history-fold="period-${period}"${period==='battle'?' open':''}><summary>${period==='battle'?'Battle':'Downtime'} <span class="tag">${rows.length}</span></summary>${rows.length?[...groups].map(([id,g])=>`<details class="history-gang-group" data-history-fold="${period}-gang-${esc(id)}" style="--gang-color:${historyGangColor(id)}"><summary>${esc(short(g.name))} <span>${[...g.fighters.values()].reduce((n,f)=>n+f.events.length,0)} records</span></summary>${[...g.fighters].map(([key,f])=>`<details class="history-fighter-group" data-history-fold="${period}-${esc(id)}-${esc(key)}"><summary>${esc(f.name)} <span>${f.events.length}</span></summary><ul>${f.events.map(historyEventItem).join('')}</ul></details>`).join('')}</details>`).join(''):'<p class="muted">No recorded changes in this interval.</p>'}</details>`;
}
function timelineDetail(event, selectedBattle) {
  if (selectedBattle) {
    const b=selectedBattle;
    const parties=b.attacker && b.defender ? [
      {name:b.attacker,gang_id:b.attacker_gang_id || list(b.gangs).find(g=>g.name===b.attacker)?.gang_id},
      {name:b.defender,gang_id:b.defender_gang_id || list(b.gangs).find(g=>g.name===b.defender)?.gang_id}
    ] : list(b.gangs);
    const participants=parties.map(g=>historyEntityLink('gang',g.gang_id,short(g.name))).join('<span class="history-versus">VS</span>');
    const related=timelineRows().slice().sort((a,b)=>Date.parse(a.recorded_at)-Date.parse(b.recorded_at));
    const battleRows=related.filter(e=>historyEventPeriod(e,b)==='battle'), downtimeRows=related.filter(e=>historyEventPeriod(e,b)==='downtime');
    const winnerId=b.winner_gang_id || list(data?.gangs).find(g=>g.name===b.winner)?.gang_id;
    const places=list(data?.territories).filter(t=>t.territory===b.territory);
    const placeId=b.local_territory_id || (places.length===1?places[0].id:null);
    return `<article class="timeline-detail"><header class="timeline-diegetic history-record-header"><div class="eyebrow">+++ ENGAGEMENT ARCHIVE // RECORD RETRIEVED +++</div><div class="history-mission"><span>MISSION</span><h4>${esc(b.scenario || 'Battle')}</h4></div><div class="history-participants">${participants}</div><div class="history-record-id">REGISTRY: KRAK/ENG/${esc(b.battle_id)} // ${esc(String(b.status || 'registered').toUpperCase())}</div></header><dl>${b.cycle!==null && b.cycle!==undefined?`<div><dt>Cycle</dt><dd>${esc(b.cycle)}</dd></div>`:''}<div><dt>Time Window</dt><dd><div class="timeline-diegetic history-imperial-window">${esc(historyImperial(b.start_at))} — ${esc(historyImperial(b.end_at))}</div><div class="history-real-window">${esc(historyDate(b.start_at))} — ${esc(historyDate(b.end_at))}<strong>Engagement time: ${historyDuration(historyPlaytime(b))}</strong></div></dd></div><div><dt>Winner</dt><dd>${historyEntityLink('gang',winnerId,b.winner || 'Unrecorded')}</dd></div><div><dt>Campaign Record</dt><dd class="timeline-diegetic history-record-id">RECORD-KEY // ${esc(b.battle_id)}</dd></div>${b.territory?`<div><dt>Territory</dt><dd>${historyEntityLink('territory',placeId,b.territory)}</dd></div>`:''}</dl><section class="timeline-battle-activity"><div class="evidence-label history-events-heading">+++ RECORDED EVENTS // CHRONOLOGICAL INDEX +++</div>${historyActivityGroup(battleRows,'battle')}${historyActivityGroup(downtimeRows,'downtime')}</section></article>`;
  }
  if (!event) return `<div class="timeline-detail muted">Select a battle, event or numbered group.</div>`;
  return `<article class="timeline-detail"><div class="timeline-diegetic eyebrow">+++ ACTIVITY REGISTER // ${esc(event.event_id)} +++</div><h4>${historyIcon(event)} ${esc(event.entity_label || event.gang_name || 'Campaign event')}</h4>${historyStamp(event.recorded_at)}<div class="timeline-mechanical history-mechanical-panel"><div class="evidence-label">Mechanical record · ${esc(human(event.action_type))}</div><p>${esc(event.description || 'Change recorded')}</p></div>${event.gang_id?`<p>Gang: ${historyEntityLink('gang',event.gang_id,short(event.gang_name))}</p>`:''}${event.local_fighter_id?`<p>Fighter: ${historyEntityLink('fighter',event.local_fighter_id,event.fighter_name)}</p>`:''}</article>`;
}
function fighterCampaignHistory(fighter) {
  const events=list(fighter.campaign_history?.events).slice().sort((a,b)=>(b.recorded_at||'').localeCompare(a.recorded_at||''));
  return `<section class="fighter-campaign-history"><h3 class="section-title">Battle and downtime record</h3><ul class="history-fighter-events">${events.map(historyEventItem).join('') || '<li>No archive activity recorded.</li>'}</ul></section>`;
}
function historyClusterEvents(events, x, distance=30) {
  const sorted=events.slice().sort((a,b)=>Date.parse(a.recorded_at)-Date.parse(b.recorded_at)), groups=[];
  for (const event of sorted) {
    const position=x(Date.parse(event.recorded_at)), previous=groups[groups.length-1];
    if (previous && position-previous.firstX<distance) {previous.items.push(event); previous.x=(previous.x*(previous.items.length-1)+position)/previous.items.length;}
    else groups.push({firstX:position,x:position,items:[event]});
  }
  // Reconcile boundary groups so their rendered circles cannot overlap.
  for(let i=1;i<groups.length;i++) {
    const a=groups[i-1],b=groups[i];
    if(b.x-a.x<distance) {const n=a.items.length+b.items.length;a.x=(a.x*a.items.length+b.x*b.items.length)/n;a.items.push(...b.items);groups.splice(i,1);i=Math.max(0,i-2);}
  }
  return groups;
}
function historySetViewport(start,end,bounds) {
  const minimum=Math.min(15*60000,bounds.end-bounds.start), span=Math.min(bounds.end-bounds.start,Math.max(minimum,end-start));
  start=Math.max(bounds.start,Math.min(start,bounds.end-span));
  historyViewport={start,end:start+span};
}
function historyBindDrag(root, viewport, bounds, start, end, plotWidth, width) {
  if (!viewport) return;
  if (!root.dataset.historyDragBound) {
    root.dataset.historyDragBound='1';
    const finish=event=>{
      if (!historyDrag || (event.pointerId!==undefined && event.pointerId!==historyDrag.pointerId)) return;
      const id=historyDrag.pointerId;historyDrag=null;root.classList.remove('history-dragging');
      if(root.hasPointerCapture?.(id))root.releasePointerCapture(id);
    };
    root.addEventListener('pointermove',event=>{
      const drag=historyDrag;
      if (!drag || event.pointerId!==drag.pointerId) return;
      if (event.ctrlKey===false) {finish(event);return;}
      const dx=event.clientX-drag.x,dy=event.clientY-drag.y;
      if (!drag.moved && Math.hypot(dx,dy)<4) return;
      drag.moved=true;historySuppressDragClick=true;event.preventDefault();
      root.classList.add('history-dragging');
      const current=root.querySelector('.campaign-timeline-scroll');
      if(current)current.scrollTop=drag.scrollTop-dy;
      const shift=-dx*(drag.end-drag.start)/drag.plotPixels;
      historySetViewport(drag.start+shift,drag.end+shift,drag.bounds);renderCampaignTimeline();
    });
    for (const name of ['pointerup','pointercancel','lostpointercapture']) root.addEventListener(name,finish);
    root.addEventListener('click',event=>{
      if(historySuppressDragClick && event.target.closest?.('.campaign-timeline-scroll')){
        event.preventDefault();event.stopImmediatePropagation();historySuppressDragClick=false;
      }
    },true);
  }
  viewport.addEventListener('pointerdown',event=>{
    historySuppressDragClick=false;
    if(!event.ctrlKey || event.button!==0)return;
    event.preventDefault();
    const rect=viewport.querySelector('svg').getBoundingClientRect();
    historyDrag={pointerId:event.pointerId,x:event.clientX,y:event.clientY,start,end,bounds,
      plotPixels:plotWidth*rect.width/width,scrollTop:viewport.scrollTop || 0,moved:false};
    // Capture on the stable root: chart children are replaced while panning.
    root.setPointerCapture(event.pointerId);
  });
}
function renderCampaignTimeline() {
  const root=document.querySelector('#campaignTimeline'), label=document.querySelector('#historyImportLabel');
  if (!root) return;
  if (!historyTimeline) {root.innerHTML='<p class="loading-state">Reading the campaign archive…</p>';return;}
  const {battles=[],events=[],import:importStatus={}}=historyTimeline;
  if (label) label.textContent=importStatus.last_imported_at ? `Archive checked ${historyDate(importStatus.last_imported_at)}` : 'Archive awaiting refresh';
  const rows=timelineRows(), gangOptions=timelineFilterOptions();
  const options=(values,current)=>values.map(([key,name])=>`<option value="${esc(key)}"${current===key?' selected':''}>${esc(name)}</option>`).join('');
  const fighters=[...new Map(events.filter(e=>e.fighter_id).map(e=>[String(e.fighter_id),e.fighter_name || e.entity_label])).entries()].sort((a,b)=>a[1].localeCompare(b[1]));
  const places=[...new Map([...events.filter(e=>e.territory_id).map(e=>[String(e.territory_id),e.place_name || 'Territory']),...battles.filter(b=>b.territory_id).map(b=>[String(b.territory_id),b.territory || 'Territory'])]).entries()];
  const periods=['during_battle','downtime','pre_first_battle','inter_session_gap','unassigned','unavailable'].map(p=>[p,historyPhaseLabel(p)]);
  const fields=[['q','Find an event'],['gang','Gang',gangOptions],['fighter','Fighter',fighters],['battle','Battle',battles.map(b=>[b.battle_id,`${b.scenario || 'Battle'} · ${list(b.gangs).map(g=>short(g.name)).join(' vs ')}`])],['place','Place',places],['action','Event type',[...new Set(events.map(e=>e.action_type).filter(Boolean))].sort().map(t=>[t,human(t)])],['phase','Period',periods],['from','From'],['to','To']];
  const filtersMarkup=`<form class="timeline-filters" data-history-filter-form>${fields.map(([key,name,values])=>`<label>${name}${values?`<select data-history-filter="${key}"><option value="">All ${key==='phase'?'periods':name.toLowerCase()+'s'}</option>${options(values,historyFilters[key])}</select>`:`<input type="${key==='q'?'search':'date'}" data-history-filter="${key}" value="${esc(historyFilters[key])}">`}</label>`).join('')}</form>`;
  if (!importStatus.available && !battles.length && !events.length) {root.innerHTML=filtersMarkup+empty('Refresh the Sheet to load campaign history.');return;}
  const day=value=>value && Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Warsaw'}).format(new Date(value)) : '';
  const scoped=battles.filter(b=>(!historyFilters.battle || String(b.battle_id)===historyFilters.battle) && (!historyFilters.gang || list(b.gang_ids).map(String).includes(historyFilters.gang)) && (!historyFilters.place || String(b.territory_id || '')===historyFilters.place) && (!historyFilters.from || day(b.end_at || b.start_at || b.documented_at)>=historyFilters.from) && (!historyFilters.to || day(b.start_at || b.documented_at)<=historyFilters.to));
  const dates=[...rows.map(e=>e.recorded_at),...scoped.flatMap(b=>[b.start_at,b.end_at,b.documented_at])].map(Date.parse).filter(Number.isFinite);
  let min=dates.length?Math.min(...dates):Date.now()-86400000, max=dates.length?Math.max(...dates):Date.now();
  if (max-min<86400000) {min-=43200000;max+=43200000;}
  const bounds={start:min,end:max};
  if (!historyViewport) historyViewport={...bounds};
  historySetViewport(historyViewport.start,historyViewport.end,bounds);
  const {start,end}=historyViewport, left=230,right=24,width=Math.max(900,Math.min(1800,app.clientWidth-40)),plotWidth=width-left-right;
  const x=t=>left+(t-start)/(end-start)*plotWidth;
  const laneIds=historyFilters.gang?[historyFilters.gang]:[...new Set([...scoped.flatMap(b=>list(b.gang_ids).map(String)),...rows.map(e=>String(e.gang_id || ''))])];
  if (!laneIds.length) laneIds.push('');
  const laneNames=new Map(gangOptions), height=100+laneIds.length*112;
  const ticks=Array.from({length:5},(_,i)=>start+(end-start)*i/4);
  const grid=ticks.map((t,i)=>`<g class="timeline-axis-tick"><line x1="${x(t)}" y1="60" x2="${x(t)}" y2="${height-12}"/><text class="timeline-axis-imperial" x="${x(t)}" y="22" text-anchor="${i===0?'start':i===4?'end':'middle'}">${esc(historyImperial(t))}</text><text x="${x(t)}" y="42" text-anchor="${i===0?'start':i===4?'end':'middle'}">${esc(historyDate(t,end-start<3*86400000))}</text></g>`).join('');
  const clusterMap=new Map();
  const lanes=laneIds.map((gangId,index)=>{
    const y=105+index*112,color=historyGangColor(gangId),name=laneNames.get(gangId) || 'Campaign';
    const gangBattles=scoped.filter(b=>list(b.gang_ids).map(String).includes(gangId));
    const ordered=gangBattles.filter(b=>b.start_at && b.end_at).slice().sort((a,b)=>Date.parse(a.start_at)-Date.parse(b.start_at));
    const gaps=ordered.slice(1).map((b,i)=>{const previous=ordered[i],a=Math.max(start,Date.parse(previous.end_at)),z=Math.min(end,Date.parse(b.start_at));return z>a?`<rect class="timeline-downtime" x="${x(a)}" y="${y+39}" width="${x(z)-x(a)}" height="6"><title>Downtime</title></rect>`:'';}).join('');
    const bars=gangBattles.flatMap(b=>historyIntervals(b).filter(s=>Date.parse(s.end_at)>=start && Date.parse(s.start_at)<=end).map(s=>{
      const a=Math.max(start,Date.parse(s.start_at)),z=Math.min(end,Date.parse(s.end_at)),w=Math.max(5,x(z)-x(a));
      const title=`${b.scenario || 'Battle'} · ${list(b.gangs).map(g=>short(g.name)).join(' vs ')}\n${historyImperial(s.start_at)} — ${historyImperial(s.end_at)}\n${historyDate(s.start_at)} — ${historyDate(s.end_at)} · Engagement time ${historyDuration(historyPlaytime(b))}`;
      return `<g class="timeline-battle-span${String(selectedHistoryBattle)===String(b.battle_id)?' selected':''}" data-history-battle="${esc(b.battle_id)}" role="button" tabindex="0" aria-label="${esc(title)}"><rect x="${x(a)}" y="${y+6}" width="${w}" height="23" rx="3"><title>${esc(title)}</title></rect>${w>95?`<text x="${x(a)+6}" y="${y+22}">${esc(b.scenario || 'Battle')}</text>`:''}</g>`;
    })).join('');
    const noTime=gangBattles.filter(b=>(!b.start_at || !b.end_at) && Date.parse(b.documented_at)>=start && Date.parse(b.documented_at)<=end).map(b=>`<path class="timeline-unverified" data-history-battle="${esc(b.battle_id)}" tabindex="0" role="button" aria-label="${esc(b.scenario || 'Battle')} · time unrecorded" d="M ${x(Date.parse(b.documented_at))} ${y+10} l 6 6 -6 6 -6 -6 z"/>`).join('');
    const clusters=historyClusterEvents(rows.filter(e=>String(e.gang_id || '')===gangId && Date.parse(e.recorded_at)>=start && Date.parse(e.recorded_at)<=end),x);
    const dots=clusters.map((c,i)=>{
      const count=c.items.length,key=`${gangId}:${i}`,title=count>1?`${count} recorded changes · ${short(name)}\n${historyDate(c.items[0].recorded_at)} — ${historyDate(c.items[count-1].recorded_at)}`:`${c.items[0].entity_label || name} · ${human(c.items[0].action_type)}\n${historyImperial(c.items[0].recorded_at)}\n${historyDate(c.items[0].recorded_at)}`;
      if (count>1) clusterMap.set(key,c.items.map(e=>String(e.event_id)));
      return `<g class="timeline-marker${count>1?' timeline-cluster':''}" ${count>1?`data-history-cluster="${esc(key)}"`:`data-history-event="${esc(c.items[0].event_id)}"`} tabindex="0" role="button" aria-label="${esc(title)}"><circle class="timeline-event-point" cx="${c.x}" cy="${y-18}" r="${count>1?12:5}"><title>${esc(title)}</title></circle>${count>1?`<text x="${c.x}" y="${y-14}" text-anchor="middle">${count}</text>`:''}</g>`;
    }).join('');
    const nameParts=short(name).match(/.{1,26}(?:\s|$)|.{1,26}/g) || [name];
    const playtime=gangBattles.reduce((n,b)=>n+(historyPlaytime(b) || 0),0);
    return `<g class="timeline-lane" style="--gang-color:${color}"><text class="timeline-lane-label" x="${left-18}" y="${y-25}" text-anchor="end">${nameParts.slice(0,3).map((part,i)=>`<tspan x="${left-18}" dy="${i?15:0}">${esc(part.trim())}</tspan>`).join('')}<title>${esc(name)}</title></text><text class="timeline-lane-engagements" x="${left-18}" y="${y+20}" text-anchor="end">${gangBattles.length} engagement${gangBattles.length===1?'':'s'}</text><text class="timeline-lane-playtime" x="${left-18}" y="${y+47}" text-anchor="end">${historyDuration(playtime)} engagement time</text><line class="timeline-lane-line" x1="${left}" y1="${y+17}" x2="${width-right}" y2="${y+17}"/><g clip-path="url(#history-plot-clip)">${gaps}${dots}${bars}${noTime}</g></g>`;
  }).join('');
  const visibleIds=new Set(rows.map(e=>String(e.event_id)));
  if (!visibleIds.has(String(selectedHistoryEvent))) selectedHistoryEvent=null;
  if (!scoped.some(b=>String(b.battle_id)===String(selectedHistoryBattle))) selectedHistoryBattle=null;
  const selected=rows.find(e=>String(e.event_id)===String(selectedHistoryEvent)),selectedBattle=scoped.find(b=>String(b.battle_id)===String(selectedHistoryBattle));
  const clusterEvents=rows.filter(e=>list(selectedHistoryCluster).includes(String(e.event_id)));
  const clusterPanel=clusterEvents.length?`<section class="timeline-cluster-panel history-mechanical-panel"><h4>${clusterEvents.length} recorded changes</h4><button type="button" data-history-nav="cluster">Zoom to this group</button><ul>${clusterEvents.map(historyEventItem).join('')}</ul></section>`:'';
  const folds=new Map([...root.querySelectorAll('details[data-history-fold]')].map(f=>[f.dataset.historyFold,f.open]));
  const scroll=root.querySelector('.campaign-timeline-scroll'), scrollLeft=scroll?.scrollLeft || 0, scrollTop=scroll?.scrollTop || 0;
  root.innerHTML=`${filtersMarkup}<div class="timeline-summary"><span>${scoped.length} engagement${scoped.length===1?'':'s'} · ${rows.length} recorded events · ${historyDuration(scoped.reduce((n,b)=>n+(historyPlaytime(b)||0),0))} engagement time</span><span>Imperial datestamps / real-world time</span></div><div class="timeline-navigation"><button data-history-nav="earlier" aria-label="Pan timeline earlier">← Earlier</button><button data-history-nav="out" aria-label="Zoom timeline out">−</button><button data-history-nav="fit">Full campaign</button><button data-history-nav="in" aria-label="Zoom timeline in">+</button><button data-history-nav="later" aria-label="Pan timeline later">Later →</button><span>Ctrl + mouse wheel to zoom · Ctrl + drag to pan · ${((max-min)/(end-start)).toFixed(1)}×</span></div><div class="campaign-timeline-scroll" role="region" aria-label="Campaign battle and downtime timeline" tabindex="0"><svg class="campaign-timeline-svg" viewBox="0 0 ${width} ${height}" role="group" aria-label="Chronological campaign activity grouped by gang"><defs><clipPath id="history-plot-clip"><rect x="${left-12}" y="60" width="${plotWidth+24}" height="${height-60}"/></clipPath></defs>${grid}${lanes}</svg></div><div class="timeline-legend"><span><i class="legend-battle"></i> Battle window</span><span><i class="legend-change"></i> Recorded change / numbered group</span><span><i class="legend-downtime"></i> Downtime</span><span>Colours identify gangs</span></div>${clusterPanel}<div id="historyEventDetail">${timelineDetail(selected,selectedBattle)}</div>`;
  for (const [key,open] of folds) {const fold=[...root.querySelectorAll('[data-history-fold]')].find(f=>f.dataset.historyFold===key);if(fold) fold.open=open;}
  const viewport=root.querySelector('.campaign-timeline-scroll');
  if (viewport) {viewport.scrollLeft=scrollLeft;viewport.scrollTop=scrollTop;}
  historyBindDrag(root,viewport,bounds,start,end,plotWidth,width);
  root.querySelectorAll('[data-history-filter]').forEach(c=>c.addEventListener(c.matches('input[type="search"]')?'input':'change',event=>{
    historyFilters[event.target.dataset.historyFilter]=event.target.value;historyViewport=null;selectedHistoryCluster=null;
    if(event.target.dataset.historyFilter==='battle'){selectedHistoryBattle=event.target.value || null;selectedHistoryEvent=null;}
    const search=event.target.matches('input[type="search"]'),caret=event.target.selectionStart;renderCampaignTimeline();
    if(search){const replacement=root.querySelector('[data-history-filter="q"]');replacement?.focus();if(caret!==null)replacement?.setSelectionRange(caret,caret);}
  }));
  root.querySelector('[data-history-filter-form]')?.addEventListener('submit',e=>e.preventDefault());
  const pick=(control,kind)=>{if(kind==='event'){selectedHistoryEvent=control.dataset.historyEvent;selectedHistoryBattle=null;selectedHistoryCluster=null;}else if(kind==='battle'){selectedHistoryBattle=control.dataset.historyBattle;selectedHistoryEvent=null;selectedHistoryCluster=null;}else{selectedHistoryCluster=clusterMap.get(control.dataset.historyCluster);selectedHistoryEvent=null;selectedHistoryBattle=null;}renderCampaignTimeline();};
  for (const kind of ['event','battle','cluster']) root.querySelectorAll(`[data-history-${kind}]`).forEach(c=>{
    c.addEventListener('click',()=>pick(c,kind));
    if(c.getAttribute('role')==='button')c.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick(c,kind);}});
  });
  const changeView=(a,z)=>{historySetViewport(a,z,bounds);renderCampaignTimeline();};
  root.querySelectorAll('[data-history-nav]').forEach(c=>c.addEventListener('click',()=>{
    const action=c.dataset.historyNav,span=end-start,mid=(start+end)/2;
    if(action==='fit')changeView(min,max);
    else if(action==='earlier'||action==='later'){const shift=span*.4*(action==='earlier'?-1:1);changeView(start+shift,end+shift);}
    else if(action==='cluster'){const ts=clusterEvents.map(e=>Date.parse(e.recorded_at));const a=Math.min(...ts),z=Math.max(...ts),margin=Math.max((z-a)*.15,450000);changeView(a-margin,z+margin);}
    else {const size=span*(action==='in'?.5:2);changeView(mid-size/2,mid+size/2);}
  }));
  viewport?.addEventListener('wheel',event=>{
    if(!event.ctrlKey)return;
    event.preventDefault();const svg=viewport.querySelector('svg'),rect=svg.getBoundingClientRect();
    const fraction=Math.max(0,Math.min(1,((event.clientX-rect.left)*width/rect.width-left)/plotWidth));
    const anchor=start+(end-start)*fraction,factor=Math.exp(Math.max(-1,Math.min(1,event.deltaY*(event.deltaMode===1?.04:event.deltaMode===2?.6:.002))));
    const span=Math.min(max-min,Math.max(900000,(end-start)*factor));
    changeView(anchor-span*fraction,anchor+span*(1-fraction));
  },{passive:false});
}

async function loadCampaignTimeline() {
  if (historyLoading) return;
  historyLoading=true; renderCampaignTimeline();
  try { historyTimeline=await api('/api/history'); }
  catch(error) { historyTimeline={battles:[],events:[],warnings:[],stats:{},import:{available:false,row_errors:[{errors:[error.message]}]}}; }
  finally { historyLoading=false; if(activeView==='chronicle'&&!currentDetail) renderCampaignTimeline(); }
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
  if (activeView === 'workshop') { await window.NCCEWorkshop.open(app,api,blocks); return; }
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
  } else if (activeView === 'chronicle') { app.innerHTML = chronicle(); loadCampaignTimeline(); }
  else if (activeView === 'archive') app.innerHTML = '<div class="eyebrow">Authored canon</div><h2>Archive</h2><p class="view-intro">The campaign’s authored records remain available in their own voice.</p><article class="card"><div class="eyebrow">C-NINE · campaign log and personnel files</div><h3><button class="card-title" data-lore="1">C-NINE Story</button></h3><p>Open the canonical story export and personnel dossiers.</p></article>';
  else if (activeView === 'system') {
    const territoryRun = await api('/api/territory-writer-runs/latest').catch(() => null);
    const plan = territoryRun?.plan || {};
    const runStatus = territoryRun?.status || 'unavailable';
    const runUsed = Boolean(territoryRun?.used);
    const runLive = ['queued','running'].includes(runStatus);
    const runCounts = territoryRun?.summary || {};
    const usage = territoryRun?.request_usage || {};
    const territorySummary = territoryRun ? runStatus === 'complete'
      ? `Finished: ${runCounts.writer?.requests_succeeded ?? usage.succeeded ?? 0} successful requests, ${runCounts.writer?.requests_failed ?? usage.failed ?? 0} failed; ${usage.input_tokens || 0} input and ${usage.output_tokens || 0} output tokens. ${JSON.stringify(runCounts.status_counts || {})}`
      : runStatus === 'error' ? `Run ended: ${territoryRun.error || 'see writer status'}. ${usage.requests || 0} requests recorded.`
      : runLive ? `Writing is running: ${usage.requests || 0} requests recorded so far.`
      : `Ready to write ${plan.entries_targeted || 0} territory entries across ${plan.territories || 0} places: origins, histories, and event accounts. One attempt per entry; fighters, gangs, battles, and authored material are excluded.`
      : 'Could not read territory writer status.';
    app.innerHTML = `<div class="eyebrow">Engine record</div><h2>System</h2>${editorialComparison(data.state)}${editorialPreview(data.state)}<section class="card writer-check"><div><strong>One-time territory writing pass</strong><p class="muted compact">${esc(territorySummary)}</p></div><button data-territory-writer="true"${!data.writer?.configured || runUsed || runLive ? ' disabled' : ''}>${runUsed ? runStatus === 'complete' ? 'Territory pass complete' : runLive ? 'Territory pass running…' : 'Territory pass already used' : 'Write all territory entries once'}</button><div class="territory-writer-status" role="status">${esc(territoryRun?.error || '')}</div></section><section class="card system-state"><div class="row"><span>Writing provider</span><span class="muted">${esc(data.writer?.status || 'unknown')}${data.writer?.model ? ' · '+esc(data.writer.model) : ''}</span></div>${data.writer?.configured ? `<div class="row"><span>Model calls this refresh</span><span class="muted">${esc(data.writer.calls_used)} / ${esc(data.writer.call_budget)}</span></div>` : ''}${Object.entries(data.state).filter(([key]) => !key.startsWith('writer_preview:') && !key.startsWith('writer_comparison:')).map(([key, value]) => `<div class="row"><span>${esc(human(key))}</span><span class="muted">${esc(value)}</span></div>`).join('')}</section>`;
  }
  if (!preserveScroll) window.scrollTo(0, 0);
}
function fighterEvidence(f) {
  return [`Role: ${f.class || 'Not recorded'} · ${f.type || 'Type not recorded'}`, `XP: ${f.xp ?? 0} · Recorded kills: ${f.kills ?? 0}`, `Status: ${fighterStatus(f)}`, ...(f.advancements ? ['Advancements: ' + f.advancements] : []), ...(f.effects ? ['Effects: ' + f.effects] : [])];
}
function memoryCard(memory) {
  const type = memory.memory_type === 'reflection' ? 'Reflection' : 'Observation';
  const status = memory.writer_status && memory.writer_status !== 'ready' ? `<p class="writer-pending" role="status">${esc(memory.writer_message || (memory.writer_status === 'stale' ? 'Earlier draft retained · not regenerated with current writing rules.' : `Narrative ${memory.writer_status} · ${memory.writer_status === 'unconfigured' ? 'configure the server-side writing provider.' : 'an explicit writing run is required.'}`))}</p>` : '';
  return `<article class="memory-card ${type.toLowerCase()}" id="memory-${esc(memory.id)}"><div class="entry-top"><span class="memory-kind">${type}</span><time>${dateStamp(memory)}</time></div>${memory.title ? `<div class="memory-trigger">${esc(memory.title)}</div>` : ''}${status}<div class="memory-voice">${writtenProse(memory.content,memory.content_runs)}</div>${evidence(memory.evidence || memory.mechanical_evidence || [], memory)}${memory.importance != null ? `<div class="memory-footer"><details class="memory-scoring"><summary>Salience ${esc(memory.importance)}</summary><p>Importance is the event’s narrative weight. It is not a game statistic.</p>${list(memory.tags).length ? `<p>Topics: ${list(memory.tags).map(esc).join(', ')}</p>` : ''}</details></div>` : ''}</article>`;
}
function mindCard(thought) {
  const memoryId = thought.memory_id || thought.id;
  const label = thought.label || thought.title || thought.name || list(thought.tags)[0] || 'Current concern';
  const status = thought.writer_status && thought.writer_status !== 'ready' ? `<p class="writer-pending" role="status">${esc(thought.writer_message || (thought.writer_status === 'stale' ? 'Earlier draft retained · not regenerated with current writing rules.' : `Narrative ${thought.writer_status} · ${thought.writer_status === 'unconfigured' ? 'configure the server-side writing provider.' : 'an explicit writing run is required.'}`))}</p>` : '';
  return `<article class="mind-card"><div class="eyebrow">${esc(human(label))}</div>${status}<div class="thought">${writtenProse(thought.content || thought.thought,thought.content_runs)}</div>${evidence(thought.evidence || [], thought, true)}${memoryId ? `<a class="memory-link" href="#memory-${esc(memoryId)}">Trace this thought to memory ↓</a>` : ''}${thought.score_details ? `<details class="mind-retrieval"><summary>Why this is on their mind</summary><dl>${Object.entries(thought.score_details).map(([key, value]) => `<div><dt>${esc(human(key))}</dt><dd>${esc(typeof value === 'number' ? Math.round(value * 100) / 100 : displayValue(value))}</dd></div>`).join('')}</dl></details>` : ''}</article>`;
}
function voiceDetails(profile) {
  if (!profile || !Object.keys(profile).length) return '';
  const traits = Array.isArray(profile.traits) ? profile.traits.map(evidenceText) : typeof profile.traits === 'object' ? Object.entries(profile.traits).map(([key, value]) => `${human(key)}: ${displayValue(value)}`) : [profile.traits].filter(Boolean);
  const context = profile.writer_context || {};
  const facets = list(context.inferred_identity);
  const explicit = Object.entries(context.identity || {}).flatMap(([key,value]) => (Array.isArray(value) ? value : [value]).filter(Boolean).map(item => ({label:human(key),value:item,source:'authored'})));
  const weights = list(context.stim_weights);
  const sourceLabel = source => source === 'mechanical_fact' ? 'Recorded' : source === 'player_authored' ? 'Player-authored' : source === 'canon_authored' ? 'Campaign canon' : 'Inferred';
  const identityMarkup = [...explicit, ...facets].map(item => `<div class="identity-facet"><div><strong>${esc(item.label)}</strong><span>${esc(sourceLabel(item.source))}</span></div><p>${esc(Array.isArray(item.value) ? item.value.join(', ') : item.value)}</p><small>${esc(item.basis || '')}</small></div>`).join('');
  const weightsMarkup = weights.map(item => `<div class="stim-weight"><div><strong>${esc(human(item.topic))}</strong><span>${esc(Number(item.weight).toFixed(2))}×</span></div><meter min="0.75" max="1.5" value="${esc(item.weight)}"></meter><small>${esc(list(item.basis).join('; ') || 'Neutral starting weight')}</small></div>`).join('');
  return `<details class="voice-profile" data-key="voice-profile"><summary>Inferred fighter profile</summary><section class="profile-subsection"><h4>Voice</h4>${profile.name ? `<p>${esc(profile.name)}</p>` : ''}${traits.length ? `<ul>${traits.map(trait => `<li>${esc(trait)}</li>`).join('')}</ul>` : ''}${evidence(profile.evidence || [], {source_label: 'Voice inferred from biography, role, characteristics, and recorded history'}, true)}</section><section class="profile-subsection"><h4>Identity from known sources</h4><p class="muted compact">Recorded role and type, authored cues, faction context, current condition and mechanics. Unknown personal facts stay unknown.</p>${identityMarkup || '<p class="muted">No supported identity facets recorded.</p>'}</section><section class="profile-subsection"><h4>Stimulus attention weights</h4><p class="muted compact">Small context weights that guide what the writer notices. They do not change game mechanics or event importance.</p><div class="stim-weight-list">${weightsMarkup || '<p class="muted">Neutral attention across topics.</p>'}</div></section></details>`;
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
  const fields = [['being','Kind of being'],['lineage','Lineage'],['culture','Culture'],['institution','Institution'],['place','Known place'],['work','Known work / craft'],['training','Training'],['condition','Relevant condition'],['life_history','Authored personal history cues'],['voice','Authored voice cues'],['gender','Gender (only if known)'],['pronouns','Pronouns (only if known)'],['writer_tags','Additional authored tags']];
  const mode = identity.narration_mode || '';
  return `<details class="identity-editor"><summary>Correct or add an explicitly known detail</summary><p class="muted compact">The profile above is inferred from the roster, authored backstory and campaign evidence. Use this optional form only to add a detail you know; unknown fields can stay blank. Gender and pronouns are never guessed.</p><form data-identity-form="${esc(fighter.id)}">${fields.map(([key,label]) => `<label>${esc(label)}<input name="${key}" value="${esc(Array.isArray(identity[key]) ? identity[key].join('; ') : identity[key] || '')}"></label>`).join('')}<label>Perspective<select name="narration_mode">${[['','From recorded identity'],['sapient','Language and personal thought'],['sensory','Sensation and learned association'],['task_log','Task and instruction log']].map(([value,label]) => `<option value="${value}"${value === mode ? ' selected' : ''}>${label}</option>`).join('')}</select></label><button type="submit">Save known detail</button><p role="status" class="identity-status"></p></form></details>`;
}
async function showFighter(id, preserveScroll = false) {
  const token = ++renderToken, f = await api('/api/fighters/' + encodeURIComponent(id));
  if (token !== renderToken) return;
  const isMara = f.name === 'Mara Kel' && /C-NINE story/i.test(String(f.backstory_source || ''));
  let maraWriterRun = null, writerDiagnostic = null;
  if (isMara) {
    [maraWriterRun, writerDiagnostic] = await Promise.all([
      api('/api/writer-runs/mara-latest').catch(() => null),
      api('/api/writer-diagnostic').catch(() => null)
    ]);
  }
  if (token !== renderToken) return;
  currentDetail = {type: 'fighter', id};
  const memories = list(f.memories).slice().sort((a, b) => Number(Boolean(a.is_baseline || a.baseline)) - Number(Boolean(b.is_baseline || b.baseline)) || (b.occurred_at || b.observed_at || '').localeCompare(a.occurred_at || a.observed_at || '') || Number(b.id) - Number(a.id));
  const mind = Array.isArray(f.mind) ? f.mind : list(f.moodlets).filter(m => m.name !== 'Dead').slice(0, 4);
  const deceased = /killed|dead/i.test(f.status || '');
  const maraWriterPending = ['queued','running'].includes(maraWriterRun?.status) || Boolean(sessionStorage.getItem('ncce-mara-writer-check') && !maraWriterRun);
  const maraWriterCanStart = (!maraWriterRun && !maraWriterPending) || maraWriterRun?.can_retry === true || maraWriterRun?.can_final_run === true || maraWriterRun?.can_medium_run === true;
  const maraWriterCheck = isMara
    ? `<section class="writer-check"><div><strong>Mara-only writer run</strong><p class="muted compact">This final sample uses medium reasoning effort and at most 5 model requests. It regenerates only Mara’s generated memories and reflection. Her player-authored biography is preserved; other fighters and campaign reports are untouched. Any entries not reached within the five calls keep their previous draft.</p></div><button data-writer-check="${esc(f.id)}"${maraWriterCanStart ? '' : ' disabled'}>${maraWriterRun?.can_medium_run ? 'Try Mara at medium effort (5 calls)' : maraWriterRun?.can_final_run ? 'Regenerate Mara’s memories' : maraWriterRun?.can_retry ? 'Run revised Mara check' : maraWriterRun?.status === 'complete' ? 'Mara check complete' : maraWriterRun?.status === 'error' ? 'Mara check ended with an error' : maraWriterPending ? 'Mara check is running' : 'Test the writer on Mara'}</button><div class="writer-check-status" role="status">${maraWriterRun ? writerRunMarkup(maraWriterRun) : ''}</div><hr><div><strong>One-call diagnostic</strong><p class="muted compact">Asks for one injury memory with a larger output allowance; displays the response and API completion details. Does not save prose to the campaign or change Mara’s record.</p></div><button data-writer-diagnostic="true"${writerDiagnostic?.used ? ' disabled' : ''}>${writerDiagnostic?.used ? 'Diagnostic used' : 'Ask the writer for one sample'}</button><div class="writer-diagnostic-status" role="status">${writerDiagnostic?.used ? writerDiagnosticMarkup(writerDiagnostic) : ''}</div></section>` : '';
  app.innerHTML = `<button class="back" data-back="fighters">← Fighters</button><div class="eyebrow">${esc(short(f.gang_name))} · fighter record</div><div class="fighter-title"><h2>${esc(f.name)}</h2><span class="status-pill">${esc(fighterStatus(f))}</span></div><p class="record-subtitle">${esc(f.type)} · ${esc(f.class)}${f.listed_in_source === 0 ? ' · Not currently listed in source' : ''}</p><div class="fighter-layout"><section class="fighter-history"><section class="biography"><h3>Backstory</h3>${narrative(f.backstory, f.backstory_source, fighterEvidence(f), {...f, source_label: 'Current mechanics and campaign context'})}${maraWriterCheck}</section><div class="sectionhead memory-heading"><div><h3>Memory stream</h3><p class="muted compact">Their recorded history · most recent first</p></div><span class="quiet-label">${memories.length} entries</span></div><div class="memory-stream">${memories.map(memoryCard).join('') || empty('No sourced memories have been generated for this fighter yet.')}</div>${fighterCampaignHistory(f)}<details class="ledger-fold" data-key="fighter-ledger"><summary>Mechanical change tracker <span>${list(f.campaign_events).length}</span></summary><div class="timeline">${list(f.campaign_events).map(campaignEvent).join('') || empty('No changes have been recorded after the baseline.')}</div></details>${list(f.events).length ? `<details class="ledger-fold" data-key="baseline-records"><summary>Baseline source records</summary>${list(f.events).map(e => `<div class="baseline-record"><strong>${esc(e.title || human(e.event_type))}</strong><p>${esc(e.detail)}</p><small>Known at baseline · date unknown · ${esc(e.source)}</small></div>`).join('')}</details>` : ''}</section><aside class="fighter-mind"><div class="mind-heading"><div class="eyebrow">Current preoccupations</div><h3>Mind</h3><p>What weighs on them now.</p></div>${deceased ? empty('This fighter has died. Their remembered history remains.') : mind.length ? mind.map(mindCard).join('') : empty('There are not enough supported memories to select a current thought.')}${voiceDetails(f.voice_profile)}${identityEditor(f)}${mechanicsPanel(f)}</aside></div>`;
  if (!preserveScroll) window.scrollTo(0, 0);
}
async function showGang(id, preserveScroll = false) {
  const token = ++renderToken, g = await api('/api/gangs/' + encodeURIComponent(id));
  if (token !== renderToken) return;
  currentDetail = {type: 'gang', id};
  const holdings = list(g.territory_list);
  app.innerHTML = `<button class="back" data-back="gangs">← Gangs</button><div class="eyebrow">${esc(g.gang_type)} · gang record</div><h2>${esc(short(g.name))}</h2><section class="region-intro">${narrative(g.backstory, g.backstory_source, g.evidence || [`Faction: ${g.gang_type}`, `${list(g.fighters).length} fighter records`, `Holdings: ${holdings.map(t => t.territory).join(', ') || 'None recorded'}`, `${list(g.battles).length} recorded battles`], g)}</section>${campaignAccount(g.campaign_account_document)}${storyStream(g.narrative_stream, 'gang')}<h3 class="section-title">Between engagements</h3>${list(g.downtime).slice(0, 1).map(downtime).join('') || empty('No downtime account is available.')}<div class="sectionhead"><h3>Fighters</h3><button class="text-button" data-gang-filter="${esc(g.gang_id)}">Find this gang’s fighters →</button></div><div class="grid">${list(g.fighters).map(fighterCard).join('') || empty('No fighter records are available for this gang.')}</div><h3 class="section-title">Holdings</h3><div class="holdings">${holdings.map(t => `<button class="holding" data-territory="${esc(t.id)}">${esc(t.territory)} <span>→</span></button>`).join('') || '<p class="muted">No current holdings are recorded.</p>'}</div><h3 class="section-title">Campaign record</h3>${list(g.battles).map(b => battle(b)).join('')}<details class="mechanics-fold" data-key="gang-mechanics"><summary>Current mechanical evidence</summary><div class="card system-state">${[['Reputation', g.reputation], ['Rating', g.rating], ['Credits', g.credits], ['Territories recorded', g.territories], ['Source updated', g.updated_at]].map(([label, value]) => `<div class="row"><span>${esc(label)}</span><span>${label === 'Source updated' ? esc(date(value,true) || 'Not recorded') : esc(value ?? 'Not recorded')}</span></div>`).join('')}</div></details>`;
  if (!preserveScroll) window.scrollTo(0, 0);
}
async function showTerritory(id, preserveScroll = false) {
  const token = ++renderToken, t = await api('/api/territories/' + encodeURIComponent(id));
  if (token !== renderToken) return;
  currentDetail = {type: 'territory', id};
  const related = data.battles.filter(b => b.territory === t.territory);
  app.innerHTML = `<button class="back" data-back="places">← Places</button><div class="eyebrow">Territory · held by ${esc(short(t.gang_name))}</div><h2>${esc(t.territory)}</h2><section class="region-intro">${narrative(t.backstory, t.backstory_source || 'inference', t.evidence || [`Current holder: ${short(t.gang_name)}`, `Card: ${t.card || 'Not recorded'}`, `Default holding: ${t.is_default ? 'Yes' : 'No'}`, `${related.length} related battle records`], t)}</section>${campaignAccount(t.campaign_account_document)}${storyStream(t.narrative_stream, 'territory')}<h3 class="section-title">Fighting over this ground</h3>${related.map(b => battle(b)).join('') || empty('No battle over this territory is recorded.')}`;
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
  if (target.dataset.writerCheck) task = runMaraWriterCheck(target);
  if (target.dataset.writerDiagnostic) task = runWriterDiagnostic(target);
  if (target.dataset.territoryWriter) task = runTerritoryWriter(target);
  if (target.dataset.clear) { filters[target.dataset.clear] = {...defaults[target.dataset.clear]}; task = render(target.dataset.clear); }
  if (target.dataset.gangFilter) { filters.fighters.gang = target.dataset.gangFilter; task = render('fighters'); }
  if (target.hasAttribute('data-retry')) task = refreshDashboard(false);
  if (task?.catch) task.catch(handleError);
});
function writerRunMarkup(run) {
  const use=run.request_usage || {}, summary=run.writer || {};
  const ledger=(use.records||[]).map(r=>`<li><strong>${esc(r.form)}</strong> · ${esc(r.subject_name||'Mara Kel')} · ${esc(r.status)} · ${Number(r.input_tokens)||0} in / ${Number(r.output_tokens)||0} out tokens<br><small>API request: ${esc(r.request_id||'unavailable')} · response: ${esc(r.response_id||'unavailable')}</small>${r.error_text?`<br><small>${esc(r.error_text)}</small>`:''}</li>`).join('');
  const live=['queued','running'].includes(run.status);
  const limit=Number(run.call_limit)||13, effort=run.reasoning_effort ? ` · ${esc(run.reasoning_effort)} reasoning` : '';
  const headline=live ? `Mara only${effort} · ${use.requests||0} of ${limit} model requests attempted so far.` : run.status==='error' ? `Writer check stopped: ${esc(run.error || 'see error status')}. ${use.requests||0} requests recorded.` : `Finished for Mara${effort}: ${summary.requests_succeeded ?? use.succeeded ?? 0} successful requests, ${summary.cache_hits || 0} cached entries, ${summary.requests_failed ?? use.failed ?? 0} failed requests; ${use.input_tokens||0} input and ${use.output_tokens||0} output tokens. No other records were processed.`;
  const emptyLedger=live ? 'Request identifiers and results are saved when this run finishes.' : 'No provider requests were needed.';
  return `<p>${headline}</p><details class="writer-ledger"><summary>Request ledger · ${use.requests||0} provider calls</summary><ol>${ledger||`<li>${emptyLedger}</li>`}</ol></details>`;
}
async function runMaraWriterCheck(button) {
  const id=button.dataset.writerCheck, status=button.parentElement.querySelector('.writer-check-status');
  button.disabled=true; status.textContent='Starting the authorized Mara-only writer run…';
  try {
    const started=await api(`/api/fighters/${encodeURIComponent(id)}/write-check`,{method:'POST'});
    sessionStorage.setItem('ncce-mara-writer-check',started.run_id);
    let run;
    while (true) {
      await new Promise(resolve=>setTimeout(resolve,2000));
      run=await api(`/api/writer-runs/${encodeURIComponent(started.run_id)}`);
      status.innerHTML=writerRunMarkup(run);
      if (run.status==='complete' || run.status==='error') break;
    }
    await showFighter(id,true);
  } catch (error) { status.textContent=error.message; button.disabled=false; }
}
function writerDiagnosticMarkup(result) {
  const details=result.response || {};
  const metadata=`${esc(details.status || 'no response status')} · ${Number(details.input_tokens)||0} input / ${Number(details.output_tokens)||0} output tokens · ${Number(details.reasoning_tokens)||0} reasoning tokens · incomplete: ${esc(details.incomplete_reason || 'none')} · output types: ${esc((details.output_types || []).join(', ') || 'none')} · request ${esc(details.request_id || 'unavailable')} · response ${esc(details.response_id || 'unavailable')}`;
  return `<p><strong>${result.status === 'succeeded' ? 'Writer sample' : 'Diagnostic result'}</strong></p>${result.text ? `<blockquote>${esc(result.text)}</blockquote>` : `<p>${esc(result.error || 'No prose was returned.')}</p>`}<small>${metadata}</small>`;
}
async function runWriterDiagnostic(button) {
  const status=button.parentElement.querySelector('.writer-diagnostic-status');
  button.disabled=true; status.textContent='Sending one isolated writer prompt…';
  try { const result=await api('/api/writer-diagnostic',{method:'POST'}); status.innerHTML=writerDiagnosticMarkup(result); button.textContent='Diagnostic used'; }
  catch (error) { status.textContent=error.message; if (!/already been used/i.test(error.message)) button.disabled=false; }
}
async function runTerritoryWriter(button) {
  const status = button.parentElement.querySelector('.territory-writer-status');
  button.disabled = true; status.textContent = 'Starting the one-time territory-only writer pass…';
  try {
    await api('/api/territory-writer-runs', {method:'POST'});
    while (true) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      const run = await api('/api/territory-writer-runs/latest');
      const use = run.request_usage || {}, result = run.summary || {};
      if (run.status === 'complete') {
        const counts = result.status_counts || {};
        status.textContent = `Complete · ${result.writer?.requests_succeeded ?? use.succeeded ?? 0} successful, ${result.writer?.requests_failed ?? use.failed ?? 0} failed · ${use.input_tokens || 0} input / ${use.output_tokens || 0} output tokens · ${Object.entries(counts).map(([key,value])=>`${key}: ${value}`).join(', ')}`;
        break;
      }
      if (run.status === 'error') { status.textContent = `Stopped · ${run.error || 'writer run failed'} · ${use.requests || 0} provider requests.`; break; }
      status.textContent = `Writing territory entries · ${use.requests || 0} provider requests so far.`;
    }
    await refreshDashboard();
    await render('system', true);
  } catch (error) { status.textContent = error.message; button.disabled = false; }
}
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
