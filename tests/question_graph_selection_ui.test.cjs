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
    append(...items){this.children.push(...items);},replaceChildren(...items){this.children=[...items];},setAttribute(key,value){this.attrs[key]=String(value);},
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
    relationLabel:x=>x,updateWorkNavigation(){},navigateWork:step=>navigations.push(step),inspectQuestionCitation(){}});
  vm.runInContext(functions(['renderQuestion','selectQuestionResult','renderQuestionGraph']),context);
  const run=code=>vm.runInContext(code,context);run('renderQuestion()');
  return {$,answer,graph,context,run,navigations,boxes:()=>$('questionSummary').children.filter(x=>x.tagName==='DETAILS'),buttons:()=>$('questionSummary').querySelectorAll('[data-question-result]')};
}

test('the selected-result announcement is visible above the diagram and the summary explains the action',()=>{
  assert.match(html,/<p id="questionGraphSelection"[^>]*role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"/);
  assert.ok(html.indexOf('id="questionGraphSelection"')<html.indexOf('id="questionGraph"'));
  assert.match(html.replace(/<[^>]*>/g,''),/Use Show in graph on a result to focus the diagram above/);
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
