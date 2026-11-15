// Guided graph questions. Scientific statements come from the Python query engine.
let questionAnswer=null, questionId=null, questionSelection=null, questionBusy=false;
function physicalRankingAvailable(){return graph?.data_kind==='live_pharos'&&graph.targets.length>0&&graph.targets.every(t=>/^UniProtKB:(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[1-9][0-9]*)?$/.test(t.id))&&!['shared_pathways','qualified_pathway_sources','native_physical'].includes($('questionRelations').value);}
function updateQuestionRankingControl(){
  const available=physicalRankingAvailable();
  $('questionRankingPhysical').disabled=!available;
  if(!available)$('questionRanking').value='alphabetical';
  $('questionRanking').disabled=questionBusy||!available;
  $('questionRankingNote').textContent=!available?(graph?.data_kind==='synthetic_demo'?'Physical priority is unavailable for synthetic demo data. It requires a real Pharos cohort with exact UniProt identifiers.':['shared_pathways','qualified_pathway_sources','native_physical'].includes($('questionRelations').value)?'Physical priority requires reported interaction paths. Choose interactions or interactions and shared pathways.':'Physical priority requires a real Pharos cohort with exact UniProt identifiers.'):$('questionRanking').value==='physical'?'Queries current STRING scores for up to 100 matching interaction partners before applying the result limit. Unscored and pathway-only matches remain after scored interactions. Source predicts physical proximity or co-complex association; it does not prove direct binding. Ordering supplements the source graph and leaves evidence paths and review states unchanged.':'Alphabetical order uses the saved graph without requesting additional STRING scores. Physical priority is available for up to 100 matching interaction partners.';
}
function questionOptions(){if($('questionRelations').value==='native_physical')return {protein:$('questionProtein').value,relations:['interactions'],template:'native_string_physical.v1',view:$('questionView').value,max_results:Number($('questionLimit').value),max_paths:Number($('questionPaths').value)};if($('questionRelations').value==='qualified_pathway_sources')return {protein:$('questionProtein').value,relations:['shared_pathways'],template:'qualified_pathway_source_context.v1',source_support:graph.qualified_view?.pathway_history&&$('nativePathwaySupport').checked?'native_supported':'all_source_annotations',view:$('questionView').value,max_results:Number($('questionLimit').value),max_paths:Number($('questionPaths').value)};const value=$('questionRelations').value,options={protein:$('questionProtein').value,relations:value==='both'?['interactions','shared_pathways']:[value],view:$('questionView').value,max_results:Number($('questionLimit').value),max_paths:Number($('questionPaths').value)};if(physicalRankingAvailable()&&$('questionRanking').value==='physical')options.ranking='physical';return options;}
function setupQuestion(){
  const previous=$('questionProtein').value;questionAnswer=null;questionId=null;questionSelection=null;
  $('questionProtein').replaceChildren();
  for(const t of graph.targets){const o=el('option',(t.symbol||t.id)+' | '+t.id);o.value=t.id;$('questionProtein').append(o);}
  const focus=graph.construction?.request?.focus_uniprot||graph.construction?.plan?.focus_uniprot||graph.scope?.focus_uniprot||graph.cohort?.focus_uniprot;
  const preferred=graph.targets.find(t=>t.id===previous)||graph.targets.find(t=>t.id==='UniProtKB:'+focus)||graph.targets.find(t=>t.symbol==='KRAS')||graph.targets[0];
  if(preferred)$('questionProtein').value=preferred.id;
  $('questionRelations').querySelector('option[value="qualified_pathway_sources"]')?.remove();
  if(graph.qualified_view){const option=el('option','Qualified WikiPathways source context');option.value='qualified_pathway_sources';$('questionRelations').append(option);$('questionRelations').value=option.value;$('questionView').value='candidates';}
  const nativePhysicalSelected=$('questionRelations').value==='native_physical';
  $('questionRelations').querySelector('option[value="native_physical"]')?.remove();
  if(graph.evidence_extension?.sources?.string_physical){const option=el('option','Native STRING physical associations');option.value='native_physical';$('questionRelations').append(option);}
  if(nativePhysicalSelected)$('questionRelations').value=graph.evidence_extension?.sources?.string_physical?'native_physical':'both';
  $('nativePathwaySupport').checked=!!graph.qualified_view?.pathway_history;
  $('questionRanking').value='alphabetical';
  $('questionOutput').classList.add('hidden');$('questionCitation').replaceChildren();
  $('questionRun').disabled=!runId||!graph.targets.length;
  $('questionStatus').textContent=runId?'Choose a scope and find evidence paths. Each accepted path must contain only accepted assertions.':'Open this snapshot in the running app to ask guided questions. This saved report supports source inspection.';
  updateQuestionPlan();
}
function updateQuestionPlan(){
  if(!graph)return;
  updateQuestionRankingControl();
  $('nativePathwaySupportControl').classList.toggle('hidden',!graph.qualified_view?.pathway_history||$('questionRelations').value!=='qualified_pathway_sources');
  if($('questionRelations').value==='native_physical'){
    const t=graph.targets.find(t=>t.id===$('questionProtein').value),name=t?.symbol||t?.id||'a selected protein';
    $('guidedQuestionDescription').textContent='Inspect saved native STRING physical associations from the separate complete human source file. Functional and assay evidence remain separate views.';
    $('questionText').textContent='Which retrieved proteins have native STRING 12.5 physical associations with '+name+'?';
    $('questionPlan').textContent='Query the saved physical source within '+graph.targets.length+' retrieved proteins, using unique reciprocal aliases and identical complete reference sequences. Physical proximity or co-complex support does not establish direct binding or disease relevance. Candidate records require review.';
    $('questionRankingNote').textContent='Saved physical source: alphabetical order, no live STRING request. Missing pairs and unresolved identities are unknown; the functional graph remains available through the other relationship choices.';
    $('questionScope').textContent=JSON.stringify(graph.evidence_extension.sources.string_physical,null,2);return;
  }
  if($('questionRelations').value==='qualified_pathway_sources'){
    const t=graph.targets.find(t=>t.id===$('questionProtein').value),name=t?.symbol||t?.id||'a selected protein';
    $('guidedQuestionDescription').textContent='Query the retained graph using exact cited WikiPathways revisions. Repeated source records are grouped; candidate review states stay visible.';
    $('questionText').textContent='Which retrieved proteins share exact-revision WikiPathways source context with '+name+'?';
    $('questionPlan').textContent='Read-only qualified graph: '+graph.qualified_view.retained_evidence_edges+' retained evidence edges. A → pathway model ← B describes shared source context. It does not establish a protein interaction or disease mechanism.';
    $('questionScope').textContent=JSON.stringify(graph.qualified_view,null,2);return;
  }
  const t=graph.targets.find(t=>t.id===$('questionProtein').value),name=t?.symbol||t?.id||'a selected protein';
  const option=$('questionRelations').value,rel=option==='both'?'reported interactions or shared pathways':option==='interactions'?'reported interactions':'shared pathways';
  const cohort=!graph.disease,scope=cohort?'in this protein cohort':'associated with '+graph.disease.name;
  $('guidedQuestionDescription').textContent=cohort?'Find proteins in the declared cohort connected to a selected protein through reported interactions or shared pathway annotations.':'Find disease-associated proteins connected to a selected protein through reported interactions or shared pathway annotations.';
  $('questionText').textContent='Which other proteins '+scope+' have '+rel+' with '+name+'?';
  $('questionPlan').textContent=(cohort?'Explicit protein cohort. ':'Exact disease: '+graph.disease.name+' ('+(graph.disease.mondoID||graph.disease_node_id)+'). ')+'Search '+graph.targets.length+' retrieved proteins around '+name+'. '+($('questionView').value==='accepted'?'Use accepted paths only.':'Explore accepted and candidate paths; unreviewed evidence stays labeled.')+' Return up to '+$('questionLimit').value+' proteins and '+$('questionPaths').value+' paths per protein.';
  $('questionScope').textContent=JSON.stringify({disease:graph.disease,cohort:graph.scope||graph.cohort||graph.question_scope?.cohort,protein:t?.id,cohort_targets:graph.targets.length,target_cohort_capped:graph.retrieval.truncated,limits:graph.question_scope?.limits,context_scope:graph.retrieval.context?.scope,filters:(cohort?'Declared cohort membership':'Exact-term disease associations')+' and structurally usable context. Rejected, quarantined and obsolete assertions are excluded.'},null,2);
}
function questionScopeChanged(){updateQuestionPlan();questionAnswer=null;questionId=null;questionSelection=null;$('questionOutput').classList.add('hidden');$('questionCitation').replaceChildren();$('questionStatus').textContent='Scope changed. Find evidence paths to refresh the answer.';if(runId)history.replaceState(null,'','?run='+encodeURIComponent(runId));updateWorkNavigation();}
function bindQuestionAnswer(answer,id){
  if(answer.source_run!==runId||answer.graph_basis_sha256!==graph.question_basis_sha256)throw new Error('This question result belongs to a different source run or review state. Run the question again.');
  questionAnswer=answer;questionId=id;questionSelection=answer.results[0]?.protein.id||null;
  $('questionProtein').value=answer.plan.protein.id;$('questionView').value=answer.plan.view;$('nativePathwaySupport').checked=answer.plan.source_support==='native_supported';
  $('questionRelations').value=answer.template==='native_string_physical.v1'?'native_physical':answer.template==='qualified_pathway_source_context.v1'?'qualified_pathway_sources':answer.plan.relations.length===2?'both':answer.plan.relations[0];
  $('questionLimit').value=answer.plan.max_results;$('questionPaths').value=answer.plan.max_paths_per_protein;
  $('questionRanking').value=answer.plan.ranking||'alphabetical';
  updateQuestionPlan();history.replaceState(null,'','?run='+encodeURIComponent(runId)+'&question='+encodeURIComponent(id));renderQuestion();
}
async function runQuestion(){
  if(questionBusy||!runId)return;
  if(!$('questionForm').reportValidity())return;
  questionBusy=true;for(const input of $('questionForm').elements)input.disabled=true;
  $('questionOutput').classList.add('hidden');questionAnswer=null;questionId=null;history.replaceState(null,'','?run='+encodeURIComponent(runId));
  updateWorkNavigation();$('questionStatus').textContent='Finding exact-scope evidence paths and assembling their citations...';
  try{const response=await api('/api/question',{run_id:runId,...questionOptions()});bindQuestionAnswer(response.answer,response.question_id);$('questionStatus').textContent='Question result saved with its source snapshot, review basis and citations.';navigateWork('answer');}
  catch(error){$('questionStatus').textContent=error.message;}
  finally{questionBusy=false;for(const input of $('questionForm').elements)input.disabled=false;$('questionRun').disabled=!runId;updateQuestionRankingControl();}
}
async function reopenQuestion(id){
  try{const response=await fetch('/api/question/'+encodeURIComponent(id)),result=await response.json();if(!response.ok)throw new Error(result.error||'Could not reopen question');if(result.answer.template==='qualified_assay_evidence.v1'){bindAssayAnswer(result.answer,result.question_id);return;}if(result.answer.template==='civic_variant_therapy.v1'){bindCivicAnswer(result.answer,result.question_id);$('civicStatus').textContent='Saved therapy question reopened against the same sources and review state.';return;}bindQuestionAnswer(result.answer,result.question_id);$('questionStatus').textContent='Saved question reopened against the same source and review state.';}
  catch(error){$('questionStatus').textContent=error.message;$('civicStatus').textContent=error.message;$('assayQuestionStatus').textContent=error.message;}
}
function renderQuestion(){
  const answer=questionAnswer;if(!answer)return;
  $('questionOutput').classList.remove('hidden');$('questionOverview').textContent=answer.overview;
  const sourceContext=answer.template==='qualified_pathway_source_context.v1';
  $('questionModeBadge').textContent=answer.template==='native_string_physical.v1'?'Native physical source · '+(answer.plan.view==='accepted'?'accepted annotations':'candidates require review'):sourceContext?'Qualified retained source context · original reviews preserved':answer.plan.view==='accepted'?'Accepted paths only':'Candidate exploration — review required';
  $('questionModeBadge').className='notice'+(answer.plan.view==='accepted'?'':' warn');
  $('questionExplore').classList.toggle('hidden',answer.plan.view!=='accepted'||answer.availability.inspectable_proteins===0||answer.returned_proteins>0);
  $('questionExplore').textContent='Explore '+answer.availability.inspectable_proteins+' proteins with inspectable paths';
  $('questionZip').href='/api/download/'+encodeURIComponent(questionId);$('questionSummary').replaceChildren();$('questionCitation').replaceChildren();
  const physical=answer.plan.ranking==='physical';
  if(physical){
    const ranking=answer.ranking||{};
    $('questionSummary').append(el('p','Physical association priority · STRING '+(ranking.source_release||'source release not supplied')+'. Native numeric scores order interaction matches; unscored and pathway-only matches follow. These scores predict physical proximity or co-complex association, not direct binding. Ordering supplements the saved graph; its evidence paths and review states are unchanged.','small'));
    const coverage=questionRankingCoverage(ranking);if(coverage)$('questionSummary').append(el('p',coverage,'small'));
  }
  for(const result of answer.results){
    const box=el('details',undefined,'evidence');box.open=result.protein.id===questionSelection;box.append(el('summary',(result.protein.sym||result.protein.name)+' | '+result.review_status.replaceAll('_',' ')+' | '+result.paths.length+' shown '+(result.paths.length===1?'path':'paths')));
    box.ontoggle=()=>{if(!box.open)return;questionSelection=result.protein.id;$('questionCitation').replaceChildren();for(const other of $('questionSummary').children)if(other!==box&&other.tagName==='DETAILS')other.open=false;renderQuestionGraph();};
    if(physical)box.append(el('p',questionPhysicalPriorityText(result,answer.ranking||{}),'small'));
    for(const s of answer.summary.filter(s=>s.protein_id===result.protein.id)){const p=el('p',s.text+' ');for(const cid of s.citation_ids){const b=el('button','['+cid+']','citation-link');b.type='button';b.setAttribute('aria-label','Inspect evidence '+cid);b.onclick=()=>inspectQuestionCitation(cid);p.append(b);}box.append(p);}
    if(result.omitted_paths)box.append(el('p',result.omitted_paths+' additional eligible paths omitted by the per-protein limit.','small'));
    $('questionSummary').append(box);
  }
  if(answer.omitted_proteins)$('questionSummary').append(el('p',answer.omitted_proteins+' additional matching proteins omitted by the result limit. '+(physical?'Ordering uses native STRING physical scores, with unscored matches after scored interactions.':'Ordering is alphabetical.'),'small'));
  $('questionGaps').replaceChildren();for(const text of answer.limitations)$('questionGaps').append(el('li',text));
  const trace={snapshot_sha256:answer.snapshot_sha256,graph_basis_sha256:answer.graph_basis_sha256,review_events_sha256:answer.review_events_sha256,answer_sha256:answer.answer_sha256,availability:answer.availability,selected_coverage:answer.plan.selected_coverage,excluded_assertions:answer.excluded_assertions};if(physical)trace.ranking=answer.ranking;
  $('questionTrace').textContent=JSON.stringify(trace,null,2);
  $('questionGraphSection').classList.toggle('hidden',!answer.results.length);renderQuestionGraph();updateWorkNavigation();
}
function questionRankingCoverage(ranking){
  const parts=[];
  if(ranking.retrieved_at)parts.push('STRING retrieval: '+ranking.retrieved_at);
  if(typeof ranking.matching_proteins==='number')parts.push(ranking.matching_proteins+' matching proteins');
  if(typeof ranking.numeric_scored==='number')parts.push(ranking.numeric_scored+' with native numeric physical scores');
  if(typeof ranking.unranked_proteins==='number')parts.push(ranking.unranked_proteins+' unranked');
  return parts.join(' · ');
}
function questionPhysicalPriorityText(result,ranking){
  const priority=result.physical_priority||{},release=priority.source_release||ranking.source_release||'release not supplied';
  if(priority.has_interaction===false||priority.state==='not_interaction_path')return 'Pathway-only match — not physically ranked. Shared pathway annotation does not establish physical association.';
  if(priority.state==='numeric'&&typeof priority.physical_score==='number')return 'STRING '+release+' native physical score: '+priority.physical_score.toFixed(3)+(typeof priority.functional_score==='number'?' · functional score: '+priority.functional_score.toFixed(3):'')+'.';
  const states={unmapped:'Protein identifier not mapped by STRING',ambiguous:'Ambiguous STRING identifier mapping',no_functional_row:'No functional-network row returned',no_returned_functional_row:'No functional-network row returned',physical_absent:'Physical score absent or below the requested source profile',physical_absent_or_below_profile:'Physical score absent or below the requested source profile',physical_not_returned_under_profile:'Physical score absent or below the requested source profile',collapsed:'Protein pair maps to one STRING representative',collapsed_representative:'Protein pair maps to one STRING representative'};
  return 'STRING '+release+' physical score unavailable: '+(states[priority.state]||(priority.state||'not supplied').replaceAll('_',' '))+'. Retained after scored matches; this is not evidence of no interaction.';
}
function renderQuestionGraph(){
  const answer=questionAnswer,result=answer?.results.find(r=>r.protein.id===questionSelection);if(!result)return;
  const nodes=new Map(answer.nodes.map(n=>[n.id,n])),did=answer.plan.disease?.id,anchor=answer.plan.protein.id;
  const compact=answer.template==='qualified_pathway_source_context.v1';
  const pathwayIds=[...new Set(result.paths.filter(p=>p.kind==='shared_pathway').flatMap(p=>p.node_ids.filter(id=>nodes.get(id)?.category==='biolink:Pathway')))];
  const h=Math.max(270,pathwayIds.length*(compact?78:70)+80),pos={[result.protein.id]:{x:compact?412:did?350:150,y:h/2},[anchor]:{x:compact?48:850,y:h/2}};
  if(did)pos[did]={x:105,y:h/2};
  pathwayIds.forEach((id,i)=>pos[id]={x:compact?230:did?610:500,y:55+i*(h-110)/Math.max(1,pathwayIds.length-1)});
  const svg=svgEl('svg',{viewBox:'0 0 '+(compact?460:1000)+' '+h,role:'img','aria-label':'Evidence paths for '+(result.protein.sym||result.protein.id)});
  if(compact){
    svg.style.minWidth='0';svg.style.maxWidth='760px';svg.style.margin='auto';const defs=svgEl('defs');
    for(const [state,color] of [['candidate','#b58236'],['accepted','#147c83']]){const marker=svgEl('marker',{id:'sourceModelArrow'+state,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'});marker.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:color}));defs.append(marker);}svg.append(defs);
  }
  function halfSize(id){return compact?(nodes.get(id)?.category==='biolink:Pathway'?{x:105,y:25}:{x:38,y:20}):{x:92,y:20};}
  function boundary(a,b,id){const dx=b.x-a.x,dy=b.y-a.y,d=halfSize(id),ratio=1/Math.max(Math.abs(dx)/d.x,Math.abs(dy)/d.y);return{x:a.x+dx*ratio,y:a.y+dy*ratio};}
  const required=new Set(result.paths.flatMap(p=>p.assertion_ids));
  for(const citation of answer.citations.filter(c=>required.has(c.assertion_id))){
    const a=pos[citation.subject],b=pos[citation.object];if(!a||!b)continue;
    const from=compact?boundary(a,b,citation.subject):a,to=compact?boundary(b,a,citation.object):b;
    const accepted=citation.review_state==='accepted',line=svgEl('line',{x1:from.x,y1:from.y,x2:to.x,y2:to.y,stroke:accepted?'#147c83':'#b58236','stroke-width':compact?2:3,'stroke-dasharray':accepted?'':'7 4',tabindex:0,role:'button','aria-label':'Inspect evidence '+citation.id});
    if(compact)line.setAttribute('marker-end','url(#sourceModelArrow'+(accepted?'accepted':'candidate')+')');
    const title=svgEl('title');title.textContent='['+citation.id+'] '+relationLabel(citation.predicate)+' | '+citation.review_state;line.append(title);line.style.cursor='pointer';line.onclick=()=>inspectQuestionCitation(citation.id);line.onkeydown=e=>{if(e.key==='Enter')inspectQuestionCitation(citation.id);};svg.append(line);
  }
  for(const [id,p] of Object.entries(pos)){
    const n=nodes.get(id);if(!n)continue;const label=n.sym||n.name||id,g=svgEl('g'),size=halfSize(id),pathway=n.category==='biolink:Pathway';
    g.append(svgEl('rect',{x:p.x-size.x,y:p.y-size.y,width:2*size.x,height:2*size.y,rx:7,fill:id===did?'#fff0d4':pathway?'#eeedf7':'#e2f2f1',stroke:'#76909d'}));
    const text=svgEl('text',{x:p.x,y:p.y+(compact&&pathway?-3:4),'text-anchor':'middle','font-size':compact?13:12,fill:'#172b3a'});
    const modelId=compact&&pathway?answer.citations.find(c=>c.object===id)?.source_model_id:null;
    text.textContent=modelId||(label.length>(compact?9:24)?label.slice(0,compact?8:23)+'…':label);
    const title=svgEl('title');title.textContent=label+' | '+id;g.append(text,title);
    if(modelId){const name=svgEl('text',{x:p.x,y:p.y+13,'text-anchor':'middle','font-size':11,fill:'#304859'});name.textContent=label.length>29?label.slice(0,28)+'…':label;g.append(name);}svg.append(g);
  }
  $('questionGraphTitle').textContent=(compact?'Shared cited models: ':'Evidence graph: ')+(result.protein.sym||result.protein.id)+(compact?' / ':' ↔ ')+(answer.plan.protein.sym||anchor);
  $('questionGraph').replaceChildren(svg);$('questionGraphNote').textContent=compact?'Both proteins point to the cited pathway model. Dashed lines retain candidate review status. Shared context is not a new protein interaction. Select a line or summary reference to inspect its source.':'Solid teal: accepted assertion. Dashed amber: requires review. Lines show reported relationships, without implying causal direction. Select a line or a summary reference to inspect its evidence.';
}
function inspectQuestionCitation(id){
  const c=questionAnswer.citations.find(c=>c.id===id);if(!c)return;
  const box=$('questionCitation');box.replaceChildren(el('h3','['+id+'] Evidence passport'),el('p',nodeLabel(c.subject)+' → '+relationLabel(c.predicate)+' → '+nodeLabel(c.object)),el('p','Review state: '+c.review_state+' | '+c.source_record_count+' source '+(c.source_record_count===1?'row':'rows')+'; independent experiment count unknown.','small'));
  for(const note of c.normalization_notes)box.append(el('p',note,'notice'));
  const sourceIds=c.source_assertion_ids,originalId=sourceIds?.[0]||c.assertion_id;
  if(sourceIds)box.append(el('p',sourceIds.length+(sourceIds.length===1?' original assertion is grouped':' original assertions are grouped')+' in this reference. Open the first below; all identifiers and records are included in the JSON and evidence ZIP.','small'));
  const full=el('button',sourceIds?'Open first original assertion':'Open full assertion and review','secondary');full.onclick=()=>{
    $('inspectionDetails').open=true;$('evidenceView').value=c.review_state==='accepted'?'accepted':'inspection';$('assertionFamily').value=c.kind;$('assertionProtein').value=c.subject;tablePage=0;activeTab='assertions';document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('active',b.dataset.tab==='assertions'));render();inspectAssertion(originalId);const back=el('button','Back to guided question','secondary');back.onclick=()=>{const target=$('guidedQuestion');if(typeof revealWorkspaceTarget==='function')revealWorkspaceTarget(target);target.scrollIntoView({block:'start'});};$('inspector').prepend(back);$('inspector').scrollIntoView({block:'start'});
  };box.append(full);
  if(c.historical_source)appendPathwayNativePassport(box,c);
  if(sourceIds){const raw=el('details');raw.append(el('summary','Original source records ('+c.evidence_records.length+')'));for(const e of c.evidence_records)raw.append(evidenceCard(e));box.append(raw);}else for(const e of c.evidence_records)box.append(evidenceCard(e));
  const details=el('details');details.append(el('summary','Assertion, snapshot and review trace'),el('pre',JSON.stringify({assertion_id:c.assertion_id,revision:c.revision,snapshot_sha256:questionAnswer.snapshot_sha256,graph_basis_sha256:questionAnswer.graph_basis_sha256,qualifiers:c.qualifiers},null,2)));box.append(details);box.scrollIntoView({block:'nearest'});
}
function appendPathwayNativePassport(box,citation){
  const native=citation.historical_source,assessment=native.assessment||{},model=native.model;
  box.append(el('h4','Archived native source check'),el('p',model?'Exact cited model '+citation.source_model_id+' · '+(native.status==='explicitly_encoded_protein_xref'?'literal protein reference':native.status==='compatible_gene_level_xref'?'compatible gene-level reference':'native support unresolved'):'Native support unresolved; no exact archived source model is available for this connection.'));
  if(!model)return;
  box.append(el('p','Native model licence: '+(model.native_license_literal||'not supplied')+'. Publisher archive licence: '+(native.selected_archive_proof?.archive_license?.id||native.selected_archive_proof?.archive_license||'not supplied')+'.','small'));
  box.append(el('p','Gene-level matches use the pinned registry relationship. They do not establish exact historical protein forms. Native XML and archive membership were replayed; the producer’s XSD check was not reexecuted by this app.','small'));
  const archive=pruningExternalLink('Open the publisher archive',native.selected_archive_proof?.source_url);if(archive)box.append(archive);
  const payload=questionAnswer.historical_models?.[citation.source_model_id];
  if(payload){const button=el('button','Download cited native GPML','secondary');button.type='button';button.onclick=()=>{const bytes=Uint8Array.from(atob(payload.gpml_base64),c=>c.charCodeAt(0)),url=URL.createObjectURL(new Blob([bytes],{type:'application/xml'})),a=el('a');a.href=url;a.download=citation.source_model_id+'.gpml';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};box.append(button);}
  const matches=[...(assessment.exact_protein_matches||[]),...(assessment.compatible_gene_matches||[])],nodes=new Set(matches.map(x=>x.node_xpath));
  for(const match of matches)box.append(el('p','Native node '+match.node_xpath+': '+(match.native_node.xrefs||[]).map(x=>(x.Database||'namespace unknown')+':'+(x.ID||'identifier missing')).join('; '),'small'));
  const records=model.publication_records||[],refs=el('details');refs.append(el('summary','Native model citations ('+records.length+')'),el('p','These are native model/reference records. Exact element attachments are labelled; no paper is assumed to support all pathway members or a physical interaction.','small'));
  for(const record of records){const fields={};for(const field of record.literal_fields||[])fields[field.tag.split('}').pop()]=field.text;const attrs=record.attributes||{},database=fields.DB||attrs.Database,identifier=fields.ID||attrs.ID,attached=(record.native_exact_reference_links||[]).some(x=>nodes.has(x.owner_xpath))||nodes.has(record.owner_xpath);const label=(fields.TITLE||((database||'Source')+':'+(identifier||'identifier not supplied')))+(attached?' · attached to matching native node':' · other/model reference');const p=el('p');if(database==='PubMed'&&/^\d+$/.test(identifier||'')){const a=pruningExternalLink(label,'https://pubmed.ncbi.nlm.nih.gov/'+identifier+'/');p.append(a);}else p.textContent=label;refs.append(p);}box.append(refs);
  const trace=el('details');trace.append(el('summary','Native model, bridge and archive proof'),el('pre',JSON.stringify(native,null,2)));box.append(trace);
}
function downloadQuestionJSON(){if(!questionAnswer)return;const u=URL.createObjectURL(new Blob([JSON.stringify(questionAnswer,null,2)],{type:'application/json'})),a=el('a');a.href=u;a.download='biograph_question.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
$('questionForm').addEventListener('submit',e=>{e.preventDefault();runQuestion();});
for(const id of ['questionProtein','questionRelations','questionView','questionLimit','questionPaths','questionRanking','nativePathwaySupport'])$(id).addEventListener('change',questionScopeChanged);
$('questionExplore').onclick=()=>{$('questionView').value='candidates';updateQuestionPlan();runQuestion();};
$('questionJson').onclick=downloadQuestionJSON;
