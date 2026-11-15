// Native GO additions use the existing Evidence tab and opt-in source reads.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const clone=value=>JSON.parse(JSON.stringify(value));

function element(tag,value){return {tag,textContent:value===undefined?'':String(value),children:[],disabled:false,
  hidden:false,value:'',listeners:{},attributes:{},
  append(...items){this.children.push(...items);if(tag==='select'&&!this.value)this.value=items.find(x=>x.tag==='option')?.value||'';},
  replaceChildren(...items){this.children=[...items];if(tag==='select')this.value=items.find(x=>x.tag==='option')?.value||'';},
  querySelector(selector){
    assert.match(selector,/^[a-z][a-z0-9]*$/,'This fixture supports literal tag selectors only.');
    for(const child of this.children){
      if(child.tag===selector)return child;
      const match=child.querySelector(selector);if(match)return match;
    }
    return null;
  },
  addEventListener(name,callback){this.listeners[name]=callback;},setAttribute(key,value){this.attributes[key]=value;},
  get options(){return this.children.filter(x=>x.tag==='option');}};}
function text(node){return node.textContent+' '+node.children.map(text).join(' ');}
function descendants(node,tag){return (node.tag===tag?[node]:[]).concat(...node.children.map(child=>descendants(child,tag)));}
function fixture(){
  const protein='UniProtKB:P04637';
  const record=n=>({observation_id:'invented:'+n,native_record_id:'goa.native:'+n,source_line:10+n,
    source_gaf_sha256:'e'.repeat(64),evidence_code:'IDA',assigned_by:'SYNTHETIC',
    reference_identifiers:['PMID:'+n,'OTHER:alias'],citations:[{id:'PMID:'+n,url:'https://pubmed.ncbi.nlm.nih.gov/'+n+'/'},{id:'OTHER:alias',url:null}],
    native_record:{raw_line:'Invented literal <img src=x onerror="bad()">'},source_observation:{id:'invented:'+n}});
  const rows=[record(1),record(2)];
  const answer={format:'biograph-steward.native-go-question.v1',template:'native_go_evidence.v1',source_run:'invented_run',
    snapshot_sha256:'a'.repeat(64),evidence_extension_sha256:'b'.repeat(64),source_publication_sha256:'c'.repeat(64),
    anchor:protein,view:'candidates',interpretation:'Native source records, no independent validation.',
    summary:{matching_concepts:1,matching_native_records:2,returned_concepts:1,offset:0,limit:25,search:'',next_offset:null},
    concepts:[{assertion_id:'assertion:invented',subject:protein,subject_label:'TP53',go_id:'GO:0000001',go_label:'Invented process',
      relation_literal:'acts_upstream_of',local_review_state:'candidate',native_record_count:2,records:rows}],records:rows};
  const graph={snapshot_sha256:answer.snapshot_sha256,evidence_extension_sha256:answer.evidence_extension_sha256,
    evidence_extension:{sources:{goa:{publication_sha256:answer.source_publication_sha256}}},
    targets:[{id:protein}],extension_observations:[{source_kind:'goa',subject:protein,graph_edge_id:'invented:edge'}]};
  return {protein,answer,graph};
}
function harness(apiImpl){
  const ids=['nativeGoaPanel','nativeGoaRows','nativeGoaAnswer','nativeGoaStatus','nativeGoaSearch','nativeGoaView',
    'nativeGoaProtein','nativeGoaAsk','nativeGoaPrev','nativeGoaNext','nativeGoaPage','nativeGoaDownload','nativeGoaForm','sourceGuide'];
  const elements=Object.fromEntries(ids.map(id=>[id,element(id==='nativeGoaProtein'||id==='nativeGoaView'?'select':'div')]));
  elements.nativeGoaPanel=element('details');
  elements.nativeGoaPanel.append(element('summary','Recovered native GO annotations'),
    element('p','Read separately sourced GO curator annotations with their recorded relation and references. Candidate records require review; no disease context is inferred.'),
    elements.nativeGoaForm,elements.nativeGoaStatus,elements.nativeGoaAnswer);
  const calls=[],downloads=[],urls=[],revoked=[],inspection=[];
  const {graph,protein}=fixture();
  const context=vm.createContext({$:id=>elements[id],graph,runId:'invented_run',nodeIndex:new Map([[protein,{sym:'TP53'}]]),
    el:(tag,value)=>{const e=element(tag,value);e.click=()=>downloads.push({href:e.href,download:e.download});return e;},
    document:{createTextNode:value=>element('text',value)},api:async(url,body)=>{calls.push({url,body:clone(body)});return apiImpl(url,body);},
    guideLink:({label,url})=>Object.assign(element('a',label),{href:url}),
    biologicalCitation:c=>c?.url&&/^https:\/\//.test(c.url)?Object.assign(element('a',c.id),{href:c.url}):null,
    loadSourceGuide:id=>inspection.push(id),
    Blob:class{constructor(parts,options){this.parts=parts;this.options=options;}},
    URL:{createObjectURL(blob){urls.push(blob);return 'blob:invented';},revokeObjectURL(url){revoked.push(url);}},
    setTimeout:callback=>{callback();return 1;}});
  elements.sourceGuide.scrollIntoView=()=>{};
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../biograph_steward/goa.js'),'utf8'),context);
  return {context,elements,calls,downloads,urls,revoked,inspection,setup(){context.setupNativeGoa();},
    run(){return context.runNativeGoaQuestion();},render(answer){context.renderNativeGoaAnswer(answer);}};
}

