// Actual asynchronous reader lifecycles; invented responses, no source/model calls.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const root=path.join(__dirname,'..');
const navigation=fs.readFileSync(path.join(root,'biograph_steward/navigation.js'),'utf8');
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
function element(tag='div',text=''){
 return {tag,textContent:text,children:[],attrs:{},value:'',disabled:false,
  append(...rows){this.children.push(...rows);},replaceChildren(...rows){this.children=[...rows];},
  setAttribute(key,value){this.attrs[key]=String(value);},get options(){return this.children;}};
}
function functionSource(start,end){
 const first=navigation.indexOf(start),last=navigation.indexOf(end,first);
 assert.ok(first>=0&&last>first);return navigation.slice(first,last);
}
function readers(){
 const elements=new Map(),pending=[],rendered=[],$=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
 const graph={snapshot_sha256:'invented-snapshot',assertions:[{id:'claim:A'},{id:'claim:B'}]};
 $('sourceGuideSelection').children=[{value:'claim:A'},{value:'claim:B'}];
 for(const [id,value]of Object.entries({pathSource:'protein:A',pathTarget:'protein:B',pathHops:'1',pathView:'candidates',pathPredicate:'test:association'}))$(id).value=value;
 const context=vm.createContext({$,graph,runId:'saved',inspectionRequest:0,pathRequest:0,el:element,
  claimLabel:row=>row.id,showWorkspaceView(){},
  renderSourceGuide:value=>rendered.push(['source',value.selection.id]),renderExploration:value=>rendered.push(['path',value]),
  api:(route,body)=>{const result=deferred();pending.push({route,body,...result});return result.promise;}});
 vm.runInContext(functionSource('async function loadSourceGuide(','\nfunction editableCopySize'),context);
 vm.runInContext(functionSource('async function runPathExploration(','\nfunction renderExploration'),context);
 for(const name of ['invalidateSourceGuide','invalidateExploration'])vm.runInContext(navigation.split('\n').find(line=>line.startsWith('function '+name+'(')),context);
 return {$,graph,context,pending,rendered,source(id='claim:A'){return context.loadSourceGuide(id);},paths(){return context.runPathExploration();}};
}
function sourceReply(id='claim:A'){return {source_run:'saved',snapshot_sha256:'invented-snapshot',selection:{id},read_only:true};}
function pathReply(count=1){return {source_run:'saved',snapshot_sha256:'invented-snapshot',search:{paths_returned:count,truncated:false,expansions:2}};}
function flags(h,status,output,on){assert.equal(h.$(status).attrs['data-loading'],String(on));assert.equal(h.$(output).attrs['aria-busy'],String(on));}

test('source inspection visibly waits through its actual deferred read and clears after success or failure',async()=>{
 for(const fail of [false,true]){
  const h=readers(),before=JSON.stringify(h.graph),done=h.source();
  flags(h,'sourceGuideStatus','sourceGuideOutput',true);
  assert.match(h.$('sourceGuideStatus').textContent,/Reading saved source context/);
  assert.equal(h.pending.length,1);assert.equal(h.pending[0].route,'/api/inspect-source');
  if(fail)h.pending[0].reject(new Error('Source check failed.'));else h.pending[0].resolve(sourceReply());
  await done;flags(h,'sourceGuideStatus','sourceGuideOutput',false);
  assert.match(h.$('sourceGuideStatus').textContent,fail?/Source check failed/:/Saved-source explanation/);
  assert.equal(h.rendered.length,fail?0:1);assert.equal(JSON.stringify(h.graph),before);
 }
});

test('an older source response cannot stop the indicator for the newer selection',async()=>{
 const h=readers(),first=h.source('claim:A'),second=h.source('claim:B');
 h.pending[0].resolve(sourceReply('claim:A'));await first;
 flags(h,'sourceGuideStatus','sourceGuideOutput',true);assert.deepEqual(h.rendered,[]);
 h.pending[1].resolve(sourceReply('claim:B'));await second;
 flags(h,'sourceGuideStatus','sourceGuideOutput',false);assert.deepEqual(h.rendered,[['source','claim:B']]);
});

