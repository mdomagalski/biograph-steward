// Real-data entry and historical controls must not masquerade as invented data/current graph.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const root=path.join(__dirname,'..');
function element(tag='div',value=''){
  const classes=new Set();return {tagName:tag.toUpperCase(),textContent:String(value),children:[],value:'',disabled:false,hidden:false,open:false,
    className:'',dataset:{},attributes:{},classList:{add:x=>classes.add(x),remove:x=>classes.delete(x),contains:x=>classes.has(x),toggle(x,on){on?classes.add(x):classes.delete(x);}},
    append(...items){this.children.push(...items);for(const item of items)if(item&&typeof item==='object')item.parentElement=this;},
    replaceChildren(...items){this.children=[];this.textContent='';this.append(...items);},
    setAttribute(key,value){this.attributes[key]=String(value);},removeAttribute(key){delete this.attributes[key];},
    addEventListener(){},scrollIntoView(){},focus(){},get options(){return this.children;}};
}
function text(node){return node.textContent+' '+node.children.map(item=>typeof item==='string'?item:text(item)).join(' ');}
function harness(query='',shared=false){
  const elements=new Map(),$=id=>{if(!elements.has(id))elements.set(id,element(id.includes('Selection')||id==='savedRun'?'select':'div'));return elements.get(id);};
  $('embeddedData').textContent='{}';
  const calls={replace:[],assign:[],views:[],sources:[],steps:[],fetch:[],history:[]};
  const location={href:'http://localhost:8766/'+query,search:query,hash:'',protocol:'http:',replace:value=>calls.replace.push(value),assign:value=>calls.assign.push(value)};
  const context=vm.createContext({$,el:element,URL,URLSearchParams,location,history:{replaceState(...args){calls.history.push(args);}},
    graph:null,runId:null,questionAnswer:null,questionSelection:null,assayAnswer:null,civicAnswer:null,
    savedReviewOnly:()=>shared,showWorkspaceView:name=>calls.views.push(name),navigateWork:step=>calls.steps.push(step),
    loadSourceGuide:id=>calls.sources.push(id),switchMode(){},
    document:{querySelector:()=>element('input')},fetch:async url=>{calls.fetch.push(url);return {ok:true,json:async()=>({previews:[{id:'historical_preview',title:'Historical control'}]})};}});
  vm.runInContext(fs.readFileSync(path.join(root,'biograph_steward/workspaces.js'),'utf8'),context);
  return {$,context,calls,location,configure(data){context.configureReviewerEntry(data);}};
}
const entry={example_url:'/?run=real_current&question=cited_current',data_kind:'live_pharos',display_title:'Explore real Pharos evidence',guided_examples:[
  {label:'Explore the cited evidence',url:'/?run=real_current&question=cited_current'},
  {label:'Review applied graph qualifications',url:'/?run=real_retained&question=retained_current',description:'Inspect the applied decisions and preserved baseline.'}]};
function real(h){h.context.graph={data_kind:'live_pharos',summary:{},targets:[]};h.context.runId='real_current';h.context.questionAnswer={source_run:'real_current',question:'Which recorded connections support this question?',citations:[{assertion_id:'claim:original'}]};}

