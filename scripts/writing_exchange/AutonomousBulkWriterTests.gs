/** Run testAutonomousBulkWriterValidation() manually in Apps Script.
 * No model calls, no NCCE writes, no Sheet writes.
 */
function testAutonomousBulkWriterValidation() {
  const person=[{section:'character_context',
    text:JSON.stringify({subject_name:'Severus „Bezlitosny”'})},
    {section:'mechanics',text:'{}'}];
  const memory=['id','PENDING','fighter_memory'];
  const reflection=['id','PENDING','fighter_reflection'];
  const good='**THE LAST SHIFT**\n\nThe gate stayed closed. I counted the lamps, and kept my place.';
  const cases=[
    [memory,good,true],
    [memory,'**SEVERUS // THE LAST SHIFT**\n\nA report.',false],
    [memory,'**BEZLITOSNY // THE LAST SHIFT**\n\nA report.',false],
    [memory,'**THE LAST SHIFT**\n\n'+'A'.repeat(350),false],
    [reflection,'**AFTERWARD**\n\n'+('I watched the gate and waited for another order. '.repeat(9)),true],
    [reflection,good,false]
  ];
  for(let i=0;i<cases.length;i++) {
    const [row,text,expected]=cases[i];
    const actual=bulkWriterValidate(row,text,person).length===0;
    if(actual!==expected)throw new Error('Autonomous writer QA regression case '+i);
  }
  return 'PASS: '+cases.length+' deterministic validation cases';
}
