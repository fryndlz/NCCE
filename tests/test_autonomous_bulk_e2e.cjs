/* True NCCE HTTP relay and SQLite, with disposable Sheets and synthetic provider replies. */
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {createHash} = require('node:crypto');
const fs = require('node:fs');
const vm = require('node:vm');

const [url, token, jobId, requestId] = process.argv.slice(2);
const files = ['Code','Bulk','AutonomousBulkWriter','AutonomousBulkWriterTests'];
const code = files.map(name => fs.readFileSync('scripts/writing_exchange/' + name + '.gs','utf8')).join('\n');
const qaKeys = ['mechanics','chronology','lore','character','style','format','length'];
const draft = '**THE CLOSED GATE**\n\nI held the gate. The lesson hurt more than the bruise.';
const replacement = '**THE LOCKED HINGE**\n\nWhen the gate stuck, I held it. Next shift, I will oil the hinge first.';
const doubleEcho = 'const [url, token, body] = process.argv.slice(1); ' +
  "fetch(url, {method:'POST', headers:{authorization:'Bearer '+token,'content-type':'application/json'}, body})" +
  '.then(async response => console.log(JSON.stringify([response.status,await response.text()])))';
function post(path, body, key = token) {
  const raw = execFileSync(process.execPath,['-e',doubleEcho,url + '/api/writing-exchange/relay/' + path,key,
    JSON.stringify(body)], {encoding:'utf8'});
  const [status,text] = JSON.parse(raw);
  return {status, body:JSON.parse(text)};
}

class Sheet {
  constructor(name, id) { this.name = name; this.id = id; this.rows = []; this.capacity = 1; }
  getName() { return this.name; }
  getSheetId() { return this.id; }
  getLastRow() { return this.rows.length; }
  getLastColumn() { return Math.max(1,...this.rows.map(row => row.length)); }
  getMaxRows() { return this.capacity; }
  insertRowsAfter(_, count) { this.capacity += count; }
  setFrozenRows() {}
  setColumnWidth() {}
  getRange(row,col=1,rows=1,cols=1) {
    return {
      getSheet:() => this, getRow:() => row, getColumn:() => col, setFontWeight() {},
      getDisplayValues:() => Array.from({length:rows},(_,y) => Array.from({length:cols},
        (_,x) => this.rows[row+y-1]?.[col+x-1] ?? '')),
      clearContent:() => { for (let y=0;y<rows;y++) this.rows[row+y-1]=[]; }
    };
  }
}

const sheets = new Map();
const book = {
  getSheetByName:name => sheets.get(name),
  insertSheet(name) { const sheet = new Sheet(name,sheets.size+1); sheets.set(name,sheet); return sheet; }
};
for (const name of ['Writer instructions','Writer skill','Voice identity']) {
  book.insertSheet(name).rows.push(['Section','Instruction'],['Synthetic test','Use the gate only.']);
}
const props = new Map([
  ['NCCE_EXCHANGE_TOKEN',token],['NCCE_BULK_WRITER_ENABLED','true'],['NCCE_BULK_WRITER_API_KEY','mock-provider-credential']
]);
let now = Date.now();
class TimerDate extends Date { static now() { return now; } }
let calls = [], rateLimited = true, configFailure = true, failCheckpointResponse = false, failImportResponse = false, failReadyWrite = false;
function makeRuntime() {
  const sandbox = vm.createContext({
    console, Date:TimerDate, SpreadsheetApp:{openById:() => book, flush() {}},
    PropertiesService:{getScriptProperties:() => ({
      getProperty:key => props.get(key), setProperty:(key,value) => props.set(key,value)
    })},
    Utilities:{DigestAlgorithm:{SHA_256:0},Charset:{UTF_8:0},
      computeDigest:(_,value) => [...createHash('sha256').update(value).digest()]},
    Sheets:{Spreadsheets:{batchUpdate(payload) {
      for (const {updateCells:update} of payload.requests) {
        const sheet = [...sheets.values()].find(s => s.id === update.start.sheetId);
        assert.ok(update.start.rowIndex+update.rows.length <= sheet.capacity);
        const first = update.rows[0].values[0].userEnteredValue.stringValue;
        if (failReadyWrite && sheet.name === 'Bulk Items' && update.start.columnIndex === 1 && first === 'READY') {
          failReadyWrite = false;
          throw new Error('simulated worker crash before READY');
        }
        update.rows.forEach((row,y) => row.values.forEach((cell,x) => {
          (sheet.rows[update.start.rowIndex+y] ??= [])[update.start.columnIndex+x] = cell.userEnteredValue.stringValue;
        }));
      }
    }}},
    UrlFetchApp:{fetch(endpoint, options) {
      const input = JSON.parse(options.payload);
      let status = 200, body;
      if (endpoint === 'https://api.openai.com/v1/chat/completions') {
        const request = JSON.parse(input.messages[1].content);
        assert.ok(request.sealed_context.some(block => block.section === 'mechanics'));
        assert.ok(request.sealed_context.some(block => block.section === 'literary_policy'));
        assert.equal(request.writing_rules.length,3);
        assert.deepEqual(Object.keys(request.checklist),qaKeys);
        const review = Boolean(input.response_format);
        calls.push(review ? 'review' : 'draft');
        if (rateLimited) {
          rateLimited = false;
          return {getResponseCode:() => 429,getContentText:() => '{"error":{"code":"rate_limit_exceeded"}}'};
        }
        if (review && configFailure) {
          configFailure = false;
          return {getResponseCode:() => 401,getContentText:() => '{"error":{"code":"invalid_api_key"}}'};
        }
        let text;
        if (review) {
          assert.deepEqual(input.response_format.json_schema.schema.required,qaKeys);
          const pass = request.draft === replacement;
          text = JSON.stringify(Object.fromEntries(qaKeys.map(key => [key,{
            pass:pass || key !== 'chronology',
            reason:pass || key !== 'chronology' ? 'Supported by test fixture.' : 'Match event ordering.'
          }])));
        } else if (request.previous_draft) {
          assert.equal(request.previous_draft,draft);
          assert.deepEqual(request.required_fixes,['chronology: Match event ordering.']);
          text = replacement;
        } else text = draft;
        body = {choices:[{finish_reason:'stop',message:{content:text}}]};
      } else {
        const path = endpoint.split('/relay/')[1];
        const result = post(path,input);
        status = result.status;
        body = result.body;
        if (failCheckpointResponse && path === 'bulk/checkpoint' && input.state.phase === 'draft' &&
            input.state.issues.length) {
          failCheckpointResponse = false;
          throw new Error('simulated lost checkpoint response');
        }
        if (failImportResponse && path === 'bulk/deliver' && body.status === 'imported') {
          failImportResponse = false;
          throw new Error('simulated lost import response');
        }
      }
      return {getResponseCode:() => status,getContentText:() => JSON.stringify(body)};
    }}
  });
  vm.runInContext(code,sandbox);
  return expression => vm.runInContext(expression,sandbox);
}
const execute = expression => makeRuntime()(expression);
const tick = () => execute("const book=SpreadsheetApp.openById(EXCHANGE_ID); " +
  "const deadline=Date.now()+1e5; runAutonomousBulkWriter(book,syncHistoricalBackfill(book,deadline),deadline);");
