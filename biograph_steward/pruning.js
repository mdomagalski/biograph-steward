// Read-only inspection of published, fixed PPI assessments. No graph mutation.
const pruningArmIds=['unpruned','native_top80','ne_top80'];
const pruningArmNames={unpruned:'Original graph',native_top80:'Native score · top 80% eligible',ne_top80:'Network Enhancement · top 80% eligible'};
let pruningAssessmentId='',pruningSummary=null,pruningOffset=0,pruningTotal=0,pruningSelectedPair=null,pruningDetailRow=null;
let pruningCatalogRequest=0,pruningSummaryRequest=0,pruningListRequest=0,pruningDetailRequest=0;
const pruningPageSize=25;
function pruningCount(value){return Number.isFinite(value)?value.toLocaleString():'Not supplied';}
function pruningPercent(value){return Number.isFinite(value)?(100*value).toFixed(2)+'%':'Not supplied';}
function pruningScore(value){return Number.isFinite(value)?Number(value.toPrecision(6)).toString():'Not supplied';}
function pruningLabel(row,side){return typeof row.labels?.[side]==='string'&&row.labels[side]?row.labels[side]:row[side];}
function pruningPairLabel(row){return pruningLabel(row,'subject')+' ↔ '+pruningLabel(row,'object');}
function pruningArm(){return $('pruningArm').value;}
function pruningBase(){return '/api/pruning-preview/'+encodeURIComponent(pruningAssessmentId);}
function pruningStatus(message,error=false){const box=$('pruningPreviewStatus');box.textContent=message;box.className=error?'notice error':'small';}
function pruningUnavailable(message){
  pruningSummaryRequest++;pruningSummary=null;pruningClearPairs();$('pruningPreviewBody').hidden=true;
  pruningStatus('Saved preview unavailable: '+message+' Reload assessments to verify the saved files again.',true);
}

