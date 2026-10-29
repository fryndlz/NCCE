const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const callbacks={},timers=[],calls=[];
const root={dataset:{},innerHTML:'',addEventListener:(name,fn)=>{callbacks[name]=fn;},querySelector(selector){if(selector==='.writer-workshop')return this.innerHTML.includes('writer-workshop')?{}:null;if(selector==='#ws-edited-preview')return this.preview ||= {innerHTML:''};return null;}};
const escaped=s=>String(s).replaceAll('<','&lt;').replaceAll('>','&gt;');
const bodyDoc={blocks:[{type:'body_paragraph',text:'Original sample'}],composition:{}};
const home={model:'same-model',effort:'low',configured:true,review:[{label:'Obsolete comparison',note:'Old feedback',versions:{A:'old',B:'old'}}],forms:['fighter_memory','place_ambient'],focus_options:{fighter_memory:[{value:'recorded_event',label:'Recorded event'}],place_ambient:[{value:'economic',label:'Livelihood'},{value:'historical',label:'History'}]},samples:[{key:'test',form:'fighter_memory',label:'Mara'},{key:'territory',form:'place_ambient',label:'Mine'}],trials:[]};
const sample={key:'test',form:'fighter_memory',label:'Mara',packet:{evidence:['Critical Injury']},document:bodyDoc};
const optimization={run_id:'opt-test',form:'fighter_memory',status:'queued',message:'<unsafe>',writer_reserved:0,writer_limit:4,reviewer_reserved:0,reviewer_limit:2,specific:{instructions:'Candidate <unsafe>'},shared:{label:'Shared',instructions:'Protected'},rounds:[],events:[],coverage:'Two source contexts',reviewer_context:'Saved review brief'};
optimization.rounds=[{number:1,pairs:[{label:'Review entry',candidates:[{status:'ready',document:bodyDoc},{status:'ready',document:bodyDoc}],review:{summary:'A complete assessment. '+('Evidence and reasoning. '.repeat(25)),candidates:[0,1].map(index=>({index,overall:6,scores:{factual_fidelity:9,distinctiveness:5},issues:[{category:'context',blocking:true,explanation:'Inspect this context. '+('More explanation. '.repeat(20)),evidence:'Exact <unsafe> evidence'}]}))}}]}];
let ids=0,historyRun=null,activationResolve=null,activationReject=null,guidelinesFail=false;
async function api(url,options){
  calls.push([url,options]);
  if(url==='/api/workshop')return home;
  if(url.endsWith('/guidelines-activate'))return new Promise((resolve,reject)=>{activationResolve=resolve;activationReject=reject;});
  if(url.startsWith('/api/workshop/guidelines?')){
    if(guidelinesFail)throw new Error('Connection lost');
    const scope=url.split('scope=')[1], change={summary:'Added 1 instruction lines; removed 1.',edits:[{before:'Old guidance',after:'New <unsafe> guidance'}]};
    const latest={revision_id:'guide-new',created_at:'2026-10-28',instructions:'New <unsafe> guidance',examples:'',change,comparison:'Previous tested instructions',source:{author:'JKSimmons'}};
    return {scope,latest,active:{revision_id:'guide-active',instructions:'# Active heading\n\nActive safe guidance',examples:''},history:[latest],proposals:[{}],timeline:[{event_id:'proposal-one',kind:'proposal',created_at:'2026-10-28T12:10:00Z',time_basis:'Review completed',run_id:'old-study-A',round:1,entry_number:1,entry:'Prior entry',instructions:'# Proposed heading\n\n**Useful** guidance\n\n1. First rule\n2. Second rule',reason:'Review reason',change},{...latest,event_id:'saved-one',kind:'saved',is_active:false}],history_limit:40};
  }
  if(url==='/api/workshop/optimizations')return {configuration:{},runs:[]};
  if(url.startsWith('/api/workshop/quality'))return {calibration:{calibrated:false,message:'Reviewer scores are advisory.',fresh_pairs:0,agreements:0,has_rejection_check:false},suggested_instructions:'Test direct subject focus.',contract:{rules:[],historical_examples:[],limitations:[]},scope_note:'Historical examples are not fresh tests.'};
  if(url.startsWith('/api/workshop/policy')){const scope=decodeURIComponent(url.split('scope=')[1]),revision={scope,revision_id:scope+'-existing',label:'Current',instructions:'Some <unsafe> instructions',examples:'Example'};return {draft:revision,active:revision,history:[],builtin:{},candidate:{}};}
  if(url.startsWith('/api/workshop/sample'))return url.includes('territory')?{...sample,key:'territory',form:'place_ambient',label:'Mine'}:sample;
  const data=options?.body?JSON.parse(options.body):{};
  if(url.endsWith('save-policy'))return {...data,revision_id:'r'+(++ids)};
  if(url.endsWith('preview'))return {...sample,plan_key:'frozen-plan',packet:{...sample.packet,creative_plan:{focus_label:'Recorded event'}},instructions:'Exact inspected instructions'};
  if(url.endsWith('generate'))return {trial_id:'once',status:'queued',form:'fighter_memory',label:'Mara',document:{},edits:[],packet:sample.packet,usage:{},instructions:'Saved instructions'};
  if(url.endsWith('/optimize'))return optimization;
  if(url.includes('/optimization?'))return historyRun || {...optimization,workflow_version:3,status:'awaiting_approval'};
  if(url.endsWith('/optimization-continue'))return {...optimization,status:'queued'};
  if(url.endsWith('/optimization-technical-decision'))return {...historyRun,tech:{...historyRun.tech,status:data.action==='approve_repair'?'repair_queued':data.action==='approve_release'?'release_queued':'queued'}};
  if(url.endsWith('/optimization-decide'))return {...optimization,status:data.approve?'approved':'rejected'};
  if(url.includes('/trial?'))return {trial_id:'once',status:'ready',form:'fighter_memory',label:'Mara',document:bodyDoc,edits:[],packet:sample.packet,usage:{requests_attempted:1,input_tokens:100},instructions:'Saved instructions'};
  throw new Error('Unexpected request '+url);
}
const context={window:{confirm:()=>false},console,setTimeout:fn=>timers.push(fn),crypto:{randomUUID:()=> 'same-request-key'}};
vm.createContext(context);vm.runInContext(fs.readFileSync('web/workshop.js','utf8'),context);
function click(action,extra={}){const button={dataset:{ws:action,...extra},disabled:false};callbacks.click({target:{closest:()=>button},preventDefault(){},stopPropagation(){}});}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await context.window.NCCEWorkshop.open(root,api,doc=>escaped(JSON.stringify(doc)));
  assert.equal(calls.filter(c=>c[1]?.method==='POST').length,0,'Opening must not write or spend');
  assert.match(root.innerHTML,/Improve a whole prose category/);
  assert.match(root.innerHTML,/<details class="ws-guidelines" data-ws-detail="guidelines-library">/);
  assert.match(root.innerHTML,/Suggested changes · not applied/);assert.match(root.innerHTML,/New &lt;unsafe&gt; guidance/);
  assert.ok(root.innerHTML.indexOf('workshop-optimization')<root.innerHTML.indexOf('class="ws-guidelines"'),'Reference belongs after the study');
  assert.equal((root.innerHTML.match(/Active instructions · full reference/g)||[]).length,1);
  assert.match(root.innerHTML,/<h5>Proposed heading<\/h5>/);assert.match(root.innerHTML,/<ol><li>First rule/);
  assert.match(root.innerHTML,/Study/);assert.match(root.innerHTML,/28 Oct 2026/);
  assert.match(root.innerHTML,/It did not replace saved guidelines or activate anything/);
  const readOnlyPostCount=calls.filter(c=>c[1]?.method==='POST').length;
  callbacks.change({target:{dataset:{},value:'shared',hasAttribute:n=>n==='data-ws-guide-scope'}});await settle();
  assert.match(root.innerHTML,/Guideline timeline · newest first/);
  click('guidelines-refresh');await settle();
  assert.equal(calls.filter(c=>c[1]?.method==='POST').length,readOnlyPostCount,'Browsing and refreshing guidelines must be read-only');
  context.window.confirm=()=>true;
  click('guidelines-activate',{eventId:'proposal-one'});click('guidelines-activate',{eventId:'proposal-one'});await settle();
  assert.match(root.innerHTML,/ws-activation-spinner/);assert.match(root.innerHTML,/Activating…/);
  assert.doesNotMatch(root.innerHTML,/ws-guideline-event is-active-version/,'No optimistic highlight while activation is pending');
  assert.equal(calls.filter(c=>c[0].endsWith('/guidelines-activate')).length,1,'Double activation click sends one request');
  const confirmed=await api('/api/workshop/guidelines?scope=shared');confirmed.timeline[0].is_active=true;confirmed.active={revision_id:'approved-proposal',instructions:'Proposed guidelines'};
  activationResolve(confirmed);await settle();
  assert.doesNotMatch(root.innerHTML,/ws-activation-spinner/);assert.match(root.innerHTML,/ws-guideline-event is-active-version/);
  assert.match(root.innerHTML,/Active proposal ✓/);assert.match(root.innerHTML,/You activated this proposal/);
  guidelinesFail=true;click('guidelines-activate',{eventId:'saved-one'});await settle();
  assert.match(root.innerHTML,/ws-activation-spinner/);assert.match(root.innerHTML,/Active proposal ✓/,'Previous active badge remains while a different version is pending');
  activationReject(new Error('Connection lost'));await settle();guidelinesFail=false;
  assert.doesNotMatch(root.innerHTML,/ws-activation-spinner/);assert.match(root.innerHTML,/Activation was not confirmed/);
  assert.match(root.innerHTML,/Active proposal ✓/,'Failure preserves the last confirmed active selection');
  context.window.confirm=()=>false;click('opt-start');await settle();
  assert.equal(calls.filter(c=>c[0].endsWith('/optimize')).length,0,'Declining paid optimization must not queue it');
  for(const legacy of ['Generate one draft','Find an entry','Shared writing craft','Workshop samples','Complete study report','Your comparison feedback','Obsolete comparison'])assert.ok(!root.innerHTML.includes(legacy),legacy+' must be absent');
  assert.ok(!root.innerHTML.includes('<unsafe>'));
  assert.match(root.innerHTML,/data-ws-opt-form/);
  callbacks.change({target:{dataset:{},value:'place_ambient',hasAttribute:name=>name==='data-ws-opt-form'}});
  await settle();
  assert.match(root.innerHTML,/Start territory scenes study/);

  context.window.confirm=()=>true;
  click('opt-start');click('opt-start');await settle();
  assert.equal(calls.filter(c=>c[0].endsWith('/optimize')).length,1,'Double click must authorize only one bounded run');
  const optBody=JSON.parse(calls.find(c=>c[0].endsWith('/optimize'))[1].body);
  assert.equal(optBody.allow_paid,true);assert.equal(optBody.max_rounds,1);
  assert.equal(optBody.sample_key,'territory','Improvement must use the selected prose type, not the manual sample');
  assert.equal(optBody.shared_revision_id,'shared-existing');assert.equal(optBody.form_revision_id,'r1');
  assert.equal(calls.filter(c=>c[0].endsWith('/save-policy')).length,1,'Starting saves one explicit candidate, while using the active shared guidance as control');
  assert.equal(JSON.parse(calls.find(c=>c[0].endsWith('/save-policy'))[1].body).instructions,'Test direct subject focus.');
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
  callbacks.change({target:{dataset:{},value:'saved-study',hasAttribute:name=>name==='data-ws-opt-history'}});await settle();
  assert.match(root.innerHTML,/ws-tech-brief/);assert.match(root.innerHTML,/<h5>Problem<\/h5>/);
  assert.match(root.innerHTML,/<h5>Solution<\/h5>/);assert.match(root.innerHTML,/<h5>Risk<\/h5>/);
  assert.match(root.innerHTML,/<details class="ws-tech-evidence" data-ws-detail="technical-evidence">/);
  callbacks.input({target:{dataset:{wsTechRejection:'exact-proposal'},value:'Try a smaller fix.',hasAttribute:n=>n==='data-ws-tech-rejection'}});
  const beforeReject=calls.filter(c=>c[0].endsWith('/optimization-technical-decision')).length;
  click('tech-reject');click('tech-reject');await settle();
  const rejected=calls.filter(c=>c[0].endsWith('/optimization-technical-decision'));
  assert.equal(rejected.length,beforeReject+1,'Double reject must submit once');
  const rejection=JSON.parse(rejected.at(-1)[1].body);
  assert.equal(rejection.note,'Try a smaller fix.');assert.equal(rejection.proposal_hash,'exact-proposal');assert.ok(rejection.request_key);
  assert.match(root.innerHTML,/Investigation queued/);
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
  assert.match(finished,/Study finished · results saved/);
  assert.doesNotMatch(finished,/This test batch is complete|data-ws="opt-continue"/);
  for(const status of ['investigating','proposal_ready','released']){
    const closed=await savedView({...optimization,status:'finished',tech:{status}});
    assert.match(closed,/Study finished · results saved/);
    assert.doesNotMatch(closed,/The writing loop is paused/);
    assert.match(closed,/<details class="ws-disclosure" data-ws-detail="finished-technical">/);
  }
  const controlledPair={label:'Blind precinct',experiment:true,candidates:[{status:'ready',document:bodyDoc},{status:'ready',document:bodyDoc}],review:null,review_pending_reveal:true};
  const blind=await savedView({...optimization,workflow_version:3,status:'awaiting_owner',rounds:[{number:1,pairs:[controlledPair]}]});
  assert.match(blind,/Your blind verdicts are needed/);assert.match(blind,/Seal verdict and reveal comparison/);
  assert.doesNotMatch(blind,/Draft A assessment|Candidate: A|Candidate: B|Independent hidden assessment/);
  assert.match(blind,/Strong neither/);assert.match(blind,/scores alone cannot qualify/);
  assert.match(blind,/Prefer A · neither acceptable/);assert.match(blind,/Tie · neither acceptable/);
  const recovered=await savedView({...optimization,workflow_version:3,status:'awaiting_resume',message:'Original review recovered',review_recovery:{job_id:'saved-review'},writer_reserved:2,reviewer_reserved:1});
  assert.match(recovered,/Resume saved round/);assert.match(recovered,/2 writing calls and 1 reviews remain/);
  assert.match(recovered,/Completed drafts and reviews will be reused/);
  const deliveryRecovery=await savedView({...optimization,status:'escalated',review_recovery_available:{job_id:'never-claimed-review'}});
  assert.match(deliveryRecovery,/Recover saved draft review/);
  assert.match(deliveryRecovery,/No writing calls will be repeated/);
  const transport=await savedView({...optimization,workflow_version:3,status:'running',rounds:[{number:1,pairs:[{...controlledPair,review_pending_reveal:false,review_transport:{status:'queued',enqueued_at:'2026-10-29T06:16:00Z',notification_accepted_at:'2026-10-29T06:16:44Z'}}]}]});
  assert.match(transport,/Waiting for Codex chat/);assert.match(transport,/Notification accepted/);
  assert.doesNotMatch(transport,/Native start|Candidate: A|Candidate: B/);
  const revealedPair={...controlledPair,review_pending_reveal:false,candidate_index:1,owner_verdict:{preference:'A',agrees:false,critical_miss:true},review:{...optimization.rounds[0].pairs[0].review,preference:'B',experiment:{changed:'Shorter instructions',addresses:'Drift',observed_effect:'Still drifted',regressions:'Subject lost'}}};
  const revealed=await savedView({...optimization,workflow_version:3,status:'awaiting_owner',rounds:[{number:1,pairs:[revealedPair]}]});
  assert.match(revealed,/Candidate: B; current setup: A/);assert.match(revealed,/Reviewer disagrees with you/);
  assert.match(revealed,/calibration revoked/);assert.match(revealed,/What this experiment changed/);
  const techSummary=await savedView({...optimization,status:'escalated',tech:{status:'proposal_ready',proposal_hash:'brief-proposal',proposal:{
    headline:'Long technical title',summary:'DETAILS_ONLY '+('Long evidence. '.repeat(60)),findings:[],proposed_changes:['Detailed change list'],validation_plan:['Detailed test plan'],risks:['Detailed risk list'],questions:[],
    decision_brief:{problem:'The writer lacks <verified> context.',solution:'Add the missing source to its requests.',risk:'Unknown types still need verification.'}}}});
  const briefOnly=techSummary.split('<ol class="ws-tech-brief">')[1].split('</ol>')[0];
  assert.match(briefOnly,/The writer lacks &lt;verified&gt; context/);assert.doesNotMatch(briefOnly,/DETAILS_ONLY|Long evidence/);
  assert.match(techSummary,/Technical evidence &amp; full report/);assert.ok(!techSummary.includes('<verified>'));
  const learning=await savedView({...optimization,workflow_version:3,status:'finished',feedback_sync:{status:'reviewing',message:'Incorporating feedback'}});
  assert.match(learning,/JKSimmons · incorporating your feedback/);assert.match(learning,/ws-activation-spinner/);
  const learned=await savedView({...optimization,workflow_version:3,status:'finished',feedback_sync:{status:'completed',active_revision_id:'latest-completed-guidance',message:'Subject focus updated.',changes:['Kept the precinct central.'],standards:'Concrete subject first.',owner_corrections:['Territory stays central.'],reviewer_inferences:['Try a shorter start.']}});
  assert.match(learned,/JKSimmons · standards updated/);assert.match(learned,/Kept the precinct central/);
  assert.match(learned,/activated automatically for future writing/);
  const css=fs.readFileSync('web/writing.css','utf8');
  assert.match(css,/\.ws-decision\.is-batch-complete\s*\{/);
  console.log('Workshop UI passed: draft-first layout, legacy removal, free opening, escaping, human gates, duplicate protection and saved-state rendering');
})().catch(error=>{console.error(error);process.exitCode=1;});
