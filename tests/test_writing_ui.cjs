// Date and semantic-renderer contracts without a browser or external packages.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({document:{querySelector:()=>({})}, Intl, Date});
vm.runInContext(fs.readFileSync('web/writing.js','utf8'),context);
const app = fs.readFileSync('web/app.js','utf8');
vm.runInContext(app.slice(0,app.indexOf('async function api(')),context);
const run = code => vm.runInContext(code,context);
assert.equal(run("NCCEWriting.formatDate('2026-10-25T09:46:31.046883+00:00').imperialDisplay"),'9.814.998.M41');
assert.equal(run("NCCEWriting.formatDate('2026-10-25T09:46:31.046883+00:00').realDisplay"),'25 October 2026 · 10:46');
assert.equal(run("NCCEWriting.formatDate('2026-10-25').imperialDisplay"),'9.815.998.M41');
assert.equal(run("NCCEWriting.formatDate('2026-10-25T00:00:00').imperialDisplay"),'9.815.998.M41');
assert.equal(run("NCCEWriting.formatDate('2027-01-01').imperialDisplay"),'9.001.998.M41');
assert.equal(run("NCCEWriting.formatDate('2026-03-29T01:30:00Z').realDisplay"),'29 March 2026 · 03:30');
assert.equal(run("NCCEWriting.formatDate('2026-02-31').imperialDisplay"),'Date unverified');
context.doc = {document_type:'incident_record', metadata:[{label:'Source',value:'District compiler'}],
  blocks:[{type:'body_paragraph',id:'source',content:[{text:'SECRET',marks:['redacted']},{text:'<img src=x onerror=alert(1)>',marks:[]}]},
          {type:'disposition_panel',blocks:[{type:'addendum_panel',text:'Result',blocks:[{type:'body_paragraph',text:'Filed'}]}]},
          {type:'testimony_note',id:'witness',anchor:'source',author:'Witness',text:'I was elsewhere.'},
          {type:'transcript',turns:[{speaker:'A',text:'Wait.'},{speaker:'B',text:'Here.'}]}],
  termination:{type:'record_termination',text:'// RECORD ENDS //'}};
const html = run('blocks(doc)');
assert.ok(!html.includes('SECRET') && !html.includes('<img'));
assert.ok(html.includes('&lt;img') && html.includes('href="#block-source"'));
assert.equal((html.match(/class="processing-panel"/g)||[]).length,1);
assert.ok(html.includes('class="nested-record"') && html.indexOf('Wait.') < html.indexOf('Here.'));
assert.ok(html.includes('// RECORD ENDS //'));
context.authored = {biography_document:{blocks:[{type:'paragraph',text:'Generated replacement'}]}};
assert.ok(run("narrative('Authored original','player_authored',[],authored)").includes('Authored original'));
assert.ok(!run("narrative('Authored original','player_authored',[],authored)").includes('Generated replacement'));
console.log('ok (date conversion, DST, semantic blocks, redactions, escaping, nesting, anchors, authorship)');
