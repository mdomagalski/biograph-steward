// Qualified assay records remain distinct from unqualified interaction paths.
let assayPage=0, assayEpoch=0;
function assayLabel(value){return String(value??'Not supplied').replaceAll('_',' ');}
async function setupAssay(){
  const epoch=++assayEpoch, attached=!!graph?.assay_evidence;
  const eligible=graph?.scope?.kind==='protein_cohort'&&graph?.data_kind==='live_pharos';
  $('assayPanel').classList.toggle('hidden',!eligible&&!attached);
  $('assayAttachForm').classList.toggle('hidden',attached||!runId||!eligible);
  $('assayLoaded').classList.toggle('hidden',!attached);
  $('assayStatus').textContent='';assayPage=0;
  if(attached){
    const rows=graph.assay_observations||[], evaluable=rows.filter(r=>r.evaluable).length;
    $('assaySummary').textContent=rows.length+' observations within this exact cohort: '+evaluable+' evaluable and '+(rows.length-evaluable)+' excluded assays. Every selected outcome remains in the ledger.';
    $('assayReceipt').textContent=JSON.stringify(graph.assay_evidence,null,2);
    $('assayProtein').replaceChildren(el('option','All cohort proteins'));
    $('assayProtein').options[0].value='all';
    for(const target of graph.targets){const option=el('option',nodeLabel(target.id)+' · '+target.id);option.value=target.id;$('assayProtein').append(option);}
    $('assayOutcome').value='all';renderAssays();return;
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
  const protein=$('assayProtein').value, outcome=$('assayOutcome').value;
  const rows=(graph?.assay_observations||[]).filter(r=>(protein==='all'||r.products.includes(protein))&&(outcome==='all'||(outcome==='excluded'?!r.evaluable:r.assay_status===outcome)));
  const size=25;assayPage=Math.min(assayPage,Math.max(0,Math.ceil(rows.length/size)-1));
  $('assayRows').replaceChildren(table(['Protein pair','Assay outcome','Evidence'],rows.slice(assayPage*size,(assayPage+1)*size).map(row=>({
    cells:[row.products.join(' ↔ '),assayLabel(row.assay_status),row.evaluable?'Qualified observation':'Excluded assay; no graph edge'],click:()=>inspectAssay(row)}))));
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
  const box=$('assayInspector'), assay=row.original.assay;
  box.replaceChildren(el('h3',row.products.join(' ↔ ')),el('p','Human protein Y2H-v1 observation: '+assayLabel(row.assay_status)));
  box.append(el('p','AD construct: '+assay.ad_orf_id+'; DB construct: '+assay.db_orf_id+'. The sorted protein order does not assign construct roles.','small'));
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
    $('assayPanel').scrollIntoView({block:'start'});status('Assay observations saved with the original Pharos cohort and complete source publication.');loadSavedWork();
  }catch(error){$('assayStatus').textContent=error.message;button.disabled=false;}
});
for(const id of ['assayProtein','assayOutcome'])$(id).addEventListener('change',()=>{assayPage=0;renderAssays();});
$('assayPrev').onclick=()=>{assayPage--;renderAssays();};$('assayNext').onclick=()=>{assayPage++;renderAssays();};
