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
    const t = add(add(parent, 'div', null, 'scroller'), 'table'), head = add(t, 'thead'), tr = add(head, 'tr');
    headings.forEach(label => add(tr, 'th', label));
    const body = add(t, 'tbody');
    rows.forEach(values => { const row = add(body, 'tr'); values.forEach(value => add(row, 'td', value)); });
  }
  function renderCoessentiality(parent, result) {
    add(parent, 'h4', result.title);
    add(parent, 'p', result.interpretation, 'warning');
    add(parent, 'p', result.query_genes + ' fixed measured-gene queries; ' + result.primary_pairs +
      ' different-chromosome primary pairs; complete N=1–10. Neither source qualification contrast demonstrates prediction improvement.', 'small');
    add(parent, 'p', result.scope, 'small');
    const curves = add(parent, 'details'); add(curves, 'summary', 'Complete primary curves, control ranges and absolute coverage');
    add(curves, 'p', 'Enrichment is observed shared-context hits divided by query-matched expected hits. Every primary point retains all 92 queries. Opposite query directions are slots, not independent experiments.', 'small');
    const arms = ['normalized', 'current', 'historical'];
    const labels = ['Normalized source context', 'Current-release eligibility contrast', 'Historical native-xref contrast'];
    const range = point => ['minimum', 'median', 'maximum'].map(key => point[key] === null ? 'UNKNOWN / undefined' : metric(point[key])).join(' / ');
    table(curves, ['N', ...labels], result.N.map(n => [n, ...arms.map(arm => metric(result.primary_curves[arm][n-1].enrichment))]));
    ['current', 'historical'].forEach((treatment, index) => {
      add(curves, 'h4', labels[index+1] + ': descriptive controls');
      add(curves, 'p', 'Twenty count-matched and twenty measured-frame degree-preserving draws. Ranges are minimum / median / maximum, not confidence intervals.', 'small');
      table(curves, ['N', 'Count-matched enrichment', 'Degree-preserving enrichment'], result.N.map(n =>
        [n, ...['count', 'degree'].map(kind => range(result.controls[treatment][kind][n-1]))]));
    });
    add(curves, 'h4', 'Absolute shared-context hit fractions');
    table(curves, ['N', ...labels], result.N.map(n => [n, ...arms.map(arm => metric(result.primary_curves[arm][n-1].observed_hit_fraction))]));
    const fractions = add(curves, 'details'); add(fractions, 'summary', 'Absolute hit-fraction ranges for all control draws');
    table(fractions, ['N', 'Current count', 'Current degree', 'Historical count', 'Historical degree'], result.N.map(n =>
      [n, ...['current', 'historical'].flatMap(t => ['count', 'degree'].map(k => range(result.controls[t][k][n-1].absolute_hit_fraction)))]));
    const proof = add(parent, 'details'); add(proof, 'summary', 'Frozen identities and diagnostic coverage');
    add(proof, 'p', 'All ' + result.arm_count + ' arms and ' + result.scope_count + ' declared scopes remain in the downloadable coess_curves and coess_controls aggregate receipts below. Sign-restricted and same-chromosome diagnostics do not replace the primary endpoint. Native pair values and matrix payloads are excluded.', 'small');
    add(proof, 'p', 'Original scientific freeze: ' + result.original_pre_value_freeze_content_sha256, 'small');
    add(proof, 'p', 'Transport continuation: ' + result.transport_repair_content_sha256, 'small');
    add(proof, 'p', 'Native capture: ' + result.capture_content_sha256, 'small');
    add(proof, 'p', result.transport_exposure_scope, 'small');
    const limits = add(proof, 'ul'); result.limitations.forEach(text => add(limits, 'li', text));
  }
  function renderGrounding(parent, result) {
    add(parent, 'h4', result.title);
    add(parent, 'p', result.scope, 'warning');
    add(parent, 'p', result.interpretation, 'small');
    const arms = ['lexical', 'sentence', 'publication'], gold = result.metrics_by_arm.lexical.gold_counts;
    add(parent, 'p', result.split + ' partition: ' + result.admitted_endpoint_cases + '/' + result.primary_frame_cases +
      ' cases admitted (' + gold.grounding_error + ' native grounding-error; ' + gold.correctly_grounded +
      ' native correctly-grounded). ' + result.outside_endpoint_cases + ' outside-endpoint cases are not negatives.', 'small');
    add(parent, 'p', 'Error recall and false-conflict rate retain all cases of their gold class, including abstentions. Conflict precision concerns review proposals, not validated corrections.', 'small');
    const ratio = (m, k) => (m[k] === null ? 'undefined' : metric(m[k])) + ' (' + m.metric_numerators[k] + '/' + m.metric_denominators[k] + ')';
    table(parent, ['Fixed context arm', 'Conflict precision', 'Error recall', 'False-conflict rate', 'Resolved coverage', 'Abstentions'], arms.map(arm => {
      const m = result.metrics_by_arm[arm];
      return [arm, ...['precision', 'error_recall', 'false_conflict_rate', 'coverage'].map(k => ratio(m, k)), m.abstention_cases];
    }));
    const proof = add(parent, 'details'); add(proof, 'summary', 'Resolved-only diagnostics and frozen evaluation identity');
    add(proof, 'p', 'Resolved-only accuracy is conditional and secondary. The common-resolved intersection contains ' +
      result.common_resolved_secondary.n_cases + ' cases; it never replaces the complete admitted frame.', 'small');
    table(proof, ['Fixed context arm', 'Secondary resolved-only accuracy', 'Unresolved', 'Model error'], arms.map(arm => {
      const m = result.metrics_by_arm[arm]; return [arm, ratio(m, 'resolved_accuracy'), m.status_counts.unresolved, m.status_counts.model_error];
    }));
    add(proof, 'p', 'Complete paired transitions and secondary aggregates remain in the source receipt. No case IDs, source text, native tag records or individual predictions are published.', 'small');
    add(proof, 'p', 'Evaluation freeze: ' + result.evaluation_freeze_content_sha256, 'small');
    add(proof, 'p', 'Private evaluator report SHA256: ' + result.source_report_file_sha256, 'small');
    add(proof, 'p', 'Reference data license: ' + result.reference.data_license + '. Integrity commitments do not authenticate the publisher or establish training independence.', 'small');
  }
  const methodNames = {
    localplus:'Original LocalPlus', fastsinksourceplus:'Original FSS · primary candidate', genemaniaplus:'Original GeneMANIA · secondary',
    global_full_allseeds_local:'Full-context LocalPlus', strict_alias_localplus:'Full-context LocalPlus · strict source profile',
    global_full_allseeds_fss:'Full-context FSS', official_blast:'Official BLAST', official_prott5_cosine3:'Official ProtT5 · three neighbors',
    official_nonexperimental:'Pre-deadline annotation baseline', official_naive:'Official frequency baseline'
  };
  const methodName = name => methodNames[name] || name;
  const namespaceName = name => ({biological_process:'Biological process',molecular_function:'Molecular function',cellular_component:'Cellular component'}[name] || name);
  const frameName = name => name === 'primary' ? 'Original protein cohort' : name === 'reserved' ? 'Additional protein cohort' : name;
  const settingName = name => name === 'partial' ? 'Partial knowledge' : name === 'partial_publishedaftert0' ? 'Later-publication subset' : name;
  function componentSources(parent, component, options) {
    if (!/^[A-Za-z0-9_-]{1,80}$/.test(options.publicationId || '')) return;
    const ul=add(parent,'ul');
    for (const source of component.sources || []) {
      if (!/^sources\/[a-z_]+\.json$/.test(source.file || '')) continue;
      const a=add(add(ul,'li'),'a',source.role+' aggregate receipt');
      a.href='/api/scientific-assessment/'+options.publicationId+'/files/'+source.file;
    }
  }
  function renderFunctionRecovery(parent,result,options) {
    const block=add(parent,'section');add(block,'h4',result.title);
    const rows=result.rows || [], find=(frame,method)=>rows.find(r=>r.frame===frame && r.setting==='partial' && r.namespace==='biological_process' && r.method===method);
    const old=find('primary','localplus'), current=find('primary','strict_alias_localplus');
    if (typeof old?.micro_Fmax==='number' && typeof current?.micro_Fmax==='number') {
      add(block,'p','Original-cohort biological-process micro-Fmax: '+metric(old.micro_Fmax)+' → '+metric(current.micro_Fmax)+' with the strict source profile.','notice');
    }
    const primary=['localplus','fastsinksourceplus','genemaniaplus','strict_alias_localplus','global_full_allseeds_fss','official_nonexperimental','official_blast','official_prott5_cosine3'].map(m=>find('primary',m)).filter(Boolean);
    table(block,['Original cohort · BPO','Micro Fmax','IA micro','Macro Fmax','IA macro','IA Smin ↓','Fixed 0.5 F1','Status'],primary.map(r=>[
      methodName(r.method),metric(r.micro_Fmax),metric(r.IA_micro_Fmax),metric(r.macro_Fmax),metric(r.IA_macro_Fmax),metric(r.IA_weighted_Smin),metric(r.fixed_0_5?.F1),r.status]));
    add(block,'p','Primary micro-Fmax endpoint: '+(result.roles?.original_primary?.conclusion || 'The original propagation candidate and its same-source comparator remain in the complete results.'),'small');
    add(block,'p','The reference measures later curator annotations recovered from dated model inputs. Fmax is the best F1 on the benchmark threshold grid; it is not a calibrated confidence or a whole-graph accuracy percentage.','small');
    add(block,'p','Read pooled and per-protein metrics together. At an unchanged 0.5 cutoff, precision, recall and coverage can trade off; the app uses these scores as hypotheses, with no automatic acceptance.','small');
    const operating=add(block,'details');add(operating,'summary','Fixed 0.5 operating-point trade-offs');
    table(operating,['Original cohort · BPO','Precision','Recall','F1','Native coverage ratio','Author status'],primary.map(r=>[
      methodName(r.method),...['PPV','recall','F1','coverage'].map(k=>metric(r.fixed_0_5?.[k])),r.fixed_0_5?.status||r.status]));
    add(operating,'p','An omitted native point is unavailable, rather than zero. After known-annotation exclusion, the author’s coverage numerator and eligible denominator can differ; a native coverage ratio above one is preserved and qualified in the source receipt.','small');
    const transfer=add(block,'details');add(transfer,'summary','Additional-cohort transfer and exact reference denominators');
    add(transfer,'p',result.roles?.transfer || 'This is a separately frozen protein cohort from the same reference study; it is not independent-study replication.','small');
    const reserved=['strict_alias_localplus','global_full_allseeds_local','global_full_allseeds_fss','official_nonexperimental','official_blast','official_prott5_cosine3'].map(m=>find('reserved',m)).filter(Boolean);
    table(transfer,['Additional cohort · BPO','Micro Fmax','IA micro','Macro Fmax','IA macro','Status'],reserved.map(r=>[methodName(r.method),metric(r.micro_Fmax),metric(r.IA_micro_Fmax),metric(r.macro_Fmax),metric(r.IA_macro_Fmax),r.status]));
    table(transfer,['Cohort','Setting','GO aspect','Author-recognized IDs','Eligible proteins','IA-eligible proteins'],(result.denominators || []).map(r=>[
      frameName(r.frame),settingName(r.setting),namespaceName(r.namespace),r.author_recognized_target_IDs,r.eligible_proteins,r.IA_eligible_proteins]));
    const uncertainty=add(block,'details');add(uncertainty,'summary','All paired uncertainty comparisons');
    add(uncertainty,'p','Shared protein resamples retain each protein’s terms together. These conditional intervals do not establish independent biological replication; proteins can share genes, graph neighbors and studies. Observed differences below are computed from the native point estimates, not bootstrap means.','small');
    table(uncertainty,['Cohort','Candidate − comparator','Readout','Observed difference','Paired 95% interval'],(result.paired_comparisons || []).map(c=>{
      const key=c.readout==='ordinary'?'micro_Fmax':c.readout==='IA_weighted'?'IA_micro_Fmax':null;
      const a=rows.find(r=>r.frame===c.frame&&r.setting===c.setting&&r.namespace===c.namespace&&r.method===c.candidate);
      const b=rows.find(r=>r.frame===c.frame&&r.setting===c.setting&&r.namespace===c.namespace&&r.method===c.comparator);
      const delta=key&&typeof a?.[key]==='number'&&typeof b?.[key]==='number'?a[key]-b[key]:null;
      return [frameName(c.frame),methodName(c.candidate)+' − '+methodName(c.comparator),c.readout,metric(delta),
        Array.isArray(c.paired_95_percentile_interval)?c.paired_95_percentile_interval.map(metric).join(' to '):'Pending'];
    }));
    const all=add(block,'details');add(all,'summary','Every declared outcome · '+rows.length+' cohort/setting/method/aspect slots');
    let populated=false;
    all.ontoggle=()=>{if(all.open&&!populated){
      table(all,['Cohort','Setting','GO aspect','Method','Status','Micro Fmax','IA micro','Macro Fmax','IA macro','Smin ↓','IA Smin ↓','Fixed 0.5 F1'],rows.map(r=>[
        frameName(r.frame),settingName(r.setting),namespaceName(r.namespace),methodName(r.method),r.status,
        ...['micro_Fmax','IA_micro_Fmax','macro_Fmax','IA_macro_Fmax','unweighted_Smin','IA_weighted_Smin'].map(k=>metric(r[k])),metric(r.fixed_0_5?.F1)]));populated=true;
    }};
    const limits=add(block,'details');add(limits,'summary','Reference scope, source versions and saved aggregates');
    add(limits,'p',result.scope,'notice');
    const ul=add(limits,'ul');(result.limitations||[]).forEach(x=>add(ul,'li',x));componentSources(limits,result,options);
  }
  const relationNames={always_None:'Always no reported relation',typed_co_mention:'Typed co-mention',specialist_native:'Published specialist',specialist_type_guard:'Specialist + type guard',flat_context_LLM:'Nano · flat context',source_audit_agent:'Nano · bounded tool agent'};
  function renderAgentReference(parent,result,options) {
    const block=add(parent,'section');add(block,'h4',result.title);add(block,'p',result.scope,'notice');
    const primary=result.primary;
    if (!primary) {add(block,'p','Final sealed relation comparison is not available.');return;}
    add(block,'p',primary.test_cases+' fixed entity pairs from '+primary.test_publications+' publications. Expert labels concern relations reported in the permitted abstract; native entity annotations are supplied.','small');
    add(block,'p',primary.agent_default_adoption_criterion_passed
      ? 'The agent met the frozen numerical adoption criterion on this source-reference task. Provenance and transfer limits still apply.'
      : 'The agent did not meet the frozen accuracy/F1 adoption criterion and is kept out of the default decision path.','notice');
    table(block,['Fixed arm','Exactly correct','Exact accuracy','Positive precision','Positive recall','Positive F1','Coverage','Unresolved'],Object.entries(primary.metrics).map(([name,m])=>[
      relationNames[name]||name,m.exact_correct+'/'+m.cases,metric(m.exact_accuracy),metric(m.exact_positive_relation.precision),metric(m.exact_positive_relation.recall),metric(m.exact_positive_relation.f1),metric(m.coverage),m.unresolved]));
    const deltas=add(block,'details');add(deltas,'summary','Agent contrasts, tool use and model costs');
    table(deltas,['Agent versus','Accuracy difference · 95% interval','Positive F1 difference · 95% interval'],Object.entries(primary.agent_paired_comparisons).map(([name,c])=>[
      relationNames[name]||name,c.accuracy_delta_95pct_paired_bootstrap.map(metric).join(' to '),c.exact_relation_F1_delta_95pct_paired_bootstrap.map(metric).join(' to ')]));
    table(deltas,['Language-model arm','Model calls','Read tools','Reported input tokens','Reported output tokens','Sum case minutes'],Object.entries(primary.execution_costs).filter(([name])=>name!=='specialist_native').map(([name,c])=>[
      relationNames[name]||name,c.model_calls,c.tool_reads,c.reported_token_usage?.prompt_tokens??'Unreported',c.reported_token_usage?.completion_tokens??'Unreported',
      typeof c.sum_case_elapsed_seconds==='number'?(c.sum_case_elapsed_seconds/60).toFixed(1):'Unreported']));
    add(deltas,'p','The flat control receives the same permitted information in one request. A fixed tool-reading order does not demonstrate adaptive retrieval. Five thousand paired publication bootstrap draws retain within-paper dependence.','small');
    if(result.gene){const gene=add(block,'details');add(gene,'summary','Complete gene-involving specialist assessment · separate denominator');
      add(gene,'p',result.gene.cases+' candidate pairs from '+result.gene.publications+' publications. These are the full gene-involving native rows, rather than the one-pair-per-paper agent sample.','small');
      table(gene,['Arm','Cases','Exact accuracy','Positive precision','Positive recall','Positive F1'],Object.entries(result.gene.metrics).map(([name,m])=>[
        relationNames[name]||name,m.cases,metric(m.exact_accuracy),metric(m.exact_positive_relation.precision),metric(m.exact_positive_relation.recall),metric(m.exact_positive_relation.f1)]));}
    if(result.artifact){const artifact=add(block,'details');add(artifact,'summary','Released artifact consistency · all native task rows');
      add(artifact,'p',result.artifact.native_candidate_rows+' candidate rows from '+result.artifact.native_candidate_publications+' candidate-bearing publications. This compares a single released checkpoint with the paper’s ten-run means; it does not audit its training membership.','small');
      table(artifact,['Native metric level','Precision','Recall','Single-checkpoint F1','Paper mean F1'],Object.entries(result.artifact.author_metric_reference_agreement).map(([kind,m])=>[
        kind,metric(m.precision),metric(m.recall),metric(m.f1),metric(result.artifact.paper_reported_10_seed_mean_F1[kind])]));}
    const proof=add(block,'details');add(proof,'summary','Reference provenance and complete aggregate reports');
    const ul=add(proof,'ul');(result.limitations||[]).forEach(x=>add(ul,'li',x));componentSources(proof,result,options);
  }
  function renderSnapshot(container, summary, options = {}) {
    if (typeof container === 'string') container = document.querySelector(container);
    if (!container) throw new Error('Scientific assessment container is unavailable.');
    if (!['biograph-steward.scientific-assessment-publication.v1.summary',
          'biograph-steward.scientific-assessment-publication.v2.summary',
          'biograph-steward.scientific-assessment-publication.v3.summary',
          'biograph-steward.scientific-assessment-publication.v4.summary'].includes(summary?.format))
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
    if (summary.coessentiality) renderCoessentiality(container, summary.coessentiality);
    if (summary.grounding) renderGrounding(container, summary.grounding);
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
  function render(container,summary,options={}) {
    if(summary?.format!=='biograph-steward.scientific-assessment-publication.v4.summary')return renderSnapshot(container,summary,options);
    if(typeof container==='string')container=document.querySelector(container);
    if(!container)throw new Error('Scientific assessment container is unavailable.');
    container.replaceChildren();add(container,'h3',summary.title);add(container,'p',summary.scope,'small');
    if(summary.function_recovery)renderFunctionRecovery(container,summary.function_recovery,options);
    if(summary.agent_reference_agreement)renderAgentReference(container,summary.agent_reference_agreement,options);
    const legacy=add(container,'details');add(legacy,'summary','99-target source workspace and earlier component assessments');
    let shown=false;
    legacy.ontoggle=()=>{if(legacy.open&&!shown){const body=add(legacy,'div');renderSnapshot(body,{...summary,title:'99-target source workspace',scope:summary.workspace_scope},options);shown=true;}};
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
