/** NCCE Historical Backfill — optional transport, completely separate from Queue.
 * Deployment: add this file to the same bound Apps Script project, then use
 * "Historical backfill" menu; requires the deployed bulk endpoints.
 * It never executes an LLM or touches normal Queue/Context rows.
 */
const BULK_JOB_HEADERS = [
  'job_id','status','scope_json','discovered','queued','imported','held',
  'created_at_utc','closed_at_utc','last_error'
];
const BULK_ITEM_HEADERS = QUEUE_HEADERS.concat(['job_id','error']);
const BULK_AUDIT_HEADERS = [
  'at_utc','job_id','request_id','action','status','receipt','message'
];

function bulkGetSheet(book, title, headers) {
  let sheet=book.getSheetByName(title);
  if (!sheet) {
    sheet=book.insertSheet(title);
    writeLiteral(sheet.getRange(1,1,1,headers.length), [headers]);
    sheet.setFrozenRows(1);
    sheet.getRange(1,1,1,headers.length).setFontWeight('bold');
    sheet.setColumnWidth(1,260);
    sheet.setColumnWidth(2,145);
  } else {
    const present=sheet.getRange(1,1,1,headers.length).getDisplayValues()[0];
    if (JSON.stringify(present)!==JSON.stringify(headers)) {
      throw new Error('Historical backfill tab '+title+' has unexpected headers.');
    }
  }
  return sheet;
}

function setupHistoricalBackfill() {
  const book=SpreadsheetApp.openById(EXCHANGE_ID);
  bulkGetSheet(book,'Bulk Jobs',BULK_JOB_HEADERS);
  bulkGetSheet(book,'Bulk Items',BULK_ITEM_HEADERS);
  bulkGetSheet(book,'Bulk Context',CONTEXT_HEADERS);
  bulkGetSheet(book,'Bulk Audit',BULK_AUDIT_HEADERS);
}

function bulkRows(sheet, n) {
  const last=sheet.getLastRow();
  return last<2 ? [] : sheet.getRange(2,1,last-1,n).getDisplayValues();
}

function bulkFind(sheet, id, n) {
  const hits=[];
  bulkRows(sheet,n).forEach((r,i)=>{if(r[0]===id)hits.push(i+2);});
  if (hits.length>1) throw new Error('Duplicate bulk ID in '+sheet.getName()+': '+id);
  return hits[0]||null;
}

function bulkAppend(sheet, rows) {
  if (!rows.length) return;
  const start = sheet.getLastRow() + 1;
  ensureRoom(sheet, start + rows.length - 1);
  writeLiteral(sheet.getRange(start, 1, rows.length, rows[0].length), rows);
}

function bulkAudit(book, jobId, requestId, action, status, receipt, message) {
  const sheet=bulkGetSheet(book,'Bulk Audit',BULK_AUDIT_HEADERS);
  bulkAppend(sheet, [[new Date().toISOString(),
    jobId,requestId,action,status,receipt||'',String(message||'').slice(0,1000)]]);
}

function bulkContextWrite(sheet,packet) {
  const id=packet.request.context_id;
  // Recover incomplete publication by abandoning old unpublished context rows.
  // Only the bulk-only context tab may be modified.
  const existing=bulkRows(sheet,7).map((r,i)=>r[0]===id?i+2:null).filter(Boolean);
  if(existing.length) existing.forEach(row=>sheet.getRange(row,1,1,7).clearContent());
  const rows=[];
  (packet.context||[]).forEach(block=>{
    const value=String(block.text||'');
    for(let off=0;off<Math.max(1,value.length);off+=20000) {
      rows.push([id,block.section,block.provenance,block.source_ref,
        block.event_at_utc||'',block.source_event_ids||'',value.slice(off,off+20000)]);
    }
  });
  if(!rows.length) throw new Error('Bulk packet has no source context');
  bulkAppend(sheet, rows);
}

