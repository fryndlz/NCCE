// Offline handoff workbook only. Does not contact Google, NCCE or a model.
import fs from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.resolve(process.argv[2] || path.join(root, 'outputs/writing-exchange-2026-11-04'));
await fs.mkdir(out, {recursive:true});
const require = createRequire(path.join(out,'package.json'));
const { Workbook, SpreadsheetFile } = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const manifestPath = path.join(out, 'exchange-manifest.json');
let manifest;
try { manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8')); }
catch (e) {
  if (e.code !== 'ENOENT') throw e;
  manifest = {schema_version:1, workbook_id:randomUUID(), created_at:new Date().toISOString(), request_ids:Array.from({length:20},()=>randomUUID())};
  await fs.writeFile(manifestPath, JSON.stringify(manifest,null,2)+'\n');
}
if (manifest.request_ids.length!==20 || new Set(manifest.request_ids).size!==20) throw Error('Invalid reserved request identities');
const source = await fs.readFile(path.join(root,'src/prose_progress.py'),'utf8');
const forms = [...source.matchAll(/^    \('([^']+)','([^']+)','([^']+)','([^']+)'\),/gm)].map(m=>m.slice(1));
if(forms.length!==16) throw Error('Expected the 16 current prose categories');
const statuses=['DRAFT','PENDING','WRITING','READY','IMPORTED','HOLD'];
const wb=Workbook.create();
const q=wb.worksheets.add('Queue'), c=wb.worksheets.add('Context'), f=wb.worksheets.add('Forms'), g=wb.worksheets.add('Guide');
const ink='#26352D', header='#31453A', soft='#EDF1EC', input='#FFF4D6', writer='#E7F1FA';
function base(s,range,title){
  s.showGridLines=false;
  s.getRange(range).format={font:{name:'Arial',size:10,color:ink},verticalAlignment:'center',rowHeight:26};
  s.getRange('A2').values=[[title]];
  s.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:ink};
}
function head(s,range,labels){
  s.getRange(range).values=[labels];
  s.getRange(range).format={fill:header,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:34,horizontalAlignment:'center',verticalAlignment:'center'};
}
base(q,'A1:P25','NCCE writing queue');
const headers=['request_id','status','form','entity_type','entity_key','entry_key','title','context_id','source_revision','event_at_utc','imperial_date','writer_text_md','writer_note','completed_at_utc','imported_at_utc','import_receipt'];
head(q,'A5:P5',headers);
q.getRange('A6:P25').values=manifest.request_ids.map(id=>[id,'DRAFT',...Array(14).fill('')]);
q.getRange('A6:A25').format.fill=soft;
q.getRange('B6:K25').format.fill=input;
q.getRange('L6:N25').format.fill=writer;
q.getRange('O6:P25').format.fill=soft;
q.getRange('A6:A25').setNumberFormat('@');
q.getRange('E6:P25').setNumberFormat('@');
const widths=[40,13,26,16,42,34,36,24,25,25,22,90,45,28,28,38];
widths.forEach((n,i)=>q.getRangeByIndexes(0,i,25,1).format.columnWidth=n);
q.getRange('A3:F3').values=[['Pending',null,'Ready',null,'Imported',null]];
for (const [cell,status] of [['B3','PENDING'],['D3','READY'],['F3','IMPORTED']])q.getRange(cell).formulas=[[`=COUNTIFS($C$6:$C$25,"<>",$B$6:$B$25,"${status}")`]];
q.getRange('H3').values=[['20 unused IDs. Drafts do not start writing.']];
q.getRange('H3:L3').format.font={name:'Arial',size:10,italic:true,color:'#58685F'};
q.getRange('B6:B25').dataValidation={rule:{type:'list',values:statuses}};
q.getRange('C6:C25').dataValidation={rule:{type:'list',formula1:'Forms!$A$6:$A$21'}};
q.getRange('D6:D25').dataValidation={rule:{type:'list',values:['fighter','gang','territory','battle','campaign','relationship']}};
for(const [status,fill] of [['PENDING','#FFF0C2'],['WRITING','#E5ECFA'],['READY','#DDEEDC'],['HOLD','#F9DDDA']])q.getRange('B6:B25').conditionalFormats.add('cellIs',{operator:'equal',formula:`"${status}"`,format:{fill}});
q.getRange('A6:A25').conditionalFormats.add('duplicateValues',{format:{fill:'#F9DDDA',font:{bold:true,color:'#9A2222'}}});
q.tables.add('A5:P25',true,'WritingQueue');
q.freezePanes.freezeRows(5);q.freezePanes.freezeColumns(2);q.tabColor=header;

