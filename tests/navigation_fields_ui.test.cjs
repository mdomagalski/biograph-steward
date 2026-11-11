// Verify source-field display without changing the values or their qualifications.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');

function harness(){
  const source=fs.readFileSync(path.join(__dirname,'../biograph_steward/navigation.js'),'utf8');
  const start=source.indexOf('function fieldList(fields){'),end=source.indexOf('\nasync function loadSourceGuide',start);
  assert.ok(start>=0&&end>start,'source-field renderer remains available');
  const el=(tag,text)=>({tag,textContent:text===undefined?'':String(text),children:[],append(...items){this.children.push(...items);}});
  const context=vm.createContext({el});vm.runInContext(source.slice(start,end),context);
  return fields=>{context.fields=fields;return vm.runInContext('fieldList(fields)',context);};
}
function descendants(node,tag){return (node.tag===tag?[node]:[]).concat(...node.children.map(child=>descendants(child,tag)));}
function text(node){return node.textContent+node.children.map(text).join(' ');}

test('official-reader field arrays show provided labels and preserve source-column locators',()=>{
  const render=harness(),fields=[{label:'Interaction detection methods',value:'psi-mi:"MI:0410"(3D electron microscopy)',columns:[7]},
    {label:'Negative flag',value:'false',columns:[36]}],before=JSON.stringify(fields),result=render(fields);
  assert.deepEqual(descendants(result,'dt').map(node=>node.textContent),['Interaction detection methods','Negative flag']);
  assert.match(text(result),/Source columns: 7/);assert.match(text(result),/Source columns: 36/);
  assert.match(text(result),/3D electron microscopy/);assert.match(text(result),/false/);
  const preserved=descendants(result,'pre').map(node=>JSON.parse(node.textContent));
  assert.deepEqual(preserved,fields);assert.equal(JSON.stringify(fields),before);
});

test('readable term objects retain exact identifiers and all extra source fields',()=>{
  const render=harness(),term={id:'MI:0498',label:'prey',source_note:'synthetic source condition'},result=render({experimental_role:term});
  assert.match(text(result),/prey \(MI:0498\)/);
  assert.deepEqual(JSON.parse(descendants(result,'pre')[0].textContent),term);
});

test('complete therapy and role lists keep original order and unrecognized grouping',()=>{
  const render=harness(),fields={therapy_members:[{id:2,name:'Drug B'},{id:1,name:'Drug A'}],
    therapy_interaction:'COMBINATION',roles:{participant_a:{id:'MI:0498',label:'prey'},participant_b:{id:'MI:0496',label:'bait'}}};
  const before=JSON.stringify(fields),result=render(fields),items=descendants(result,'li').map(node=>node.textContent);
  assert.deepEqual(items,['Drug B (2)','Drug A (1)']);assert.match(text(result),/COMBINATION/);
  const values=descendants(result,'pre').map(node=>JSON.parse(node.textContent));
  assert.deepEqual(values,[fields.therapy_members,fields.roles]);assert.equal(JSON.stringify(fields),before);
});

test('zero, false, empty source strings and null stay distinct and HTML stays text',()=>{
  const render=harness(),value='<img src=x onerror="throw new Error()">',result=render({score:0,negative:false,empty:'',missing:null,unsafe:value});
  const descriptions=descendants(result,'dd');
  assert.equal(text(descriptions[0]),'0');assert.equal(text(descriptions[1]),'false');
  assert.equal(text(descriptions[2]),'');assert.equal(text(descriptions[3]),'Not supplied');
  assert.equal(text(descriptions[4]),value);assert.equal(descendants(result,'img').length,0);
});

test('source trail distinguishes the retrieval aggregator from supplied source labels',()=>{
  const source=fs.readFileSync(path.join(__dirname,'../biograph_steward/navigation.js'),'utf8');
  const start=source.indexOf('function renderSourceGuide(result){'),end=source.indexOf('\nasync function runPathExploration',start);
  const el=(tag,value)=>({tag,textContent:value===undefined?'':String(value),children:[],append(...items){this.children.push(...items);},replaceChildren(...items){this.children=[...items];}});
  const output=el('div'),context=vm.createContext({el,$:()=>output,fieldList:()=>el('dl'),document:{createTextNode:value=>el('text',value)}});
  vm.runInContext(source.slice(start,end),context);
  context.result={assertion:null,selection:{id:'synthetic:claim'},summary:'Synthetic source fact',review:{note:'Synthetic review state'},qualifiers:{},
    sections:[],links:[],questions:[],limitations:[],missing_context:[],source_records:[{
      aggregator:'IntAct/IMEx distribution',source_labels:['UniProt'],reference_status:'references_supplied',link_ids:[]}]};
  vm.runInContext('renderSourceGuide(result)',context);
  assert.match(text(output),/Retrieved through: IntAct\/IMEx distribution/);
  assert.match(text(output),/Source labels supplied: UniProt/);
  assert.doesNotMatch(text(output),/Primary source:/);
});
