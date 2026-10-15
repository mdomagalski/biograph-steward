let plannerReady=false,plannerBusy=false;
async function setupPlanner(){
  $('plannerResult').replaceChildren();$('plannerStatus').textContent='';plannerReady=false;$('plannerRun').disabled=true;
  if(!runId){$('plannerConfig').textContent='Model planning is available in the running app with a saved source run.';return;}
  try{const response=await fetch('/api/planner'),config=await response.json();plannerReady=config.configured===true;
    $('plannerConfig').textContent=plannerReady?'Configured model: '+config.model+' | '+config.endpoint:'Live planner unavailable: '+config.reason;
  }catch(_){$('plannerConfig').textContent='Could not read planner configuration. Deterministic guided questions remain available.';}
  $('plannerRun').disabled=!plannerReady;
}
$('plannerForm').addEventListener('submit',async event=>{
  event.preventDefault();if(plannerBusy||!plannerReady||!runId)return;
  plannerBusy=true;$('plannerRun').disabled=true;$('plannerResult').replaceChildren();$('plannerStatus').textContent='Requesting one bounded plan, then validating it before any local query...';
  try{const r=await api('/api/plan',{run_id:runId,question:$('plannerQuestion').value});
    $('plannerStatus').textContent=r.status+': '+r.reason;
    const plan=el('details');plan.append(el('summary','Proposed scope and model/tool trace'),el('pre',JSON.stringify(r.trace,null,2)));$('plannerResult').append(plan);
    const zip=el('a','Download planner trace and cited output ZIP');zip.href='/api/download/'+encodeURIComponent(r.plan_id);$('plannerResult').append(zip);
    if(r.answer){$('plannerResult').append(el('p',r.answer.overview));for(const s of r.answer.summary)$('plannerResult').append(el('p',s.text+' '+s.citation_ids.map(id=>'['+id+']').join(' ')));
      for(const c of r.answer.citations){const details=el('details');details.append(el('summary','['+c.id+'] '+c.review_state+' | '+c.kind));for(const e of c.evidence_records)details.append(evidenceCard(e));$('plannerResult').append(details);}
    }
  }catch(error){$('plannerStatus').textContent=error.message;}
  finally{plannerBusy=false;$('plannerRun').disabled=!plannerReady;}
});
