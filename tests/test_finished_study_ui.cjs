const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('web/workshop.js','utf8');
const instructions='Write 70–100 words. Keep the territory function, narrator and factual limits. Closing may be empty. <saved & exact>';
const run={run_id:'closed-study',form:'territory_origin',status:'finished',workflow_version:3,
  specific:{revision_id:'saved-category',instructions,examples:'Example is illustrative, never canon.'},
  shared:{revision_id:'saved-shared',instructions:'Preserve source hierarchy and viewpoint.'},
  rounds:[{number:1,pairs:[{label:'A territory',candidates:[],review:{summary:'Saved',candidates:[]},owner_verdict:{preference:'neither'}}]}]};

async function harness(saved=structuredClone(run)){
  const handlers={},calls=[],timers=[];let confirms=0,allow=false;
  const root={dataset:{},innerHTML:'',addEventListener:(k,v)=>handlers[k]=v,querySelector(selector){return selector==='.writer-workshop'?{}:null;}};
  const context={window:{confirm:()=>{confirms++;return allow;}},console,crypto:{randomUUID:()=> 'new-approved-request'},setTimeout:f=>timers.push(f)};
  vm.createContext(context);vm.runInContext(source,context);
  async function api(url,options){
    calls.push([url,options]);
    if(url==='/api/workshop')return {configured:true,forms:['territory_origin','fighter_memory'],samples:[{key:'territory',form:'territory_origin'},{key:'fighter',form:'fighter_memory'}]};
    if(url==='/api/workshop/optimizations')return {configuration:{},bridge:{online:true},runs:[saved]};
    if(url.startsWith('/api/workshop/quality'))return {suggested_instructions:'DEFAULT, NOT SAVED',calibration:{message:'Advisory',fresh_pairs:0,agreements:0},contract:{rules:[],historical_examples:[],limitations:[]}};
    if(url.startsWith('/api/workshop/guidelines?'))return {scope:'territory_origin',timeline:[],active:{instructions:'Active'},history_limit:40};
    if(url.startsWith('/api/workshop/sample?'))return {key:'territory',packet_hash:'current-source'};
    if(url.startsWith('/api/workshop/policy?'))return {active:{revision_id:'different-current-shared'}};
    if(url.endsWith('/save-policy'))return {revision_id:'edited-category'};
    if(url.endsWith('/optimize'))return {run_id:'new-study',status:'queued',form:'territory_origin',rounds:[]};
    throw Error('Unexpected request '+url);
  }
  await context.window.NCCEWorkshop.open(root,api,()=> 'Saved prose');
  const settle=()=>new Promise(r=>setImmediate(r));
  const click=async ws=>{handlers.click({target:{closest:()=>({dataset:{ws}})},preventDefault(){},stopPropagation(){}});await settle();};
  const posts=()=>calls.filter(([,o])=>o?.method==='POST');
  return {root,calls,timers,click,posts,confirms:()=>confirms,allow:v=>allow=v,
    edit:async(value)=>{handlers.input({target:{value,hasAttribute:n=>n==='data-ws-candidate'}});await settle();},
    changeForm:async(value)=>{handlers.change({target:{value,hasAttribute:n=>n==='data-ws-opt-form'}});await settle();}};
}

(async()=>{
  const original=JSON.stringify(run),h=await harness(run);
  assert.match(h.root.innerHTML,/Study finished · results saved/);
  assert.doesNotMatch(h.root.innerHTML,/The writing loop is paused/);
  await h.click('opt-prepare-saved');
  assert.match(h.root.innerHTML,/&lt;saved &amp; exact&gt;/);
  assert.match(h.root.innerHTML,/Preparing is free/);
  assert.match(h.root.innerHTML,/4 writing calls and 2 pair reviews/);
  assert.equal(h.posts().length,0);assert.equal(h.timers.length,0);assert.equal(h.confirms(),0);
  assert.equal(JSON.stringify(run),original,'Preparing must not change finished audit or owner ratings');
  await h.click('opt-start');
  assert.equal(h.confirms(),1);assert.equal(h.posts().length,0,'Declining test must not save a policy or queue work');
  h.allow(true);await h.click('opt-start');
  assert.equal(h.posts().length,1);
  const [url,options]=h.posts()[0],body=JSON.parse(options.body);
  assert.ok(url.endsWith('/optimize'));assert.equal(body.form_revision_id,'saved-category');
  assert.equal(body.shared_revision_id,'saved-shared');assert.equal(body.allow_paid,true);assert.equal(body.max_rounds,1);
  assert.equal(JSON.stringify(run),original);

  const changed=await harness();await changed.click('opt-prepare-saved');await changed.edit(instructions+' A deliberate edit.');changed.allow(true);await changed.click('opt-start');
  const edited=changed.posts().find(([url])=>url.endsWith('/save-policy'));
  assert.equal(JSON.parse(edited[1].body).examples,run.specific.examples,'Editing guidance retains its example boundary');
  assert.equal(JSON.parse(changed.posts().at(-1)[1].body).form_revision_id,'edited-category','Edits must not silently reuse the original revision');

  const hidden=structuredClone(run);hidden.specific={instructions:'Hidden until blind verdicts are sealed.'};hidden.shared={instructions:'Hidden'};
  hidden.rounds[0].pairs[0]={label:'Unrated',candidates:[],review:null,review_pending_reveal:true};
  const blind=await harness(hidden);
  assert.match(blind.root.innerHTML,/data-ws="opt-prepare-saved" disabled/);
  assert.match(blind.root.innerHTML,/Rate the remaining draft pair/);
  await blind.click('opt-prepare-saved');assert.equal(blind.posts().length,0);
  assert.doesNotMatch(blind.root.innerHTML,/&lt;saved &amp; exact&gt;/);

  const switched=await harness();await switched.click('opt-prepare-saved');await switched.changeForm('fighter_memory');
  assert.doesNotMatch(switched.root.innerHTML,/&lt;saved &amp; exact&gt;/,'Another category must not inherit prepared guidance');
  console.log('PASS finished-study preparation: exact saved revisions, zero-call preparation, blind guard, editing and confirmation gates');
})().catch(e=>{console.error(e);process.exitCode=1;});
