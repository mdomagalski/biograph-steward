// Read-only aggregate results. No reference rows, model calls or graph writes.
let biologicalComparisonCatalogEpoch=0,biologicalComparisonSummaryEpoch=0;
let biologicalComparisonId='',biologicalComparisonInitialized=false;
const biologicalComparisonArms=['unpruned','human_experimental_top80','native_top80','ne_top80','pa_top80','combined_experimental_top80','mps_top80'];
const biologicalComparisonFiles={
  'processed_qc_report.json':'Current processed-reference result',
  'processed_qc_protocol.json':'Processed-reference protocol',
  'report.json':'Original figure-data result',
  'protocol.json':'Original frozen protocol',
  'source_qualification.json':'Source qualification',
  'selection_receipt.json':'Preselected graph views',
  'sources.json':'Study and source links'
};
function biologicalComparisonCount(value){return Number.isInteger(value)&&value>=0?value.toLocaleString():'Not supplied';}
function biologicalComparisonPercent(value){return typeof value==='number'&&Number.isFinite(value)?(100*value).toFixed(1)+'%':'Unscorable';}
function biologicalComparisonStatus(text,error=false){
  $('biologicalComparisonStatus').textContent=text;
  $('biologicalComparisonStatus').className=error?'notice error':'small';
}
async function biologicalComparisonGet(path){
  const response=await fetch(path);let result;
  try{result=await response.json();}catch(_){throw new Error('The workspace did not return a saved comparison.');}
  if(!response.ok)throw new Error(result.error||'The saved experimental comparison could not be verified.');
  return result;
}
function biologicalComparisonBase(id){
  if(typeof id!=='string'||!/^[A-Za-z0-9_-]{1,80}$/.test(id))throw new Error('Invalid saved comparison identifier.');
  return '/api/biological-comparison/'+encodeURIComponent(id);
}
function biologicalComparisonView(summary){
  if(summary?.format!=='biograph-steward.biological-comparison-publication.v1.summary'||
      summary.scientific_accuracy_established!==false||summary.graph_changes_performed_by_viewer!==false)
    throw new Error('The saved comparison scope is invalid.');
  const current=summary.current_processed_reference_check;
  if(current&&(!current.strict||!current.entry_family||current.new_independent_confirmation!==false))
    throw new Error('The processed-reference check is incomplete.');
  const metrics=current?current.strict:{arms:summary.arms,primary_unique_eligible_positive_pairs:summary.positive_reference_pairs};
  const count=metrics.primary_unique_eligible_positive_pairs;
  if(!Number.isInteger(count)||count<0||!biologicalComparisonArms.every(arm=>{
    const row=metrics.arms?.[arm];
    return row&&row.eligible_positive_pairs===count&&Number.isInteger(row.positive_pairs_retained)&&
      row.positive_pairs_retained>=0&&row.positive_pairs_retained<=count;
  })||summary.primary_arm!=='human_experimental_top80')throw new Error('The saved comparison counts are incomplete.');
  return {current,metrics,count};
}
function renderBiologicalComparison(summary,id){
  const {current,metrics,count}=biologicalComparisonView(summary),base=biologicalComparisonBase(id);
  const primary=metrics.arms[summary.primary_arm],native=metrics.arms.native_top80,ne=metrics.arms.ne_top80;
  $('biologicalComparisonScope').textContent='Historical source graph: '+biologicalComparisonCount(summary.source_graph_nodes)+
    ' proteins and '+biologicalComparisonCount(summary.source_pairs)+' source pairs. This is separate from the colorectal 99-protein workspace. '+
    'Each ranked view retains '+biologicalComparisonCount(summary.ranked_view_pairs_retained)+' source pairs; the original graph remains intact.';
  $('biologicalComparisonFinding').textContent=(current?'Current author-processed check: ':'Original figure-data assessment: ')+
    'the fixed primary retains '+biologicalComparisonCount(primary.positive_pairs_retained)+' of '+biologicalComparisonCount(count)+
    ' eligible positive pairs ('+biologicalComparisonPercent(primary.micro_retention)+'), compared with '+
    biologicalComparisonCount(native.positive_pairs_retained)+' for native STRING confidence and '+
    biologicalComparisonCount(ne.positive_pairs_retained)+' for Network Enhancement. '+
    (current?'This is a correction within the same study, not another untouched confirmation.':'Author-processed QC is not supplied for this publication.');
  const table=el('table'),head=el('thead'),header=el('tr'),body=el('tbody');
  table.append(el('caption',current?'Current processed reference · strict accession mapping':'Original reference · strict accession mapping'));
  for(const label of ['Fixed graph view','Positive pairs retained','Retention','Isolated proteins']){
    const th=el('th',label);th.scope='col';header.append(th);
  }
  head.append(header);
  for(const arm of biologicalComparisonArms){
    const row=metrics.arms[arm],tr=el('tr');
    const label=(summary.labels?.[arm]||arm)+(arm==='ne_top80'?' (secondary comparator)':'');
    for(const value of [label,biologicalComparisonCount(row.positive_pairs_retained)+' / '+biologicalComparisonCount(count),
      biologicalComparisonPercent(row.micro_retention),biologicalComparisonCount(row.isolated_proteins)])tr.append(el('td',value));
    body.append(tr);
  }
  table.append(head,body);$('biologicalComparisonTable').replaceChildren(table);
  const sensitivity=$('biologicalComparisonSensitivity');sensitivity.textContent='';
  if(current){
    const entry=current.entry_family,n=entry.primary_unique_eligible_positive_pairs;
    sensitivity.textContent='Entry-level sensitivity: fixed primary '+biologicalComparisonCount(entry.arms?.[summary.primary_arm]?.positive_pairs_retained)+
      '/'+biologicalComparisonCount(n)+', native '+biologicalComparisonCount(entry.arms?.native_top80?.positive_pairs_retained)+
      '/'+biologicalComparisonCount(n)+', Network Enhancement '+biologicalComparisonCount(entry.arms?.ne_top80?.positive_pairs_retained)+
      '/'+biologicalComparisonCount(n)+'. This broader mapping does not establish isoform, sequence or construct equivalence.';
  }
  const details=$('biologicalComparisonDetails');details.replaceChildren();
  if(current){
    details.append(el('p','Strict mapping scores '+biologicalComparisonCount(count)+' unique eligible positive pairs from '+
      biologicalComparisonCount(metrics.native_call_rows_preserved)+' author-reported call rows; '+
      biologicalComparisonCount(metrics.evaluation_category_row_counts?.mapping_unresolved)+' rows remain unresolved. '+
      biologicalComparisonCount(metrics.evaluable_exact_author_bait_ENSGs)+' bait genes have an eligible denominator; '+
      biologicalComparisonCount(metrics.zero_denominator_valid_bait_ENSGs)+' do not.','small'));
    details.append(el('p',current.reference,'small'));
  }
  details.append(el('p','This is one HEK293T protein-association study, with positive calls only. Missing, unresolved or source-absent pairs are not negative interactions. Retention does not estimate pruning precision, direct binding, clinical relevance or colorectal-cancer accuracy.','small'));
  details.append(el('p','All ranked views use the same retained-pair budget. Exploratory methods do not replace the fixed primary after seeing results. '+
    biologicalComparisonCount(summary.source_pairs_removed_per_ranked_view)+' source pairs are removed in each ranked view; protected and quarantined records remain retained.','small'));
  details.append(el('p','The original figure-data assessment remains available below. Current processing checks preserve the original rankings, graph budgets and study history.','small'));
  const links=$('biologicalComparisonLinks');links.replaceChildren();
  links.append(guideLink({label:'Open complete comparison report',url:base+'/report.html'}));
  for(const [name,label] of Object.entries(biologicalComparisonFiles)){
    if(summary.downloads?.[name]!==base+'/files/'+name)continue;
    const link=guideLink({label,url:base+'/files/'+name});link.download=name;
    if(name==='processed_qc_report.json'||name==='report.json')links.append(link);
    else {const line=el('p');line.append(link);details.append(line);}
  }
  $('biologicalComparisonBody').hidden=false;
}
async function loadBiologicalComparison(id){
  const request=++biologicalComparisonSummaryEpoch;biologicalComparisonId=id;
  $('biologicalComparisonBody').hidden=true;biologicalComparisonStatus('Verifying the saved experimental comparison…');
  try{
    const summary=await biologicalComparisonGet(biologicalComparisonBase(id));
    if(request!==biologicalComparisonSummaryEpoch||id!==biologicalComparisonId)return;
    if(summary.id!==id)throw new Error('The comparison belongs to a different saved assessment.');
    renderBiologicalComparison(summary,id);
    biologicalComparisonStatus('Saved aggregate results verified. No source retrieval, model call or graph change was made.');
  }catch(error){if(request===biologicalComparisonSummaryEpoch){$('biologicalComparisonBody').hidden=true;biologicalComparisonStatus(error.message,true);}}
}
async function loadBiologicalComparisons(){
  const request=++biologicalComparisonCatalogEpoch,previous=biologicalComparisonId;
  biologicalComparisonSummaryEpoch++;biologicalComparisonId='';$('biologicalComparisonBody').hidden=true;
  const select=$('biologicalComparisonSelection');select.disabled=true;$('biologicalComparisonReload').disabled=true;
  biologicalComparisonStatus('Checking saved experimental comparisons…');
  try{
    const result=await biologicalComparisonGet('/api/biological-comparisons');
    if(request!==biologicalComparisonCatalogEpoch)return;
    if(!Array.isArray(result.comparisons)||!result.comparisons.every(row=>typeof row.id==='string'&&/^[A-Za-z0-9_-]{1,80}$/.test(row.id)))
      throw new Error('The saved comparison list is invalid.');
    select.replaceChildren();
    for(const row of result.comparisons){const option=el('option',(row.summary?.title||'Experimental reference comparison')+' · '+row.id);option.value=row.id;select.append(option);}
    if(!result.comparisons.length){const option=el('option','No verified saved comparison');option.value='';select.append(option);biologicalComparisonStatus('No verified experimental comparison is available.');return;}
    select.value=result.comparisons.some(row=>row.id===previous)?previous:result.comparisons[0].id;select.disabled=false;
    await loadBiologicalComparison(select.value);
  }catch(error){if(request===biologicalComparisonCatalogEpoch)biologicalComparisonStatus(error.message,true);}
  finally{if(request===biologicalComparisonCatalogEpoch)$('biologicalComparisonReload').disabled=false;}
}
function initializeBiologicalComparisons(){
  if(biologicalComparisonInitialized)return;biologicalComparisonInitialized=true;
  $('biologicalComparisonSelection').onchange=()=>loadBiologicalComparison($('biologicalComparisonSelection').value);
  $('biologicalComparisonReload').onclick=loadBiologicalComparisons;
  loadBiologicalComparisons();
}
