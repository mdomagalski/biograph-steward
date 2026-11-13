// Native GO context remains separate, immutable and bound to the selected claim.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const clone=value=>JSON.parse(JSON.stringify(value));

function element(tag,value){return {tag,textContent:value===undefined?'':String(value),children:[],attributes:{},disabled:false,
  append(...items){this.children.push(...items);},replaceChildren(...items){this.children=[...items];},setAttribute(k,v){this.attributes[k]=v;}};}
function descendants(node,tag){return (node.tag===tag?[node]:[]).concat(...node.children.map(child=>descendants(child,tag)));}
function text(node){return node.textContent+node.children.map(text).join(' ');}
function fixture(){
  const record={id:'goa.native:invented1',source_line:11,subject:'UniProtKB:P15056',go_id:'GO:0004674',relation_literal:'enables',negated:false,
    evidence_code:'IDA',assigned_by:'INVENTED',annotation_date:'20260101',gene_product_form_id:null,taxon_ids:['taxon:9606'],
    reference_identifiers:['PMID:36949045','DOI:10.1000/invented','OTHER:one','javascript:alert(1)'],
    annotation_extension_raw:'part_of(CL:0000639),occurs_in(GO:0005737)|part_of(CL:0000236)',
    extension_or_groups_raw:[['part_of(CL:0000639)','occurs_in(GO:0005737)'],['part_of(CL:0000236)']],
    with_from_raw:'UniProtKB:P00001|UniProtKB:P00002,UniProtKB:P00003',with_from_or_groups_raw:[['UniProtKB:P00001'],['UniProtKB:P00002','UniProtKB:P00003']],
    raw_line:'Invented raw source <img src=x onerror="bad()">',parsed:{DB_Object_Symbol:'BRAF'},strict_projection_candidate_for_edge_ids:['invented:edge:1']};
  const other=clone(record);other.id='goa.native:invented2';other.source_line=12;other.negated=true;other.gene_product_form_id='UniProtKB:P15056-2';
  other.annotation_extension_raw='';other.extension_or_groups_raw=[];other.strict_projection_candidate_for_edge_ids=[];
  const response={format:'biograph-steward.native-go-selection.v1',source_run:'invented_workspace',selection_id:'claim:go',snapshot_sha256:'invented-snapshot',read_only:true,
    source:{headers:['!gaf-version: 2.2','!generated-by: INVENTED','!date-generated: 2026-01-01','!go-version: invented'],gaf_sha256:'a'.repeat(64)},
    query:{protein:record.subject,go_id:record.go_id},record_count:2,records:[record,other],
    compatibility:{status:'one_compatible_native_record',candidate_count:1,native_record_ids:[record.id]},limitations:['Invented source boundary.'],quality_control:{status:'not_configured'}};
  const guide={source_run:response.source_run,snapshot_sha256:response.snapshot_sha256,selection:{id:response.selection_id},
    assertion:{subject:record.subject,object:record.go_id,predicate:'biolink:has_go_annotation'},summary:'Invented original Pharos projection',review:{note:'Original review unchanged'},qualifiers:{},
    sections:[],links:[],questions:[],limitations:[],missing_context:[],source_records:[],native_go_context:{configured:true,eligible:true}};
  return {guide,response};
}
function harness(apiImpl){
  const source=fs.readFileSync(path.join(__dirname,'../biograph_steward/navigation.js'),'utf8');
  const helpersStart=source.indexOf('function guideLink(link){'),helpersEnd=source.indexOf('\nasync function loadSourceGuide',helpersStart);
  const start=source.indexOf('function renderSourceGuide(result){'),end=source.indexOf('\nasync function runPathExploration',start);
  assert.ok(helpersStart>=0&&helpersEnd>helpersStart&&start>=0&&end>start);
  const output=element('div'),selection={value:'claim:go'},calls=[];
  const context=vm.createContext({el:element,$:id=>id==='sourceGuideSelection'?selection:output,
    graph:{snapshot_sha256:'invented-snapshot'},runId:'invented_workspace',inspectionRequest:7,
    nodeLabel:value=>value,relationLabel:value=>value,document:{createTextNode:value=>element('text',value)},
    api:async(url,body)=>{calls.push({url,body:clone(body)});return apiImpl(url,body);}});
  vm.runInContext(source.slice(helpersStart,helpersEnd)+'\n'+source.slice(start,end),context);
  return {context,output,selection,calls,render(guide){context.guide=guide;vm.runInContext('renderSourceGuide(guide)',context);return output;},
    button(){return descendants(output,'button').find(node=>node.textContent==='Inspect preserved native GO annotations');}};
}

