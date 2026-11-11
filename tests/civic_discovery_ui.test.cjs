// Synthetic DOM checks for external discovery links; not literature or usability validation.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');

function harness(){
  const elements=new Map(),network=[];
  function element(tag='div',text=''){
    return {tag,tagName:tag.toUpperCase(),textContent:text,children:[],
      classList:{add(){},remove(){},toggle(){}},append(...items){this.children.push(...items);},
      replaceChildren(...items){this.children=[...items];},setAttribute(){},addEventListener(){},scrollIntoView(){}};
  }
  const $=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
  const graph={assertions:[{id:'synthetic:assertion',review_state:'candidate'}],question_basis_sha256:'synthetic-basis'};
  const context=vm.createContext({$,graph,el:element,evidenceCard:()=>element('div','Source record'),
    fetch:async(...args)=>{network.push(args);throw new Error('Unexpected discovery retrieval');},
    api:async(...args)=>{network.push(args);throw new Error('Unexpected API call');}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../biograph_steward/civic.js'),'utf8'),context);
  return {$,graph,context,network,run:code=>vm.runInContext(code,context)};
}
function links(node){return (node.tag==='a'?[node]:[]).concat(...node.children.map(links));}
function discoveries(node){return links(node).filter(link=>link.href?.startsWith('https://linkeddiscoveries.ncbi.nlm.nih.gov/'));}
function citation({reference='PMID:20619739',publication='https://pubmed.ncbi.nlm.nih.gov/20619739/',rawType='PUBMED',rawId='20619739',contextRecords=true}={}){
  return {id:'E001',review_state:'candidate',qualifiers:{disease:'DOID:9256'},kind:'variant_therapy_response',
    assertion_id:'synthetic:assertion',revision:'synthetic:revision',overlap:{status:'unresolved'},
    study_context:{summary:'Source context',therapy_notes:[],overview:{shared_references:[]},
      records:contextRecords?[{evidence_id:'synthetic:evidence',evidence_level:'B',evidence_level_label:'Clinical evidence',source_title:'Synthetic paper',
        therapy_label:'Synthetic therapy',description:'Synthetic description',evidence_url:'https://civicdb.org/evidence/1',
        source_reference:reference,publication_url:publication,record_locators:['synthetic:locator']}]:[],
      context_note:'Paper verification unresolved.',level_definitions_url:'https://docs.civicdb.org/en/latest/model/evidence/level.html'},
    evidence_records:[{evidence_record:{id:1,status:'ACCEPTED',evidenceLevel:'B',molecularProfile:{name:'Synthetic profile',rawName:'#VID1'},
      disease:{name:'Synthetic disease',doid:'9256'},therapies:[{name:'Synthetic therapy'}],therapyInteractionType:null,
      source:{sourceType:rawType,citationId:rawId,title:'Synthetic paper'}}}]};
}
function checkLink(link,pmid){
  assert.equal(link.href,'https://linkeddiscoveries.ncbi.nlm.nih.gov/'+pmid+'/');
  assert.equal(link.textContent,'Explore related literature · Linked Discoveries');
  assert.equal(link.target,'_blank');assert.equal(link.rel,'noopener noreferrer');
  assert.match(link.title,/discovery leads, not independent confirmation/);
}

test('source-context details link the explicit PMID without requesting or changing evidence',()=>{
  const h=harness(),value=citation(),before=JSON.stringify(value),graphBefore=JSON.stringify(h.graph);
  h.context.input=value;const output=h.run('renderCivicContexts(input)');
  const found=discoveries(output);assert.equal(found.length,1);checkLink(found[0],'20619739');
  assert.ok(links(output).some(link=>link.href==='https://pubmed.ncbi.nlm.nih.gov/20619739/'));
  assert.equal(JSON.stringify(value),before);assert.equal(JSON.stringify(h.graph),graphBefore);assert.equal(h.network.length,0);
});

test('the raw PubMed source passport also exposes a safe discovery link',()=>{
  const h=harness(),value=citation({rawId:'19223544',contextRecords:false}),answer={citations:[value],civic_snapshot_sha256:'synthetic-civic',snapshot_sha256:'synthetic-pharos'};
  const before=JSON.stringify(answer),graphBefore=JSON.stringify(h.graph);h.context.input=answer;
  h.run('civicAnswer=input; inspectCivicCitation("E001")');
  const found=discoveries(h.$('civicPassport'));assert.equal(found.length,1);checkLink(found[0],'19223544');
  assert.ok(links(h.$('civicPassport')).some(link=>link.href==='https://pubmed.ncbi.nlm.nih.gov/19223544/'));
  assert.equal(JSON.stringify(answer),before);assert.equal(JSON.stringify(h.graph),graphBefore);assert.equal(h.network.length,0);
});

test('context references do not infer a PMID from a URL, DOI, malformed ID or title',()=>{
  for(const reference of [undefined,null,'DOI:10.1000/example','20619739','pmid:20619739','PMID:0','PMID:020619739','PMID:20619739 extra','PMID:20619739/','PMID:20619739?x=1']){
    const h=harness(),value=citation({reference});value.study_context.records[0].source_reference=reference;h.context.input=value;
    assert.equal(discoveries(h.run('renderCivicContexts(input)')).length,0,String(reference));
  }
  const h=harness();h.context.input=citation({publication:null});
  assert.equal(discoveries(h.run('renderCivicContexts(input)')).length,0);
});

test('passport discovery links require an explicit PubMed source and canonical positive ID',()=>{
  for(const [rawType,rawId] of [['DOI','20619739'],['PUBMED','10.1000/example'],['PUBMED','0'],['PUBMED','020619739'],['PUBMED','20619739 extra'],['PUBMED','20619739?x=1']]){
    const h=harness();h.context.input={citations:[citation({rawType,rawId,contextRecords:false})]};
    h.run('civicAnswer=input; inspectCivicCitation("E001")');
    assert.equal(discoveries(h.$('civicPassport')).length,0,JSON.stringify([rawType,rawId]));assert.equal(h.network.length,0);
  }
});
