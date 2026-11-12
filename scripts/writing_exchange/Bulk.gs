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

function bulkAudit(book, jobId, requestId, action, status, receipt, message) {
  const sheet=bulkGetSheet(book,'Bulk Audit',BULK_AUDIT_HEADERS);
  const next=sheet.getLastRow()+1;
  writeLiteral(sheet.getRange(next,1,1,7), [[new Date().toISOString(),
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
  writeLiteral(sheet.getRange(sheet.getLastRow()+1,1,rows.length,7),rows);
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
  const decision=ui.alert('Authorize this finite job?',
    'Gang names: '+(names.join(', ')||'(none)')+
    '\nHouse types: '+(houses.join(', ')||'(none)')+
    '\nOnly existing unfinished fighter memories will be selected. Every item is tracked; corrections later require your explicit approval.',
    ui.ButtonSet.YES_NO);
  if(decision!==ui.Button.YES)return;
  setupHistoricalBackfill();
  const job=callNCCE('bulk/create',{
    gang_names:names,house_types:houses,owner_authorized:true
  });
  const book=SpreadsheetApp.openById(EXCHANGE_ID);
  const sheet=book.getSheetByName('Bulk Jobs');
  if(bulkFind(sheet,job.job_id,10))throw new Error('Bulk job exists already');
  writeLiteral(sheet.getRange(sheet.getLastRow()+1,1,1,10), [[
    job.job_id,job.state,JSON.stringify(job.scope),String(job.discovered),
    String(job.queued),'0',String(job.skipped.length),new Date().toISOString(),'',''
  ]]);
  // Materialize the COMPLETE finite manifest up front. WRITING is released
  // in dependency order; WAITING items are visible and counted meanwhile.
  const manifest=callNCCE('bulk/status',{job_id:job.job_id});
  const itemSheet=book.getSheetByName('Bulk Items');
  const entries=(manifest.items||[]).map(entry=>[
    entry.request_id,entry.status==='PENDING'?'WAITING':entry.status,
    entry.form,'fighter',entry.entity_key,entry.target_key,
    entry.title||'', '',entry.source_revision||'','', '', '', '', '', '', '',
    job.job_id,entry.error||''
  ]);
  if(entries.length)writeLiteral(
    itemSheet.getRange(itemSheet.getLastRow()+1,1,entries.length,18),entries);
  bulkAudit(book,job.job_id,'','CREATE',job.state,'',
    'Manifest discovered '+job.discovered+', queued '+job.queued+', skipped '+job.skipped.length);
  ui.alert('Backfill '+job.job_id+' created: '+job.queued+
    ' queued, '+job.skipped.length+' skipped. Open Bulk Jobs / Bulk Items to inspect.');
}

/** Optional part of the existing timer. Errors here must never stop normal relay. */
function syncHistoricalBackfill(book) {
  if(!book.getSheetByName('Bulk Jobs'))return; // feature not initialized
  const jobs=bulkGetSheet(book,'Bulk Jobs',BULK_JOB_HEADERS);
  const items=bulkGetSheet(book,'Bulk Items',BULK_ITEM_HEADERS);
  const context=bulkGetSheet(book,'Bulk Context',CONTEXT_HEADERS);
  const active=bulkRows(jobs,10).filter(r=>r[0]&&r[1]==='ACTIVE');
  for(const job of active) {
    const jobId=job[0];
    // Deliver already-approved bulk texts FIRST. Preserve exactly as written.
    let delivered=0;
    for(const row of bulkRows(items,18).filter(r=>r[16]===jobId&&r[1]==='READY'&&r[11]).slice(0,10)) {
      const cellRow=bulkFind(items,row[0],18);
      const result=callNCCE('bulk/deliver',{
        job_id:jobId,request_id:row[0],status:'READY',
        source_revision:row[8],writer_text_md:row[11],
        writer_note:row[12],completed_at_utc:row[13]
      });
      const current=items.getRange(cellRow,1,1,18).getDisplayValues()[0];
      if(current[0]!==row[0]||current[1]!=='READY'||
         current[8]!==row[8]||current[11]!==row[11]) {
        throw new Error('Bulk draft changed during delivery; NCCE receipt retained. Reconcile by ID.');
      }
      if(result.status==='imported') {
        writeLiteral(items.getRange(cellRow,15,1,2),
          [[result.imported_at_utc||new Date().toISOString(),result.receipt]]);
        writeLiteral(items.getRange(cellRow,2),[['IMPORTED']]);
      } else {
        writeLiteral(items.getRange(cellRow,18),[[result.error||'Held by NCCE']]);
        writeLiteral(items.getRange(cellRow,2),[['HOLD']]);
      }
      bulkAudit(book,jobId,row[0],'DELIVER',result.status,result.receipt,result.error);
      delivered++;
    }
    const update=callNCCE('bulk/poll',{job_id:jobId,limit:25});
    for(const packet of update.packets||[]) {
      const r=packet.request;
      const found=bulkFind(items,r.request_id,18);
      if(found) {
        const prior=items.getRange(found,1,1,18).getDisplayValues()[0];
        // A manifest placeholder can be promoted once, not an active claim.
        if(prior[1]!=='WAITING'||prior[11])continue;
      }
      bulkContextWrite(context,packet);
      SpreadsheetApp.flush();
      const line=BULK_ITEM_HEADERS.map(h=>h==='job_id'?jobId:
        h==='status'?'DRAFT':String(r[h]||''));
      const target=found||items.getLastRow()+1;
      writeLiteral(items.getRange(target,1,1,18),[line]);
      SpreadsheetApp.flush();
      writeLiteral(items.getRange(target,2),[['PENDING']]);
      bulkAudit(book,jobId,r.request_id,'EXPOSE','PENDING','',r.title);
    }
    const fresh=callNCCE('bulk/status',{job_id:jobId});
    // Reconcile NCCE-side holds (including source-drift BEFORE a packet was
    // released). Keep any editor-owned WRITING/READY text strictly untouched.
    for(const entry of fresh.items||[]) {
      if(!['HOLD','SKIPPED'].includes(entry.status))continue;
      const itemRow=bulkFind(items,entry.request_id,18);
      if(!itemRow)continue;
      const saved=items.getRange(itemRow,1,1,18).getDisplayValues()[0];
      if(!['WAITING','PENDING','SKIPPED','HOLD'].includes(saved[1])||saved[11])continue;
      if(saved[1]!==entry.status) {
        writeLiteral(items.getRange(itemRow,2),[[entry.status]]);
        bulkAudit(book,jobId,entry.request_id,'HOLD',entry.status,'',entry.error);
      }
      if(saved[17]!==String(entry.error||'')) {
        writeLiteral(items.getRange(itemRow,18),[[entry.error||'']]);
      }
    }
    const jobRow=bulkFind(jobs,jobId,10);
    writeLiteral(jobs.getRange(jobRow,2,1,6),[[
      fresh.state,JSON.stringify(fresh.scope),String(fresh.manifest.source_count),
      String(fresh.count),String(fresh.statuses.IMPORTED||0),
      String((fresh.statuses.HOLD||0)+(fresh.statuses.SKIPPED||0))
    ]]);
    const waiting=(fresh.statuses.PENDING||0)+(fresh.statuses.WRITING||0);
    if(!waiting) {
      const closed=callNCCE('bulk/close',{job_id:jobId});
      writeLiteral(jobs.getRange(jobRow,2),[[closed.state]]);
      writeLiteral(jobs.getRange(jobRow,9),[[new Date().toISOString()]]);
      bulkAudit(book,jobId,'','CLOSE',closed.state,'','Finite manifest exhausted');
    }
  }
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
  writeLiteral(jobs.getRange(selected.getRow(),2),[[completed.state]]);
  writeLiteral(jobs.getRange(selected.getRow(),9),[[new Date().toISOString()]]);
  const items=book.getSheetByName('Bulk Items');
  const finalManifest=callNCCE('bulk/status',{job_id:row[0]});
  for(const item of finalManifest.items||[]) {
    if(item.status!=='HOLD')continue;
    const i=bulkFind(items,item.request_id,18);
    if(!i)continue;
    const state=items.getRange(i,2).getDisplayValue();
    if(state==='WAITING')writeLiteral(items.getRange(i,2),[['HOLD']]);
    writeLiteral(items.getRange(i,18),[[item.error||'Unresolved historical backfill']]);
  }
  bulkAudit(book,row[0],'','FINALIZE',completed.state,'',
    'Explicit owner finalization; unresolved items retained for reconciliation');
  ui.alert('Job '+row[0]+' closed: '+completed.state);
}
