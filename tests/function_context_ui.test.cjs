const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');

function element(tag) {return {tag, textContent:'', children:[], style:{}, attributes:{}, value:'',
  append(...nodes) {this.children.push(...nodes); if (tag === 'select' && !this.value) this.value = nodes.find(n => n.tag === 'option')?.value || '';},
  replaceChildren(...nodes) {this.children = [...nodes]; if (tag === 'select') this.value = nodes.find(n => n.tag === 'option')?.value || '';},
  setAttribute(k,v) {this.attributes[k] = String(v);}};}
function text(n) {return n.textContent + ' ' + n.children.map(text).join(' ');}
function nodes(n,tag) {return (n.tag === tag ? [n] : []).concat(...n.children.map(c => nodes(c,tag)));}
function fixture() {
  const c = n => ({protein:'UniProtKB:P' + String(n).padStart(5,'0'),symbol:'GENE' + n,
    raw_STRING_weight:.8,normalized_contribution:.2,source_pair:{pair_id:'pharos319ppi:1:' + n}});
  const answer = {format:'biograph-steward.exact-onehop-LocalPlus-query.v1',
    curated_acceptance:false,uncalibrated_score:true,query:{id:'UniProtKB:P00533',symbol:'EGFR'},
    source_versions:{t0_date:'2023-08-14'},weighted_degree:4,qualified_neighbor_count:12,known_training_term_count:5,
    candidates:[{GO_ID:'GO:0000001',label:'Invented <img src=x>',aspect:'BPO',score:.8,
      contributors:[c(1),c(2),c(3),c(4)]}]};
  const summary = {id:'saved_model',purpose:'Historical example',downloads:{full_qualified_graph:'downloads/graph.json.gz'},
    proteins:[{id:'UniProtKB:P00533',display_label:'EGFR · P00533'},{id:'UniProtKB:Q13948',display_label:'CUX1 · Q13948'}],limitations:['No curator truth claim.']};
  return {answer,summary};
}
function harness(fetch) {
  const ids=['functionContextPanel','functionContextPublication','functionContextProtein','functionContextOpen','functionContextStatus','functionContextBody'];
  const elements = Object.fromEntries(ids.map(id => [id,element(/Publication$|Protein$/.test(id)?'select':'div')]));
  const context=vm.createContext({window:{},document:{getElementById:id=>elements[id],createElement:element,createElementNS:(_,tag)=>element(tag)},fetch});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../biograph_steward/function_context.js'),'utf8'),context);
  context.FunctionContext=context.window.FunctionContext;
  return {context,elements,render(answer=fixture().answer) {context.FunctionContext.render(elements.functionContextBody,answer,fixture().summary,'/api/function-context/saved_model/');}};
}

test('historical model context exposes exact contribution basis without accepting a GO annotation',()=>{
  const ui=harness();ui.render();const body=ui.elements.functionContextBody;
  assert.match(text(body),/Historical model hypotheses/);assert.match(text(body),/no annotation accepted/);
  assert.match(text(body),/not a probability/);assert.match(text(body),/absent from the selected benchmark training set/);
  assert.match(text(body),/not establish a new discovery/);assert.match(text(body),/without native GAF relations/);
  assert.match(text(body),/not establish direct physical binding/);assert.match(text(body),/No publication reference is inferred/);
  assert.equal(nodes(body,'svg').length,1);assert.equal(nodes(body,'img').length,0);
  assert.match(text(body),/Invented <img src=x>/);
  const contributionTable=nodes(body,'table')[1];
  assert.equal(nodes(contributionTable,'tbody')[0].children.length,3);
  const expand=nodes(body,'details').find(d=>text(d.children[0]).includes('all 4 contributions'));
  expand.open=true;expand.ontoggle();expand.ontoggle();
  assert.equal(nodes(expand,'table').length,1);assert.equal(nodes(nodes(expand,'table')[0],'tbody')[0].children.length,4);
  assert.ok(nodes(body,'a').some(a=>a.href==='/api/function-context/saved_model/download/full_qualified_graph'));
});

test('source-qualified isolate abstains and does not draw fictitious neighbors',()=>{
  const {answer}=fixture();answer.query={id:'UniProtKB:Q13948',symbol:'CUX1'};
  answer.candidates=[];answer.state='no_qualified_neighbor_context';answer.weighted_degree=0;
  answer.source_qualification=[{message:'Archived mapping is ambiguous.'}];
  const ui=harness();ui.render(answer);
  assert.match(text(ui.elements.functionContextBody),/Abstained/);
  assert.match(text(ui.elements.functionContextBody),/does not imply that the protein has no biological function/);
  assert.match(text(ui.elements.functionContextBody),/Archived mapping is ambiguous/);
  assert.equal(nodes(ui.elements.functionContextBody,'svg').length,0);
});

test('diagram and leading table rank contributions without changing the saved source order',()=>{
  const {answer}=fixture(), cs=answer.candidates[0].contributors;
  cs[0].normalized_contribution=.1;cs[1].normalized_contribution=.2;
  cs[2].normalized_contribution=.05;cs[3].normalized_contribution=.45;
  const before=JSON.stringify(answer),ui=harness();ui.render(answer);
  const body=ui.elements.functionContextBody,t=nodes(body,'table')[1];
  assert.deepEqual(nodes(t,'tbody')[0].children.map(row=>row.children[0].textContent),['GENE4 · P00004','GENE2 · P00002','GENE1 · P00001']);
  assert.match(text(nodes(body,'svg')[0]),/GENE4/);assert.doesNotMatch(text(nodes(body,'svg')[0]),/GENE3/);
  assert.equal(JSON.stringify(answer),before);
});

