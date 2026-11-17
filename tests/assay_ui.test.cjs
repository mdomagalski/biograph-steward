// Synthetic DOM/state checks. These do not establish browser layout or usability.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');

function harness() {
  const elements = new Map(), urls = [], calls = [], fetches=[];
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
    study:'pubmed:99999999',
    assay_status:'curated_negative',evaluable:true,graph_edge_id:'edge:1',source_file:'source/40075158.txt',
    display:{citations:[{label:'Synthetic PMID',url:'https://pubmed.ncbi.nlm.nih.gov/99999999/'}],
      field_groups:[{group:'roles_and_experimental_context',text:'Synthetic host; A is prey and B is bait.',
        fields:[{label:'Assay host',value:'Synthetic host',columns:[29]}]}]}};
  const graph={scope:{kind:'protein_cohort'},data_kind:'live_pharos',db_version:'pharos319',assay_evidence:{source_kind:'intact_mitab27',source_accounting:{source_evidence_rows:1,excluded_evidence:0}},
    assay_observations:[observation],targets:observation.products.map(id=>({id})),edges:[],assertions:[],
    question_basis_sha256:'basis',snapshot_sha256:'snapshot',assay_attachment_sha256:'attachment',assay_publication_sha256:'publication'};
  const context=vm.createContext({$,graph,runId:'synthetic-run',URL,
    el:element,table:(headers,rows)=>({headers,rows}),nodeLabel:x=>x,
    document:{createTextNode:text=>element('text',text),getElementById:$},
    history:{replaceState:(a,b,url)=>urls.push(url)},switchQuestionWorkflow(){},updateWorkNavigation(){},
    navigateWork(){},loadSavedWork(){},api:async(url,body)=>{calls.push({url,body});return context.response;},
    fetch:async url=>{fetches.push(url);return context.fetchResponse||{ok:true,json:async()=>({status:'unavailable',source_run:'synthetic-run'})};}});
  $('assayProtein').value='all';$('assayOutcome').value='all';$('questionWorkflow').value='connections';
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../biograph_steward/assay.js'),'utf8'),context);
  return {$,context,graph,observation,urls,calls,fetches};
}

function reuse(h,overrides={}){return {status:'available',source_run:'synthetic-run',graph_basis_sha256:'basis',
  snapshot_sha256:'snapshot',assay_attachment_sha256:'attachment',assay_publication_sha256:'publication',
  observations:[{observation_id:h.observation.id,products:[...h.observation.products],study:h.observation.study,
    current_string_status:'confirmed_user_assisted',provider:'STRING',provider_version:'12.5',
    record_ids:['imex:IM-INVENTED-1','intact:EBI-INVENTED-1'],historical_pharos_reuse:null,
    explanation:'Synthetic source-link trace.',observation_provenance:'user_assisted_source_link',
    evidence_links:[{label:'Synthetic source record',url:'https://www.ebi.ac.uk/intact/query/IM-INVENTED-1'}]}],
  report_url:'/api/assay-source-reuse/synthetic-run/report.html',...overrides};}
function serveReuse(h,value){h.context.fetchResponse={ok:true,json:async()=>value};}
function textOf(element){return JSON.stringify(element.children);}
async function setup(h){return vm.runInContext('setupAssay()',h.context);}

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

test('source reuse is scoped to current STRING and displayed without changing the graph or answer',async()=>{
  const h=harness(),graphBefore=JSON.stringify(h.graph);serveReuse(h,reuse(h));await setup(h);
  assert.deepEqual(h.fetches,['/api/assay-source-reuse/synthetic-run']);
  const table=h.$('assayRows').children[0];assert.equal(table.headers[3],'Source reuse');
  assert.match(table.rows[0].cells[3].textContent,/Shared record in current STRING 12\.5 \(user-assisted\)/);
  h.context.row=h.observation;vm.runInContext('inspectAssay(row)',h.context);
  const inspected=textOf(h.$('assayInspector'));
  assert.match(inspected,/original pharos319 import remains unresolved/);
  assert.match(inspected,/not an independent replication/);
  assert.match(inspected,/Synthetic host/);assert.match(inspected,/Synthetic source record/);
  assert.match(inspected,/\/api\/assay-source-reuse\/synthetic-run\/report\.html/);
  assert.match(inspected,/\/api\/download\/synthetic-run/);
  assert.match(inspected,/Saved-answer JSON and graph\/decision exports retain their existing contents/);
  const saved=answer(h),before=JSON.stringify(saved);h.context.answer=saved;vm.runInContext('bindAssayAnswer(answer,"saved-answer")',h.context);
  assert.match(textOf(h.$('assayAnswerRecords')),/Shared record in current STRING 12\.5/);
  assert.match(textOf(h.$('assayAnswerRecords')),/Synthetic host/);
  assert.equal(JSON.stringify(saved),before);assert.equal(JSON.stringify(h.graph),graphBefore);
  assert.equal(h.$('assayRows').children[0].rows[0].cells[1],'curated negative');
});

