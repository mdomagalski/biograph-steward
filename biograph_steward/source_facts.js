/* Draft source records are sidecars; checking a claim never changes the graph. */
async function setupSourceFactReports(){
  const box=$('sourceFactReports');
  try{
    const response=await fetch('/api/source-facts'),data=await response.json();
    if(!response.ok)throw new Error(data.error||'Could not load source-fact records.');
    box.replaceChildren();
    for(const report of data.reports){
      const p=el('p'),a=el('a',report.source_id+' — '+report.records+' draft records');
      a.href=report.report_url;p.append(a,document.createTextNode(' · '+report.coverage_gaps+' flagged coverage gaps'));box.append(p);
    }
    if(!data.reports.length)box.append(el('p','No saved source-fact dossier is available.','small'));
    if(data.invalid_reports_withheld)box.append(el('p',data.invalid_reports_withheld+' artifact(s) failed integrity checks and were withheld.','notice warn'));
  }catch(error){box.replaceChildren(el('p',error.message,'small'));}
}
if(!JSON.parse($('embeddedData').textContent))setupSourceFactReports();
