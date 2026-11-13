// One read-only aggregate snapshot. Scientific labels come from bound receipts.
(function () {
  'use strict';
  const node = (tag, value, className) => {
    const item = document.createElement(tag);
    if (value !== undefined && value !== null) item.textContent = String(value);
    if (className) item.className = className;
    return item;
  };
  const add = (parent, tag, text, className) => {
    const item = node(tag, text, className); parent.append(item); return item;
  };
  const metric = value => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(6) : 'Unavailable';
  function table(parent, headings, rows) {
    const t = add(parent, 'table'), head = add(t, 'thead'), tr = add(head, 'tr');
    headings.forEach(label => add(tr, 'th', label));
    const body = add(t, 'tbody');
    rows.forEach(values => { const row = add(body, 'tr'); values.forEach(value => add(row, 'td', value)); });
  }
  function render(container, summary, options = {}) {
    if (typeof container === 'string') container = document.querySelector(container);
    if (!container) throw new Error('Scientific assessment container is unavailable.');
    if (summary?.format !== 'biograph-steward.scientific-assessment-publication.v1.summary')
      throw new Error('Unsupported scientific assessment snapshot.');
    container.replaceChildren();
    add(container, 'h3', summary.title);
    add(container, 'p', 'Whole-graph scientific precision remains unidentified. Prospective prediction improvement is unproved.', 'warning');
    add(container, 'p', summary.scope, 'small');
    const h = summary.native_history, d = summary.default_view, go = summary.GO, crc = summary.CRC_cohort, cv = summary.CIViC;
    table(container, ['Assessment axis', 'Result and unit', 'Unknown / qualification'], [
      ['Native Wiki history', h.verified + '/' + h.requested + ' exact model revisions; ' + h.source_compatible_connections + '/' + h.original_connections + ' protein/version source connections', h.literal_protein_xref + ' literal protein; ' + h.compatible_gene_xref + ' gene compatible; ' + h.unknown_connections + ' UNKNOWN'],
      ['Default retained view', d.retained + '/' + d.original + ' original evidence rows', d.GO_identifier_currency_excluded + ' GO identifier-currency exclusions; Wiki UNKNOWN retained'],
      ['GO experimental curation', go.compatible_experimental + '/' + go.original + ' original GO assertions compatible', go.UNKNOWN + ' UNKNOWN; coverage, not scientific precision'],
      ['CRC genomic cohort', crc.supported + '/' + crc.original + ' original disease assertions supported', crc.UNKNOWN + ' UNKNOWN; statistical cohort source, not expert gold'],
      ['CIViC expert conclusions', cv.expert_clinical_conclusions + ' separate expert conclusions; ' + cv.exact_original_contexts_resolved + '/' + cv.original + ' original response contexts resolved', cv.UNKNOWN + ' original assertions unresolved by this layer']
    ]);
    const scope = add(container, 'details'); add(scope, 'summary', 'Interpret these denominators');
    ['native_history', 'default_view', 'GO', 'CRC_cohort', 'CIViC'].forEach(key => add(scope, 'p', summary[key].interpretation, 'small'));
    add(scope, 'p', 'GO ontology release ' + go.ontology_release + '; GAF generated ' + go.GAF_generated + '.', 'small');
    add(container, 'h4', 'Recorded-assay recovery: development comparison');
    const im = summary.INMC;
    add(container, 'p', im.interpretation);
    add(container, 'p', im.eligible_pairs + ' eligible measured pairs: ' + im.detected + ' detected; ' + im.conditional_nondetected + ' conditional non-detections. Three-seed means; seeds are computational repeats.', 'small');
    im.experiments.forEach(experiment => {
      add(container, 'h4', experiment.title);
      table(container, ['Feature view', 'Unique memberships', 'Mean AP', 'Mean AUROC'], experiment.arms.map(arm => [arm.label, arm.unique_memberships, metric(arm.mean_AP), metric(arm.mean_AUROC)]));
      const seeds = add(container, 'details'); add(seeds, 'summary', 'Fixed seed results');
      table(seeds, ['Feature view', 'Seed', 'AP', 'AUROC'], experiment.arms.flatMap(arm => experiment.seeds.map(seed => [arm.label, seed, metric(arm.AP_by_seed[String(seed)]), metric(arm.AUROC_by_seed[String(seed)])])));
    });
    add(container, 'p', im.scope, 'small'); add(container, 'p', im.decision, 'small');
    const limits = add(container, 'ul'); summary.remaining_gaps.forEach(text => add(limits, 'li', text));
    const proof = add(container, 'details'); add(proof, 'summary', 'Source receipts, hashes and primary methods');
    add(proof, 'p', 'Graph: ' + summary.graph_sha256, 'small');
    const sourceList = add(proof, 'ul');
    let base = options.baseUrl;
    if (!base && /^[A-Za-z0-9_-]{1,80}$/.test(options.publicationId || '')) base = '/api/scientific-assessment/' + options.publicationId + '/';
    if (base && !/^\/(?!\/)[^\\?#]*\/$/.test(base)) throw new Error('Scientific assessment links require a local absolute base URL.');
    summary.sources.forEach(source => {
      const row = add(sourceList, 'li');
      if (base && /^sources\/[a-z_]+\.json$/.test(source.file)) {
        const link = add(row, 'a', source.role + ' source receipt'); link.href = base + 'files/' + source.file;
      } else add(row, 'span', source.role + ' source receipt');
      add(row, 'code', ' · ' + source.file_sha256);
    });
    const links = add(proof, 'ul'); summary.literature.forEach(source => {
      const row = add(links, 'li');
      const url = new URL(source.url);
      if (url.protocol !== 'https:') throw new Error('Primary reference links require HTTPS.');
      const link = add(row, 'a', source.title); link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
    });
    if (base) { const link = add(proof, 'a', 'Open the compact assessment report'); link.href = base + 'report'; }
    return container;
  }
  window.ScientificAssessment = Object.freeze({render});
}());

// Catalogue loading uses only verified compact publications; no source fetch,
// model call or graph mutation is triggered by opening the assessment tab.
let scientificAssessmentRequest=0;
async function initializeScientificAssessments(){
  const select=document.getElementById('scientificAssessmentSelection'),status=document.getElementById('scientificAssessmentStatus'),body=document.getElementById('scientificAssessmentBody');
  if(!select||!status||!body)return;
  const epoch=++scientificAssessmentRequest;select.disabled=true;status.textContent='Checking saved scientific assessments…';
  try{
    const response=await fetch('/api/scientific-assessments'),data=await response.json();
    if(!response.ok)throw new Error(data.error||'Assessment catalogue unavailable.');
    if(epoch!==scientificAssessmentRequest)return;
    const rows=(data.assessments||[]).sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)));
    select.replaceChildren();
    for(const row of rows){if(!/^[A-Za-z0-9_-]{1,80}$/.test(row.id))throw new Error('Invalid assessment identifier.');const option=document.createElement('option');option.value=row.id;option.textContent=row.created_at+' · '+row.id;select.append(option);}
    select.disabled=!rows.length;
    function show(){const row=rows.find(item=>item.id===select.value);if(!row)return;ScientificAssessment.render(body,row.summary,{publicationId:row.id});status.textContent='Verified aggregate receipts for a fixed source snapshot. Complete source replay remains in the workspace package.';}
    select.onchange=show;
    if(rows.length)show();else{body.replaceChildren();status.textContent='No verified scientific assessment is published in this workspace.';}
  }catch(error){if(epoch===scientificAssessmentRequest){body.replaceChildren();status.textContent=error.message;}}
  document.getElementById('scientificAssessmentReload').onclick=initializeScientificAssessments;
}
