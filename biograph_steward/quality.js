/* Read-only, exact-source-bound verifier sidecars. No graph/review writes. */
async function setupQualityReports(){
  const box=$('qualityReports');
  try{
    const response=await fetch('/api/evidence-quality');const data=await response.json();
    if(!response.ok)throw new Error(data.error||'Could not load evidence-quality reports.');
    box.replaceChildren();
    for(const r of data.reports){
      const p=el('p'),a=el('a','Inspect '+r.name+' — '+r.cases+' cases, '+r.model_requests+' verifier turns');
      a.href=r.report_url;p.append(a);const download=el('a','Download reproducible comparison');download.href=r.download_url;
      p.append(document.createTextNode(' · '),download);box.append(p);
    }
    if(!data.reports.length)box.append(el('p','No completed source-consistency comparison is available.','small'));
    if(data.invalid_reports_withheld)box.append(el('p',data.invalid_reports_withheld+' report(s) failed integrity checks and were withheld.','notice warn'));
  }catch(error){box.replaceChildren(el('p',error.message,'small'));}
}
async function appendQualityFindings(assertion,container){
  if(!runId||assertion.kind!=='variant_therapy_response')return;
  const sourceRun=runId,box=el('section',undefined,'evidence');container.append(box);
  box.append(el('h4','Source verification'),el('p','Checking for an assessment of this exact source and assertion revision…','small'));
  try{
    const response=await fetch('/api/evidence-quality?run='+encodeURIComponent(sourceRun)+'&assertion='+encodeURIComponent(assertion.id));
    const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not load source verification.');
    if(sourceRun!==runId||!box.isConnected)return;
    box.replaceChildren(el('h4','Advisory source verification'));
    if(!data.passports.length){box.append(el('p','No assessment matches this exact source and assertion revision. No support is inferred.','small'));return;}
    for(const p of data.passports){
      const c=p.case,o=p.observation,a=o.assessment;
      box.append(el('h5',p.report_name),el('p',p.lifecycle_note,'notice'),el('p','Verifier: '+(a?.verdict||o.status)+' | Recommendation: '+o.decisions.assisted),
        el('p',a?.explanation||o.findings.map(f=>f.detail).join('; ')||'No semantic verification was run.'));
      if(a){box.append(el('p','Context mismatches: '+(a.context_mismatches.join('; ')||'none reported'),'small'),el('p','Missing details: '+(a.missing_details.join('; ')||'none reported'),'small'));}
      for(const e of a?.evidence||[]){const quote=el('blockquote',e.quote);box.append(quote,el('p',c.selection.passages[e.sentence_index].locator,'small'));}
      const source=el('details');source.append(el('summary','Claim and exact supplied source passages'),el('p',c.task.claim));
      for(const s of c.task.document.sentences)source.append(el('p','['+s.index+'] '+s.text),el('p',c.selection.passages[s.index].locator,'small'));
      const report=el('a','Inspect comparison and source passport');report.href='/api/evaluation/'+encodeURIComponent(p.report_name)+'/';box.append(source,report);
    }
    box.append(el('p','These are machine assessments of unmodified source annotations. Synthetic test edits never attach to real evidence edges. Use the existing human review form to record any decision.','small'));
  }catch(error){box.replaceChildren(el('h4','Source verification unavailable'),el('p',error.message,'small'));}
}
if(!JSON.parse($('embeddedData').textContent))setupQualityReports();
