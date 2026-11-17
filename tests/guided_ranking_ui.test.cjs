// Synthetic DOM/state checks. These do not establish biological accuracy or browser layout.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');

function harness(){
  const elements=new Map(),calls=[],urls=[],navigations=[];
  function element(tag='div',text=''){
    const classes=new Set(),listeners={};
    return {tag,tagName:tag.toUpperCase(),textContent:text,children:[],value:'',disabled:false,style:{},dataset:{},listeners,
      classList:{add:x=>classes.add(x),remove:x=>classes.delete(x),toggle(x,on){if(on===undefined)on=!classes.has(x);on?classes.add(x):classes.delete(x);},contains:x=>classes.has(x)},
      append(...items){this.children.push(...items);},replaceChildren(...items){this.children=[...items];},
      querySelector(selector){
        const match=/^option\[value="([^"]+)"\]$/.exec(selector);
        if(!match)throw new Error('Unsupported selector in the synthetic DOM: '+selector);
        return this.children.find(child=>child.tagName==='OPTION'&&child.value===match[1])||null;
      },
      remove(){for(const item of elements.values())item.children=item.children.filter(child=>child!==this);},
      setAttribute(){},addEventListener(type,listener){listeners[type]=listener;},scrollIntoView(){},reportValidity(){return true;}};
  }
  const $=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
  const graph={data_kind:'live_pharos',scope:{kind:'protein_cohort'},targets:[{id:'UniProtKB:P12345',symbol:'AAA'},{id:'UniProtKB:Q12345',symbol:'BBB'}],retrieval:{truncated:false},question_basis_sha256:'basis',nodes:[]};
  for(const [id,value] of Object.entries({questionProtein:'UniProtKB:P12345',questionRelations:'both',questionView:'candidates',questionLimit:'8',questionPaths:'2',questionRanking:'alphabetical'}))$(id).value=value;
  $('questionForm').elements=['questionProtein','questionRelations','questionView','questionLimit','questionPaths','questionRanking','questionRun'].map($);
  const context=vm.createContext({$,graph,runId:'test-run',el:element,svgEl:element,history:{replaceState:(a,b,url)=>urls.push(url)},updateWorkNavigation(){},navigateWork:step=>navigations.push(step),URL,URLSearchParams,
    api:async(url,body)=>{calls.push({url,body});return await context.response;}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../biograph_steward/guided.js'),'utf8'),context);
  // The graph renderer is covered by existing evidence-path behavior, not this control harness.
  vm.runInContext('renderQuestionGraph=()=>{}',context);
  return {$,graph,context,calls,urls,navigations,run:code=>vm.runInContext(code,context)};
}
function answer(h,{physical=false,results}={}){
  return {source_run:'test-run',graph_basis_sha256:'basis',snapshot_sha256:'snapshot',answer_sha256:'answer',
    plan:{protein:{id:'UniProtKB:P12345'},relations:['interactions','shared_pathways'],view:'candidates',max_results:8,max_paths_per_protein:2,...(physical?{ranking:'physical'}:{})},
    ...(physical?{ranking:{source_release:'12.5',retrieved_at:'2026-10-27T12:00:00Z',matching_proteins:2,numeric_scored:1,unranked_proteins:1,states:{numeric:1,unmapped:1},packet_sha256:'ranking-packet',ordering:'Native physical score, unranked last.'}}:{}),
    overview:'Synthetic source statements.',availability:{inspectable_proteins:3},returned_proteins:2,omitted_proteins:1,summary:[],limitations:[],nodes:[],citations:[],results:results||[
      {protein:{id:'UniProtKB:Q12345',sym:'BBB'},review_status:'candidate',paths:[{kind:'interaction'}],physical_priority:{state:'numeric',physical_score:0,functional_score:0.5,source_release:'12.5',has_interaction:true}},
      {protein:{id:'UniProtKB:Q54321',sym:'CCC'},review_status:'accepted',paths:[{kind:'interaction'}],physical_priority:{state:'unmapped',physical_score:null,functional_score:null,source_release:'12.5',has_interaction:true}}]};
}
function bind(h,value){h.context.answer=value;h.run('bindQuestionAnswer(answer,"saved-question")');}
function text(element){return [element.textContent,...element.children.map(text)].join(' ');}
function plain(value){return JSON.parse(JSON.stringify(value));}

test('the existing form exposes one optional order selector and explanatory note',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../biograph_steward/ui.html'),'utf8');
  assert.equal((html.match(/id="questionRanking"/g)||[]).length,1);
  assert.match(html,/<option value="alphabetical">Alphabetical<\/option>/);
  assert.match(html,/>Physical association priority · STRING<\/option>/);
  assert.match(html,/id="questionRankingNote"/);
});
test('alphabetical default preserves the old request shape and physical is explicitly opt in',()=>{
  const h=harness();h.run('setupQuestion()');
  assert.equal(h.$('questionRanking').value,'alphabetical');
  const old={protein:'UniProtKB:P12345',relations:['interactions','shared_pathways'],view:'candidates',max_results:8,max_paths:2};
  assert.deepEqual(plain(h.run('questionOptions()')),old);
  h.$('questionRanking').value='physical';h.run('updateQuestionPlan()');
  assert.deepEqual(plain(h.run('questionOptions()')),{...old,ranking:'physical'});
  assert.match(h.$('questionRankingNote').textContent,/does not prove direct binding/);
  assert.match(h.$('questionRankingNote').textContent,/review states unchanged/);
});
test('all six scope controls invalidate the saved answer and its URL',()=>{
  const h=harness();
  for(const id of ['questionProtein','questionRelations','questionView','questionLimit','questionPaths','questionRanking']){
    bind(h,answer(h,{physical:true}));h.$(id).listeners.change();
    assert.equal(h.run('questionAnswer'),null);assert.equal(h.run('questionId'),null);assert.equal(h.run('questionSelection'),null);
    assert.ok(h.$('questionOutput').classList.contains('hidden'));
    assert.equal(h.urls.at(-1),'?run=test-run');assert.equal(h.$('questionCitation').children.length,0);
  }
});
test('reopening physical answers restores mode and shows native zero without changing source graph',()=>{
  const h=harness(),before=JSON.stringify(h.graph),value=answer(h,{physical:true}),saved=JSON.stringify(value);bind(h,value);
  assert.equal(h.$('questionRanking').value,'physical');
  const output=text(h.$('questionSummary'));
  assert.match(output,/STRING 12\.5 native physical score: 0\.000/);
  assert.match(output,/functional score: 0\.500/);
  assert.match(output,/not direct binding/);
  assert.match(output,/Protein identifier not mapped by STRING/);
  assert.match(output,/not evidence of no interaction/);
  assert.match(output,/1 with native numeric physical scores/);assert.match(output,/1 unranked/);assert.match(output,/STRING retrieval: 2026-10-27/);
  assert.doesNotMatch(output,/Ordering is alphabetical/);
  assert.equal(JSON.stringify(value),saved);assert.equal(JSON.stringify(h.graph),before);
  assert.equal(JSON.parse(h.$('questionTrace').textContent).ranking.source_release,'12.5');
});
test('pathway-only matches remain visible without implying a physical score',()=>{
  const h=harness(),value=answer(h,{physical:true,results:[{protein:{id:'UniProtKB:Q12345',sym:'BBB'},review_status:'accepted',paths:[{kind:'shared_pathway'}],physical_priority:{state:'not_interaction_path',has_interaction:false,physical_score:null}}]});bind(h,value);
  assert.match(text(h.$('questionSummary')),/Pathway-only match — not physically ranked/);
  assert.match(text(h.$('questionSummary')),/Shared pathway annotation does not establish physical association/);
});
test('old saved answers reset a previously selected physical mode to alphabetical',()=>{
  const h=harness();bind(h,answer(h,{physical:true}));bind(h,answer(h));
  assert.equal(h.$('questionRanking').value,'alphabetical');
  assert.match(text(h.$('questionSummary')),/Ordering is alphabetical/);
  assert.doesNotMatch(text(h.$('questionSummary')),/native physical score|Physical association priority/);
  assert.equal(JSON.parse(h.$('questionTrace').textContent).ranking,undefined);
});
test('synthetic demos and nonexact cohorts cannot request physical priority',()=>{
  for(const mutate of [g=>g.data_kind='synthetic_demo',g=>g.data_kind='unknown',g=>g.targets[0].id='SYMBOL:AAA']){
    const h=harness();mutate(h.graph);h.$('questionRanking').value='physical';h.run('updateQuestionPlan()');
    assert.equal(h.$('questionRanking').value,'alphabetical');assert.equal(h.$('questionRanking').disabled,true);
    assert.equal(h.$('questionRankingPhysical').disabled,true);assert.equal(h.run('questionOptions().ranking'),undefined);
    assert.match(h.$('questionRankingNote').textContent,/real Pharos cohort/);
  }
});
test('real disease cohorts permit physical priority but pathway-only queries do not',()=>{
  const h=harness();h.graph.disease={name:'Synthetic disease',mondoID:'MONDO:synthetic'};h.graph.scope={kind:'disease'};
  h.$('questionRanking').value='physical';h.run('updateQuestionPlan()');assert.equal(h.$('questionRanking').value,'physical');
  assert.equal(h.run('questionOptions().ranking'),'physical');
  h.$('questionRelations').value='shared_pathways';h.$('questionRelations').listeners.change();
  assert.equal(h.$('questionRanking').value,'alphabetical');assert.equal(h.$('questionRankingPhysical').disabled,true);
  assert.equal(h.run('questionOptions().ranking'),undefined);assert.match(h.$('questionRankingNote').textContent,/requires reported interaction paths/);
});
test('busy form includes order selector and restores its eligibility after success',async()=>{
  const h=harness();let finish;h.context.response=new Promise(resolve=>finish=resolve);
  h.$('questionRanking').value='physical';const pending=h.run('runQuestion()');
  assert.equal(h.$('questionRanking').disabled,true);assert.equal(h.run('questionBusy'),true);
  assert.equal(h.calls[0].body.ranking,'physical');
  finish({question_id:'saved-question',answer:answer(h,{physical:true})});await pending;
  assert.equal(h.$('questionRanking').disabled,false);assert.equal(h.run('questionBusy'),false);
  assert.equal(h.$('questionRanking').value,'physical');
});
test('a completed empty question opens its visible answer instead of the hidden graph',async()=>{
  for(const empty of [false,true]){
    const h=harness(),result=answer(h,empty?{results:[]}:{}),before=JSON.stringify(h.graph);
    h.context.response={question_id:'saved-question',answer:result};await h.run('runQuestion()');
    assert.deepEqual(h.navigations,[empty?'answer':'graph']);
    assert.equal(h.$('questionGraphSection').classList.contains('hidden'),empty);
    assert.equal(h.$('questionOutput').classList.contains('hidden'),false);
    assert.equal(h.run('questionBusy'),false);assert.equal(JSON.stringify(h.graph),before);
    assert.equal(h.calls.length,1);
  }
});
test('failed retrieval clears the old answer and does not silently show alphabetical results',async()=>{
  const h=harness();bind(h,answer(h));h.$('questionRanking').value='physical';
  h.context.api=async()=>{throw new Error('Source request failed; no result was saved.');};
  await h.run('runQuestion()');
  assert.equal(h.run('questionAnswer'),null);assert.ok(h.$('questionOutput').classList.contains('hidden'));
  assert.match(h.$('questionStatus').textContent,/Source request failed/);
  assert.equal(h.$('questionRanking').value,'physical');assert.equal(h.$('questionRanking').disabled,false);
});