test('native addition controls are opt-in, hide on unrelated workspaces and retain exact protein IDs',()=>{
  const ui=harness(async()=>{throw new Error('No automatic read');});ui.setup();
  assert.equal(ui.elements.nativeGoaPanel.hidden,false);assert.equal(ui.elements.nativeGoaProtein.value,'UniProtKB:P04637');
  assert.equal(ui.elements.nativeGoaAsk.disabled,false);assert.equal(ui.calls.length,0);
  ui.context.graph.extension_observations=[];ui.setup();
  assert.equal(ui.elements.nativeGoaPanel.hidden,true);assert.equal(ui.elements.nativeGoaAsk.disabled,true);assert.equal(ui.calls.length,0);
});

test('location profile explains all-code evidence and switching workspaces restores recovery wording',()=>{
  const ui=harness(async()=>{throw new Error('No automatic read');});
  const panel=ui.elements.nativeGoaPanel,source=ui.context.graph.evidence_extension.sources.goa;
  source.policy='complete-cohort-positive-active-CC-located-in-all-codes.v1';ui.setup();
  assert.equal(panel.querySelector('summary').textContent,'Native GO locations');
  assert.match(panel.querySelector('p').textContent,/positive active cellular-component located_in/);
  assert.match(panel.querySelector('p').textContent,/All supplied evidence codes remain visible/);
  assert.match(panel.querySelector('p').textContent,/not necessarily experimental or manually reviewed/);
  assert.match(panel.querySelector('p').textContent,/Candidates require review/);
  for(const legacy of ['complete-go-frame-explicit-active-replacement-native-annotations.v1',undefined]){
    if(legacy===undefined)delete source.policy;else source.policy=legacy;
    ui.setup();
    assert.equal(panel.querySelector('summary').textContent,'Recovered native GO annotations');
    assert.match(panel.querySelector('p').textContent,/separately sourced GO curator annotations/);
    assert.doesNotMatch(panel.querySelector('p').textContent,/All supplied evidence codes/);
  }
  assert.equal(ui.calls.length,0,'Changing source-profile copy never queries or promotes evidence.');
});

test('accepted-only empty result stays explicit and never renders candidates',async()=>{
  const {answer}=fixture();answer.view='accepted';answer.concepts=[];answer.records=[];
  answer.summary={matching_concepts:0,matching_native_records:0,returned_concepts:0,offset:0,limit:25,search:'',next_offset:null};
  const ui=harness(async()=>answer);ui.setup();ui.elements.nativeGoaView.value='accepted';await ui.run();
  assert.deepEqual(ui.calls,[{url:'/api/native-go-question',body:{run_id:'invented_run',protein:'UniProtKB:P04637',view:'accepted',search:'',offset:0,limit:25}}]);
  assert.match(text(ui.elements.nativeGoaRows),/No accepted native GO annotation/);
  assert.equal(descendants(ui.elements.nativeGoaRows,'article').length,0);
});

