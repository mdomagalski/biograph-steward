// Exercise the actual manual question renderer and controls on an invented DOM.
// No source retrieval, model calls, review changes or browser-layout claims.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const source=fs.readFileSync(path.join(__dirname,'../biograph_steward/guided.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../biograph_steward/ui.html'),'utf8');
function functions(names){return names.map(name=>{const begin=source.indexOf('function '+name+'('),end=source.indexOf('\nfunction ',begin+1);assert.ok(begin>=0,name);return source.slice(begin,end<0?source.length:end);}).join('\n');}
function element(tag='div',text='',className=''){
  const classes=new Set(className.split(' ').filter(Boolean));
  return {tag,tagName:tag.toUpperCase(),children:[],textContent:text,style:{},dataset:{},attrs:{},open:false,
    classList:{toggle(key,on){if(on===undefined)on=!classes.has(key);on?classes.add(key):classes.delete(key);},remove(key){classes.delete(key);},contains:key=>classes.has(key)},
    append(...items){this.children.push(...items);},replaceChildren(...items){this.children=[...items];},setAttribute(key,value){this.attrs[key]=String(value);},get options(){return this.children;},scrollIntoView(){},
    querySelectorAll(selector){assert.equal(selector,'[data-question-result]');const found=[];function scan(node){for(const child of node.children||[]){if(child.dataset?.questionResult)found.push(child);scan(child);}}scan(this);return found;}};
}
function harness(){
  const elements=new Map(),navigations=[],$=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
  const answer={template:'native_string_physical.v1',overview:'Invented saved answer.',plan:{protein:{id:'p1',sym:'ONE'},view:'candidates'},
    results:[{protein:{id:'p2',sym:'TWO'},review_status:'candidate',paths:[{kind:'interaction',node_ids:['p1','p2'],assertion_ids:['a2']}]},
      {protein:{id:'p3',sym:'THREE'},review_status:'accepted',paths:[{kind:'interaction',node_ids:['p1','p3'],assertion_ids:['a3']}]}],
    summary:[{protein_id:'p2',text:'Source context for TWO.',citation_ids:[]},{protein_id:'p3',text:'Source context for THREE.',citation_ids:[]}],
    citations:[{id:'E002',assertion_id:'a2',subject:'p1',object:'p2',predicate:'associated_with',review_state:'candidate'},
      {id:'E003',assertion_id:'a3',subject:'p1',object:'p3',predicate:'associated_with',review_state:'accepted'}],
    nodes:['p1','p2','p3'].map(id=>({id,category:'biolink:Protein'})),availability:{inspectable_proteins:2},limitations:[]};
  const graph={invented:true,review_events:[]};
  const context=vm.createContext({$,questionAnswer:answer,questionId:'saved',questionSelection:'p2',graph,el:element,svgEl:(tag,attrs)=>Object.assign(element(tag),{attrs:{...attrs}}),
    relationLabel:x=>x,updateWorkNavigation(){},navigateWork:step=>navigations.push(step),inspectQuestionCitation(){},showWorkspaceView:step=>navigations.push(step),render(){},updateQuestionPlan(){},history:{replaceState(){}},savedQuestionURL:()=>'?saved',runId:'invented'});
  vm.runInContext(functions(['renderQuestion','selectQuestionResult','renderQuestionGraph','renderQuestionOverview','browseQuestionWorkspaceGraph','bindQuestionAnswer']),context);
  const run=code=>vm.runInContext(code,context);run('renderQuestion()');
  return {$,answer,graph,context,run,navigations,boxes:()=>$('questionSummary').children.filter(x=>x.tagName==='DETAILS'),buttons:()=>$('questionSummary').querySelectorAll('[data-question-result]')};
}