test('native physical source uses the existing relationship selector and stays separate from live ranking',()=>{
  const h=harness();h.graph.evidence_extension={sources:{string_physical:{publication_sha256:'invented-native-source',policy:'invented-source-policy'}}};
  h.run('setupQuestion()');
  assert.equal(h.$('questionRelations').querySelector('option[value="native_physical"]').textContent,'Native STRING physical associations');
  assert.equal(h.$('questionRelations').value,'both','Adding a source does not silently replace the default functional question.');
  h.$('questionRelations').value='native_physical';h.$('questionRanking').value='physical';h.run('updateQuestionPlan()');
  assert.equal(h.$('questionRanking').value,'alphabetical');assert.equal(h.$('questionRanking').disabled,true);
  assert.deepEqual(plain(h.run('questionOptions()')),{protein:'UniProtKB:P12345',relations:['interactions'],template:'native_string_physical.v1',view:'candidates',max_results:8,max_paths:2});
  assert.match(h.$('questionPlan').textContent,/identical complete reference sequences/);
  assert.match(h.$('questionRankingNote').textContent,/no live STRING request/);
  assert.match(h.$('questionRankingNote').textContent,/unresolved identities are unknown/);
  assert.equal(h.calls.length,0);
  delete h.graph.evidence_extension;h.run('setupQuestion()');
  assert.equal(h.$('questionRelations').querySelector('option[value="native_physical"]'),null);
});