test('native GO inspection is opt-in and offered only for configured eligible claims',()=>{
  for(const flags of [undefined,{configured:false,eligible:true},{configured:true,eligible:false},{configured:true,eligible:true}]){
    const {guide,response}=fixture(),ui=harness(async()=>response);guide.native_go_context=flags;ui.render(guide);
    assert.equal(Boolean(ui.button()),flags?.configured===true&&flags?.eligible===true);assert.equal(ui.calls.length,0);
  }
});

test('native rows preserve polarity, references, forms and OR-of-AND context as text',async()=>{
  const {guide,response}=fixture(),before=JSON.stringify({guide,response}),ui=harness(async()=>response);
  ui.render(guide);await ui.button().onclick();
  assert.deepEqual(ui.calls,[{url:'/api/native-go-context',body:{run_id:'invented_workspace',selection_id:'claim:go'}}]);
  assert.equal(descendants(ui.output,'article').length,2);assert.match(text(ui.output),/Positive-polarity annotation/);assert.match(text(ui.output),/NOT annotation/);
  assert.match(text(ui.output),/qualified by NOT/);assert.match(text(ui.output),/UniProtKB:P15056-2/);
  assert.match(text(ui.output),/Alternative 1: part_of\(CL:0000639\) AND occurs_in\(GO:0005737\)/);
  assert.match(text(ui.output),/Alternative 2: part_of\(CL:0000236\)/);
  assert.match(text(ui.output),/not independent experiment counts/);assert.match(text(ui.output),/do not identify or repair the historical Pharos record/);
  assert.match(text(ui.output),/No bound saved native quality-check output is configured/);
  assert.match(text(ui.output),/Matches the available Pharos fields; original annotation identity remains unresolved/);
  assert.match(text(ui.output),/Related native annotation for this exact protein\/GO pair; not a strict match/);
  const links=descendants(ui.output,'a');
  assert.ok(links.some(a=>a.href==='https://pubmed.ncbi.nlm.nih.gov/36949045/'));
  assert.ok(links.some(a=>a.href==='https://doi.org/10.1000%2Finvented'));
  assert.ok(links.every(a=>a.href.startsWith('https://pubmed.ncbi.nlm.nih.gov/')||a.href.startsWith('https://doi.org/')));
  assert.equal(descendants(ui.output,'img').length,0);assert.equal(descendants(ui.output,'script').length,0);
  assert.match(text(ui.output),/<img src=x onerror="bad\(\)">/);
  const preserved=descendants(ui.output,'pre').filter(node=>node.textContent.startsWith('{')).map(node=>JSON.parse(node.textContent)).filter(value=>value.id?.startsWith('goa.native:'));
  assert.deepEqual(preserved,response.records);assert.equal(JSON.stringify({guide,response}),before);
});

