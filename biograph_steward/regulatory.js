// Source-qualified questions over saved directed records; no model or retrieval.
let regulatoryAnswer=null,regulatoryOffset=0,regulatoryEpoch=0,regulatoryTimer=null;
function setupRegulatory(){
  regulatoryEpoch++;regulatoryAnswer=null;regulatoryOffset=0;
  if(regulatoryTimer){clearTimeout(regulatoryTimer);regulatoryTimer=null;}
  $('regulatoryAnswer').hidden=true;$('regulatoryStatus').textContent='';
  $('regulatoryRows').replaceChildren();$('regulatorySearch').value='';
  $('regulatoryView').value='records';resetRegulatorySiteFilters();updateRegulatoryView();
  const choices=$('regulatoryProtein');choices.replaceChildren();
  const records=(graph?.extension_observations||[]).filter(r=>r.source_kind==='signor');
  const represented=new Set(records.flatMap(r=>r.products||[]));
  const targets=(graph?.targets||[]).filter(r=>represented.has(r.id));
  const label=r=>nodeIndex.get(r.id)?.sym||nodeIndex.get(r.id)?.name||r.id;
  for(const target of targets.sort((a,b)=>label(a).localeCompare(label(b)))){
    const option=el('option',label(target)+' · '+target.id);option.value=target.id;choices.append(option);
  }
  if(represented.has('UniProtKB:P00533'))choices.value='UniProtKB:P00533';
  $('regulatoryAsk').disabled=!records.length||!runId;
  for(const [button,protein] of [['regulatoryExampleMcc','UniProtKB:P23508'],['regulatoryExampleBraf','UniProtKB:P15056'],['regulatoryExampleContext','UniProtKB:P00533']])$(button).disabled=!runId||!represented.has(protein);
}
async function runRegulatoryQuestion(){
  if(!runId)return;
  if(regulatoryTimer){clearTimeout(regulatoryTimer);regulatoryTimer=null;}
  const request=++regulatoryEpoch,sourceRun=runId,extension=graph.evidence_extension_sha256;
  $('regulatoryAsk').disabled=true;$('regulatoryStatus').textContent='Reading saved regulatory records and their conditions…';
  try{
    const sites=$('regulatoryView').value==='sites';
    const body={run_id:sourceRun,protein:$('regulatoryProtein').value,
      direction:$('regulatoryDirection').value,offset:regulatoryOffset,limit:25};
    if(sites)Object.assign(body,{site:$('regulatorySite').value,cell_context:$('regulatoryCell').value,
      tissue_context:$('regulatoryTissue').value,context_reporting:$('regulatoryContextReporting').value});
    else body.search=$('regulatorySearch').value;
    const result=await api(sites?'/api/regulatory-sites':'/api/regulatory-question',body);
    if(request!==regulatoryEpoch||sourceRun!==runId)return;
    if(result.source_run!==sourceRun||result.evidence_extension_sha256!==extension||result.snapshot_sha256!==graph.snapshot_sha256)
      throw new Error('The regulatory answer belongs to different saved evidence.');
    if(sites&&result.format!=='biograph-steward.regulatory-sites.v1')throw new Error('The saved answer is not a site/context view.');
    regulatoryAnswer=result;renderRegulatoryAnswer(result);
    $('regulatoryStatus').textContent='Source-qualified answer. No model call, retrieval or graph decision was made.';
  }catch(error){if(request===regulatoryEpoch)$('regulatoryStatus').textContent=error.message;}
  finally{if(request===regulatoryEpoch)$('regulatoryAsk').disabled=false;}
}
function resetRegulatorySiteFilters(){
  $('regulatorySite').value='';$('regulatorySiteChoices').replaceChildren();
  for(const id of ['regulatoryCell','regulatoryTissue']){
    const option=el('option','All reported values');option.value='';$(id).replaceChildren(option);
  }
  $('regulatoryContextReporting').value='all';
}
function updateRegulatoryView(){
  const sites=$('regulatoryView').value==='sites';
  $('regulatorySiteFilters').hidden=!sites;$('regulatorySearchControls').hidden=sites;
  $('regulatoryAsk').textContent=sites?'Show sites and context':'Show reported regulation';
}
function regulatorySiteChoices(filters){
  $('regulatorySiteChoices').replaceChildren();
  for(const row of filters?.sites||[]){const option=el('option');option.value=row.value;option.label=row.label;$('regulatorySiteChoices').append(option);}
  for(const [id,key] of [['regulatoryCell','cell_contexts'],['regulatoryTissue','tissue_contexts']]){
    const selected=$(id).value,all=el('option','All reported values');all.value='';$(id).replaceChildren(all);
    for(const row of filters?.[key]||[]){
      const option=el('option',row.label+(row.label!==row.value?' · '+row.value:'')+' ('+row.observations+')');
      option.value=row.value;$(id).append(option);
    }
    if([...$(id).options].some(option=>option.value===selected))$(id).value=selected;
  }
}
function regulatorySiteDetails(row){
  const view=row.site_view,box=el('div',undefined,'notice'),site=view.reported_site;
  const position=site?site.substrate_label+' '+site.label:(row.residue_raw||'No single reported position');
  if(view.status==='split_source_view'){
    box.append(el('p','Modification step: source reports '+(view.modification_action==='phosphate_removal'?'phosphate removal':'phosphate addition')+
      ' at '+position+' through '+row.subject_label+'.'));
  }else{
    box.append(el('p','Reported position: '+position));
    const reasons={residue_unreported:'The source supplies no residue.',
      residue_not_one_explicit_position:'The residue field does not identify one explicit position.',
      mechanism_not_supported_phosphate_addition_or_removal:'The recorded mechanism does not supply a supported phosphate-change step.'};
    box.append(el('p',(view.reasons||[]).map(reason=>reasons[reason]||'The site/modification description remains unresolved.').join(' '),'small'));
  }
  box.append(el('p','Separate protein response: '+(view.source_protein_effect_literal||'Unreported')+'.'));
  box.append(el('p','A phosphate increase is not necessarily protein activation. This view preserves the source’s net protein effect and does not infer a causal effect of occupancy at this site.','small'));
  if(site)box.append(el('p','Source-reported coordinate; canonical sequence and experimental isoform are unverified.','small'));
  return box;
}
function regulatoryContext(value,display){
  const span=el('span');
  if(!value){span.textContent='Unreported';return span;}
  const values=value.split(';');
  values.forEach((term,index)=>{
    if(index)span.append(document.createTextNode('; '));
    const named=(display||[]).find(row=>row.id===term&&row.mapping==='exact_ontology_identifier_display');
    if(/^BTO:\d{7}$/.test(term))span.append(guideLink({label:(named?named.label+' · ':'')+term,url:'https://www.ebi.ac.uk/ols4/ontologies/bto/classes?iri='+encodeURIComponent('http://purl.obolibrary.org/obo/'+term.replace(':','_'))}));
    else span.append(document.createTextNode(term));
  });
  return span;
}
function renderRegulatoryAnswer(answer){
  $('regulatoryAnswer').hidden=false;$('regulatoryInterpretation').textContent=answer.interpretation;
  const s=answer.summary,box=$('regulatoryRows');box.replaceChildren();
  if(answer.template==='source_regulatory_sites_context.v1')regulatorySiteChoices(s.available_filters);
  $('regulatoryContextSummary').textContent=s.direction_observations+' source '+(s.direction_observations===1?'record':'records')+' from '+s.distinct_source_publications+' cited '+(s.distinct_source_publications===1?'publication':'publications')+' for this direction; '+s.cell_context_unreported_observations+
    ' have no reported cell context and '+s.tissue_context_unreported_observations+' have no reported tissue context. Counts include records outside the current filters.';
  if(!answer.records.length)box.append(el('p','No saved record matches this question and search. This does not establish absence of regulation elsewhere.'));
  for(const row of answer.records){
    const card=el('article',undefined,'evidence');
    card.append(el('h4',row.subject_label+' → '+row.object_label+(row.self_regulation?' · self-regulation':'')));
    if(row.site_view)card.append(regulatorySiteDetails(row));
    else card.append(el('p','Reported effect: '+(row.effect_literal||'Unreported')+' · Mechanism: '+(row.mechanism_literal||'Unreported')+
      ' · Site: '+(row.residue_raw||'Unreported')));
    const context=el('p');context.append(document.createTextNode('Cell context: '),regulatoryContext(row.cell_context_raw,row.cell_context_display),
      document.createTextNode(' · Tissue context: '),regulatoryContext(row.tissue_context_raw,row.tissue_context_display));card.append(context);
    card.append(el('p',(row.source_reported_direct?'Direct':'Indirect')+' (source-reported) · Local review: '+row.local_review_state+' · '+row.source_record_id,'small'));
    const organism=el('p','Source experimental organism: ','small');
    if(row.source_experimental_organism_reporting_state==='source_reported_in_vitro')organism.append(document.createTextNode('In vitro (source code −1)'));
    else if(row.source_experimental_taxon&&/^NCBITaxon:[1-9]\d*$/.test(row.source_experimental_taxon)){
      organism.append(guideLink({label:row.source_experimental_organism_display?.label||row.source_experimental_taxon,url:'https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id='+row.source_experimental_taxon.split(':')[1]}));
    }else organism.append(document.createTextNode(row.source_experimental_organism_raw||'Unreported'));
    organism.append(document.createTextNode(' · Human protein identifiers can represent source remapping.'));card.append(organism);
    const prior=row.saved_pair_context?.saved_string_capture;
    if(prior){
      const text=prior.state==='functional_score_below400'?
        'Already reported in saved STRING '+prior.source_release+' at '+biologicalNumber(prior.functional_score)+'; below this workspace’s '+biologicalNumber(prior.workspace_selection_threshold)+' display cutoff.':
        prior.functional_score!==null&&prior.functional_score!==undefined?
        'Saved STRING '+prior.source_release+' functional association score: '+biologicalNumber(prior.functional_score)+'.':
        'Saved STRING pair coverage: '+prior.state.replaceAll('_',' ')+'.';
      card.append(el('p',text+' Supporting-study reuse has not been resolved.','small'));
      const priorInspect=el('button','Inspect saved STRING coverage','secondary');priorInspect.type='button';
      priorInspect.onclick=()=>{loadSourceGuide(prior.id);$('sourceGuide').scrollIntoView({block:'start'});};card.append(priorInspect);
    }
    const source=el('p');source.append(document.createTextNode('Source citations: '));
    for(const citation of row.citations||[]){const link=biologicalCitation(citation);if(link)source.append(link,document.createTextNode(' '));}
    card.append(source);
    const audit=row.project_literature_check;
    if(audit?.notes?.length){
      for(const note of audit.notes){
        card.append(el('p',note.summary,'notice'));
        const details=el('details');details.append(el('summary',note.title+' · agent-assisted source check'));
        if(note.conditions?.length)details.append(el('p','Conditions: '+note.conditions.join(' '),'small'));
        if(note.what_is_not_established?.length)details.append(el('p','Unresolved scope: '+note.what_is_not_established.join(' '),'small'));
        if(note.documented_mapping)details.append(el('p','Documented coordinate mapping: '+note.documented_mapping,'small'));
        if(note.site_support_scope)details.append(el('p',note.site_support_scope,'small'));
        for(const reference of note.sources||[]){const link=biologicalCitation({label:reference.material||'Inspected source',url:reference.url});if(link){const p=el('p');p.append(link,document.createTextNode(' · '+reference.section));details.append(p);}}
        details.append(el('p','This check does not change the source claim or local review state.','small'));card.append(details);
      }
    }else card.append(el('p','No project literature check is attached to this source record.','small'));
    for(const paper of row.publication_metadata||[]){
      card.append(el('p',paper.title||'Publication title not supplied','small'));
      const details=(paper.publication_types||[]).join(', '),notices=(paper.correction_types||[]).join(', ');
      if(details||notices)card.append(el('p','Publication metadata: '+details+(notices?' · Linked notices: '+notices:''),'small'));
    }
    const inspect=el('button','Inspect claim, context and citation','secondary');inspect.type='button';
    inspect.onclick=()=>{loadSourceGuide(row.observation_id);$('sourceGuide').scrollIntoView({block:'start'});};
    card.append(inspect);box.append(card);
  }
  $('regulatoryPage').textContent=s.matching_observations+' matching of '+s.direction_observations+' direction-selected records'+
    (s.returned?' · '+(s.offset+1)+'–'+(s.offset+s.returned):'');
  $('regulatoryPrev').disabled=s.offset===0;$('regulatoryNext').disabled=s.next_offset===null;
}
$('regulatoryForm').onsubmit=e=>{e.preventDefault();regulatoryOffset=0;runRegulatoryQuestion();};
function regulatoryExample(protein,direction,search,view='records'){
  $('regulatoryProtein').value=protein;$('regulatoryDirection').value=direction;$('regulatorySearch').value=search;
  resetRegulatorySiteFilters();$('regulatoryView').value=view;if(view==='sites')$('regulatorySite').value=search;updateRegulatoryView();
  regulatoryOffset=0;if(regulatoryTimer){clearTimeout(regulatoryTimer);regulatoryTimer=null;}
  runRegulatoryQuestion();
}
$('regulatoryExampleMcc').onclick=()=>regulatoryExample('UniProtKB:P23508','incoming','');
$('regulatoryExampleBraf').onclick=()=>regulatoryExample('UniProtKB:P15056','outgoing','Ser614','sites');
$('regulatoryExampleContext').onclick=()=>regulatoryExample('UniProtKB:P00533','outgoing','SIGNOR-33633');
for(const id of ['regulatoryProtein','regulatoryDirection','regulatoryView'])$(id).onchange=()=>{
  if(regulatoryTimer){clearTimeout(regulatoryTimer);regulatoryTimer=null;}
  regulatoryEpoch++;regulatoryAnswer=null;regulatoryOffset=0;$('regulatoryAnswer').hidden=true;
  if(id!=='regulatoryView')resetRegulatorySiteFilters();updateRegulatoryView();
  $('regulatoryStatus').textContent='Choose '+$('regulatoryAsk').textContent+' for the new question.';
  $('regulatoryAsk').disabled=!runId||!graph?.evidence_extension?.sources?.signor;
};
for(const id of ['regulatorySite','regulatoryCell','regulatoryTissue','regulatoryContextReporting'])$(id).addEventListener('input',()=>{
  regulatoryEpoch++;regulatoryAnswer=null;regulatoryOffset=0;$('regulatoryAnswer').hidden=true;
  $('regulatoryStatus').textContent='Choose Show sites and context to apply these filters.';
});
$('regulatorySearch').addEventListener('input',()=>{
  regulatoryEpoch++;regulatoryAnswer=null;regulatoryOffset=0;if(regulatoryTimer)clearTimeout(regulatoryTimer);
  regulatoryTimer=setTimeout(()=>runRegulatoryQuestion(),250);
});
$('regulatoryPrev').onclick=()=>{regulatoryOffset=Math.max(0,regulatoryOffset-25);runRegulatoryQuestion();};
$('regulatoryNext').onclick=()=>{const next=regulatoryAnswer?.summary?.next_offset;if(Number.isInteger(next)){regulatoryOffset=next;runRegulatoryQuestion();}};
$('regulatoryDownload').onclick=()=>{
  if(!regulatoryAnswer)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(regulatoryAnswer,null,2)],{type:'application/json'}));
  const a=el('a');a.href=url;a.download='source_regulatory_answer_page.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
