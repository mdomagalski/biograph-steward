// Exercise the actual saved-path selector/requests. No graph or review edits.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const source=fs.readFileSync(path.join(__dirname,'../biograph_steward/navigation.js'),'utf8');
function element(tag='div',text=''){
  return {tag,textContent:text,children:[],value:'',disabled:false,attrs:{},
    append(...children){this.children.push(...children);},replaceChildren(...children){this.children=[...children];},
    get options(){return this.children;},setAttribute(key,value){this.attrs[key]=value;}};
}
function node(id,sym=id,category='biolink:Protein'){return {id,sym,name:sym,category};}
function add(graph,id,subject,object,{state='candidate',symmetric=false,predicate='test:association',kind='protein_interaction',usable=true,qualifiers={}}={}){
  graph.assertions.push({id,subject,object,predicate,kind,symmetric,lifecycle_state:state,qualifiers,
    structurally_usable_evidence_ids:usable?['edge:'+id]:[]});
  graph.edges.push({id:'edge:'+id,subject,object,predicate,status:'passed_structural_checks',qualifiers});return graph;
}
function fixture(){return {snapshot_sha256:'fixture',nodes:[node('sink','Annotation','biolink:Pathway'),node('B','Beta'),node('A','Alpha'),node('C','Gamma')],assertions:[],edges:[]};}
function harness(graph){
  const elements=new Map(),requests=[],$=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
  $('pathView').value='candidates';$('pathHops').value='2';
  const context=vm.createContext({graph,runId:'saved',pathRequest:0,$,el:element,
    relationLabel:x=>x,nodeLabel:id=>graph.nodes.find(n=>n.id===id)?.sym||id,
    renderExploration:()=>{},api:async(route,body)=>{requests.push({route,body});return {source_run:'saved',snapshot_sha256:graph.snapshot_sha256,search:{paths_returned:1,truncated:false,expansions:1}};}});
  const begin=source.indexOf('function populatePathEntities(){'),end=source.indexOf('\nfunction populateNeptuneNodes',begin);
  vm.runInContext(source.slice(begin,end),context);
  const runBegin=source.indexOf('async function runPathExploration(){'),runEnd=source.indexOf('\nfunction renderExploration',runBegin);
  vm.runInContext(source.slice(runBegin,runEnd),context);
  const invalidBegin=source.indexOf('function invalidateExploration(){'),invalidEnd=source.indexOf('\n',invalidBegin);
  vm.runInContext(source.slice(invalidBegin,invalidEnd),context);
  const run=code=>vm.runInContext(code,context);run('populatePathEntities()');
  return {$,run,context,requests,ids:id=>$(id).options.map(o=>o.value),graph};
}

test('starts sort by protein/name and typing replaces an unrelated off-filter start',()=>{
  const g=fixture();add(g,'bs','B','sink');add(g,'as','A','sink');
  const before=JSON.stringify(g),h=harness(g);
  assert.deepEqual(h.ids('pathSource'),['A','B']);assert.equal(h.$('pathSource').value,'A');
  h.$('pathEntitySearch').value='beTA';h.run('populatePathEntities()');
  assert.deepEqual(h.ids('pathSource'),['B']);assert.equal(h.$('pathSource').value,'B');
  assert.equal(h.$('pathExploreButton').disabled,false);assert.match(h.$('pathEntityCount').textContent,/Proteins first/);
  assert.equal(JSON.stringify(g),before);
});

test('end suggestions respect direction, explicit symmetry, hops and independent text search',()=>{
  const g=fixture();add(g,'ab','A','B');add(g,'bc','B','C');add(g,'as','A','sink');
  const h=harness(g);assert.deepEqual(h.ids('pathTarget'),['','B','C','sink']);
  h.$('pathTargetSearch').value='Gamma';h.run('populatePathEntities()');
  assert.deepEqual(h.ids('pathTarget'),['','C']);assert.equal(h.$('pathTarget').value,'C');assert.equal(h.$('pathSource').value,'A');
  h.$('pathTargetSearch').value='';h.$('pathHops').value='1';h.run('populatePathEntities()');
  assert.deepEqual(h.ids('pathTarget'),['','B','sink']);assert.equal(h.$('pathTarget').value,'');
  h.$('pathSource').value='B';h.run('populatePathEntities()');assert.deepEqual(h.ids('pathTarget'),['','C']);
  g.assertions[0].symmetric='true';h.context.graph=JSON.parse(JSON.stringify(g));h.run('populatePathEntities()');
  assert.deepEqual(h.ids('pathTarget'),['','C'],'a truthy string cannot invent an inverse');
  g.assertions[0].symmetric=true;h.context.graph=JSON.parse(JSON.stringify(g));h.run('populatePathEntities()');
  assert.deepEqual(h.ids('pathTarget'),['','A','C']);
});