test('two native records share one concept card while relation and exact references remain visible',async()=>{
  const {answer}=fixture(),ui=harness(async()=>answer);ui.setup();await ui.run();
  assert.equal(descendants(ui.elements.nativeGoaRows,'article').length,1);
  const card=descendants(ui.elements.nativeGoaRows,'article')[0];
  const recordDetails=card.children.filter(node=>node.tag==='details');
  assert.equal(recordDetails.length,2);
  for(const record of recordDetails){
    assert.equal(record.children.some(node=>node.tag==='pre'),false,'Technical raw source stays collapsed inside the record.');
    assert.ok(record.children.some(node=>node.tag==='details'&&node.children.some(child=>
      child.tag==='summary'&&child.textContent.startsWith('Technical source record'))));
  }
  assert.match(text(ui.elements.nativeGoaRows),/acts_upstream_of/);assert.match(text(ui.elements.nativeGoaRows),/Local review: candidate/);
  assert.match(text(ui.elements.nativeGoaRows),/OTHER:alias/);assert.match(text(ui.elements.nativeGoaRows),/not independent experiment counts/);
  const links=descendants(ui.elements.nativeGoaRows,'a');
  assert.equal(links.filter(a=>a.href.startsWith('https://pubmed.ncbi.nlm.nih.gov/')).length,2);
  assert.equal(links.some(a=>a.href.includes('OTHER:alias')),false);
  assert.equal(descendants(ui.elements.nativeGoaRows,'img').length,0);assert.match(text(ui.elements.nativeGoaRows),/<img src=x onerror="bad\(\)">/);
  const inspect=descendants(ui.elements.nativeGoaRows,'button').find(n=>n.textContent==='Inspect source and recorded conditions');inspect.onclick();
  assert.deepEqual(ui.inspection,['assertion:invented']);
});

test('changed workspace, snapshot, publication or selection cannot display a stale answer',async()=>{
  for(const mutate of [ui=>{ui.context.runId='other';},ui=>{ui.context.graph.snapshot_sha256='other';},
    ui=>{ui.context.graph.evidence_extension_sha256='other';},ui=>{ui.context.graph.evidence_extension.sources.goa.publication_sha256='other';},
    ui=>{ui.context.invalidateNativeGoa();}]){
    const {answer}=fixture();let resolve;const pending=new Promise(done=>{resolve=done;});
    const ui=harness(async()=>pending);ui.setup();const request=ui.run();mutate(ui);resolve(answer);await request;
    assert.equal(descendants(ui.elements.nativeGoaRows,'article').length,0);
  }
});

test('mismatched response or source failure never uses a fallback or renders an answer',async()=>{
  for(const failure of [async()=>{throw new Error('Preserved source unavailable.');},
    async()=>({...fixture().answer,source_run:'wrong'}),async()=>({...fixture().answer,format:'wrong'}),
    async()=>({...fixture().answer,anchor:'other'}),async()=>({...fixture().answer,view:'accepted'})]){
    const ui=harness(failure);ui.setup();await ui.run();
    assert.equal(ui.calls.length,1);assert.equal(descendants(ui.elements.nativeGoaRows,'article').length,0);
    assert.equal(ui.elements.nativeGoaAnswer.hidden,true);
  }
});

test('only the current shown answer can be downloaded after source controls change',async()=>{
  const {answer}=fixture(),ui=harness(async()=>answer);ui.setup();await ui.run();ui.elements.nativeGoaDownload.onclick();
  assert.deepEqual(ui.downloads,[{href:'blob:invented',download:'native_go_answer_page.json'}]);
  assert.deepEqual(JSON.parse(ui.urls[0].parts[0]),answer);assert.deepEqual(ui.revoked,['blob:invented']);
  ui.context.invalidateNativeGoa();ui.elements.nativeGoaDownload.onclick();assert.equal(ui.downloads.length,1);
});
