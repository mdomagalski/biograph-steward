// Actual legacy renderer/state functions on an invented DOM; no data retrieval.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const html=fs.readFileSync(path.join(__dirname,'../biograph_steward/ui.html'),'utf8');
const guided=fs.readFileSync(path.join(__dirname,'../biograph_steward/guided.js'),'utf8');
function fn(source,name){const begin=source.indexOf('function '+name+'('),end=source.indexOf('\nfunction ',begin+1);assert.ok(begin>=0,name);return source.slice(begin,end<0?source.length:end);}
function node(tag='div',attrs={}){return {tag,attrs:{...attrs},style:{},children:[],value:'',disabled:false,checked:false,options:[],listeners:{},textContent:'',
  classList:{toggle(){}},append(...children){this.children.push(...children);},replaceChildren(...children){this.children=[...children];},setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,v){this.listeners[k]=v;}};}
function dom(){const all=new Map();return {$:id=>{if(!all.has(id))all.set(id,node());return all.get(id);},all};}
function builder(){const h=dom();let selected='live';h.$('disease').options=[{value:'',disabled:false},{value:'Exact disease',disabled:false}];
  for(const[id,value]of Object.entries({disease:'',cap:'100',paths:'5',profile:'scoped'}))h.$(id).value=value;
  const context=vm.createContext({$:h.$,mode:()=>selected});
  vm.runInContext('let buildBusy=false;'+['buildReadiness','updateBuildAvailability','busy'].map(n=>fn(html,n)).join('\n'),context);
  return {...h,context,run:code=>vm.runInContext(code,context),mode:value=>{selected=value;}};
}
test('live build explains its exact disease prerequisite and enables the valid default profile',()=>{const h=builder();h.run('busy(false)');assert.equal(h.$('buildBtn').disabled,true);assert.match(h.$('buildHint').textContent,/exact disease/i);
  h.$('disease').value='Exact disease';h.run('updateBuildAvailability()');assert.equal(h.$('buildBtn').disabled,false);assert.match(h.$('buildHint').textContent,/ready/i);
  h.run('busy(true)');assert.equal(h.$('buildBtn').disabled,true);h.run('busy(false)');assert.equal(h.$('buildBtn').disabled,false);
  h.$('disease').value='';h.run('busy(false)');assert.equal(h.$('buildBtn').disabled,true);
});
test('backend-required numeric ranges gate live building; invented demo stays available',()=>{const h=builder();h.$('disease').value='Exact disease';h.$('paths').value='-1';h.run('updateBuildAvailability()');assert.equal(h.$('buildBtn').disabled,true,'backend validates pathway_top before overriding scoped retrieval');assert.match(h.$('buildHint').textContent,/Switch to Quick pathway preview/);
  h.$('profile').value='preview';h.run('updateBuildAvailability()');assert.equal(h.$('buildBtn').disabled,true);
  h.$('paths').value='0';h.run('updateBuildAvailability()');assert.equal(h.$('buildBtn').disabled,false);
  for(const cap of ['','0','501','2.5']){h.$('cap').value=cap;h.run('updateBuildAvailability()');assert.equal(h.$('buildBtn').disabled,true);}
  h.mode('demo');h.run('updateBuildAvailability()');assert.equal(h.$('buildBtn').disabled,false);
});
test('guarded build makes no request until ready and preserves the established valid request',async()=>{const h=builder(),calls=[];Object.assign(h.context,{status(){},runId:null,history:{replaceState(){}},showGraph(){},api:async(url,body)=>{calls.push({url,body});return {run_id:'invented',graph:{}};}});
  h.$('schemaCheck').checked=true;h.run('async '+fn(html,'build'));await h.run('build()');assert.equal(calls.length,0);
  h.$('disease').value='Exact disease';await h.run('build()');assert.deepEqual(JSON.parse(JSON.stringify(calls)),[{url:'/api/build',body:{mode:'live',disease:'Exact disease',max_targets:100,pathway_top:5,profile:'scoped',tissue_term:'',refresh:false,check_schema:true}}]);assert.equal(h.$('buildBtn').disabled,false);
});
function checkHit(svg,click){const lines=svg.children.filter(n=>n.tag==='line');assert.equal(lines.length,2);const hit=lines.find(n=>n.attrs.stroke==='transparent'),visible=lines.find(n=>n!==hit);
  assert.equal(hit.attrs['stroke-width'],14);assert.equal(hit.attrs['stroke-dasharray'],'none');assert.equal(hit.attrs['vector-effect'],'non-scaling-stroke');assert.equal(hit.attrs['pointer-events'],'stroke');assert.equal(visible.attrs['pointer-events'],'none');
  assert.ok(visible.attrs['stroke-dasharray']);assert.equal(hit.attrs.tabindex,0);click(hit);return hit;}
test('guided dashed evidence keeps its visual semantics and has a continuous wide hit target',()=>{const h=dom(),calls=[];const answer={plan:{protein:{id:'p1',sym:'ONE'}},nodes:[{id:'p1',category:'biolink:Protein'},{id:'p2',category:'biolink:Protein'}],results:[{protein:{id:'p2',sym:'TWO'},paths:[{kind:'interaction',assertion_ids:['a1'],node_ids:['p1','p2']}]}],citations:[{id:'E001',assertion_id:'a1',subject:'p1',object:'p2',predicate:'interacts',review_state:'candidate'}]};
  const context=vm.createContext({$:h.$,questionAnswer:answer,questionSelection:'p2',svgEl:node,relationLabel:x=>x,inspectQuestionCitation:id=>calls.push(id)});vm.runInContext(fn(guided,'renderQuestionGraph'),context);vm.runInContext('renderQuestionGraph()',context);
  const hit=checkHit(h.$('questionGraph').children[0],n=>n.onclick());hit.onkeydown({key:' ',preventDefault(){}});assert.deepEqual(calls,['E001','E001']);
});
test('bounded graph uses the same full hit target without changing the evidence selection',()=>{const h=dom(),calls=[],targets=[{id:'p1'},{id:'p2'}],edge={subject:'p1',object:'p2',predicate:'observed',record_kind:'assay_observation',qualifiers:{measurement_qualifier:'detected'}};
  h.$('assertionProtein').value='all';const graph={targets,nodes:targets.map(n=>({...n,category:'biolink:Protein'}))};
  const context=vm.createContext({$:h.$,graph,filteredTargets:()=>targets.slice(),visibleEdges:()=>[edge],bothProteinEnds:()=>true,svgEl:node,relationLabel:x=>x,assayLabel:x=>x,nodeLabel:x=>x,inspectEdge:e=>calls.push(e),inspectTarget(){},inspectNode(){}});vm.runInContext(fn(html,'renderGraph'),context);vm.runInContext('renderGraph()',context);
  const hit=checkHit(h.$('graphBox').children[0],n=>n.listeners.click());hit.listeners.keydown({key:' ',preventDefault(){}});assert.equal(calls.length,2);assert.equal(calls[0],edge);assert.equal(calls[1],edge);
});
test('legacy headings no longer imply an incomplete numbered wizard',()=>{assert.doesNotMatch(html,/<h2>1\. Choose a data source/);assert.doesNotMatch(html,/<h2>2\. Explore the bounded graph/);assert.doesNotMatch(html,/<h2>3\. Review assertions and records/);assert.match(html,/id="workspaceTabAsk"[^>]*>Question &amp; graph/);});
