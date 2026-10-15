// Guided graph questions. Scientific statements come from the Python query engine.
let questionAnswer=null, questionId=null, questionSelection=null, questionBusy=false;
function questionOptions(){const value=$('questionRelations').value;return {protein:$('questionProtein').value,relations:value==='both'?['interactions','shared_pathways']:[value],view:$('questionView').value,max_results:Number($('questionLimit').value),max_paths:Number($('questionPaths').value)};}
function setupQuestion(){
  const previous=$('questionProtein').value;questionAnswer=null;questionId=null;questionSelection=null;
  $('questionProtein').replaceChildren();
  for(const t of graph.targets){const o=el('option',(t.symbol||t.id)+' | '+t.id);o.value=t.id;$('questionProtein').append(o);}
  const preferred=graph.targets.find(t=>t.id===previous)||graph.targets.find(t=>t.symbol==='KRAS')||graph.targets[0];
  if(preferred)$('questionProtein').value=preferred.id;
  $('questionOutput').classList.add('hidden');$('questionCitation').replaceChildren();
  $('questionRun').disabled=!runId||!graph.targets.length;
  $('questionStatus').textContent=runId?'Choose a scope and find evidence paths. Each accepted path must contain only accepted assertions.':'Open this snapshot in the running app to ask guided questions. This saved report supports source inspection.';
  updateQuestionPlan();
}
function updateQuestionPlan(){
  if(!graph)return;
  const t=graph.targets.find(t=>t.id===$('questionProtein').value),name=t?.symbol||t?.id||'a selected protein';
  const option=$('questionRelations').value,rel=option==='both'?'reported interactions or shared pathways':option==='interactions'?'reported interactions':'shared pathways';
  $('questionText').textContent='Which other proteins associated with '+graph.disease.name+' have '+rel+' with '+name+'?';
  $('questionPlan').textContent='Exact disease: '+graph.disease.name+' ('+(graph.disease.mondoID||graph.disease_node_id)+'). Search '+graph.targets.length+' retrieved proteins around '+name+'. '+($('questionView').value==='accepted'?'Use accepted paths only.':'Explore accepted and candidate paths; unreviewed evidence stays labeled.')+' Return up to '+$('questionLimit').value+' proteins and '+$('questionPaths').value+' paths per protein.';
  $('questionScope').textContent=JSON.stringify({disease:graph.disease,protein:t?.id,cohort_targets:graph.targets.length,target_cohort_capped:graph.retrieval.truncated,limits:graph.question_scope?.limits,context_scope:graph.retrieval.context?.scope,filters:'Exact-term disease associations and structurally usable context. Rejected, quarantined and obsolete assertions are excluded.'},null,2);
}
function questionScopeChanged(){updateQuestionPlan();questionAnswer=null;questionId=null;$('questionOutput').classList.add('hidden');$('questionStatus').textContent='Scope changed. Find evidence paths to refresh the answer.';if(runId)history.replaceState(null,'','?run='+encodeURIComponent(runId));}
function bindQuestionAnswer(answer,id){
  if(answer.source_run!==runId||answer.graph_basis_sha256!==graph.question_basis_sha256)throw new Error('This question result belongs to a different source run or review state. Run the question again.');
  questionAnswer=answer;questionId=id;questionSelection=answer.results[0]?.protein.id||null;
  $('questionProtein').value=answer.plan.protein.id;$('questionView').value=answer.plan.view;
  $('questionRelations').value=answer.plan.relations.length===2?'both':answer.plan.relations[0];
  $('questionLimit').value=answer.plan.max_results;$('questionPaths').value=answer.plan.max_paths_per_protein;
  updateQuestionPlan();history.replaceState(null,'','?run='+encodeURIComponent(runId)+'&question='+encodeURIComponent(id));renderQuestion();
}
async function runQuestion(){
  if(questionBusy||!runId)return;
  if(!$('questionForm').reportValidity())return;
  questionBusy=true;for(const input of $('questionForm').elements)input.disabled=true;
  $('questionOutput').classList.add('hidden');questionAnswer=null;questionId=null;history.replaceState(null,'','?run='+encodeURIComponent(runId));
  $('questionStatus').textContent='Finding exact-scope evidence paths and assembling their citations...';
  try{const response=await api('/api/question',{run_id:runId,...questionOptions()});bindQuestionAnswer(response.answer,response.question_id);$('questionStatus').textContent='Question result saved with its source snapshot, review basis and citations.';}
  catch(error){$('questionStatus').textContent=error.message;}
  finally{questionBusy=false;for(const input of $('questionForm').elements)input.disabled=false;$('questionRun').disabled=!runId;}
}
async function reopenQuestion(id){
  try{const response=await fetch('/api/question/'+encodeURIComponent(id)),result=await response.json();if(!response.ok)throw new Error(result.error||'Could not reopen question');bindQuestionAnswer(result.answer,result.question_id);$('questionStatus').textContent='Saved question reopened against the same source and review state.';}
  catch(error){$('questionStatus').textContent=error.message;}
}
function renderQuestion(){
  const answer=questionAnswer;if(!answer)return;
  $('questionOutput').classList.remove('hidden');$('questionOverview').textContent=answer.overview;
  $('questionModeBadge').textContent=answer.plan.view==='accepted'?'Accepted paths only':'Candidate exploration — review required';
  $('questionModeBadge').className='notice'+(answer.plan.view==='accepted'?'':' warn');
  $('questionExplore').classList.toggle('hidden',answer.plan.view!=='accepted'||answer.availability.inspectable_proteins===0||answer.returned_proteins>0);
  $('questionExplore').textContent='Explore '+answer.availability.inspectable_proteins+' proteins with inspectable paths';
  $('questionZip').href='/api/download/'+encodeURIComponent(questionId);$('questionSummary').replaceChildren();$('questionCitation').replaceChildren();
  for(const result of answer.results){
    const box=el('details',undefined,'evidence');box.open=result.protein.id===questionSelection;box.append(el('summary',(result.protein.sym||result.protein.name)+' | '+result.review_status.replaceAll('_',' ')+' | '+result.paths.length+' shown '+(result.paths.length===1?'path':'paths')));
    box.ontoggle=()=>{if(!box.open)return;questionSelection=result.protein.id;$('questionCitation').replaceChildren();for(const other of $('questionSummary').children)if(other!==box&&other.tagName==='DETAILS')other.open=false;renderQuestionGraph();};
    for(const s of answer.summary.filter(s=>s.protein_id===result.protein.id)){const p=el('p',s.text+' ');for(const cid of s.citation_ids){const b=el('button','['+cid+']','citation-link');b.type='button';b.setAttribute('aria-label','Inspect evidence '+cid);b.onclick=()=>inspectQuestionCitation(cid);p.append(b);}box.append(p);}
    if(result.omitted_paths)box.append(el('p',result.omitted_paths+' additional eligible paths omitted by the per-protein limit.','small'));
    $('questionSummary').append(box);
  }
  if(answer.omitted_proteins)$('questionSummary').append(el('p',answer.omitted_proteins+' additional matching proteins omitted by the result limit. Ordering is alphabetical.','small'));
  $('questionGaps').replaceChildren();for(const text of answer.limitations)$('questionGaps').append(el('li',text));
  $('questionTrace').textContent=JSON.stringify({snapshot_sha256:answer.snapshot_sha256,graph_basis_sha256:answer.graph_basis_sha256,review_events_sha256:answer.review_events_sha256,answer_sha256:answer.answer_sha256,availability:answer.availability,selected_coverage:answer.plan.selected_coverage,excluded_assertions:answer.excluded_assertions},null,2);
  $('questionGraphSection').classList.toggle('hidden',!answer.results.length);renderQuestionGraph();
}
function renderQuestionGraph(){
  const answer=questionAnswer,result=answer?.results.find(r=>r.protein.id===questionSelection);if(!result)return;
  const nodes=new Map(answer.nodes.map(n=>[n.id,n])),did=answer.plan.disease.id,anchor=answer.plan.protein.id;
  const pathwayIds=[...new Set(result.paths.filter(p=>p.kind==='shared_pathway').map(p=>p.node_ids[2]))];
  const h=Math.max(270,pathwayIds.length*70+80),pos={[did]:{x:105,y:h/2},[result.protein.id]:{x:350,y:h/2},[anchor]:{x:865,y:h/2}};
  pathwayIds.forEach((id,i)=>pos[id]={x:610,y:55+i*(h-110)/Math.max(1,pathwayIds.length-1)});
  const svg=svgEl('svg',{viewBox:'0 0 1000 '+h,role:'img','aria-label':'Evidence paths for '+(result.protein.sym||result.protein.id)});
  const required=new Set(result.paths.flatMap(p=>p.assertion_ids));
  for(const citation of answer.citations.filter(c=>required.has(c.assertion_id))){
    const a=pos[citation.subject],b=pos[citation.object];if(!a||!b)continue;
    const accepted=citation.review_state==='accepted',line=svgEl('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:accepted?'#147c83':'#b58236','stroke-width':3,'stroke-dasharray':accepted?'':'7 4',tabindex:0,role:'button','aria-label':'Inspect evidence '+citation.id});
    const title=svgEl('title');title.textContent='['+citation.id+'] '+relationLabel(citation.predicate)+' | '+citation.review_state;line.append(title);line.style.cursor='pointer';line.onclick=()=>inspectQuestionCitation(citation.id);line.onkeydown=e=>{if(e.key==='Enter')inspectQuestionCitation(citation.id);};svg.append(line);
  }
  for(const [id,p] of Object.entries(pos)){const n=nodes.get(id),label=n.sym||n.name,g=svgEl('g');g.append(svgEl('rect',{x:p.x-92,y:p.y-20,width:184,height:40,rx:7,fill:id===did?'#fff0d4':n.category==='biolink:Pathway'?'#eeedf7':'#e2f2f1',stroke:'#76909d'}));const text=svgEl('text',{x:p.x,y:p.y+4,'text-anchor':'middle','font-size':12,fill:'#172b3a'});text.textContent=label.length>24?label.slice(0,23)+'…':label;const title=svgEl('title');title.textContent=label+' | '+id;g.append(text,title);svg.append(g);}
  $('questionGraphTitle').textContent='Evidence graph: '+(result.protein.sym||result.protein.id)+' ↔ '+(answer.plan.protein.sym||anchor);
  $('questionGraph').replaceChildren(svg);$('questionGraphNote').textContent='Solid teal: accepted assertion. Dashed amber: requires review. Lines show reported relationships, without implying causal direction. Select a line or a summary reference to inspect its evidence.';
}
function inspectQuestionCitation(id){
  const c=questionAnswer.citations.find(c=>c.id===id);if(!c)return;
  const box=$('questionCitation');box.replaceChildren(el('h3','['+id+'] Evidence passport'),el('p',nodeLabel(c.subject)+' → '+relationLabel(c.predicate)+' → '+nodeLabel(c.object)),el('p','Review state: '+c.review_state+' | '+c.source_record_count+' source '+(c.source_record_count===1?'row':'rows')+'; independent experiment count unknown.','small'));
  for(const note of c.normalization_notes)box.append(el('p',note,'notice'));
  const full=el('button','Open full assertion and review','secondary');full.onclick=()=>{
    $('inspectionDetails').open=true;$('evidenceView').value=c.review_state==='accepted'?'accepted':'inspection';$('assertionFamily').value=c.kind;$('assertionProtein').value=c.subject;tablePage=0;activeTab='assertions';document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('active',b.dataset.tab==='assertions'));render();inspectAssertion(c.assertion_id);const back=el('button','Back to guided question','secondary');back.onclick=()=>$('guidedQuestion').scrollIntoView({block:'start'});$('inspector').prepend(back);$('inspector').scrollIntoView({block:'start'});
  };box.append(full);
  for(const e of c.evidence_records)box.append(evidenceCard(e));
  const details=el('details');details.append(el('summary','Assertion, snapshot and review trace'),el('pre',JSON.stringify({assertion_id:c.assertion_id,revision:c.revision,snapshot_sha256:questionAnswer.snapshot_sha256,graph_basis_sha256:questionAnswer.graph_basis_sha256,qualifiers:c.qualifiers},null,2)));box.append(details);box.scrollIntoView({block:'nearest'});
}
function downloadQuestionJSON(){if(!questionAnswer)return;const u=URL.createObjectURL(new Blob([JSON.stringify(questionAnswer,null,2)],{type:'application/json'})),a=el('a');a.href=u;a.download='biograph_question.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
$('questionForm').addEventListener('submit',e=>{e.preventDefault();runQuestion();});
for(const id of ['questionProtein','questionRelations','questionView','questionLimit','questionPaths'])$(id).addEventListener('change',questionScopeChanged);
$('questionExplore').onclick=()=>{$('questionView').value='candidates';updateQuestionPlan();runQuestion();};
$('questionJson').onclick=downloadQuestionJSON;
