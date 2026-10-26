// Date and semantic-renderer contracts without a browser or external packages.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({document:{querySelector:()=>({})}, Intl, Date});
vm.runInContext(fs.readFileSync('web/writing.js','utf8'),context);
const app = fs.readFileSync('web/app.js','utf8');
vm.runInContext(app.slice(0,app.indexOf('async function api(')),context);
vm.runInContext(app.slice(app.indexOf('function memoryCard('),app.indexOf('async function showFighter(')),context);
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
assert.ok(app.includes('Test the writer on Mara') && app.includes('Run revised Mara check') && app.includes('Regenerate Mara’s memories') && app.includes('Try Mara at medium effort (5 calls)') && app.includes('at most 5 model requests'));
assert.ok(app.includes('writer-ledger') && app.includes('r.request_id') && app.includes('r.response_id'));
assert.ok(app.includes("/api/writer-runs/mara-latest") && app.includes('writerRunMarkup(run)'));
assert.ok(app.includes('of ${limit} model requests attempted so far') && app.includes('innerHTML=writerRunMarkup(run)'));
assert.ok(app.includes('/api/writer-diagnostic') && app.includes('Ask the writer for one sample') && app.includes('writerDiagnosticMarkup'));
context.profile = {name:'crew / workshop',traits:['practical'],evidence:['Authored maintenance cues'],writer_context:{
  identity:{},inferred_identity:[{label:'Authored work or craft',value:'maintenance fitter',source:'player_authored',basis:'Named in Backstory'}],
  stim_weights:[{topic:'injury',weight:1.3,basis:['voice tendency: enduring']}]
}};
const profile = run('voiceDetails(profile)');
assert.ok(profile.includes('Identity from known sources') && profile.includes('maintenance fitter'));
assert.ok(profile.includes('Stimulus attention weights') && profile.includes('1.30×'));
assert.ok(profile.includes('Player-authored') && profile.includes('They do not change game mechanics'));
context.fighter = {id:7,writer_identity:{}};
const editor = run('identityEditor(fighter)');
assert.ok(editor.includes('inferred from the roster') && editor.includes('Gender and pronouns are never guessed'));
assert.ok(editor.includes('Correct or add an explicitly known detail'));
context.staleMemory = {id:'memory',memory_type:'observation',writer_status:'stale',title:'Condition changed',content:'The hurt makes the next shift uncertain.',evidence:['Status changed']};
assert.ok(run('memoryCard(staleMemory)').includes('Earlier draft retained'));
const server = fs.readFileSync('src/server.py','utf8');
assert.ok(server.includes("p=='/api/writer-runs/mara-latest'") && server.includes('requests_attempted'));
assert.ok(server.includes("p=='/api/writer-diagnostic'") && server.includes("'writer_diagnostic_used'"));
assert.ok(server.includes("'can_final_run':can_final_run") && server.includes("'can_medium_run':can_medium_run") && server.includes("'mara_writer_check_medium_used'") && server.includes("reasoning_effort='medium'"));
assert.equal((server.match(/^import llm_writer$/gm)||[]).length,1,'writer module is imported once at module scope so every API route can read its run summary');
console.log('ok (date conversion, DST, semantic blocks, redactions, escaping, authorship precedence, inferred identity/stims, stale drafts, formatted dossier, persistent Mara result and live usage ledger)');

// New documents keep application dates outside the diegetic header and escape composition.
context.composed={document_type:'survey_note', reference:'NC/PREVIEW/1', writer_status:'ready',
  composition:{heading:'<script>unsafe</script>',subject:'An assessment'},
  date_display:{imperialDisplay:'9.815.998.M41',realDisplay:'25 October 2026'},
  blocks:[{type:'body_paragraph',text:'The doors remain shut.'}]};
const composed=run('blocks(composed)');
assert.match(composed,/record-ui-date[^]*25 October 2026/);
assert.match(composed,/&lt;script&gt;unsafe&lt;\/script&gt;/);
const diegeticHeader=composed.slice(composed.indexOf('<header'),composed.indexOf('</header>'));
assert.match(diegeticHeader,/9\.815\.998\.M41/);
assert.doesNotMatch(diegeticHeader,/2026|District compiler|generated inference/);
context.previewState={'writer_preview:test:claimed':'1','writer_preview:test':JSON.stringify({status:'complete',usage:{requests_attempted:4,cached_input_tokens:100},entries:[{label:'Hypothetical test',document:context.composed}]})};
vm.runInContext(app.slice(app.indexOf('function editorialPreview('),app.indexOf('function captureUi(')),context);
const preview=run('editorialPreview(previewState)');
assert.match(preview,/not been added to campaign history/);
assert.match(preview,/4 requests/);
assert.match(preview,/Hypothetical test/);
assert.doesNotMatch(preview,/<script>/);
