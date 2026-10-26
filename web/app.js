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
    : document?.writer_message || (document?.writer_status === 'unconfigured' ? 'Narrative pending · configure the server-side writing provider.' : `Narrative ${document?.writer_status} · retry on the next refresh.`);
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
  const header = document.document_type ? `<header class="record-header"><div class="eyebrow">${esc(human(document.document_type))}</div>${document.date_display && !document.suppress_date ? dateStamp(document) : ''}<dl class="metadata-group">${list(document.metadata).map(field => `<div><dt>${inline(field.label)}</dt><dd>${inline(field.value)}</dd></div>`).join('')}</dl></header>` : '';
  const status = document?.writer_status && document.writer_status !== 'ready' ? `<p class="writer-pending" role="status">${esc(statusMessage)}</p>` : '';
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
  const authoredBody = isAuthored ? (/C-NINE story/i.test(String(source || '')) ? authoredDossier(value) : prose(value)) : blocks(document, value);
  return `<div class="narrative"><div class="eyebrow">${isAuthored ? 'Authored campaign record' : 'Generated inference'}</div>${authoredBody}</div>${isAuthored ? `<div class="authored-source">${esc(source || 'Authored campaign canon')}</div>` : evidence(basis, {...meta, ...document})}`;
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
  return `<div class="sectionhead"><div><div class="eyebrow">Dominion Krakamunda</div><h2>Campaign Chronicle</h2></div><span class="quiet-label">Lives · claims · consequences</span></div>${region ? `<section class="region-intro">${narrative(region.backstory, region.backstory_source || 'inference', region.evidence || [`${data.gangs.length} active gang records`, `${data.territories.length} territory records`, `${data.battles.length} recorded battles`], region)}</section>` : ''}<section class="campaign-timeline"><div class="timeline-heading"><div><div class="eyebrow">Recorded campaign history</div><h3>Battle and downtime timeline</h3><p>Session dates provide candidate windows. They show record timing, not verified moments of play.</p></div><span class="timeline-refresh-state" id="historyImportLabel">Loading archive…</span></div><div id="campaignTimeline" class="loading-state" role="status">Reading the campaign history archive…</div></section><div class="split chronicle-layout"><section><h3 class="section-title">Recent battle accounts</h3>${data.battles.slice(0, 3).map((record, index) => battle(record, index === 0)).join('') || empty('No battle records have been imported yet.')}<details class="ledger-fold" data-key="campaign-ledger"><summary>Latest mechanical campaign records <span>${data.campaignEvents.length}</span></summary><div class="timeline">${data.campaignEvents.map(campaignEvent).join('') || empty('No changes have been recorded since the baseline.')}</div></details></section><aside><h3 class="section-title">Between games</h3>${latestDowntime.map(downtime).join('') || empty('Downtime accounts will appear as the campaign develops.')}</aside></div>`;
}

