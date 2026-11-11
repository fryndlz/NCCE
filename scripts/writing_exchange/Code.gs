/** NCCE private Sheet relay. No LLM calls; no campaign-source writes. */
const EXCHANGE_ID = '1xokVbI3kya5koTqx9IOyUly2lP22batgLlo4oBlYBas';
const BASE_URL = 'https://ncce-private-preview.onrender.com';
const QUEUE_HEADERS = 'request_id,status,form,entity_type,entity_key,entry_key,title,context_id,source_revision,event_at_utc,imperial_date,writer_text_md,writer_note,completed_at_utc,imported_at_utc,import_receipt'.split(',');
const CONTEXT_HEADERS = 'context_id,section,provenance,source_ref,event_at_utc,source_event_ids,text'.split(',');

function onOpen() {
  SpreadsheetApp.getUi().createMenu('NCCE relay')
    .addItem('Sync now', 'syncNCCE').addItem('Revise selected IMPORTED entry', 'reviseSelectedNCCE')
    .addItem('Install 5-minute relay', 'installNCCERelay')
    .addItem('Stop relay', 'stopNCCERelay').addToUi();
}

/** Owner-initiated: a NEW request and Queue row, never mutation of imported prose. */
function reviseSelectedNCCE() {
  const book = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  if (!book || book.getId() !== EXCHANGE_ID) {
    ui.alert('Open the NCCE Writing Exchange to request a revision.'); return;
  }
  const selection = book.getActiveRange();
  const queue = book.getSheetByName('Queue');
  if (!selection || selection.getSheet().getSheetId() !== queue.getSheetId() || selection.getRow() < 6) {
    ui.alert('Select an imported entry row in Queue.'); return;
  }
  const values = queue.getRange(selection.getRow(), 1, 1, 16).getDisplayValues()[0];
  if (values[1] !== 'IMPORTED' || !values[0] || !values[15]) {
    ui.alert('The selected row must be IMPORTED and have an import receipt.'); return;
  }
  const decision = ui.alert('Revise imported prose?',
    'A NEW WRITING request will be created for ' + values[6] +
    '. The original import and receipt will remain unchanged. Continue?',
    ui.ButtonSet.YES_NO);
  if (decision !== ui.Button.YES) return;
  const result = callNCCE('revise', {request_id: values[0], expected_receipt: values[15]});
  if (!result.request_id || !['PENDING','DEFERRED'].includes(result.status)) {
    throw new Error('NCCE did not confirm a revision request.');
  }
  syncNCCE(); // Publish its sealed new request and context into the Queue.
  ui.alert('Correction request created: ' + result.request_id +
    '. Edit that NEW row, then approve it through the normal WRITING → READY flow.');
}

function installNCCERelay() {
  // This first successful sync verifies credentials/headers before installing.
  syncNCCE();
  stopNCCERelay();
  ScriptApp.newTrigger('syncNCCE').timeBased().everyMinutes(5).create();
}

function stopNCCERelay() {
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'syncNCCE')
    .forEach(t => ScriptApp.deleteTrigger(t));
}

function callNCCE(path, payload) {
  const token = PropertiesService.getScriptProperties().getProperty('NCCE_EXCHANGE_TOKEN');
  if (!token || token.length < 32) throw new Error('Set NCCE_EXCHANGE_TOKEN in Script properties first.');
  const response = UrlFetchApp.fetch(BASE_URL + '/api/writing-exchange/relay/' + path, {
    method: 'post', contentType: 'application/json', headers: {Authorization: 'Bearer ' + token},
    payload: JSON.stringify(payload), muteHttpExceptions: true, followRedirects: false
  });
  if (response.getResponseCode() !== 200) {
    // Never log credentials or complete response bodies containing prose/context.
    throw new Error('NCCE relay HTTP ' + response.getResponseCode() + '; saved rows remain unchanged.');
  }
  return JSON.parse(response.getContentText());
}

