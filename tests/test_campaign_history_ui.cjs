const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const appRoot = {clientWidth: 1000, innerHTML: '', querySelectorAll: () => [], querySelector: () => null};
const timelineRoot = {innerHTML: '', querySelectorAll: () => [], querySelector: () => null};
const importLabel = {textContent: ''};
const document = {querySelector(selector) {
  if (selector === '#app') return appRoot;
  if (selector === '#campaignTimeline') return timelineRoot;
  if (selector === '#historyImportLabel') return importLabel;
  return null;
}};
const source = fs.readFileSync('web/app.js', 'utf8');
const renderer = source.slice(0, source.indexOf('function selectControl'));
const context = vm.createContext({document, console, Intl, Date, Map, Set});
vm.runInContext(renderer, context);
vm.runInContext(`
  data = {gangs:[{gang_id:'gang-1',name:'House One'}]};
  historyTimeline = {
    battles:[{battle_id:'battle-1',scenario:'Takeover',status:'played',timing_basis:'session_timestamp_proxy',
      start_at:'2026-10-25T10:00:00+00:00',end_at:'2026-10-25T11:00:00+00:00',gang_ids:['gang-1'],
      gangs:[{gang_id:'gang-1',name:'House One'}],attacker:'House One',defender:'House Two',winner:'House One',
      sessions:[{session_id:'session-1',status:'completed',start_at:'2026-10-25T10:00:00+00:00',end_at:'2026-10-25T11:00:00+00:00'}],raw_record:{id:'battle-1'}}],
    events:[{event_id:'event-1',source_table:'gang_logs',source_row:2,recorded_at:'2026-10-25T10:30:00+00:00',
      gang_id:'gang-1',gang_name:'House One',fighter_id:'fighter-1',fighter_name:'Mara Kel',entity_label:'Mara Kel',
      action_type:'fighter_xp_changed',phase:'during_battle',confidence:'candidate_session_window',battle_id:'battle-1',
      description:'Fighter "Mara Kel" XP changed from 2 to 3',participation:{status:'inferred',basis:'positive_xp_delta_in_battle_window',confidence:'inference'},raw_record:{id:'event-1'}}],
    warnings:[],stats:{battle_records:1,activity_records:1,timed_battles:1},import:{available:true,last_imported_at:'2026-10-26T00:00:00+00:00'}
  };
  renderCampaignTimeline();
`, context);

assert.match(timelineRoot.innerHTML, /data-history-filter="battle"/);
assert.match(timelineRoot.innerHTML, /candidate session window/i);
assert.match(timelineRoot.innerHTML, /data-history-battle="battle-1"/);
assert.match(timelineRoot.innerHTML, /data-history-event="event-1"/);
assert.match(timelineRoot.innerHTML, /candidate window/);

vm.runInContext(`selectedHistoryBattle='battle-1'; renderCampaignTimeline();`, context);
assert.match(timelineRoot.innerHTML, /Activity and nearby downtime/);
assert.match(timelineRoot.innerHTML, /Mara Kel/);
assert.match(timelineRoot.innerHTML, /Original battle record/);
console.log('ok (campaign timeline rendering and battle drilldown)');
