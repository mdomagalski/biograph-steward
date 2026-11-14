"""Render aggregate-only results; no abstracts, native cases or credentials."""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path

from biograph_steward.client import digest


def verified(source):
    value=json.loads(Path(source).read_text())
    if value.get('content_sha256')!=digest({k:v for k,v in value.items() if k!='content_sha256'}):
        raise ValueError('Aggregate report seal differs.')
    return value


def aggregate_page(title,body,value,output):
    esc=html.escape
    document=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BioGraph Steward — {esc(title)}</title><style>body{{font:16px/1.55 system-ui,sans-serif;color:#182c3e;background:#f6f8fa;max-width:1180px;margin:32px auto;padding:0 24px}}
h1{{font-size:30px;line-height:1.2}}h2{{font-size:23px}}section{{background:white;border:1px solid #dbe4ea;border-radius:12px;padding:24px;margin:20px 0}}
.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #dbe4ea}}th{{background:#edf2f6}}
a{{color:#125c95}}code{{overflow-wrap:anywhere}}.scope{{border-left:5px solid #177e89;padding:12px 16px;background:#edf8f8}}</style>
{body}<section><details><summary>Traceability</summary><p>Aggregate content seal: <code>{esc(value['content_sha256'])}</code>.</p>
<p>Source abstracts, individual reference labels, model weights and credentials are excluded from this aggregate page.</p></details></section></html>'''
    output=Path(output)
    if output.exists():raise ValueError('Choose a new presentation output.')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(document);return output


def render_gene(source,output):
    value=verified(source);esc=html.escape;pct=lambda n:f'{100*n:.1f}%'
    names={'always_None':'Always no reported relation','typed_co_mention':'Typed co-mention control',
           'specialist_native':'Published specialist','specialist_type_guard':'Specialist + type guard'}
    uncertainty=value['publication_cluster_uncertainty'];rows=[]
    for arm,m in value['metrics'].items():
        exact=m['exact_positive_relation'];ci=uncertainty['arm_intervals'][arm]['exact_positive_F1']
        fields=[names[arm],f"{m['exact_correct']:,}/{m['cases']:,}",pct(m['exact_accuracy']),
            pct(exact['precision']),pct(exact['recall']),pct(exact['f1']),pct(ci[0])+' to '+pct(ci[1]),
            pct(m['entity_pair']['f1']),str(m['unresolved'])]
        rows.append('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in fields)+'</tr>')
    families=[]
    family_names={'ChemicalEntity--GeneOrGeneProduct':'Chemical–gene',
        'DiseaseOrPhenotypicFeature--GeneOrGeneProduct':'Disease/phenotype–gene',
        'GeneOrGeneProduct--GeneOrGeneProduct':'Gene–gene'}
    for kind,methods in value['per_entity_type_metrics'].items():
        m=methods['specialist_native'];e=m['exact_positive_relation']
        fields=[family_names.get(kind,kind),f"{m['cases']:,}",pct(e['precision']),pct(e['recall']),pct(e['f1'])]
        families.append('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in fields)+'</tr>')
    differences=[]
    for name,intervals in uncertainty['paired_delta_intervals'].items():
        interval=intervals['exact_positive_F1']
        label=name.replace('specialist_native','published specialist').replace('typed_co_mention','co-mention control').replace('specialist_type_guard','type guard')
        differences.append(f'<li>{esc(label)}: 95% F1-difference interval {100*interval[0]:+.1f} to {100*interval[1]:+.1f} percentage points.</li>')
    body=f'''<section><h1>Curator-reference agreement for literature relations</h1>
<p class="scope">{value['cases']:,} native gene-involving candidate pairs from {value['publications']} publications.
The test asks which relation an abstract reports. It does not measure the biological correctness of every Pharos edge.</p>
<p>The authors' script intends the released model for BC8 test use, but no checkpoint training-ID or split manifest independently establishes its fine-tuning membership.
These numbers are reference agreement under that provenance limitation. Gold entity annotations are provided.</p></section>
<section><h2>Complete candidate denominators</h2><div class="table"><table><thead><tr><th>Method</th><th>Exactly correct</th><th>Exact accuracy</th><th>Positive precision</th><th>Positive recall</th><th>Positive F1</th><th>95% F1 interval</th><th>Pair F1</th><th>Unresolved</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div><p>Positive scores require the correct relation type. Pair F1 only asks whether a qualifying relation is present.
The co-mention control proposes an Association for every typed candidate; it is a weak control and is not the deployed Pharos workflow.
Unresolved outputs remain in the full accuracy and recall denominators.</p><ul>{''.join(differences)}</ul></section>
<section><h2>Published specialist across relation families</h2><div class="table"><table><thead><tr><th>Native pair family</th><th>Candidates</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead><tbody>{''.join(families)}</tbody></table></div>
<p>Gene is the corpus shorthand for its GeneOrGeneProduct category. This assessment does not establish canonical human-protein identity, species transfer or direct physical binding.</p></section>
<section><h2>How to interpret the result</h2><p>The 95% intervals resample entire publications 5,000 times, retaining all their correlated candidate rows.
They describe variation across this benchmark's publications; repeated entities or evidence across papers can remain.
The primary agent comparison uses one pair per publication, so its denominator differs from this complete pair table.</p>
<p>A no-relation label means no qualifying annotated relation in the permitted abstract. It does not mean no biological relationship exists elsewhere.
Model scores are uncalibrated. No graph acceptance or pruning was performed by this assessment.</p>
<p>Sources: <a href="https://doi.org/10.1093/database/baae069">curated BioCreative reference</a>, <a href="https://doi.org/10.1093/bioinformatics/btaf226">BioREDirect method</a>,
<a href="https://doi.org/10.1111/j.1467-9868.2007.00593.x">cluster bootstrap method</a>.</p></section>'''
    return aggregate_page('Literature relation reference agreement',body,value,output)


def render_artifact(source,output):
    value=verified(source);esc=html.escape;names={'pair':'Related entity pair','pair+novelty':'Pair + source novelty',
        'relation':'Relation type','relation+novelty':'Relation type + source novelty',
        'relation+direction':'Relation type + entity roles','all':'Relation type + novelty + roles'};rows=[]
    for kind,m in value['author_metric_reference_agreement'].items():
        mean=value['paper_reported_10_seed_mean_F1'][kind];delta=value['single_checkpoint_minus_paper_mean_F1'][kind]
        fields=[names[kind],f"{100*m['precision']:.2f}%",f"{100*m['recall']:.2f}%",f"{100*m['f1']:.2f}%",f'{100*mean:.2f}%',f'{100*delta:+.2f} points']
        rows.append('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in fields)+'</tr>')
    body=f'''<section><h1>Released-model artifact consistency</h1><p class="scope">All {value['native_candidate_rows']:,} author-processed candidate rows, from {value['native_candidate_publications']} candidate-bearing publications in the 400-abstract release.</p>
<p>This diagnostic uses the same fixed specialist weights and the authors' own metric helpers. It checks reference agreement across the complete native task;
it does not prove which examples were used to fine-tune the downloaded weights.</p></section>
<section><h2>Single released checkpoint and published means</h2><div class="table"><table><thead><tr><th>Metric level</th><th>Precision</th><th>Recall</th><th>Single checkpoint F1</th><th>Paper 10-run mean F1</th><th>Difference</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p>A single checkpoint is not expected to exactly reproduce the paper's multiple-seed mean. Numeric proximity does not establish training-split independence.</p></section>
<section><h2>Reference and scope</h2><p>Original relation and source-novelty labels use the BioCreative curation protocol. Added entity-role labels came from a separate BioREDirect annotation process:
a two-annotator pilot followed by single annotation of the remaining articles. Source novelty describes the article's contribution, not a discovery beyond Pharos.</p>
<p>Gold entities are supplied. Native Bind does not automatically establish direct physical binding. One source abstract has no processed candidate row.
The frozen inference uses the authors' native inference decoder. Their separate summary script has a different positive-class selection loop,
so its paper means are a diagnostic comparator, not an exact numerical reproduction target.
No model selection, threshold tuning, additional agent requests or graph changes were introduced.</p>
<p><a href="https://doi.org/10.1093/bioinformatics/btaf226">BioREDirect paper and protocol</a> · <a href="https://github.com/ncbi-nlp/BioREDirect">official source and intended test script</a></p></section>'''
    return aggregate_page('Released artifact consistency',body,value,output)


def render(source,output):
    value=verified(source)
    esc=html.escape
    pct=lambda x:f'{100*x:.1f}%'
    count=lambda x:f'{x:,}' if isinstance(x,(int,float)) else 'unreported'
    names={'always_None':'Always no reported relation','typed_co_mention':'Typed co-mention',
        'specialist_native':'Published BioREDirect specialist','specialist_type_guard':'Specialist + type guard',
        'flat_context_LLM':'Nano model, flat context','source_audit_agent':'Nano model, bounded tool agent'}
    rows=[]
    for arm,m in value['metrics'].items():
        exact=m['exact_positive_relation'];pair=m['entity_pair']
        rows.append('<tr>'+''.join(f'<td>{esc(str(x))}</td>' for x in
            (names[arm],f"{m['exact_correct']}/{m['cases']}",pct(m['exact_accuracy']),
             pct(exact['precision']),pct(exact['recall']),pct(exact['f1']),pct(pair['f1']),
             pct(m['coverage']),m['unresolved']))+'</tr>')
    comparisons=[]
    for name,c in value['agent_paired_comparisons'].items():
        fmt=lambda interval:' to '.join(f'{100*x:+.1f}' for x in interval)+' percentage points'
        comparisons.append(f"<li>Against {esc(names[name])}: accuracy delta 95% interval "
            f"{fmt(c['accuracy_delta_95pct_paired_bootstrap'])}; exact positive-relation F1 delta "
            f"{fmt(c['exact_relation_F1_delta_95pct_paired_bootstrap'])}.</li>")
    costs=[]
    for name,c in value['execution_costs'].items():
        if name=='specialist_native':continue
        u=c['reported_token_usage']
        costs.append(f"<tr><td>{esc(names[name])}</td><td>{c['model_calls']}</td>"
            f"<td>{c['tool_reads']}</td><td>{count(u.get('prompt_tokens'))}</td>"
            f"<td>{count(u.get('completion_tokens'))}</td>"
            f"<td>{c['sum_case_elapsed_seconds']/60:.1f} minutes</td></tr>")
    outcome=('The bounded agent met the frozen numerical reference-agreement criterion; provenance and transfer limits still apply.' if
        value['agent_default_adoption_criterion_passed'] else
        'The bounded agent did not meet the frozen accuracy and F1 adoption criterion. It is not promoted to the default decision path.')
    doc=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BioGraph Steward — expert-curated relation assessment</title><style>
body{{font:16px/1.55 system-ui,sans-serif;color:#182c3e;background:#f6f8fa;max-width:1220px;margin:32px auto;padding:0 24px}}
h1{{font-size:30px;line-height:1.2}}h2{{font-size:23px}}main,section{{background:white;border:1px solid #dbe4ea;border-radius:12px;padding:24px;margin:20px 0}}
.scope{{border-left:5px solid #177e89;padding:12px 16px;background:#edf8f8}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{text-align:left;padding:10px;border-bottom:1px solid #dbe4ea}}th{{background:#edf2f6}}small,code{{overflow-wrap:anywhere}}a{{color:#125c95}}
</style><main><h1>Expert-curated literature relation assessment</h1>
<p class="scope">{value['test_cases']} fixed gene-involving entity pairs from {value['test_publications']} separate BioCreative VIII abstracts.
The question is whether each abstract reports a relation of the stated type. This is not an estimate of whole-Pharos biological truth.</p>
<p>{esc(outcome)}</p><p>All test-arm predictions were completed and sealed before the selected expert relation labels were opened.
Unresolved and invalid outputs remain in the denominator. No live graph was changed.</p></main>
<section><h2>Reference agreement and model exposure</h2><p>The authors' prediction script applies the released specialist to BC8 test data.
The downloaded checkpoint has no training-ID or split manifest linking its weights to the paper's experiment, so its actual fine-tuning membership is not independently audited.
These results measure agreement with expert reference labels; unseen fine-tuning independence remains unestablished. Public language-model pretraining exposure is also incompletely auditable.</p></section>
<section><h2>All fixed comparison arms</h2><div class="table"><table><thead><tr>
<th>Method</th><th>Exactly correct</th><th>Exact accuracy</th><th>Exact positive precision</th><th>Exact positive recall</th><th>Exact positive F1</th><th>Pair F1</th><th>Coverage</th><th>Unresolved</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p>Exact relation scoring requires the correct native relation type. Pair scoring only asks whether a qualifying source relation is present.
An incorrect positive type counts as both a false positive and a missed correct type. A no-relation label applies to the permitted abstract, not to biology everywhere.</p></section>
<section><h2>Does the agent add value?</h2><ul>{''.join(comparisons)}</ul>
<p>Intervals use 5,000 fixed-seed paired publication bootstrap samples. They describe this selected source-case frame, not all Pharos edges.
The frozen promotion rule requires positive lower bounds for both metrics against the native specialist, type-guarded specialist and the same model with flat context.</p>
<div class="table"><table><thead><tr><th>Language-model arm</th><th>Calls</th><th>Tool reads</th><th>Input tokens</th><th>Output tokens</th><th>Sum case latency</th></tr></thead><tbody>{''.join(costs)}</tbody></table></div>
<p>The flat control receives the same permitted document, entity-context and specialist outputs in one request. The agent chooses tools in a bounded feedback loop.
Calling every tool in a fixed order does not demonstrate adaptive retrieval. Recorded token counts are not a price estimate.
Case latency includes serving and schema processing on shared compute; it is not an isolated throughput benchmark.</p></section>
<section><h2>What was verified, and what remains limited</h2><p>Relation labels are the authors' expert-curated annotations.
The specialist reproduces the released BioREDirect preprocessing, checkpoint and decoder. Native entity spans and IDs are supplied; this does not test entity detection or canonical protein mapping.
The NVIDIA Nano model is served by the existing vLLM deployment. It may read three tools, but cannot retrieve labels or alter the graph.</p>
<p>Source-unit IDs resolve to unchanged native passages. Correct IDs do not establish that the selected text entails the relation.
Native Bind annotations are not automatically direct physical binding. Public model-training overlap cannot be completely audited.
Original source abstracts, author model/code and individual cases are excluded from this aggregate page.</p>
<p>Sources: <a href="https://doi.org/10.1093/database/baae069">BioCreative VIII curated reference</a>,
<a href="https://doi.org/10.1093/bioinformatics/btaf226">BioREDirect paper</a>,
<a href="https://github.com/ncbi-nlp/BioREDirect">official model/code artifacts</a>.</p>
<small>Aggregate content seal: <code>{esc(value['content_sha256'])}</code><br>
Frozen comparison: <code>{esc(value['comparison_content_sha256'])}</code><br>
Frozen predictions: <code>{esc(value['prediction_freeze_content_sha256'])}</code></small></section></html>'''
    output=Path(output)
    if output.exists():raise ValueError('Choose a new presentation output.')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(doc)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--kind',choices=('primary','gene','artifact'),default='primary')
    args=parser.parse_args();print({'primary':render,'gene':render_gene,'artifact':render_artifact}[args.kind](args.source,args.output))


if __name__=='__main__':main()
