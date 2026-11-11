// Qualified assay records remain distinct from unqualified interaction paths.
let assayPage=0, assayEpoch=0, assayAnswer=null, assayQuestionId=null;
let assayReuseState={status:'unavailable'}, assayReuseViews={table:[],inspector:[],answer:[]};
function assayLabel(value){return String(value??'Not supplied').replaceAll('_',' ');}
function assayReuseLink(label,url){
  if(typeof url!=='string')return null;
  const reportPath=runId?'/api/assay-source-reuse/'+encodeURIComponent(runId)+'/report.html':null;
  let href;
  if(url===reportPath)href=url;
  else{
    try{const parsed=new URL(url);if(!['https:','http:'].includes(parsed.protocol)||parsed.username||parsed.password)return null;href=parsed.href;}
    catch{return null;}
  }
  const link=el('a',label);link.href=href;return link;
}
function assayReuseObservation(id){return assayReuseState.status==='available'?assayReuseState.data.observations.find(row=>row.observation_id===id):null;}
function assayReuseDownloadLink(){
  if(assayReuseState.status!=='available'||typeof runId!=='string'||!(/^[A-Za-z0-9_-]{1,80}$/).test(runId)||assayReuseState.data.source_run!==runId)return null;
  const link=el('a','Download run ZIP with audit and proof');link.href='/api/download/'+encodeURIComponent(runId);return link;
}
function assayReuseLabel(id){
  const row=assayReuseObservation(id);
  if(row?.current_string_status==='confirmed_user_assisted')return 'Shared record in current STRING 12.5 (user-assisted)';
  if(row)return 'Current STRING reuse unresolved';
  if(assayReuseState.status==='loading')return 'Checking saved source-reuse audit…';
  if(assayReuseState.status==='unverifiable')return 'Source-reuse audit could not be verified';
  return 'No verified source-reuse annotation';
}
function fillAssayReuseView(view){
  const {box,id,detail}=view,row=assayReuseObservation(id);
  if(!detail){box.textContent=assayReuseLabel(id);return;}
  box.replaceChildren(el('h4','Source reuse audit'),el('p',assayReuseLabel(id),'notice'));
  if(row){
    box.append(el('p',row.explanation),el('p','Source record identifiers: '+row.record_ids.join(' · '),'small'));
    box.append(el('p',row.current_string_status==='confirmed_user_assisted'?'The shared record was identified through a user-assisted source-link observation. This is not an independent replication.':'This record was not resolved in the observed STRING evidence view. That does not establish that it is absent from STRING.'));
  }
  box.append(el('p','Reuse in the original '+(graph?.db_version||'Pharos snapshot')+' import remains unresolved. This audit does not establish additional independent evidence or biological improvement. The assay context and local review are retained.','small'));
  if(assayReuseState.status==='unverifiable')box.append(el('p','The saved audit could not be verified for this workspace. No shared-record conclusion is displayed.','small'));
  const links=el('p');
  for(const citation of row?.evidence_links||[]){if(!citation||typeof citation.label!=='string')continue;const link=assayReuseLink(citation.label,citation.url);if(!link)continue;if(links.childNodes.length)links.append(document.createTextNode(' · '));links.append(link);}
  if(assayReuseState.status==='available'){
    const report=assayReuseLink('Verified source-reuse report',assayReuseState.data.report_url);
    if(report){if(links.childNodes.length)links.append(document.createTextNode(' · '));links.append(report);}
    const download=assayReuseDownloadLink();if(download){if(links.childNodes.length)links.append(document.createTextNode(' · '));links.append(download);}
    box.append(el('p','The audit supplement and copied proof are included in Download run ZIP. Saved-answer JSON and graph/decision exports retain their existing contents.','small'));
  }
  if(links.childNodes.length)box.append(links);
}
function assayReuseView(id,group,detail=false){
  const box=el(detail?'section':'span');box.dataset.sourceReuseObservation=id;
  const view={box,id,detail};assayReuseViews[group].push(view);fillAssayReuseView(view);return box;
}
function refreshAssayReuseViews(){for(const views of Object.values(assayReuseViews))for(const view of views)fillAssayReuseView(view);}
async function loadAssaySourceReuse(epoch,sourceRun,basis){
  const current=()=>epoch===assayEpoch&&runId===sourceRun&&graph?.question_basis_sha256===basis;
  if(!sourceRun){assayReuseState={status:'unavailable'};refreshAssayReuseViews();return;}
  try{
    const response=await fetch('/api/assay-source-reuse/'+encodeURIComponent(sourceRun)), data=await response.json();
    if(!current())return;
    if(!response.ok)throw new Error('Source-reuse audit could not be verified.');
    if(!['available','unavailable'].includes(data.status)||data.source_run!==sourceRun)throw new Error('Source-reuse workspace mismatch.');
    if(data.status==='available'){
      for(const [key,graphKey] of [['graph_basis_sha256','question_basis_sha256'],['snapshot_sha256','snapshot_sha256'],['assay_attachment_sha256','assay_attachment_sha256'],['assay_publication_sha256','assay_publication_sha256']]){
        if(typeof data[key]!=='string'||!data[key]||data[key]!==graph[graphKey])throw new Error('Source-reuse source basis mismatch.');
      }
      if(!Array.isArray(data.observations))throw new Error('Source-reuse observations are missing.');
      const ids=new Set();
      for(const row of data.observations){
        const source=(graph.assay_observations||[]).find(item=>item.id===row.observation_id);
        if(!source||ids.has(row.observation_id)||!Array.isArray(row.products)||JSON.stringify([...row.products].sort())!==JSON.stringify([...source.products].sort())||row.study!==source.study)throw new Error('Source-reuse observation mismatch.');
        if(row.provider!=='STRING'||row.provider_version!=='12.5'||row.historical_pharos_reuse!==null||!['confirmed_user_assisted','unknown_not_observed'].includes(row.current_string_status)||!Array.isArray(row.record_ids)||!row.record_ids.length||!row.record_ids.every(id=>typeof id==='string'&&id.length)||typeof row.explanation!=='string'||!Array.isArray(row.evidence_links))throw new Error('Source-reuse qualification mismatch.');
        if(row.observation_provenance!==(row.current_string_status==='confirmed_user_assisted'?'user_assisted_source_link':'not_observed'))throw new Error('Source-reuse observation provenance mismatch.');
        ids.add(row.observation_id);
      }
      const reportPath='/api/assay-source-reuse/'+encodeURIComponent(sourceRun)+'/report.html';
      if(data.report_url!==reportPath)throw new Error('Source-reuse report route mismatch.');
    }
    assayReuseState={status:data.status,data};
  }catch(error){if(!current())return;assayReuseState={status:'unverifiable'};}
  refreshAssayReuseViews();
}
async function setupAssay(){
  const epoch=++assayEpoch, attached=!!graph?.assay_evidence;
  const eligible=graph?.scope?.kind==='protein_cohort'&&graph?.data_kind==='live_pharos';
  const intact=graph?.assay_evidence?.source_kind==='intact_mitab27';
  assayAnswer=null;assayQuestionId=null;$('assayAnswerOutput').classList.add('hidden');
  assayReuseState={status:attached?'loading':'unavailable'};assayReuseViews={table:[],inspector:[],answer:[]};
  $('assayQuestionControls').classList.toggle('hidden',!intact);$('assayWorkflowOption').disabled=!intact;
  if(!intact&&$('questionWorkflow').value==='assay'){$('questionWorkflow').value='connections';switchQuestionWorkflow();}
  updateWorkNavigation();
  $('assayPanel').classList.toggle('hidden',!eligible&&!attached);
  $('assayAttachForm').classList.toggle('hidden',attached||!runId||!eligible);
  $('assayLoaded').classList.toggle('hidden',!attached);
  $('assayStatus').textContent='';assayPage=0;
  if(attached){
    const rows=graph.assay_observations||[], evaluable=rows.filter(r=>r.evaluable).length;
    $('assaySummary').textContent=rows.length+' observations within this exact cohort: '+evaluable+' evaluable and '+(rows.length-evaluable)+' excluded assays. Every selected outcome remains in the ledger.';
    if(intact){const source=graph.assay_evidence.source_accounting;$('assaySummary').textContent+=' The source publication preserves '+source.source_evidence_rows+' evidence rows, including '+source.excluded_evidence+' outside the declared human-protein task.';}
    $('assayReceipt').textContent=JSON.stringify(graph.assay_evidence,null,2);
    $('assayProtein').replaceChildren(el('option','All cohort proteins'));
    $('assayProtein').options[0].value='all';
    for(const target of graph.targets){const option=el('option',nodeLabel(target.id)+' · '+target.id);option.value=target.id;$('assayProtein').append(option);}
    $('assayOutcome').value='all';renderAssays();await loadAssaySourceReuse(epoch,runId,graph.question_basis_sha256);return;
  }
  if(!eligible||!runId)return;
  $('assayAttach').disabled=true;$('assayPublication').replaceChildren();
  try{
    const response=await fetch('/api/assay-publications'), data=await response.json();
    if(epoch!==assayEpoch)return;
    if(!response.ok)throw new Error(data.error||'Could not list saved assay publications.');
    for(const item of data.publications){const option=el('option',item.publication_id);option.value=item.publication_id;$('assayPublication').append(option);}
    $('assayAttach').disabled=!data.publications.length;
    $('assayStatus').textContent=data.publications.length?'Choose a saved publication. Attachment verifies its files and saves a new run.':'No saved assay publication is available in this workspace.';
  }catch(error){if(epoch===assayEpoch)$('assayStatus').textContent=error.message;}
}
function renderAssays(){
  assayReuseViews.table=[];assayReuseViews.inspector=[];
  const protein=$('assayProtein').value, outcome=$('assayOutcome').value;
  const rows=(graph?.assay_observations||[]).filter(r=>(protein==='all'||r.products.includes(protein))&&(outcome==='all'||(outcome==='excluded'?!r.evaluable:r.assay_status===outcome)));
  const size=25;assayPage=Math.min(assayPage,Math.max(0,Math.ceil(rows.length/size)-1));
  $('assayRows').replaceChildren(table(['Protein pair','Assay outcome','Evidence','Source reuse'],rows.slice(assayPage*size,(assayPage+1)*size).map(row=>({
    cells:[row.products.join(' ↔ '),assayLabel(row.assay_status),row.evaluable?'Qualified observation':'Excluded assay; no graph edge',assayReuseView(row.id,'table')],click:()=>inspectAssay(row)}))));
  $('assayPage').textContent=rows.length+' matching observations'+(rows.length?' · Page '+(assayPage+1)+' of '+Math.ceil(rows.length/size):'');
  $('assayPrev').disabled=assayPage===0;$('assayNext').disabled=(assayPage+1)*size>=rows.length;
  $('assayInspector').replaceChildren(el('p','Select an observation for its assay conditions and source records.','small'));
}
function assaySourceLink(label,path){
  const link=el('a',label);
  link.href=runId?'/api/assay-source/'+encodeURIComponent(runId)+'/'+path:'assay_source/'+path;
  return link;
}
function inspectAssay(row){
  assayReuseViews.inspector=[];
  if(row.source_kind==='intact_mitab27'){inspectIntactAssay(row);return;}
  const box=$('assayInspector'), assay=row.original.assay, constructs=row.constructs||{};
  box.replaceChildren(el('h3',row.products.join(' ↔ ')),el('p','Assay: '+assayLabel(row.assay)+' · Outcome: '+assayLabel(row.assay_status)));
  box.append(assayReuseView(row.id,'inspector',true));
  if(row.assay_status==='detected')box.append(el('p','The authors reported a positive result for this assay and construct combination. This does not establish an interaction in every biological setting.','notice'));
  box.append(el('h4','Constructs used in this assay'));
  box.append(el('p','Constructs are engineered DNA reagents used to make the test proteins. The authors’ ORF IDs identify the protein-coding clones used in those reagents.'));
  box.append(table(['Assay component','Experimental role','Author ORF / construct ID'],[
    {cells:['AD — activation domain',assayLabel(constructs.ad_experimental_role?.label),assayLabel(constructs.ad_orf_id??assay.ad_orf_id)]},
    {cells:['DB — DNA-binding domain',assayLabel(constructs.db_experimental_role?.label),assayLabel(constructs.db_orf_id??assay.db_orf_id)]}
  ]));
  box.append(el('p','In a two-hybrid assay, one test protein is fused to the activation domain (prey) and the other to the DNA-binding domain (bait). These are experimental roles; they do not establish which protein regulates the other.'));
  const mapping=el('p','To identify the protein for each construct, match its ID in the ');
  mapping.append(assaySourceLink('Construct crosswalk','source/freeze/source/orf_map.tsv'),document.createTextNode('. The displayed protein-pair order does not assign these roles.'));
  box.append(mapping,el('p','Assay host: '+assayLabel(row.assay_host_taxon)+'. The human label describes the tested proteins.','small'));
  const terms=el('details');terms.append(el('summary','Experimental-role definitions (PSI-MI)'));
  const definitions=el('a','PSI-MI: two hybrid (MI:0018), bait (MI:0496) and prey (MI:0498)');
  definitions.href='https://github.com/HUPO-PSI/psi-mi-CV/blob/master/psi-mi.owl';terms.append(definitions);box.append(terms);
  box.append(el('p','Pharos status in the original frozen comparison lookup: '+assayLabel(row.lookup.pharos_status)+'. This is not a new lookup against the current cohort.','small'));
  box.append(el('p','Nondetection is conditional on this assay. Failed assays do not establish a negative interaction.','notice'));
  const edge=graph.edges.find(e=>e.id===row.graph_edge_id), assertion=edge&&graph.assertions.find(a=>a.id===edge.assertion_id);
  if(assertion){
    const button=el('button','Inspect qualified assertion and review','secondary');
    button.onclick=()=>{$('inspectionDetails').open=true;$('evidenceView').value='inspection';inspectAssertion(assertion.id);$('inspector').scrollIntoView({block:'start'});};
    box.append(el('p','Local review: '+assayLabel(assertion.lifecycle_state), 'small'),button);
  }
  const links=el('p');
  for(const [label,path] of [['Publication receipt','publication.json'],['Author assay table','source/freeze/source/panel.tsv'],['Raw assay records','source/freeze/source/raw_human.tsv'],['Construct crosswalk','source/freeze/source/orf_map.tsv']]){
    if(links.childNodes.length)links.append(document.createTextNode(' · '));links.append(assaySourceLink(label,path));
  }
  box.append(links);
  for(const [label,data] of [['Assay context and source locators', {study:row.study,assay:row.assay,detection_method:row.detection_method,participant_taxon:row.participant_taxon,assay_host_taxon:row.assay_host_taxon,constructs:row.constructs,source_locators:row.source_locators}],['Original assessed record',row.original],['Original frozen Pharos lookup',row.lookup]]){
    const details=el('details');details.append(el('summary',label),el('pre',JSON.stringify(data,null,2)));box.append(details);
  }
}
$('assayAttachForm').addEventListener('submit',async event=>{
  event.preventDefault();const button=$('assayAttach');button.disabled=true;
  $('assayStatus').textContent='Verifying source records and attaching observations within this cohort…';
  try{
    const result=await api('/api/assay-attach',{run_id:runId,publication_id:$('assayPublication').value});
    runId=result.run_id;history.replaceState(null,'','?run='+encodeURIComponent(runId));showGraph(result.graph);
    if(typeof revealWorkspaceTarget==='function')revealWorkspaceTarget($('assayPanel'));
    $('assayPanel').scrollIntoView({block:'start'});status('Assay observations saved with the original Pharos cohort and complete source publication.');loadSavedWork();
  }catch(error){$('assayStatus').textContent=error.message;button.disabled=false;}
});
for(const id of ['assayProtein','assayOutcome'])$(id).addEventListener('change',()=>{assayPage=0;renderAssays();if(id==='assayProtein'){assayAnswer=null;assayQuestionId=null;$('assayAnswerOutput').classList.add('hidden');if(runId)history.replaceState(null,'','?run='+encodeURIComponent(runId));updateWorkNavigation();}});
$('assayPrev').onclick=()=>{assayPage--;renderAssays();};$('assayNext').onclick=()=>{assayPage++;renderAssays();};