function createHistoricalBackfill() {
  const ui=SpreadsheetApp.getUi();
  const result=ui.prompt('Historical backfill',
    'Enter exact gang or House selectors separated by commas. Examples: gang:C-NINE, gang:Kły Sprawiedliwości, house:House Orlock. This is a ONE-OFF snapshot and uses autonomous approval ONLY for this job.',
    ui.ButtonSet.OK_CANCEL);
  if(result.getSelectedButton()!==ui.Button.OK)return;
  const names=[],houses=[];
  result.getResponseText().split(',').map(x=>x.trim()).filter(Boolean).forEach(value=>{
    if(value.startsWith('gang:'))names.push(value.slice(5).trim());
    else if(value.startsWith('house:'))houses.push(value.slice(6).trim());
    else throw new Error('Use gang: or house: before every name');
  });
  if(!names.length&&!houses.length)throw new Error('No backfill scope was selected');
  const window = ui.prompt('Inclusive event dates (UTC)', 'Enter YYYY-MM-DD .. YYYY-MM-DD.', ui.ButtonSet.OK_CANCEL);
  if (window.getSelectedButton() !== ui.Button.OK) return;
  const dates = window.getResponseText().trim().match(/^(\d{4}-\d{2}-\d{2})\s*\.\.\s*(\d{4}-\d{2}-\d{2})$/);
  if (!dates || dates[1] > dates[2]) throw new Error('Enter two ordered ISO dates.');
  const cap = ui.prompt('Maximum number of items', 'The whole job is refused if its scope exceeds this limit (1–2000).', ui.ButtonSet.OK_CANCEL);
  if (cap.getSelectedButton() !== ui.Button.OK) return;
  const maxItems = Number(cap.getResponseText().trim());
  if (!Number.isInteger(maxItems) || maxItems < 1 || maxItems > 2000) throw new Error('Enter a limit between 1 and 2000.');
  const decision = ui.alert('Authorize this finite job?',
    'Scope: ' + [...names, ...houses].join(', ') + '\nUTC events: ' + dates[1] + ' to ' + dates[2] +
    '\nLimit: ' + maxItems + ' items. OpenAI receives their NCCE evidence and guidance for writing and independent review.' +
    '\nThis authorizes at most 3 writer calls and 9 reviewer calls per item. Later corrections require your approval.',
    ui.ButtonSet.YES_NO);
  if (decision !== ui.Button.YES) return;
  setupHistoricalBackfill();
  const job = callNCCE('bulk/create', {
    gang_names:names, house_types:houses, start_date:dates[1], end_date:dates[2], max_items:maxItems,
    owner_authorized:true, autonomous_writer_authorized:true
  });
  ui.alert('Backfill ' + job.job_id + ' created: ' + job.queued +
    ' queued, ' + job.skipped.length + ' skipped. The relay will publish the manifest on its next tick.');
}

function bulkIndex(sheet, width) {
  const result = new Map();
  bulkRows(sheet, width).forEach((values, i) => {
    if (!values[0]) return;
    if (result.has(values[0])) throw new Error('Duplicate bulk ID in ' + sheet.getName() + ': ' + values[0]);
    result.set(values[0], {values, number:i + 2});
  });
  return result;
}

