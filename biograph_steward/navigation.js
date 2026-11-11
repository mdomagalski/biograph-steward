// Task panels retain the existing DOM, source passports and review handlers.
// Tab semantics follow WAI-ARIA APG; no new UI framework or graph store is needed.
const workspaceNames=['data','ask','evidence','compare','export'];
const workspaceSuffix={data:'Data',ask:'Ask',evidence:'Evidence',compare:'Compare',export:'Export'};
let workspaceView='data',workspaceLoaded=false,inspectionRequest=0,pathRequest=0;
function workspaceHashTarget(){try{return $(decodeURIComponent(location.hash.slice(1)));}catch(_){return null;}}
function showWorkspaceView(name,{focus=false,persist=true}={}){
  if(!workspaceNames.includes(name))return;
  const button=$('workspaceTab'+workspaceSuffix[name]);
  if(button.disabled)return;
  workspaceView=name;
  for(const key of workspaceNames){
    const active=key===name,tab=$('workspaceTab'+workspaceSuffix[key]);
    tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;
    $('workspace'+workspaceSuffix[key]).hidden=!active;
  }
  if(persist){const url=new URL(location.href);url.searchParams.set('view',name);history.replaceState(null,'',url.pathname+url.search+url.hash);}
  if(focus)button.focus();
}
function revealWorkspaceTarget(target){
  if(!target)return;
  const panel=target.closest('[data-workspace-panel]');
  if(panel)showWorkspaceView(panel.dataset.workspacePanel);
}
function initializeWorkspaceNavigation(){
  const move=(id,view)=>{const item=$(id);if(item)$('workspace'+workspaceSuffix[view]).append(item);};
  for(const key of workspaceNames)$('workspace'+workspaceSuffix[key]).dataset.workspacePanel=key;
  for(const id of ['savedWorkPanel','controls','constructionPublication'])move(id,'data');
  for(const id of ['answerNavigation','workspaceQuestionChoice','plannerPanel','guidedQuestion','civicQuestion'])move(id,'ask');
  // Put broad exploration after the existing focused question flow.
  move('pathExplorer','ask');
  for(const id of ['assayPanel','inspectionDetails'])move(id,'evidence');
  for(const id of ['benchmarkPanel','refreshPanel'])move(id,'compare');
  move('submissionPanel','export');
  for(const id of ['downloadJson','downloadZip'])$('workspaceDownloads').append($(id));
  $('workspaceContext').append($('results'));
  const tabs=workspaceNames.map(key=>$('workspaceTab'+workspaceSuffix[key]));
  for(const button of tabs){
    button.onclick=()=>showWorkspaceView(button.dataset.workspace);
    button.addEventListener('keydown',event=>{
      const enabled=tabs.filter(tab=>!tab.disabled),index=enabled.indexOf(button);
      let next;
      if(event.key==='ArrowRight')next=enabled[(index+1)%enabled.length];
      if(event.key==='ArrowLeft')next=enabled[(index+enabled.length-1)%enabled.length];
      if(event.key==='Home')next=enabled[0];
      if(event.key==='End')next=enabled[enabled.length-1];
      if(next){event.preventDefault();showWorkspaceView(next.dataset.workspace,{focus:true});}
    });
  }
  const followHash=()=>{const target=workspaceHashTarget();if(target){revealWorkspaceTarget(target);if(target.tagName==='DETAILS')target.open=true;}};
  document.addEventListener('click',event=>{
    const link=event.target.closest('a[href^="#"]');
    if(link&&link.hash.length>1){let target;try{target=$(decodeURIComponent(link.hash.slice(1)));}catch(_){return;}if(target)revealWorkspaceTarget(target);}
  });
  window.addEventListener('hashchange',followHash);
  const requested=new URLSearchParams(location.search).get('view');
  if(requested==='compare')showWorkspaceView(requested,{persist:false});
  if(location.hash)followHash();
}
function setupWorkspace(){
  inspectionRequest++;pathRequest++;
  for(const key of ['ask','evidence','export'])$('workspaceTab'+workspaceSuffix[key]).disabled=false;
  $('sourceGuideOutput').replaceChildren();$('pathExploreResults').replaceChildren();
  $('sourceGuideStatus').textContent='Select a claim or choose Inspect source on a path.';
  $('pathExploreStatus').textContent='Searches this saved graph only. No source retrieval or model call is made.';
  $('sourceGuideButton').disabled=!runId;$('pathExploreButton').disabled=!runId;
  $('sourceGuideSearch').value='';populateSourceGuide();populatePathEntities();
  const relations=[...new Set((graph.assertions||[]).map(a=>a.predicate))].sort();
  $('pathPredicate').replaceChildren(el('option','All saved relationship types'));$('pathPredicate').options[0].value='';
  for(const predicate of relations){const option=el('option',relationLabel(predicate));option.value=predicate;$('pathPredicate').append(option);}
  if(!workspaceLoaded){
    const requested=new URLSearchParams(location.search).get('view');
    showWorkspaceView(workspaceNames.includes(requested)?requested:'ask',{persist:false});
    workspaceLoaded=true;
  }
  if(location.hash)revealWorkspaceTarget(workspaceHashTarget());
}
function claimLabel(a){return nodeLabel(a.subject)+' → '+relationLabel(a.predicate)+' → '+nodeLabel(a.object)+' ['+a.lifecycle_state+'] · '+a.id;}
function populateSourceGuide(){
  if(!graph)return;
  const query=$('sourceGuideSearch').value.trim().toLowerCase(),selected=$('sourceGuideSelection').value;
  const matches=(graph.assertions||[]).filter(a=>!query||claimLabel(a).toLowerCase().includes(query));
  const shown=matches.slice(0,100);
  $('sourceGuideSelection').replaceChildren();
  for(const a of shown){const option=el('option',claimLabel(a));option.value=a.id;$('sourceGuideSelection').append(option);}
  if(shown.some(a=>a.id===selected))$('sourceGuideSelection').value=selected;
  $('sourceGuideCount').textContent=matches.length+' matching claims. '+(matches.length>100?'Showing the first 100; narrow the search to find another claim.':'');
  $('sourceGuideButton').disabled=!runId||!shown.length;
}
function populatePathEntities(){
  if(!graph)return;
  const query=$('pathEntitySearch').value.trim().toLowerCase();
  const matches=graph.nodes.filter(n=>!query||[n.id,n.name,n.sym,n.symbol].some(v=>typeof v==='string'&&v.toLowerCase().includes(query)));
  const shown=matches.slice(0,300);
  for(const id of ['pathSource','pathTarget']){
    const previous=$(id).value,selected=graph.nodes.find(n=>n.id===previous),items=[...shown];
    if(selected&&!items.some(n=>n.id===previous))items.push(selected);
    $(id).replaceChildren();
    if(id==='pathTarget'){const option=el('option','Any reachable entity');option.value='';$(id).append(option);}
    for(const node of items){const option=el('option',(node.sym||node.name||node.id)+' · '+node.id);option.value=node.id;$(id).append(option);}
    if(items.some(n=>n.id===previous))$(id).value=previous;
  }
  $('pathEntityCount').textContent=matches.length+' matching entities. '+(matches.length>300?'Showing the first 300; narrow the search. Current selections remain available.':'');
}
function guideLink(link){
  const a=el('a',link.label);a.href=link.url;a.target='_blank';a.rel='noopener noreferrer';return a;
}
function fieldList(fields){
  const list=el('dl',undefined,'guide-facts');
  for(const [key,value] of Object.entries(fields||{})){
    list.append(el('dt',key.replaceAll('_',' ')),el('dd',typeof value==='object'?JSON.stringify(value):value??'Not supplied'));
  }
  return list;
}
async function loadSourceGuide(selectionId){
  if(!runId)return;
  showWorkspaceView('evidence');
  const selected=graph.assertions.find(a=>a.id===selectionId);
  if(![...$('sourceGuideSelection').options].some(option=>option.value===selectionId)){
    const option=el('option',selected?claimLabel(selected):'Source observation · '+selectionId);option.value=selectionId;$('sourceGuideSelection').append(option);
  }
  $('sourceGuideSelection').value=selectionId;
  const request=++inspectionRequest,sourceRun=runId,sourceSnapshot=graph.snapshot_sha256;
  $('sourceGuideStatus').textContent='Reading saved source context…';$('sourceGuideOutput').replaceChildren();
  try{
    const result=await api('/api/inspect-source',{run_id:sourceRun,selection_id:selectionId});
    if(request!==inspectionRequest||sourceRun!==runId)return;
    if(result.source_run!==sourceRun||result.snapshot_sha256!==sourceSnapshot||result.selection?.id!==selectionId||result.read_only!==true)throw new Error('Source guide does not match the selected saved evidence.');
    renderSourceGuide(result);
    $('sourceGuideStatus').textContent='Saved-source explanation. No model call, source search or review decision was made.';
  }catch(error){if(request===inspectionRequest)$('sourceGuideStatus').textContent=error.message;}
}
function renderSourceGuide(result){
  const box=$('sourceGuideOutput'),a=result.assertion;
  const heading=a?nodeLabel(a.subject)+' → '+relationLabel(a.predicate)+' → '+nodeLabel(a.object):'Selected source observation';
  box.replaceChildren(el('h4',heading),el('p','Selected record: '+result.selection.id,'small'),el('p',result.summary),el('p',result.review.note,'notice'));
  const recorded=Object.fromEntries(Object.entries(result.qualifiers).filter(([key,value])=>value!==null&&value!==undefined&&key!=='observation_id'));
  if(Object.keys(recorded).length){const facts=el('div',undefined,'source-record');facts.append(el('strong','Conditions recorded on this claim'),fieldList(recorded));box.append(facts);}
  const outcome=result.sections.find(section=>section.title==='Source outcome');
  if(outcome)box.append(el('p',outcome.text,'notice'));
  const columns=el('div',undefined,'guide-layout'),questions=el('div'),sources=el('div');
  const links=new Map(result.links.map(link=>[link.id,link]));
  for(const question of result.questions){
    const card=el('section',undefined,'evidence');card.append(el('h4',question.question),el('p',question.answer));
    for(const id of question.link_ids||[]){const link=links.get(id);if(link){const p=el('p');p.append(guideLink(link));card.append(p);}}
    questions.append(card);
  }
  sources.append(el('h4','Source trail'));
  for(const source of result.source_records){
    const card=el('div',undefined,'source-record');
    card.append(el('strong',(source.source_labels||[]).join(', ')||source.aggregator||'Source label not supplied'),el('p','Reference: '+source.reference_status.replaceAll('_',' ')));
    for(const id of source.link_ids||[]){const link=links.get(id);if(link){const p=el('p');p.append(guideLink(link));card.append(p);}}
    sources.append(card);
  }
  const trail=el('ul');
  for(const link of result.links){const li=el('li');li.append(guideLink(link),document.createTextNode(' · '+link.kind.replaceAll('_',' ')));trail.append(li);}
  sources.append(trail);
  if(result.missing_context.length){sources.append(el('h4','Missing or unresolved context'));for(const gap of result.missing_context)sources.append(el('p',gap.field.replaceAll('_',' ')+': '+gap.note,'small'));}
  columns.append(questions,sources);box.append(columns);
  for(const section of result.sections){const details=el('details');details.append(el('summary',section.title),el('p',section.text),fieldList(section.fields));box.append(details);}
  const qualifiers=el('details');qualifiers.append(el('summary','Preserved claim conditions'),fieldList(result.qualifiers));box.append(qualifiers);
  const limits=el('details');limits.append(el('summary','Scope and interpretation limits'));for(const text of result.limitations)limits.append(el('p',text,'small'));box.append(limits);
}
async function runPathExploration(){
  if(!runId)return;
  const request=++pathRequest,sourceRun=runId,sourceSnapshot=graph.snapshot_sha256;
  $('pathExploreStatus').textContent='Following saved assertions…';$('pathExploreButton').disabled=true;$('pathExploreResults').replaceChildren();
  try{
    const predicate=$('pathPredicate').value;
    const result=await api('/api/explore',{run_id:sourceRun,source:$('pathSource').value,target:$('pathTarget').value||null,max_hops:Number($('pathHops').value),view:$('pathView').value,predicates:predicate?[predicate]:null});
    if(request!==pathRequest||sourceRun!==runId)return;
    if(result.source_run!==sourceRun||result.snapshot_sha256!==sourceSnapshot)throw new Error('Path result belongs to different saved evidence.');
    renderExploration(result);
    $('pathExploreStatus').textContent=result.search.paths_returned+' paths shown. '+(result.search.truncated?'Search stopped at '+result.search.truncation_reason.replaceAll('_',' ')+'. More paths may exist.':'Search complete within the selected bounds.')+' '+result.search.expansions+' assertion expansions.';
  }catch(error){if(request===pathRequest)$('pathExploreStatus').textContent=error.message;}
  finally{if(request===pathRequest)$('pathExploreButton').disabled=false;}
}
function renderExploration(result){
  const box=$('pathExploreResults');box.replaceChildren(el('p',result.interpretation,'notice'));
  if(!result.paths.length)box.append(el('p','No path was returned in this saved scope and evidence view. This does not establish biological absence.'));
  for(const path of result.paths){
    const card=el('details',undefined,'evidence');card.open=result.paths.length===1;
    card.append(el('summary',path.node_ids.map(nodeLabel).join(' → ')+' · '+path.review_status.replaceAll('_',' ')));
    for(const step of path.steps){
      const item=el('div',undefined,'path-step');
      item.append(el('strong',nodeLabel(step.subject)+' → '+relationLabel(step.predicate)+' → '+nodeLabel(step.object)),el('p','Local review: '+step.review_state+(step.traversal_direction==='reverse_symmetric'?' · Traversed in reverse using the saved symmetric flag.':''),'small'));
      if(Object.keys(step.qualifiers).length)item.append(fieldList(step.qualifiers));
      const button=el('button','Inspect source '+step.citation_id,'secondary');button.type='button';button.onclick=()=>{loadSourceGuide(step.assertion_id);$('sourceGuide').scrollIntoView({block:'start'});};item.append(button);card.append(item);
    }
    box.append(card);
  }
  const trace=el('details');trace.append(el('summary','Query bounds, excluded assertions and source binding'),el('pre',JSON.stringify({query:result.query,search:result.search,excluded_assertions:result.excluded_assertions,graph_basis_sha256:result.graph_basis_sha256,snapshot_sha256:result.snapshot_sha256},null,2)));box.append(trace);
}
initializeWorkspaceNavigation();
function invalidateSourceGuide(){inspectionRequest++;$('sourceGuideOutput').replaceChildren();$('sourceGuideStatus').textContent='Selection changed. Open the guide for this source.';}
function invalidateExploration(){pathRequest++;$('pathExploreResults').replaceChildren();$('pathExploreStatus').textContent='Scope changed. Explore paths for the current selections.';$('pathExploreButton').disabled=!runId;}
$('sourceGuideSearch').addEventListener('input',()=>{invalidateSourceGuide();populateSourceGuide();});
$('sourceGuideSelection').addEventListener('change',invalidateSourceGuide);
$('pathEntitySearch').addEventListener('input',()=>{invalidateExploration();populatePathEntities();});
for(const id of ['pathSource','pathTarget','pathHops','pathView','pathPredicate'])$(id).addEventListener('change',invalidateExploration);
$('sourceGuideForm').addEventListener('submit',event=>{event.preventDefault();loadSourceGuide($('sourceGuideSelection').value);});
$('pathExploreForm').addEventListener('submit',event=>{event.preventDefault();runPathExploration();});
$('loadSupportComparators').onclick=async()=>{
  $('supportComparatorStatus').textContent='Checking saved local assessments…';
  try{
    const response=await fetch('/api/support-comparators'),result=await response.json();
    if(!response.ok)throw new Error(result.error||'Could not read saved assessments.');
    const box=$('supportComparatorReports');box.replaceChildren();
    for(const report of result.reports){
      const p=el('p'),link=el('a','Open assessment · '+report.id);link.href=report.url;link.target='_blank';link.rel='noopener noreferrer';
      p.append(link,document.createTextNode(' — '+report.case_count+' development claims; '+report.unique_query_count+' distinct queries; '+report.hosted_model_calls+' hosted calls. Status: '+report.status.replaceAll('_',' ')+'.'));box.append(p);
    }
    $('supportComparatorStatus').textContent=result.reports.length?'These assessments evaluate method fit; they do not report biological accuracy.':'No verified saved comparator preparation is available.';
  }catch(error){$('supportComparatorStatus').textContent=error.message;}
};
// Keep old source-inspection entry points working across task panels.
const originalInspectAssertion=inspectAssertion;
inspectAssertion=function(id){showWorkspaceView('evidence');originalInspectAssertion(id);loadSourceGuide(id);};
const originalInspectAssay=inspectAssay;
inspectAssay=function(row){showWorkspaceView('evidence');originalInspectAssay(row);loadSourceGuide(row.id);};
