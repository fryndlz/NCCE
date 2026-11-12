/** Optional historical-backfill transport. Does not touch Queue, Context or syncNCCE. */
const BULK_JOB_HEADERS = [
  'job_id','gang_id','gang_name','status','approval_policy','snapshot_count',
  'imported_count','held_count','skipped_count','created_at','closed_at'
];
const BULK_ITEM_HEADERS = [
  'job_id','request_id','status','sequence','fighter_id','form','title',
  'source_revision','context_id','writer_text_md','writer_note',
  'imported_at_utc','import_receipt','error'
];
const BULK_CONTEXT_HEADERS = CONTEXT_HEADERS;

function bulkSheet_(book, title, headers) {
  let sheet = book.getSheetByName(title);
  if (!sheet) {
    sheet = book.insertSheet(title);
    writeLiteral(sheet.getRange(1,1,1,headers.length),[headers]);
    sheet.setFrozenRows(1);
    sheet.getRange(1,1,1,headers.length).setFontWeight('bold');
  }
  const actual = sheet.getRange(1,1,1,headers.length).getDisplayValues()[0];
  if (JSON.stringify(actual) !== JSON.stringify(headers)) {
    throw new Error('Bulk tab headers changed: '+title+'; no write attempted.');
  }
  return sheet;
}

function bulkFind_(sheet, value, column) {
  if (sheet.getLastRow() < 2) return null;
  const matches = sheet.getRange(2,column,sheet.getLastRow()-1,1)
    .getDisplayValues().map((r,i) => r[0] === value ? i+2 : null).filter(Boolean);
  if (matches.length > 1) throw new Error('Duplicate bulk ID in '+sheet.getName());
  return matches[0] || null;
}

function bulkAppendContext_(sheet, packet) {
  if (!packet || !packet.request || !packet.context) throw new Error('Missing sealed backfill context');
  const id = packet.request.context_id;
  if (sheet.getLastRow()>=2 && sheet.getRange(2,1,sheet.getLastRow()-1,1)
      .getDisplayValues().some(r=>r[0]===id)) return;
  const lines = [];
  packet.context.forEach(block => {
    const full = String(block.text || '');
    for (let offset=0;offset<Math.max(1,full.length);offset+=20000) {
      lines.push([id,block.section,block.provenance,block.source_ref||'',
        block.event_at_utc||'',block.source_event_ids||'',full.slice(offset,offset+20000)]);
    }
  });
  if (lines.length) {
    const start=sheet.getLastRow()+1;
    ensureRoom(sheet,start+lines.length-1);
    writeLiteral(sheet.getRange(start,1,lines.length,7),lines);
  }
}

function bulkUpdateJob_(sheet, job) {
  let row=bulkFind_(sheet,job.job_id,1);
  if (!row) row=sheet.getLastRow()+1;
  ensureRoom(sheet,row);
  const counts=job.counts||{};
  writeLiteral(sheet.getRange(row,1,1,BULK_JOB_HEADERS.length),[[
    job.job_id,job.gang_id,job.gang_name,job.state,job.approval_policy,
    job.snapshot_count,counts.IMPORTED||0,counts.HELD||0,job.skipped_count||0,
    job.created_at,job.closed_at||''
  ]]);
}

function bulkPublishItem_(itemsSheet, contextSheet, item) {
  const packet=item.packet;
  if (!packet || !packet.request) throw new Error('Missing frozen packet for bulk item');
  const request=packet.request;
  const existing=bulkFind_(itemsSheet,item.request_id,2);
  if (existing) {
    const old=itemsSheet.getRange(existing,1,1,BULK_ITEM_HEADERS.length).getDisplayValues()[0];
    if (old[0]!==item.job_id || old[7]!==request.source_revision || old[8]!==request.context_id) {
      throw new Error('Bulk request ID/source collision. Preserve saved draft; reconcile manually.');
    }
    if (old[2]==='HOLD' && item.status==='WRITING')
      writeLiteral(itemsSheet.getRange(existing,3),[['WRITING']]); // Keep all prior wording.
    return;
  }
  bulkAppendContext_(contextSheet,packet);
  SpreadsheetApp.flush();
  const row=itemsSheet.getLastRow()+1;
  ensureRoom(itemsSheet,row);
  const doc=[item.job_id,item.request_id,'WRITING',item.sequence,item.fighter_id,
    request.form,request.title,request.source_revision,request.context_id,
    '','','','',''];
  writeLiteral(itemsSheet.getRange(row,1,1,BULK_ITEM_HEADERS.length),[doc]);
}