test('the selected-result announcement is visible above the diagram and the summary explains the action',()=>{
  assert.match(html,/<p id="questionGraphSelection"[^>]*role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"/);
  assert.ok(html.indexOf('id="questionGraphSelection"')<html.indexOf('id="questionGraph"'));
  assert.match(html.replace(/<[^>]*>/g,''),/Use Show in graph on a result to focus the diagram above/);
});

test('binding a saved question opens all returned results and supplies a reversible detail selector',()=>{
  const h=harness(),before=JSON.stringify(h.answer);h.answer.source_run='invented';h.answer.graph_basis_sha256='basis';h.graph.question_basis_sha256='basis';
  h.context.answer=h.answer;h.run('bindQuestionAnswer(answer,"saved-question")');
  assert.equal(h.run('questionSelection'),null);assert.match(h.$('questionGraphSelection').textContent,/Overview: 2 of 2 returned results/);
  assert.equal(h.$('questionGraphView').children.length,3);assert.equal(h.$('questionGraphView').children[0].value,'');assert.equal(h.$('questionGraphAll').disabled,true);
  let svg=h.$('questionGraph').children[0];assert.equal(svg.children.filter(n=>n.tagName==='G').length,3);assert.equal(svg.children.filter(n=>n.tagName==='LINE').length,4);
  h.$('questionGraphView').value='p3';h.$('questionGraphView').onchange();assert.equal(h.run('questionSelection'),'p3');assert.equal(h.$('questionGraphAll').disabled,false);
  h.$('questionGraphAll').onclick();assert.equal(h.run('questionSelection'),null);assert.match(h.$('questionGraphSelection').textContent,/Overview: 2 of 2/);
  assert.equal(JSON.stringify(h.answer),JSON.stringify({...JSON.parse(before),source_run:'invented',graph_basis_sha256:'basis'}));
});

test('overview retains recorded pathway and location relations and clickable citation targets',()=>{
  const h=harness(),calls=[];h.context.inspectQuestionCitation=id=>calls.push(id);
  h.answer.template='qualified_pathway_source_context.v1';h.answer.nodes.push({id:'model',name:'Recorded pathway model',category:'biolink:Pathway'});
  h.answer.results[0].paths=[{kind:'shared_pathway',node_ids:['p1','model','p2'],assertion_ids:['m1','m2']}];h.answer.results[1].paths=[{kind:'location',node_ids:['p3','model'],assertion_ids:['m3']}];
  h.answer.citations=[{id:'E001',assertion_id:'m1',subject:'p1',object:'model',predicate:'participates_in',review_state:'candidate'},{id:'E002',assertion_id:'m2',subject:'p2',object:'model',predicate:'participates_in',review_state:'candidate'},{id:'E003',assertion_id:'m3',subject:'p3',object:'model',predicate:'located_in',review_state:'accepted'}];
  const before=JSON.stringify(h.answer);h.run('selectQuestionResult(null)');const svg=h.$('questionGraph').children[0],lines=svg.children.filter(n=>n.tagName==='LINE'),hits=lines.filter(n=>n.attrs.role==='button');
  assert.equal(hits.length,3);assert.equal(lines.filter(n=>n.attrs['pointer-events']==='none').length,3);
  assert.match(hits[0].children[0].textContent,/participates_in/);assert.match(hits[2].children[0].textContent,/located_in/);
  assert.equal(hits[0].attrs['stroke-dasharray'],'none');assert.equal(hits[0].attrs['stroke-width'],14);assert.equal(hits[0].attrs['pointer-events'],'stroke');
  hits[0].onclick();hits[2].onkeydown({key:' ',preventDefault(){}});assert.deepEqual(calls,['E001','E003']);
  assert.equal(JSON.stringify(h.answer),before);assert.equal(svg.children.filter(n=>n.tagName==='G').length,4);
});

test('overview caps a large drawing explicitly without truncating the saved answer',()=>{
  const h=harness();h.answer.results=[];h.answer.nodes=[{id:'p1',category:'biolink:Protein'}];h.answer.citations=[];
  for(let i=0;i<25;i++){const id='result'+i;h.answer.nodes.push({id,sym:'RESULT'+i,category:'biolink:Protein'});h.answer.results.push({protein:{id,sym:'RESULT'+i},paths:[{node_ids:['p1',id],assertion_ids:['a'+i]}]});h.answer.citations.push({id:'E'+i,assertion_id:'a'+i,subject:'p1',object:id,predicate:'recorded_relation',review_state:'candidate'});}
  const before=JSON.stringify(h.answer);h.run('selectQuestionResult(null)');
  assert.match(h.$('questionGraphSelection').textContent,/20 of 25 returned results/);assert.match(h.$('questionGraphSelection').textContent,/20 of 25 cited connections/);assert.match(h.$('questionGraphSelection').textContent,/Drawing limits/);
  assert.equal(h.$('questionGraph').children[0].children.filter(n=>n.tagName==='G').length,21);assert.equal(JSON.stringify(h.answer),before);
});

test('workspace browse reuses the existing bounded reader rather than claiming a full graph render',()=>{
  const h=harness(),before=JSON.stringify(h.graph);h.$('assertionProtein').append(Object.assign(element('option'),{value:'p1'}));h.graph.nodes=[{id:'p1'},{id:'p2'},{id:'p3'}];h.graph.edges=[{},{}];
  h.run('renderQuestionGraph()');assert.match(h.$('questionGraphScope').textContent,/3 entities and 2 source records/);assert.match(h.$('questionGraphScope').textContent,/not the complete workspace/);
  const graphBefore=JSON.stringify(h.graph);assert.equal(h.run('browseQuestionWorkspaceGraph()'),true);assert.equal(h.$('inspectionDetails').open,true);assert.equal(h.$('evidenceView').value,'inspection');assert.equal(h.$('assertionFamily').value,'all');assert.equal(h.$('assertionProtein').value,'p1');assert.deepEqual(h.navigations,['evidence']);assert.equal(JSON.stringify(h.graph),graphBefore);
});

test('reading a different summary keeps the displayed diagram and source passport unchanged',()=>{
  const h=harness(),before=JSON.stringify(h.answer),graphBefore=JSON.stringify(h.graph);
  h.$('questionCitation').append(element('p','Inspected citation remains open.'));
  const second=h.boxes()[1];second.open=true;second.ontoggle?.();
  assert.equal(h.run('questionSelection'),'p2');
  assert.match(h.$('questionGraphTitle').textContent,/TWO/);
  assert.match(h.$('questionGraphSelection').textContent,/TWO \(1 of 2 shown results\)/);
  assert.equal(h.$('questionCitation').children.length,1);
  assert.deepEqual(h.navigations,[]);
  assert.equal(JSON.stringify(h.answer),before);assert.equal(JSON.stringify(h.graph),graphBefore);
});

test('Show in graph deliberately selects the requested diagram and returns through existing graph navigation',()=>{
  const h=harness(),before=JSON.stringify(h.answer),graphBefore=JSON.stringify(h.graph);
  h.$('questionCitation').append(element('p','Previous selection citation.'));
  const buttons=h.buttons();assert.equal(buttons[0].textContent,'Shown in graph');assert.equal(buttons[0].attrs['aria-pressed'],'true');
  buttons[1].onclick();
  assert.equal(h.run('questionSelection'),'p3');assert.deepEqual(h.navigations,['graph']);
  assert.match(h.$('questionGraphTitle').textContent,/THREE/);
  assert.match(h.$('questionGraphSelection').textContent,/THREE \(2 of 2 shown results\)/);
  assert.match(h.$('questionGraph').children[0].attrs['aria-label'],/THREE/);
  assert.equal(buttons[1].textContent,'Shown in graph');assert.equal(buttons[1].attrs['aria-pressed'],'true');
  assert.equal(buttons[0].textContent,'Show in graph');assert.equal(buttons[0].attrs['aria-pressed'],'false');
  assert.equal(buttons[1].type,'button');assert.equal(buttons[1].attrs['aria-controls'],'questionGraphSection');
  assert.equal(h.$('questionCitation').children.length,0);
  assert.equal(JSON.stringify(h.answer),before);assert.equal(JSON.stringify(h.graph),graphBefore);
});

test('returning to the already shown result preserves inspection, and unknown results cannot replace the graph',()=>{
  const h=harness();h.$('questionCitation').append(element('p','Current citation.'));
  h.buttons()[0].onclick();assert.deepEqual(h.navigations,['graph']);assert.equal(h.$('questionCitation').children.length,1);
  const title=h.$('questionGraphTitle').textContent;
  assert.equal(h.run('selectQuestionResult("not-in-this-answer")'),false);
  assert.equal(h.$('questionGraphTitle').textContent,title);assert.equal(h.run('questionSelection'),'p2');
  assert.deepEqual(h.navigations,['graph']);
});
