// Real async UI lifecycles with deferred responses; no source/model/browser calls.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const root=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(root,'biograph_steward/ui.html'),'utf8');
const guided=fs.readFileSync(path.join(root,'biograph_steward/guided.js'),'utf8');
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
function workspace({questionFailure=false,deferQuestion=false}={}){
 const elements=new Map(),$=id=>{if(!elements.has(id))elements.set(id,{textContent:'',className:'',hidden:false,attributes:{},setAttribute(k,v){this.attributes[k]=String(v);}});return elements.get(id);};
 const graph=deferred(),question=deferred(),calls=[],messages=[],bindings=[];
 const context=vm.createContext({$,URLSearchParams,savedRun:'saved',runId:null,location:{search:'?view=data&question=q'},
   busy:on=>calls.push(['busy',on]),status:(message,error)=>messages.push({message,error}),
   showGraph:value=>calls.push(['graph',value]),showQualificationSummary(){},showWorkspaceView:view=>calls.push(['workspace',view]),navigateWork:step=>calls.push(['navigate',step]),
   bindQuestionAnswer:()=>bindings.push('question'),bindAssayAnswer:()=>bindings.push('assay'),bindCivicAnswer:()=>bindings.push('therapy'),
   fetch:async url=>{calls.push(['fetch',url]);if(url==='/api/run/saved')return graph.promise;
    if(deferQuestion)await question.promise;
    return {ok:!questionFailure,json:async()=>questionFailure?{error:'Saved question source check failed.'}:{question_id:'q',answer:{template:'invented_fixture'}}};}});
 const loaderStart=html.indexOf('function workspaceLoading('),loaderEnd=html.indexOf('\nlet buildBusy',loaderStart);
 vm.runInContext(html.slice(loaderStart,loaderEnd),context);
 const questionStart=guided.indexOf('async function reopenQuestion('),questionEnd=guided.indexOf('\nfunction renderQuestion(',questionStart);
 vm.runInContext(guided.slice(questionStart,questionEnd),context);
 const start=html.indexOf('  if(savedRun)(async()=>{'),end=html.indexOf('\n  })();',start)+'\n  })();'.length;
 const actualOpening=html.slice(start,end).replace('if(savedRun)','globalThis.openingTask=');
 return {$,context,calls,messages,bindings,graph,question,start(){vm.runInContext(actualOpening,context);return context.openingTask;},response(){let count=0;return {ok:true,json:async()=>{count++;assert.equal(count,1,'Response body must be read once');return {run_id:'saved',graph:{invented:true}};}};}};
}

test('workspace opening shows a nonblocking top status until graph and cited question both finish',async()=>{
 const h=workspace({deferQuestion:true}),done=h.start();
 assert.equal(h.$('workspaceLoadingStatus').hidden,false);assert.equal(h.$('workspaceLoadingStatus').attributes['data-loading'],'true');
 assert.match(h.$('workspaceLoadingStatus').textContent,/Opening saved evidence/);
 h.graph.resolve(h.response());await new Promise(resolve=>setImmediate(resolve));
 assert.match(h.$('workspaceLoadingStatus').textContent,/Opening the saved question/);
 assert.equal(h.$('workspaceViews').attributes['aria-busy'],'true');
 h.question.resolve();await done;
 assert.equal(h.$('workspaceLoadingStatus').hidden,true);assert.equal(h.$('workspaceLoadingStatus').attributes['data-loading'],'false');
 assert.equal(h.$('workspaceViews').attributes['aria-busy'],'false');assert.deepEqual(h.bindings,['question']);
});

test('ordinary saved questions open their overview while explicit agent workspace views remain unchanged',async()=>{
 for(const [view,empty]of [['ask',false],['ask',true],['data',false],['data',true]]){
  const h=workspace();h.context.location.search='?view='+view+'&question=q';h.context.questionAnswer={results:empty?[]:[{protein:{id:'fixture'}}]};const done=h.start();h.graph.resolve(h.response());await done;
  if(view==='ask')assert.ok(h.calls.some(call=>call[0]==='navigate'&&call[1]===(empty?'answer':'graph')));
  else{assert.ok(h.calls.some(call=>call[0]==='workspace'&&call[1]==='data'));assert.ok(!h.calls.some(call=>call[0]==='navigate'));}
 }
});

test('failed graph and rejected saved-question loads settle the ring and keep a visible error without false readiness',async()=>{
 for(const questionFailure of [false,true]){
  const h=workspace({questionFailure}),done=h.start();
  if(questionFailure)h.graph.resolve(h.response());else h.graph.reject(new Error('Saved workspace unavailable.'));
  await done;const indicator=h.$('workspaceLoadingStatus');
  assert.equal(indicator.hidden,false);assert.match(indicator.className,/error/);assert.equal(indicator.attributes['data-loading'],'false');
  assert.match(indicator.textContent,questionFailure?/Saved question source check failed/:/Saved workspace unavailable/);
  assert.equal(h.$('workspaceViews').attributes['aria-busy'],'false');
  assert.equal(h.messages.some(row=>row.message.startsWith('Saved evidence opened.')),false);
  if(questionFailure)assert.match(h.$('questionStatus').textContent,/source check failed/);
 }
});

test('ordinary, assay and therapy saved-question branches return explicit completion without altering binding choice',async()=>{
 for(const [template,binding]of [['invented_fixture','question'],['qualified_assay_evidence.v1','assay'],['civic_variant_therapy.v1','therapy']]){
  const h=workspace();h.context.fetch=async()=>({ok:true,json:async()=>({question_id:'q',answer:{template}})});
  assert.equal(await h.context.reopenQuestion('q'),true);assert.deepEqual(h.bindings,[binding]);
 }
});

test('loading styling is decorative, polite and motion-safe, with no login-page spinner',()=>{
 assert.match(html,/<p id="workspaceLoadingStatus"[^>]*role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"[^>]*hidden/);
 assert.ok(html.indexOf('id="workspaceLoadingStatus"')<html.indexOf('id="workspaceContext"'));
 assert.match(html,/@media\(prefers-reduced-motion:reduce\)\{\[data-loading="true"\]::before\{animation:none\}\}/);
 assert.match(html,/\[data-loading="true"\]::before\{content:""/);
 const login=fs.readFileSync(path.join(root,'biograph_steward/login.html'),'utf8');assert.ok(!login.includes('data-loading'));
});