function appendIntactGroups(box,groups){
  for(const group of groups||[]){
    const section=el('section');section.dataset.fieldGroup=group.group;
    section.append(el('h4',assayLabel(group.group)),el('p',group.text));
    section.append(table(['Source field','Reported value','MITAB columns'],group.fields.map(field=>({cells:[field.label,field.value,field.columns.join(', ')]}))));
    box.append(section);
  }
}
function appendIntactLinks(box,citations){
  const links=el('p');
  for(const citation of citations||[]){
    const parsed=new URL(citation.url);if(!['https:','http:'].includes(parsed.protocol)||parsed.username||parsed.password)continue;
    if(links.childNodes.length)links.append(document.createTextNode(' · '));
    const link=el('a',citation.label);link.href=parsed.href;links.append(link);
  }
  box.append(links);
}
function inspectIntactAssay(row){
  const box=$('assayInspector');box.replaceChildren(el('h3',row.products.join(' ↔ ')),el('p','Source-qualified IntAct / IMEx record · '+assayLabel(row.assay_status)));
  box.append(el('p','Source curation, experimental outcome and local review are separate. This record does not establish direct binding or disease relevance.','notice'));
  box.append(assayReuseView(row.id,'inspector',true));
  appendIntactLinks(box,row.display.citations);appendIntactGroups(box,row.display.field_groups);
  const links=el('p');links.append(assaySourceLink('Publication receipt','publication.json'),document.createTextNode(' · '),assaySourceLink('Original MITAB source',row.source_file),document.createTextNode(' · '),assaySourceLink('Complete source-row ledger','row_ledger.jsonl'));box.append(links);
  const edge=graph.edges.find(e=>e.id===row.graph_edge_id),assertion=edge&&graph.assertions.find(a=>a.id===edge.assertion_id);
  if(assertion){const button=el('button','Inspect source-bound assertion and local review','secondary');button.onclick=()=>{$('inspectionDetails').open=true;inspectAssertion(assertion.id);$('inspector').scrollIntoView({block:'start'});};box.append(el('p','Local review: '+assayLabel(assertion.lifecycle_state),'small'),button);}
}
function bindAssayAnswer(answer,id){
  if(answer.source_run!==runId||answer.graph_basis_sha256!==graph.question_basis_sha256||answer.assay_attachment_sha256!==graph.assay_attachment_sha256)throw new Error('This qualified answer belongs to a different source or review basis. Run the question again.');
  assayAnswer=answer;assayQuestionId=id;$('questionWorkflow').value='assay';switchQuestionWorkflow();
  $('assayProtein').value=answer.plan.protein||'all';$('assayOutcome').value='all';assayPage=0;renderAssays();history.replaceState(null,'','?run='+encodeURIComponent(runId)+'&question='+encodeURIComponent(id));
  $('assayAnswerOutput').classList.remove('hidden');$('assayAnswerOverview').textContent=answer.overview;
  $('assayAnswerDownload').href='/api/download/'+encodeURIComponent(id);
  $('assayAnswerGraph').replaceChildren(table(['Source participant A','Qualified evidence record','Source participant B'],answer.results.map(row=>({cells:[row.source_observation.products[0],row.citation_id+' · '+row.source_observation.assay_status,row.source_observation.products[1]],click:()=>document.getElementById('assay-'+row.citation_id).scrollIntoView({block:'start'})}))));
  const box=$('assayAnswerRecords');box.replaceChildren();
  assayReuseViews.answer=[];
  for(const row of answer.results){
    const section=el('section');section.id='assay-'+row.citation_id;section.dataset.observationId=row.observation_id;
    section.append(el('h3','['+row.citation_id+'] Source evidence record'),el('p','Local review: '+assayLabel(row.local_review_state)+' — separate from source curation and outcome.','notice'));
    section.append(assayReuseView(row.observation_id,'answer',true));appendIntactLinks(section,row.citations);appendIntactGroups(section,row.field_groups);box.append(section);
  }
  const limits=el('details');limits.append(el('summary','Scope, coverage and limitations'));for(const note of answer.limitations)limits.append(el('p',note));limits.append(el('pre',JSON.stringify(answer.source_attachment_summary,null,2)));box.append(limits);
  $('assayQuestionStatus').textContent='Saved qualified answer. All outcomes and local review states within the selected protein scope are retained.';updateWorkNavigation();
}
$('assayAsk').onclick=async()=>{
  if(!runId)return;const button=$('assayAsk');button.disabled=true;
  $('assayQuestionStatus').textContent='Assembling source-qualified evidence and its references…';
  try{const protein=$('assayProtein').value;const result=await api('/api/assay-question',{run_id:runId,protein:protein==='all'?null:protein});bindAssayAnswer(result.answer,result.question_id);navigateWork('answer');loadSavedWork();}
  catch(error){$('assayQuestionStatus').textContent=error.message;}finally{button.disabled=false;}
};
