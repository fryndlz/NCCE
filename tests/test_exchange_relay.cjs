/* Exercise the real Apps Script against in-memory Google services. No network. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('scripts/writing_exchange/Code.gs','utf8');
let nextId=10,batchRequests=[],httpCalls=[],failStatus=false;
class Sheet {
  constructor(name){this.name=name;this.id=nextId++;this.rows=[];this.max=1000;this.table={tableId:String(this.id),range:{sheetId:this.id,startRowIndex:4,endRowIndex:25,startColumnIndex:0,endColumnIndex:name==='Queue'?16:7}};}
  getSheetId(){return this.id;}getLastRow(){let n=this.rows.length;while(n&&!this.rows[n-1]?.some(v=>v!==''&&v!=null))n--;return n;}getMaxRows(){return this.max;}
  setColumnWidth(){}setFrozenRows(){}autoResizeRows(){}insertRowsAfter(_,n){this.max+=n;}
  insertRowsBefore(row,n){this.rows.splice(row-1,0,...Array.from({length:n},()=>[]));this.max+=n;}
  getRange(r,c=1,n=1,m=1){
    if(typeof r==='string'){const match=r.match(/^([A-Z]+)(\d+)$/);c=match[1].charCodeAt(0)-64;r=+match[2];}
    const self=this;return {getSheet:()=>self,getRow:()=>r,getColumn:()=>c,
      getDisplayValues:()=>Array.from({length:n},(_,i)=>Array.from({length:m},(_,j)=>String(self.rows[r+i-1]?.[c+j-1]??''))),
      clearContent(){for(let i=0;i<n;i++)for(let j=0;j<m;j++)(self.rows[r+i-1]??=[])[c+j-1]='';},
      setWrap(){},setFormula(value){(self.rows[r-1]??=[])[c-1]=value;}};
  }
}
const book={sheets:[],getSheetByName(name){return this.sheets.find(s=>s.name===name);},insertSheet(name){const s=new Sheet(name);this.sheets.push(s);return s;}};
const queue=book.insertSheet('Queue'),context=book.insertSheet('Context');
queue.rows[4]='request_id,status,form,entity_type,entity_key,entry_key,title,context_id,source_revision,event_at_utc,imperial_date,writer_text_md,writer_note,completed_at_utc,imported_at_utc,import_receipt'.split(',');
context.rows[4]='context_id,section,provenance,source_ref,event_at_utc,source_event_ids,text'.split(',');
queue.rows[5]=['mara-pilot','IMPORTED','fighter_memory','','','','','','','','','Accepted Mara'];
queue.rows[6]=['unused-placeholder','DRAFT'];
context.rows[5]=['ctx:mara','authored_canon','','','','','Preserved canon'];
context.rows[29]=['','','','','','source directory','Do not overwrite'];
const request={request_id:'new-uuid',status:'PENDING',form:'territory_origin',entity_type:'territory',entity_key:'7',entry_key:'sealed',title:'Place',context_id:'ctx:new',source_revision:'sha256:test',event_at_utc:'',imperial_date:''};
let outbox={packets:[{request,context:[{section:'mechanics',provenance:'mechanical_fact',source_ref:'facts',text:'Facts'},{section:'brief',provenance:'instruction',source_ref:'brief',text:'Write.'}]}],guidance:{'Automation instructions':'# Instructions\n\n## Work\nWrite once.'},holds:[]};
let imports=0;
const ctx=vm.createContext({console,Set,JSON,Date,Error,
  LockService:{getScriptLock:()=>({tryLock:()=>true,releaseLock(){}})},
  SpreadsheetApp:{openById:()=>book,flush(){}},
  PropertiesService:{getScriptProperties:()=>({getProperty:()=> 'disposable-test-only-00000000000000',setProperty(){}})},
  Sheets:{Spreadsheets:{get:()=>({sheets:book.sheets.map(s=>({properties:{sheetId:s.id},tables:[s.table]}))}),batchUpdate(payload){
    for(const r of payload.requests){batchRequests.push(r);
      if(r.repeatCell)continue;
      if(r.updateTable){const t=r.updateTable.table;book.sheets.find(s=>s.table.tableId===t.tableId).table.range=t.range;continue;}
      const u=r.updateCells,s=book.sheets.find(s=>s.id===u.start.sheetId);
      if(failStatus&&s===queue&&u.start.columnIndex===1&&u.rows[0].values[0].userEnteredValue.stringValue==='IMPORTED'){failStatus=false;throw Error('Ack failed');}
      u.rows.forEach((row,i)=>row.values.forEach((cell,j)=>{assert.ok('stringValue'in cell.userEnteredValue);(s.rows[u.start.rowIndex+i]??=[])[u.start.columnIndex+j]=cell.userEnteredValue.stringValue;}));
    }
  }}},
  UrlFetchApp:{fetch(url,options){httpCalls.push({url,options});assert.equal(options.followRedirects,false);const p=JSON.parse(options.payload);
    let result=outbox;if(url.endsWith('/deliver')){imports++;result={status:'imported',request_id:p.request_id,receipt:'same-committed-receipt',imported_at_utc:'2026-11-05T01:00:00Z'};outbox={...outbox,packets:[]};}
    return {getResponseCode:()=>200,getContentText:()=>JSON.stringify(result)};
  }}
});
vm.runInContext(source,ctx);
const run=()=>vm.runInContext('syncNCCE()',ctx);
run();assert.equal(queue.rows[6][0],request.request_id);assert.equal(queue.rows[6][1],'PENDING');
assert.equal(context.rows[5][6],'Preserved canon');assert.equal(context.rows[29][6],'Do not overwrite');
const contextCount=context.rows.filter(r=>r?.[0]==='ctx:new').length;assert.equal(contextCount,2);
run();assert.equal(context.rows.filter(r=>r?.[0]==='ctx:new').length,2);
assert.equal(queue.rows[5][11],'Accepted Mara');
// A failed acknowledgement must resend saved text, not generate or export again.
const literal='=HYPERLINK("not a formula")\n\n**A proper draft.**';
queue.rows[6][1]='READY';queue.rows[6][11]=literal;failStatus=true;
assert.throws(run,/Ack failed/);assert.equal(queue.rows[6][1],'READY');
run();assert.equal(queue.rows[6][1],'IMPORTED');assert.equal(queue.rows[6][11],literal);
assert.equal(queue.rows[6][15],'same-committed-receipt');assert.equal(imports,2);
assert.ok(batchRequests.every(r=>!r.updateCells||r.updateCells.rows.every(row=>row.values.every(c=>!('formulaValue'in c.userEnteredValue)))));
// Interrupted publishing of the relay's own DRAFT is recoverable without writing.
request.request_id='another-uuid';request.context_id='ctx:another';outbox.packets=[{request,context:[{section:'brief',text:'One.'}]}];
queue.rows[7]=[request.request_id,'DRAFT',request.form,request.entity_type,request.entity_key,request.entry_key,request.title,request.context_id,request.source_revision];
run();assert.equal(queue.rows[7][1],'PENDING');
// Growth preserves footer records outside the native Context table.
outbox.packets=[];
const growthPacket={request:{...request,context_id:'ctx:growth'},context:Array.from({length:30},(_,i)=>({section:'mechanics',text:String(i)}))};
ctx.growthPacket=growthPacket;ctx.contextSheet=context;
vm.runInContext('appendContext(contextSheet,growthPacket)',ctx);
assert.equal(context.rows.filter(r=>r?.[0]==='ctx:growth').length,30);
assert.ok(context.table.range.endRowIndex>25);
assert.ok(context.rows.findIndex(r=>r?.[6]==='Do not overwrite')+1>context.table.range.endRowIndex);
// Reprioritization withdraws only unclaimed, empty rows; claims and text survive.
outbox.packets=[];outbox.deferred=[{request_id:'another-uuid',source_revision:request.source_revision}];
run();assert.equal(queue.rows[7][1],'DRAFT');
queue.rows[7][1]='WRITING';run();assert.equal(queue.rows[7][1],'WRITING');
queue.rows[7][1]='PENDING';queue.rows[7][11]='Partial saved draft';run();assert.equal(queue.rows[7][1],'PENDING');
queue.rows[7][11]='';outbox.deferred=[];
const lastPoll=httpCalls.filter(c=>c.url.endsWith('/poll')).at(-1);
assert.equal(JSON.parse(lastPoll.options.payload).protocol_version,2);
assert.ok(JSON.parse(lastPoll.options.payload).queue_state.every(r=>r.status!=='IMPORTED'));
// Duplicated IDs stop transport rather than attach prose to an arbitrary row.
// Operator report reflects actual dispatchable rows AFTER deferral, never a backlog job list.
outbox.waterfall={legacy_saved:12,deferred:1,categories:Array.from({length:16},(_,i)=>({
  form:'form_'+i,group:'Group',name:'Category '+i,phase:0,policy:'exchange',
  authored:0,accepted:0,needs_writing:2,blocked:1,total:2}))};
queue.rows[7][1]='PENDING';queue.rows[7][11]='';
outbox.deferred=[{request_id:'another-uuid',source_revision:request.source_revision}];
run();
const status=book.getSheetByName('Queue status');
assert.equal(status.rows[2][1],'0 jobs after the latest successful reconciliation');
assert.equal(status.rows.filter(r=>String(r?.[2]).startsWith('form_')).length,16);
assert.ok(!status.rows.some(r=>r?.[3]==='mara-pilot'||r?.[3]==='another-uuid'));
outbox.deferred=[];queue.rows[7][1]='PENDING';run();
assert.equal(status.rows[2][1],'1 jobs after the latest successful reconciliation');
assert.equal(status.rows[4][3],'another-uuid');
queue.rows[7][11]='Partial saved prose';run();
assert.equal(status.rows[2][1],'0 jobs after the latest successful reconciliation');
assert.ok(!status.rows.some(r=>r?.[3]==='another-uuid')); // Also clears shrinking report tails.
queue.rows[8]=queue.rows[7].slice();assert.throws(run,/Duplicate request ID/);
console.log('PASS Apps Script relay: immutable pilot, literal Markdown, receipts after ACK failure, DRAFT recovery, table growth, duplicate stop');
