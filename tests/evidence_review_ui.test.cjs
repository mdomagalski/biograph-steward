// Exercise the existing review fork from readable source inspection, without new permissions.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const root=path.join(__dirname,'..');
const navigation=fs.readFileSync(path.join(root,'biograph_steward/navigation.js'),'utf8');
const html=fs.readFileSync(path.join(root,'biograph_steward/ui.html'),'utf8');
function harness({shared=false,qualified=false,source='source_run',subject='UniProtKB:P05067'}={}){
  class Element{
    constructor(tag,text=''){this.tag=tag;this.textContent=String(text);this.children=[];this.value='';this.hidden=false;this.disabled=false;this.attributes={};this.listeners={};this.style={};this.classList={toggle(){}};}
    append(...items){this.children.push(...items);}prepend(...items){this.children.unshift(...items);}replaceChildren(...items){this.children=[...items];}
    setAttribute(key,value){this.attributes[key]=String(value);}addEventListener(name,fn){this.listeners[name]=fn;}
    get options(){return this.children;}scrollIntoView(value){this.scrolled=value;}focus(value){this.focused=value||true;}
  }
  const elements=new Map(),element=(tag,value)=>new Element(tag,value),ids=['inspectionDetails','evidenceView','assertionFamily','assertionProtein','inspector','sourceGuideStatus','workspaceReviewMode','localReviewHelp'];
  for(const id of ids)elements.set(id,element('div'));elements.get('assertionProtein').append(Object.assign(element('option'),{value:'all'}),Object.assign(element('option'),{value:'UniProtKB:P05067'}));
  const assertion={id:'claim:invented',subject,object:'GO:0005634',kind:'native_go_annotation',predicate:'biograph:has_native_go_annotation',lifecycle_state:'candidate',validation_status:'valid',normalization_notes:[],origin_note:'Invented UI control',qualifiers:{species:'NCBITaxon:9606'},evidence_edge_ids:[],review_history:[],allowed_transitions:['provisional','rejected']};
  const graph={snapshot_sha256:'snapshot-for-UI-check',snapshot_created_at:'recorded',db_version:'invented',qualified_view:qualified,assertions:[assertion],edges:[]};
  const original=JSON.stringify(graph),calls=[],statuses=[],tabs=[{dataset:{tab:'assertions'},classList:{toggle(){}}}];
  const context=vm.createContext({graph,runId:source,tablePage:5,activeTab:'targets',
    savedReviewOnly:()=>shared,el:element,nodeLabel:x=>x,relationLabel:x=>x,
    $:id=>elements.get(id)||find(elements.get('inspector'),n=>n.id===id),
    document:{querySelectorAll:()=>tabs,createTextNode:value=>element('text',value)},
    revealWorkspaceTarget:target=>{target.revealed=true;return true;},render:()=>calls.push({kind:'render'}),
    history:{replaceState:(...args)=>calls.push({kind:'history',url:args[2]})},status:text=>statuses.push(text),
    api:async(url,body)=>{calls.push({kind:'api',url,body:JSON.parse(JSON.stringify(body))});const changed=JSON.parse(original);changed.assertions[0].lifecycle_state=body.state;return {run_id:'reviewed_copy',graph:changed};},
    showGraph:value=>{context.graph=value;},evidenceCard:()=>element('div')});
  vm.runInContext(navigation.slice(navigation.indexOf('function reviewWorkspaceMode(){'),navigation.indexOf('function renderSourceGuide(result){')),context);
  vm.runInContext(html.slice(html.indexOf('function inspectAssertion(id){'),html.indexOf('\nfunction inspectNode(',html.indexOf('function inspectAssertion(id){'))),context);
  return {context,elements,assertion,graph,original,calls,statuses};
}
function find(node,predicate){if(!node)return null;if(predicate(node))return node;for(const child of node.children||[]){const value=find(child,predicate);if(value)return value;}return null;}
function text(node){return (node?.textContent||'')+' '+(node?.children||[]).map(text).join(' ');}

