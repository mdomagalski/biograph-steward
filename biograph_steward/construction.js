// A bounded, deterministic construction request. Evidence answers come from Python.
let constructionBusy=false,constructionPlanId=null,constructionPlanGeneration=0;
function clearConstructionPlan(){constructionPlanGeneration++;constructionPlanId=null;$('constructionPlannedBuild').disabled=true;$('constructionPlanPreview').replaceChildren();$('constructionPlanStatus').textContent='';}
function constructionAccessions(){return $('constructionProteins').value.split(/[\s,]+/).filter(Boolean);}
function updateConstructionQuestion(){
  const accessions=constructionAccessions(),previous=$('constructionFocus').value;
  $('constructionFocus').replaceChildren();
  for(const accession of [...new Set(accessions)]){const option=el('option',accession);option.value=accession;$('constructionFocus').append(option);}
  if(accessions.includes(previous))$('constructionFocus').value=previous;
  if(!accessions.length){const option=el('option','Enter the cohort first');option.value='';$('constructionFocus').append(option);}
  const ppi=$('constructionProfile').value==='ppi';
  for(const option of $('constructionRelations').options)option.disabled=ppi&&option.value!=='interactions';
  if(ppi)$('constructionRelations').value='interactions';
  const selected=$('constructionRelations').value,relation=selected==='both'?'reported interactions or shared pathways':selected==='shared_pathways'?'shared pathways':'reported interactions';
  $('constructionQuestion').textContent='Which proteins in this cohort have '+relation+' with '+($('constructionFocus').value||'the selected protein')+'?';
  $('constructionProteinHint').textContent=accessions.length+' of 25 accessions entered. Separate accessions with spaces, commas or new lines. Gene symbols and aliases are not substituted.';
  $('constructionProfileNote').textContent=ppi?'Retrieve interaction annotations and keep partners within your cohort. Missing annotations are not evidence of no interaction.':'Retrieve bounded pathway, GO, interaction, drug and publication context. The answer uses interactions and shared pathways; other records remain available for inspection.';
}
function constructionProgress(message,error=false){const box=$('constructionStatus');box.className=error?'notice error':'notice';box.textContent=message;}
function setupConstructionPublication(g,receipt=null){
  clearConstructionPlan();$('submissionStatus').textContent='';$('submissionDownload').replaceChildren();
  const cohort=!g.disease,scope=g.scope||g.cohort||{},construction=g.construction,demo=g.data_kind==='synthetic_demo';
  const therapy=[...$('questionWorkflow').options].find(o=>o.value==='therapy');
  if(therapy)therapy.disabled=cohort;
  if(cohort){$('questionWorkflow').value='connections';switchQuestionWorkflow();}
  $('benchmarkPanel').classList.toggle('hidden',cohort);
  $('constructionPublication').classList.toggle('hidden',!cohort||!construction);
  if(!cohort||!construction)return;
  const requested=scope.requested_uniprot||construction.request?.accessions||[],resolutions=scope.resolutions||[];
  const unresolved=resolutions.filter(row=>row.status!=='resolved');
  $('constructionPublicationSummary').textContent=(demo?'SYNTHETIC EXAMPLE — invented annotations. ':'')+'Saved in this workspace: '+g.targets.length+' resolved proteins from '+requested.length+' requested accessions, with '+(g.assertions?.length||0)+' candidate and reviewed assertions. Publication preserves the source snapshot and review states.';
  const box=$('constructionPublicationCoverage');box.replaceChildren();
  const focus=construction.request?.focus_uniprot||construction.plan?.focus_uniprot;
  if(receipt?.answer_status==='anchor_unresolved'||unresolved.some(row=>row.requested_uniprot===focus))box.append(el('p','The focus protein did not resolve exactly, so no initial answer was generated. The graph and unresolved identity record are saved. Choose a resolved protein below to ask a new question.','notice warn'));
  if(unresolved.length){box.append(el('p',unresolved.length+' accessions were unresolved. Their absence does not establish missing biology.','notice warn'));
    box.append(table(['Requested accession','Resolution','Returned accession'],unresolved.map(row=>({cells:[row.requested_uniprot||'Not supplied',String(row.status||'unresolved').replaceAll('_',' '),row.returned_uniprot||'Not supplied']}))));}
  else box.append(el('p',demo?'The fixed example contains three synthetic target records.':'Every requested accession resolved exactly. Source-row coverage is shown below.','small'));
  const summary=g.retrieval?.context?.summary||{};
  const rows=Object.entries(summary).filter(([,count])=>Object.keys(count.target_statuses||{}).some(status=>status!=='not_requested')).map(([family,count])=>({cells:[familyNames[family]||family,count.available??'Not supplied',count.retrieved??0,count.retained??0,Object.entries(count.target_statuses||{}).map(([status,n])=>n+' '+status.replaceAll('_',' ')).join('; ')]}));
  if(rows.length)box.append(table(['Evidence family','Reported rows','Scanned rows','Retained rows','Coverage'],rows));
  box.append(el('p','Counts describe this bounded retrieval. Source records are not independent experiments; no score here establishes scientific accuracy.','small'));
  if(runId){const link=el('a','Download graph and source trace');link.href='/api/download/'+encodeURIComponent(runId);box.append(link);}
  $('constructionPublicationTrace').textContent=JSON.stringify({construction,scope,publication:receipt,snapshot_sha256:g.snapshot_sha256,graph_basis_sha256:g.question_basis_sha256,coverage:g.retrieval?.context?.scope},null,2);
  if(requested.length){$('constructionProteins').value=requested.join(', ');$('constructionProfile').value=construction.request?.profile||construction.plan?.profile||'ppi';updateConstructionQuestion();const focus=construction.request?.focus_uniprot||construction.plan?.focus_uniprot;if(requested.includes(focus))$('constructionFocus').value=focus;updateConstructionQuestion();}
}
async function constructGraph(mode='live'){
  const demo=mode==='demo',planned=mode==='planned';
  if(planned&&!constructionPlanId){constructionProgress('Plan the question before building.',true);return;}
  if(constructionBusy||(!demo&&!$('constructionForm').reportValidity()))return;
  const accessions=constructionAccessions();
  if(!demo&&(!accessions.length||accessions.length>25)){constructionProgress('Enter between 1 and 25 exact UniProt accessions.',true);return;}
  if(!demo&&new Set(accessions).size!==accessions.length){constructionProgress('Each accession must appear only once. Remove duplicate entries before building.',true);return;}
  const accessionPattern=/^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[1-9][0-9]*)?$/;
  const invalid=accessions.filter(accession=>!accessionPattern.test(accession));
  if(!demo&&invalid.length){constructionProgress('Use exact UniProt accessions, not gene symbols or aliases. Check: '+invalid.join(', '),true);return;}
  const relation=$('constructionRelations').value,request=demo?{mode:'demo'}:planned?{mode:'planned',plan_id:constructionPlanId,refresh:$('constructionRefresh').checked}:{mode:'live',accessions,focus_uniprot:$('constructionFocus').value,profile:$('constructionProfile').value,relations:relation==='both'?['interactions','shared_pathways']:[relation],refresh:$('constructionRefresh').checked};
  constructionBusy=true;busy(true);for(const input of $('constructionForm').elements)input.disabled=true;
  $('constructionProgress').replaceChildren();constructionProgress(demo?'Building the explicitly synthetic construction example…':'Resolving the declared proteins, retrieving bounded Pharos evidence, and saving the graph with a cited answer. This can take several minutes.');
  let publishedRun=null;
  try{
    const result=await api('/api/construct',request);
    publishedRun=result.run_id;
    runId=result.run_id;history.replaceState(null,'','?run='+encodeURIComponent(runId));showGraph(result.graph);setupConstructionPublication(result.graph,result.construction);
    const answered=!!(result.question&&result.question_id);
    if(answered){bindQuestionAnswer(result.question,result.question_id);$('questionStatus').textContent='Construction completed. This saved answer traces candidate paths to their source records.';navigateWork('answer');}
    else $('questionStatus').textContent='The graph is saved, but its focus protein did not resolve exactly. Choose a resolved protein to ask a new question.';
    constructionProgress(answered?'Graph and cited answer saved. Inspect source coverage, unresolved identities and candidate evidence before drawing conclusions.':'Graph and source trace saved. No initial answer was generated because the focus protein did not resolve exactly.');
    status(answered?'Construction completed. The graph, answer and source trace are saved together.':'Graph publication completed with an unresolved focus protein; no initial answer was generated.');loadSavedWork();loadRefreshRuns();
  }catch(error){constructionProgress(error.message,true);status((publishedRun?'Graph saved as '+publishedRun+', but the display could not finish: ':'Construction did not complete: ')+error.message,true);}
  finally{constructionBusy=false;for(const input of $('constructionForm').elements)input.disabled=false;busy(false);updateConstructionQuestion();$('constructionPlannedBuild').disabled=!constructionPlanId;}
}
async function planConstructionGraph(){
  if(constructionBusy||!$('constructionForm').reportValidity())return;
  clearConstructionPlan();
  const generation=constructionPlanGeneration;
  const question=$('constructionAgentQuestion').value.trim();
  if(!question){$('constructionPlanStatus').textContent='Enter the question you want the agent to plan.';return;}
  constructionBusy=true;busy(true);for(const input of $('constructionForm').elements)input.disabled=true;
  $('constructionPlanStatus').textContent='Planning one bounded request with the configured model. No source evidence is being retrieved yet…';
  try{
    const result=await api('/api/construction-plan',{question,accessions:constructionAccessions(),focus_uniprot:$('constructionFocus').value});
    if(generation!==constructionPlanGeneration)return;
    const trace=result.trace,request=trace.construction_request;
    $('constructionPlanStatus').textContent=(trace.status==='validated'?'Plan ready for inspection. ':trace.status==='abstained'?'The agent declined this request. ':'No executable plan was produced. ')+(trace.validated_plan?.reason||trace.error||'');
    const preview=$('constructionPlanPreview');
    if(request){constructionPlanId=result.plan_id;preview.append(table(['Choice','Planned retrieval'],[{cells:['Proteins',request.accessions.join(', ')]},{cells:['Focus',request.focus_uniprot]},{cells:['Evidence',request.profile]},{cells:['Answer connections',request.relations.join(', ')]}]));}
    const link=el('a','Download the planning record');link.href='/api/download/'+encodeURIComponent(result.plan_id);preview.append(link);
  }catch(error){if(generation===constructionPlanGeneration)$('constructionPlanStatus').textContent=error.message;}
  finally{constructionBusy=false;for(const input of $('constructionForm').elements)input.disabled=false;busy(false);$('constructionPlannedBuild').disabled=!constructionPlanId;}
}
async function exportSubmission(){
  if(!runId){$('submissionStatus').textContent='Open a saved workspace graph before exporting.';return;}
  const sourceRun=runId;
  $('submissionExport').disabled=true;$('submissionDownload').replaceChildren();$('submissionStatus').textContent='Verifying sources and preparing the graph with its complete decision ledger…';
  try{
    const result=await api('/api/submission-export',{run_id:sourceRun});
    if(runId!==sourceRun)return;
    $('submissionStatus').textContent='Export verified. Every input edge remains undecided and retained; no biological pruning was performed.';
    const link=el('a','Download graph, decisions and complete sources');link.href=result.download_url;$('submissionDownload').append(link);
  }catch(error){if(runId===sourceRun)$('submissionStatus').textContent=error.message;}
  finally{$('submissionExport').disabled=false;}
}
$('constructionPlanButton').addEventListener('click',planConstructionGraph);
$('constructionPlannedBuild').addEventListener('click',()=>constructGraph('planned'));
$('constructionAgentQuestion').addEventListener('input',clearConstructionPlan);
$('submissionExport').addEventListener('click',exportSubmission);
$('constructionForm').addEventListener('submit',event=>{event.preventDefault();constructGraph();});
$('constructionDemo').addEventListener('click',()=>constructGraph('demo'));
for(const id of ['constructionProteins','constructionFocus','constructionProfile','constructionRelations'])$(id).addEventListener(id==='constructionProteins'?'input':'change',()=>{clearConstructionPlan();updateConstructionQuestion();});
updateConstructionQuestion();
