// Task panels retain the existing DOM, source passports and review handlers.
// Tab semantics follow WAI-ARIA APG; no new UI framework or graph store is needed.
const workspaceNames=['data','ask','evidence','compare','export'];
const workspaceSuffix={data:'Data',ask:'Ask',evidence:'Evidence',compare:'Compare',export:'Export'};
let workspaceView='data',workspaceLoaded=false,inspectionRequest=0,pathRequest=0;
let neptuneRequest=0,neptuneStatusRequest=0,neptuneConfigured=false;
let editableCopyRequest=0,editableCopyState=null;
function workspaceHashTarget(){try{return $(decodeURIComponent(location.hash.slice(1)));}catch(_){return null;}}
function initializeWorkspaceAssessments(){
  initializeScientificAssessments();
  if(savedReviewOnly())return;
  initializePruningPreview();
  initializeBiologicalComparisons();
  initializeFunctionContexts();
}
function showWorkspaceView(name,{focus=false,persist=true,scroll=false}={}){
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
  if(scroll)$('workspace'+workspaceSuffix[name]).scrollIntoView({block:'start'});
}
function revealWorkspaceTarget(target){
  if(!target)return false;
  if(savedReviewOnly()&&target.closest('[data-development-view]'))return false;
  let ancestor=target.closest('details');while(ancestor){ancestor.open=true;ancestor=ancestor.parentElement?.closest('details');}
  const panel=target.closest('[data-workspace-panel]');
  if(panel)showWorkspaceView(panel.dataset.workspacePanel);
  return true;
}
function initializeWorkspaceNavigation(){
  const move=(id,view)=>{const item=$(id);if(item)$('workspace'+workspaceSuffix[view]).append(item);};
  for(const key of workspaceNames)$('workspace'+workspaceSuffix[key]).dataset.workspacePanel=key;
  for(const id of ['savedWorkPanel','constructionPublication'])$('otherSavedExamples').append($(id));
  move('controls','data');
  const scopeRow=$('diseaseTitle')?.closest('.row');if(scopeRow)$('workspaceProvenance').append(scopeRow);
  if($('stats'))$('workspaceProvenance').append($('stats'));
  for(const id of ['answerNavigation','workspaceQuestionChoice','plannerPanel','guidedQuestion','civicQuestion'])move(id,'ask');
  // Put broad exploration after the existing focused question flow.
  const advanced=el('details',undefined,'card');advanced.id='advancedPathExploration';advanced.append(el('summary','Explore paths in this saved graph'));advanced.append($('pathExplorer'));$('workspaceAsk').append(advanced);
  for(const id of ['assayPanel','inspectionDetails'])move(id,'evidence');
  for(const id of ['functionContextPanel','biologicalComparisonPanel','supportComparatorPanel','benchmarkPanel','refreshPanel']){const item=$(id);if(item)$('comparisonResearchHistory').append(item);}
  $('comparisonPruningControls').append($('pruningPreviewPanel'));
  if(savedReviewOnly())$('savedWorkspaceSummary').textContent='Saved workspaces and source versions';
  move('submissionPanel','export');
  for(const id of ['downloadJson','downloadZip'])$('workspaceDownloads').append($(id));
  $('workspaceContext').append($('results'));
  const tabs=workspaceNames.map(key=>$('workspaceTab'+workspaceSuffix[key]));
  for(const button of tabs){
    button.onclick=()=>showWorkspaceView(button.dataset.workspace,{scroll:true});
    button.addEventListener('keydown',event=>{
      const enabled=tabs.filter(tab=>!tab.disabled),index=enabled.indexOf(button);
      let next;
      if(event.key==='ArrowRight')next=enabled[(index+1)%enabled.length];
      if(event.key==='ArrowLeft')next=enabled[(index+enabled.length-1)%enabled.length];
      if(event.key==='Home')next=enabled[0];
      if(event.key==='End')next=enabled[enabled.length-1];
      if(next){event.preventDefault();showWorkspaceView(next.dataset.workspace,{focus:true,scroll:true});}
    });
  }
  const followHash=()=>{const target=workspaceHashTarget();if(target&&revealWorkspaceTarget(target)&&target.tagName==='DETAILS')target.open=true;};
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
  if(typeof reviewerQualificationSummary!=='undefined')reviewerQualificationSummary=null;
  inspectionRequest++;pathRequest++;
  for(const key of ['ask','evidence','export'])$('workspaceTab'+workspaceSuffix[key]).disabled=false;
  $('sourceGuideOutput').replaceChildren();$('pathExploreResults').replaceChildren();
  for(const [status,output] of [['sourceGuideStatus','sourceGuideOutput'],['pathExploreStatus','pathExploreResults']]){$(status).setAttribute('data-loading','false');$(output).setAttribute('aria-busy','false');}
  $('sourceGuideStatus').textContent='Select a claim or choose Inspect source on a path.';
  $('pathExploreStatus').textContent='Searches this saved graph only. No source retrieval or model call is made.';
  $('sourceGuideButton').disabled=!runId;$('pathExploreButton').disabled=!runId;
  $('sourceGuideSearch').value='';populateSourceGuide();
  if(typeof updateReviewWorkflow==='function')updateReviewWorkflow();
  setupEditableCopyDownload();
  if(!savedReviewOnly())setupNeptune();
  setupNativeGoa();
  const relations=[...new Set((graph.assertions||[]).map(a=>a.predicate))].sort();
  $('pathPredicate').replaceChildren(el('option','All saved relationship types'));$('pathPredicate').options[0].value='';
  for(const predicate of relations){const option=el('option',relationLabel(predicate));option.value=predicate;$('pathPredicate').append(option);}
  $('pathEntitySearch').value='';$('pathTargetSearch').value='';$('pathSource').value='';$('pathTarget').value='';
  $('pathView').value='candidates';populatePathEntities();
  if(!workspaceLoaded){
    const requested=new URLSearchParams(location.search).get('view');
    showWorkspaceView(workspaceNames.includes(requested)?requested:'ask',{persist:false});
    workspaceLoaded=true;
  }
  if(location.hash)revealWorkspaceTarget(workspaceHashTarget());
  if(typeof updateReviewerHome==='function')updateReviewerHome();
}
function claimLabel(a){return nodeLabel(a.subject)+' → '+relationLabel(a.predicate)+' → '+nodeLabel(a.object)+' ['+a.lifecycle_state+'] · '+a.id;}
function populateSourceGuide(){
  if(!graph)return;
  const query=$('sourceGuideSearch').value.trim().toLowerCase(),selected=$('sourceGuideSelection').value;
  const matches=(graph.assertions||[]).filter(a=>!query||[claimLabel(a),a.subject,a.predicate,a.object].some(v=>typeof v==='string'&&v.toLowerCase().includes(query)));
  const shown=matches.slice(0,100);
  $('sourceGuideSelection').replaceChildren();
  for(const a of shown){const option=el('option',claimLabel(a));option.value=a.id;$('sourceGuideSelection').append(option);}
  if(shown.some(a=>a.id===selected))$('sourceGuideSelection').value=selected;
  $('sourceGuideCount').textContent=matches.length+' matching claims. '+(matches.length>100?'Showing the first 100; narrow the search to find another claim.':'');
  $('sourceGuideButton').disabled=!runId||!shown.length;
}
function populatePathEntities(){
  if(!graph)return;
  const index=pathNavigationIndex(),scope=pathNavigationScope(index),query=$('pathEntitySearch').value.trim().toLowerCase();
  const matches=[...scope.adjacency.keys()].map(id=>index.nodes.get(id)).filter(node=>pathNodeMatches(node,query)).sort(pathNodeOrder);
  const shown=matches.slice(0,300),previous=$('pathSource').value;
  $('pathSource').replaceChildren();
  for(const node of shown){const option=el('option',pathNodeLabel(node));option.value=node.id;$('pathSource').append(option);}
  const selected=shown.find(node=>node.id===previous)||shown[0];$('pathSource').value=selected?.id||'';
  $('pathSource').disabled=!shown.length;
  if(previous!==$('pathSource').value){$('pathTargetSearch').value='';$('pathTarget').value='';}
  $('pathEntityCount').textContent=!scope.adjacency.size?($('pathView').value==='accepted'?'No starting entities have locally accepted assertions in this scope. Choose Candidates and accepted to inspect unreviewed evidence.':'No starting entities have eligible outgoing assertions under these filters.'):
    matches.length+' matching starting '+(matches.length===1?'entity':'entities')+'. Proteins first, then name. '+(matches.length>300?'Showing the first 300; keep typing to narrow the list.':'');
  const reachable=pathReachableEntities(scope.adjacency,selected?.id,Number($('pathHops').value)||2),targetQuery=$('pathTargetSearch').value.trim().toLowerCase();
  const endpoints=[...reachable.ids].map(id=>index.nodes.get(id)).filter(node=>pathNodeMatches(node,targetQuery)).sort(pathNodeOrder),endShown=endpoints.slice(0,300),oldTarget=$('pathTarget').value;
  $('pathTarget').replaceChildren();const any=el('option',targetQuery?'Choose a matching reachable entity':'Any reachable entity');any.value='';$('pathTarget').append(any);
  for(const node of endShown){const option=el('option',pathNodeLabel(node));option.value=node.id;$('pathTarget').append(option);}
  $('pathTarget').value=endShown.some(node=>node.id===oldTarget)?oldTarget:(targetQuery?endShown[0]?.id||'':'');
  $('pathTarget').disabled=!endShown.length;
  $('pathTargetCount').textContent=endpoints.length+' matching reachable '+(endpoints.length===1?'entity':'entities')+' within '+$('pathHops').value+' '+($('pathHops').value==='1'?'connection':'connections')+'. '+(endpoints.length>300?'Showing the first 300; keep typing to narrow the list. ':'')+(reachable.truncated?'Suggestions stop at the 2,000-expansion search bound; other routes may exist.':'Only recorded routes in the current evidence view are suggested.');
  $('pathExploreButton').disabled=!runId||!selected||(!!targetQuery&&!endShown.length);
  renderPathExamples(index);
}
let pathNavigationGraph=null,pathNavigationCache=null;
function pathNodeLabel(node){return (node.sym||node.symbol||node.name||node.id)+' · '+node.id;}
function pathNodeMatches(node,query){return !query||[node.id,node.name,node.sym,node.symbol].some(value=>typeof value==='string'&&value.toLowerCase().includes(query));}
function pathNodeOrder(a,b){return Number(b.category==='biolink:Protein')-Number(a.category==='biolink:Protein')||pathNodeLabel(a).localeCompare(pathNodeLabel(b),undefined,{sensitivity:'base',numeric:true})||a.id.localeCompare(b.id);}
function pathNavigationIndex(){
  if(pathNavigationGraph===graph&&pathNavigationCache)return pathNavigationCache;
  const nodes=new Map((graph.nodes||[]).map(node=>[node.id,node])),edges=new Map((graph.edges||[]).map(edge=>[edge.id,edge]));
  // This previews exploration.py's existing source/review policy for selectors.
  // The backend still validates and performs every submitted path query.
  const assertions=(graph.assertions||[]).filter(assertion=>{
    if(!['candidate','provisional','accepted'].includes(assertion.lifecycle_state)||assertion.subject===assertion.object||!nodes.has(assertion.subject)||!nodes.has(assertion.object))return false;
    const ids=assertion.structurally_usable_evidence_ids;if(!Array.isArray(ids)||ids.some(id=>!edges.has(id)))return false;
    const evidence=[...new Set(ids)].map(id=>edges.get(id)).filter(edge=>edge.status==='passed_structural_checks');
    return evidence.length>0&&evidence.every(edge=>edge.subject===assertion.subject&&edge.object===assertion.object&&edge.predicate===assertion.predicate&&pathQualifierKey(edge.qualifiers||{})===pathQualifierKey(assertion.qualifiers||{}));
  });
  pathNavigationGraph=graph;pathNavigationCache={nodes,assertions};return pathNavigationCache;
}
function pathQualifierKey(value){
  const sorted=item=>Array.isArray(item)?item.map(sorted):item&&typeof item==='object'?Object.fromEntries(Object.keys(item).sort().map(key=>[key,sorted(item[key])])):item;
  return JSON.stringify(sorted(Object.fromEntries(Object.entries(value).filter(([,item])=>item!==null))));
}
function pathRawOrder(a,b){return a<b?-1:a>b?1:0;}
function pathNavigationScope(index){
  const adjacency=new Map(),accepted=$('pathView').value==='accepted',predicate=$('pathPredicate').value;
  const add=(from,to,id)=>{if(!adjacency.has(from))adjacency.set(from,[]);adjacency.get(from).push({to,id});};
  for(const assertion of index.assertions){
    if((accepted&&assertion.lifecycle_state!=='accepted')||(predicate&&assertion.predicate!==predicate))continue;
    add(assertion.subject,assertion.object,assertion.id);
    if(assertion.symmetric===true&&assertion.subject!==assertion.object)add(assertion.object,assertion.subject,assertion.id);
  }
  for(const rows of adjacency.values())rows.sort((a,b)=>pathRawOrder(a.to,b.to)||pathRawOrder(a.id,b.id));
  return {adjacency};
}
function pathReachableEntities(adjacency,source,hops){
  const ids=new Set(),queue=source?[[source]]:[];let cursor=0,expansions=0,truncated=false;
  while(cursor<queue.length&&!truncated){
    const route=queue[cursor++];
    for(const {to} of adjacency.get(route.at(-1))||[]){
      if(expansions>=2000){truncated=true;break;}expansions++;
      if(route.includes(to))continue;
      ids.add(to);if(route.length<hops)queue.push([...route,to]);
    }
  }
  return {ids,truncated};
}
function pathExampleQueries(index){
  const families=[['Recorded protein association',a=>a.kind==='protein_interaction','UniProtKB:P01116'],['GO annotation',a=>['native_go_annotation','go_annotation'].includes(a.kind),'UniProtKB:P04637'],['Pathway membership',a=>a.kind==='pathway_membership','UniProtKB:P15056']];
  return families.map(([label,include,preferred])=>{
    const choices=index.assertions.filter(include).map(a=>({a,source:a.object===preferred&&a.symmetric===true?a.object:a.subject,target:a.object===preferred&&a.symmetric===true?a.subject:a.object}));
    choices.sort((x,y)=>Number(y.source===preferred)-Number(x.source===preferred)||Number(y.target==='UniProtKB:Q9Y5S2')-Number(x.target==='UniProtKB:Q9Y5S2')||Number(y.target==='GO:0005634')-Number(x.target==='GO:0005634')||Number(!!y.a.qualifiers?.evidence_type?.includes('native_physical'))-Number(!!x.a.qualifiers?.evidence_type?.includes('native_physical'))||pathNodeOrder(index.nodes.get(x.target),index.nodes.get(y.target))||x.a.id.localeCompare(y.a.id));
    const chosen=choices[0];return chosen?{label,source:chosen.source,target:chosen.target,predicate:chosen.a.predicate,assertion_id:chosen.a.id}:null;
  }).filter(Boolean);
}
function renderPathExamples(index){
  const box=$('pathExamples');if(!box)return;box.replaceChildren();
  const examples=pathExampleQueries(index);if(!examples.length)return;
  box.append(el('p','Try a route that is present in this saved workspace. Examples include candidates, use one connection and show the underlying source records. They do not imply a biological mechanism.'));
  const list=el('div',undefined,'reviewer-examples');
  for(const example of examples){
    const button=el('button',pathNodeLabel(index.nodes.get(example.source)).split(' · ')[0]+' → '+pathNodeLabel(index.nodes.get(example.target)).split(' · ')[0]+' · '+example.label,'secondary');button.type='button';
    button.onclick=()=>{invalidateExploration();$('pathEntitySearch').value=example.source;$('pathTargetSearch').value='';$('pathView').value='candidates';$('pathPredicate').value=example.predicate;$('pathHops').value='1';populatePathEntities();$('pathTarget').value=example.target;runPathExploration();};
    list.append(button);
  }
  box.append(list);
}
function populateNeptuneNodes(){
  if(!graph)return;
  const query=$('neptuneNodeSearch').value.trim().toLowerCase(),previous=$('neptuneNode').value;
  const matches=graph.nodes.filter(node=>!query||[node.id,node.name,node.sym].some(value=>typeof value==='string'&&value.toLowerCase().includes(query)));
  const shown=matches.slice(0,300),selected=graph.nodes.find(node=>node.id===previous);
  if(selected&&!shown.some(node=>node.id===previous))shown.push(selected);
  $('neptuneNode').replaceChildren();
  for(const node of shown){const option=el('option',(node.sym||node.name||node.id)+' · '+node.id);option.value=node.id;$('neptuneNode').append(option);}
  if(shown.some(node=>node.id===previous))$('neptuneNode').value=previous;
  $('neptuneNodeCount').textContent=matches.length+' matching entities. '+(matches.length>300?'Showing the first 300; narrow the search. Current selection remains available.':'');
  $('neptuneRead').disabled=!runId||!neptuneConfigured||!shown.length;
}
async function setupNeptune(){
  const request=++neptuneStatusRequest,sourceRun=runId;
  neptuneRequest++;
  neptuneConfigured=false;$('neptuneOutput').replaceChildren();$('neptuneNodeSearch').value='';populateNeptuneNodes();
  $('neptuneWorkspace').textContent='Current saved workspace: '+(sourceRun||'not saved')+' · '+graph.nodes.length+' entities · '+graph.edges.length+' evidence records';
  if(!sourceRun){$('neptuneStatus').textContent='Open a saved workspace in the app to use Neptune.';return;}
  $('neptuneStatus').textContent='Checking Neptune configuration…';
  try{
    const response=await fetch('/api/neptune-status'),value=await response.json();
    if(!response.ok)throw new Error(value.error||'Neptune configuration could not be read.');
    if(request!==neptuneStatusRequest||sourceRun!==runId)return;
    neptuneConfigured=value.configured===true&&value.backend==='neptune';populateNeptuneNodes();
    $('neptuneStatus').textContent=neptuneConfigured?'Neptune configured. Select an entity to verify and read its evidence.':'Neptune is not configured for this workspace.';
  }catch(error){if(request===neptuneStatusRequest)$('neptuneStatus').textContent=error.message;}
}
function invalidateNeptuneSelection(){
  neptuneRequest++;$('neptuneOutput').replaceChildren();
  $('neptuneRead').disabled=!runId||!neptuneConfigured||!$('neptuneNode').value;
  if(neptuneConfigured)$('neptuneStatus').textContent='Selection changed. Read Neptune to inspect this entity.';
}
async function readNeptuneSelection(){
  if(!runId||!neptuneConfigured)return;
  const request=++neptuneRequest,sourceRun=runId,sourceSnapshot=graph.snapshot_sha256,nodeId=$('neptuneNode').value;
  $('neptuneRead').disabled=true;$('neptuneOutput').replaceChildren();$('neptuneStatus').textContent='Verifying the saved graph in Neptune and reading selected evidence…';
  try{
    const result=await api('/api/neptune-inspect',{run_id:sourceRun,node_id:nodeId,limit:Number($('neptuneLimit').value)});
    if(request!==neptuneRequest||sourceRun!==runId)return;
    if(result.backend!=='neptune'||result.source_run!==sourceRun||result.snapshot_sha256!==sourceSnapshot||result.node_id!==nodeId||result.read_only!==true||!result.full_parity_verified_at)throw new Error('Neptune result does not match this saved workspace and entity.');
    const box=$('neptuneOutput');
    box.append(el('p','Read from AWS Neptune · full source parity verified '+result.full_parity_verified_at,'notice'),
      el('p','Dataset: '+result.dataset_id,'small'),el('p',result.edges.length+' evidence records and '+result.assertions.length+' qualified claims returned.'+(result.truncated?' The record limit was reached; increase it to inspect more.':'')));
    for(const guide of result.source_guides||[]){
      const card=el('section',undefined,'evidence');card.append(el('p',guide.summary),el('p','Local review state: '+guide.review.state,'small'));
      const button=el('button','Inspect complete saved source','secondary');button.type='button';button.onclick=()=>{loadSourceGuide(guide.selection.id);$('sourceGuide').scrollIntoView({block:'start'});};card.append(button);
      for(const link of (guide.links||[]).filter(link=>['publication','source_record'].includes(link.kind)).slice(0,2)){const line=el('p');line.append(guideLink(link));card.append(line);}
      box.append(card);
    }
    if(result.guides_omitted)box.append(el('p','Showing the first three source guides. Other returned claims remain available through Guided source inspection.','small'));
    if(!result.edge_ids.length)box.append(el('p','No incident evidence records for this entity in the saved workspace.','small'));
    $('neptuneStatus').textContent='Neptune read verified. Source qualifications and review states were preserved.';
  }catch(error){if(request===neptuneRequest)$('neptuneStatus').textContent=error.message;}
  finally{if(request===neptuneRequest)$('neptuneRead').disabled=!neptuneConfigured||!$('neptuneNode').value;}
}
function guideLink(link){
  const a=el('a',link.label);a.href=link.url;a.target='_blank';a.rel='noopener noreferrer';return a;
}
function fieldList(fields){
  const list=el('dl',undefined,'guide-facts');
  const rows=Array.isArray(fields)?fields:Object.entries(fields||{}).map(([key,value])=>({label:key.replaceAll('_',' '),value}));
  const valueText=value=>{
    if(value===null||value===undefined)return 'Not supplied';
    if(typeof value!=='object')return String(value);
    if(!Array.isArray(value)){
      const label=typeof value.label==='string'?value.label:typeof value.name==='string'?value.name:null;
      if(label)return label+(value.id!==null&&value.id!==undefined?' ('+String(value.id)+')':'');
    }
    return JSON.stringify(value,null,2);
  };
  for(const field of rows){
    const value=field.value,description=el('dd');
    const nativeField=!Array.isArray(fields);
    const technicalLabels={
      'mapping proof':['Protein identity records','Expand the recorded value for exact aliases, sequences and checksums.'],
      'complete source files':['Preserved source files','Expand the recorded value for source URLs, paths and checksums.'],
      'all source channels':['Recorded source channels','Expand the recorded value for the complete source fields.']
    };
    if(nativeField&&Object.hasOwn(technicalLabels,field.label)&&value!==null&&typeof value==='object'){
      const [label,note]=technicalLabels[field.label];description.append(el('span',label+': '+Object.keys(value).length+'. '+note));
    }else if(nativeField&&field.label==='native scores'&&value!==null&&!Array.isArray(value)&&typeof value==='object'&&Object.values(value).every(v=>v===null||typeof v!=='object')){
      const scores=Object.entries(value);
      if(scores.length){
        const items=el('ul');for(const [key,score] of scores)items.append(el('li',key.replaceAll('_',' ')+': '+valueText(score)));description.append(items);
        description.append(el('p','These are recorded source scores, not probabilities that a biological claim is true.','small'));
      }else description.append(el('span','No source scores supplied'));
    }else if(Array.isArray(value)){
      if(!value.length)description.append(el('span','No values supplied'));
      else{const items=el('ul');for(const item of value)items.append(el('li',valueText(item)));description.append(items);}
    }else description.append(el('span',valueText(value)));
    // Readable labels never replace the original value, grouping or source locator.
    if(Array.isArray(fields)||value!==null&&typeof value==='object'){
      const raw=el('details');raw.append(el('summary',Array.isArray(fields)?'Original source field':'Complete recorded value'));
      if(Array.isArray(field.columns))raw.append(el('p','Source columns: '+field.columns.join(', '),'small'));
      raw.append(el('pre',JSON.stringify(Array.isArray(fields)?field:value,null,2)));description.append(raw);
    }
    list.append(el('dt',field.label??'Source field'),description);
  }
  return list;
}
function nativeGoEvidenceHelp(code){
  // Factual code meanings from the GO Consortium guide; never a truth score.
  const labels={EXP:'Experiment',IDA:'Direct assay',IPI:'Physical interaction',IMP:'Mutant phenotype',
    IGI:'Genetic interaction',IEP:'Expression pattern',HTP:'High-throughput experiment',
    HDA:'High-throughput assay',HMP:'High-throughput mutant phenotype',HGI:'High-throughput genetic interaction',
    HEP:'High-throughput expression pattern',IBA:'Ancestor-based phylogenetic inference',
    IBD:'Descendant-based phylogenetic inference',IKR:'Key-residue inference',IRD:'Rapid-divergence inference',
    ISS:'Sequence or structure similarity',ISO:'Sequence orthology',ISA:'Sequence alignment',
    ISM:'Sequence model',IGC:'Genomic context',RCA:'Reviewed computational analysis',
    TAS:'Traceable author statement',NAS:'Non-traceable author statement',IC:'Curator inference',
    ND:'No biological data available',IEA:'Electronic annotation'};
  let note='The code describes the support method; it is not a confidence score. Read the reference, polarity and recorded conditions.';
  if(code==='IPI')note='Inspect With/from and the reference for the interacting entity and assay. This code alone does not establish direct binding.';
  else if(code==='IEA')note='Automatically assigned rather than individually reviewed. Inspect the recorded method or signature; several resources can reuse the same inference.';
  else if(['HTP','HDA','HMP','HGI','HEP'].includes(code))note='A high-throughput method supported this annotation. Inspect the study and conditions; the code does not establish a separate targeted validation.';
  else if(code==='ND')note='The source records a knowledge gap. This does not mean the protein lacks a biological function.';
  const box=el('details');box.append(el('summary',code+' — '+(Object.hasOwn(labels,code)?labels[code]:'Meaning not listed in this guide')),el('p',note,'small'));
  const source=el('p');source.append(guideLink({label:'Official evidence-code guide',url:'https://geneontology.org/docs/guide-go-evidence-codes/'}));box.append(source);
  return box;
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
  $('sourceGuideStatus').textContent='Reading saved source context…';$('sourceGuideStatus').setAttribute('data-loading','true');$('sourceGuideOutput').setAttribute('aria-busy','true');$('sourceGuideOutput').replaceChildren();
  try{
    const result=await api('/api/inspect-source',{run_id:sourceRun,selection_id:selectionId});
    if(request!==inspectionRequest||sourceRun!==runId)return;
    if(result.source_run!==sourceRun||result.snapshot_sha256!==sourceSnapshot||result.selection?.id!==selectionId||result.read_only!==true)throw new Error('Source guide does not match the selected saved evidence.');
    renderSourceGuide(result);
    $('sourceGuideStatus').textContent='Saved-source explanation. No model call, source search or review decision was made.';
  }catch(error){if(request===inspectionRequest)$('sourceGuideStatus').textContent=error.message;}
  finally{if(request===inspectionRequest&&sourceRun===runId){$('sourceGuideStatus').setAttribute('data-loading','false');$('sourceGuideOutput').setAttribute('aria-busy','false');}}
}
function editableCopySize(bytes){return (bytes/1000000).toFixed(1)+' MB';}
function editableCopyLink(copy){
  const link=el('a','Download an editable local copy ('+editableCopySize(copy.bytes)+')','download-action');
  link.href=copy.download_url;link.download=copy.filename;
  link.setAttribute('aria-label','Download an editable local copy of this workspace, '+editableCopySize(copy.bytes));
  return link;
}
function renderEditableCopyDownload(){
  const quick=$('workspaceEditableCopy'),panel=$('editableCopyExport');if(!quick||!panel)return;
  quick.replaceChildren();panel.replaceChildren();quick.hidden=true;panel.hidden=true;
  const state=editableCopyState;if(!state||state.run_id!==runId)return;
  if(state.status==='available'){
    quick.hidden=false;quick.append(editableCopyLink(state.copy));
    quick.append(el('span',' Includes the app, the full saved workspace, attached source records, its demonstration question and local launch instructions.','small'));
    panel.hidden=false;panel.append(el('h3','Continue working with your own copy'),editableCopyLink(state.copy));
    panel.append(el('p','This complete package opens the same saved evidence on your computer. Local editing records evidence-review decisions and reasons. Each review saves a new run and preserves the original.'));
    panel.append(el('p','Extract the ZIP into a new folder. With Python 3.10 or newer, run:'));
    panel.append(el('pre','python3 START_EDITABLE_LOCAL.py'));
    panel.append(el('p','Open the address printed in the terminal. Under Inspect sources, choose a claim and Record evidence review. Enter Reviewer, Decision and Reason, then choose Save review in a new run. No model, AWS account or new data retrieval is needed.','small'));
    const verification=el('details');verification.append(el('summary','Download identity'),el('p','Workspace: '+state.run_id,'small'),el('pre','SHA-256: '+state.copy.sha256));panel.append(verification);
  }else if(savedReviewOnly()){
    panel.hidden=false;panel.append(el('h3','Continue working locally'));
    const message=state.status==='checking'?'Checking for a complete editable copy…':state.status==='error'?'The local-copy download could not be verified. Reopen this workspace to check again.':'A complete editable copy is not available for this selected workspace. Use a separately supplied complete source workspace with the local app.';
    const note=el('p',message,'small');note.setAttribute('role','status');note.setAttribute('aria-live','polite');note.setAttribute('aria-atomic','true');note.setAttribute('data-loading',String(state.status==='checking'));panel.append(note);
  }
}
async function setupEditableCopyDownload(){
  const request=++editableCopyRequest,sourceRun=runId,sourceGraph=graph,sourceSnapshot=graph?.snapshot_sha256;
  if(!$('workspaceEditableCopy')||!$('editableCopyExport'))return;
  editableCopyState=sourceRun?{status:'checking',run_id:sourceRun}:null;renderEditableCopyDownload();
  if(!sourceRun)return;
  const current=()=>request===editableCopyRequest&&sourceRun===runId&&sourceGraph===graph&&sourceSnapshot===graph?.snapshot_sha256;
  try{
    const response=await fetch('/api/editable-copy/'+encodeURIComponent(sourceRun)),copy=await response.json();
    if(!current())return;
    if(!response.ok)throw new Error('Complete copy metadata could not be verified.');
    if(copy.run_id!==sourceRun||typeof copy.available!=='boolean')throw new Error('Complete copy belongs to a different workspace.');
    if(!copy.available){editableCopyState={status:'unavailable',run_id:sourceRun};renderEditableCopyDownload();return;}
    const expected='/api/editable-copy/'+encodeURIComponent(sourceRun)+'/download';
    if(copy.download_url!==expected||!Number.isSafeInteger(copy.bytes)||copy.bytes<=0||
       typeof copy.filename!=='string'||!/^[-A-Za-z0-9_.]+\.zip$/.test(copy.filename)||
       typeof copy.sha256!=='string'||!/^[0-9a-f]{64}$/.test(copy.sha256)||
       typeof copy.source_graph_sha256!=='string'||!/^[0-9a-f]{64}$/.test(copy.source_graph_sha256)||
       copy.snapshot_sha256!==sourceSnapshot||copy.requires?.model!==false||copy.requires?.AWS!==false)
      throw new Error('Complete copy metadata is incomplete or does not match this workspace.');
    editableCopyState={status:'available',run_id:sourceRun,copy};renderEditableCopyDownload();
  }catch(error){if(current()){editableCopyState={status:'error',run_id:sourceRun};renderEditableCopyDownload();}}
}
function reviewWorkspaceMode(){
  if(savedReviewOnly())return {editable:false,message:'Read-only example. You can inspect source records, recorded decisions and agent proposals here. To record your own evidence review, open a complete saved source workspace in the local app. Saving a review creates a new run and preserves the earlier one.'};
  if(graph?.qualified_view)return {editable:false,message:'This applied retained-graph view is read-only. Its original baseline and decision ledger are preserved. Review an ordinary source workspace in the local app, then publish a new decision view.'};
  if(!runId)return {editable:false,message:'This exported report is read-only. Open the complete ordinary workspace in the running local app to record a review as a new run.'};
  return {editable:true,message:'Reviews save as a new run. Inspect a source claim, choose Record evidence review, then enter Reviewer, Decision and Reason. Save review in a new run creates your reviewed copy and preserves the earlier run and sources.'};
}
function updateReviewWorkflow(){
  const mode=reviewWorkspaceMode(),notice=$('workspaceReviewMode'),help=$('localReviewHelp');
  if(notice){notice.hidden=false;notice.textContent=mode.message;}
  if(help)help.hidden=mode.editable;
}
function openEvidenceReview(assertionId){
  if(!reviewWorkspaceMode().editable)return false;
  const assertion=(graph.assertions||[]).find(row=>row.id===assertionId);
  if(!assertion)return false;
  const target=$('inspectionDetails');
  if(typeof revealWorkspaceTarget==='function'&&!revealWorkspaceTarget(target))return false;
  target.open=true;$('evidenceView').value='inspection';$('assertionFamily').value=assertion.kind;
  const proteins=$('assertionProtein');proteins.value=[...proteins.options].some(option=>option.value===assertion.subject)?assertion.subject:'all';
  tablePage=0;activeTab='assertions';
  document.querySelectorAll('.tab').forEach(button=>button.classList.toggle('active',button.dataset.tab==='assertions'));
  render();inspectAssertion(assertionId);
  const form=$('evidenceReviewForm');if(!form)return false;
  form.scrollIntoView({block:'start'});form.focus({preventScroll:true});return true;
}
function sourceReviewControls(assertionId){
  const mode=reviewWorkspaceMode(),box=el('section',undefined,'evidence');
  const sourceRun=runId,sourceSnapshot=graph?.snapshot_sha256;
  const note=el('p',mode.message,'small');note.id='sourceReviewModeNote';
  box.append(el('h4','Record an evidence review'),note);
  const button=el('button','Record evidence review','secondary review-action');button.type='button';button.disabled=!mode.editable;button.setAttribute('aria-describedby',note.id);
  button.onclick=()=>{if(sourceRun!==runId||sourceSnapshot!==graph?.snapshot_sha256){$('sourceGuideStatus').textContent='The workspace changed. Reopen this claim before recording a review.';return;}openEvidenceReview(assertionId);};box.append(button);
  if(!mode.editable){const help=el('button','How to review an editable local copy','secondary');help.type='button';help.onclick=()=>{const target=$('localReviewHelp');if(!target)return;target.hidden=false;target.open=true;target.scrollIntoView({block:'start'});};box.append(document.createTextNode(' '),help);}
  return box;
}
function renderSourceGuide(result){
  const box=$('sourceGuideOutput'),a=result.assertion;
  const heading=a?nodeLabel(a.subject)+' → '+relationLabel(a.predicate)+' → '+nodeLabel(a.object):'Selected source observation';
  box.replaceChildren(el('h4',heading),el('p','Selected record: '+result.selection.id,'small'),el('p',result.summary),el('p',result.review.note,'notice'));
  if(a)box.append(sourceReviewControls(a.id));
  const recorded=Object.fromEntries(Object.entries(result.qualifiers).filter(([key,value])=>value!==null&&value!==undefined&&key!=='observation_id'));
  if(Object.keys(recorded).length){const facts=el('div',undefined,'source-record');facts.append(el('strong','Conditions recorded on this claim'),fieldList(recorded));box.append(facts);}
  if(result.native_go_context?.configured===true&&result.native_go_context?.eligible===true)box.append(nativeGoContextPanel(result));
  if(result.protein_context?.status==='unverifiable_saved_context')box.append(el('p','The optional saved protein context could not be verified. The original source remains available below.','small'));
  if(typeof window!=='undefined'&&window.ProteinContext){
    const sourceRun=runId,sourceSnapshot=graph?.snapshot_sha256,request=inspectionRequest,selectionId=result.selection.id;
    const context=window.ProteinContext.panel(result,{api,labelForProtein:nodeLabel,
      isCurrent:()=>Boolean(sourceRun&&sourceSnapshot)&&request===inspectionRequest&&sourceRun===runId&&sourceSnapshot===graph?.snapshot_sha256&&$('sourceGuideSelection').value===selectionId});
    if(context)box.append(context);
  }
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
    card.append(el('strong','Source record'),
      el('p','Retrieved through: '+(source.aggregator||'Not supplied')),
      el('p','Source labels supplied: '+((source.source_labels||[]).join(', ')||'Not supplied')),
      el('p','Reference: '+source.reference_status.replaceAll('_',' ')));
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
function nativeGoContextPanel(guide){
  const panel=el('section',undefined,'evidence'),button=el('button','Inspect preserved native GO annotations','secondary'),status=el('p','Read the separately preserved native annotation source for this exact protein and GO term.','small'),output=el('div');
  button.type='button';status.setAttribute('role','status');
  panel.append(el('h4','Separate native GO source context'),status,button,output);
  button.onclick=async()=>{
    const request=inspectionRequest,sourceRun=runId,sourceSnapshot=graph?.snapshot_sha256,selectionId=guide.selection.id;
    const current=()=>Boolean(sourceRun&&sourceSnapshot)&&request===inspectionRequest&&sourceRun===runId&&sourceSnapshot===graph?.snapshot_sha256&&$('sourceGuideSelection').value===selectionId;
    if(!current())return;
    button.disabled=true;output.replaceChildren();status.textContent='Verifying preserved native GO source bytes…';
    try{
      const result=await api('/api/native-go-context',{run_id:sourceRun,selection_id:selectionId});
      if(!current())return;
      if(result.format!=='biograph-steward.native-go-selection.v1'||result.source_run!==sourceRun||result.selection_id!==selectionId||result.snapshot_sha256!==sourceSnapshot||result.read_only!==true||!Array.isArray(result.records)||result.record_count!==result.records.length||result.query?.protein!==guide.assertion?.subject||result.query?.go_id!==guide.assertion?.object)throw new Error('Preserved native GO context does not match this selected saved claim.');
      renderNativeGoContext(result,output);
      status.textContent=result.record_count+' preserved native annotations shown. Historical Pharos record identity remains unresolved; no graph or review was changed.';
    }catch(error){if(current())status.textContent='Native GO context remains unresolved: '+error.message;}
    finally{if(current())button.disabled=false;}
  };
  return panel;
}
function nativeGoReference(identifier){
  const pmid=/^PMID:([1-9][0-9]*)$/i.exec(identifier);
  if(pmid)return guideLink({label:identifier,url:'https://pubmed.ncbi.nlm.nih.gov/'+pmid[1]+'/'});
  const doi=/^DOI:(10\.[0-9]{4,9}\/\S+)$/i.exec(identifier);
  if(doi)return guideLink({label:identifier,url:'https://doi.org/'+encodeURIComponent(doi[1])});
  return el('span',identifier);
}
function nativeGoGroups(title,groups,raw){
  const box=el('div');box.append(el('strong',title));
  if(raw==='')box.append(el('p','No value supplied in this native row.','small'));
  else{
    box.append(el('p','Source literals retain OR alternatives and AND groups; identifier meanings are not inferred.','small'));
    const alternatives=el('ol');
    for(const [index,group] of (groups||[]).entries())alternatives.append(el('li','Alternative '+(index+1)+': '+group.join(' AND ')));
    box.append(alternatives);
  }
  const original=el('details');original.append(el('summary','Exact source field'),el('pre',raw));box.append(original);return box;
}
function nativeGoQuality(record){
  const box=el('section'),qc=record.saved_quality_control;
  box.append(el('strong','Separate saved native quality checks'));
  if(!qc){box.append(el('p','No bound quality-check result is available for this row. No quality pass is implied.','small'));return box;}
  if(qc.extension_unsatisfiable===true)box.append(el('p','At least one combination of context terms conflicts under the pinned ontology; other alternatives may differ. The base annotation is not judged biologically false.','notice'));
  if(qc.normalization){
    if(qc.normalization.base_rule_filtered===true)box.append(el('p','The saved native-rule derivative filtered this base record. The original source row remains visible here; the Pharos graph is unchanged.','notice'));
    for(const change of qc.normalization.changed_columns||[]){
      const item=el('div');item.append(el('p','Normalized derivative: '+change.field+' (source column '+change.column+')'),fieldList({original_source_value:change.before,derivative_values:change.after_values}));box.append(item);
    }
  }
  if(qc.taxon_result){
    const taxon=qc.taxon_result;
    const message=taxon.negated_annotation_exempt?'Taxon check: this NOT-qualified record is exempt, not a validated taxon pass.':/(?:^|\.)PASS$/.test(String(taxon.result_type))?'No taxon conflict reported by this saved check.':'Taxon check reported '+taxon.result_type+(taxon.message?' · '+taxon.message:'');
    box.append(el('p',message,'small'));
  }
  const raw=el('details');raw.append(el('summary','Selected rule results and complete saved check'));
  for(const rule of qc.rule_results||[])raw.append(el('p','Selected rule '+rule.rule+': '+rule.result_type+(rule.message?' · '+rule.message:''),'small'));
  raw.append(el('pre',JSON.stringify(qc,null,2)));box.append(raw);return box;
}
function nativeGoDownloadPanel(result){
  const box=el('div'),button=el('button','Download native GO + QC packet','secondary'),status=el('p','','small');
  button.type='button';status.setAttribute('role','status');
  box.append(el('p','Separate full native GO + saved QC packet; contains more source rows than this selected claim. Keep outside the workspace ZIP.','small'),button,status);
  button.onclick=async()=>{
    const request=inspectionRequest,sourceRun=result.source_run,sourceSnapshot=result.snapshot_sha256,selectionId=result.selection_id;
    const current=()=>request===inspectionRequest&&sourceRun===runId&&sourceSnapshot===graph?.snapshot_sha256&&$('sourceGuideSelection').value===selectionId;
    if(!current())return;
    button.disabled=true;status.textContent='Verifying and packing the separate preserved native GO and QC source files…';
    try{
      const response=await fetch('/api/download-native-go-context',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run_id:sourceRun,selection_id:selectionId})});
      if(!current())return;
      if(!response.ok){let error;try{error=await response.json();}catch(_){error={};}throw new Error(error.error||'The separate native GO packet could not be exported.');}
      if((response.headers.get('Content-Type')||'').split(';')[0].trim().toLowerCase()!=='application/zip')throw new Error('The native GO export did not return a ZIP attachment.');
      const attachment=await response.blob();
      if(!current())return;
      const supplied=/\bfilename="([A-Za-z0-9_.-]+\.zip)"/.exec(response.headers.get('Content-Disposition')||'');
      const url=URL.createObjectURL(attachment),link=el('a');link.href=url;link.download=supplied?supplied[1]:'native_go_context_qc.zip';
      try{link.click();}finally{setTimeout(()=>URL.revokeObjectURL(url),1000);}
      status.textContent='Downloaded the separate native GO + QC packet. Follow its README and keep the matching complete workspace separately.';
    }catch(error){if(current())status.textContent='Native GO packet was not downloaded: '+error.message;}
    finally{if(current())button.disabled=false;}
  };
  return box;
}
function renderNativeGoContext(result,box){
  box.replaceChildren(el('p','These versioned native GO rows are separate source context. They do not identify or repair the historical Pharos record, establish independent biological truth, or change its review state.','notice'));
  const headers=Array.isArray(result.source?.headers)?result.source.headers:[];
  for(const header of headers.filter(value=>/^!(?:date-generated|go-version|generated-by):/.test(value)))box.append(el('p',header,'small'));
  box.append(el('p','Exact source query: '+result.query.protein+' · '+result.query.go_id,'small'));
  if(result.compatibility){
    box.append(el('p','Match to available Pharos fields: '+result.compatibility.candidate_count+' candidate records. Matching these fields does not establish the original annotation identity.','small'));
  }
  if(result.quality_control?.status==='verified_saved_output'){
    box.append(el('p','Separate quality checks: verified saved output.','small'));
  }else box.append(el('p','No bound saved native quality-check output is configured. No GO quality pass is implied.','small'));
  if(result.quality_control?.status==='verified_saved_output'&&result.source_bytes_and_native_scope_verified===true)box.append(nativeGoDownloadPanel(result));
  if(!result.record_count)box.append(el('p','No matching row was found in this preserved source scope. This is not evidence of biological absence.'));
  const compatible=new Set(result.compatibility?.native_record_ids||[]);
  for(const record of result.records){
    const card=el('article',undefined,'source-record');
    card.append(el('h4',(record.negated?'NOT annotation':'Positive-polarity annotation')+' · '+record.subject+' · '+record.go_id),
      el('p','Native relation: '+record.relation_literal+(record.negated?' (qualified by NOT)':'')),
      el('p','Native source line '+record.source_line+' · '+record.id,'small'),
      el('p',(Array.isArray(record.strict_projection_candidate_for_edge_ids)?record.strict_projection_candidate_for_edge_ids.length>0:compatible.has(record.id))?'Matches the available Pharos fields; original annotation identity remains unresolved.':'Related native annotation for this exact protein/GO pair; not a strict match to the available Pharos fields.','small'));
    card.append(fieldList({evidence_code:record.evidence_code,assigned_by:record.assigned_by,annotation_date:record.annotation_date,gene_product_form:record.gene_product_form_id,taxon_ids:record.taxon_ids}),nativeGoEvidenceHelp(record.evidence_code));
    const references=el('div');references.append(el('strong','Native reference identifiers'),el('p','These identifiers may name the same reference; they are not independent experiment counts.','small'));
    const list=el('ul');for(const identifier of record.reference_identifiers||[]){const item=el('li');item.append(nativeGoReference(identifier));list.append(item);}references.append(list);card.append(references);
    card.append(nativeGoGroups('Annotation extension',record.extension_or_groups_raw,record.annotation_extension_raw),nativeGoGroups('With/from',record.with_from_or_groups_raw,record.with_from_raw));
    card.append(nativeGoQuality(record));
    const raw=el('details');raw.append(el('summary','Exact native source line and complete inspection record'),el('pre',record.raw_line),el('pre',JSON.stringify(record,null,2)));card.append(raw);box.append(card);
  }
  const provenance=el('details');provenance.append(el('summary','Source version and inspection boundaries'),fieldList(result.source));
  if(result.quality_control?.status==='verified_saved_output'){
    provenance.append(el('p',result.quality_control.method_note,'small'));
    provenance.append(fieldList({saved_quality_ontology:result.quality_control.ontology,
      retraction_table_headers:result.quality_control.retracted_reference_headers,
      ontobio_version:result.quality_control.ontobio_version}));
    for(const note of result.quality_control.limits||[])provenance.append(el('p',note,'small'));
  }
  for(const note of result.limitations||[])provenance.append(el('p',note,'small'));box.append(provenance);
}
async function runPathExploration(){
  if(!runId||!$('pathSource').value||$('pathExploreButton').disabled)return;
  const request=++pathRequest,sourceRun=runId,sourceSnapshot=graph.snapshot_sha256;
  $('pathExploreStatus').textContent='Following saved assertions…';$('pathExploreStatus').setAttribute('data-loading','true');$('pathExploreResults').setAttribute('aria-busy','true');$('pathExploreButton').disabled=true;$('pathExploreResults').replaceChildren();
  try{
    const predicate=$('pathPredicate').value;
    const result=await api('/api/explore',{run_id:sourceRun,source:$('pathSource').value,target:$('pathTarget').value||null,max_hops:Number($('pathHops').value),view:$('pathView').value,predicates:predicate?[predicate]:null});
    if(request!==pathRequest||sourceRun!==runId)return;
    if(result.source_run!==sourceRun||result.snapshot_sha256!==sourceSnapshot)throw new Error('Path result belongs to different saved evidence.');
    renderExploration(result);
    $('pathExploreStatus').textContent=result.search.paths_returned+' '+(result.search.paths_returned===1?'path':'paths')+' shown. '+(result.search.truncated?'Search stopped at '+result.search.truncation_reason.replaceAll('_',' ')+'. More paths may exist.':'Search complete within the selected bounds.')+' '+result.search.expansions+' assertion expansions.';
  }catch(error){if(request===pathRequest)$('pathExploreStatus').textContent=error.message;}
  finally{if(request===pathRequest&&sourceRun===runId){$('pathExploreStatus').setAttribute('data-loading','false');$('pathExploreResults').setAttribute('aria-busy','false');$('pathExploreButton').disabled=!runId||!$('pathSource').value||(!!$('pathTargetSearch').value.trim()&&!$('pathTarget').value);}}
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
function invalidateSourceGuide(){inspectionRequest++;$('sourceGuideOutput').replaceChildren();$('sourceGuideStatus').setAttribute('data-loading','false');$('sourceGuideOutput').setAttribute('aria-busy','false');$('sourceGuideStatus').textContent='Selection changed. Open the guide for this source.';}
function invalidateExploration(){pathRequest++;$('pathExploreResults').replaceChildren();$('pathExploreStatus').setAttribute('data-loading','false');$('pathExploreResults').setAttribute('aria-busy','false');$('pathExploreStatus').textContent='Scope changed. Explore paths for the current selections.';$('pathExploreButton').disabled=!runId||!$('pathSource').value||(!!$('pathTargetSearch').value.trim()&&!$('pathTarget').value);}
$('sourceGuideSearch').addEventListener('input',()=>{invalidateSourceGuide();populateSourceGuide();});
$('sourceGuideSelection').addEventListener('change',invalidateSourceGuide);
$('pathEntitySearch').addEventListener('input',()=>{invalidateExploration();populatePathEntities();});
$('pathTargetSearch').addEventListener('input',()=>{invalidateExploration();populatePathEntities();});
$('pathSource').addEventListener('change',()=>{invalidateExploration();$('pathTargetSearch').value='';$('pathTarget').value='';populatePathEntities();});
$('pathTarget').addEventListener('change',invalidateExploration);
for(const id of ['pathHops','pathView','pathPredicate'])$(id).addEventListener('change',()=>{invalidateExploration();populatePathEntities();});
$('sourceGuideForm').addEventListener('submit',event=>{event.preventDefault();loadSourceGuide($('sourceGuideSelection').value);});
$('neptuneNodeSearch').addEventListener('input',()=>{populateNeptuneNodes();invalidateNeptuneSelection();});
$('neptuneNode').addEventListener('change',invalidateNeptuneSelection);
$('neptuneLimit').addEventListener('change',invalidateNeptuneSelection);
$('neptuneForm').addEventListener('submit',event=>{event.preventDefault();readNeptuneSelection();});
$('pathExploreForm').addEventListener('submit',event=>{event.preventDefault();runPathExploration();});
$('loadSupportComparators').onclick=async()=>{
  if(savedReviewOnly())return;
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
