/**
 * Owner-operated batch editorial corrections for already imported bulk prose.
 * This file must be added to the SAME bound Apps Script project as Code.gs
 * and Bulk.gs. It does not generate prose or mark a revision READY.
 *
 * Editorial QA row contract:
 * E original request_id, F import receipt, J correction path,
 * M correction request_id. Bulk Items: A ID, B status, P receipt, Q job ID.
 */
const EDITORIAL_QA_HEADERS = [
  'Bulk row','Fighter','Form','Original status','Original request_id',
  'Import receipt','Unicode chars','Rule findings','Audit status',
  'Correction path','Next action','Owner approval','Correction request_id'
];

function createCorrectionsForFailedQA() {
  const book=SpreadsheetApp.getActiveSpreadsheet();
  const ui=SpreadsheetApp.getUi();
  if(!book||book.getId()!==EXCHANGE_ID) throw new Error('Open the NCCE Writing Exchange first.');
  const qa=book.getSheetByName('Editorial QA');
  const bulk=book.getSheetByName('Bulk Items');
  if(!qa||!bulk) throw new Error('Editorial QA and Bulk Items tabs must exist.');
  const h=qa.getRange(1,1,1,13).getDisplayValues()[0];
  if(JSON.stringify(h)!==JSON.stringify(EDITORIAL_QA_HEADERS)) {
    throw new Error('Editorial QA headers have changed; batch aborted.');
  }
  const last=qa.getLastRow();
  if(last<2){ui.alert('No audited entries found.');return;}
  const audited=qa.getRange(2,1,last-1,13).getDisplayValues();
  const original=bulkRows(bulk,18);
  const indexed=new Map();
  original.forEach(row=>{
    if(!row[0])return;
    if(indexed.has(row[0]))throw new Error('Duplicate bulk request '+row[0]);
    indexed.set(row[0],row);
  });
  const found=[];
  let skippedExisting=0;
  audited.forEach((r,i)=>{
    if(r[9]!=='REVISION_REQUIRED')return;
    if(r[12]){skippedExisting++;return;} // never create a duplicate by click
    const src=indexed.get(r[4]);
    if(!src||src[1]!=='IMPORTED'||!src[15]||src[15]!==r[5]||src[2]!==r[2]) {
      throw new Error('Imported source/receipt mismatch in QA row '+(i+2)+'; no requests created.');
    }
    if(!src[16])throw new Error('Missing historical job ID in QA row '+(i+2));
    found.push({qaRow:i+2,jobId:src[16],request_id:r[4],receipt:r[5]});
  });
  if(found.length===0){
    ui.alert('No new failed QA entries need correction requests. '+skippedExisting+
      ' already have linked requests. Drafts and approvals are handled separately.');
    return;
  }
  if(found.length>100)throw new Error('Maximum 100 correction requests per batch.');
  const jobs=[...new Set(found.map(x=>x.jobId))];
  if(jobs.length!==1)throw new Error('Select one historical job per batch; mixed jobs rejected.');
  const answer=ui.alert('Create '+found.length+' versioned corrections?',
    'This creates ordinary PENDING writing requests. It does NOT rewrite, approve, or import text. '+
    'Original imported memories and receipts stay unchanged. Existing linked requests: '+
    skippedExisting+'. Proceed?',ui.ButtonSet.YES_NO);
  if(answer!==ui.Button.YES)return;

  const result=callNCCE('bulk/revise-batch',{
    owner_authorized:true,job_id:jobs[0],
    items:found.map(x=>({request_id:x.request_id,receipt:x.receipt}))
  });
  if(result.total!==found.length||!Array.isArray(result.created)||
     !Array.isArray(result.reused)||!Array.isArray(result.blocked)) {
    throw new Error('NCCE returned an invalid batch response; inspect server before retrying.');
  }
  const successful=[...result.created,...result.reused];
  const matched=new Map(successful.map(x=>[x.parent,x.request_id]));
  if(matched.size!==successful.length)throw new Error('Duplicate batch response IDs.');
  successful.forEach(x=>{
    const row=found.find(z=>z.request_id===x.parent);
    if(!row||!x.request_id)throw new Error('Unmatched batch response; inspect NCCE.');
    const current=qa.getRange(row.qaRow,1,1,13).getDisplayValues()[0];
    if(current[4]!==row.request_id||current[5]!==row.receipt||
       current[9]!=='REVISION_REQUIRED') {
      throw new Error('QA row changed after request creation; reconcile by original ID.');
    }
    if(current[12]&&current[12]!==x.request_id) {
      throw new Error('Conflicting revision in QA row '+row.qaRow);
    }
    writeLiteral(qa.getRange(row.qaRow,13),[[x.request_id]]);
    bulkAudit(book,jobs[0],row.request_id,'EDITORIAL_BATCH_REVISION',
      'PENDING','', 'New ordinary Queue correction: '+x.request_id);
  });
  const errors=result.blocked.map(x=>x.parent+': '+x.error);
  // Publishing to Queue is a separate relay step. A sync failure must not
  // be mistaken for failure to create requests, which now exist on NCCE.
  let syncProblem='';
  if(successful.length){
    try{syncNCCE();}catch(e){syncProblem=String(e.message||e).slice(0,250);}
  }
  ui.alert('Editorial batch result',
    'Created: '+result.created.length+'; reused: '+result.reused.length+
    '; blocked: '+result.blocked.length+'.'+
    (errors.length?'\nBlocked IDs: '+errors.join('; ').slice(0,650):'')+
    (syncProblem?'\nQueue sync needs retry: '+syncProblem:'')+
    '\nCorrections are not yet approved or imported.',ui.ButtonSet.OK);
}