test('reopening a native physical answer restores its source mode and preserves review wording',()=>{
  const h=harness();h.graph.evidence_extension={sources:{string_physical:{publication_sha256:'invented-native-source'}}};h.run('setupQuestion()');
  const value=answer(h);value.template='native_string_physical.v1';value.plan.relations=['interactions'];
  bind(h,value);
  assert.equal(h.$('questionRelations').value,'native_physical');
  assert.equal(h.$('questionRanking').value,'alphabetical');
  assert.match(h.$('questionModeBadge').textContent,/Native physical source.*candidates require review/);
  assert.doesNotMatch(text(h.$('questionSummary')),/Physical association priority/);
  assert.equal(h.calls.length,0);
});


test('operator-owned saved review mode hides live priority and disables new decision export without changing graph',()=>{
  const h=harness(),before=JSON.stringify(h.graph);h.context.appCapabilities={saved_data_only:true};
  h.graph.evidence_extension={sources:{string_physical:{publication_sha256:'invented-native-source'}}};
  const withProfile=JSON.stringify(h.graph);
  h.run('setupQuestion();applySavedReviewControls()');
  h.$('questionRanking').value='physical';h.run('updateQuestionPlan()');
  assert.equal(h.$('questionRankingPhysical').hidden,true);assert.equal(h.$('questionRankingPhysical').disabled,true);
  assert.equal(h.$('questionRanking').value,'alphabetical');
  assert.equal(h.$('submissionExport').disabled,true);
  assert.match(h.$('submissionStatus').textContent,/Download the saved run ZIP.*does not create new decision exports/);
  assert.ok(h.$('controls').classList.contains('hidden'));assert.ok(h.$('plannerPanel').classList.contains('hidden'));
  assert.ok(h.$('civicRetrievePanel').classList.contains('hidden'));
  for(const id of ['assayAsk','civicRun','biologicalAsk','regulatoryAsk','regulatoryExampleMcc','regulatoryExampleBraf','regulatoryExampleContext'])assert.equal(h.$(id).disabled,true);
  for(const id of ['assayQuestionControls','civicForm','regulatoryForm'])assert.ok(h.$(id).classList.contains('hidden'));
  assert.match(h.$('biologicalStatus').textContent,/Open saved answers or inspect source records/);
  h.$('questionRelations').value='native_physical';h.run('updateQuestionPlan()');
  assert.equal(h.run('questionOptions().template'),'native_string_physical.v1');
  assert.equal(JSON.stringify(h.graph),withProfile);assert.equal(h.calls.length,0);
});

test('automatic exact saved-question reopen preserves its agent link while changed scopes clear it',()=>{
 const h=harness();
 h.context.location={search:'?run=test-run&question=saved-question&agent_job=source_agent_recorded&view=data'};
 bind(h,answer(h));assert.equal(h.urls.at(-1),'?run=test-run&question=saved-question&agent_job=source_agent_recorded&view=data');
 assert.equal(h.run('savedQuestionURL("new-question")'),'?run=test-run&question=new-question');
 for(const search of ['?run=other&question=saved-question&agent_job=source_agent_recorded','?run=test-run&question=saved-question&agent_job=..%2Foutside','?run=test-run&question=saved-question&agent_job=source_agent_a&agent_job=source_agent_b']){h.context.location.search=search;assert.equal(h.run('savedQuestionURL("saved-question")'),'?run=test-run&question=saved-question');}
 h.context.location.search='?run=test-run&question=saved-question&agent_job=source_agent_recorded&view=data';
 h.run('setupQuestion()');h.$('questionRelations').listeners.change();assert.equal(h.urls.at(-1),'?run=test-run');
});
