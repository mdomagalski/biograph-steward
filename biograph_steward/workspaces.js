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
    savedWork=data.runs;const selected=$('savedRun').value||runId;
    $('savedRun').replaceChildren();
    for(const run of savedWork){const label=run.data_kind==='synthetic_demo'?'Synthetic demonstration':run.has_civic?'Pharos + CIViC':'Pharos';const option=el('option',label+' · '+run.run_id+' · '+run.questions.length+' saved answers');option.value=run.run_id;$('savedRun').append(option);}
    if(savedWork.some(r=>r.run_id===selected))$('savedRun').value=selected;
    $('savedRun').disabled=!savedWork.length;chooseSavedRun();
    $('savedExample').classList.toggle('hidden',!data.example_url);
    if(data.example_url)$('savedExample').href=data.example_url;
    $('savedWorkStatus').textContent=savedWork.length+' saved graphs. '+data.note+(data.withheld?' '+data.withheld+' incomplete or unsupported entries omitted.':'');
  }catch(error){$('savedWorkStatus').textContent=error.message;}
}
function updateWorkNavigation(){
  const therapy=$('questionWorkflow').value==='therapy',answer=therapy?civicAnswer:questionAnswer;
  $('navGraph').disabled=!answer?.results.length;
  $('navAnswer').disabled=!answer;
  $('navSources').disabled=!answer?.citations.length;
  $('workNavigationHint').textContent=answer?'Your answer is ready. Open the graph, read the summary, or inspect a cited source.':'Choose a question and find evidence to open its graph, answer and sources.';
}
function navigateWork(step){
  const therapy=$('questionWorkflow').value==='therapy';let target;
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
