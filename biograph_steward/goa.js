// Source-backed native GO additions stay inside the existing Evidence task.
let nativeGoaAnswer=null,nativeGoaOffset=0,nativeGoaEpoch=0;
function setupNativeGoa(){
  if(!$('nativeGoaPanel'))return;
  nativeGoaEpoch++;nativeGoaAnswer=null;nativeGoaOffset=0;
  const records=(graph?.extension_observations||[]).filter(r=>r.source_kind==='goa');
  $('nativeGoaPanel').hidden=!records.length;
  $('nativeGoaRows').replaceChildren();$('nativeGoaAnswer').hidden=true;
  $('nativeGoaStatus').textContent='Choose a protein to inspect the recovered annotations.';
  $('nativeGoaSearch').value='';$('nativeGoaView').value='candidates';
  const represented=new Set(records.filter(r=>r.graph_edge_id).map(r=>r.subject));
  const select=$('nativeGoaProtein');select.replaceChildren();
  const label=r=>nodeIndex.get(r.id)?.sym||nodeIndex.get(r.id)?.name||r.id;
  for(const row of (graph?.targets||[]).filter(t=>represented.has(t.id)).sort((a,b)=>label(a).localeCompare(label(b)))){
    const option=el('option',label(row)+' · '+row.id);option.value=row.id;select.append(option);
  }
  if(represented.has('UniProtKB:P04637'))select.value='UniProtKB:P04637';
  $('nativeGoaAsk').disabled=!runId||!select.options.length;
}
async function runNativeGoaQuestion(){
  if(!runId)return;
  const request=++nativeGoaEpoch,sourceRun=runId,extension=graph.evidence_extension_sha256,
    snapshot=graph.snapshot_sha256,publication=graph.evidence_extension?.sources?.goa?.publication_sha256;
  const query={run_id:sourceRun,protein:$('nativeGoaProtein').value,
    view:$('nativeGoaView').value,search:$('nativeGoaSearch').value,offset:nativeGoaOffset,limit:25};
  $('nativeGoaAsk').disabled=true;$('nativeGoaStatus').textContent='Reading saved native GO annotations…';
  try{
    const result=await api('/api/native-go-question',query);
    if(request!==nativeGoaEpoch||sourceRun!==runId||!graph||graph.snapshot_sha256!==snapshot||
      graph.evidence_extension_sha256!==extension||graph.evidence_extension?.sources?.goa?.publication_sha256!==publication)return;
    if(result.format!=='biograph-steward.native-go-question.v1'||result.source_run!==sourceRun||
      result.evidence_extension_sha256!==extension||result.snapshot_sha256!==snapshot||
      result.source_publication_sha256!==publication||result.anchor!==query.protein||result.view!==query.view||
      result.summary?.search!==query.search||result.summary?.offset!==query.offset||result.summary?.limit!==query.limit)
      throw new Error('The native GO answer belongs to different saved evidence.');
    nativeGoaAnswer=result;renderNativeGoaAnswer(result);
    $('nativeGoaStatus').textContent='Saved curator annotations. No retrieval, model call or review decision was made.';
  }catch(error){if(request===nativeGoaEpoch)$('nativeGoaStatus').textContent=error.message;}
  finally{if(request===nativeGoaEpoch)$('nativeGoaAsk').disabled=false;}
}
function renderNativeGoaAnswer(answer){
  $('nativeGoaAnswer').hidden=false;
  const box=$('nativeGoaRows'),s=answer.summary;box.replaceChildren(el('p',answer.interpretation,'notice'));
  box.append(el('p',s.matching_concepts+' GO '+(s.matching_concepts===1?'relationship':'relationships')+
    ' from '+s.matching_native_records+' native source '+(s.matching_native_records===1?'record':'records')+
    '. Source records and reference identifiers are not independent experiment counts.','small'));
  if(!answer.concepts.length)box.append(el('p',answer.view==='accepted'?
    'No accepted native GO annotation matches this selection. Inspect candidates to see source-supported records awaiting review.':
    'No recovered native annotation matches this selection. This does not establish absence of biology or evidence elsewhere.'));
  for(const concept of answer.concepts){
    const card=el('article',undefined,'evidence');
    card.append(el('h4',concept.subject_label+' · '+concept.relation_literal.replaceAll('_',' ')+' · '+concept.go_label));
    const term=el('p');term.append(guideLink({label:concept.go_id,url:'https://amigo.geneontology.org/amigo/term/'+encodeURIComponent(concept.go_id)}),
      document.createTextNode(' · Native relation: '+concept.relation_literal+' · Local review: '+concept.local_review_state));card.append(term);
    for(const row of concept.records){
      const record=el('details');record.append(el('summary',row.evidence_code+' · '+row.assigned_by+' · source line '+row.source_line));
      const refs=el('p','Reference identifiers: '+row.reference_identifiers.join(' | '));record.append(refs);
      const links=el('p');
      for(const citation of row.citations||[]){const link=biologicalCitation(citation);if(link)links.append(link,document.createTextNode(' '));}
      const technical=el('details');technical.append(el('summary','Technical source record (GAF fields and provenance)'),
        el('pre',row.native_record.raw_line),el('pre',JSON.stringify({native_record_id:row.native_record_id,
          source_gaf_sha256:row.source_gaf_sha256,source_line:row.source_line,source_observation:row.source_observation},null,2)));
      record.append(links,el('p','Identifiers on one annotation can name the same reference.','small'),technical);
      card.append(record);
    }
    const inspect=el('button','Inspect source and recorded conditions','secondary');inspect.type='button';
    inspect.onclick=()=>{loadSourceGuide(concept.assertion_id);$('sourceGuide').scrollIntoView({block:'start'});};card.append(inspect);
    box.append(card);
  }
  $('nativeGoaPage').textContent=s.matching_concepts+' matching '+(s.matching_concepts===1?'relationship':'relationships')+(s.returned_concepts?
    ' · '+(s.offset+1)+'–'+(s.offset+s.returned_concepts):'');
  $('nativeGoaPrev').disabled=s.offset===0;$('nativeGoaNext').disabled=s.next_offset===null;
}
function invalidateNativeGoa(){
  nativeGoaEpoch++;nativeGoaOffset=0;nativeGoaAnswer=null;
  $('nativeGoaAnswer').hidden=true;$('nativeGoaStatus').textContent='Show annotations to apply this selection.';
  $('nativeGoaAsk').disabled=!runId||!$('nativeGoaProtein').options.length;
}
if($('nativeGoaForm')){
  $('nativeGoaForm').addEventListener('submit',event=>{event.preventDefault();nativeGoaOffset=0;runNativeGoaQuestion();});
  for(const id of ['nativeGoaProtein','nativeGoaView'])$(id).addEventListener('change',invalidateNativeGoa);
  $('nativeGoaSearch').addEventListener('input',invalidateNativeGoa);
  $('nativeGoaPrev').onclick=()=>{nativeGoaOffset=Math.max(0,nativeGoaOffset-25);runNativeGoaQuestion();};
  $('nativeGoaNext').onclick=()=>{const next=nativeGoaAnswer?.summary?.next_offset;if(Number.isInteger(next)){nativeGoaOffset=next;runNativeGoaQuestion();}};
  $('nativeGoaDownload').onclick=()=>{
    if(!nativeGoaAnswer)return;
    const url=URL.createObjectURL(new Blob([JSON.stringify(nativeGoaAnswer,null,2)],{type:'application/json'}));
    const a=el('a');a.href=url;a.download='native_go_answer_page.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
}
