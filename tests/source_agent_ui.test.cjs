const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
function element(tag='div',value=''){
  return {tagName:tag.toUpperCase(),textContent:String(value??''),children:[],value:'',disabled:false,hidden:false,style:{},attributes:{},handlers:{},
    append(...items){this.children.push(...items);},replaceChildren(...items){this.children=[];this.textContent='';this.append(...items);},
    setAttribute(key,value){this.attributes[key]=String(value);},addEventListener(key,fn){this.handlers[key]=fn;},get options(){return this.children;}};
}
function text(node){return node.textContent+' '+node.children.map(item=>typeof item==='string'?item:text(item)).join(' ');}
const script=fs.readFileSync(path.join(__dirname,'../biograph_steward/source_agent.js'),'utf8');
function job(kind='live_nim',status='completed'){
  return {job_id:'source_agent_invented',source_run:'invented',actual_model_run:kind==='live_nim',provider_kind:kind,result:{
    source_run:'invented',status,question:'Inspect invented physical records.',plan:{action:'query',tool:'native_physical',arguments:{protein_id:'protein:a',view:'candidates'},reason:'Select the requested source.'},
    answer:{overview:'Two candidate citations.',statements:[{text:'Recorded annotation.',citation_ids:['E001']},{text:'Another recorded annotation.',citation_ids:['E002']}],
      citations:[{id:'E001',subject:'protein:a',object:'protein:b',review_state:'candidate',assertion_id:'claim:a'},
        {id:'E002',subject:'protein:a',object:'protein:c',review_state:'candidate',assertion_id:'claim:b'}],limitations:['Missing source information remains unknown.']},
    focus_graph:{nodes:[{id:'protein:a',name:'Anchor'},{id:'protein:b',name:'Partner'}],edges:[{id:'e1',subject:'protein:a',object:'protein:b'}],assertions:[{lifecycle_state:'candidate',evidence_edge_ids:['e1']}]},
    inspections:[{citation_id:'E001',passport:{summary:'Invented original source',review:{state:'candidate',note:'Candidate is a review state.'},qualifiers:{native_score:459},questions:[],links:[]}}],
    proposals:[{citation_id:'E001',decision:'abstain',reason:'Source context is unresolved.',review_question:'What was measured?',proposal_only:true,applied:false}],
    trace:{model_calls:3,tool_calls:[{tool:'native_physical'},{tool:'inspect_source'}]},source_bindings:{snapshot_sha256:'a'.repeat(64)},content_sha256:'b'.repeat(64)}};
}
function harness({saved=false,query='',responses={}}={}){
  const elements=new Map(),calls=[],manual=[],posts=[],$=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
  const context=vm.createContext({$,el:element,svgEl:element,URLSearchParams,location:{search:query},runId:'invented',savedReviewOnly:()=>saved,
    fieldList:value=>element('dl',JSON.stringify(value)),guideLink:link=>element('a',link.label),showWorkspaceView:view=>manual.push(view),loadSourceGuide:id=>manual.push(id),
    api:async(...args)=>{posts.push(args);return job();},fetch:async route=>{calls.push(route);const value=responses[route];if(value===undefined)throw new Error('Unexpected fetch '+route);return {ok:true,json:async()=>value};}});
  vm.runInContext(script,context);return {$,context,calls,manual,posts};
}
test('source-agent is the primary Start here entry and manual controls remain available',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../biograph_steward/ui.html'),'utf8');
  assert.ok(html.indexOf('id="sourceAgentPanel"')<html.indexOf('id="reviewerHome"'));
  for(const label of ['Agent workflow','Run the source agent','Replay the recorded run','Read the cited answer'])assert.ok(html.includes(label));
  assert.ok(html.includes('Live inference and new agent jobs are disabled.'));
});
test('saved-mode initialization reads config/list only and never silently opens or infers',async()=>{
  const h=harness({saved:true,responses:{'/api/source-agent/status?run_id=invented':{saved_data_only:true,configured:null,enabled:false,catalogue:{tools:[{name:'native_physical'}]}},
    '/api/source-agent/jobs?run_id=invented':{jobs:[{job_id:'source_agent_invented',actual_model_run:false,status:'completed',question:'Invented fixture'}]}}});
  await h.context.setupSourceAgent();assert.equal(h.$('sourceAgentLive').hidden,true);assert.equal(h.$('sourceAgentRun').disabled,true);
  assert.equal(h.calls.length,2);assert.deepEqual(h.posts,[]);assert.match(text(h.$('sourceAgentJobs')),/Development\/test record/);
  assert.match(text(h.$('sourceAgentStatus')),/No agent is running now/);
  await h.context.runSourceAgent({preventDefault(){}});assert.equal(h.posts.length,0);
});
test('configured operator status is explicitly unprobed and only submission triggers the controller',async()=>{
  const h=harness({responses:{'/api/source-agent/status?run_id=invented':{configured:true,enabled:true,model:'test-model',provider:'nim',catalogue:{tools:[{name:'native_physical'}]}},
    '/api/source-agent/jobs?run_id=invented':{jobs:[]}}});
  await h.context.setupSourceAgent();assert.match(text(h.$('sourceAgentConfig')),/Connectivity has not been checked/);assert.equal(h.posts.length,0);
  h.$('sourceAgentQuestion').value='Inspect candidate physical records.';h.$('sourceAgentView').value='candidates';
  await h.context.runSourceAgent({preventDefault(){}});assert.equal(h.posts.length,1);assert.equal(h.posts[0][0],'/api/source-agent/run');
  assert.match(text(h.$('sourceAgentOutput')),/New agent attempt recorded/);
});
test('recorded result renders all four phases, all citations and nonmutating proposals',()=>{
  const h=harness();h.context.renderSourceAgentJob(job(),{replay:true});const rendered=text(h.$('sourceAgentOutput'));
  for(const phrase of ['1. Research question','2. Validated tool plan','3. Evidence and source inspection','4. Proposed review decisions','No model or external retrieval runs; saved-source checks verify this record','2 returned citations; 1 selected','[E002]','Needs review · proposal only','3 model calls · 2 tool calls'])assert.ok(rendered.includes(phrase),phrase);
  assert.ok(!rendered.includes('undefined'));assert.deepEqual(h.manual,[]);assert.deepEqual(h.posts,[]);
  const download=h.$('sourceAgentOutput').children.at(-1);assert.equal(download.href,'/api/source-agent/job/source_agent_invented/download');
});
test('injected and partial jobs remain honestly labeled and never become success claims',()=>{
  const h=harness();const record=job('injected_test_model','invalid_proposal');record.result.proposals=[];record.result.error='Uninspected citation rejected';
  h.context.renderSourceAgentJob(record,{replay:true});const rendered=text(h.$('sourceAgentOutput'));
  assert.match(rendered,/Development\/test record replay/);assert.match(rendered,/does not demonstrate a live model run/);
  assert.match(rendered,/No valid decision proposal/);assert.match(rendered,/Uninspected citation rejected/);
  assert.match(text(h.$('sourceAgentStatus')),/partial evidence does not make the whole agent run successful/);
});
test('a recorded job for another workspace cannot silently change the displayed evidence basis',()=>{
  const h=harness(),record=job();record.source_run='other';assert.throws(()=>h.context.renderSourceAgentJob(record),/different saved workspace/);
  assert.equal(h.$('sourceAgentOutput').children.length,0);
});
test('preflight refusal explains the unsupported scope without silently broadening it',()=>{
  const h=harness(),record=job('unknown','scope_rejected');record.result.scope={unsupported_requirements:['direct_binding_requirement','explicit_review_view_conflict']};
  record.result.plan=null;record.result.answer=null;record.result.inspections=[];record.result.proposals=[];record.result.focus_graph=null;
  h.context.renderSourceAgentJob(record);const rendered=text(h.$('sourceAgentOutput'));
  assert.match(rendered,/cannot verify direct binding/);assert.match(rendered,/candidate\/accepted view conflict/);
  assert.match(rendered,/No executable plan was validated/);assert.equal(h.posts.length,0);
});
test('a featured URL replays only an exact actual-model job from the current workspace',async()=>{
  const record=job(),url='/api/source-agent/job/source_agent_invented';
  const responses={'/api/source-agent/status?run_id=invented':{saved_data_only:true,enabled:false,catalogue:{tools:[]}},
    '/api/source-agent/jobs?run_id=invented':{jobs:[{...record,result:undefined}]},[url]:record};
  const h=harness({saved:true,query:'?run=invented&agent_job=source_agent_invented',responses});await h.context.setupSourceAgent();
  assert.ok(h.calls.includes(url));assert.match(text(h.$('sourceAgentOutput')),/Recorded model run replay/);assert.equal(h.posts.length,0);
  for(const bad of [{...record,actual_model_run:false},{...record,source_run:'other'}]){
    const wrong=harness({saved:true,query:'?agent_job=source_agent_invented',responses:{...responses,
      '/api/source-agent/jobs?run_id=invented':{jobs:[bad]}}});await wrong.context.setupSourceAgent();
    assert.ok(!wrong.calls.includes(url));assert.match(text(wrong.$('sourceAgentStatus')),/not a verified actual-model run for this workspace/);
  }
});
test('a multi-assertion citation renders every actual source passport and the full inspection count',()=>{
  const h=harness(),record=job(),first=record.result.inspections[0].passport;
  record.result.inspections[0]={citation_id:'E001',passport:first,passports:[first,{...first,summary:'Second original source assertion'}],
    inspected_assertion_ids:['claim:a','claim:b'],omitted_assertion_ids:[],complete_citation_inspection:true};
  h.context.renderSourceAgentJob(record);const rendered=text(h.$('sourceAgentOutput'));
  for(const phrase of ['2 source assertions inspected','Source assertion 1 of 2','Source assertion 2 of 2','Second original source assertion','Every source assertion in this selected citation was inspected.'])assert.ok(rendered.includes(phrase),phrase);
});
