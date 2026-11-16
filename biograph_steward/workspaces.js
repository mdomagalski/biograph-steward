// One current reviewer story; the catalogue supplies its actual saved URLs.
let reviewerEntry=null,reviewerQualificationSummary=null;
function reviewerSavedURL(value){
  if(typeof value!=='string'||!value.startsWith('/?'))return null;
  try{const url=new URL(value,location.href);if(url.origin!==new URL(location.href).origin||url.pathname!=='/'||!(/^[A-Za-z0-9_-]{1,80}$/).test(url.searchParams.get('run')||'')||[...url.searchParams.keys()].some(key=>!['run','question','view','agent_job'].includes(key)))return null;
    const question=url.searchParams.get('question');if(question&&!(/^[A-Za-z0-9_-]{1,80}$/).test(question))return null;
    if(url.searchParams.has('agent_job')&&(url.searchParams.getAll('agent_job').length!==1||!/^source_agent_[A-Za-z0-9_-]{1,67}$/.test(url.searchParams.get('agent_job'))))return null;
    return url;
  }catch(_){return null;}
}
function reviewerAnswerReady(){return typeof questionAnswer!=='undefined'&&questionAnswer&&questionAnswer.source_run===runId&&Array.isArray(questionAnswer.citations);}
function reviewerSourceClaim(){if(!reviewerAnswerReady())return null;const citation=questionAnswer.citations[0];return citation?.source_assertion_ids?.[0]||citation?.assertion_id||null;}
function reviewerExampleLinks(target){
  if(!target)return;target.replaceChildren();
  if(graph?.snapshot_sha256&&reviewerEntry?.snapshot_sha256&&graph.snapshot_sha256!==reviewerEntry.snapshot_sha256)return;
  const primary=reviewerSavedURL(reviewerEntry?.example_url);
  for(const item of reviewerEntry?.guided_examples||[]){const url=reviewerSavedURL(item.url);if(!url||!primary||url.searchParams.get('run')===primary.searchParams.get('run')||url.searchParams.get('run')===runId)continue;
    const box=el('div',undefined,'reviewer-example'),link=el('a',item.label||'Review applied graph qualifications');link.href=url.pathname+url.search;box.append(link);
    if(typeof item.description==='string')box.append(el('p',item.description));target.append(box);
  }
}
function showQualificationSummary(summary){
  reviewerQualificationSummary=null;
  const qualified=graph?.qualified_view;
  if(summary&&qualified&&summary.baseline_records===qualified.baseline_evidence_edges&&summary.retained_records===qualified.retained_evidence_edges&&summary.excluded_records===summary.baseline_records-summary.retained_records&&Array.isArray(summary.reason_groups))reviewerQualificationSummary=summary;
  updateAppliedQualification();
}
function updateAppliedQualification(){
  const box=$('appliedQualificationSummary');if(!box)return;box.replaceChildren();
  const qualified=graph?.qualified_view;
  if(qualified){
    const baseline=qualified.baseline_evidence_edges,retained=qualified.retained_evidence_edges;
    if(Number.isInteger(baseline)&&Number.isInteger(retained)&&baseline>=retained){const line=el('p');line.append(el('strong',baseline.toLocaleString()+' → '+retained.toLocaleString()+' evidence records'));box.append(line,el('p',(baseline-retained).toLocaleString()+' records excluded by this saved qualification view. The original input and every keep, prune or abstain decision remain in the export.'));}
    if(graph.summary?.dispositions){const counts=graph.summary.dispositions;box.append(el('p',['keep','prune','abstain'].filter(key=>Number.isInteger(counts[key])).map(key=>({keep:'Kept',prune:'Excluded',abstain:'Unresolved and retained'}[key])+': '+counts[key].toLocaleString()).join(' · '),'small'));}
    if(reviewerQualificationSummary){const summary=reviewerQualificationSummary;for(const group of summary.reason_groups){if(group.decision!=='prune'||!Number.isInteger(group.records)||typeof group.reason!=='string')continue;const description=group.reason.includes('obsolete_term_in_current_ontology_view')?'retired GO identifiers in the pinned ontology view':group.reason.replaceAll('_',' ');box.append(el('p',group.records.toLocaleString()+' excluded: '+description));}if(typeof summary.interpretation==='string')box.append(el('p',summary.interpretation,'notice'));const proof=el('details');proof.append(el('summary','Recorded qualification rule and source binding'),el('pre',JSON.stringify(summary,null,2)));box.append(proof);}
    if(!reviewerQualificationSummary)box.append(el('p','This is the applied retained graph. Exclusions follow the recorded source qualification; a removed annotation is not automatically a biologically false relationship. Unresolved records stay retained.','notice'));
    const exportButton=el('button','Inspect retained graph and decision export','secondary');exportButton.type='button';exportButton.onclick=()=>showWorkspaceView('export',{scroll:true});box.append(exportButton);
  }else if(graph){box.append(el('p',graph.data_kind==='synthetic_demo'?'This is an invented interface demonstration. It provides no biological assessment.':'This workspace exposes source annotations and candidate additions. It is not the separate retained graph with applied qualification decisions.'));}
  else box.append(el('p','Open the real saved example to inspect its graph and the separate retained view.'));
  reviewerExampleLinks($('appliedQualificationLinks'));
}
function updateReviewerHome(){
  if(!$('reviewerHome'))return;
  const entryURL=reviewerSavedURL(reviewerEntry?.example_url),ready=reviewerAnswerReady(),synthetic=graph?.data_kind==='synthetic_demo';
  const primaryLoaded=entryURL&&runId===entryURL.searchParams.get('run');
  $('reviewerDataLabel').textContent=synthetic?'Invented offline records':graph?.data_kind==='live_pharos'?'Saved Pharos evidence':'Saved evidence, with its source trail';
  $('reviewerHomeTitle').textContent=synthetic?'You are viewing the invented offline demonstration.':reviewerEntry?.agent_job_id?'Guided source reader':reviewerEntry?.display_title||'A question. Its evidence. A transparent assessment.';
  const status=$('reviewerHomeStatus');status.className='notice'+(synthetic?' warn':'');
  status.textContent=synthetic?'These records are invented. Use the real-data example for source inspection and scientific assessment.':graph?.data_kind==='live_pharos'?'Real source records are open. Candidate annotations and local acceptance remain distinct.':entryURL?'Opening the real saved example and checking its sources…':'No real reviewer workspace is available in this installation. A code-only checkout needs its source packet separately.';
  if(reviewerEntry?.agent_entry_unavailable){status.textContent+=' '+reviewerEntry.note;status.className='notice warn';}
  $('reviewerAnswer').disabled=!ready&&!entryURL;
  $('reviewerAnswer').textContent=ready?'Read the cited answer':'Open the real-data example';
  if(primaryLoaded&&!ready)$('reviewerAnswer').disabled=true;
  $('reviewerSource').disabled=!reviewerSourceClaim();
  $('reviewerQuestionDescription').textContent=ready?questionAnswer.question:'Open the selected saved question and its evidence graph. Candidate records remain distinct from accepted evidence.';
  $('reviewerOffline').hidden=!!entryURL||savedReviewOnly()||graph?.data_kind==='live_pharos';
  reviewerExampleLinks($('reviewerExampleLinks'));
  $('reviewerGuidedExamples').hidden=!$('reviewerExampleLinks').children.length;
  updateAppliedQualification();
}
function configureReviewerEntry(data){
  const entry=data.reviewer_entry;
  reviewerEntry=entry?.data_kind==='live_pharos'&&reviewerSavedURL(entry.example_url)?entry:null;
  if(!reviewerEntry&&data.example_url){const url=reviewerSavedURL(data.example_url),run=url&&(data.runs||[]).find(row=>row.run_id===url.searchParams.get('run')&&row.data_kind==='live_pharos');if(run)reviewerEntry={example_url:data.example_url,data_kind:'live_pharos',display_title:'Explore real Pharos evidence',guided_examples:[]};}
  updateReviewerHome();
  const params=new URLSearchParams(location.search);
  if(reviewerEntry&&!params.has('run')&&!params.has('pruning')&&!location.hash){const url=reviewerSavedURL(reviewerEntry.example_url);url.searchParams.set('view','data');location.replace(url.pathname+url.search);}
}
$('reviewerAnswer').onclick=()=>{if(reviewerAnswerReady()){showWorkspaceView('ask');navigateWork('question');}else{const url=reviewerSavedURL(reviewerEntry?.example_url);if(url)location.assign(url.pathname+url.search);}};
$('reviewerSource').onclick=()=>{const id=reviewerSourceClaim();if(!id)return;showWorkspaceView('evidence');$('sourceGuideSelection').value=id;loadSourceGuide(id);$('sourceGuide').scrollIntoView({block:'start'});};
$('reviewerAssess').onclick=()=>{showWorkspaceView('compare');$('appliedQualificationPanel').scrollIntoView({block:'start'});};
$('reviewerOpenOffline').onclick=()=>{if(savedReviewOnly())return;$('controls').open=true;document.querySelector('input[name="mode"][value="demo"]').checked=true;switchMode();$('controls').scrollIntoView({block:'start'});};