function bulkReconcile(items, itemsById, jobId, fresh) {
  const missing = [];
  for (const entry of fresh.items || []) {
    const saved = itemsById.get(entry.request_id);
    const remote = entry.status;
    const receipt = entry.receipt || '';
    const error = entry.error || '';
    if (!saved) {
      missing.push([
        entry.request_id, ['PENDING','WRITING'].includes(remote) ? 'WAITING' : remote,
        entry.form,'fighter',entry.entity_key,entry.target_key,entry.title || '', '', '',
        entry.event_at_utc || '', '', '', '', '', entry.imported_at_utc || '', receipt,jobId,error
      ]);
      continue;
    }
    const {values, number} = saved;
    if (values[16] !== jobId) throw new Error('Bulk item assigned to a different job: ' + entry.request_id);
    if (remote === 'IMPORTED') {
      if (values[1] === 'IMPORTED' && values[15] === receipt) continue;
      if (values[15] && values[15] !== receipt) {
        writeLiteral(items.getRange(number,18), [['Receipt mismatch. Review NCCE audit before editing.']]);
        continue;
      }
      if (values[11] && entry.text_sha256 && entry.text_sha256 !== bulkWriterHash(values[11])) {
        writeLiteral(items.getRange(number,18), [['NCCE imported a different draft. Review the original receipt.']]);
        continue;
      }
      writeLiteral(items.getRange(number,15,1,2), [[entry.imported_at_utc || '',receipt]]);
      writeLiteral(items.getRange(number,2), [['IMPORTED']]);
    } else if (['HOLD','SKIPPED'].includes(remote) && values[1] !== 'IMPORTED') {
      if (values[17] !== error) writeLiteral(items.getRange(number,18), [[error]]);
      if (values[1] !== remote) writeLiteral(items.getRange(number,2), [[remote]]);
    }
  }
  bulkAppend(items, missing);
}

function bulkUpdateJob(jobs, jobRow, fresh, diagnostic) {
  const scope = fresh.manifest.start_date ? {
    gang_ids:fresh.scope, start_date:fresh.manifest.start_date, end_date:fresh.manifest.end_date
  } : fresh.scope;
  const skipped = fresh.statuses.SKIPPED || 0;
  const data = [fresh.job_id,fresh.state,JSON.stringify(scope),String(fresh.manifest.source_count ?? fresh.count),
    String(fresh.count - skipped),String(fresh.statuses.IMPORTED || 0),String(fresh.statuses.HOLD || 0),
    fresh.created_at || '',fresh.closed_at || '',diagnostic || ''];
  if (jobRow) {
    if (JSON.stringify(jobRow.values) !== JSON.stringify(data)) {
      writeLiteral(jobs.getRange(jobRow.number,1,1,data.length), [data]);
    }
  } else bulkAppend(jobs,[data]);
}

function bulkDeliverReady(book, items, jobId, itemsById) {
  const ready = [...itemsById.values()].filter(s => s.values[16] === jobId && s.values[1] === 'READY');
  for (const {number,values} of ready.slice(0,10)) {
    const payload = {
      qa_protocol:BULK_QA_PROTOCOL, job_id:jobId, request_id:values[0],status:'READY',
      source_revision:values[8],writer_text_md:values[11],
      writer_note:values[12],completed_at_utc:values[13]
    };
    let result;
    try { result = callNCCE('bulk/deliver',payload); }
    catch (error) {
      if (error.httpStatus !== 400) throw error;
      if (values[17] !== error.message) writeLiteral(items.getRange(number,18), [[error.message]]);
      continue;
    }
    const current = items.getRange(number,1,1,18).getDisplayValues()[0];
    if ([0,1,7,8,11,16].some(i => current[i] !== values[i])) {
      throw new Error('Bulk row changed during delivery. NCCE receipt will be reconciled by ID.');
    }
    if (result.status === 'imported') {
      if (!result.receipt || !result.imported_at_utc) throw new Error('NCCE returned an incomplete receipt');
      writeLiteral(items.getRange(number,15,1,2), [[result.imported_at_utc,result.receipt]]);
      writeLiteral(items.getRange(number,2), [['IMPORTED']]);
      if (current[17]) writeLiteral(items.getRange(number,18), [['']]);
    } else if (result.status === 'needs_review' || result.status === 'held') {
      writeLiteral(items.getRange(number,18), [[result.error]]);
      writeLiteral(items.getRange(number,2), [[result.status === 'held' ? 'HOLD' : 'WRITING']]);
    } else throw new Error('Unexpected bulk delivery result');
    bulkAudit(book,jobId,values[0],'DELIVER',result.status,result.receipt,result.error);
  }
}