const inspection = () => post('bulk/status',{job_id:jobId}).body;
const item = () => sheets.get('Bulk Items').rows.find(row => row[0] === requestId);

assert.equal(post('bulk/status',{job_id:jobId},'unauthorized').status,401);
assert.equal(execute('testAutonomousBulkWriterValidation()'),'PASS: 6 deterministic validation cases');
assert.throws(() => execute("bulkWriterVerdict(JSON.stringify({pass:true,issues:[]}))"),/incomplete/);
execute('setupHistoricalBackfill()');
tick();
assert.equal(item()[1],'WRITING');
assert.equal(item()[11],'');
assert.deepEqual(calls,['draft']);
tick();
assert.deepEqual(calls,['draft']);
now += 10 * 60000;
tick();
tick();
assert.ok(props.get('NCCE_BULK_PAUSE_' + jobId).includes('401'));
assert.deepEqual(calls,['draft','draft','review']);
tick(); // Paused until an operator corrects configuration.
assert.deepEqual(calls,['draft','draft','review']);
props.delete('NCCE_BULK_PAUSE_' + jobId);
now += 10 * 60000;
failCheckpointResponse = true;
assert.throws(tick,/lost checkpoint response/);
assert.equal(item()[1],'WRITING');
tick();
assert.deepEqual(calls,['draft','draft','review','review','draft']);
failReadyWrite = true;
assert.throws(tick,/simulated worker crash/);
assert.equal(item()[1],'WRITING');
assert.equal(item()[11],replacement);
tick();
assert.equal(item()[1],'READY');
assert.deepEqual(calls,['draft','draft','review','review','draft','review']);
failImportResponse = true;
tick();
assert.equal(item()[1],'READY');
const firstReceipt = inspection().items[0].receipt;
assert.ok(firstReceipt);
tick();
assert.equal(item()[1],'IMPORTED');
assert.equal(item()[15],firstReceipt);
assert.deepEqual(inspection().statuses,{IMPORTED:1});
assert.equal(inspection().state,'COMPLETED');
assert.ok(sheets.get('Bulk Reports').rows[1][8].includes('range=Q2'));
const report = sheets.get('Bulk Reports').rows[1].slice();
tick();
assert.deepEqual(sheets.get('Bulk Reports').rows,[sheets.get('Bulk Reports').rows[0],report]);
assert.equal(calls.length,6);
const revised = post('bulk/revise',{job_id:jobId,request_id:requestId,expected_receipt:firstReceipt});
assert.equal(revised.status,200);
assert.equal(revised.body.status,'PENDING');
assert.notEqual(revised.body.request_id,requestId);
assert.equal(inspection().items[0].receipt,firstReceipt);
console.log('PASS: actual HTTP + SQLite, one-item timed backfill, quota retry, key pause, rejected checklist, interrupted checkpoints, receipt replay, report and manual correction');
