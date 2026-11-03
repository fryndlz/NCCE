const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const timers=[],root={dataset:{view:'workshop'},innerHTML:'',addEventListener(){},querySelector(s){return s==='.writer-workshop' && this.innerHTML.includes('writer-workshop')?{}:null;}};
let releaseHome;
const home=new Promise(resolve=>releaseHome=resolve);
const context=vm.createContext({window:{},console,setTimeout:f=>timers.push(f)});
vm.runInContext(fs.readFileSync('web/workshop.js','utf8'),context);
async function api(url){
  if(url==='/api/workshop')return home;
  if(url==='/api/workshop/optimizations')return {configuration:{},runs:[]};
  if(url==='/api/workshop/population')return {runs:[],max_calls:80};
  if(url==='/api/workshop/production')return {policies:{},items:[]};
  if(url.startsWith('/api/workshop/guidelines?'))return null;
  if(url.startsWith('/api/workshop/quality'))return {suggested_instructions:'',contract:{rules:[],historical_examples:[],limitations:[]}};
  throw Error('Unexpected '+url);
}
(async()=>{
  const opening=context.window.NCCEWorkshop.open(root,api,()=> '');
  root.dataset.view='retrieval';root.innerHTML='<section class="writer-workshop rag-workbench">Writing context · keep this page</section>';
  const retrieval=root.innerHTML;
  releaseHome({forms:[],samples:[],configured:false});
  await opening;
  assert.equal(root.innerHTML,retrieval,'Late Workshop opening overwrote Writing context');
  for(const f of timers)await f();
  assert.equal(root.innerHTML,retrieval,'Late Workshop timer overwrote Writing context');
  console.log('Workshop navigation passed: delayed responses preserve Writing context');
})().catch(e=>{console.error(e);process.exitCode=1;});
