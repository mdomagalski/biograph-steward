// Source-specific guided question. All scientific summary text comes from Python.
let civicAnswer=null,civicQuestionId=null,civicSelection=null,civicBusy=false;
function switchQuestionWorkflow(){
  const mode=$('questionWorkflow').value, therapy=mode==='therapy';
  $('guidedQuestion').classList.toggle('hidden',mode!=='connections');$('civicQuestion').classList.toggle('hidden',!therapy);
  updateWorkNavigation();
}
function setupCivic(){
  civicAnswer=null;civicQuestionId=null;civicSelection=null;
  $('civicOutput').classList.add('hidden');$('civicPassport').replaceChildren();
  const report=graph.civic;
  $('civicRetrievePanel').classList.toggle('hidden',!!report);$('civicLoaded').classList.toggle('hidden',!report);
  $('civicRetrieve').disabled=!runId||graph.data_kind==='synthetic_demo'||!graph.targets.some(t=>t.id==='UniProtKB:P01116');
  $('civicRun').disabled=!runId||!report;
  $('civicStatus').textContent=report?(runId?'Choose a complete profile and inspect locally reviewed or candidate evidence.':'Open this source in the running app to execute new questions.'):'Retrieve this fixed CIViC scope from a live Pharos cohort containing KRAS (UniProtKB:P01116).';
  if(report){
    $('civicInventory').textContent=report.retrieved_items+' distinct CIViC items retrieved; '+report.normalized_items+' usable source annotations; '+report.excluded_items.length+' excluded with reasons. CIViC source status ACCEPTED does not accept an assertion locally.';
    $('civicCoverage').textContent=JSON.stringify({coverage:report.coverage,mapping:report.mapping,excluded_items:report.excluded_items.map(r=>({evidence_id:r.evidence_id,reason:r.reason})),overlap:report.overlap,source_snapshot_sha256:report.source_snapshot_sha256,created_at:report.created_at},null,2);
    $('civicProfile').replaceChildren();const all=el('option','All retrieved KRAS-containing profiles');all.value='all';$('civicProfile').append(all);
    const ids=new Set(graph.assertions.filter(a=>a.kind==='variant_therapy_response').map(a=>a.subject));
    for(const id of [...ids].sort((a,b)=>nodeLabel(a).localeCompare(nodeLabel(b)))){const o=el('option',nodeLabel(id)+' | '+id);o.value=id;$('civicProfile').append(o);}
  }
  switchQuestionWorkflow();
}
async function retrieveCivic(){
  if(civicBusy||!runId||!$('civicCap').reportValidity())return;
  civicBusy=true;$('civicRetrieve').disabled=true;$('civicStatus').textContent='Retrieving exact-scope public CIViC evidence and preserving raw responses...';
  try{const result=await api('/api/civic',{run_id:runId,max_items:Number($('civicCap').value)});runId=result.run_id;history.replaceState(null,'','?run='+encodeURIComponent(runId));$('questionWorkflow').value='therapy';showGraph(result.graph);$('civicStatus').textContent='CIViC evidence saved in a new run. Original Pharos records and human review history are preserved.';}
  catch(error){$('civicStatus').textContent=error.message;}
  finally{civicBusy=false;$('civicRetrieve').disabled=!!graph.civic||!runId;}
}
function civicOptions(){return {profile:$('civicProfile').value,therapy:$('civicTherapy').value,view:$('civicView').value,max_results:Number($('civicLimit').value),max_paths:Number($('civicPaths').value)};}
function civicScopeChanged(){
  civicAnswer=null;civicQuestionId=null;$('civicOutput').classList.add('hidden');$('civicPassport').replaceChildren();
  $('civicStatus').textContent='Scope changed. Find therapy evidence to refresh the answer.';
  if(runId)history.replaceState(null,'','?run='+encodeURIComponent(runId));
  updateWorkNavigation();
}
async function runCivicQuestion(){
  if(civicBusy||!runId||!$('civicForm').reportValidity())return;
  const options=civicOptions();civicBusy=true;for(const input of $('civicForm').elements)input.disabled=true;
  civicScopeChanged();$('civicStatus').textContent='Finding qualified response assertions and assembling source citations...';
  try{const result=await api('/api/therapy-question',{run_id:runId,...options});bindCivicAnswer(result.answer,result.question_id);$('civicStatus').textContent='Therapy question saved with both source hashes and the current review basis.';navigateWork('answer');}
  catch(error){$('civicStatus').textContent=error.message;}
  finally{civicBusy=false;for(const input of $('civicForm').elements)input.disabled=false;$('civicRun').disabled=!runId;}
}
function bindCivicAnswer(answer,id){
  if(answer.source_run!==runId||answer.graph_basis_sha256!==graph.question_basis_sha256||answer.civic_snapshot_sha256!==graph.civic_snapshot_sha256)throw new Error('This therapy answer belongs to different sources or a different review state. Run the question again.');
  civicAnswer=answer;civicQuestionId=id;civicSelection=answer.results[0]?.profile.id||null;
  $('questionWorkflow').value='therapy';switchQuestionWorkflow();
  $('civicProfile').value=answer.plan.profile;$('civicTherapy').value=answer.plan.therapy;$('civicView').value=answer.plan.view;
  $('civicLimit').value=answer.plan.max_results;$('civicPaths').value=answer.plan.max_paths_per_profile;
  history.replaceState(null,'','?run='+encodeURIComponent(runId)+'&question='+encodeURIComponent(id));renderCivicQuestion();updateWorkNavigation();
}
function civicRelatedLiteratureLink(pmid){
  if(typeof pmid!=='string'||!(/^[1-9]\d*$/).test(pmid))return null;
  const link=el('a','Explore related literature · Linked Discoveries');
  link.href='https://linkeddiscoveries.ncbi.nlm.nih.gov/'+pmid+'/';link.target='_blank';link.rel='noopener noreferrer';
  link.title='Related publications are discovery leads, not independent confirmation.';
  return link;
}
function renderCivicContexts(citation){
  const box=el('div',undefined,'source-context'),context=citation.study_context;
  if(!context){box.append(el('p','This saved answer predates the source-context display. Run the question again to include it.','small'));return box;}
  box.append(el('p',context.summary,'small'));
  for(const note of context.therapy_notes)box.append(el('p',note,'small'));
  for(const group of context.overview.shared_references)box.append(el('p',group.reference+' is shared by '+group.evidence_ids.join(', ')+'; independent experiment count is unresolved.','small'));
  for(const record of context.records){
    const card=el('div',undefined,'source-record');
    card.append(el('strong',record.evidence_id+' | '+record.evidence_level+' — '+record.evidence_level_label),el('p',record.source_title));
    const details=el('details');details.append(el('summary','Source description and references — '+record.evidence_id),
      el('p','CIViC therapy list: '+record.therapy_label),el('p','Source description (as reported): '+record.description));
    const source=el('a','Open CIViC record');source.href=record.evidence_url;source.target='_blank';source.rel='noopener noreferrer';details.append(source);
    if(record.publication_url){const p=el('p'),link=el('a',record.source_reference);link.href=record.publication_url;link.target='_blank';link.rel='noopener noreferrer';p.append(link);
      const reference=typeof record.source_reference==='string'&&/^PMID:([1-9]\d*)$/.exec(record.source_reference),related=civicRelatedLiteratureLink(reference?reference[1]:null);
      if(related)p.append(el('span',' · '),related);details.append(p);}
    details.append(el('p','Record locator: '+record.record_locators.join('; '),'small'));card.append(details);box.append(card);
  }
  const note=el('p',context.context_note+' ','small'),levels=el('a','CIViC level definitions');levels.href=context.level_definitions_url;levels.target='_blank';levels.rel='noopener noreferrer';note.append(levels);box.append(note);
  return box;
}
function civicDisplayCoverageNotices(answer){
  if(answer.template!=='civic_variant_therapy.v1')return [];
  if(answer.display_coverage)return answer.display_coverage.notices;
  // Compatibility for historical saved answers: disclose their recorded caps
  // without modifying the answer, its selection, or its integrity hash.
  const results=answer.results||[],accepted=answer.plan?.view==='accepted',availability=answer.availability||{},
    shown=results.reduce((sum,r)=>sum+r.paths.length,0),eligible=availability[accepted?'accepted_assertions':'inspectable_assertions'],
    matching=answer.matching_profiles??(results.length+(answer.omitted_profiles||0)),omitted=answer.omitted_profiles??(matching-results.length),
    count=eligible===undefined?String(shown):shown+' of '+eligible,
    notices=['Display coverage: '+count+' eligible response assertions shown across '+results.length+' of '+matching+' matching molecular profiles in the '+(accepted?'locally accepted view.':'candidate/accepted view.'),
      omitted+' matching molecular profiles omitted by the profile display limit.'];
  for(const r of results)notices.push(r.profile.name+' ('+r.profile.id+'): '+r.paths.length+' of '+r.eligible_path_count+' eligible response assertions shown; '+r.omitted_paths+' omitted by the per-profile display limit.');
  const discordant=(answer.discordant_annotations||[]).length;
  if(discordant)notices.push('Differing annotations: '+discordant+' comparable profile/therapy groups in this question\'s selected view have differing response annotations or directions. These are not adjudicated contradictions; relevant assertions may be outside the display limits.');
  if(accepted&&!shown)notices.push('No locally accepted response assertions are shown. '+
    (availability.inspectable_assertions===undefined?'':availability.inspectable_assertions+' structurally inspectable candidate/accepted assertions match this question before the local-review filter. ')+
    'An empty accepted view does not establish absence of candidate evidence or biological absence.');
  notices.push('Coverage counts describe the retrieved source and selected question view; they do not establish complete CIViC or literature coverage.');
  return notices;
}