test('separate annotation notes identify reuse and obsolete terms without changing historical scores',()=>{
  const {answer,summary}=fixture(),before=JSON.stringify(answer),ui=harness();
  const notes={content_sha256:'a'.repeat(64),queries:{[answer.query.id]:[{query:answer.query.id,GO_ID:'GO:0000001',aspect:'BPO',
    pre_t0_all_evidence:{literal_source_row:true},july2026_goa:{term_deprecated:true,exact_NOT_record_ids:[],
      positive_matches:[{native_record_id:'goa.native:invented',source_line:123,membership:'admitted_ancestor',evidence:'IDA',
        source_term:'GO:0000002',source_relation:'involved_in',product_form:'UniProtKB:P00533-2',extension:'occurs_in(invented:cell)',
        with_from:[],ontology_path:['GO:0000002','GO:0000001'],path_predicates:['is_a'],references:['PMID:123','GO_REF:0000001']}]} }]}};
  ui.context.FunctionContext.render(ui.elements.functionContextBody,answer,summary,'/api/function-context/saved_model/',notes);
  const body=ui.elements.functionContextBody;
  assert.match(text(body),/Obsolete in July 2026/);assert.match(text(body),/already appears in the publisher’s broader pre-t0/);
  assert.match(text(body),/adds no new annotation concept/);assert.match(text(body),/Ancestor context from GO:0000002/);
  assert.match(text(body),/involved_in/);assert.match(text(body),/UniProtKB:P00533-2/);
  assert.match(text(body),/occurs_in\(invented:cell\)/);assert.match(text(body),/0.800000/);
  assert.ok(nodes(body,'a').some(n=>n.href==='https://pubmed.ncbi.nlm.nih.gov/123/'));
  assert.ok(nodes(body,'a').some(n=>n.href==='/api/function-context/saved_model/download/annotation_overlap'));
  assert.equal(JSON.stringify(answer),before);
});

test('catalogue loading never triggers a model query and hides when no registered source exists',async()=>{
  const calls=[];const ui=harness(async url=>{calls.push(url);return {ok:true,json:async()=>({contexts:[]})};});
  await ui.context.initializeFunctionContexts();
  assert.deepEqual(calls,['/api/function-contexts']);assert.equal(ui.elements.functionContextPanel.hidden,true);
  assert.equal(ui.elements.functionContextOpen.disabled,true);
});

test('a baseline ancestor or alias match is not mislabeled as missing annotation context',()=>{
  const {answer,summary}=fixture(),ui=harness();
  const notes={content_sha256:'a'.repeat(64),queries:{[answer.query.id]:[{
    GO_ID:'GO:0000001',aspect:'BPO',pre_t0_all_evidence:{literal_source_row:false,author_admitted:true},
    july2026_goa:{term_deprecated:false,positive_matches:[],exact_NOT_record_ids:[]}}]}};
  ui.context.FunctionContext.render(ui.elements.functionContextBody,answer,summary,'/api/function-context/saved_model/',notes);
  const body=ui.elements.functionContextBody;
  assert.match(text(body),/Implied by broader pre-t0 annotations/);
  assert.match(text(body),/ancestor or alias handling/);
  assert.doesNotMatch(text(body),/No broader pre-t0 match recorded/);
  assert.doesNotMatch(text(body),/No matching term was found in the publisher/);
});

test('changing source selection while a saved query loads cannot display the old response',async()=>{
  const {answer,summary}=fixture(),calls=[];let resolve;
  const pending=new Promise(done=>{resolve=done;});
  const ui=harness(async url=>{calls.push(url);return url==='/api/function-contexts'?{ok:true,json:async()=>({contexts:[summary]})}:pending;});
  await ui.context.initializeFunctionContexts();
  assert.equal(calls.length,1);const request=ui.elements.functionContextOpen.onclick();
  ui.elements.functionContextProtein.value='UniProtKB:Q13948';ui.elements.functionContextProtein.onchange();
  resolve({ok:true,json:async()=>({context_id:'saved_model',answer})});await request;
  assert.equal(ui.elements.functionContextBody.children.length,0);
  assert.equal(ui.elements.functionContextOpen.disabled,false);
});

test('verified query opens only the exact configured GET path and preserves response identity',async()=>{
  const {answer,summary}=fixture(),calls=[];
  const ui=harness(async url=>{calls.push(url);return {ok:true,json:async()=>url==='/api/function-contexts'?{contexts:[summary]}:{context_id:'saved_model',answer}};});
  await ui.context.initializeFunctionContexts();await ui.elements.functionContextOpen.onclick();
  assert.deepEqual(calls,['/api/function-contexts','/api/function-context/saved_model/query/P00533']);
  assert.match(text(ui.elements.functionContextBody),/EGFR/);
  answer.query.id='UniProtKB:P01116';await ui.elements.functionContextOpen.onclick();
  assert.equal(ui.elements.functionContextBody.children.length,0);
  assert.match(ui.elements.functionContextStatus.textContent,/another selection/);
});
