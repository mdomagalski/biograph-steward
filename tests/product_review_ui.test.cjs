// Run the actual startup and hash gates without loading source data or a browser.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const root=path.join(__dirname,'..');
const navigation=fs.readFileSync(path.join(root,'biograph_steward/navigation.js'),'utf8');
function declaration(start,end){return navigation.slice(navigation.indexOf(start),navigation.indexOf(end,navigation.indexOf(start)));}

test('shared startup reads current scientific results and starts no development catalogue',()=>{
  for(const saved of [true,false]){
    const calls=[],context=vm.createContext({savedReviewOnly:()=>saved,
      initializeScientificAssessments:()=>calls.push('current-science'),
      initializePruningPreview:()=>calls.push('pruning-history'),
      initializeBiologicalComparisons:()=>calls.push('experimental-history'),
      initializeFunctionContexts:()=>calls.push('function-history')});
    vm.runInContext(declaration('function initializeWorkspaceAssessments(){','function showWorkspaceView('),context);
    context.initializeWorkspaceAssessments();
    assert.deepEqual(calls,saved?['current-science']:['current-science','pruning-history','experimental-history','function-history']);
  }
});

test('shared deep links cannot reopen hidden development panels but sources still navigate',()=>{
  for(const saved of [true,false]){
    const opened=[],panel={dataset:{workspacePanel:'compare'}},details={open:false,parentElement:{closest:()=>null}};
    const target={closest:selector=>selector==='[data-development-view]'?{}:selector==='details'?details:panel};
    const context=vm.createContext({savedReviewOnly:()=>saved,showWorkspaceView:value=>opened.push(value)});
    vm.runInContext(declaration('function revealWorkspaceTarget(target){','function initializeWorkspaceNavigation(){'),context);
    assert.equal(context.revealWorkspaceTarget(target),!saved);
    assert.equal(details.open,!saved);assert.deepEqual(opened,saved?[]:['compare']);
    context.revealWorkspaceTarget({closest:selector=>selector==='[data-development-view]'?null:selector==='details'?null:{dataset:{workspacePanel:'evidence'}}});
    assert.equal(opened.at(-1),'evidence');
  }
});

test('refresh script makes no hidden startup requests in saved mode and remains available to operators',async()=>{
  for(const saved of [true,false]){
    const calls=[],elements=new Map();
    const $=id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:id==='embeddedData'?'null':'',classList:{add(){}},replaceChildren(){},append(){}});return elements.get(id);};
    const context=vm.createContext({$,savedReviewOnly:()=>saved,runId:null,el:()=>({}),
      fetch:async url=>{calls.push(url);return {ok:true,json:async()=>({runs:[],comparisons:[],note:''})};}});
    vm.runInContext(fs.readFileSync(path.join(root,'biograph_steward/refresh.js'),'utf8'),context);
    await new Promise(resolve=>setImmediate(resolve));
    assert.deepEqual(calls,saved?[]:['/api/refresh-runs','/api/refresh-history']);
    assert.equal(typeof context.loadRefreshRuns,'function');
  }
});

test('shared workspace skips database diagnostics while retaining native source inspection',()=>{
  for(const saved of [true,false]){
    const calls=[],elements=new Map();
    const element=()=>({children:[],replaceChildren(...items){this.children=items;},append(item){this.children.push(item);},get options(){return this.children;}});
    const $=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
    const context=vm.createContext({$,el:element,savedReviewOnly:()=>saved,runId:'saved',graph:{assertions:[]},
      inspectionRequest:0,pathRequest:0,workspaceLoaded:true,workspaceSuffix:{ask:'Ask',evidence:'Evidence',export:'Export'},
      populateSourceGuide(){},populatePathEntities(){},setupEditableCopyDownload:()=>calls.push('prepared-copy-check'),setupNeptune:()=>calls.push('database-diagnostic'),
      setupNativeGoa:()=>calls.push('native-go-source'),location:{hash:''}});
    vm.runInContext(declaration('function setupWorkspace(){','function claimLabel('),context);
    context.setupWorkspace();
    assert.deepEqual(calls,saved?['prepared-copy-check','native-go-source']:['prepared-copy-check','database-diagnostic','native-go-source']);
    assert.equal($('sourceGuideButton').disabled,false);
  }
});
