const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const html=fs.readFileSync(path.join(__dirname,'../biograph_steward/ui.html'),'utf8');
function harness(nodes){
  const setup=html.slice(html.indexOf('nodeIndex=new Map(g.nodes.map'),html.indexOf('contextPage=0;',html.indexOf('nodeIndex=new Map(g.nodes.map')));
  const label=html.slice(html.indexOf('function nodeLabel(id){'),html.indexOf('\n',html.indexOf('function nodeLabel(id){')));
  const context=vm.createContext({g:{nodes},nodeIndex:new Map(),proteinSymbolCounts:new Map()});
  vm.runInContext(setup+'\n'+label,context);
  return id=>vm.runInContext('nodeLabel('+JSON.stringify(id)+')',context);
}
test('same-symbol protein products retain separate visible identities without merging source records',()=>{
  const nodes=[{id:'UniProtKB:P39880',sym:'CUX1',name:'Homeobox protein cut-like 1',category:'biolink:Protein'},
    {id:'UniProtKB:Q13948',sym:'CUX1',name:'Protein CASP',category:'biolink:Protein'},
    {id:'UniProtKB:P04637',sym:'TP53',category:'biolink:Protein'}];
  const before=JSON.stringify(nodes),label=harness(nodes);
  assert.equal(label(nodes[0].id),'CUX1 (P39880)');assert.equal(label(nodes[1].id),'CUX1 (Q13948)');
  assert.equal(label(nodes[2].id),'TP53');assert.equal(JSON.stringify(nodes),before);
});
test('a nonprotein label is not evidence of a second protein product',()=>{
  const label=harness([{id:'UniProtKB:P39880',sym:'CUX1',category:'biolink:Protein'},{id:'synthetic:pathway',sym:'CUX1',category:'biolink:Pathway'}]);
  assert.equal(label('UniProtKB:P39880'),'CUX1');assert.equal(label('missing:id'),'missing:id');
});
test('switching a same-name product retargets the assertion filter before reading its records',()=>{
  const source=html.slice(html.indexOf('function inspectSameSymbolProtein(id){'),html.indexOf('\n',html.indexOf('function inspectSameSymbolProtein(id){')));
  const field={value:'UniProtKB:P39880',options:[{value:'all'},{value:'UniProtKB:P39880'},{value:'UniProtKB:Q13948'}]},events=[];
  const context=vm.createContext({$:()=>field,render:()=>events.push('render:'+field.value),inspectTarget:id=>events.push('inspect:'+id)});
  vm.runInContext(source+"\ninspectSameSymbolProtein('UniProtKB:Q13948');",context);
  assert.equal(field.value,'UniProtKB:Q13948');assert.deepEqual(events,['render:UniProtKB:Q13948','inspect:UniProtKB:Q13948']);
  events.length=0;vm.runInContext("inspectSameSymbolProtein('synthetic:noncohort');",context);
  assert.equal(field.value,'all');assert.equal(events[0],'render:all');
});