test('an unresolved second record is never labelled as absent or independent',async()=>{
  const h=harness(),value=reuse(h);value.observations[0].current_string_status='unknown_not_observed';
  value.observations[0].observation_provenance='not_observed';serveReuse(h,value);await setup(h);
  h.context.row=h.observation;vm.runInContext('inspectAssay(row)',h.context);
  const text=textOf(h.$('assayInspector'));assert.match(text,/Current STRING reuse unresolved/);
  assert.match(text,/does not establish that it is absent from STRING/);
  assert.doesNotMatch(text,/Shared record in current STRING/);
});

test('missing annotation and failed verification remain distinct and preserve records',async()=>{
  const h=harness();await setup(h);
  assert.equal(h.$('assayRows').children[0].rows.length,1);
  assert.equal(h.$('assayRows').children[0].rows[0].cells[3].textContent,'No verified source-reuse annotation');
  h.context.fetchResponse={ok:false,json:async()=>({error:'Synthetic invalid proof'})};await setup(h);
  assert.equal(h.$('assayRows').children[0].rows.length,1);
  assert.match(h.$('assayRows').children[0].rows[0].cells[3].textContent,/could not be verified/);
  h.context.row=h.observation;vm.runInContext('inspectAssay(row)',h.context);
  assert.match(textOf(h.$('assayInspector')),/No shared-record conclusion is displayed/);
  assert.doesNotMatch(textOf(h.$('assayInspector')),/Download run ZIP with audit and proof/);
});

test('every source binding and exact observation identity must match before showing a flag',async()=>{
  const mutations=[
    value=>value.source_run='other-run',value=>value.graph_basis_sha256='other-review',
    value=>value.snapshot_sha256='other-snapshot',value=>value.assay_attachment_sha256='other-attachment',
    value=>value.assay_publication_sha256='other-publication',value=>value.observations[0].observation_id='invented:other',
    value=>value.observations[0].products=['UniProtKB:P12345','UniProtKB:OTHER'],
    value=>value.observations[0].study='pubmed:other',value=>value.observations.push({...value.observations[0]}),
    value=>value.observations[0].provider_version='other',value=>value.observations[0].historical_pharos_reuse=true,
    value=>value.observations[0].observation_provenance='not_observed',value=>value.report_url='/api/download/other-run'
  ];
  for(const mutate of mutations){const h=harness(),value=reuse(h);mutate(value);serveReuse(h,value);await setup(h);
    assert.match(h.$('assayRows').children[0].rows[0].cells[3].textContent,/could not be verified/);}
});

test('async reuse updates retain selected assay context and saved answer views',async()=>{
  const h=harness();let release;h.context.fetchResponse=new Promise(resolve=>{release=resolve;});
  const pending=setup(h);h.context.row=h.observation;vm.runInContext('inspectAssay(row)',h.context);
  const inspector=h.$('assayInspector').children,contextSection=inspector.find(item=>item.dataset?.fieldGroup);
  h.context.answer=answer(h);vm.runInContext('bindAssayAnswer(answer,"saved-answer")',h.context);
  // Reopen the inspector after the answer's existing filter reset.
  vm.runInContext('inspectAssay(row)',h.context);const selected=h.$('assayInspector').children;
  release({ok:true,json:async()=>reuse(h)});await pending;
  assert.equal(h.$('assayInspector').children,selected);
  assert.match(textOf(h.$('assayInspector')),/Shared record in current STRING/);
  assert.match(textOf(h.$('assayAnswerRecords')),/Shared record in current STRING/);
  assert.match(textOf(h.$('assayInspector')),/Synthetic host/);assert.ok(contextSection);
});

test('a late response from an earlier workspace cannot update the current views',async()=>{
  const h=harness();let release;h.context.fetchResponse=new Promise(resolve=>{release=resolve;});const old=setup(h);
  h.context.runId='new-run';h.context.fetchResponse={ok:true,json:async()=>({status:'unavailable',source_run:'new-run'})};await setup(h);
  release({ok:true,json:async()=>reuse(h)});await old;
  assert.equal(h.$('assayRows').children[0].rows[0].cells[3].textContent,'No verified source-reuse annotation');
});

test('reuse links reject unsafe schemes credentials and unrelated local routes',async()=>{
  const h=harness(),value=reuse(h);
  value.observations[0].evidence_links.push(...[
    ['Unsafe script','javascript:alert(1)'],['Unsafe credentials','https://name:secret@example.org/proof'],
    ['Other API','/api/download/other-run'],['Supplied download','/api/download/synthetic-run'],['Protocol-relative','//example.org/proof'],
    ['Malformed','http://['],['Safe source','https://example.org/evidence?id=1']
  ].map(([label,url])=>({label,url})));
  serveReuse(h,value);await setup(h);h.context.row=h.observation;vm.runInContext('inspectAssay(row)',h.context);
  const text=textOf(h.$('assayInspector'));assert.match(text,/Safe source/);
  for(const label of ['Unsafe script','Unsafe credentials','Other API','Supplied download','Protocol-relative','Malformed'])assert.ok(!text.includes(label));
  assert.match(text,/Download run ZIP with audit and proof/);assert.match(text,/\/api\/download\/synthetic-run/);
});