test('root opens only the catalogue-selected real entry and lands on Start here',()=>{
  const h=harness();h.configure({reviewer_entry:entry,runs:[]});
  assert.deepEqual(h.calls.replace,['/?run=real_current&question=cited_current&view=data']);
  assert.equal(h.$('reviewerOffline').hidden,true);
  assert.equal(h.$('reviewerSource').disabled,true);
  assert.match(text(h.$('reviewerExampleLinks')),/Review applied graph qualifications/);
  assert.equal(h.$('reviewerExampleLinks').children.length,1);
});
test('explicit current, synthetic, and historical pruning links are not silently replaced',()=>{
  for(const query of ['?run=chosen&question=chosen_answer','?run=synthetic','?pruning=historical_preview']){
    const h=harness(query);h.configure({reviewer_entry:entry,runs:[]});assert.deepEqual(h.calls.replace,[]);
  }
});
test('empty installation never auto-builds or promotes a synthetic entry',()=>{
  const h=harness();h.configure({reviewer_entry:{...entry,data_kind:'synthetic_demo'},runs:[]});
  assert.deepEqual(h.calls.replace,[]);assert.deepEqual(h.calls.fetch,[]);
  assert.equal(h.$('reviewerAnswer').disabled,true);assert.equal(h.$('reviewerOffline').hidden,false);
  assert.match(text(h.$('reviewerHomeStatus')),/No real reviewer workspace/);
});
test('a genuinely synthetic workspace keeps its warning even when a real example exists',()=>{
  const h=harness('?run=invented');h.context.graph={data_kind:'synthetic_demo'};h.context.runId='invented';h.configure({reviewer_entry:entry,runs:[]});
  assert.match(text(h.$('reviewerDataLabel')),/Invented offline records/);
  assert.match(text(h.$('reviewerHomeTitle')),/invented offline/);
  assert.match(text(h.$('reviewerHomeStatus')),/records are invented/);
});
test('an explicitly opened different cohort does not inherit another cohort companion link',()=>{
  const h=harness('?run=other_cohort');h.context.runId='other_cohort';
  h.context.graph={data_kind:'live_pharos',snapshot_sha256:'b'.repeat(64)};
  h.configure({reviewer_entry:{...entry,snapshot_sha256:'a'.repeat(64)},runs:[]});
  assert.equal(h.$('reviewerExampleLinks').children.length,0);
  assert.equal(h.$('appliedQualificationLinks').children.length,0);
});
test('loaded cited answer and source actions reuse the existing question and exact source claim',()=>{
  const h=harness('?run=real_current');real(h);h.configure({reviewer_entry:entry,runs:[]});
  h.$('reviewerAnswer').onclick();h.$('reviewerSource').onclick();
  assert.deepEqual(h.calls.views,['ask','evidence']);assert.equal(h.$('navQuestion').attributes['aria-current'],'step');
  assert.deepEqual(h.calls.sources,['claim:original']);assert.equal(h.$('sourceGuideSelection').value,'claim:original');
  assert.deepEqual(h.calls.assign,[]);assert.deepEqual(h.calls.fetch,[]);
});
test('applied graph counts are read from actual saved graph, including unresolved retained decisions',()=>{
  const h=harness('?run=real_retained');h.context.graph={data_kind:'live_pharos',qualified_view:{baseline_evidence_edges:11,retained_evidence_edges:8},summary:{dispositions:{keep:2,prune:3,abstain:6}}};
  h.context.runId='real_retained';
  h.configure({reviewer_entry:entry,runs:[]});const content=text(h.$('appliedQualificationSummary'));
  assert.match(content,/11 → 8/);assert.match(content,/3 records excluded/);assert.match(content,/Unresolved and retained: 6/);
  assert.match(content,/not automatically a biologically false/);assert.doesNotMatch(content,/298|16,985|16,687/);
  assert.equal(h.$('appliedQualificationLinks').children.length,0,'Do not send a reviewer back to the same applied workspace.');
});
test('source-bound qualification reason is readable, preserves unknown clauses and rejects stale counts',()=>{
  const h=harness('?run=real_retained');h.context.graph={data_kind:'live_pharos',qualified_view:{baseline_evidence_edges:11,retained_evidence_edges:8},summary:{}};
  const summary={baseline_records:11,retained_records:8,excluded_records:3,abstained_records:6,reason_groups:[{decision:'prune',records:3,reason:'Only obsolete identifiers excluded; other pathway claims remain unknown'}],interpretation:'Identifier currency only.'};
  h.context.showQualificationSummary(summary);
  const paragraphs=h.$('appliedQualificationSummary').children.filter(n=>n.tagName==='P');
  assert.ok(paragraphs.some(n=>n.textContent==='3 excluded: Only obsolete identifiers excluded; other pathway claims remain unknown'));
  h.context.showQualificationSummary({...summary,baseline_records:12});
  assert.doesNotMatch(text(h.$('appliedQualificationSummary')),/Only obsolete identifiers excluded/);
});
test('catalogue URLs cannot navigate to external endpoints or mutate query scope',()=>{
  for(const url of ['https://evil.invalid/?run=real','//evil.invalid/?run=real','/?run=real&token=secret','/api/run/real','/?run=../../bad']){
    const h=harness();h.configure({reviewer_entry:{...entry,example_url:url},runs:[]});assert.deepEqual(h.calls.replace,[]);
  }
});
test('catalogue accepts only a syntactically bounded recorded-agent link and preserves the manual question',()=>{
  const h=harness();h.configure({reviewer_entry:{...entry,example_url:'/?run=real_current&question=cited_current&agent_job=source_agent_recorded'},runs:[]});
  assert.deepEqual(h.calls.replace,['/?run=real_current&question=cited_current&agent_job=source_agent_recorded&view=data']);
  // Actual source match and live-vs-injected provenance are rechecked by the
  // separate source-agent reader before it opens any recorded result.
  for(const suffix of ['agent_job=','agent_job=plan_recorded','agent_job=..%2Foutside',
    'agent_job=source_agent_a&agent_job=source_agent_b','agent_job=source_agent_'+'a'.repeat(68)]){
    const bad=harness();bad.configure({reviewer_entry:{...entry,example_url:'/?run=real_current&'+suffix},runs:[]});assert.deepEqual(bad.calls.replace,[]);
  }
});
test('an unavailable registered agent is visible while the manual reader remains available',()=>{
  const h=harness('?run=real_current');real(h);
  h.configure({reviewer_entry:{...entry,agent_entry_unavailable:true,note:'The featured agent record could not be verified. The guided source reader remains available.'},runs:[]});
  assert.match(text(h.$('reviewerHomeStatus')),/featured agent record could not be verified/);
  assert.equal(h.$('reviewerHomeStatus').className,'notice warn');assert.equal(h.$('reviewerAnswer').disabled,false);
  assert.deepEqual(h.calls.replace,[]);
});
test('shared reviewer mode exposes no invented builder route on empty setup',()=>{
  const h=harness('',true);h.configure({reviewer_entry:null,runs:[]});assert.equal(h.$('reviewerOffline').hidden,true);
  h.$('reviewerOpenOffline').onclick();assert.equal(h.$('controls').open,false);
});
test('historical pruning catalogue does not auto-select a graph or rewrite a fresh page URL',async()=>{
  const h=harness();vm.runInContext(fs.readFileSync(path.join(root,'biograph_steward/pruning.js'),'utf8'),h.context);
  const loaded=[];h.context.loadPruningAssessment=async(...args)=>loaded.push(args);
  await h.context.loadPruningAssessments();
  assert.deepEqual(h.calls.fetch,['/api/pruning-previews']);assert.deepEqual(loaded,[]);assert.deepEqual(h.calls.history,[]);
  const explicit=harness('?pruning=historical_preview');vm.runInContext(fs.readFileSync(path.join(root,'biograph_steward/pruning.js'),'utf8'),explicit.context);
  explicit.context.loadPruningAssessment=async(...args)=>loaded.push(args);await explicit.context.loadPruningAssessments();assert.equal(loaded[0][0],'historical_preview');
});
test('actual page keeps construction collapsed and reviewer steps separate from research history',()=>{
  const html=fs.readFileSync(path.join(root,'biograph_steward/ui.html'),'utf8');
  assert.match(html,/<details id="controls" class="card">/);assert.doesNotMatch(html,/<details id="controls"[^>]*\bopen\b/);
  for(const label of ['Start here','Question &amp; graph','Inspect sources','What changed','Read the cited answer','Inspect its source'])assert.ok(html.includes(label));
  assert.ok(html.includes('id="comparisonPruningControls"'));assert.ok(html.includes('id="appliedQualificationPanel"'));
  assert.equal((html.match(/id="questionText"/g)||[]).length,1);
  assert.ok(html.indexOf('id="questionText"')<html.indexOf('id="customQuestionOptions"'));
  assert.ok(html.includes('id="scientificAssessmentHistory"'));assert.ok(html.includes('Synthetic demonstration only.'));
  const login=fs.readFileSync(path.join(root,'biograph_steward/login.html'),'utf8');assert.match(login,/<h1>BioGraph Steward<\/h1>/);assert.ok(login.includes('name="return_to"'));assert.ok(login.includes('type="password"'));
});

test('a featured agent entry leaves the separate manual card clearly labelled as a source reader',()=>{
 const h=harness();real(h);h.configure({reviewer_entry:{...entry,agent_job_id:'source_agent_recorded',display_title:'Follow a recorded source-agent workflow'},runs:[]});
 assert.equal(h.$('reviewerHomeTitle').textContent,'Guided source reader');
});