/**
 * Separate transport: deliver saved READY bulk drafts, then claim another
 * bounded batch per active job. Existing normal relay is never invoked here.
 */
function syncNCCEBulk() {
  const lock=LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const book=SpreadsheetApp.openById(EXCHANGE_ID);
    const jobsTab=bulkSheet_(book,'Bulk Jobs',BULK_JOB_HEADERS);
    const itemsTab=bulkSheet_(book,'Bulk Items',BULK_ITEM_HEADERS);
    const ctxTab=bulkSheet_(book,'Bulk Context',BULK_CONTEXT_HEADERS);
    const saved=itemsTab.getLastRow()<2 ? [] :
      itemsTab.getRange(2,1,itemsTab.getLastRow()-1,BULK_ITEM_HEADERS.length).getDisplayValues();
    const used=new Set();
    saved.forEach(r=>{
      if (used.has(r[1])) throw new Error('Duplicate bulk request ID; delivery suspended.');
      if (r[1])used.add(r[1]);
    });
    // Deliver first. NCCE deduplicates a retry after a lost acknowledgement.
    for (const previous of saved.filter(r=>r[2]==='READY')) {
      if (!previous[9]) throw new Error('READY bulk draft has no text: '+previous[1]);
      const reply=callNCCE('bulk/deliver',{
        job_id:previous[0],request_id:previous[1],source_revision:previous[7],
        writer_text_md:previous[9],writer_note:previous[10]
      });
      const row=bulkFind_(itemsTab,previous[1],2);
      if (!row) throw new Error('Bulk row disappeared after delivery; retained NCCE receipt is authoritative');
      const current=itemsTab.getRange(row,1,1,BULK_ITEM_HEADERS.length).getDisplayValues()[0];
      if (current[2]!=='READY' || current[0]!==previous[0] ||
          current[7]!==previous[7] || current[9]!==previous[9]) {
        throw new Error('Bulk draft changed during import; do not rewrite or duplicate it.');
      }
      if (reply.status==='imported') {
        writeLiteral(itemsTab.getRange(row,12,1,3),[[
          reply.imported_at_utc||'',reply.receipt||'',''
        ]]);
        writeLiteral(itemsTab.getRange(row,3),[['IMPORTED']]);
      } else {
        writeLiteral(itemsTab.getRange(row,14),[[reply.error||'Held for manual reconciliation']]);
        writeLiteral(itemsTab.getRange(row,3),[['HOLD']]);
      }
    }
    const found=callNCCE('bulk/poll',{});
    for (const job of found.jobs||[]) {
      bulkUpdateJob_(jobsTab,job);
      if (!['AUTHORIZED','RUNNING'].includes(job.state)) continue;
      const claimed=callNCCE('bulk/poll',{job_id:job.job_id,claim:true,limit:25});
      for (const item of claimed.items||[]) bulkPublishItem_(itemsTab,ctxTab,item);
    }
    PropertiesService.getScriptProperties().setProperty('NCCE_BULK_LAST_SUCCESS_UTC',new Date().toISOString());
  } finally {lock.releaseLock();}
}

function installNCCEBulkRelay() {
  syncNCCEBulk(); // Prove that credentials, headers and separate routing work.
  stopNCCEBulkRelay();
  ScriptApp.newTrigger('syncNCCEBulk').timeBased().everyMinutes(5).create();
}

function stopNCCEBulkRelay() {
  ScriptApp.getProjectTriggers().filter(t=>t.getHandlerFunction()==='syncNCCEBulk')
    .forEach(t=>ScriptApp.deleteTrigger(t));
}

