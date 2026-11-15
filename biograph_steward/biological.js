// Deterministic saved-source question; no retrieval, model or graph writes.
let biologicalAnswer=null,biologicalOffset=0,biologicalEpoch=0,biologicalTimer=null;
function setupBiological(){
  biologicalEpoch++;biologicalAnswer=null;biologicalOffset=0;
  if(biologicalTimer){clearTimeout(biologicalTimer);biologicalTimer=null;}
  const summary=graph?.evidence_extension,source=summary?.sources||{};
  const enabled=['string','mapit','signor','bioplex'].some(kind=>!!source[kind]);
  $('biologicalPanel').classList.toggle('hidden',!enabled);
  $('biologicalAnswer').classList.add('hidden');$('biologicalSearch').value='';
  $('biologicalStatus').textContent='';$('biologicalRows').replaceChildren();
  setupRegulatory();
  setupBioplexContext();
  if(!enabled)return;
  const parts=[];
  if(source.string)parts.push('STRING '+(source.string.source_release||'12.5')+': '+source.string.additional_source_records+' versioned association records; '+source.string.new_workspace_pairs+' additional workspace pairs.');
  if(source.mapit)parts.push('MAP-IT: '+source.mapit.qualified_partner_observations+' qualified tissue observations; '+source.mapit.extension_nodes_added+' additional participant proteins.');
  if(source.signor)parts.push('SIGNOR: '+source.signor.qualified_regulatory_observations+' source-reported regulatory records, including '+source.signor.self_regulatory_records+' self-regulatory records.');
  if(source.bioplex)parts.push('BioPlex HCT116: '+source.bioplex.context_only_observations+' context records for '+source.bioplex.selected_unique_pairs+' existing pairs; no new graph edges.');
  $('biologicalSummary').textContent=parts.join(' ');
  for(const option of $('biologicalView').options)option.disabled=!source[option.value];
  $('biologicalViewControls').hidden=!source.mapit&&!source.signor&&!source.bioplex;
  $('biologicalView').value=source.mapit?'mapit':source.signor?'signor':source.bioplex?'bioplex':'mapit';
  switchBiologicalView();
  $('biologicalAsk').disabled=!source.mapit||!runId;
  if(!source.mapit)$('biologicalStatus').textContent='This saved run includes the STRING update. Open a run with qualified MAP-IT observations for the tissue question.';
  else if(!runId)$('biologicalStatus').textContent='Open this saved run in the workspace server to verify its tissue answer.';
}
function switchBiologicalView(){
  const source=graph?.evidence_extension?.sources||{},mode=$('biologicalView').value;
  $('biologicalTissueView').hidden=mode!=='mapit'||!source.mapit;
  $('regulatoryPanel').hidden=mode!=='signor'||!source.signor;
  $('bioplexPanel').hidden=mode!=='bioplex'||!source.bioplex;
}
function setupBioplexContext(){
  const box=$('bioplexRows');box.replaceChildren();
  const records=(graph?.extension_observations||[]).filter(row=>row.source_kind==='bioplex');
  for(const row of records){
    const card=el('article',undefined,'evidence');
    const bait=row.bait?.symbol||row.bait?.uniprot||'Unreported bait';
    const prey=row.prey?.symbol||row.prey?.uniprot||'Unreported prey';
    card.append(el('h4',bait+' and '+prey));
    card.append(el('p','Recorded bait: '+bait+' · Reported co-isolating prey: '+prey));
    card.append(el('p','Cell model: '+(row.cell_line_literal||'Unreported')+' · Author inference: gene-level coassociation','small'));
    const raw=row.source_scores_raw?.pInt;
    const score=raw!==null&&raw!==undefined&&raw!==''&&Number.isFinite(Number(raw))?String(raw):null;
    card.append(el('p',score===null?'Companion pair score is unreported or ambiguous; all matched source records remain preserved.':
      'CompPASS-Plus pInt: '+score+' · Undirected pair-class score; not calibrated biological confidence.','small'));
    const citations=el('p');
    for(const citation of row.citations||[]){const link=biologicalCitation(citation);if(link)citations.append(link,document.createTextNode(' '));}
    card.append(citations);
    const inspect=el('button','Inspect assay and cell-model context','secondary');inspect.type='button';inspect.disabled=!runId;
    inspect.onclick=()=>{loadSourceGuide(row.observation_id||row.id);$('sourceGuide').scrollIntoView({block:'start'});};card.append(inspect);
    const original=(row.baseline_pair_edge_ids||[]).find(id=>(graph?.edges||[]).some(edge=>edge.id===id&&!edge.extension_source_kind));
    if(original){const baseline=el('button','Inspect original Pharos annotation','secondary');baseline.type='button';baseline.disabled=!runId;
      baseline.onclick=()=>{loadSourceGuide(original);$('sourceGuide').scrollIntoView({block:'start'});};card.append(document.createTextNode(' '),baseline);}
    box.append(card);
  }
  $('bioplexScope').textContent=records.length?
    records.length+' saved source-context records from one BioPlex study. Exact study reuse within Pharos or STRING remains unresolved. Source files remain in the private packet; native-data redistribution terms are unverified.':
    'This saved workspace has no BioPlex context packet.';
}
$('biologicalView').onchange=switchBiologicalView;
async function runBiologicalQuestion(){
  if(!runId)return;
  const request=++biologicalEpoch,sourceRun=runId,extension=graph.evidence_extension_sha256;
  $('biologicalAsk').disabled=true;$('biologicalStatus').textContent='Reading the verified saved tissue records…';
  try{
    const result=await api('/api/biological-question',{run_id:sourceRun,search:$('biologicalSearch').value,offset:biologicalOffset,limit:25});
    if(request!==biologicalEpoch||sourceRun!==runId)return;
    if(result.source_run!==sourceRun||result.evidence_extension_sha256!==extension||result.snapshot_sha256!==graph.snapshot_sha256)throw new Error('The answer belongs to different saved evidence.');
    biologicalAnswer=result;renderBiologicalAnswer(result);
    $('biologicalStatus').textContent='Saved-data answer. No model call, new retrieval or review decision was made.';
  }catch(error){if(request===biologicalEpoch)$('biologicalStatus').textContent=error.message;}
  finally{if(request===biologicalEpoch)$('biologicalAsk').disabled=false;}
}
function biologicalCitation(citation){
  if(!citation||typeof citation.url!=='string')return null;
  try{const u=new URL(citation.url);if(!['https:','http:'].includes(u.protocol)||u.username||u.password)return null;}
  catch(_){return null;}
  const roleLabel={resource_publication:'Resource paper',source_field_definitions:'Source field definitions'}[citation.role];
  return guideLink({label:citation.label||citation.title||roleLabel||citation.id||'Source reference',url:citation.url});
}
function biologicalNumber(value){
  return typeof value==='number'&&Number.isFinite(value)?Number(value.toPrecision(4)).toString():String(value??'not supplied');
}
function biologicalArchiveLabel(state){
  return {present_in_archived_public_PPI_profile:'Already in the archived public Pharos PPI view',
    raw_archived_pair_below_public_profile:'Recorded in the archive below its public score cutoff',
    no_nonmock_archived_PPI_pair:'No pair record in the archived PPI layer (excluding mock data)'}[state]||'Archive comparison unresolved';
}
function renderBiologicalAnswer(answer){
  $('biologicalAnswer').classList.remove('hidden');$('biologicalInterpretation').textContent=answer.interpretation;
  const box=$('biologicalRows');box.replaceChildren();
  box.append(el('p','Archive labels refer to the April 2024 snapshot. Absence from current Pharos has not been established.','small'));
  if(!answer.records.length)box.append(el('p','No recorded partner matches this search. This does not establish biological absence.'));
  for(const row of answer.records){
    const card=el('article',undefined,'evidence');
    card.append(el('h4',row.partner_label+' · '+row.partner));
    const source=el('p');source.append(document.createTextNode('Source: '));
    for(const citation of row.citations||[]){const link=biologicalCitation(citation);if(link){source.append(link,document.createTextNode(' '));}}
    card.append(source,el('p','Enriched proximity · '+(row.tissue_label||'Tissue context not supplied')));
    const stats=row.statistics||{};
    card.append(el('p','Isotype−Primary Beta_Ab: '+biologicalNumber(stats.Beta_Ab)+' · Full-family BH Q: '+biologicalNumber(stats.Q_Ab),'small'));
    card.append(el('p','Local review: '+row.local_review_state+' · '+biologicalArchiveLabel(row.archive_lookup?.status),'small'));
    const inspect=el('button','Inspect source and assay context','secondary');inspect.type='button';
    inspect.onclick=()=>{loadSourceGuide(row.observation_id);$('sourceGuide').scrollIntoView({block:'start'});};
    card.append(inspect);box.append(card);
  }
  const s=answer.summary;
  $('biologicalPage').textContent=s.matching_observations+' matching of '+s.source_observations+' source observations'+(s.returned?' · '+(s.offset+1)+'–'+(s.offset+s.returned):'');
  $('biologicalPrev').disabled=s.offset===0;$('biologicalNext').disabled=s.next_offset===null;
}
$('biologicalAsk').onclick=()=>{biologicalOffset=0;runBiologicalQuestion();};
$('biologicalPrev').onclick=()=>{biologicalOffset=Math.max(0,biologicalOffset-25);runBiologicalQuestion();};
$('biologicalNext').onclick=()=>{const next=biologicalAnswer?.summary?.next_offset;if(Number.isInteger(next)){biologicalOffset=next;runBiologicalQuestion();}};
$('biologicalSearch').addEventListener('input',()=>{biologicalEpoch++;biologicalAnswer=null;biologicalOffset=0;if(biologicalTimer)clearTimeout(biologicalTimer);biologicalTimer=setTimeout(()=>runBiologicalQuestion(),250);});
$('biologicalDownload').onclick=()=>{
  if(!biologicalAnswer)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(biologicalAnswer,null,2)],{type:'application/json'}));
  const link=el('a');link.href=url;link.download='egfr_tissue_evidence_page.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
