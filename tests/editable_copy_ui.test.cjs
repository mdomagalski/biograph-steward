// Complete local copies use a verified prepared download, never browser ZIP assembly.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const root=path.join(__dirname,'..');
const navigation=fs.readFileSync(path.join(root,'biograph_steward/navigation.js'),'utf8');
const html=fs.readFileSync(path.join(root,'biograph_steward/ui.html'),'utf8');
const functions=navigation.slice(navigation.indexOf('function editableCopySize('),navigation.indexOf('function reviewWorkspaceMode(){'));
const snapshot='a'.repeat(64);
function metadata(run='native_example',overrides={}){
  return {available:true,run_id:run,label:'Invented complete workspace package',filename:'Workspace_Local_Copy.zip',bytes:123456789,
    sha256:'b'.repeat(64),source_graph_sha256:'c'.repeat(64),snapshot_sha256:snapshot,
    download_url:'/api/editable-copy/'+run+'/download',requires:{python:'3.10+',model:false,AWS:false},...overrides};
}
function harness({shared=true,source='native_example',fetchImpl}={}){
  class Element{
    constructor(tag,value=''){this.tag=tag;this.textContent=value??'';this.children=[];this.attributes={};this.hidden=false;}
    append(...items){this.children.push(...items);}replaceChildren(...items){this.children=items;}
    setAttribute(key,value){this.attributes[key]=String(value);}
  }
  const elements=new Map([['workspaceEditableCopy',new Element('div')],['editableCopyExport',new Element('section')]]),calls=[];
  const context=vm.createContext({runId:source,graph:{snapshot_sha256:snapshot},el:(tag,value)=>new Element(tag,value),$:id=>elements.get(id),savedReviewOnly:()=>shared,
    fetch:async(...args)=>{calls.push(args);return fetchImpl?fetchImpl(...args):{ok:true,json:async()=>metadata(source)};}});
  vm.runInContext('let editableCopyRequest=0,editableCopyState=null;\n'+functions,context);
  return {context,elements,calls,state:()=>vm.runInContext('editableCopyState',context)};
}
function find(node,predicate){if(predicate(node))return node;for(const child of node.children||[]){const found=find(child,predicate);if(found)return found;}return null;}
function text(node){return (node?.textContent||'')+' '+(node?.children||[]).map(text).join(' ');}
function anchor(h,id='workspaceEditableCopy'){return find(h.elements.get(id),n=>n.tag==='a');}

test('complete-copy entry includes its size and real local review instructions in both placements',async()=>{
  const h=harness();await h.context.setupEditableCopyDownload();
  assert.equal(h.state().status,'available');assert.equal(h.elements.get('workspaceEditableCopy').hidden,false);
  for(const id of ['workspaceEditableCopy','editableCopyExport']){
    const link=anchor(h,id);assert.ok(link);assert.equal(link.href,'/api/editable-copy/native_example/download');assert.equal(link.download,'Workspace_Local_Copy.zip');assert.match(link.textContent,/123\.5 MB/);
  }
  const description=text(h.elements.get('editableCopyExport'));assert.match(description,/START_EDITABLE_LOCAL\.py/);assert.match(description,/Save review in a new run/);assert.match(description,/No model, AWS account or new data retrieval/);
  assert.match(html,/id="workspaceEditableCopy"[^>]*hidden/);assert.match(html,/id="editableCopyExport"[^>]*hidden/);
  assert.match(html,/recorded-agent JSON is an inspection record/);
  assert.deepEqual(h.calls,[['/api/editable-copy/native_example']]);
  assert.equal(anchor(h).onclick,undefined); // Native link streams directly; no Blob or download fetch.
});

test('unregistered and failed checks offer no broken download or route expansion',async()=>{
  for(const response of [
    {ok:true,json:async()=>({available:false,run_id:'native_example',reason:'Not registered.'})},
    {ok:false,json:async()=>({error:'/private/operator/path must never be shown'})}
  ]){
    const h=harness({fetchImpl:async()=>response});await h.context.setupEditableCopyDownload();
    assert.equal(h.elements.get('workspaceEditableCopy').hidden,true);assert.equal(anchor(h),null);
    assert.equal(h.elements.get('editableCopyExport').hidden,false);assert.equal(anchor(h,'editableCopyExport'),null);
    assert.doesNotMatch(text(h.elements.get('editableCopyExport')),/private\/operator/);
    assert.equal(h.calls.length,1);assert.equal(h.calls[0].length,1); // GET metadata only; no review or retrieval body.
  }
  const local=harness({shared:false,fetchImpl:async()=>({ok:true,json:async()=>({available:false,run_id:'native_example'})})});
  await local.context.setupEditableCopyDownload();assert.equal(local.elements.get('editableCopyExport').hidden,true);
});

test('only the bound same-origin ZIP is exposed after complete metadata passes',async()=>{
  for(const overrides of [
    {run_id:'another_workspace'}, {snapshot_sha256:'d'.repeat(64)},
    {download_url:'https://outside.invalid/file.zip'}, {download_url:'/api/download/native_example'},
    {filename:'../file.zip'}, {bytes:0}, {sha256:'unverified'}, {source_graph_sha256:''},
    {requires:{python:'3.10+',model:true,AWS:false}}
  ]){
    const h=harness({fetchImpl:async()=>({ok:true,json:async()=>metadata('native_example',overrides)})});await h.context.setupEditableCopyDownload();
    assert.equal(h.state().status,'error',JSON.stringify(overrides));assert.equal(anchor(h),null);assert.equal(anchor(h,'editableCopyExport'),null);
  }
});

test('a late response cannot replace the package for the newly selected workspace',async()=>{
  let finishFirst;
  const first=new Promise(resolve=>{finishFirst=resolve;});
  const h=harness({fetchImpl:async url=>url.endsWith('/native_example')?first:{ok:true,json:async()=>metadata('another_workspace')}});
  const pending=h.context.setupEditableCopyDownload();
  assert.equal(h.elements.get('workspaceEditableCopy').hidden,true);assert.match(text(h.elements.get('editableCopyExport')),/Checking/);
  h.context.runId='another_workspace';h.context.graph={snapshot_sha256:snapshot};await h.context.setupEditableCopyDownload();
  finishFirst({ok:true,json:async()=>metadata()});await pending;
  assert.equal(anchor(h).href,'/api/editable-copy/another_workspace/download');assert.equal(h.state().run_id,'another_workspace');
});

test('a graph replacement invalidates a pending package even if its source snapshot is the same',async()=>{
  let finish;
  const h=harness({fetchImpl:()=>new Promise(resolve=>{finish=resolve;})});const pending=h.context.setupEditableCopyDownload();
  h.context.graph={snapshot_sha256:snapshot};finish({ok:true,json:async()=>metadata()});await pending;
  assert.equal(anchor(h),null);
});

test('a static exported graph does not request or invent a complete workspace download',async()=>{
  const h=harness({source:null});await h.context.setupEditableCopyDownload();
  assert.equal(h.calls.length,0);assert.equal(h.elements.get('workspaceEditableCopy').hidden,true);assert.equal(h.elements.get('editableCopyExport').hidden,true);
});