function dataRows(sheet, columns) {
  return sheet.getLastRow() < 6 ? [] : sheet.getRange(6, 1, sheet.getLastRow() - 5, columns).getDisplayValues();
}

function verifyHeaders(sheet, expected) {
  if (!sheet || JSON.stringify(sheet.getRange(5, 1, 1, expected.length).getDisplayValues()[0]) !== JSON.stringify(expected)) {
    throw new Error('Exchange headers changed; nothing was written.');
  }
}

function matches(rows, id) { return rows.map((r, i) => r[0] === id ? i + 6 : null).filter(x => x !== null); }

function findRow(sheet, id, columns) {
  const found = matches(dataRows(sheet, columns), id);
  if (found.length > 1) throw new Error('Duplicate request ID; reconcile the Sheet before syncing.');
  return found[0] || null;
}

function writeLiteral(range, values) {
  // Sheets API stringValue preserves leading '=', '+', '@' and all Markdown.
  // SpreadsheetApp.setValues interprets '=' as a formula even for prose.
  const sheet = range.getSheet();
  Sheets.Spreadsheets.batchUpdate({requests: [{updateCells: {
    start: {sheetId: sheet.getSheetId(), rowIndex: range.getRow() - 1, columnIndex: range.getColumn() - 1},
    rows: values.map(row => ({values: row.map(v => ({userEnteredValue: {stringValue: String(v ?? '')}}))})),
    fields: 'userEnteredValue'
  }}]}, EXCHANGE_ID);
}

function ensureRoom(sheet, endRow) {
  if (endRow > sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(), endRow - sheet.getMaxRows() + 100);
}

function tableFor(sheet) {
  const meta = Sheets.Spreadsheets.get(EXCHANGE_ID, {fields: 'sheets(properties(sheetId),tables(tableId,range))'});
  const match = meta.sheets.find(s => s.properties.sheetId === sheet.getSheetId());
  const table = (match?.tables || []).find(t => t.range.startRowIndex === 4 && (t.range.startColumnIndex || 0) === 0);
  if (!table) throw new Error('Native exchange table missing; sync stopped.');
  return table;
}

function growTable(sheet, endRow) {
  const table = tableFor(sheet);
  if (endRow <= table.range.endRowIndex) return;
  ensureRoom(sheet, endRow);
  Sheets.Spreadsheets.batchUpdate({requests: [{updateTable: {
    table: {tableId: table.tableId, range: {...table.range, endRowIndex: endRow}}, fields: 'range'
  }}]}, EXCHANGE_ID);
}

function appendContext(contextSheet, packet) {
  const id = packet.request.context_id;
  // On a transport crash, remove only this not-yet-published packet's partial
  // rows and write them again. No work chat can see a PENDING request yet.
  const prior = matches(dataRows(contextSheet, 7), id);
  if (prior.length) prior.forEach(row => contextSheet.getRange(row, 1, 1, 7).clearContent());
  const rows = [];
  packet.context.forEach(block => {
    // Full context, never silent truncation. Each cell stays below 50k chars.
    const text = String(block.text || '');
    for (let offset = 0; offset < Math.max(text.length, 1); offset += 20000) {
      rows.push([id, block.section, block.provenance, block.source_ref, block.event_at_utc || '',
        block.source_event_ids || '', text.slice(offset, offset + 20000)]);
    }
  });
  const table = tableFor(contextSheet);
  const existing = contextSheet.getRange(6, 1, table.range.endRowIndex - 5, 7).getDisplayValues();
  let start = null, free = 0;
  for (let i = 0; i < existing.length; i++) {
    free = existing[i].every(v => !v) ? free + 1 : 0;
    if (free === rows.length) {start = i + 7 - rows.length; break;}
  }
  if (start === null) {
    // Insert before footer/source-directory rows; preserve them outside the table.
    start = table.range.endRowIndex + 1;
    contextSheet.insertRowsBefore(start, Math.max(20, rows.length));
    growTable(contextSheet, start + Math.max(20, rows.length) - 1);
  }
  writeLiteral(contextSheet.getRange(start, 1, rows.length, 7), rows);
}