test('changing the selected source cancels its visible wait without allowing its late response to render',async()=>{
 const h=readers(),done=h.source();h.context.invalidateSourceGuide();
 flags(h,'sourceGuideStatus','sourceGuideOutput',false);
 h.pending[0].resolve(sourceReply());await done;
 assert.deepEqual(h.rendered,[]);assert.match(h.$('sourceGuideStatus').textContent,/Selection changed/);
});

test('saved-path waits settle for empty matches and errors while preserving the submitted scope',async()=>{
 for(const fail of [false,true]){
  const h=readers(),before=JSON.stringify(h.graph),done=h.paths();
  flags(h,'pathExploreStatus','pathExploreResults',true);assert.equal(h.$('pathExploreButton').disabled,true);
  assert.deepEqual(JSON.parse(JSON.stringify(h.pending[0].body)),{run_id:'saved',source:'protein:A',target:'protein:B',max_hops:1,view:'candidates',predicates:['test:association']});
  if(fail)h.pending[0].reject(new Error('Saved path unavailable.'));else h.pending[0].resolve(pathReply(0));
  await done;flags(h,'pathExploreStatus','pathExploreResults',false);assert.equal(h.$('pathExploreButton').disabled,false);
  assert.match(h.$('pathExploreStatus').textContent,fail?/Saved path unavailable/:/0 paths shown\. Search complete/);
  assert.equal(JSON.stringify(h.graph),before);
 }
});

test('changed path filters clear the old wait and a late result cannot clear a newer request',async()=>{
 const h=readers(),first=h.paths();h.context.invalidateExploration();
 flags(h,'pathExploreStatus','pathExploreResults',false);
 const second=h.paths();h.pending[0].resolve(pathReply());await first;
 flags(h,'pathExploreStatus','pathExploreResults',true);assert.deepEqual(h.rendered,[]);
 h.pending[1].resolve(pathReply());await second;flags(h,'pathExploreStatus','pathExploreResults',false);
 assert.equal(h.rendered.length,1);
});

test('the compact scientific-results catalogue clears its indicator after empty or failed reads, including stale replies',async()=>{
 const elements=new Map(),pending=[],$=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
 const context=vm.createContext({document:{getElementById:$,createElement:element},fetch:()=>{const row=deferred();pending.push(row);return row.promise;},ScientificAssessment:{render(){throw new Error('No result should render for an empty catalogue.');}}});
 const source=fs.readFileSync(path.join(root,'biograph_steward/scientific_assessment.js'),'utf8');
 vm.runInContext(source.slice(source.indexOf('let scientificAssessmentRequest=0;')),context);
 const first=context.initializeScientificAssessments(),second=context.initializeScientificAssessments();
 assert.equal($('scientificAssessmentStatus').attrs['data-loading'],'true');assert.equal($('scientificAssessmentBody').attrs['aria-busy'],'true');
 pending[0].resolve({ok:true,json:async()=>({assessments:[]})});await first;
 assert.equal($('scientificAssessmentStatus').attrs['data-loading'],'true');
 pending[1].reject(new Error('Assessment unavailable.'));await second;
 assert.equal($('scientificAssessmentStatus').attrs['data-loading'],'false');assert.equal($('scientificAssessmentBody').attrs['aria-busy'],'false');
 assert.match($('scientificAssessmentStatus').textContent,/Assessment unavailable/);
 const third=context.initializeScientificAssessments();pending[2].resolve({ok:true,json:async()=>({assessments:[]})});await third;
 assert.equal($('scientificAssessmentStatus').attrs['data-loading'],'false');assert.match($('scientificAssessmentStatus').textContent,/No verified scientific assessment/);
});