test('public, retained and static views explain why recording is unavailable without enabling it',()=>{
  for(const options of [{shared:true},{qualified:true},{source:null}]){
    const h=harness(options),mode=h.context.reviewWorkspaceMode();assert.equal(mode.editable,false);
    const card=h.context.sourceReviewControls(h.assertion.id),record=card.children.find(n=>n.tag==='button');
    assert.equal(record.disabled,true);assert.ok(record.attributes['aria-describedby']);record.onclick();
    assert.equal(h.context.openEvidenceReview(h.assertion.id),false);assert.equal(h.calls.length,0);
    const help=card.children.filter(n=>n.tag==='button')[1];help.onclick();assert.equal(h.elements.get('localReviewHelp').open,true);
    h.context.inspectAssertion(h.assertion.id);assert.equal(find(h.elements.get('inspector'),n=>n.tag==='form'),null);
    assert.match(text(h.elements.get('inspector')),/read-only/i);assert.equal(JSON.stringify(h.graph),h.original);
  }
});

test('visible mode notice explains a new-run review and local edit recipe stays explanatory',()=>{
  const shared=harness({shared:true});shared.context.updateReviewWorkflow();
  assert.equal(shared.elements.get('workspaceReviewMode').hidden,false);assert.match(shared.elements.get('workspaceReviewMode').textContent,/Read-only example/);
  assert.equal(shared.elements.get('localReviewHelp').hidden,false);assert.equal(shared.calls.length,0);
  const local=harness();local.context.updateReviewWorkflow();assert.match(local.elements.get('workspaceReviewMode').textContent,/new run/);assert.equal(local.elements.get('localReviewHelp').hidden,true);
  assert.match(html,/python3 app\.py serve --runs-dir runs --host 127\.0\.0\.1 --port 8765 --no-browser/);
  assert.match(html,/recorded-agent JSON is an inspection record/);
});

test('record action opens and focuses the existing form without submitting or modifying evidence',()=>{
  const h=harness(),card=h.context.sourceReviewControls(h.assertion.id),button=card.children.find(n=>n.tag==='button');
  assert.equal(button.disabled,false);button.onclick();
  const form=find(h.elements.get('inspector'),n=>n.id==='evidenceReviewForm');
  assert.ok(form);assert.deepEqual(JSON.parse(JSON.stringify(form.scrolled)),{block:'start'});assert.ok(form.focused);
  assert.match(text(form),/Reviewing: UniProtKB:P05067/);assert.match(text(form),/Current local decision: candidate/);
  assert.equal(h.context.tablePage,0);assert.equal(h.context.activeTab,'assertions');
  assert.equal(h.calls.filter(r=>r.kind==='api').length,0);assert.equal(JSON.stringify(h.graph),h.original);
});

test('a source-guide action from an earlier workspace cannot submit a review against the replacement',()=>{
  const h=harness(),card=h.context.sourceReviewControls(h.assertion.id),button=card.children.find(n=>n.tag==='button');h.context.runId='different_run';button.onclick();
  assert.match(h.elements.get('sourceGuideStatus').textContent,/workspace changed/);assert.equal(h.calls.length,0);
});

test('reviewing a nonprotein subject retains the all-protein filter and reaches the actual claim',()=>{
  const h=harness({subject:'molecular_profile:invented'});assert.equal(h.context.openEvidenceReview(h.assertion.id),true);
  assert.equal(h.elements.get('assertionProtein').value,'all');assert.match(text(h.elements.get('inspector')),/molecular_profile:invented/);
});

test('submit preserves the source-run request, opens the new run and exposes its parent link',async()=>{
  const h=harness();h.context.openEvidenceReview(h.assertion.id);
  const inspector=h.elements.get('inspector'),form=find(inspector,n=>n.id==='evidenceReviewForm');
  find(form,n=>n.id==='reviewActor').value='Demo workflow check';find(form,n=>n.id==='reviewState').value='provisional';find(form,n=>n.id==='reviewReason').value='Invented UI check; not biological acceptance.';
  await form.listeners.submit({preventDefault(){}});
  const request=h.calls.find(r=>r.kind==='api');
  assert.equal(request.url,'/api/review');assert.deepEqual(request.body,{run_id:'source_run',assertion_id:'claim:invented',state:'provisional',reviewer:'Demo workflow check',reason:'Invented UI check; not biological acceptance.'});
  assert.equal(h.context.runId,'reviewed_copy');assert.equal(h.context.graph.assertions[0].lifecycle_state,'provisional');
  assert.equal(JSON.stringify(h.graph),h.original);assert.equal(h.statuses.at(-1),'Review saved in a new run. The earlier run remains available.');
  const original=find(inspector,n=>n.tag==='a'&&n.textContent==='Open the earlier run');assert.ok(original);assert.equal(original.href,'?run=source_run&view=evidence');
  assert.match(text(inspector),/Review saved in new run reviewed_copy/);
});