function writeGuidance(book, guidance) {
  Object.entries(guidance).forEach(([title, text]) => {
    // Do not overwrite the manually maintained Writer skill tab. This transport
    // owns separate clearly named tabs, including the full identity reference.
    const name = title === 'Writer skill' ? 'Automation skill' : title;
    const sheet = book.getSheetByName(name) || book.insertSheet(name);
    const parts = [['Section', 'Instructions']];
    for (const section of text.split(/(?=^## )/m)) {
      const titleLine = section.split('\n')[0].replace(/^#+\s*/, '') || title;
      for (let offset = 0; offset < section.length; offset += 1000) parts.push([titleLine, section.slice(offset, offset + 1000)]);
    }
    if (JSON.stringify(sheet.getRange(1, 1, parts.length, 2).getDisplayValues()) === JSON.stringify(parts)) return;
    ensureRoom(sheet, parts.length);
    writeLiteral(sheet.getRange(1, 1, parts.length, 2), parts);
    sheet.getRange(1, 1, parts.length, 2).setWrap(true);
    sheet.setColumnWidth(1, 220); sheet.setColumnWidth(2, 850);
    sheet.setFrozenRows(1);
    sheet.autoResizeRows(1, parts.length);
  });
}

// Reporting only: never schedules a job or changes Queue/Context.
function writeQueueStatus(book, waterfall, queue) {
  if (!waterfall || !waterfall.categories) return; // Older server: retain last report.
  const sheet = book.getSheetByName('Queue status') || book.insertSheet('Queue status');
  const available = dataRows(queue,16).filter(r => r[2] && r[1] === 'PENDING' && !r[11]);
  const parts = [
    ['QUEUE STATUS','Operator dashboard — the writer reads Queue, not this tab.'],
    ['WRITER INPUT','Only PENDING rows without saved prose. DRAFT = deferred; IMPORTED = already on the site.'],
    ['AVAILABLE NOW',String(available.length)+' jobs after the latest successful reconciliation'],
    ['Status','Prose type / form ID','Entry','Request'],
    ...available.map(r => [r[1],r[2],r[6],r[0].slice(0,8)]), // Full IDs remain in Queue.
    [],
    ['FULL BACKLOG','All 16 prose types — these are counts, not instructions to write them now.'],
    ['Stage','Prose type','Form ID','Authored','Accepted','To write','Blocked','Total slots'],
    ...waterfall.categories.map(c => [c.policy === 'authored_only' ? 'Authored only' : String(c.phase),
      c.group+' — '+c.name,c.form,String(c.authored),String(c.accepted),
      c.policy === 'authored_only' ? 'Not queued' : String(c.needs_writing),String(c.blocked),String(c.total)]),
    [],
    ['Stage order','0 Baselines → 1 Recorded events → 2 Reflections → 3 Current thoughts → 4 Histories / downtime → 5 Regional chronicle'],
    ['Count definitions','Authored = source text. Accepted = current exchange/pilot receipt. To write = unaccepted derived slots, including legacy drafts. Blocked is a subset of To write awaiting prerequisites or recovery.'],
    ['Authored-only policy','Post-battle addenda remain authored only. Missing gang backstories enter Stage 0. Total slots include authored and derived records.'],
    ['Preserved history',String(waterfall.legacy_saved)+' legacy projections saved; '+String(waterfall.deferred)+' requests deferred. Deferred battle reports remain in Queue as DRAFT for later reuse, not writer jobs.']
  ].map(row => Array.from({length:8},(_,i) => row[i] || ''));
  const height=Math.max(parts.length,sheet.getLastRow());
  ensureRoom(sheet,height);
  const before=sheet.getRange(1,1,height,8).getDisplayValues();
  const padded=Array.from({length:height},(_,i) => parts[i] || Array(8).fill(''));
  if (JSON.stringify(before) === JSON.stringify(padded)) return;
  writeLiteral(sheet.getRange(1,1,height,8),padded);
  sheet.getRange(1,1,height,8).setWrap(true);
  [95,235,180,85,70,70,70,80].forEach((width,i) => sheet.setColumnWidth(i+1,width));
  const range=(start,end) => ({sheetId:sheet.getSheetId(),startRowIndex:start,endRowIndex:end,startColumnIndex:0,endColumnIndex:8});
  const headerRows=[0,3,5+available.length,6+available.length];
  Sheets.Spreadsheets.batchUpdate({requests:[
    {repeatCell:{range:range(0,height),cell:{userEnteredFormat:{verticalAlignment:'TOP',
      backgroundColor:{red:0.96,green:0.97,blue:0.95},textFormat:{fontFamily:'Arial',fontSize:10,bold:false,foregroundColor:{red:0.13,green:0.18,blue:0.15}}}},
      fields:'userEnteredFormat(verticalAlignment,backgroundColor,textFormat)'}},
    ...headerRows.map(row => ({repeatCell:{range:range(row,row+1),cell:{userEnteredFormat:{
      backgroundColor:{red:0.16,green:0.24,blue:0.19},textFormat:{bold:true,foregroundColor:{red:1,green:1,blue:1}}}},
      fields:'userEnteredFormat(backgroundColor,textFormat.bold,textFormat.foregroundColor)'}}))
  ]},EXCHANGE_ID);
  sheet.setFrozenRows(1);
  sheet.autoResizeRows(1,height);
}

function syncNCCE() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const book = SpreadsheetApp.openById(EXCHANGE_ID);
    const queue = book.getSheetByName('Queue'), context = book.getSheetByName('Context');
    verifyHeaders(queue, QUEUE_HEADERS); verifyHeaders(context, CONTEXT_HEADERS);
    const rows = dataRows(queue, 16);
    const seen = new Set();
    rows.filter(r => r[2]).forEach(r => {
      if (seen.has(r[0])) throw new Error('Duplicate request ID; sync stopped.');
      seen.add(r[0]);
    });
    // Deliver existing output before asking for new work. Maximum 5 per run.
    for (const row of rows.filter(r => r[1] === 'READY' && r[2]).slice(0, 5)) {
      const payload = {request_id: row[0], status: 'READY', source_revision: row[8],
        writer_text_md: row[11], writer_note: row[12], completed_at_utc: row[13]};
      const receipt = callNCCE('deliver', payload);
      const currentRow = findRow(queue, row[0], 16);
      if (!currentRow) throw new Error('Delivered row moved or disappeared; receipt is retained in NCCE.');
      const current = queue.getRange(currentRow, 1, 1, 16).getDisplayValues()[0];
      if (current[1] !== 'READY' || current[8] !== row[8] || current[11] !== row[11]) {
        throw new Error('Delivered row changed during import; reconcile retained NCCE receipt, do not regenerate.');
      }
      if (receipt.status === 'imported') {
        writeLiteral(queue.getRange(currentRow, 15, 1, 2), [[receipt.imported_at_utc, receipt.receipt]]);
        writeLiteral(queue.getRange(currentRow, 2), [['IMPORTED']]);
      } else {
        writeLiteral(queue.getRange(currentRow, 13), [[receipt.error || 'Held by NCCE; draft preserved.']]);
        writeLiteral(queue.getRange(currentRow, 2), [['HOLD']]);
      }
    }
    const queueState = dataRows(queue,16).filter(r => r[2] && ['PENDING','WRITING','READY','HOLD'].includes(r[1]))
      .map(r => ({request_id:r[0],status:r[1],has_text:!!r[11],note:r[12] || ''}));
    const outbox = callNCCE('poll', {protocol_version:2,queue_state:queueState});
    // Explicit owner-authorized correction of a paused origin brief. Never touch prose.
    for (const amendment of outbox.amendments || []) {
      const row=findRow(queue,amendment.request_id,16);
      if (!row) continue;
      const current=queue.getRange(row,1,1,16).getDisplayValues()[0];
      if (!['PENDING','WRITING'].includes(current[1]) || current[8]!==amendment.previous_revision) continue;
      appendContext(context,amendment.packet);
      SpreadsheetApp.flush();
      const latest=queue.getRange(row,1,1,16).getDisplayValues()[0];
      if (latest[0]!==current[0] || latest[1]!==current[1] || latest[8]!==current[8] || latest[11]!==current[11]) {
        throw new Error('Paused brief changed during amendment; draft retained for reconciliation.');
      }
      writeLiteral(queue.getRange(row,9),[[amendment.source_revision]]);
    }
    writeGuidance(book, outbox.guidance);
    for (const item of outbox.deferred || []) {
      const row=findRow(queue,item.request_id,16);
      if (!row) continue;
      const current=queue.getRange(row,1,1,16).getDisplayValues()[0];
      if (current[1]==='PENDING' && !current[11] && current[8]===item.source_revision) {
        writeLiteral(queue.getRange(row,2),[['DRAFT']]);
      }
    }
    for (const hold of outbox.holds || []) {
      const row = findRow(queue, hold.request_id, 16);
      if (!row) continue;
      const current = queue.getRange(row, 1, 1, 16).getDisplayValues()[0];
      if (current[8] !== hold.source_revision || ['IMPORTED','HOLD'].includes(current[1])) continue;
      writeLiteral(queue.getRange(row, 13), [[hold.error]]);
      writeLiteral(queue.getRange(row, 2), [['HOLD']]);
    }
    for (const packet of outbox.packets) {
      const request = packet.request;
      const existing = findRow(queue, request.request_id, 16);
      if (existing) {
        const current = queue.getRange(existing, 1, 1, 16).getDisplayValues()[0];
        if (['WRITING','READY'].includes(current[1]) || current[11]) continue;
        // Recover only an interrupted relay publication of its own complete DRAFT.
        if (current[1] === 'DRAFT' && current[8] === request.source_revision && current[7] === request.context_id) {
          appendContext(context, packet);
          SpreadsheetApp.flush();
          writeLiteral(queue.getRange(existing, 2), [['PENDING']]);
        }
        continue; // Never reset WRITING/READY/HOLD or overwrite prose.
      }
      appendContext(context, packet);
      SpreadsheetApp.flush();
      const empty = dataRows(queue, 16).findIndex(r => !r[2] && (!r[1] || r[1] === 'DRAFT'));
      const target = empty >= 0 ? empty + 6 : Math.max(6, queue.getLastRow() + 1);
      ensureRoom(queue, target);
      growTable(queue, target);
      // Reuse blank placeholder capacity, but packet UUID replaces placeholder.
      writeLiteral(queue.getRange(target, 1, 1, 16), [QUEUE_HEADERS.map(h => h === 'status' ? 'DRAFT' : request[h] || '')]);
      SpreadsheetApp.flush();
      writeLiteral(queue.getRange(target, 2), [['PENDING']]); // Publish only after complete context.
    }
    // Counters include appended requests rather than only the original 20 slots.
    queue.getRange('B3').setFormula('=COUNTIFS(C6:C,"<>",B6:B,"PENDING")');
    queue.getRange('D3').setFormula('=COUNTIFS(C6:C,"<>",B6:B,"READY")');
    queue.getRange('F3').setFormula('=COUNTIFS(C6:C,"<>",B6:B,"IMPORTED")');
    writeQueueStatus(book,outbox.waterfall,queue); // Read actual statuses after all mutations.
    PropertiesService.getScriptProperties().setProperty('NCCE_LAST_SUCCESS_UTC', new Date().toISOString());
  } finally { lock.releaseLock(); }
}