base(c,'A1:G34','Frozen writing context');
head(c,'A5:G5',['context_id','section','provenance','source_ref','event_at_utc','source_event_ids','text']);
c.getRange('A6:G25').format.fill=input;
c.getRange('A6:G25').setNumberFormat('@');
[25,24,23,56,27,44,95].forEach((n,i)=>c.getRangeByIndexes(0,i,34,1).format.columnWidth=n);
c.getRange('C6:C25').dataValidation={rule:{type:'list',values:['mechanical_fact','player_authored','canon_authored','inference','connective_fiction','reference','instruction']}};
c.getRange('B6:B25').dataValidation={rule:{type:'list',values:['brief','mechanics','authored_canon','rules','chronology','existing_fiction','character_context']}};
c.getRange('A3').values=[['One packet may span several rows. Match context_id exactly; never select context by row number.']];
c.getRange('F28').values=[['Source directory (links only)']];
c.getRange('F28').format.font={name:'Arial',size:10,bold:true};
c.getRange('F30:G32').values=[
 ['Krakamunda: mechanical authority','https://docs.google.com/spreadsheets/d/1Ofh1kDys_xp4a-idPc1NA2I1GCqndbVGjxenatezh00/edit'],
 ['C-NINE: scoped authored canon','https://docs.google.com/document/d/1vAajSzxjaKXjAQ571gcTeM5ocqSVccUS1pljDR_Ysk4/edit'],
 ['Rulebooks','Add the verified book / edition / page and relevant excerpt for each real request.']
];
c.getRange('F30:G32').format.wrapText=true;
c.getRange('F30:G32').format.rowHeight=42;
c.tables.add('A5:G25',true,'WritingContext');c.freezePanes.freezeRows(5);

base(f,'A1:E21','Prose forms');
head(f,'A5:E5',['form','section','display_name','purpose','generation_policy']);
f.getRange('A6:E21').values=forms.map(row=>[...row,row[0]==='gang_origin'?'Authored-only; do not queue generation.':'Only an explicitly requested, missing or revised entry.']);
[27,17,25,68,67].forEach((n,i)=>f.getRangeByIndexes(0,i,21,1).format.columnWidth=n);
f.getRange('D6:E21').format.wrapText=true;f.getRange('A6:E21').format.rowHeight=44;
f.tables.add('A5:E21',true,'ProseForms');f.freezePanes.freezeRows(5);

