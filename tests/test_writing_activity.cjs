const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context={window:{}};vm.createContext(context);vm.runInContext(fs.readFileSync('web/writing_activity.js','utf8'),context);
const activity=context.window.NCCEWritingActivity;
const run={run_id:'opt-test',status:'running',writer_reserved:1,reviewer_reserved:0,visited_steps:['context','draft'],activity:{phase:'draft',actor:'JuniorWriter',message:'Writing draft A <unsafe>',sample:1}};
let view=activity.model(run);assert.equal(view.people.filter(p=>p.active).length,1);assert.equal(view.people[0].active,true);
let html=activity.render(run);assert.ok(!html.includes('<unsafe>'));assert.match(html,/Writing draft A &lt;unsafe&gt;/);assert.match(html,/agent-writer is-working/);assert.match(html,/aria-current="step"/);
assert.match(html,/Repeat for entry 2/);assert.match(html,/4 writing calls \+ 2 pair reviews/);
run.activity={phase:'review',actor:'JKSimmons',message:'Checking both drafts'};view=activity.model(run);assert.equal(view.people[1].active,true);assert.equal(view.people[0].active,false);
assert.match(activity.render(run),/data-working-agent="JKSimmons"/);
assert.match(activity.render(run),/agent-work-spinner/);
assert.ok(activity.render(run).indexOf('agent-live-event')<activity.render(run).indexOf('writing-flow'),'Live status is visible with empty handoff history');
run.status='escalated';run.activity={phase:'escalated',actor:'StoryTechMan',message:'Missing a historical source'};view=activity.model(run);
assert.ok(view.people.every(p=>!p.active));assert.equal(view.people[2].attention,true);assert.match(activity.render(run),/Missing a historical source/);
run.status='awaiting_approval';assert.doesNotMatch(activity.render(run),/agent-work-spinner|agent-queued-event/);run.activity={phase:'approval',actor:'human',message:'Please approve'};assert.ok(activity.model(run).people.every(p=>!p.active));assert.match(activity.render(run),/You decide/);
run.status='approved';run.activity={phase:'complete',actor:'human',message:'Approved'};assert.match(activity.render(run),/approved is active/);
assert.ok(activity.model(null).people.every(p=>!p.active));assert.match(activity.render(null),/I’m ready/);
run.status='running';run.activity={phase:'awaiting_reviewer',actor:'StoryTechMan',message:'Waiting for Codex'};
assert.ok(activity.model(run).people.every(p=>!p.active));assert.match(activity.render(run),/Waiting for Codex/);
assert.match(activity.render(run),/Waiting for JKSimmons to begin/);
assert.doesNotMatch(activity.render(run),/agent-work-spinner/);
run.activity={phase:'revise',actor:'JKSimmons',message:'Save candidate'};
assert.equal(activity.model(run).people[0].expression,'sad');assert.equal(activity.model(run).people[1].expression,'angry');
const neutral=activity.render(run,{personas:false});assert.ok(!neutral.includes('Enough fog'));assert.match(neutral,/Save candidate/);
const original=JSON.stringify(run);activity.render(run);assert.equal(JSON.stringify(run),original,'Personas cannot mutate grades or run state');
run.dialogue=[{from:'JKSimmons',to:'JuniorWriter',phase:'evaluate',text:'Long <unsafe> assessment. '+('Keep all evidence. '.repeat(30))}];
const readable=activity.render(run);assert.match(readable,/handoff-card/);assert.match(readable,/Full handoff/);assert.ok(!readable.includes('<unsafe>'));assert.match(readable,/Keep all evidence/);
run.status='escalated';run.tech={status:'investigating'};view=activity.model(run);assert.equal(view.people[2].active,true);assert.ok(view.people.slice(0,2).every(p=>!p.active));
for(const status of ['investigating','repairing','releasing']){
  run.tech.status=status;assert.match(activity.render(run),/data-working-agent="StoryTechMan"/);
  assert.match(activity.render(run),/agent-work-spinner/);
}
for(const status of ['queued','repair_queued','release_queued']){
  run.tech.status=status;assert.match(activity.render(run),/Waiting for StoryTechMan to begin/);
  assert.doesNotMatch(activity.render(run),/agent-work-spinner/);
}
run.tech.status='proposal_ready';assert.doesNotMatch(activity.render(run),/agent-work-spinner/);assert.ok(activity.model(run).people.every(p=>!p.active));
run.tech=null;run.status='awaiting_next_round';assert.equal(activity.model(run).attention,false);
for(const status of ['awaiting_next_round','budget_exhausted']){
  run.status=status;const waiting=activity.model(run);
  assert.equal(waiting.attention,false);assert.equal(waiting.phase,'decision');
  assert.ok(waiting.people.every(p=>!p.active && !p.attention));
}
// The graph reads actual status, round kind, pair position and scoped technical state.
function current(r){return activity.workflow(r).node;}
const validation={...run,status:'running',tech:null,rounds:[{number:2,kind:'validation',pairs:[]}],activity:{phase:'draft',actor:'JuniorWriter',round:2,sample:2,draft:1}};
assert.equal(activity.workflow(validation).mode,'Validation');assert.equal(current(validation),'draft');
assert.match(activity.render(validation),/data-flow-mode="validation"/);
assert.match(activity.render(validation),/entry 2\/2/);
assert.equal(current({...validation,activity:{phase:'evaluate'}}),'pair','A pair review is not a whole-round pass');
for(const phase of ['context','draft','review','awaiting_reviewer']){
  const r={...validation,activity:{phase,actor:phase==='draft'?'JuniorWriter':phase==='review'?'JKSimmons':'StoryTechMan'}};
  assert.equal(activity.workflow(r).mode,'Validation');
  if(phase==='context')assert.ok(activity.model(r).people.every(p=>!p.active),'Routine context checks do not invoke a Codex agent');
}
assert.equal(current({...validation,status:'awaiting_next_round',validation_pending:true}),'allowance');
assert.equal(current({...validation,status:'awaiting_approval'}),'approval');
assert.equal(current({...validation,status:'approved'}),'activate');
for(const [status,node] of Object.entries({queued:'investigate',investigating:'investigate',proposal_ready:'proposal',repair_queued:'repair',repairing:'repair',repair_ready:'release-decision',release_queued:'release',releasing:'release',released:'new-study',needs_input:'halt'})){
  const r={...validation,status:'escalated',activity:{phase:'decision'},tech:{status}};
  assert.equal(current(r),node,'Technical '+status+' must show its own stage');
  const h=activity.render(r);assert.equal((h.match(/aria-current="step"/g)||[]).length,1);
  assert.match(h,new RegExp('flow-step flow-node is-current" data-flow-node="'+node+'"'));
}
for(const status of ['escalated','stopped','awaiting_samples','finished','rejected'])assert.equal(current({...validation,status}),'halt');
const historical={...validation,status:'awaiting_next_round',visited_steps:['review','validation','activate','escalated'],activity:{phase:'review'}};
const historyGraph=activity.render(historical).split('<figure')[1];
assert.doesNotMatch(historyGraph,/is-visited|flow-edge/,'Historical node visits cannot invent traversed routes');
assert.match(historyGraph,/flow-step flow-node is-current" data-flow-node="allowance"/);
assert.equal(activity.workflow({...validation,status:'queued',validation_pending:false}).mode,'Learning','Next round mode comes from current pending flag');
assert.equal(activity.workflow({...validation,status:'queued',validation_pending:true}).mode,'Validation');
assert.match(historyGraph,/Separate approval of the exact tested repair/);
assert.match(historyGraph,/Validation falls short/);assert.match(historyGraph,/do not call the StoryTechMan model/);
const css=fs.readFileSync('web/writing.css','utf8');
assert.match(css,/prefers-reduced-motion/);
assert.match(css,/\.flow-tip\s*\{\s*display:none/,'Descriptions must be hidden by default');
assert.match(css,/\.flow-node:hover>\.flow-tip,\.flow-node:focus-within>\.flow-tip/,'Hover and keyboard/touch focus reveal descriptions');
const compact=activity.render({...validation,status:'running',tech:null});
assert.match(compact,/aria-describedby="flow-tip-context"/);assert.match(compact,/role="tooltip" id="flow-tip-context"/);
assert.match(compact,/<details class="flow-repair" data-ws-detail="flow-repair">/,'Repair subgraph starts collapsed');
assert.match(activity.render({...validation,tech:{status:'repairing'}}),/<details class="flow-repair" data-ws-detail="flow-repair" open>/,'Current repair branch opens automatically');
assert.doesNotMatch(compact.split('<figure')[1],/<p[ >]/,'No explanation paragraphs are permanently visible in the graph');
console.log('PASS live agent heads and workflow: one working actor, escaped speech, review transition, human escalation, approval, idle and reduced motion');