/** Imported bulk prose is corrected as a NEW, manual-approval normal request. */
function reviseSelectedBulkNCCE() {
  const ui=SpreadsheetApp.getUi(),book=SpreadsheetApp.getActiveSpreadsheet();
  const sheet=book.getSheetByName('Bulk Items'),selected=book.getActiveRange();
  if (!sheet || !selected || selected.getSheet().getSheetId()!==sheet.getSheetId() ||
      selected.getRow()<2) {ui.alert('Select an IMPORTED row in Bulk Items.');return;}
  const values=sheet.getRange(selected.getRow(),1,1,BULK_ITEM_HEADERS.length).getDisplayValues()[0];
  if (values[2]!=='IMPORTED' || !values[12]) {
    ui.alert('Bulk memory must be IMPORTED and have a receipt.');return;
  }
  if (ui.alert('Request manual correction?',
      'Create a new standard Exchange revision for this imported memory? The original ID and receipt remain intact.',
      ui.ButtonSet.YES_NO)!==ui.Button.YES)return;
  const response=callNCCE('bulk/correct',{job_id:values[0],
    request_id:values[1],expected_receipt:values[12]});
  if (!response.request_id) throw new Error('NCCE did not confirm the revision request.');
  syncNCCE();
  ui.alert('Manual correction request: '+response.request_id+'; review it in the normal Queue.');
}

function escalateSelectedBulkNCCE() {
  const ui=SpreadsheetApp.getUi(),book=SpreadsheetApp.getActiveSpreadsheet();
  const sheet=book.getSheetByName('Bulk Items'),selected=book.getActiveRange();
  if (!sheet || !selected || selected.getSheet().getSheetId()!==sheet.getSheetId() ||
      selected.getRow()<2) {ui.alert('Select an unimported Bulk Items row.');return;}
  const v=sheet.getRange(selected.getRow(),1,1,BULK_ITEM_HEADERS.length).getDisplayValues()[0];
  if (!['HOLD','WRITING'].includes(v[2])) {
    ui.alert('Only held or unfinished bulk drafts can be escalated.');return;
  }
  if (ui.alert('Return to manual review?',
      'Transfer this same request ID to the normal Exchange for explicit review?',
      ui.ButtonSet.YES_NO)!==ui.Button.YES)return;
  const response=callNCCE('bulk/escalate',{job_id:v[0],request_id:v[1]});
  if (response.state!=='ESCALATED')throw new Error('NCCE did not transfer the request.');
  writeLiteral(sheet.getRange(selected.getRow(),3),[['ESCALATED']]);
  syncNCCE();
  ui.alert('Transferred request '+v[1]+' to the normal Exchange.');
}

/** Explicit owner retry; existing text is preserved for editing, never auto-resent. */
function retrySelectedBulkNCCE() {
  const ui=SpreadsheetApp.getUi(),book=SpreadsheetApp.getActiveSpreadsheet();
  const sheet=book.getSheetByName('Bulk Items'),selected=book.getActiveRange();
  if (!sheet || !selected || selected.getSheet().getSheetId()!==sheet.getSheetId() ||
      selected.getRow()<2) {ui.alert('Select a HOLD row in Bulk Items.');return;}
  const v=sheet.getRange(selected.getRow(),1,1,BULK_ITEM_HEADERS.length).getDisplayValues()[0];
  if (v[2]!=='HOLD') {ui.alert('This bulk entry is not on HOLD.');return;}
  if (ui.alert('Retry held draft?',
      'Retain the same ID and source revision, clear its held status, and allow editing before a new READY submission?',
      ui.ButtonSet.YES_NO)!==ui.Button.YES)return;
  const item=callNCCE('bulk/retry',{job_id:v[0],request_id:v[1]});
  if (item.state!=='PENDING')throw new Error('NCCE did not confirm the retry.');
  writeLiteral(sheet.getRange(selected.getRow(),3),[['WRITING']]);
  ui.alert('Edit the saved draft, then set this Bulk Items row to READY.');
}