function historyDate(value, time = true) {
  if (!value) return 'Time not recorded';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return String(value);
  return new Intl.DateTimeFormat('en-GB', {timeZone:'Europe/Warsaw', year:'numeric', month:'short', day:'2-digit', ...(time ? {hour:'2-digit',minute:'2-digit'} : {})}).format(parsed);
}
const historyPhaseLabel = phase => ({during_battle:'Inside candidate battle window',downtime:'Between battles',current_downtime:'After latest battle',pre_first_battle:'Before first timed battle',pre_battle:'Before first battle',inter_session_gap:'Between sessions · battle unresolved',unassigned:'Unassigned',unavailable:'Time unavailable',ambiguous_overlap:'Overlapping battle windows',open_battle_window:'Open / incomplete battle session'}[phase] || human(phase));
function timelineFilterOptions() {
  const gangs = new Map((data?.gangs || []).map(gang => [String(gang.gang_id), short(gang.name)]));
  for (const event of list(historyTimeline?.events)) if (event.gang_id && !gangs.has(String(event.gang_id))) gangs.set(String(event.gang_id), event.gang_name || 'Gang ' + String(event.gang_id).slice(0,8));
  for (const battle of list(historyTimeline?.battles)) for (const gang of list(battle.gangs)) if (gang.gang_id && !gangs.has(String(gang.gang_id))) gangs.set(String(gang.gang_id), gang.name || 'Gang ' + String(gang.gang_id).slice(0,8));
  return [...gangs.entries()].sort((a,b)=>a[1].localeCompare(b[1]));
}
function timelineRows() {
  const query = historyFilters.q.trim().toLocaleLowerCase();
  const localDay = value => value && !Number.isNaN(new Date(value).valueOf()) ? new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Warsaw',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value)) : '';
  return list(historyTimeline?.events).filter(event =>
    (!historyFilters.gang || String(event.gang_id || '') === historyFilters.gang) &&
    (!historyFilters.fighter || String(event.fighter_id || '') === historyFilters.fighter) &&
    (!historyFilters.place || String(event.territory_id || '') === historyFilters.place) &&
    (!historyFilters.action || String(event.action_type || '') === historyFilters.action) &&
    (!historyFilters.phase || event.phase === historyFilters.phase) &&
    (!historyFilters.battle || [event.battle_id,event.preceding_battle_id,event.next_battle_id].filter(Boolean).map(String).includes(historyFilters.battle)) &&
    (!historyFilters.from || (localDay(event.recorded_at) && localDay(event.recorded_at) >= historyFilters.from)) &&
    (!historyFilters.to || (localDay(event.recorded_at) && localDay(event.recorded_at) <= historyFilters.to)) &&
    (!query || [event.entity_label,event.gang_name,event.action_type,event.description,event.phase,event.event_id].some(value => String(value || '').toLocaleLowerCase().includes(query)))
  );
}
function timelineDetail(event, selectedBattle) {
  if (selectedBattle) {
    const names = selectedBattle.attacker && selectedBattle.defender ? `${selectedBattle.attacker} vs ${selectedBattle.defender}` : list(selectedBattle.gangs).map(gang => gang.name).join(' vs ') || 'Participants not resolved';
    const sessions = list(selectedBattle.sessions).map(session => `<li>${esc(session.status || 'Status not recorded')} · ${esc(historyDate(session.start_at))} – ${esc(historyDate(session.end_at))}${session.warning ? ` · ${esc(session.warning)}` : ''} · session ${esc(session.session_id)}</li>`).join('');
    const related = timelineRows().filter(event => [event.battle_id,event.preceding_battle_id,event.next_battle_id].filter(Boolean).map(String).includes(String(selectedBattle.battle_id))).sort((a,b)=>(a.recorded_at||'').localeCompare(b.recorded_at||''));
    const groups = new Map();
    for (const event of related) {
      const gang = event.gang_name || 'Gang not identified', fighter = event.fighter_name || event.entity_label || 'Gang-level activity';
      if (!groups.has(gang)) groups.set(gang,new Map());
      const fighters = groups.get(gang); if (!fighters.has(fighter)) fighters.set(fighter,[]); fighters.get(fighter).push(event);
    }
    const activity = related.length ? `<section class="timeline-battle-activity"><h4>Activity and nearby downtime</h4>${[...groups].map(([gang,fighters])=>`<div class="timeline-activity-gang"><strong>${esc(gang)}</strong>${[...fighters].map(([fighter,items])=>`<div class="timeline-activity-fighter"><span>${esc(fighter)}</span><ul>${items.map(event=>`<li><button type="button" data-history-event="${esc(event.event_id)}"><time>${esc(historyDate(event.recorded_at))}</time> · ${esc(historyPhaseLabel(event.phase))} · ${esc(event.description||human(event.action_type)||'Change recorded')}</button></li>`).join('')}</ul></div>`).join('')}</div>`).join('')}</section>` : `<p>No activity logs are linked to this battle window or its adjacent downtime.</p>`;
    return `<article class="timeline-detail"><div class="eyebrow">Documented campaign battle · ${esc(selectedBattle.timing_basis || 'timing unavailable')}</div><h4>${esc(selectedBattle.scenario || 'Battle')} · ${esc(names)}</h4><dl><div><dt>Candidate window</dt><dd>${esc(historyDate(selectedBattle.start_at))} – ${esc(historyDate(selectedBattle.end_at))}</dd></div><div><dt>Window source</dt><dd>Session created/updated timestamps are proxies, not confirmed gameplay times.</dd></div><div><dt>Result</dt><dd>${esc(selectedBattle.winner || 'No result recorded')}</dd></div><div><dt>Campaign record</dt><dd>${esc(selectedBattle.status || 'Status not recorded')} · ${esc(selectedBattle.battle_id)}</dd></div>${selectedBattle.territory ? `<div><dt>Territory</dt><dd>${esc(selectedBattle.territory)}</dd></div>` : ''}${selectedBattle.cycle ? `<div><dt>Cycle</dt><dd>${esc(selectedBattle.cycle)}</dd></div>` : ''}</dl>${sessions ? `<div class="timeline-detail-sessions"><strong>Linked sessions</strong><ul>${sessions}</ul></div>` : `<p>Timing unavailable: this documented battle has no linked timed session.</p>`}${activity}<details class="timeline-raw"><summary>Original battle record</summary><pre>${esc(JSON.stringify(selectedBattle.raw_record || {}, null, 2))}</pre></details></article>`;
  }
  if (!event) return `<div class="timeline-detail muted">Select a battle or activity marker to inspect its record.</div>`;
  const battleRecord = list(historyTimeline?.battles).find(item => item.battle_id === event.battle_id || item.battle_id === event.preceding_battle_id || item.battle_id === event.next_battle_id);
  const battleLabel = battleRecord ? `${battleRecord.scenario || 'Battle'} · ${battleRecord.gangs.map(gang => gang.name).join(' vs ') || 'participants not resolved'}` : '';
  const participation = event.participation || {};
  const participationLabel = participation.status === 'inferred' ? `Inferred · ${participation.basis} (${participation.confidence})` : participation.status === 'not_supported' ? 'Not inferred from this XP change' : 'Unknown · no supported participation evidence';
  return `<article class="timeline-detail"><div class="eyebrow">${esc(historyPhaseLabel(event.phase))} · ${esc(event.confidence || '')}</div><h4>${esc(event.entity_label || event.gang_name || 'Campaign event')}</h4><p class="timeline-detail-description">${esc(event.description || human(event.action_type) || 'No description recorded.')}</p><dl><div><dt>Recorded</dt><dd>${esc(historyDate(event.recorded_at))}${event.recorded_at_raw && event.recorded_at_raw !== event.recorded_at ? ` <small>(${esc(event.recorded_at_raw)})</small>` : ''}</dd></div><div><dt>Gang</dt><dd>${esc(event.gang_name || event.gang_id || 'Not identified')}</dd></div>${event.fighter_id ? `<div><dt>Fighter ID</dt><dd>${esc(event.fighter_id)}</dd></div>` : ''}${event.action_type ? `<div><dt>Event type</dt><dd>${esc(event.action_type)}</dd></div>` : ''}${event.fighter_id ? `<div><dt>Battle participation</dt><dd>${esc(participationLabel)}<small> XP evidence is inference; timestamps and attendance are not proof.</small></dd></div>` : ''}${battleLabel ? `<div><dt>Battle</dt><dd>${esc(battleLabel)}</dd></div>` : ''}${event.preceding_battle_id ? `<div><dt>After</dt><dd>Battle ${esc(event.preceding_battle_id.slice(0,8))}</dd></div>` : ''}${event.next_battle_id ? `<div><dt>Before</dt><dd>Battle ${esc(event.next_battle_id.slice(0,8))}</dd></div>` : ''}<div><dt>Source</dt><dd>${esc(event.source_table)} · row ${esc(event.source_row ?? 'unknown')} · ${esc(event.event_id)}</dd></div></dl><details class="timeline-raw"><summary>Original source record</summary><pre>${esc(JSON.stringify(event.raw_record || {}, null, 2))}</pre></details></article>`;
}
function fighterCampaignHistory(fighter) {
  const history=fighter.campaign_history||{}, events=list(history.events).slice().sort((a,b)=>(b.recorded_at||'').localeCompare(a.recorded_at||''));
  return `<section class="fighter-campaign-history"><div class="sectionhead"><div><h3 class="section-title">Battle and downtime record</h3><p class="muted compact">Changes grouped by recorded session time. This does not establish individual attendance.</p></div><span class="quiet-label">${events.length} archive entries</span></div>${events.length?`<div class="fighter-history-events">${events.map(event=>`<article class="fighter-history-event"><div class="eyebrow">${esc(historyPhaseLabel(event.phase))} · ${esc(event.confidence||'')}</div><time>${esc(historyDate(event.recorded_at))}</time><p>${esc(event.description||human(event.action_type)||'Change recorded')}</p><details><summary>Source record · ${esc(event.source_table)} · ${esc(event.event_id)}</summary><pre>${esc(JSON.stringify(event.raw_record||{},null,2))}</pre></details></article>`).join('')}</div>`:empty(history.import?.available?'No activity rows currently resolve to this fighter.':'Fighter archive history will appear after the next Sheet refresh.')}</section>`;
}
function renderCampaignTimeline() {
  const root = document.querySelector('#campaignTimeline');
  const label = document.querySelector('#historyImportLabel');
  if (!root) return;
  if (!historyTimeline) { root.innerHTML = `<div class="loading-state" role="status">${historyLoading ? 'Reading the campaign history archive…' : 'Campaign history is not available yet.'}</div>`; return; }
  const {battles = [], events = [], warnings = [], import: importStatus = {}, stats = {}} = historyTimeline;
  if (label) label.textContent = importStatus.last_imported_at ? `Archive checked ${historyDate(importStatus.last_imported_at)}` : 'Waiting for first archive import';
  const rows = timelineRows();
  const gangOptions = timelineFilterOptions().map(([id,name]) => `<option value="${esc(id)}"${historyFilters.gang === id ? ' selected' : ''}>${esc(name)}</option>`).join('');
  const fighters = [...new Map(list(historyTimeline?.events).filter(event=>event.fighter_id).map(event=>[String(event.fighter_id),event.fighter_name||event.entity_label||('Fighter '+String(event.fighter_id).slice(0,8))])).entries()].sort((a,b)=>a[1].localeCompare(b[1]));
  const places = [...new Map([...list(historyTimeline?.events).filter(event=>event.territory_id).map(event=>[String(event.territory_id),event.place_name||('Place '+String(event.territory_id).slice(0,8))]),...list(historyTimeline?.battles).filter(battle=>battle.territory_id).map(battle=>[String(battle.territory_id),battle.territory||('Place '+String(battle.territory_id).slice(0,8))])]).entries()].sort((a,b)=>a[1].localeCompare(b[1]));
  const actions = [...new Set(list(historyTimeline?.events).map(event=>event.action_type).filter(Boolean))].sort();
  const battleOptions = list(historyTimeline?.battles).map(battle => [battle.battle_id, `${battle.scenario || 'Battle'} · ${list(battle.gangs).map(gang=>gang.name).join(' vs ') || battle.battle_id.slice(0,8)}`]).map(([id,name])=>`<option value="${esc(id)}"${historyFilters.battle===id?' selected':''}>${esc(name)}</option>`).join('');
  const filtersMarkup = `<form class="timeline-filters" data-history-filter-form><label>Find an event<input type="search" data-history-filter="q" value="${esc(historyFilters.q)}" placeholder="Fighter, change, source…"></label><label>Gang<select data-history-filter="gang"><option value="">All gangs</option>${gangOptions}</select></label><label>Fighter<select data-history-filter="fighter"><option value="">All fighters</option>${fighters.map(([id,name])=>`<option value="${esc(id)}"${historyFilters.fighter===id?' selected':''}>${esc(name)}</option>`).join('')}</select></label><label>Battle<select data-history-filter="battle"><option value="">All battles</option>${battleOptions}</select></label><label>Place<select data-history-filter="place"><option value="">All places</option>${places.map(([id,name])=>`<option value="${esc(id)}"${historyFilters.place===id?' selected':''}>${esc(name)}</option>`).join('')}</select></label><label>Event type<select data-history-filter="action"><option value="">All event types</option>${actions.map(action=>`<option value="${esc(action)}"${historyFilters.action===action?' selected':''}>${esc(human(action))}</option>`).join('')}</select></label><label>Period<select data-history-filter="phase"><option value="">All periods</option>${['during_battle','downtime','current_downtime','pre_first_battle','inter_session_gap','unassigned','unavailable','ambiguous_overlap','open_battle_window'].map(phase => `<option value="${phase}"${historyFilters.phase === phase ? ' selected' : ''}>${esc(historyPhaseLabel(phase))}</option>`).join('')}</select></label><label>From<input type="date" data-history-filter="from" value="${esc(historyFilters.from)}"></label><label>To<input type="date" data-history-filter="to" value="${esc(historyFilters.to)}"></label></form>`;
  if (!importStatus.available && !battles.length && !events.length) {
    const missing = list(importStatus.missing_tabs).length ? list(importStatus.missing_tabs).join(', ') : 'No archive rows have been imported yet.';
    root.innerHTML = `${filtersMarkup}<div class="empty-state">The archive tabs have not been imported. Refresh from the Sheet to read Munda Manager history. Missing tabs: ${esc(missing)}</div>`;
    return;
  }
  const dayOf=value=>value?new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Warsaw',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value)):'';
  const inScopeBattles = battles.filter(item => (!historyFilters.battle || String(item.battle_id)===historyFilters.battle) && (!historyFilters.gang || item.gang_ids.map(String).includes(historyFilters.gang)) && (!historyFilters.place || String(item.territory_id||'')===historyFilters.place) && (!historyFilters.from || dayOf(item.end_at||item.start_at||item.documented_at)>=historyFilters.from) && (!historyFilters.to || dayOf(item.start_at||item.end_at||item.documented_at)<=historyFilters.to));
  const timed = inScopeBattles.filter(item => item.start_at && item.end_at);
  const knownDates = [...rows.map(event => event.recorded_at), ...timed.flatMap(item => [item.start_at,item.end_at]), ...inScopeBattles.map(item => item.documented_at)].filter(value => value && !Number.isNaN(new Date(value).valueOf())).map(value => new Date(value).valueOf());
  let start = knownDates.length ? Math.min(...knownDates) : Date.now()-86400000;
  let end = knownDates.length ? Math.max(...knownDates) : Date.now();
  if (end-start < 86400000) { start -= 43200000; end += 43200000; }
  const left = 205, right = 24, width = Math.max(880, Math.min(1800, app.clientWidth - 40));
  const plotWidth = width-left-right, x = time => left + ((time-start)/(end-start))*plotWidth;
  const laneIds = historyFilters.gang ? [historyFilters.gang] : [...new Set([...inScopeBattles.flatMap(item => item.gang_ids.map(String)), ...rows.map(item => String(item.gang_id || '')).filter(Boolean)])];
  const laneNames = new Map(timelineFilterOptions());
  if (!laneIds.length) laneIds.push('');
  const laneY = new Map(laneIds.map((id,index) => [id,64+index*72]));
  const height = 74+laneIds.length*72;
  const ticks = Array.from({length:6},(_,index)=>start+(end-start)*index/5);
  const grid = ticks.map((time,index)=>`<g class="timeline-axis-tick"><line x1="${x(time)}" y1="36" x2="${x(time)}" y2="${height-12}"/><text x="${x(time)}" y="23" text-anchor="${index===0?'start':index===5?'end':'middle'}">${esc(historyDate(time,false))}</text></g>`).join('');
  const lanes = laneIds.map((gangId,index)=>{
    const y=laneY.get(gangId), name=laneNames.get(gangId) || (gangId ? 'Gang '+gangId.slice(0,8) : 'Campaign records');
    const gangBattles=timed.filter(item=>item.gang_ids.map(String).includes(gangId));
    const downtime=gangBattles.slice().sort((a,b)=>a.start_at.localeCompare(b.start_at)).slice(1).map((item,j)=>{
      const previous=gangBattles.slice().sort((a,b)=>a.start_at.localeCompare(b.start_at))[j];
      if (!previous?.end_at || item.start_at<=previous.end_at) return '';
      return `<rect class="timeline-downtime" x="${x(new Date(previous.end_at).valueOf())}" y="${y+8}" width="${Math.max(1,x(new Date(item.start_at).valueOf())-x(new Date(previous.end_at).valueOf()))}" height="7" rx="3"><title>Downtime between recorded battle windows</title></rect>`;
    }).join('');
    const bars=inScopeBattles.filter(item=>item.gang_ids.map(String).includes(gangId)).flatMap(item=>list(item.sessions).filter(session=>session.start_at&&session.end_at).map(session=>{
      const x1=x(new Date(session.start_at).valueOf()), x2=x(new Date(session.end_at).valueOf());
      const names=item.gangs.map(gang=>gang.name).join(' vs ');
      const title=`${item.scenario||'Battle'} · ${names}\nCandidate session window: ${historyDate(session.start_at)} – ${historyDate(session.end_at)}\nSession ${session.session_id}`;
      return `<g class="timeline-battle-span${String(selectedHistoryBattle)===String(item.battle_id)?' selected':''}" data-history-battle="${esc(item.battle_id)}" tabindex="0" role="button" aria-label="${esc(title)}"><rect x="${x1}" y="${y-11}" width="${Math.max(4,x2-x1)}" height="21" rx="4"><title>${esc(title)}</title></rect>${x2-x1>90?`<text x="${x1+7}" y="${y+4}">${esc(item.scenario||'Battle')}</text>`:''}</g>`;
    })).join('');
    const noTime=battles.filter(item=>(!item.start_at||!item.end_at)&&(item.documented_at||item.start_at)&&item.gang_ids.map(String).includes(gangId)&&(!historyFilters.battle||String(item.battle_id)===historyFilters.battle)&&(!historyFilters.place||String(item.territory_id||'')===historyFilters.place)&&(!historyFilters.from||dayOf(item.documented_at||item.start_at)>=historyFilters.from)&&(!historyFilters.to||dayOf(item.documented_at||item.start_at)<=historyFilters.to)).map(item=>`<path class="timeline-unverified" data-history-battle="${esc(item.battle_id)}" tabindex="0" role="button" aria-label="${esc(`${item.scenario||'Battle'} · timing unavailable; this is record creation time`)}" d="M ${x(new Date(item.documented_at||item.start_at).valueOf())} ${y-6} l 6 6 -6 6 -6 -6 z"><title>${esc(`${item.scenario||'Battle'} · timing unavailable; this is record creation time`)}</title></path>`).join('');
    const laneEvents=rows.filter(event=>String(event.gang_id||'')===gangId && event.recorded_at);
    const dots=laneEvents.map((event,i)=>{
      const t=new Date(event.recorded_at).valueOf(); if (t<start || t>end) return '';
      const nearby=laneEvents.slice(0,i).filter(other=>Math.abs(new Date(other.recorded_at).valueOf()-t)<3600000).length;
      const jitter=[0,-12,12,-22,22][nearby%5], phaseClass=/battle/.test(event.phase)?'battle':event.phase==='downtime'||event.phase==='current_downtime'?'downtime':'uncertain';
      const title=`${event.entity_label||name} · ${event.action_type||'Campaign change'}\n${historyPhaseLabel(event.phase)} · ${historyDate(event.recorded_at)}\n${event.description||''}`;
      return `<circle class="timeline-event-point ${phaseClass}" cx="${x(t)}" cy="${y+jitter}" r="5" data-history-event="${esc(event.event_id)}" tabindex="0" role="button" aria-label="${esc(title)}"><title>${esc(title)}</title></circle>`;
    }).join('');
    return `<g class="timeline-lane"><text class="timeline-lane-label" x="${left-14}" y="${y+4}" text-anchor="end">${esc(short(name))}</text><line class="timeline-lane-line" x1="${left}" y1="${y}" x2="${width-right}" y2="${y}"/>${downtime}${bars}${noTime}${dots}</g>`;
  }).join('');
  const visibleIds=new Set(rows.map(event=>String(event.event_id)));
  if (selectedHistoryEvent && !visibleIds.has(String(selectedHistoryEvent))) selectedHistoryEvent=null;
  const visibleBattleIds = new Set(battles.filter(item=>(!historyFilters.battle||String(item.battle_id)===historyFilters.battle)&&(!historyFilters.gang||item.gang_ids.map(String).includes(historyFilters.gang))&&(!historyFilters.place||String(item.territory_id||'')===historyFilters.place)).map(item=>String(item.battle_id)));
  if (selectedHistoryBattle && !visibleBattleIds.has(String(selectedHistoryBattle))) selectedHistoryBattle=null;
  const selected=rows.find(event=>String(event.event_id)===String(selectedHistoryEvent));
  const selectedBattle=battles.find(item=>String(item.battle_id)===String(selectedHistoryBattle));
  const eventRows=rows.slice().reverse().map(event=>`<button type="button" class="timeline-event-row${String(selectedHistoryEvent)===String(event.event_id)?' selected':''}" data-history-event="${esc(event.event_id)}"><span class="timeline-event-time">${esc(historyDate(event.recorded_at))}</span><span class="timeline-event-actor">${esc(event.entity_label||event.gang_name||'Campaign')}</span><span class="timeline-event-text">${esc(event.description||human(event.action_type)||'Change recorded')}</span><span class="timeline-event-phase">${esc(historyPhaseLabel(event.phase))}</span></button>`).join('');
  const battleRows=battles.filter(item=>visibleBattleIds.has(String(item.battle_id))).map(item=>`<button type="button" class="timeline-event-row timeline-battle-row${String(selectedHistoryBattle)===String(item.battle_id)?' selected':''}" data-history-battle="${esc(item.battle_id)}"><span class="timeline-event-time">${esc(item.start_at?historyDate(item.start_at):historyDate(item.documented_at))}</span><span class="timeline-event-actor">${esc(item.scenario||'Battle')}</span><span class="timeline-event-text">${esc(item.gangs.map(gang=>gang.name).join(' vs ')||'Participants unresolved')} · ${esc(item.winner||'Outcome unrecorded')}</span><span class="timeline-event-phase">${esc(item.timing_basis==='session_timestamp_proxy'?'Candidate window':'Timing unverified')}</span></button>`).join('');
  const warningText=warnings.length?`${warnings.length} archive/timing item${warnings.length===1?'':'s'} need attention`:'No unresolved archive links reported';
  const openFolds=[...root.querySelectorAll('details[data-history-fold]')].filter(fold=>fold.open).map(fold=>fold.dataset.historyFold);
  root.innerHTML=`${filtersMarkup}<div class="timeline-summary"><span>${esc(stats.battle_records||0)} battles · ${esc(stats.activity_records||0)} activity records</span><span>${esc(stats.timed_battles||0)} candidate windows · ${esc(warningText)}</span></div><div class="campaign-timeline-scroll" role="region" aria-label="Campaign battle and downtime timeline" tabindex="0"><svg class="campaign-timeline-svg" viewBox="0 0 ${width} ${height}" role="group" aria-label="Chronological campaign activity grouped by gang">${grid}${lanes}</svg></div><div class="timeline-legend"><span><i class="legend-battle"></i> Candidate battle window</span><span><i class="legend-change"></i> Recorded change</span><span><i class="legend-downtime"></i> Gap between candidate windows</span><span><i class="legend-unverified"></i> Battle timing unavailable</span></div><div id="historyEventDetail">${timelineDetail(selected,selectedBattle)}</div><details data-history-fold="battles" class="timeline-event-list"><summary>Battle registry (${visibleBattleIds.size})</summary><div>${battleRows||empty('No battles match these filters.')}</div></details><details data-history-fold="events" class="timeline-event-list"><summary>Browse recorded changes (${rows.length})</summary><div>${eventRows||empty('No events match these filters.')}</div></details>${warnings.length?`<details data-history-fold="warnings" class="timeline-warning-list"><summary>Timing and source notes</summary>${warnings.map(w=>`<p>${esc(human(w.kind))} · ${esc(w.message||w.record_id||w.source_row||'Review source record')}${w.battle_id?` · Battle ${esc(String(w.battle_id).slice(0,8))}`:''}</p>`).join('')}</details>`:''}`;
  for (const fold of openFolds) { const replacement=root.querySelector(`[data-history-fold="${fold}"]`); if (replacement) replacement.open=true; }
  root.querySelectorAll('[data-history-filter]').forEach(control=>control.addEventListener(control.matches('input[type="search"]')?'input':'change',event=>{
    historyFilters[event.target.dataset.historyFilter]=event.target.value;
    const search=event.target.matches('input[type="search"]'), start=search?event.target.selectionStart:null, end=search?event.target.selectionEnd:null;
    renderCampaignTimeline();
    if (search) { const replacement=root.querySelector('[data-history-filter="q"]'); replacement?.focus(); if (replacement && start!==null) replacement.setSelectionRange(start,end); }
  }));
  root.querySelector('[data-history-filter-form]')?.addEventListener('submit',event=>event.preventDefault());
  root.querySelectorAll('[data-history-event]').forEach(control=>control.addEventListener('click',()=>{selectedHistoryEvent=control.dataset.historyEvent;selectedHistoryBattle=null;renderCampaignTimeline();}));
  root.querySelectorAll('[data-history-battle]').forEach(control=>control.addEventListener('click',()=>{selectedHistoryBattle=control.dataset.historyBattle;selectedHistoryEvent=null;renderCampaignTimeline();}));
  root.querySelectorAll('[data-history-event][role="button"], [data-history-battle][role="button"]').forEach(control=>control.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();if(control.dataset.historyEvent){selectedHistoryEvent=control.dataset.historyEvent;selectedHistoryBattle=null;}else{selectedHistoryBattle=control.dataset.historyBattle;selectedHistoryEvent=null;}renderCampaignTimeline();}}));
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
    app.innerHTML = `<div class="eyebrow">Engine record</div><h2>System</h2><section class="card writer-check"><div><strong>One-time territory writing pass</strong><p class="muted compact">${esc(territorySummary)}</p></div><button data-territory-writer="true"${!data.writer?.configured || runUsed || runLive ? ' disabled' : ''}>${runUsed ? runStatus === 'complete' ? 'Territory pass complete' : runLive ? 'Territory pass running…' : 'Territory pass already used' : 'Write all territory entries once'}</button><div class="territory-writer-status" role="status">${esc(territoryRun?.error || '')}</div></section><section class="card system-state"><div class="row"><span>Writing provider</span><span class="muted">${esc(data.writer?.status || 'unknown')}${data.writer?.model ? ' · '+esc(data.writer.model) : ''}</span></div>${data.writer?.configured ? `<div class="row"><span>Model calls this refresh</span><span class="muted">${esc(data.writer.calls_used)} / ${esc(data.writer.call_budget)}</span></div>` : ''}${Object.entries(data.state).map(([key, value]) => `<div class="row"><span>${esc(human(key))}</span><span class="muted">${esc(value)}</span></div>`).join('')}</section>`;
  }
  if (!preserveScroll) window.scrollTo(0, 0);
}
function fighterEvidence(f) {
  return [`Role: ${f.class || 'Not recorded'} · ${f.type || 'Type not recorded'}`, `XP: ${f.xp ?? 0} · Recorded kills: ${f.kills ?? 0}`, `Status: ${fighterStatus(f)}`, ...(f.advancements ? ['Advancements: ' + f.advancements] : []), ...(f.effects ? ['Effects: ' + f.effects] : [])];
}
function memoryCard(memory) {
  const type = memory.memory_type === 'reflection' ? 'Reflection' : 'Observation';
  const status = memory.writer_status && memory.writer_status !== 'ready' ? `<p class="writer-pending" role="status">${esc(memory.writer_message || (memory.writer_status === 'stale' ? 'Earlier draft retained · not regenerated with current writing rules.' : `Narrative ${memory.writer_status} · ${memory.writer_status === 'unconfigured' ? 'configure the server-side writing provider.' : 'retry on the next refresh.'}`))}</p>` : '';
  return `<article class="memory-card ${type.toLowerCase()}" id="memory-${esc(memory.id)}"><div class="entry-top"><span class="memory-kind">${type}</span><time>${dateStamp(memory)}</time></div>${memory.title ? `<div class="memory-trigger">${esc(memory.title)}</div>` : ''}${status}<div class="memory-voice">${writtenProse(memory.content,memory.content_runs)}</div>${evidence(memory.evidence || memory.mechanical_evidence || [], memory)}${memory.importance != null ? `<div class="memory-footer"><details class="memory-scoring"><summary>Salience ${esc(memory.importance)}</summary><p>Importance is the event’s narrative weight. It is not a game statistic.</p>${list(memory.tags).length ? `<p>Topics: ${list(memory.tags).map(esc).join(', ')}</p>` : ''}</details></div>` : ''}</article>`;
}
function mindCard(thought) {
  const memoryId = thought.memory_id || thought.id;
  const label = thought.label || thought.title || thought.name || list(thought.tags)[0] || 'Current concern';
  const status = thought.writer_status && thought.writer_status !== 'ready' ? `<p class="writer-pending" role="status">${esc(thought.writer_message || (thought.writer_status === 'stale' ? 'Earlier draft retained · not regenerated with current writing rules.' : `Narrative ${thought.writer_status} · ${thought.writer_status === 'unconfigured' ? 'configure the server-side writing provider.' : 'retry on the next refresh.'}`))}</p>` : '';
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