function renderCivicDisplayCoverage(answer){
  const box=el('div',undefined,'notice warn');box.setAttribute('aria-label','Evidence display coverage');
  box.append(el('strong','Evidence display coverage'));
  for(const text of civicDisplayCoverageNotices(answer))box.append(el('p',text));
  return box;
}

function renderCivicContextOverview(answer){
  const box=el('div',undefined,'notice'),context=answer.source_context_overview;if(!context)return box;
  box.append(el('p','Displayed sources: '+context.displayed_records+' CIViC items / '+context.cited_sources+' distinct cited sources. '+context.scope_note));
  for(const group of context.shared_references)box.append(el('p',group.reference+' is shared by '+group.evidence_ids.join(', ')+'.'));
  if(context.unresolved_source_records)box.append(el('p',context.unresolved_source_records+' displayed items have unresolved source references.'));
  if(!context.displayed_records)box.append(el('p','No source items are shown in this view. An empty result does not establish biological absence.'));
  return box;
}
function renderCivicQuestion(){
  const answer=civicAnswer;if(!answer)return;
  $('civicOutput').classList.remove('hidden');$('civicPassport').replaceChildren();
  $('civicMode').textContent=answer.plan.view==='accepted'?'Locally accepted evidence only':'Candidate exploration — local human review required';
  $('civicMode').className='notice'+(answer.plan.view==='accepted'?'':' warn');$('civicOverview').textContent=answer.overview;
  $('civicExplore').classList.toggle('hidden',answer.plan.view!=='accepted'||answer.returned_profiles>0||answer.availability.inspectable_assertions===0);
  $('civicExplore').textContent='Explore '+answer.availability.inspectable_assertions+' candidate/accepted assertions';
  $('civicZip').href='/api/download/'+encodeURIComponent(civicQuestionId);
  $('civicAlerts').classList.add('hidden'); // Shared coverage notice below includes scoped differing annotations.
  $('civicSummary').replaceChildren();
  $('civicSummary').append(renderCivicDisplayCoverage(answer));
  if(answer.source_context_overview)$('civicSummary').append(renderCivicContextOverview(answer));
  for(const result of answer.results){
    const box=el('details',undefined,'evidence');box.open=result.profile.id===civicSelection;
    box.append(el('summary',result.profile.name+' | '+result.paths.length+' response assertions shown'));
    box.ontoggle=()=>{if(!box.open)return;civicSelection=result.profile.id;for(const other of $('civicSummary').children)if(other!==box&&other.tagName==='DETAILS')other.open=false;$('civicPassport').replaceChildren();renderCivicGraph();};
    for(const s of answer.summary.filter(s=>s.profile_id===result.profile.id)){
      const p=el('p',s.text+' ');for(const cid of s.citation_ids){const b=el('button','['+cid+']','citation-link');b.type='button';b.setAttribute('aria-label','Inspect CIViC evidence '+cid);b.onclick=()=>inspectCivicCitation(cid);p.append(b);}box.append(p);
      for(const cid of s.citation_ids){const c=answer.citations.find(c=>c.id===cid);if(c)box.append(renderCivicContexts(c));}
    }
    $('civicSummary').append(box);
  }
  $('civicGaps').replaceChildren();for(const text of answer.limitations)$('civicGaps').append(el('li',text));
  $('civicTrace').textContent=JSON.stringify({plan:answer.plan,availability:answer.availability,discordant_annotations:answer.discordant_annotations,overlap:answer.overlap_summary,pharos_snapshot_sha256:answer.snapshot_sha256,civic_snapshot_sha256:answer.civic_snapshot_sha256,civic_created_at:answer.civic_created_at,graph_basis_sha256:answer.graph_basis_sha256,answer_sha256:answer.answer_sha256},null,2);
  renderCivicGraph();
}
function renderCivicGraph(){
  const answer=civicAnswer,result=answer?.results.find(r=>r.profile.id===civicSelection);$('civicGraph').replaceChildren();
  $('civicGraphTitle').textContent=result?'Qualified evidence graph: '+result.profile.name:'No locally accepted therapy assertions';if(!result)return;
  const required=new Set(result.paths.flatMap(p=>p.assertion_ids)),citations=answer.citations.filter(c=>required.has(c.assertion_id));
  const therapies=[...new Set(citations.map(c=>c.object))],nodes=new Map(answer.nodes.map(n=>[n.id,n])),h=Math.max(300,therapies.length*120+80,citations.length*40+100);
  const svg=svgEl('svg',{viewBox:'0 0 1000 '+h,role:'img','aria-label':'Complete molecular profile and qualified therapy response assertions'});
  const positions={[result.profile.id]:{x:200,y:h/2}};therapies.forEach((id,i)=>positions[id]={x:760,y:60+i*(h-120)/Math.max(1,therapies.length-1)});
  for(const c of citations){const a=positions[c.subject],b=positions[c.object],peers=citations.filter(x=>x.object===c.object),offset=(peers.indexOf(c)-(peers.length-1)/2)*70,mx=(a.x+b.x)/2,my=(a.y+b.y)/2,line=svgEl('path',{d:'M '+a.x+' '+a.y+' Q '+mx+' '+(my+offset)+' '+b.x+' '+b.y,fill:'none',stroke:c.review_state==='accepted'?'#147c83':'#b58236','stroke-width':3,'stroke-dasharray':c.review_state==='accepted'?'':'7 4',tabindex:0,role:'button','aria-label':'Inspect CIViC evidence '+c.id});
    const title=svgEl('title');title.textContent='['+c.id+'] '+c.qualifiers.evidence_direction+' '+c.qualifiers.response+' | '+nodeLabel(c.qualifiers.disease);line.append(title);line.onclick=()=>inspectCivicCitation(c.id);line.onkeydown=e=>{if(e.key==='Enter')inspectCivicCitation(c.id);};const label=svgEl('text',{x:mx,y:my+offset/2-7,'text-anchor':'middle','font-size':12,fill:'#172b3a',role:'button',tabindex:0,'aria-label':'Open response reference '+c.id});label.textContent='['+c.id+'] '+c.qualifiers.evidence_direction.replaceAll('_',' ')+' '+c.qualifiers.response;label.onclick=()=>inspectCivicCitation(c.id);label.onkeydown=e=>{if(e.key==='Enter')inspectCivicCitation(c.id);};svg.append(line,label);}
  for(const [id,p] of Object.entries(positions)){const n=nodes.get(id),g=svgEl('g');g.append(svgEl('rect',{x:p.x-155,y:p.y-26,width:310,height:52,rx:7,fill:id===result.profile.id?'#eeedf7':'#e2f2f1',stroke:'#76909d'}));const label=svgEl('text',{x:p.x,y:p.y+4,'text-anchor':'middle','font-size':13,fill:'#172b3a'});label.textContent=n.name.length>38?n.name.slice(0,37)+'…':n.name;const title=svgEl('title');title.textContent=n.name+' | '+id;g.append(label,title);svg.append(g);}
  $('civicGraph').append(svg);
}
function inspectCivicCitation(id){
  const c=civicAnswer.citations.find(c=>c.id===id);if(!c)return;const box=$('civicPassport');
  box.replaceChildren(el('h3','['+id+'] CIViC evidence passport'),el('p','Local review: '+c.review_state+' | '+c.evidence_records.length+' source items; independent experiment count unresolved.'));
  box.append(el('p','Conditions: '+Object.entries(c.qualifiers).filter(([,v])=>v!==null).map(([k,v])=>k+' = '+v).join('; '),'small'));
  const full=el('button','Open assertion and record a review','secondary');full.onclick=()=>{
    $('inspectionDetails').open=true;$('evidenceView').value='inspection';$('assertionFamily').value=c.kind;$('assertionProtein').value='all';tablePage=0;activeTab='assertions';document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('active',b.dataset.tab==='assertions'));render();inspectAssertion(c.assertion_id);
    const back=el('button','Back to therapy question','secondary');back.onclick=()=>{const target=$('civicQuestion');if(typeof revealWorkspaceTarget==='function')revealWorkspaceTarget(target);target.scrollIntoView({block:'start'});};$('inspector').prepend(back);$('inspector').scrollIntoView({block:'start'});
  };box.append(full,renderCivicContexts(c));
  for(const e of c.evidence_records){const r=e.evidence_record;box.append(el('h4','CIViC evidence '+r.id+' | source '+r.status+' | level '+r.evidenceLevel),el('p','Molecular profile: '+r.molecularProfile.name+' | expression: '+r.molecularProfile.rawName),el('p','Disease: '+r.disease.name+' | DOID:'+r.disease.doid),el('p','CIViC therapy list: '+r.therapies.map(t=>t.name).join(r.therapyInteractionType==='SUBSTITUTES'?' or ':r.therapyInteractionType==='SEQUENTIAL'?' / ':' + ')+' | '+(r.therapyInteractionType||'one drug listed; regimen not established')),
      el('p','Source citation: '+(r.source.citation||r.source.title||r.source.citationId)));
    const link=el('a','Open CIViC source record');link.href='https://civicdb.org/evidence/'+r.id;link.target='_blank';link.rel='noopener noreferrer';box.append(link);
    if(r.source.sourceType==='PUBMED'&&/^\d+$/.test(r.source.citationId)){const p=el('p'),a=el('a','Open PubMed '+r.source.citationId);a.href='https://pubmed.ncbi.nlm.nih.gov/'+r.source.citationId+'/';a.target='_blank';a.rel='noopener noreferrer';p.append(a);
      const related=civicRelatedLiteratureLink(r.source.citationId);if(related)p.append(el('span',' · '),related);box.append(p);}
    box.append(evidenceCard(e));
  }
  const overlap=el('details');overlap.append(el('summary','Pharos overlap and source trace'),el('pre',JSON.stringify({overlap:c.overlap,assertion_id:c.assertion_id,revision:c.revision,civic_snapshot_sha256:civicAnswer.civic_snapshot_sha256,pharos_snapshot_sha256:civicAnswer.snapshot_sha256},null,2)));box.append(overlap);box.scrollIntoView({block:'nearest'});
}
$('questionWorkflow').addEventListener('change',()=>{switchQuestionWorkflow();if($('questionWorkflow').value==='assay')navigateWork('question');});
$('civicRetrieve').onclick=retrieveCivic;
$('civicForm').addEventListener('submit',e=>{e.preventDefault();runCivicQuestion();});
for(const id of ['civicProfile','civicTherapy','civicView','civicLimit','civicPaths'])$(id).addEventListener('change',civicScopeChanged);
$('civicExplore').onclick=()=>{$('civicView').value='candidates';runCivicQuestion();};
