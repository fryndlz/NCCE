const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const callbacks={},timers=[],calls=[];
const root={dataset:{},innerHTML:'',addEventListener:(name,fn)=>{callbacks[name]=fn;},querySelector(selector){if(selector==='.writer-workshop')return this.innerHTML.includes('writer-workshop')?{}:null;if(selector==='#ws-edited-preview')return this.preview ||= {innerHTML:''};return null;}};
const escaped=s=>String(s).replaceAll('<','&lt;').replaceAll('>','&gt;');
const bodyDoc={blocks:[{type:'body_paragraph',text:'Original sample'}],composition:{}};
const home={model:'same-model',effort:'low',configured:true,review:[{label:'Obsolete comparison',note:'Old feedback',versions:{A:'old',B:'old'}}],forms:['fighter_memory','place_ambient'],focus_options:{fighter_memory:[{value:'recorded_event',label:'Recorded event'}],place_ambient:[{value:'economic',label:'Livelihood'},{value:'historical',label:'History'}]},samples:[{key:'test',form:'fighter_memory',label:'Mara'},{key:'territory',form:'place_ambient',label:'Mine'}],trials:[]};
const sample={key:'test',form:'fighter_memory',label:'Mara',packet:{evidence:['Critical Injury']},document:bodyDoc};
const optimization={run_id:'opt-test',form:'fighter_memory',status:'queued',message:'<unsafe>',writer_reserved:0,writer_limit:4,reviewer_reserved:0,reviewer_limit:2,specific:{instructions:'Candidate <unsafe>'},shared:{label:'Shared',instructions:'Protected'},rounds:[],events:[],coverage:'Two source contexts',reviewer_context:'Saved review brief'};
optimization.rounds=[{number:1,pairs:[{label:'Review entry',candidates:[{status:'ready',document:bodyDoc},{status:'ready',document:bodyDoc}],review:{summary:'A complete assessment. '+('Evidence and reasoning. '.repeat(25)),candidates:[0,1].map(index=>({index,overall:6,scores:{factual_fidelity:9,distinctiveness:5},issues:[{category:'context',blocking:true,explanation:'Inspect this context. '+('More explanation. '.repeat(20)),evidence:'Exact <unsafe> evidence'}]}))}}]}];
let ids=0,historyRun=null;
async function api(url,options){
  calls.push([url,options]);
  if(url==='/api/workshop')return home;
  if(url==='/api/workshop/optimizations')return {configuration:{},runs:[]};
  if(url.startsWith('/api/workshop/policy')){const scope=decodeURIComponent(url.split('scope=')[1]);return {draft:{scope,revision_id:scope+'-existing',label:'Current',instructions:'Some <unsafe> instructions',examples:'Example'},active:null,history:[],builtin:{},candidate:{}};}
  if(url.startsWith('/api/workshop/sample'))return url.includes('territory')?{...sample,key:'territory',form:'place_ambient',label:'Mine'}:sample;
  const data=options?.body?JSON.parse(options.body):{};
  if(url.endsWith('save-policy'))return {...data,revision_id:'r'+(++ids)};
  if(url.endsWith('preview'))return {...sample,plan_key:'frozen-plan',packet:{...sample.packet,creative_plan:{focus_label:'Recorded event'}},instructions:'Exact inspected instructions'};
  if(url.endsWith('generate'))return {trial_id:'once',status:'queued',form:'fighter_memory',label:'Mara',document:{},edits:[],packet:sample.packet,usage:{},instructions:'Saved instructions'};
  if(url.endsWith('/optimize'))return optimization;
  if(url.includes('/optimization?'))return historyRun || {...optimization,status:'awaiting_approval'};
  if(url.endsWith('/optimization-continue'))return {...optimization,status:'queued'};
  if(url.endsWith('/optimization-technical-decision'))return {...historyRun,tech:{...historyRun.tech,status:data.action==='approve_repair'?'repair_queued':data.action==='approve_release'?'release_queued':'rejected'}};
  if(url.endsWith('/optimization-decide'))return {...optimization,status:data.approve?'approved':'rejected'};
  if(url.includes('/trial?'))return {trial_id:'once',status:'ready',form:'fighter_memory',label:'Mara',document:bodyDoc,edits:[],packet:sample.packet,usage:{requests_attempted:1,input_tokens:100},instructions:'Saved instructions'};
  throw new Error('Unexpected request '+url);
}
const context={window:{confirm:()=>false},console,setTimeout:fn=>timers.push(fn),crypto:{randomUUID:()=> 'same-request-key'}};
vm.createContext(context);vm.runInContext(fs.readFileSync('web/workshop.js','utf8'),context);
function click(action){const button={dataset:{ws:action},disabled:false};callbacks.click({target:{closest:()=>button}});}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await context.window.NCCEWorkshop.open(root,api,doc=>escaped(JSON.stringify(doc)));
  assert.equal(calls.filter(c=>c[1]?.method==='POST').length,0,'Opening must not write or spend');
  assert.match(root.innerHTML,/Improve a whole prose category/);
  click('opt-start');await settle();
  assert.equal(calls.filter(c=>c[0].endsWith('/optimize')).length,0,'Declining paid optimization must not queue it');
  for(const legacy of ['Generate one draft','Find an entry','Shared writing craft','Workshop samples','Complete study report','Your comparison feedback','Obsolete comparison'])assert.ok(!root.innerHTML.includes(legacy),legacy+' must be absent');
  assert.ok(!root.innerHTML.includes('<unsafe>'));
  assert.match(root.innerHTML,/data-ws-opt-form/);
  callbacks.change({target:{dataset:{},value:'place_ambient',hasAttribute:name=>name==='data-ws-opt-form'}});
  assert.match(root.innerHTML,/Start territory scenes study/);

  context.window.confirm=()=>true;
  click('opt-start');click('opt-start');await settle();
  assert.equal(calls.filter(c=>c[0].endsWith('/optimize')).length,1,'Double click must authorize only one bounded run');
  const optBody=JSON.parse(calls.find(c=>c[0].endsWith('/optimize'))[1].body);
  assert.equal(optBody.allow_paid,true);assert.equal(optBody.max_rounds,1);
  assert.equal(optBody.sample_key,'territory','Improvement must use the selected prose type, not the manual sample');
  assert.equal(optBody.shared_revision_id,'shared-existing');assert.equal(optBody.form_revision_id,'place_ambient-existing');
  assert.equal(calls.filter(c=>c[0].endsWith('/save-policy')).length,0,'Starting a study must preserve existing saved guidance');
  assert.equal(optBody.focus,'auto');assert.equal(optBody.plan_key,null);
  assert.match(root.innerHTML,/ws-draft-grid/);assert.match(root.innerHTML,/ws-score-list/);
  assert.match(root.innerHTML,/Full assessment/);assert.match(root.innerHTML,/Exact &lt;unsafe&gt; evidence/);
  assert.match(root.innerHTML,/context · blocking/);
  assert.ok(!root.innerHTML.includes('<unsafe>'));
  // A native dropdown/editor keeps its DOM while a poll result arrives.
  const selectedControl={matches:()=>true};context.document={activeElement:selectedControl};root.contains=node=>node===selectedControl;
  const stableMarkup=root.innerHTML;
  await timers.shift()();await settle();assert.equal(root.innerHTML,stableMarkup,'Polling must not replace a focused control');
  // Expanded disclosures survive the deferred repaint.
  let markup=root.innerHTML;
  const expanded={tagName:'DETAILS',dataset:{wsDetail:'owner-evidence'},open:true,parentElement:root,querySelector:()=>({textContent:'Evidence'}),closest:()=>({dataset:{wsRun:'opt-test'}})};
  root.querySelectorAll=()=>[expanded];
  Object.defineProperty(root,'innerHTML',{configurable:true,get:()=>markup,set:value=>{markup=value;expanded.open=false;}});
  context.document.activeElement=null;callbacks.focusout();await timers.shift()();await settle();
  assert.equal(expanded.open,true,'Expanded evidence must survive a poll repaint');
  assert.match(root.innerHTML,/Approve tested setup/);
  context.window.confirm=()=>false;click('opt-approve');await settle();
  assert.equal(calls.filter(c=>c[0].endsWith('/optimization-decide')).length,0,'Activation needs human confirmation');
  context.window.confirm=()=>true;click('opt-approve');await settle();
  assert.equal(calls.filter(c=>c[0].endsWith('/optimization-decide')).length,1);
  historyRun={...optimization,status:'budget_exhausted',message:'Raw legacy budget message'};
  callbacks.change({target:{dataset:{},value:'saved-study',hasAttribute:name=>name==='data-ws-opt-history'}});await settle();
  assert.match(root.innerHTML,/This test batch is complete/);
  assert.match(root.innerHTML,/The setup has not yet met the approval requirements/);
  assert.ok(!root.innerHTML.includes('Reserved request slots') && !root.innerHTML.includes('Tested form instructions'));
  context.window.confirm=()=>false;click('opt-continue');await settle();
  assert.equal(calls.filter(c=>c[0].endsWith('/optimization-continue')).length,0);
  context.window.confirm=()=>true;click('opt-continue');click('opt-continue');await settle();
  assert.equal(calls.filter(c=>c[0].endsWith('/optimization-continue')).length,1,'One human approval must grant only one round');
  const grant=JSON.parse(calls.find(c=>c[0].endsWith('/optimization-continue'))[1].body);assert.equal(grant.additional_rounds,1);assert.equal(grant.allow_paid,true);
  historyRun={...optimization,status:'escalated',tech:{status:'proposal_ready',proposal_hash:'exact-proposal',proposal:{headline:'Repair context preparation',summary:'Evidence checked',findings:[],proposed_changes:['Add verified reference'],validation_plan:['Check actual packet'],risks:[],questions:[]}}};
  callbacks.change({target:{dataset:{},value:'saved-study',hasAttribute:name=>name==='data-ws-opt-history'}});await settle();
  assert.match(root.innerHTML,/Approve development repair/);
  context.window.confirm=()=>false;click('tech-approve');await settle();assert.equal(calls.filter(c=>c[0].endsWith('/optimization-technical-decision')).length,0);
  context.window.confirm=()=>true;click('tech-approve');await settle();
  const repair=JSON.parse(calls.find(c=>c[0].endsWith('/optimization-technical-decision'))[1].body);assert.equal(repair.proposal_hash,'exact-proposal');assert.equal(repair.action,'approve_repair');
  // Reopening a paused study must prompt a decision without authorizing work.
  const pendingContext={window:{confirm:()=>false},console,setTimeout:()=>{},crypto:{randomUUID:()=> 'unused'}};
  vm.createContext(pendingContext);vm.runInContext(fs.readFileSync('web/workshop.js','utf8'),pendingContext);
  const pendingRoot={dataset:{},innerHTML:'',addEventListener:()=>{},querySelector(){return this.innerHTML.includes('writer-workshop')?{}:null;}};
  const postCount=calls.filter(c=>c[1]?.method==='POST').length;
  await pendingContext.window.NCCEWorkshop.open(pendingRoot,(url,options)=>url==='/api/workshop/optimizations'?Promise.resolve({configuration:{},runs:[{...optimization,status:'budget_exhausted'}]}):api(url,options),doc=>escaped(JSON.stringify(doc)));
  assert.match(pendingRoot.innerHTML,/This test batch is complete/);
  assert.match(pendingRoot.innerHTML,/Authorize another test round/);
  assert.equal(calls.filter(c=>c[1]?.method==='POST').length,postCount,'Opening an owner decision must not queue work');
  // Reopen each saved decision state without spending or changing its audit.
  async function savedView(run){
    const c={window:{confirm:()=>false},console,setTimeout:()=>{},crypto:{randomUUID:()=> 'unused'}};
    vm.createContext(c);vm.runInContext(fs.readFileSync('web/workshop.js','utf8'),c);
    const r={dataset:{},innerHTML:'',addEventListener:()=>{},querySelector(){return this.innerHTML.includes('writer-workshop')?{}:null;}};
    const before=JSON.stringify(run), count=calls.filter(x=>x[1]?.method==='POST').length;
    await c.window.NCCEWorkshop.open(r,(url,options)=>url==='/api/workshop/optimizations'?Promise.resolve({configuration:{},runs:[run]}):api(url,options),doc=>escaped(JSON.stringify(doc)));
    assert.equal(JSON.stringify(run),before,'Rendering must preserve stored status and audit');
    assert.equal(calls.filter(x=>x[1]?.method==='POST').length,count,'Reopening must not write or spend');
    return r.innerHTML;
  }
  for(const status of ['budget_exhausted','awaiting_next_round']){
    const h=await savedView({...optimization,status,message:'Historical allowance message'});
    assert.match(h,/ws-decision is-batch-complete/);
    assert.match(h,/The rounds you authorized have finished\. Drafts and reviews are saved/);
    assert.match(h,/The setup has not yet met the approval requirements/);
    assert.match(h,/4 fresh writing calls \+ 2 pair reviews/);
    assert.match(h,/Authorize another test round/);assert.match(h,/Finish and keep findings/);
    const panel=h.slice(h.indexOf('<section class="ws-decision'));
    assert.doesNotMatch(panel,/role="alert"|API account|provider-credit|test allowance/);
  }
  const validating=await savedView({...optimization,status:'awaiting_next_round',validation_pending:true});
  assert.match(validating,/Promising setup · validate on fresh entries/);
  assert.match(validating,/same prompt must now pass on fresh entries before activation/);
  assert.match(validating,/Authorize validation round/);
  assert.doesNotMatch(validating,/This test batch is complete|Approve tested setup/);
  for(const status of ['escalated','awaiting_next_round']){
    const h=await savedView({...optimization,status,message:'Writing provider could not be reached',tech:{status:'needs_input',error:'Technical connection failed'}});
    assert.match(h,/<p role="alert">Technical connection failed/);
    if(status==='escalated'){
      assert.match(h,/The writing loop is paused/);assert.match(h,/Writing provider could not be reached/);
      assert.doesNotMatch(h,/ws-decision is-batch-complete/);
    }
  }
  const finished=await savedView({...optimization,status:'finished'});
  assert.doesNotMatch(finished,/This test batch is complete|data-ws="opt-continue"/);
  const css=fs.readFileSync('web/writing.css','utf8');
  assert.match(css,/\.ws-decision\.is-batch-complete\s*\{/);
  console.log('Workshop UI passed: draft-first layout, legacy removal, free opening, escaping, human gates, duplicate protection and saved-state rendering');
})().catch(error=>{console.error(error);process.exitCode=1;});