async function pruningGet(url){
  const response=await fetch(url);let result;
  try{result=await response.json();}catch(_){throw new Error('The workspace did not return a pruning assessment.');}
  if(!response.ok)throw new Error(result.error||'The saved pruning assessment could not be verified.');
  return result;
}
function pruningPersist(pairId=null){
  const url=new URL(location.href);
  if(pruningAssessmentId)url.searchParams.set('pruning',pruningAssessmentId);
  if(pairId)url.searchParams.set('pruning_pair',pairId);else url.searchParams.delete('pruning_pair');
  history.replaceState(null,'',url.pathname+url.search+url.hash);
}
function pruningClearPairs(message='Choose a pair to inspect its source records.',{keepDetail=false}={}){
  pruningListRequest++;pruningDetailRequest++;pruningTotal=0;
  if(!keepDetail){pruningSelectedPair=null;pruningDetailRow=null;}
  $('pruningPairs').replaceChildren();$('pruningPage').textContent='';
  $('pruningPrevious').disabled=true;$('pruningNext').disabled=true;
  $('pruningPairStatus').textContent=message;
  if(!keepDetail)$('pruningDetail').replaceChildren(el('p','Select a pair to compare both decisions and inspect its recorded assay context.'));
}
function pruningExternalLink(label,url){
  if(typeof url!=='string')return null;
  try{const parsed=new URL(url);if(!['http:','https:'].includes(parsed.protocol)||parsed.username||parsed.password)return null;
    const link=el('a',label);link.href=parsed.href;link.target='_blank';link.rel='noopener noreferrer';return link;
  }catch(_){return null;}
}
function pruningDisposition(row,arm){
  if(!row.graph_present)return 'No source edge · not pruned';
  const value=row.arms[arm];
  if(value.retained===false)return 'Removed from view';
  return value.decision==='abstain'?'Abstain · retained':'Retained';
}
function pruningAssayText(row){
  if(row.assay_state==='detected')return 'Recorded detection';
  if(row.assay_state==='not_detected')return 'Recorded nondetection';
  if(row.assay_state==='excluded')return 'Excluded assay: '+String(row.assay?.status||'reason not supplied').replaceAll('_',' ');
  return 'No assay observation in this panel';
}
function pruningTable(headers,rows,className=''){
  const table=el('table',undefined,className),head=el('thead'),tr=el('tr'),body=el('tbody');
  for(const label of headers){const th=el('th',label);th.scope='col';tr.append(th);}head.append(tr);
  for(const cells of rows){const row=el('tr');for(const value of cells){const td=el('td');td.append(value instanceof Node?value:document.createTextNode(String(value)));row.append(td);}body.append(row);}
  table.append(head,body);return table;
}
async function loadPruningAssessments(){
  const request=++pruningCatalogRequest,previous=pruningAssessmentId;
  pruningSummaryRequest++;pruningSummary=null;pruningAssessmentId='';pruningClearPairs();
  $('pruningPreviewBody').hidden=true;$('pruningAssessment').disabled=true;$('pruningReload').disabled=true;
  pruningStatus('Checking saved pruning assessments…');
  try{
    const result=await pruningGet('/api/pruning-previews');if(request!==pruningCatalogRequest)return;
    if(!Array.isArray(result.previews))throw new Error('Saved assessment list is invalid.');
    const select=$('pruningAssessment');select.replaceChildren();
    for(const preview of result.previews){const option=el('option',preview.title||preview.id);option.value=preview.id;select.append(option);}
    if(!result.previews.length){const option=el('option','No verified saved assessment');option.value='';select.append(option);pruningStatus('No verified saved pruning assessment is available in this workspace.');return;}
    const url=new URL(location.href),requested=url.searchParams.get('pruning');
    const selected=[previous,requested,result.previews[0].id].find(id=>result.previews.some(p=>p.id===id));
    select.value=selected;select.disabled=false;
    const reopenPair=!previous&&requested===selected?url.searchParams.get('pruning_pair'):null;
    await loadPruningAssessment(selected,reopenPair);
  }catch(error){if(request===pruningCatalogRequest)pruningStatus(error.message,true);}
  finally{if(request===pruningCatalogRequest)$('pruningReload').disabled=false;}
}
async function loadPruningAssessment(id,reopenPair=null){
  const request=++pruningSummaryRequest;pruningAssessmentId=id;pruningSummary=null;
  pruningClearPairs();$('pruningPreviewBody').hidden=true;pruningStatus('Verifying the saved assessment…');
  try{
    const result=await pruningGet(pruningBase());if(request!==pruningSummaryRequest||id!==pruningAssessmentId)return;
    if(!result.scope||result.scope.current_workspace_applied!==false||!pruningArmIds.every(arm=>result.arms?.[arm]))throw new Error('Saved assessment summary is invalid.');
    pruningSummary=result;pruningOffset=0;$('pruningArm').value='unpruned';$('pruningSelection').value=reopenPair?'all':'measured';$('pruningSearch').value=reopenPair||'';
    $('pruningPreviewBody').hidden=false;renderPruningSummary();pruningPersist(reopenPair);
    pruningStatus('Saved retrospective assessment verified. Browsing these views does not change the current workspace.');
    await loadPruningPairs();
    if(reopenPair&&request===pruningSummaryRequest&&id===pruningAssessmentId)await inspectPruningPair(reopenPair);
  }catch(error){if(request===pruningSummaryRequest){pruningSummary=null;$('pruningPreviewBody').hidden=true;pruningStatus(error.message,true);}}
}
function renderPruningSummary(){
  if(!pruningSummary)return;
  const summary=pruningSummary,scope=summary.scope,arm=summary.arms[pruningArm()],base=summary.arms.unpruned,assay=arm.assay||{};
  $('pruningScope').textContent='Saved assessment: '+(summary.title||pruningAssessmentId)+' · '+(scope.source_database||'Source')+' · source version '+(scope.source_version||'not supplied')+' · '+pruningCount(scope.source_protein_count)+' resolved source proteins · '+pruningCount(scope.source_edge_count)+' original source edges. '+(scope.dataset_status==='consumed_development'?'Previously used development data. ':'')+'This is not the graph currently open in the workspace.';
  const cards=[
    [pruningCount(arm.retained_edges),'Source edges retained',pruningCount(arm.pruned_edges)+' removed in this view'],
    [pruningCount(assay.pruned_detected),'Recorded detections lost',pruningCount(assay.retained_detected)+' of '+pruningCount(base.assay?.retained_detected)+' source-present detections retained'],
    [pruningPercent(assay.retained_detection_fraction),'Detection fraction in retained measured pairs',pruningCount(assay.retained_pairs)+' measured pairs retained'],
    [pruningCount(arm.utility?.isolated_nodes),'Isolated source proteins',pruningCount(arm.utility?.preserved_node_count)+' source protein records preserved']
  ];
  $('pruningMetrics').replaceChildren();for(const [number,label,note] of cards){const card=el('div');card.append(el('strong',number),el('span',label),el('p',note,'small'));$('pruningMetrics').append(card);}
  $('pruningCoverage').textContent='Assay coverage: '+pruningCount(assay.assay_eligible_pairs)+' evaluable pairs; '+pruningCount(assay.source_present_pairs)+' represented in the original source graph and '+pruningCount(assay.source_absent_pairs)+' not represented. This view retains '+pruningCount(assay.retained_detected)+' of '+pruningCount(assay.detected_total)+' recorded detections across the full panel. Source-absent pairs are uncovered, not pruned.';
  const comparison=pruningTable(['Saved view','Source edges retained','Recorded detections lost','Retained detection fraction','Isolated proteins'],pruningArmIds.map(id=>{
    const row=summary.arms[id];return [pruningArmNames[id],pruningCount(row.retained_edges),pruningCount(row.assay?.pruned_detected),pruningPercent(row.assay?.retained_detection_fraction),pruningCount(row.utility?.isolated_nodes)];
  }),'pruning-comparison');
  [...comparison.tBodies[0].rows].forEach((row,index)=>row.setAttribute('aria-current',String(pruningArmIds[index]===pruningArm())));
  $('pruningComparison').replaceChildren(comparison);
  $('pruningDecision').textContent=summary.comparison?.primary_decision==='tradeoff_no_clear_NE_advantage'?'The fixed rule for a clear NE advantage was not met. Compare retained detections, detection fraction and coverage in the table; this result does not establish overall superiority. The original graph remains intact.':summary.comparison?.primary_decision==='bounded_NE_advantage_observed'?'This saved assessment met its bounded rule for NE advantage on the previously used panel. It does not establish independent biological accuracy, and the original graph remains intact.':'This saved assessment reports bounded task results. Inspect retention, coverage and assay context before interpreting a pruning view; no default graph change is made.';
  const info=$('pruningInterpretation');info.replaceChildren();
  if(summary.comparison?.primary_rule)info.append(el('p','Fixed comparison rule: '+summary.comparison.primary_rule));
  const ap=summary.comparison?.average_precision;
  if(ap?.native&&ap?.ne)info.append(el('p','Secondary raw-score ranking, before pruning: native AP '+pruningScore(ap.native.value)+'; NE AP '+pruningScore(ap.ne.value)+'. Numeric coverage: '+pruningCount(ap.native.numeric_scores)+' native and '+pruningCount(ap.ne.numeric_scores)+' NE scores.'));
  if(summary.comparison?.average_precision_policy)info.append(el('p',summary.comparison.average_precision_policy,'small'));
  for(const message of summary.limitations||[])info.append(el('p',message,'small'));
  info.append(el('p','Physical association priority in Ask & explore uses another source view and is not a pruning arm here. Its scores are not substituted into this fixed assessment.','small'));
  if(graph&&runId){const p=el('p'),link=el('a','Open the current workspace’s physical-priority control');link.href='#questionRanking';p.append(link);info.append(p);}
  const paper=pruningExternalLink('Study and assay methods',scope.reference_url);if(paper){const p=el('p');p.append(paper);info.append(p);}
  const trace=$('pruningTrace');trace.replaceChildren();const details=el('details');details.append(el('summary','Source and fixed-assessment identifiers'),el('pre',JSON.stringify({scope:summary.scope,provenance:summary.provenance},null,2)));trace.append(details);
  const downloads=$('pruningDownloadLinks');downloads.replaceChildren();
  const labels={'manifest.json':'Preview file manifest','summary.json':'Assessment summary','protocol.json':'Frozen comparison protocol','result.json':'Completed result receipt','metrics.json':'Metrics and coverage','pair_accounting.jsonl':'Measured-pair accounting','dispositions.jsonl':'Pair choices for each saved view'};
  const list=el('ul');
  for(const [name,url] of Object.entries(summary.downloads||{})){
    if(!Object.hasOwn(labels,name)||url!==pruningBase()+'/files/'+encodeURIComponent(name))continue;
    const item=el('li'),link=el('a',labels[name]+' · '+name);link.href=url;link.download=name;item.append(link);list.append(item);
  }
  if(list.childNodes.length)downloads.append(list);else downloads.append(el('p','No saved assessment download links were supplied.','small'));

}
async function loadPruningPairs({keepDetail=false}={}){
  if(!pruningSummary)return;
  const request=++pruningListRequest,id=pruningAssessmentId,arm=pruningArm(),selection=$('pruningSelection').value,search=$('pruningSearch').value.trim(),offset=pruningOffset;
  pruningDetailRequest++;
  if(keepDetail&&pruningDetailRow)renderPruningDetail(pruningDetailRow);
  else{pruningSelectedPair=null;pruningDetailRow=null;$('pruningDetail').replaceChildren(el('p','Select a pair to compare both decisions and inspect its recorded assay context.'));}
  $('pruningPairStatus').textContent='Reading saved pairs…';$('pruningSearchButton').disabled=true;$('pruningPrevious').disabled=true;$('pruningNext').disabled=true;
  const params=new URLSearchParams({arm,selection,search,offset:String(offset),limit:String(pruningPageSize)});
  try{
    const result=await pruningGet(pruningBase()+'/pairs?'+params);if(request!==pruningListRequest||id!==pruningAssessmentId)return;
    if(result.arm!==arm||result.selection!==selection||result.search!==search||!Array.isArray(result.rows)||!Number.isInteger(result.total)||result.total<0||result.offset!==offset||result.limit!==pruningPageSize||result.rows.length>pruningPageSize||result.offset+result.rows.length>result.total)throw new Error('Saved pair response does not match these filters.');
    pruningOffset=result.offset;pruningTotal=result.total;renderPruningPairs(result.rows);pruningPersist(pruningSelectedPair);
    if(keepDetail&&pruningDetailRow&&!result.rows.some(row=>row.pair_id===pruningSelectedPair))$('pruningDetail').prepend(el('p','The selected pair is not on this result page; its saved decisions remain shown.','small'));
    const first=result.total?result.offset+1:0,last=result.offset+result.rows.length;
    $('pruningPage').textContent=pruningCount(first)+'–'+pruningCount(last)+' of '+pruningCount(result.total);
    $('pruningPrevious').disabled=result.offset===0;$('pruningNext').disabled=last>=result.total;
    $('pruningPairStatus').textContent=result.total?pruningCount(result.total)+' saved pairs match these filters. Counts above describe the complete assessment, not this page.':arm==='unpruned'&&['removed','detections_removed'].includes(selection)?'The original view removes no source edges. Select a pruning view to inspect its removals.':selection==='detections_removed'&&pruningSummary.arms[arm].assay?.pruned_detected===0?'This saved view removes no source-present recorded detections in this panel. That does not certify unassayed removals as biologically safe.':'No saved pair matches these filters. A missing match does not establish biological absence.';
    return result;
  }catch(error){if(request===pruningListRequest)pruningUnavailable(error.message);}
  finally{if(request===pruningListRequest)$('pruningSearchButton').disabled=false;}
}
function renderPruningPairs(rows){
  const table=el('table'),caption=el('caption','Saved pairs in the selected view'),head=el('thead'),tr=el('tr'),body=el('tbody');
  for(const label of ['Protein pair','Preview decision','Assay observation','Providers','Inspect']){const th=el('th',label);th.scope='col';tr.append(th);}head.append(tr);
  for(const row of rows){
    const item=el('tr');item.dataset.pruningPair=row.pair_id;item.classList.toggle('selected',row.pair_id===pruningSelectedPair);const name=el('td'),pair=el('span',pruningPairLabel(row),'pruning-pair');pair.append(el('small',row.subject+' ↔ '+row.object));name.append(pair);
    const decision=el('td'),removed=row.graph_present&&row.arms[pruningArm()].retained===false;decision.append(el('span',pruningDisposition(row,pruningArm()),'pruning-badge'+(removed?' removed':'')));
    const assay=el('td');assay.append(el('span',pruningAssayText(row),'pruning-badge'+(row.assay_state==='detected'?(removed?' warning':' detected'):'')));
    const providers=el('td',row.providers?.length?row.providers.join(', '):row.graph_present?'Not supplied':'No source edge');
    const action=el('td'),button=el('button','Inspect','secondary');button.type='button';button.setAttribute('aria-label','Inspect '+pruningPairLabel(row));button.onclick=()=>inspectPruningPair(row.pair_id);action.append(button);
    item.append(name,decision,assay,providers,action);body.append(item);
  }
  table.append(caption,head,body);$('pruningPairs').replaceChildren(table);
}
function pruningPairDiagram(row){
  const arm=pruningArm(),present=row.graph_present,retained=present&&row.arms[arm].retained;
  const state=!present?'No source edge for this pair':retained?'Source edge retained in this view':'Source edge removed from this view';
  const svg=svgEl('svg',{viewBox:'0 0 680 155',role:'img','aria-label':pruningArmNames[arm]+': '+state});
  if(present){const line=svgEl('line',{x1:245,y1:48,x2:435,y2:48,stroke:retained?'#147c83':'#9b650e','stroke-width':3,'stroke-dasharray':retained?'':'8 5'});svg.append(line);}
  for(const [side,x] of [['subject',25],['object',435]]){
    const group=svgEl('g'),rect=svgEl('rect',{x,y:22,width:220,height:54,rx:7,fill:present?'#eef6f6':'#f1f5f7',stroke:'#76909d','stroke-dasharray':present?'':'4 3'});
    const title=svgEl('title');title.textContent=pruningLabel(row,side)+' | '+row[side];group.append(rect,title);
    const label=svgEl('text',{x:x+110,y:43,'text-anchor':'middle','font-size':12,fill:'#172b3a'}),value=pruningLabel(row,side);label.textContent=value.length>28?value.slice(0,27)+'…':value;
    const identifier=svgEl('text',{x:x+110,y:62,'text-anchor':'middle','font-size':11,fill:'#52697b'});identifier.textContent=row[side];group.append(label,identifier);svg.append(group);
  }
  const text=svgEl('text',{x:340,y:105,'text-anchor':'middle','font-size':12,fill:'#172b3a'});text.textContent=state;svg.append(text);
  const note=svgEl('text',{x:340,y:127,'text-anchor':'middle','font-size':11,fill:'#52697b'});note.textContent=present?'Both source protein records remain; line style shows a policy decision.':'Reference endpoints shown; source node presence is not asserted.';svg.append(note);return svg;
}
async function inspectPruningPair(pairId){
  const request=++pruningDetailRequest,id=pruningAssessmentId,arm=pruningArm();
  $('pruningDetail').replaceChildren(el('p','Reading the saved pair and its source context…'));
  try{
    const row=await pruningGet(pruningBase()+'/pair/'+encodeURIComponent(pairId));
    if(request!==pruningDetailRequest||id!==pruningAssessmentId||arm!==pruningArm())return;
    if(row.pair_id!==pairId||!row.arms||!pruningArmIds.every(key=>row.arms[key]))throw new Error('Saved pair response does not match this selection.');
    pruningSelectedPair=pairId;pruningDetailRow=row;pruningPersist(pairId);renderPruningDetail(row);
    for(const tr of $('pruningPairs').querySelectorAll('tbody tr'))tr.classList.toggle('selected',tr.dataset.pruningPair===pairId);
    if(window.matchMedia('(max-width:1050px)').matches)$('pruningDetail').scrollIntoView({block:'start'});
    $('pruningDetail').focus({preventScroll:true});
  }catch(error){if(request===pruningDetailRequest)pruningUnavailable(error.message);}
}
function renderPruningDetail(row){
  const box=$('pruningDetail');box.replaceChildren(el('h3',pruningPairLabel(row)),el('p',row.subject+' ↔ '+row.object,'small'),el('p','Selected saved view: '+pruningArmNames[pruningArm()],'small'));
  const diagram=el('div',undefined,'graph-box');diagram.append(pruningPairDiagram(row));box.append(diagram,el('p','This drawing shows the selected saved view. It does not show biological truth, review acceptance or the current workspace graph.','small'));
  if(row.graph_present&&row.assay_state==='detected'&&row.arms[pruningArm()].retained===false)box.append(el('p','This policy removes a source association for a pair with a recorded assay detection. The observation and original source evidence remain preserved.','notice error'));
  else if(row.graph_present&&row.assay_state==='detected'&&row.arms.native_top80.retained===false&&row.arms.ne_top80.retained===true)box.append(el('p','Native-score pruning removes this pair’s source association despite its recorded detection. Network Enhancement retains it in the saved comparison.','notice warn'));
  box.append(pruningTable(['Saved view','Decision'],pruningArmIds.map(arm=>[pruningArmNames[arm],pruningDisposition(row,arm)])));
  box.append(el('p','Abstain means outside the policy’s assessed set: the source edge stays retained. It does not mean validated.','small'));
  if(!row.graph_present)box.append(el('p','This nominated pair is not represented by an edge in the source graph. Neither policy removes a source edge for it.','notice'));
  box.append(el('h4',pruningAssayText(row)));
  if(row.assay_state==='unassessed')box.append(el('p','There is no assay observation for this pair in the saved panel. This is unassessed evidence, not a negative result.'));
  if(row.assay_state==='detected')box.append(el('p','The authors reported detection for the recorded assay and construct combination. This does not establish an interaction in every biological setting.'));
  if(row.assay_state==='not_detected')box.append(el('p','The recorded constructs were not detected under these assay conditions. This does not establish universal noninteraction or make another source association false.'));
  if(row.assay_state==='excluded')box.append(el('p','This observation was excluded from scoring under the unchanged assay rules. Its original row and constructs remain in the reference.'));
  if(row.assay){
    box.append(el('p','Author source row: '+pruningCount(row.assay.source_row)+'.','small'));
    const constructs=row.assay.constructs||{};
    box.append(pruningTable(['Reported construct','Identifier'],[['AD · activation-domain construct (prey)',constructs.ad_orf_id??'Not supplied'],['DB · DNA-binding-domain construct (bait)',constructs.db_orf_id??'Not supplied']]));
    box.append(el('p','Prey is fused to the activation domain and bait to the DNA-binding domain in a two-hybrid assay. These roles do not establish regulatory direction. Protein-to-construct orientation is not inferred from this unordered graph pair.','small'));
    const exposure=row.assay.exposure||{},flags=[];
    if(exposure.huri_overlap)flags.push('HuRI pair overlap');if(exposure.inmc_overlap)flags.push('INMC pair overlap');if(exposure.consumed_intact_exact_pair)flags.push('consumed IntAct pair overlap');
    box.append(el('p',flags.length?'Known pair-exposure flags: '+flags.join('; ')+'.':'No HuRI, INMC or consumed-IntAct pair-overlap flag is recorded.','small'),el('p','Pair-overlap flags do not establish independent replication or exclude other reused studies.','small'));
  }
  const paper=pruningExternalLink('Open the study and assay methods',pruningSummary.scope.reference_url);if(paper){const p=el('p');p.append(paper);box.append(p);}
  const details=el('details');details.append(el('summary','Source records, scores and fixed-assessment trace'));
  details.append(el('p','Providers: '+(row.providers?.join(', ')||'No source provider assigned for an uncovered pair.')));
  details.append(el('p','Native association score: '+pruningScore(row.native_score)+' · NE-transformed score: '+pruningScore(row.ne_score)+'. These are not probabilities of Y2H detection; NE scores are not calibrated confidence.','small'));
  details.append(el('pre',JSON.stringify({pair_id:row.pair_id,evidence_edge_ids:row.edge_ids,pruning_eligible:row.pruning_eligible,source_providers:row.providers,assay:row.assay,provenance:pruningSummary.provenance},null,2)));
  const raw=el('a','Open this saved pair as JSON');raw.href=pruningBase()+'/pair/'+encodeURIComponent(row.pair_id);raw.target='_blank';raw.rel='noopener noreferrer';const p=el('p');p.append(raw);details.append(p);box.append(details);
}
function initializePruningPreview(){
  if(!$('pruningPreviewPanel'))return;
  $('pruningReload').onclick=loadPruningAssessments;
  $('pruningAssessment').addEventListener('change',()=>loadPruningAssessment($('pruningAssessment').value));
  $('pruningArm').addEventListener('change',()=>{const keepDetail=!!pruningDetailRow;pruningOffset=0;pruningClearPairs('View changed. Reading its saved decisions…',{keepDetail});renderPruningSummary();loadPruningPairs({keepDetail});});
  $('pruningSelection').addEventListener('change',()=>{pruningOffset=0;pruningClearPairs('Filters changed. Reading saved pairs…');loadPruningPairs();});
  $('pruningSearch').addEventListener('input',()=>{pruningOffset=0;pruningClearPairs('Search changed. Choose Find saved pairs to update the list.');$('pruningSearchButton').disabled=false;});
  $('pruningSearchForm').addEventListener('submit',event=>{event.preventDefault();pruningOffset=0;loadPruningPairs();});
  $('pruningPrevious').onclick=()=>{pruningOffset=Math.max(0,pruningOffset-pruningPageSize);loadPruningPairs();};
  $('pruningNext').onclick=()=>{if(pruningOffset+pruningPageSize<pruningTotal){pruningOffset+=pruningPageSize;loadPruningPairs();}};
  $('pruningExample').onclick=async()=>{
    pruningClearPairs('Finding the saved walkthrough pair…');pruningOffset=0;$('pruningSearch').value='P22674 P38936';$('pruningSelection').value='all';
    const id=pruningAssessmentId,request=pruningListRequest+1,result=await loadPruningPairs();
    if(result?.rows?.length===1&&id===pruningAssessmentId&&request===pruningListRequest)await inspectPruningPair(result.rows[0].pair_id);
  };
  if(['http:','https:'].includes(location.protocol))loadPruningAssessments();
  else{pruningStatus('Open this report in the running workspace to browse verified saved pruning assessments.');$('pruningReload').disabled=true;}
}