test('saved QC flags remain derivative-specific and do not imply biological rejection',async()=>{
  const {guide,response}=fixture();response.quality_control={status:'verified_saved_output',method_note:'Actual saved selected native rules; not rerun here.',limits:['Not full GO pipeline conformance.']};
  response.records[0].saved_quality_control={extension_unsatisfiable:true,normalization:{base_rule_filtered:false,changed_columns:[{column:4,field:'relation',before:'part_of',after_values:['located_in']}]},
    rule_results:[{rule:'GORULE:0000061',result_type:'REPAIRED',message:'Invented repair'}],taxon_result:{result_type:'PASS',negated_annotation_exempt:false,message:'Invented selected rule'}};
  response.records[1].saved_quality_control={normalization:{base_rule_filtered:true,changed_columns:[]},rule_results:[],taxon_result:{result_type:'EXEMPT',negated_annotation_exempt:true,message:''}};
  const before=JSON.stringify(response),ui=harness(async()=>response);ui.render(guide);await ui.button().onclick();
  assert.match(text(ui.output),/combination of context terms conflicts under the pinned ontology/);
  assert.match(text(ui.output),/base annotation is not judged biologically false/);
  assert.match(text(ui.output),/Normalized derivative: relation/);assert.match(text(ui.output),/part_of/);assert.match(text(ui.output),/located_in/);
  assert.match(text(ui.output),/this NOT-qualified record is exempt, not a validated taxon pass/);
  assert.match(text(ui.output),/No taxon conflict reported by this saved check/);
  assert.match(text(ui.output),/Pharos graph is unchanged/);assert.match(text(ui.output),/Not full GO pipeline conformance/);
  const provenance=descendants(ui.output,'details').find(value=>value.children.some(child=>child.tag==='summary'&&child.textContent==='Source version and inspection boundaries'));
  assert.match(text(provenance),/Not full GO pipeline conformance/);assert.match(text(provenance),/Actual saved selected native rules; not rerun here/);
  assert.equal(JSON.stringify(response),before);
});

test('empty native scope remains unknown rather than biological absence',async()=>{
  const {guide,response}=fixture();response.records=[];response.record_count=0;response.compatibility={status:'no_compatible_native_record',candidate_count:0,native_record_ids:[]};
  const ui=harness(async()=>response);ui.render(guide);await ui.button().onclick();
  assert.match(text(ui.output),/No matching row was found in this preserved source scope/);assert.match(text(ui.output),/not evidence of biological absence/);
});

test('changed selection, workspace, snapshot or request cannot display stale GO context',async()=>{
  for(const mutate of [ui=>{ui.selection.value='claim:other';},ui=>{ui.context.runId='other_workspace';},ui=>{ui.context.graph.snapshot_sha256='other_snapshot';},ui=>{ui.context.graph=null;},ui=>{ui.context.inspectionRequest++;}]){
    const {guide,response}=fixture();let resolve;const pending=new Promise(done=>{resolve=done;}),ui=harness(async()=>pending);ui.render(guide);
    const request=ui.button().onclick();mutate(ui);resolve(response);await request;
    assert.equal(descendants(ui.output,'article').length,0);
  }
});

test('mismatched result bindings and incomplete record counts remain unresolved',async()=>{
  for(const mutate of [v=>{v.format='other';},v=>{v.source_run='other';},v=>{v.selection_id='other';},v=>{v.snapshot_sha256='other';},v=>{v.read_only=false;},v=>{v.query.protein='UniProtKB:P00001';},v=>{v.query.go_id='GO:0000001';},v=>{v.record_count=1;}]){
    const {guide,response}=fixture();mutate(response);const ui=harness(async()=>response);ui.render(guide);await ui.button().onclick();
    assert.equal(descendants(ui.output,'article').length,0);assert.match(text(ui.output),/Native GO context remains unresolved/);assert.equal(ui.calls.length,1);
  }
});

test('source read failure remains unresolved without a fallback request',async()=>{
  const {guide}=fixture(),ui=harness(async()=>{throw new Error('Preserved source could not be verified.');});ui.render(guide);await ui.button().onclick();
  assert.match(text(ui.output),/Native GO context remains unresolved: Preserved source could not be verified/);assert.equal(ui.calls.length,1);assert.equal(descendants(ui.output,'article').length,0);
});