// Existing saved-run and saved-question routes remain responsible for validation.
let savedWork = [];
function chooseSavedRun(){
  const run=savedWork.find(r=>r.run_id===$('savedRun').value),select=$('savedQuestion');
  select.replaceChildren();
  const graphOption=el('option','Open graph and choose a question');graphOption.value=run?.url||'';select.append(graphOption);
  for(const q of run?.questions||[]){const option=el('option',q.question+' · '+q.view+' · '+q.question_id);option.value=q.url;select.append(option);}
  select.disabled=!run;$('openSavedWork').disabled=!run;
}
async function loadSavedWork(){
  $('savedWorkStatus').textContent='Loading saved graphs and questions…';
  try{
    const response=await fetch('/api/workspaces'),data=await response.json();
    if(!response.ok)throw new Error(data.error||'Could not load saved work.');
    savedWork=data.runs;configureReviewerEntry(data);const selected=$('savedRun').value||runId;
    $('savedRun').replaceChildren();
    for(const run of savedWork){const label=run.data_kind==='synthetic_demo'?'Synthetic demonstration':run.qualified_view?'Qualified retained graph':run.has_civic?'Pharos + CIViC':'Pharos';const option=el('option',label+' · '+run.run_id+' · '+run.questions.length+' saved answers');option.value=run.run_id;$('savedRun').append(option);}
    if(savedWork.some(r=>r.run_id===selected))$('savedRun').value=selected;
    $('savedRun').disabled=!savedWork.length;chooseSavedRun();
    $('savedExample').classList.toggle('hidden',!data.example_url);
    if(data.example_url)$('savedExample').href=data.example_url;
    $('savedWorkStatus').textContent=savedWork.length+' saved graphs. '+data.note+(data.withheld?' '+data.withheld+' incomplete or unsupported entries omitted.':'');
  }catch(error){$('savedWorkStatus').textContent=error.message;if($('reviewerHomeStatus'))$('reviewerHomeStatus').textContent='Saved evidence could not be opened: '+error.message;}
}
function updateWorkNavigation(){
  const mode=$('questionWorkflow').value, therapy=mode==='therapy',answer=mode==='assay'?assayAnswer:therapy?civicAnswer:questionAnswer;
  $('navGraph').disabled=!answer?.results.length;
  $('navAnswer').disabled=!answer;
  $('navSources').disabled=!answer?.citations.length;
  $('workNavigationHint').textContent=answer?'Your answer is ready. Open the graph, read the summary, or inspect a cited source.':'Choose a question and find evidence to open its graph, answer and sources.';
}
function navigateWork(step){
  const mode=$('questionWorkflow').value,therapy=mode==='therapy';let target;
  if(mode==='assay'){
    target=$(step==='question'?'assayQuestionControls':step==='graph'?'assayGraphTitle':step==='sources'?'assayAnswerRecords':'assayAnswerTitle');
    if(target){if(typeof revealWorkspaceTarget==='function')revealWorkspaceTarget(target);target.tabIndex=-1;target.focus({preventScroll:true});target.scrollIntoView({block:'start'});}
    return;
  }
  if(step==='question')target=$(therapy?'civicQuestion':'guidedQuestion');
  if(step==='graph')target=$(therapy?'civicGraphTitle':'questionGraphTitle');
  if(step==='answer')target=$(therapy?'civicAnswerTitle':'questionAnswerTitle');
  if(step==='sources'){
    const answer=therapy?civicAnswer:questionAnswer;
    const selected=answer?.results.find(r=>therapy?r.profile.id===civicSelection:r.protein.id===questionSelection);
    const citationId=selected?.paths.flatMap(p=>p.citation_ids)[0];
    if(therapy){if(!$('civicPassport').children.length&&citationId)inspectCivicCitation(citationId);target=$('civicPassport');}
    else{if(!$('questionCitation').children.length&&citationId)inspectQuestionCitation(citationId);target=$('questionCitation');}
  }
  if(target){
    if(typeof revealWorkspaceTarget==='function')revealWorkspaceTarget(target);
    for(const name of ['Question','Graph','Answer','Sources']){const button=$('nav'+name),active=name.toLowerCase()===step;button.classList.toggle('secondary',!active);if(active)button.setAttribute('aria-current','step');else button.removeAttribute('aria-current');}
    target.tabIndex=-1;target.focus({preventScroll:true});target.scrollIntoView({block:'start'});
  }
}
for(const step of ['Question','Graph','Answer','Sources'])$('nav'+step).onclick=()=>navigateWork(step.toLowerCase());
$('savedRun').onchange=chooseSavedRun;
$('reloadSavedWork').onclick=loadSavedWork;
$('savedWorkForm').onsubmit=event=>{event.preventDefault();const url=$('savedQuestion').value;if(url)location.assign(url);};
if(!JSON.parse($('embeddedData').textContent))loadSavedWork();
else $('savedWorkPanel').classList.add('hidden');
if(location.hash==='#refreshPanel')$('refreshPanel').open=true;
