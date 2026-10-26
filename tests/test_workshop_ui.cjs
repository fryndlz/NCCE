const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const callbacks={},timers=[],calls=[];
const root={dataset:{},innerHTML:'',addEventListener:(name,fn)=>{callbacks[name]=fn;},querySelector(selector){if(selector==='.writer-workshop')return this.innerHTML.includes('writer-workshop')?{}:null;if(selector==='#ws-edited-preview')return this.preview ||= {innerHTML:''};return null;}};
const escaped=s=>String(s).replaceAll('<','&lt;').replaceAll('>','&gt;');
const bodyDoc={blocks:[{type:'body_paragraph',text:'Original sample'}],composition:{}};
const home={model:'same-model',effort:'low',configured:true,review:[],samples:[{key:'test',form:'fighter_memory',label:'Mara'}],trials:[]};
const sample={key:'test',form:'fighter_memory',label:'Mara',packet:{evidence:['Critical Injury']},document:bodyDoc};
let ids=0;
async function api(url,options){
  calls.push([url,options]);
  if(url==='/api/workshop')return home;
  if(url.startsWith('/api/workshop/policy')){const scope=url.includes('shared')?'shared':'fighter_memory';return {draft:{scope,label:'Current',instructions:'Some <unsafe> instructions',examples:'Example'},active:null,history:[],builtin:{},candidate:{}};}
  if(url.startsWith('/api/workshop/sample'))return sample;
  const data=options?.body?JSON.parse(options.body):{};
  if(url.endsWith('save-policy'))return {...data,revision_id:'r'+(++ids)};
  if(url.endsWith('preview'))return {...sample,instructions:'Exact inspected instructions'};
  if(url.endsWith('generate'))return {trial_id:'once',status:'queued',form:'fighter_memory',label:'Mara',document:{},edits:[],packet:sample.packet,usage:{},instructions:'Saved instructions'};
  if(url.includes('/trial?'))return {trial_id:'once',status:'ready',form:'fighter_memory',label:'Mara',document:bodyDoc,edits:[],packet:sample.packet,usage:{requests_attempted:1,input_tokens:100},instructions:'Saved instructions'};
  throw new Error('Unexpected request '+url);
}
const context={window:{},console,setTimeout:fn=>timers.push(fn),crypto:{randomUUID:()=> 'same-request-key'}};
vm.createContext(context);vm.runInContext(fs.readFileSync('web/workshop.js','utf8'),context);
function click(action){const button={dataset:{ws:action},disabled:false};callbacks.click({target:{closest:()=>button}});}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await context.window.NCCEWorkshop.open(root,api,doc=>escaped(JSON.stringify(doc)));
  assert.equal(calls.filter(c=>c[1]?.method==='POST').length,0,'Opening must not write or spend');
  assert.match(root.innerHTML,/Generate one draft/);assert.ok(!root.innerHTML.includes('<unsafe>'));
  click('inspect');await settle();
  assert.match(root.innerHTML,/Exact inspected instructions/);
  assert.equal(calls.filter(c=>c[0].endsWith('/generate')).length,0,'Inspection is free');
  click('generate');click('generate');await settle();
  assert.equal(calls.filter(c=>c[0].endsWith('/generate')).length,1,'Double click must send one generation');
  await timers.shift()();await settle();
  assert.match(root.innerHTML,/100 input/);
  callbacks.input({target:{dataset:{},value:'<img src=x onerror=bad()>',hasAttribute:name=>name==='data-ws-body'}});
  assert.ok(!root.preview.innerHTML.includes('<img'),'Edited preview must escape prose');
  console.log('Workshop UI passed: free opening/inspection, escaping, one-call double-click protection, completion rendering');
})().catch(error=>{console.error(error);process.exitCode=1;});
