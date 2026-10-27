// Synthetic DOM/state checks. These do not establish browser layout or usability.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');

function harness() {
  const elements = new Map(), urls = [], calls = [];
  function element(tag='div',text='') {
    const value={tag,textContent:text,children:[],options:[],value:'',disabled:false,dataset:{},
      childNodes:[],classList:{toggle(){},add(){},remove(){}},
      append(...items){this.children.push(...items);this.childNodes=this.children;this.options=this.children;},
      replaceChildren(...items){this.children=[...items];this.childNodes=this.children;this.options=this.children;},
      addEventListener(){},focus(){},scrollIntoView(){}};
    return value;
  }
  const $=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
  const observation={id:'invented:1',source_kind:'intact_mitab27',products:['UniProtKB:P12345','UniProtKB:Q12345'],
    assay_status:'curated_negative',evaluable:true,graph_edge_id:'edge:1',source_file:'source/40075158.txt',
    display:{citations:[{label:'Synthetic PMID',url:'https://pubmed.ncbi.nlm.nih.gov/99999999/'}],
      field_groups:[{group:'roles_and_experimental_context',text:'Synthetic host; A is prey and B is bait.',
        fields:[{label:'Assay host',value:'Synthetic host',columns:[29]}]}]}};
  const graph={scope:{kind:'protein_cohort'},data_kind:'live_pharos',assay_evidence:{source_kind:'intact_mitab27'},
    assay_observations:[observation],targets:observation.products.map(id=>({id})),edges:[],assertions:[],
    question_basis_sha256:'basis',assay_attachment_sha256:'attachment'};
  const context=vm.createContext({$,graph,runId:'synthetic-run',URL,
    el:element,table:(headers,rows)=>({headers,rows}),nodeLabel:x=>x,
    document:{createTextNode:text=>element('text',text),getElementById:$},
    history:{replaceState:(a,b,url)=>urls.push(url)},switchQuestionWorkflow(){},updateWorkNavigation(){},
    navigateWork(){},loadSavedWork(){},api:async(url,body)=>{calls.push({url,body});return context.response;}});
  $('assayProtein').value='all';$('assayOutcome').value='all';$('questionWorkflow').value='connections';
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../biograph_steward/assay.js'),'utf8'),context);
  return {$,context,graph,observation,urls,calls};
}

function answer(h){return {template:'qualified_assay_evidence.v1',source_run:'synthetic-run',
  graph_basis_sha256:'basis',assay_attachment_sha256:'attachment',plan:{protein:null},overview:'Synthetic answer',
  source_attachment_summary:{source_kind:'intact_mitab27'},limitations:['Synthetic limitation'],
  results:[{observation_id:'invented:1',citation_id:'E001',local_review_state:'candidate',
    source_observation:h.observation,citations:h.observation.display.citations,
    field_groups:h.observation.display.field_groups}]};}

test('IntAct inspector never enters the Y2H construct or lookup branch',()=>{
  const h=harness();h.context.row=h.observation;vm.runInContext('inspectAssay(row)',h.context);
  const all=JSON.stringify(h.$('assayInspector').children);
  assert.ok(all.includes('Synthetic host'));assert.ok(all.includes('Source-qualified IntAct'));
  assert.ok(!all.includes('activation domain'));assert.ok(!all.includes('construct crosswalk'));
  assert.ok(all.includes('/api/assay-source/synthetic-run/source/40075158.txt'));
});
test('saved qualified answer retains its rows and source fields',()=>{
  const h=harness();h.$('assayOutcome').value='detected';h.context.answer=answer(h);vm.runInContext('bindAssayAnswer(answer,"saved-answer")',h.context);
  assert.equal(h.$('questionWorkflow').value,'assay');assert.equal(h.$('assayProtein').value,'all');
  assert.equal(h.$('assayAnswerGraph').children[0].rows.length,1);
  assert.equal(h.$('assayOutcome').value,'all');assert.equal(h.$('assayRows').children[0].rows.length,1);
  assert.ok(JSON.stringify(h.$('assayAnswerRecords').children).includes('Synthetic host'));
  assert.equal(h.$('assayAnswerDownload').href,'/api/download/saved-answer');
  assert.ok(h.urls[0].includes('&question=saved-answer'));
});
test('a stale source basis is rejected before displaying an answer',()=>{
  const h=harness();h.context.answer={...answer(h),graph_basis_sha256:'other-basis'};
  assert.throws(()=>vm.runInContext('bindAssayAnswer(answer,"saved-answer")',h.context),/different source/);
  assert.equal(h.urls.length,0);
});
test('the question sends exact protein scope and preserves negative records',async()=>{
  const h=harness();h.$('assayProtein').value='UniProtKB:P12345';
  h.context.response={question_id:'saved-answer',answer:{...answer(h),plan:{protein:'UniProtKB:P12345'}}};
  await h.$('assayAsk').onclick();
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls)),[{url:'/api/assay-question',body:{run_id:'synthetic-run',protein:'UniProtKB:P12345'}}]);
  assert.ok(JSON.stringify(h.$('assayAnswerGraph').children).includes('curated_negative'));
});
