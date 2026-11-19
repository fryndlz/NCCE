/** Autonomous bulk writer, opt-in: configure NCCE_BULK_WRITER_API_KEY and
 * NCCE_BULK_WRITER_ENABLED=true in Script Properties. Never used by normal Queue.
 * This is a model-backed worker; the NCCE relay alone cannot generate prose.
 * External API use/cost and transfer of sealed context require owner consent.
 */
const BULK_WRITER_MODEL = 'gpt-4.1';
const BULK_WRITER_BATCH = 2;
const BULK_WRITER_MAX_ATTEMPTS = 2;

function bulkWriterProps() { return PropertiesService.getScriptProperties(); }
function bulkWriterEnabled() {
  const p=bulkWriterProps();
  return p.getProperty('NCCE_BULK_WRITER_ENABLED')==='true' &&
    !!p.getProperty('NCCE_BULK_WRITER_API_KEY');
}
function bulkWriterNormalize(s) {
  return String(s||'').normalize('NFKC').toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();
}
function bulkWriterTitle(md) {
  const first=String(md||'').split(/\r?\n/).find(s=>s.trim())||'';
  return first.replace(/^#+\s*/,'').replace(/^\*\*(.*)\*\*$/,'$1').trim();
}
function bulkWriterIdentity(blocks) {
  const person=blocks.find(b=>b.section==='character_context');
  let name='';
  if(person) { try { name=JSON.parse(person.text).subject_name||''; } catch(e) {} }
  const tokens=new Set();
  const add=s=>{ const n=bulkWriterNormalize(s); if(n.length>=3)tokens.add(n); };
  add(name);
  name.replace(/[„“"]([^”"“]+)[”"]/g,(_,alias)=>{add(alias);return '';})
    .split(/[\s,]+/).forEach(add);
  return [...tokens];
}
function bulkWriterValidate(row,md,blocks) {
  const errors=[];
  if(typeof md!=='string'||!md.trim())return ['Missing prose'];
  if(md.length>=30000)errors.push('Over 30000 characters');
  if(!/^\*\*[^\n*]+\*\*\s*\n\s*\n[\s\S]+/.test(md))
    errors.push('Use **TITLE** then a blank line and complete prose');
  if(row[2]==='fighter_memory') {
    if([...md].length>350)errors.push('Memory exceeds 350 Unicode characters including Markdown');
    const title=bulkWriterNormalize(bulkWriterTitle(md));
    for(const part of bulkWriterIdentity(blocks)) {
      if((' '+title+' ').includes(' '+part+' '))errors.push('Title contains fighter name or alias: '+part);
    }
  } else if(row[2]==='fighter_reflection') {
    const words=md.trim().split(/\s+/).length;
    if(words<60||words>130)errors.push('Reflection must be 60–130 words');
  } else errors.push('Unsupported bulk form');
  if(/\b(?:as an ai|language model|here is your)\b/i.test(md))errors.push('Model meta-commentary');
  return [...new Set(errors)];
}
function bulkWriterContext(book,id) {
  const sheet=book.getSheetByName('Bulk Context');
  const data=bulkRows(sheet,7).filter(r=>r[0]===id);
  if(!data.length)throw new Error('Missing sealed context '+id);
  const blocks=[];
  for(const r of data) {
    const prev=blocks[blocks.length-1];
    if(prev&&prev.section===r[1]&&prev.provenance===r[2]&&prev.source_ref===r[3])prev.text+=r[6];
    else blocks.push({section:r[1],provenance:r[2],source_ref:r[3],text:r[6]});
  }
  if(!blocks.some(b=>b.section==='mechanics')||!blocks.some(b=>b.section==='character_context'))
    throw new Error('Incomplete sealed context '+id);
  return blocks;
}
function bulkWriterGuidance(book) {
  return ['Writer instructions','Writer skill','Voice identity'].map(name=>{
    const s=book.getSheetByName(name);
    if(!s)return '';
    return name+'\n'+bulkRows(s,Math.min(s.getLastColumn(),3))
      .map(r=>r.filter(Boolean).join(' | ')).join('\n');
  }).join('\n\n').slice(0,55000);
}
function bulkWriterCall(messages) {
  const p=bulkWriterProps(),key=p.getProperty('NCCE_BULK_WRITER_API_KEY');
  if(!key)throw new Error('Missing autonomous writer API key');
  const model=p.getProperty('NCCE_BULK_WRITER_MODEL')||BULK_WRITER_MODEL;
  const response=UrlFetchApp.fetch('https://api.openai.com/v1/chat/completions',{
    method:'post',contentType:'application/json',
    headers:{Authorization:'Bearer '+key},
    payload:JSON.stringify({model,messages,temperature:0.6,max_completion_tokens:1600}),
    muteHttpExceptions:true
  });
  if(response.getResponseCode()!==200)
    throw new Error('Writer API HTTP '+response.getResponseCode());
  const parsed=JSON.parse(response.getContentText());
  const content=parsed.choices?.[0]?.message?.content;
  if(typeof content!=='string'||!content.trim())throw new Error('Writer returned no prose');
  return content.trim();
}
function bulkWriterReview(md,row,blocks,guidance) {
  const answer=bulkWriterCall([
    {role:'system',content:'You are a strict independent literary and factual QA editor. Return only JSON with keys pass (boolean), issues (array of short strings). Reject invented mechanics, unsupported attendance, GM-only leaks, contradictions, weak character voice, wrong form or any breach of the supplied writing rules. Do not rewrite the text.'},
    {role:'user',content:JSON.stringify({form:row[2],source_revision:row[8],
      sealed_context:blocks,writing_rules:guidance,draft:md})}
  ]);
  try {
    const parsed=JSON.parse(answer.replace(/^\`\`\`(?:json)?\s*|\s*\`\`\`$/g,''));
    if(parsed.pass===true&&Array.isArray(parsed.issues)&&!parsed.issues.length)return [];
    return Array.isArray(parsed.issues)&&parsed.issues.length?parsed.issues:['Independent QA did not pass'];
  } catch(e) { return ['Independent QA did not return valid JSON']; }
}
function bulkWriterDraft(row,blocks,guidance,prior,issues) {
  return bulkWriterCall([
    {role:'system',content:'Write the final diegetic Necromunda prose only, with **NAME-FREE TITLE** and blank line. You are the commissioned NCCE writer. Obey every sealed instruction and all factual constraints. Do not invent battle attendance, injury causes, or GM-only secrets. For fighter_memory use at most 350 Unicode characters including Markdown; for fighter_reflection use 60–130 words. Do not put the subject name or alias in a fighter_memory title.'},
    {role:'user',content:JSON.stringify({request:{id:row[0],form:row[2],entity_key:row[4],
      title_hint:row[6],source_revision:row[8],context_id:row[7]},
      sealed_context:blocks,writing_rules:guidance,
      previous_draft:prior||null,required_fixes:issues||[]})}
  ]);
}
/** Each tick does bounded work, preserves immutable identity, and retries until
 * deterministic + independent editorial QA pass. It never revises IMPORTED.
 */
function runAutonomousBulkWriter(book) {
  if(!bulkWriterEnabled())return;
  const jobs=book.getSheetByName('Bulk Jobs'),sheet=book.getSheetByName('Bulk Items');
  if(!jobs||!sheet)return;
  const active=new Set(bulkRows(jobs,10).filter(r=>r[1]==='ACTIVE').map(r=>r[0]));
  const rows=bulkRows(sheet,18);
  const guidance=bulkWriterGuidance(book);
  let completed=0;
  for(let i=0;i<rows.length&&completed<BULK_WRITER_BATCH;i++) {
    const row=rows[i];
    if(!active.has(row[16])||row[1]!=='PENDING'||!row[7]||!row[8]||row[11])continue;
    const sheetRow=i+2,originalId=row[0],revision=row[8];
    const blocks=bulkWriterContext(book,row[7]);
    writeLiteral(sheet.getRange(sheetRow,2),[['WRITING']]);
    let draft='',issues=[];
    try {
      for(let attempt=1;attempt<=BULK_WRITER_MAX_ATTEMPTS;attempt++) {
        draft=bulkWriterDraft(row,blocks,guidance,draft,issues);
        issues=bulkWriterValidate(row,draft,blocks);
        if(!issues.length)issues=bulkWriterReview(draft,row,blocks,guidance);
        if(!issues.length)break;
      }
      const current=sheet.getRange(sheetRow,1,1,18).getDisplayValues()[0];
      if(current[0]!==originalId||current[8]!==revision||current[1]!=='WRITING'||current[11])
        throw new Error('Writer claim or source changed; no overwrite');
      if(issues.length) {
        writeLiteral(sheet.getRange(sheetRow,13),[['QA FAILED: '+issues.join('; ').slice(0,900)]]);
        writeLiteral(sheet.getRange(sheetRow,2),[['PENDING']]);
        bulkAudit(book,row[16],originalId,'WRITER_RETRY','PENDING','',issues.join('; '));
      } else {
        writeLiteral(sheet.getRange(sheetRow,12,1,3),[[draft,
          'QA PASS: deterministic checks and independent editorial review',new Date().toISOString()]]);
        SpreadsheetApp.flush();
        const saved=sheet.getRange(sheetRow,1,1,18).getDisplayValues()[0];
        if(saved[0]!==originalId||saved[8]!==revision||saved[11]!==draft||
           bulkWriterValidate(row,saved[11],blocks).length)
          throw new Error('Saved draft failed read-back verification');
        writeLiteral(sheet.getRange(sheetRow,2),[['READY']]);
        bulkAudit(book,row[16],originalId,'WRITER_QA','READY','','All checks passed');
      }
    } catch(e) {
      const current=sheet.getRange(sheetRow,1,1,18).getDisplayValues()[0];
      if(current[0]===originalId&&current[1]==='WRITING'&&!current[11]) {
        writeLiteral(sheet.getRange(sheetRow,13),[['WRITER ERROR: '+String(e.message).slice(0,700)]]);
        writeLiteral(sheet.getRange(sheetRow,2),[['PENDING']]);
      }
      bulkAudit(book,row[16],originalId,'WRITER_ERROR','PENDING','',String(e.message));
    }
    completed++;
  }
}