function bulkExpose(book, items, context, itemsById, jobId, packets, deadline) {
  for (const packet of packets) {
    if (Date.now() > deadline) break;
    const r = packet.request;
    const previous = itemsById.get(r.request_id);
    if (previous && previous.values[16] !== jobId) throw new Error('Bulk packet job mismatch: ' + r.request_id);
    if (previous && (!['WAITING','DRAFT'].includes(previous.values[1]) || previous.values[11])) continue;
    if (previous) {
      const current = items.getRange(previous.number,1,1,18).getDisplayValues()[0];
      if ([0,1,11,16].some(i => current[i] !== previous.values[i])) continue;
    }
    bulkContextWrite(context,packet);
    SpreadsheetApp.flush();
    const line = BULK_ITEM_HEADERS.map(h => h === 'job_id' ? jobId :
      h === 'status' ? 'DRAFT' : String(r[h] || ''));
    const number = previous?.number || items.getLastRow()+1;
    ensureRoom(items,number);
    writeLiteral(items.getRange(number,1,1,18),[line]);
    SpreadsheetApp.flush();
    writeLiteral(items.getRange(number,2),[['PENDING']]);
    bulkAudit(book,jobId,r.request_id,'EXPOSE','PENDING','',r.title);
  }
}

/** Existing five-minute trigger runs transport before making at most one model call. */
function syncHistoricalBackfill(book, deadline) {
  if (!book.getSheetByName('Bulk Jobs')) return [];
  const jobs = bulkGetSheet(book,'Bulk Jobs',BULK_JOB_HEADERS);
  const items = bulkGetSheet(book,'Bulk Items',BULK_ITEM_HEADERS);
  const context = bulkGetSheet(book,'Bulk Context',CONTEXT_HEADERS);
  const jobRows = bulkIndex(jobs,10);
  const reports = book.getSheetByName('Bulk Reports');
  const reported = new Set(reports ? bulkRows(reports,10).map(row => row[1]) : []);
  const batches = [];
  for (const job of callNCCE('bulk/jobs',{}).jobs) {
    if (Date.now() > deadline) break;
    const jobId = job.job_id, jobRow = jobRows.get(jobId);
    const isClosed = ['COMPLETED','COMPLETED_WITH_ERRORS'].includes(job.state);
    if (jobRow && jobRow.values[1] === job.state && job.state !== 'ACTIVE' &&
        (!isClosed || reported.has(jobId))) continue;
    try {
      let itemsById = bulkIndex(items,18);
      const enabled = typeof bulkWriterJobEnabled === 'function' && bulkWriterJobEnabled(jobId,job.writer_authorized);
      if (job.state === 'ACTIVE') {
        bulkDeliverReady(book,items,jobId,itemsById);
        const update = callNCCE('bulk/poll',{job_id:jobId,limit:10,resolve_blocked:!!enabled});
        const packets = update.packets || [];
        bulkExpose(book,items,context,itemsById,jobId,packets,deadline);
        batches.push({jobId,packets,authorized:job.writer_authorized});
        itemsById = bulkIndex(items,18);
      }
      let fresh = callNCCE('bulk/status',{job_id:jobId});
      bulkReconcile(items,itemsById,jobId,fresh);
      if (fresh.state === 'ACTIVE' && !(fresh.statuses.PENDING || fresh.statuses.WRITING)) {
        fresh = callNCCE('bulk/close',{job_id:jobId});
      }
      const pause = PropertiesService.getScriptProperties().getProperty('NCCE_BULK_PAUSE_' + jobId);
      bulkUpdateJob(jobs,jobRow,fresh,fresh.state === 'ACTIVE' ?
        pause || (enabled ? '' : 'Autonomous writer is disabled or awaits job authorization.') : '');
      if (['COMPLETED','COMPLETED_WITH_ERRORS'].includes(fresh.state) && !reported.has(jobId)) {
        bulkFinalReport(book,jobId,fresh.state,fresh);
      }
    } catch (error) {
      console.error('Bulk job ' + jobId + ': ' + error.message);
      if (jobRow) writeLiteral(jobs.getRange(jobRow.number,10), [[String(error.message).slice(0,350)]]);
    }
  }
  return batches;
}

