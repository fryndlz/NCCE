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
context.maraText = `KEL, Mara\nDesignation: Maintenance Fitter\nLabour Grade: General Crewman\nMedical Category: Hereditary Deep-Work Variant α\nResponsible for maintenance of drilling apparatus.\n\nWorkshop Audit — 781.M41\nSix machines returned to service.\n\n“They’re not twenty-nine machines. It’s one workshop.”\n\nC9-MK/a4d4\n\n[SYS.██] RECORD TERMINATED`;
context.mara = {backstory_source:'player-authored / C-NINE story'};
const dossier = run('narrative(maraText,mara.backstory_source,[],mara)');
assert.ok(dossier.includes('class="personnel-fields"') && dossier.includes('Maintenance Fitter'));
assert.ok(dossier.includes('personnel-section-label') && dossier.includes('Workshop Audit'));
assert.ok(dossier.includes('personnel-quote') && dossier.includes('It’s one workshop'));
assert.ok(dossier.includes('personnel-watermark') && dossier.includes('C9-MK/a4d4'));
assert.ok(dossier.includes('personnel-system') && dossier.includes('RECORD TERMINATED'));
assert.ok(app.includes('Test the writer on Mara') && app.includes('at most 13 model requests'));
assert.ok(app.includes('writer-ledger') && app.includes('r.request_id') && app.includes('r.response_id'));
assert.ok(app.includes("/api/writer-runs/mara-latest") && app.includes('writerRunMarkup(run)'));
assert.ok(app.includes('of 13 model requests attempted so far') && app.includes('innerHTML=writerRunMarkup(run)'));
const server = fs.readFileSync('src/server.py','utf8');
assert.ok(server.includes("p=='/api/writer-runs/mara-latest'") && server.includes('requests_attempted'));
console.log('ok (date conversion, DST, semantic blocks, redactions, escaping, authorship precedence, formatted dossier, persistent Mara result and live usage ledger)');