const guide=[
 ['Current state','Framework only. No automatic campaign export, writing, app import or publishing is connected.'],
 ['When you are back','Upload this workbook to Drive, open with Google Sheets, then save as a native Google Sheet. Keep one working copy separate from Krakamunda.'],
 ['Give the chat','Paste WRITING_CHAT_INSTRUCTIONS.md into your existing writing Project chat. Supply the new Sheet URL. First ask for the read/write capability check only.'],
 ['First real test','Ask Codex to prepare ONE real request and its Context packet. After checking it, change that row to PENDING and ask the writing chat for that request_id.'],
 ['If tools cannot edit','The chat returns the JSON handoff from its instructions. Transfer the finished text into the matching row; do not generate it again.'],
 ['Colours','Grey: immutable IDs / future import receipt. Pale amber: request preparation. Pale blue: writer output. Colours are guidance, not access protection.'],
 ['DRAFT','Unprepared or unapproved. All twenty reserved request IDs start here. A blank form means no actual entry has been requested.'],
 ['PENDING','Coordinator has verified identity, form, evidence, chronology and source revision. The authorized writer may claim this work.'],
 ['WRITING','One writer has claimed it. Do not retry blindly after interruption; inspect for already written text first.'],
 ['READY','Complete text is saved. This does not mean it is published or authored canon.'],
 ['IMPORTED','Future importer has committed the app record and stored a receipt. The writer never sets this status.'],
 ['HOLD','Missing context, identity issue, save problem or uncertain completion. Preserve any text and explain in writer_note.'],
 ['IDs and sorting','request_id identifies the work; entity_key identifies its subject; entry_key identifies the intended entry. Never use a row number or name alone. Sort whole rows.'],
 ['Context and revisions','Join all Context rows by context_id. Freeze source_revision before PENDING. Changed evidence requires a new packet revision and new request ID.'],
 ['Dates','event_at_utc is known occurrence time in ISO 8601 UTC text; unknown stays blank. imperial_date must be supplied by NCCE. Never turn scrape time into occurrence time.'],
 ['One entry, one writing','No automatic alternatives or reviewer selection. Save complete prose, even if delivery is interrupted. Revisions require an explicit new request and preserve the old draft.'],
 ['Authored content','Player-authored text supersedes generated inference. Gang backstories remain authored-only. No replacement of authored prose is requested by this workbook.'],
 ['Complete composition','writer_text_md holds the whole formatted document: headings, metadata, paragraphs and sign-off when appropriate. Technical notes stay outside the prose.'],
 ['Rulebook context','Use relevant verified territory/faction rules, with edition/page or URL, in Context. A link alone does not mean the chat has read the book.'],
 ['Who prepares requests','Codex prepares the source identities and context until an NCCE exporter exists. You do not need to invent fighter IDs or fill the technical fields yourself.'],
 ['Next integration','NCCE still needs an exporter and importer. A READY entry will not appear in the app until that bridge is implemented and tested.'],
 ['Workbook identity',manifest.workbook_id],
 ['Prepared UTC',new Date(manifest.created_at)]
];
base(g,'A1:B28','Writing exchange guide');head(g,'A5:B5',['Item','Instructions']);
g.getRange(`A6:B${5+guide.length}`).values=guide;
g.getRange('A1:A28').format.columnWidth=26;g.getRange('B1:B28').format.columnWidth=108;
g.getRange('A6:A28').format.font={name:'Arial',size:10,bold:true,color:ink};
g.getRange('A6:B28').format.wrapText=true;g.getRange('A6:B28').format.rowHeight=48;
g.getRange('B28').setNumberFormat('yyyy-mm-dd hh:mm:ss "UTC"');
g.tabColor='#89958B';

// Scenario proof: counts ignore unused ID rows and update on actual request transitions.
function counts(){return ['B3','D3','F3'].map(x=>q.getRange(x).values[0][0]);}
q.getRange('C6').values=[['fighter_memory']];q.getRange('B6').values=[['PENDING']];wb.recalculate();
if(JSON.stringify(counts())!=='[1,0,0]')throw Error('Pending count failed '+JSON.stringify(counts()));
q.getRange('B6').values=[['READY']];wb.recalculate();
if(JSON.stringify(counts())!=='[0,1,0]')throw Error('Ready count failed');
q.getRange('B6').values=[['IMPORTED']];wb.recalculate();
if(JSON.stringify(counts())!=='[0,0,1]')throw Error('Imported count failed');
q.getRange('B6').values=[['DRAFT']];q.getRange('C6').values=[['']];wb.recalculate();
if(JSON.stringify(counts())!=='[0,0,0]')throw Error('Reset failed');
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!',options:{useRegex:true,maxResults:10},maxChars:1500});
await fs.writeFile(path.join(out,'verification.json'),JSON.stringify({reserved_ids:20,categories:forms.length,counts:counts(),formula_scan:errors.ndjson},null,2));
for(const [sheetName,range,name] of [['Queue','A1:F12','queue-inputs'],['Queue','G4:P10','queue-output'],['Context','A1:G12','context'],['Context','F28:G32','sources'],['Forms','A1:E21','forms'],['Guide','A1:B28','guide']]){
  const image=await wb.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(path.join(out,`${name}.png`),new Uint8Array(await image.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(out,'NCCE-Writing-Exchange.xlsx'));
await fs.copyFile(path.join(root,'docs/WRITING_CHAT_INSTRUCTIONS.md'),path.join(out,'WRITING_CHAT_INSTRUCTIONS.md'));
console.log(JSON.stringify({file:path.join(out,'NCCE-Writing-Exchange.xlsx'),categories:forms.length,reserved_ids:20,counts:counts()}));