function resumeSelectedBulkJob() {
  const book = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const selected = book?.getActiveRange();
  if (book?.getId() !== EXCHANGE_ID || selected?.getSheet().getName() !== 'Bulk Jobs' || selected.getRow() < 2) {
    ui.alert('Select the existing ACTIVE job in Bulk Jobs.'); return;
  }
  const [jobId,status] = selected.getSheet().getRange(selected.getRow(),1,1,2).getDisplayValues()[0];
  if (status !== 'ACTIVE' || !/^[a-f0-9-]{36}$/.test(jobId)) throw new Error('Select an ACTIVE job.');
  const p = PropertiesService.getScriptProperties();
  if (!p.getProperty('NCCE_BULK_WRITER_API_KEY') || p.getProperty('NCCE_BULK_WRITER_ENABLED') !== 'true') {
    ui.alert('The autonomous writer needs an API credential and must be enabled in Apps Script.'); return;
  }
  const fresh = callNCCE('bulk/status',{job_id:jobId});
  if (fresh.state !== 'ACTIVE') throw new Error('The existing job is not active in NCCE.');
  const remaining = (fresh.statuses.PENDING || 0) + (fresh.statuses.WRITING || 0);
  if (ui.alert('Resume this exact job?', jobId + '\n' + remaining +
    ' items remain. Approve sending their sealed evidence and guidance to OpenAI, within the existing per-item attempt limits.',
    ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(2000)) throw new Error('Relay is running. Try again after this tick.');
  try {
    const key = 'NCCE_BULK_WRITER_JOB_IDS';
    const jobIds = new Set((p.getProperty(key) || '').split(',').map(x => x.trim()).filter(Boolean));
    jobIds.add(jobId);
    p.setProperty(key,[...jobIds].join(','));
    p.deleteProperty('NCCE_BULK_PAUSE_' + jobId);
  } finally { lock.releaseLock(); }
  ui.alert('Authorized the same job. The existing timer will continue from its saved checkpoints.');
}

function showBulkOperationalStatus() {
  SpreadsheetApp.getUi().alert(bulkOperationalStatus());
}

function bulkOperationalStatus() {
  const p = PropertiesService.getScriptProperties();
  const jobs = callNCCE('bulk/jobs',{}).jobs;
  const enabled = jobs.filter(job => job.state === 'ACTIVE' && bulkWriterJobEnabled(job.job_id,job.writer_authorized));
  const result = [
    'NCCE relay credentials: verified',
    'OpenAI key present: ' + Boolean(p.getProperty('NCCE_BULK_WRITER_API_KEY')),
    'Writer enabled: ' + (p.getProperty('NCCE_BULK_WRITER_ENABLED') === 'true'),
    'Authorized active jobs: ' + enabled.length,
    'syncNCCE triggers for this account: ' + ScriptApp.getProjectTriggers().filter(x => x.getHandlerFunction() === 'syncNCCE').length,
    'Last successful normal relay: ' + (p.getProperty('NCCE_LAST_SUCCESS_UTC') || 'unknown')
  ].join('\n');
  console.log(result);
  return result;
}

function reviseSelectedBulkMemory() {
  const book=SpreadsheetApp.getActiveSpreadsheet();
  const ui=SpreadsheetApp.getUi();
  const items=book&&book.getSheetByName('Bulk Items');
  const selected=book&&book.getActiveRange();
  if(!book||book.getId()!==EXCHANGE_ID||!items||!selected||
     selected.getSheet().getSheetId()!==items.getSheetId()||selected.getRow()<2) {
    ui.alert('Select an IMPORTED row on Bulk Items first.');return;
  }
  const row=items.getRange(selected.getRow(),1,1,18).getDisplayValues()[0];
  if(row[1]!=='IMPORTED'||!row[15]||!row[16]) {
    ui.alert('Select an imported bulk item with a receipt.');return;
  }
  const decision=ui.alert('Return to manual correction?',
    'NCCE will create a NEW revision request in the ordinary Queue. The original ID, memory and receipt are preserved. The correction will require individual approval.',
    ui.ButtonSet.YES_NO);
  if(decision!==ui.Button.YES)return;
  const revised=callNCCE('bulk/revise',{
    job_id:row[16],request_id:row[0],expected_receipt:row[15]
  });
  bulkAudit(book,row[16],row[0],'MANUAL_REVISION',revised.status,'',
    'New normal Queue correction ID: '+revised.request_id);
  syncNCCE();
  ui.alert('Correction request '+revised.request_id+' created in normal Queue.');
}


/** Explicitly close a blocked job WITH ERRORS, preserving all failed items. */
function finalizeSelectedBulkJob() {
  const book=SpreadsheetApp.getActiveSpreadsheet();
  const ui=SpreadsheetApp.getUi();
  const jobs=book&&book.getSheetByName('Bulk Jobs');
  const selected=book&&book.getActiveRange();
  if(!book||book.getId()!==EXCHANGE_ID||!jobs||!selected||
     selected.getSheet().getSheetId()!==jobs.getSheetId()||selected.getRow()<2) {
    ui.alert('Select an ACTIVE job row in Bulk Jobs first.');return;
  }
  const row=jobs.getRange(selected.getRow(),1,1,10).getDisplayValues()[0];
  if(!row[0]||row[1]!=='ACTIVE'){
    ui.alert('Only an ACTIVE job may be finalized.');return;
  }
  const yes=ui.alert('Finish this job with errors?',
    'All unprocessed WAITING items will be preserved as HOLD with their reasons. This does not remove already imported prose, alter original IDs, or silently approve anything. Claimed WRITING drafts prevent finalization.',
    ui.ButtonSet.YES_NO);
  if(yes!==ui.Button.YES)return;
  const completed=callNCCE('bulk/close',{job_id:row[0],finalize_unresolved:true});
  const items=book.getSheetByName('Bulk Items');
  const finalManifest=callNCCE('bulk/status',{job_id:row[0]});
  bulkReconcile(items,bulkIndex(items,18),row[0],finalManifest);
  bulkUpdateJob(jobs, {number:selected.getRow(),values:row}, finalManifest);
  bulkFinalReport(book,row[0],completed.state,finalManifest);
  bulkAudit(book,row[0],'','FINALIZE',completed.state,'',
    'Explicit owner finalization; unresolved items retained for reconciliation');
  ui.alert('Job '+row[0]+' closed: '+completed.state);
}

/** One immutable completion record, with a direct review link. Imported entries
 * remain revisable only via the existing human-approved Queue correction flow.
 */
function bulkFinalReport(book,jobId,state,manifest) {
  const headers=['completed_at_utc','job_id','state','imported','skipped',
    'held','unresolved','total','review_url','correction_action'];
  const sheet=bulkGetSheet(book,'Bulk Reports',headers);
  if(bulkRows(sheet,headers.length).some(r=>r[1]===jobId))return;
  const statuses=manifest.statuses||{};
  const unresolved=(statuses.PENDING||0)+(statuses.WRITING||0);
  const items = book.getSheetByName('Bulk Items');
  const first = bulkRows(items,18).findIndex(row => row[16] === jobId);
  const review = 'https://docs.google.com/spreadsheets/d/' + EXCHANGE_ID +
    '/edit#gid=' + items.getSheetId() + (first < 0 ? '' : '&range=Q' + (first + 2));
  bulkAppend(sheet,[[
    manifest.closed_at || new Date().toISOString(),jobId,state,String(statuses.IMPORTED||0),
    String(statuses.SKIPPED||0),String(statuses.HOLD||0),
    String(unresolved),String(manifest.count||0),review,
    'Select IMPORTED Bulk Items row → Historical backfill → Revise selected bulk entry'
  ]]);
  bulkAudit(book,jobId,'','FINAL_REPORT',state,'',review);
}
