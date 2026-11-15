// The legacy source card owns STRING-functional/MAP-IT/SIGNOR/BioPlex only.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {test}=require('node:test');
function harness(){
  const elements=new Map();
  const $=id=>{if(!elements.has(id)){const classes=new Set();elements.set(id,{value:'',hidden:false,disabled:false,textContent:'',
    options:['mapit','signor','bioplex'].map(value=>({value})),
    classList:{add:x=>classes.add(x),toggle(x,on){on?classes.add(x):classes.delete(x);},contains:x=>classes.has(x)},
    replaceChildren(){},addEventListener(){}});}return elements.get(id);};
  const context=vm.createContext({$,graph:{},runId:'invented',setupRegulatory(){},api(){throw new Error('No source or question request expected');}});
  vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../biograph_steward/biological.js'),'utf8'),context);
  return {$,context,setup(sources){context.graph={evidence_extension:{sources}};context.setupBiological();}};
}
test('native-only and unsupported source profiles do not create an empty legacy card',()=>{
  const ui=harness();
  for(const sources of [{},{goa:{}},{string_physical:{}},{goa:{},string_physical:{}},{future_profile:{}}]){
    ui.setup(sources);assert.equal(ui.$('biologicalPanel').classList.contains('hidden'),true);
  }
});
test('each owned legacy source still renders its existing card and workspace switching clears ownership',()=>{
  const ui=harness();
  for(const kind of ['string','mapit','signor','bioplex']){
    ui.setup({[kind]:{}});assert.equal(ui.$('biologicalPanel').classList.contains('hidden'),false);
    ui.setup({goa:{},string_physical:{}});assert.equal(ui.$('biologicalPanel').classList.contains('hidden'),true);
  }
});