test('accepted-only and relationship filters do not silently broaden the evidence view',()=>{
  const g=fixture();add(g,'ab','A','B');add(g,'as','A','sink',{predicate:'test:membership',state:'accepted'});
  const h=harness(g);h.$('pathPredicate').value='test:membership';h.run('populatePathEntities()');
  assert.deepEqual(h.ids('pathTarget'),['','sink']);
  h.$('pathView').value='accepted';h.$('pathPredicate').value='test:association';h.run('populatePathEntities()');
  assert.equal(h.$('pathExploreButton').disabled,true);assert.deepEqual(h.ids('pathSource'),[]);
  assert.equal(h.$('pathView').value,'accepted');assert.match(h.$('pathEntityCount').textContent,/No starting entities have locally accepted assertions/);
});

test('unusable, rejected, self-only and inconsistent-evidence records cannot become suggested starts',()=>{
  const g=fixture();add(g,'bad','A','B',{usable:false});add(g,'reject','B','C',{state:'rejected'});add(g,'self','C','C');
  add(g,'mismatch','sink','A');g.edges.at(-1).qualifiers={taxon:'wrong'};
  const h=harness(g);assert.deepEqual(h.ids('pathSource'),[]);assert.equal(h.$('pathExploreButton').disabled,true);
});

test('one-click examples submit exact saved IDs and a bounded existing query without changing data',async()=>{
  const g={snapshot_sha256:'fixture',nodes:[node('UniProtKB:P01116','KRAS'),node('UniProtKB:Q9Y5S2','CDC42BPB'),node('UniProtKB:P04637','TP53'),node('GO:0005634','nucleus','biolink:CellularComponent'),node('UniProtKB:P15056','BRAF'),node('pathway','Saved pathway','biolink:Pathway')],assertions:[],edges:[]};
  add(g,'ppi','UniProtKB:P01116','UniProtKB:Q9Y5S2',{symmetric:true});
  add(g,'go','UniProtKB:P04637','GO:0005634',{kind:'native_go_annotation',predicate:'test:go'});
  add(g,'path','UniProtKB:P15056','pathway',{kind:'pathway_membership',predicate:'test:membership'});
  const before=JSON.stringify(g),h=harness(g),buttons=h.$('pathExamples').children.find(n=>n.tag==='div').children;
  assert.equal(buttons.length,3);assert.match(buttons[0].textContent,/KRAS → CDC42BPB/);
  for(const button of buttons){button.onclick();await new Promise(resolve=>setImmediate(resolve));}
  assert.equal(h.requests.length,3);
  assert.deepEqual(JSON.parse(JSON.stringify(h.requests.map(r=>r.body))),[
    {run_id:'saved',source:'UniProtKB:P01116',target:'UniProtKB:Q9Y5S2',max_hops:1,view:'candidates',predicates:['test:association']},
    {run_id:'saved',source:'UniProtKB:P04637',target:'GO:0005634',max_hops:1,view:'candidates',predicates:['test:go']},
    {run_id:'saved',source:'UniProtKB:P15056',target:'pathway',max_hops:1,view:'candidates',predicates:['test:membership']}]);
  assert.ok(h.requests.every(r=>r.route==='/api/explore'));assert.equal(JSON.stringify(g),before);
});

test('typing finds starts beyond the initial cap, and no end match disables submission',()=>{
  const g={snapshot_sha256:'fixture',nodes:[node('end','End','biolink:Pathway')],assertions:[],edges:[]};
  for(let i=349;i>=0;i--){const id='P'+String(i).padStart(3,'0');g.nodes.push(node(id,id));add(g,'a'+id,id,'end');}
  const h=harness(g);assert.equal(h.ids('pathSource').length,300);assert.match(h.$('pathEntityCount').textContent,/350 matching starting entities/);
  h.$('pathEntitySearch').value='P349';h.run('populatePathEntities()');assert.deepEqual(h.ids('pathSource'),['P349']);
  h.$('pathTargetSearch').value='not reachable';h.run('populatePathEntities()');assert.equal(h.$('pathExploreButton').disabled,true);
  assert.match(h.$('pathTargetCount').textContent,/0 matching reachable entities/);
});
