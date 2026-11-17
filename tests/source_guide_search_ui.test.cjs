// The guide uses the same identifier-and-label search pattern as nearby selectors.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');

function harness(assertions){
  const source=fs.readFileSync(path.join(__dirname,'../biograph_steward/navigation.js'),'utf8');
  const start=source.indexOf('function claimLabel(a){'),end=source.indexOf('\nfunction populatePathEntities()',start);
  assert.ok(start>=0&&end>start,'existing source-guide selector remains available');
  const element=()=>({value:'',textContent:'',disabled:false,options:[],
    replaceChildren(){this.options=[];this.value='';},append(option){this.options.push(option);}});
  const elements={sourceGuideSearch:element(),sourceGuideSelection:element(),sourceGuideCount:element(),sourceGuideButton:element()};
  const labels={'UniProtKB:P01111':'NRAS','UniProtKB:P15056':'BRAF','GO:0005794':'Golgi apparatus','GO:0004674':'protein kinase activity'};
  const context=vm.createContext({graph:{assertions},runId:'invented',
    $:id=>elements[id],el:(tag,label)=>({tag,textContent:label,value:''}),
    nodeLabel:id=>labels[id]||id,relationLabel:()=> 'GO annotation'});
  vm.runInContext(source.slice(start,end),context);
  return {elements,context,search(query){elements.sourceGuideSearch.value=query;vm.runInContext('populateSourceGuide()',context);return elements.sourceGuideSelection.options.map(option=>option.value);}};
}

test('source guide finds raw GO, protein and predicate identifiers as well as labels',()=>{
  const assertions=[{id:'claim:NRAS',subject:'UniProtKB:P01111',predicate:'biolink:has_go_annotation',object:'GO:0005794',lifecycle_state:'candidate'},
    {id:'claim:BRAF',subject:'UniProtKB:P15056',predicate:'biolink:has_go_annotation',object:'GO:0004674',lifecycle_state:'candidate'}];
  const before=JSON.stringify(assertions),ui=harness(assertions);
  for(const query of ['GO:0005794',' go:0005794 ','UniProtKB:P01111','UNIPROTKB:P01111','Golgi apparatus','nras','claim:NRAS']){
    assert.deepEqual(ui.search(query),['claim:NRAS'],query);
  }
  assert.deepEqual(ui.search('BIOLINK:HAS_GO_ANNOTATION'),['claim:NRAS','claim:BRAF']);
  assert.deepEqual(ui.search('not present'),[]);assert.equal(ui.elements.sourceGuideButton.disabled,true);
  assert.equal(JSON.stringify(assertions),before);
});

test('source guide retains its first-100 cap, source ordering and selected visible claim',()=>{
  const assertions=Array.from({length:105},(_,i)=>({id:'claim:'+i,subject:'UniProtKB:P01111',predicate:'biolink:has_go_annotation',object:'GO:0005794',lifecycle_state:'candidate'}));
  const ui=harness(assertions);ui.elements.sourceGuideSelection.value='claim:42';
  assert.deepEqual(ui.search('GO:0005794'),assertions.slice(0,100).map(a=>a.id));
  assert.equal(ui.elements.sourceGuideSelection.value,'claim:42');
  assert.match(ui.elements.sourceGuideCount.textContent,/105 matching claims/);
  assert.match(ui.elements.sourceGuideCount.textContent,/Showing the first 100/);
  assert.equal(ui.elements.sourceGuideButton.disabled,false);
  ui.context.runId=null;ui.search('');assert.equal(ui.elements.sourceGuideButton.disabled,true);
});
