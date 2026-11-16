// Current source tools, separate from the preserved experimental planners.
// The server controls model/tool budgets, source verification and write policy.
let sourceAgentEpoch=0,sourceAgentBusy=false,sourceAgentConfig=null,sourceAgentJob=null;
const sourceAgentNames={native_physical:'Native physical interaction records',native_location:'Native GO location annotations',archived_pathway:'Verified archived pathway records'};
function sourceAgentGuardRecord(job){return (job.status||job.result?.status)==='scope_rejected'&&(job.model_calls??job.result?.trace?.model_calls)===0;}
function sourceAgentRecordLabel(job){return job.actual_model_run===true?'Recorded model run':sourceAgentGuardRecord(job)?'Controller guard · no model call':job.provider_kind==='injected_test_model'?'Development/test record':'Recorded attempt · model run not established';}
const sourceAgentScopeNotes={one_exact_mentioned_primary_protein_required:'Name one exact protein from this workspace.',explicit_anchor_differs_from_question:'The selected protein and the question name different targets.',explicit_review_view_conflict:'The question and the selected candidate/accepted view conflict.',requested_source_tool_unavailable:'This workspace does not contain the requested source tool.',no_current_source_tools_attached:'This workspace has none of the current source tools attached.',direct_binding_requirement:'The physical source reports associations; it cannot verify direct binding.',assay_requirement:'These tools cannot filter records by an assay or construct.',tissue_or_cell_condition:'These tools do not support the requested tissue or cell-line filter.',disease_specific_requirement:'Cohort membership does not make the native evidence disease-specific.',experimental_only_filter:'This source tool does not implement an experimental-only evidence filter.',multiple_source_tool_requirements:'Choose one source family for this bounded run.',multiple_source_execution:'This workflow executes one source query per run.',unresolved_protein_identifier:'The question includes a protein identifier outside this saved cohort.'};
function sourceAgentDisclosure(label,value){const box=el('details');box.append(el('summary',label),el('pre',JSON.stringify(value,null,2)));return box;}
function sourceAgentSteps(){
  // Reuse the main workspace's WAI-ARIA tab pattern for one readable step at a time.
  const box=el('div'),nav=el('div',undefined,'source-agent-steps');nav.setAttribute('role','tablist');nav.setAttribute('aria-label','Recorded agent workflow steps');
  const labels=['1. Question & plan','2. Evidence graph','3. Source inspection','4. Review proposals'],panels=[],buttons=[];
  function show(index,focus=false){for(let i=0;i<buttons.length;i++){buttons[i].setAttribute('aria-selected',String(i===index));buttons[i].tabIndex=i===index?0:-1;panels[i].hidden=i!==index;}if(focus){buttons[index].focus?.();nav.scrollIntoView?.({block:'nearest'});}}
  labels.forEach((label,index)=>{const button=el('button',label),panel=el('section');button.type='button';button.id='sourceAgentStepTab'+index;panel.id='sourceAgentStepPanel'+index;
    button.setAttribute('role','tab');button.setAttribute('aria-controls',panel.id);panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',button.id);panel.tabIndex=0;
    button.onclick=()=>show(index);button.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight')next=(index+1)%labels.length;if(event.key==='ArrowLeft')next=(index+labels.length-1)%labels.length;if(event.key==='Home')next=0;if(event.key==='End')next=labels.length-1;if(next!==undefined){event.preventDefault();show(next,true);}});
    buttons.push(button);panels.push(panel);nav.append(button);
  });
  box.append(nav,...panels);show(0);
  return {box,panels,finish(){panels.slice(0,-1).forEach((panel,index)=>{const next=el('button','Continue: '+labels[index+1].slice(3),'secondary');next.type='button';next.onclick=()=>show(index+1,true);panel.append(next);});}};
}
function sourceAgentToolCount(trace){return Array.isArray(trace?.tool_calls)?trace.tool_calls.length:(trace?.tool_calls||0);}
function sourceAgentMessage(text,error=false){$('sourceAgentStatus').textContent=text;$('sourceAgentStatus').className=error?'notice error':'small';}
function sourceAgentSetBusy(value){sourceAgentBusy=value;$('sourceAgentRun').disabled=value||!sourceAgentConfig?.enabled;$('sourceAgentReplay').disabled=value||!$('sourceAgentJobs').value;}
async function sourceAgentRead(path){const response=await fetch(path),value=await response.json();if(!response.ok)throw new Error(value.error||'Agent record could not be verified.');return value;}
async function setupSourceAgent(){
  const epoch=++sourceAgentEpoch,source=runId;sourceAgentConfig=null;sourceAgentJob=null;
  $('sourceAgentOutput').replaceChildren();$('sourceAgentRun').disabled=true;$('sourceAgentReplay').disabled=true;
  $('sourceAgentLive').hidden=savedReviewOnly();$('sourceAgentReplayMode').hidden=!savedReviewOnly();
  $('sourceAgentConfig').textContent='';$('sourceAgentJobs').replaceChildren(el('option','No recorded runs selected'));
  if(!source){sourceAgentMessage('Open a saved source workspace to use the agent workflow. The guided evidence reader remains available below.');return;}
  sourceAgentMessage('Checking local tool coverage and recorded agent runs. No model request is made.');
  try{
    const config=await sourceAgentRead('/api/source-agent/status?run_id='+encodeURIComponent(source));
    if(epoch!==sourceAgentEpoch||source!==runId)return;sourceAgentConfig=config;
    const available=(config.catalogue?.tools||[]).filter(tool=>tool.available!==false).map(tool=>sourceAgentNames[tool.name||tool.id]||tool.name||tool.id).filter(Boolean);
    $('sourceAgentTools').textContent=available.length?'Tools in this workspace: '+available.join(' · '):'No supported current-source tool is available in this workspace.';
    $('sourceAgentConfig').textContent=config.saved_data_only?'':config.configured?'Configured model: '+config.model+' ('+config.provider+'). Connectivity has not been checked; a request may still fail.':(config.reason||'No model has been configured.');
    const listing=await sourceAgentRead('/api/source-agent/jobs?run_id='+encodeURIComponent(source));
    if(epoch!==sourceAgentEpoch||source!==runId)return;
    const jobs=listing.jobs||[];$('sourceAgentJobs').replaceChildren(el('option','Choose a recorded agent run'));$('sourceAgentJobs').options[0].value='';
    for(const job of jobs){const option=el('option',sourceAgentRecordLabel(job)+' · '+job.status+' · '+job.question);option.value=job.job_id;$('sourceAgentJobs').append(option);}
    $('sourceAgentRecordNote').textContent=jobs.length?jobs.length+' verified recorded runs. Replaying uses saved results and source checks; it does not call a model.':'No verified agent run has been recorded for this workspace. The manual cited example below is not an agent run.';
    if(listing.unavailable_jobs?.length)$('sourceAgentRecordNote').textContent+=' '+listing.unavailable_jobs.length+' saved records could not be verified and are unavailable.';
    sourceAgentSetBusy(false);
    const requested=new URLSearchParams(location.search).get('agent_job');
    const requestedJob=requested&&/^source_agent_[A-Za-z0-9_-]{1,67}$/.test(requested)?jobs.find(job=>job.job_id===requested&&job.source_run===source&&job.actual_model_run===true):null;
    if(requestedJob){$('sourceAgentJobs').value=requested;await replaySourceAgent();}
    else if(requested)sourceAgentMessage('The linked record is not a verified actual-model run for this workspace. Choose a matching recorded run below; no other workspace or model was opened.',true);
    else sourceAgentMessage(config.saved_data_only?'Choose a verified recorded run to follow its question, plan, sources and proposed decisions. No agent is running now.':config.enabled?'Ask a source-evidence question. The model will plan one query, select sources to inspect, then propose review decisions.':'Live agent unavailable. Use a recorded run or the guided evidence reader below.');
  }catch(error){if(epoch===sourceAgentEpoch)sourceAgentMessage(error.message,true);}
}
function renderSourceAgentGraph(focus,anchor){
  const box=el('div',undefined,'graph-box'),nodes=focus?.nodes||[],edges=focus?.edges||[];
  if(!nodes.length){box.append(el('p','No evidence graph was returned for this scope.','small'));return box;}
  if(!nodes.some(node=>node.id===anchor)){box.append(el('p','The graph anchor is unavailable. Inspect the complete recorded source graph instead.','small'));return box;}
  // Reuse the guided source-path columns. Facing border ports keep each line
  // in the clear gap between columns, never behind an unrelated protein box.
  const others=nodes.filter(node=>node.id!==anchor),star=edges.every(edge=>(edge.subject||edge.source)===anchor||(edge.object||edge.target)===anchor);
  const contexts=star?[]:others.filter(node=>node.category!=='biolink:Protein'),partners=star?others:others.filter(node=>node.category==='biolink:Protein');
  const height=Math.max(270,Math.max(contexts.length,partners.length)*64+40),svg=svgEl('svg',{viewBox:'0 0 1000 '+height,role:'img','aria-label':'Source-bound evidence returned by the agent query'}),positions=new Map([[anchor,{x:170,y:height/2}]]);svg.style.minWidth='540px';
  for(const [rows,x] of [[contexts,500],[partners,830]])rows.forEach((node,index)=>positions.set(node.id,{x,y:(index+1)*height/(rows.length+1)}));
  const states=new Map();for(const assertion of focus.assertions||[])for(const eid of assertion.evidence_edge_ids||[])states.set(eid,assertion.lifecycle_state);
  let omitted=0;
  for(const edge of edges){const a=positions.get(edge.subject||edge.source),b=positions.get(edge.object||edge.target);if(!a||!b||a.x===b.x||(!star&&Math.abs(a.x-b.x)>330)){omitted++;continue;}const direction=a.x<b.x?1:-1,state=states.get(edge.id)||edge.review_state||edge.lifecycle_state,accepted=state==='accepted',line=svgEl('line',{x1:a.x+135*direction,y1:a.y,x2:b.x-135*direction,y2:b.y,stroke:accepted?'#147c83':'#b58236','stroke-width':2,'stroke-dasharray':accepted?'':'6 4'}),title=svgEl('title');title.textContent=[edge.predicate,edge.citation_id,state].filter(Boolean).join(' · ');line.append(title);svg.append(line);}
  for(const node of nodes){const p=positions.get(node.id),g=svgEl('g'),name=node.sym||node.symbol||node.name||node.id;g.append(svgEl('rect',{x:p.x-135,y:p.y-24,width:270,height:48,rx:8,fill:node.id===anchor?'#dcefed':'#edf3f7',stroke:'#76909d'}));const label=svgEl('text',{x:p.x,y:p.y+5,'text-anchor':'middle','font-size':13,fill:'#172b3a'});label.textContent=name.length>34?name.slice(0,33)+'…':name;const title=svgEl('title');title.textContent=name+' · '+node.id;g.append(label,title);svg.append(g);}
  box.append(svg);if(omitted)box.append(el('p',omitted+' source edges are not drawn in this column layout. Every edge remains in the downloadable recorded graph.','small'));return box;
}
function renderSourceAgentPassport(inspection,citation=null){
  const passports=Array.isArray(inspection.passports)?inspection.passports:[inspection.passport].filter(Boolean),box=el('details',undefined,'evidence');
  box.append(el('summary','Inspected citation ['+inspection.citation_id+'] · '+passports.length+' source '+(passports.length===1?'assertion':'assertions')));
  if(citation?.historical_source){
    const native=citation.historical_source,status=native.status,label=status==='explicitly_encoded_protein_xref'?'literal protein reference':status==='compatible_gene_level_xref'?'compatible gene-level reference':'native support unresolved';
    box.append(el('h4','Archived model '+citation.source_model_id+' · '+label));
    box.append(el('p',status==='compatible_gene_level_xref'?'This archived model supports a compatible gene-level reference. It does not establish an exact historical protein form.':'Read the recorded native model and identifier qualification for the precise source identity claim.'));
    box.append(el('p','Shared model context does not establish direct protein binding.','small'));
    const url=native.selected_archive_proof?.source_url;if(typeof url==='string'&&/^https:\/\//.test(url)){const link=el('p');link.append(guideLink({label:'Open the publisher archive',url}));box.append(link);}
    box.append(sourceAgentDisclosure('Archived model and identifier qualification',native));
  }
  if(inspection.complete_citation_inspection===true)box.append(el('p','Every source assertion in this selected citation was inspected.','small'));
  if(inspection.omitted_assertion_ids?.length)box.append(el('p',inspection.omitted_assertion_ids.length+' source assertions were not inspected; this citation inspection is incomplete.','notice warn'));
  for(const [index,passport] of passports.entries()){
    const item=passports.length===1?box:el('details',undefined,'evidence');
    if(passports.length>1)item.append(el('summary','Source assertion '+(index+1)+' of '+passports.length));
    item.append(el('p',passport.summary||'Recorded source inspection'),el('p',passport.review?.note||'Local source review state: '+(passport.review?.state||'not supplied'),'notice'));
    if(passport.qualifiers)item.append(fieldList(passport.qualifiers));
    for(const section of passport.sections||[]){const details=el('details');details.append(el('summary',section.title),el('p',section.text),fieldList(section.fields||{}));item.append(details);}
    for(const question of passport.questions||[])item.append(el('h4',question.question),el('p',question.answer));
    for(const link of passport.links||[]){if(typeof link.url==='string'&&/^https:\/\//.test(link.url)){const p=el('p');p.append(guideLink(link));item.append(p);}}
    item.append(sourceAgentDisclosure('Complete recorded source passport',passport));if(item!==box)box.append(item);
  }
  return box;
}
function renderSourceAgentJob(job,{replay=true}={}){
  if(job.source_run!==runId)throw new Error('This agent record belongs to a different saved workspace. Open its source workspace first.');
  sourceAgentJob=job;const result=job.result,output=$('sourceAgentOutput');output.replaceChildren();
  const actual=job.actual_model_run===true,kind=sourceAgentRecordLabel(job);
  if(savedReviewOnly())$('sourceAgentReplayMode').hidden=true;
  output.append(el('p',(replay?kind+' replay. No model or external retrieval runs; saved-source checks verify this record.':'New agent attempt recorded.')+' Status: '+result.status+'. Graph and review decisions were not changed.','notice'+(actual?'':' warn')));
  if(actual)output.append(el('p','Recorded model: '+(result.trace?.model_requested||'see verified trace')+' · '+(result.trace?.model_calls||0)+' model calls.','small'));
  if(!actual)output.append(el('p',sourceAgentGuardRecord(job)?'The application blocked this unsupported or unresolved request before inference. No model judgment was made.':'This record does not demonstrate a live model run. Its provider kind is '+job.provider_kind+'.','notice warn'));
  const steps=sourceAgentSteps();output.append(steps.box);
  const question=el('section',undefined,'path-step');question.append(el('h3','Research question'),el('p',result.question));steps.panels[0].append(question);
  const plan=el('section',undefined,'path-step');plan.append(el('h3','Validated tool plan'));
  if(result.plan?.action==='query'){plan.append(el('p',sourceAgentNames[result.plan.tool]||result.plan.tool),fieldList(result.plan.arguments||{}));}else plan.append(el('p',result.plan?.reason||'No executable plan was validated.'));
  for(const issue of result.scope?.unsupported_requirements||[])plan.append(el('p',sourceAgentScopeNotes[issue]||'Unsupported requirement: '+issue.replaceAll('_',' '),'notice warn'));
  if(result.plan?.reason)plan.append(el('p','Model explanation of its scope (not verified scientific evidence): '+result.plan.reason,'small'));steps.panels[0].append(plan);
  const evidence=el('section',undefined,'path-step');evidence.append(el('h3','Cited answer and evidence graph'));
  if(result.answer){evidence.append(el('p',result.answer.overview));
    evidence.append(renderSourceAgentGraph(result.focus_graph,result.plan?.arguments?.protein_id));
    const statements=result.answer.statements||[],statementNode=statement=>el('p',statement.text+' '+(statement.citation_ids||[]).map(id=>'['+id+']').join(' '));
    if(statements.length)evidence.append(statementNode(statements[0]));
    if(statements.length>1){const remaining=el('details');remaining.append(el('summary','Read '+(statements.length-1)+' more cited statements'));for(const statement of statements.slice(1))remaining.append(statementNode(statement));evidence.append(remaining);}
    evidence.append(el('p','Dashed lines retain candidate review status. The diagram shows source annotations, not proven direct binding or a causal mechanism.','small'));
    const reads=(result.inspections||[]).reduce((total,item)=>total+(Array.isArray(item.passports)?item.passports.length:item.passport?1:0),0);
    evidence.append(el('p',(result.answer.citations||[]).length+' returned citations; '+(result.inspections||[]).length+' selected for source inspection. '+reads+' source assertions inspected. All returned evidence remains in the saved result.','small'));
    const citations=el('details');citations.append(el('summary','All returned source citations'));
    for(const citation of result.answer.citations||[]){const card=el('div',undefined,'evidence');card.append(el('p','['+citation.id+'] '+(citation.subject||'')+' → '+(citation.object||'')+' · '+(citation.review_state||'review state not supplied')));const aid=(citation.source_assertion_ids||[])[0]||citation.assertion_id;if(aid){const open=el('button','Inspect this claim manually','secondary');open.type='button';open.onclick=()=>{showWorkspaceView('evidence');loadSourceGuide(aid);};card.append(open);}citations.append(card);}steps.panels[2].append(citations);
  }else evidence.append(el('p','No query evidence was returned. This does not establish biological absence.'));
  const sources=el('section',undefined,'path-step');sources.append(el('h3','Inspected source records'),el('p','Open a selected citation to inspect its recorded source, qualifications and references. All returned citations are also available here.'));
  for(const inspection of result.inspections||[])sources.append(renderSourceAgentPassport(inspection,(result.answer?.citations||[]).find(citation=>citation.id===inspection.citation_id)));
  if(!(result.inspections||[]).length)sources.append(el('p','No source inspection was performed for this recorded outcome.'));
  steps.panels[2].append(sources);
  if(result.answer?.limitations?.length){const limits=el('details');limits.append(el('summary','Interpretation and source limitations'));for(const limit of result.answer.limitations)limits.append(el('p',typeof limit==='string'?limit:JSON.stringify(limit),'small'));evidence.append(limits);}
  steps.panels[1].append(evidence);
  const proposals=el('section',undefined,'path-step');proposals.append(el('h3','Proposed review decisions'),el('p','These are proposals for a reviewer. No assertion was accepted, removed or changed. A model proposal is not independent scientific validation.','notice warn'));
  if(!(result.proposals||[]).length)proposals.append(el('p','No valid decision proposal was produced.'));
  for(const proposal of result.proposals||[]){const card=el('div',undefined,'evidence'),label=proposal.decision==='keep'?'Retain candidate context':proposal.decision==='abstain'?'Needs review':proposal.decision;card.append(el('strong','['+proposal.citation_id+'] '+label+' · proposal only'),el('p',proposal.reason));if(proposal.review_question)card.append(el('p','Review question: '+proposal.review_question,'small'));proposals.append(card);}
  steps.panels[3].append(proposals);steps.finish();
  if(result.error)output.append(el('p','Recorded issue: '+result.error,'notice warn'));
  const trace=el('details');trace.append(el('summary','Model/tool trace and source bindings'),el('p',(result.trace?.model_calls||0)+' model calls · '+sourceAgentToolCount(result.trace)+' tool calls'),el('pre',JSON.stringify({source_bindings:result.source_bindings,scope:result.scope,trace:result.trace,content_sha256:result.content_sha256},null,2)));output.append(trace);
  const download=el('a','Download this verified agent record');download.href='/api/source-agent/job/'+encodeURIComponent(job.job_id)+'/download';output.append(download);
  sourceAgentMessage((replay?'Recorded run opened':'Agent run saved')+'. '+(['completed','completed_empty'].includes(result.status)?'Review the cited evidence and proposed decisions.':'The recorded status is '+result.status+'; partial evidence does not make the whole agent run successful.'));
}
async function replaySourceAgent(){
  const identifier=$('sourceAgentJobs').value;if(!identifier||sourceAgentBusy)return;const epoch=sourceAgentEpoch,source=runId;sourceAgentSetBusy(true);sourceAgentMessage('Verifying the recorded result against its saved source. No model request is made.');
  try{const job=await sourceAgentRead('/api/source-agent/job/'+encodeURIComponent(identifier));if(epoch===sourceAgentEpoch&&source===runId)renderSourceAgentJob(job,{replay:true});}catch(error){if(epoch===sourceAgentEpoch)sourceAgentMessage(error.message,true);}finally{if(epoch===sourceAgentEpoch)sourceAgentSetBusy(false);}
}
async function runSourceAgent(event){
  event.preventDefault();if(sourceAgentBusy||savedReviewOnly()||!sourceAgentConfig?.enabled||!runId)return;
  const epoch=sourceAgentEpoch,source=runId;sourceAgentSetBusy(true);$('sourceAgentOutput').replaceChildren();sourceAgentMessage('The agent is planning one saved-source query, selecting up to three citations, and inspecting their source records. At most three model calls; no graph or review edits.');
  try{const job=await api('/api/source-agent/run',{run_id:source,question:$('sourceAgentQuestion').value,constraints:{view:$('sourceAgentView').value}});if(epoch===sourceAgentEpoch&&source===runId)renderSourceAgentJob(job,{replay:false});}catch(error){if(epoch===sourceAgentEpoch)sourceAgentMessage(error.message,true);}finally{if(epoch===sourceAgentEpoch)sourceAgentSetBusy(false);}
}
$('sourceAgentForm').addEventListener('submit',runSourceAgent);
$('sourceAgentJobs').addEventListener('change',()=>{$('sourceAgentReplay').disabled=sourceAgentBusy||!$('sourceAgentJobs').value;});
$('sourceAgentReplay').addEventListener('click',replaySourceAgent);
