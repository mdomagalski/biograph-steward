/* Snapshot comparison uses saved sources; no model or network retrieval is triggered. */
let refreshChoices = [];
function setupRefresh(){
  for(const [id,preferred] of [['refreshBefore',null],['refreshAfter',runId]]){
    const select=$(id),previous=select.value;
    select.replaceChildren();
    for(const choice of refreshChoices){
      const option=el('option',choice.run_id+' · '+choice.reviews+' review events'+(choice.data_kind==='synthetic_demo'?' · synthetic':''));
      option.value=choice.run_id;select.append(option);
    }
    const selected=preferred||previous;
    if(selected&&refreshChoices.some(c=>c.run_id===selected))select.value=selected;
  }
  $('refreshCompare').disabled=refreshChoices.length===0;
}
async function loadRefreshRuns(){
  try{
    const response=await fetch('/api/refresh-runs'),data=await response.json();
    if(!response.ok)throw new Error(data.error||'Could not list saved runs.');
    refreshChoices=data.runs;setupRefresh();
    $('refreshStatus').textContent=refreshChoices.length?'Select saved runs to compare.':'Build or reopen a workbench run first. Experimental panel packets are outside this comparison.';
  }catch(error){$('refreshStatus').textContent=error.message;}
}
async function loadRefreshHistory(){
  const box=$('refreshHistory');if(!box)return;
  box.replaceChildren(el('p','Checking saved comparison files…','small'));
  try{
    const response=await fetch('/api/refresh-history'),data=await response.json();
    if(!response.ok)throw new Error(data.error||'Could not list saved comparisons.');
    box.replaceChildren();
    box.append(el('h3','Saved comparison history'));
    box.append(el('p','Open recorded results without making another comparison. Archive access checks saved files; current replay remains a separate check.','small'));
    if(!data.comparisons.length)box.append(el('p','No saved comparisons found.'));
    for(const item of data.comparisons){
      const row=el('details'),title=el('summary',item.name+(item.run_id===runId?' · current run':''));row.append(title);
      row.append(el('p',item.message,item.integrity==='passed'?'notice':'notice warn'));
      if(item.created_at)row.append(el('p','Saved '+item.created_at,'small'));
      const counts=Object.entries(item.status_counts||{}).map(([key,n])=>n+' '+key.replaceAll('_',' '));
      if(counts.length)row.append(el('p',counts.join(' · '),'small'));
      if(item.report_url){const link=el('a','Open read-only comparison archive');link.href=item.report_url;link.target='_blank';link.rel='noopener';row.append(link);}
      if(item.replay_report_url){row.append(document.createTextNode(' · '));const replay=el('a','Replay and open verified report');replay.href=item.replay_report_url;replay.target='_blank';replay.rel='noopener';row.append(replay);}
      if(item.changed_implementation_modules?.length)row.append(el('p','Implementation differs: '+item.changed_implementation_modules.join(', ')+'. Live graph access and replay exports still require the recorded implementation.','small'));
      if(item.run_id===runId)row.open=true;
      box.append(row);
    }
    box.append(el('p',data.note,'small'));
  }catch(error){box.replaceChildren(el('p',error.message,'notice warn'));}
}
$('refreshReload').onclick=()=>Promise.all([loadRefreshRuns(),loadRefreshHistory()]);
$('refreshForm').onsubmit=async event=>{
  event.preventDefault();$('refreshCompare').disabled=true;
  $('refreshStatus').textContent='Checking saved sources and evidence changes…';$('refreshResult').replaceChildren();
  try{
    const result=await api('/api/refresh-compare',{before_run:$('refreshBefore').value,after_run:$('refreshAfter').value,carry_reviews:$('refreshCarry').checked});
    const box=$('refreshResult'),comparison=result.comparison;
    const counts=comparison.summary.status_counts||{};
    box.append(el('p',Object.entries(counts).map(([key,n])=>n+' '+key.replaceAll('_',' ')).join(' · '),'notice'));
    const eligible=comparison.summary.eligible_review_assertions||0;
    const inherited=result.graph.review_events.filter(e=>e.migration?.comparison_sha256===comparison.comparison_sha256).length;
    box.append(el('p',eligible+' assertion'+(eligible===1?'':'s')+' eligible for prior-review carryover. '+inherited+' inherited review event'+(inherited===1?'':'s')+' added.','small'));
    const report=el('a','Open full comparison and review provenance');report.href=result.report_url;report.target='_blank';report.rel='noopener';box.append(report);
    box.append(document.createTextNode(' · '));const download=el('a','Download comparison and sources');download.href=result.download_url;box.append(download);
    const open=el('button','Open resulting evidence graph','secondary');open.style.margin='12px 0';
    open.onclick=()=>{runId=result.run_id;history.replaceState(null,'','?run='+encodeURIComponent(runId));showGraph(result.graph);status('Comparison run opened. Original source runs remain unchanged.');};box.append(el('p'),open);
    const rows=comparison.assertions.filter(a=>a.status!=='unchanged'||a.review_eligible).slice(0,100);
    const assertions=new Map(result.graph.assertions.map(a=>[a.id,a])),nodes=new Map(result.graph.nodes.map(n=>[n.id,n]));
    const label=id=>nodes.get(id)?.sym||nodes.get(id)?.name||id;
    if(rows.length){const scroller=el('div',undefined,'scroller');scroller.append(table(['Claim','Observed change','Comparison','Review carryover'],rows.map(a=>{
      const claim=assertions.get(a.assertion_id);
      return {cells:[claim?label(claim.subject)+' → '+label(claim.object):a.assertion_id,a.observed_change,a.status,a.review_eligible?'Eligible':'Requires review']};
    })));box.append(scroller);}
    box.append(el('p','Up to 100 changed or review-eligible assertions shown here. The full report includes all assertions, compatibility reasons and original review provenance. A disappearance is not a scientific retraction.','small'));
    $('refreshStatus').textContent='Comparison saved as '+result.run_id+'.';
    loadRefreshHistory();
  }catch(error){$('refreshStatus').textContent=error.message;}
  finally{$('refreshCompare').disabled=refreshChoices.length===0;}
};
if(!JSON.parse($('embeddedData').textContent)){loadRefreshRuns();loadRefreshHistory();}
else $('refreshPanel').classList.add('hidden');
