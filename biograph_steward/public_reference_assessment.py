"""Present the already published public-reference aggregates; never assign labels.

The source report is a fixed, aggregate-only research deliverable. This adapter
keeps positive recovery, conditional assay agreement and whole-graph truth
separate when bringing that deliverable into the existing assessment viewer.
"""
from copy import deepcopy
import hashlib
from html import escape
import json
import math

FILE = 'sources/public_reference.json'
OPENCELL_FILE = 'sources/opencell_localization.json'
FORMAT = 'biograph-steward.public-curator-reference-assessment.v1'
ARMS = {
    'A_raw_Pharos_scope_qualified': 'Captured Pharos',
    'A_retained_scope_qualified': 'Retained Pharos',
    'B_native_location_scope_qualified': 'Native positive location records',
    'C_native_experimental_scope_qualified': 'Native experimental records only',
    'A_raw_Pharos_author_coarse_control': 'Author coarse-map sensitivity control',
}
PANELS = tuple(prefix + scope for prefix in ('canonical_', 'manual_assay_')
               for scope in ('current_workspace_218', 'historical_pruning_3172',
                             'historical_full_network_20412'))


def need(ok, message):
    if not ok:
        raise ValueError('Public reference assessment: ' + message)


def count(value):
    need(type(value) is int and value >= 0, 'invalid count.')
    return value


def summary(raw, pin):
    need(isinstance(pin, str) and hashlib.sha256(raw).hexdigest() == pin,
         'source FILE pin differs.')
    from .scientific_assessment import _task_tree
    value = _task_tree(json.loads(raw))
    need(value['format'] == FORMAT and value['whole_graph_biological_accuracy'] is None
         and value['graph_or_local_review_states_changed_by_assessment'] is False
         and value['new_reference_labels_assigned_by_AI'] is False
         and type(value['new_models_fitted']) is int and value['new_models_fitted'] == 0
         and type(value['model_calls']) is int and value['model_calls'] == 0,
         'reference scope or truth claims changed.')
    loc = value['localization']
    n, matched, unknown = (count(loc[k]) for k in ('primary_protein_rows',
        'matched_primary_test_proteins', 'unmatched_primary_reference_unknown'))
    need(matched + unknown == n and set(loc['metrics']) == set(ARMS),
         'localization cohort or fixed arms differ.')
    rows = []
    for arm, label in ARMS.items():
        levels = loc['metrics'][arm]
        need(set(levels) == {'level1', 'level2', 'level3'}, 'localization levels differ.')
        for level in ('level1', 'level2', 'level3'):
            m = levels[level]
            total, recovered, missed, extra = (count(m[k]) for k in (
                'reference_positive_labels', 'recovered_reference_positive_labels',
                'reference_positive_labels_not_recovered', 'extra_predicted_labels_truth_unknown'))
            need(recovered + missed == total and m['frozen_protein_rows'] == matched
                 and all(m[k] is None for k in ('precision', 'specificity', 'F1', 'MCC'))
                 and m['biological_false_positive_labels_assigned'] == 0,
                 'positive recovery cannot supply negative labels or precision.')
            ratio = recovered / total if total else None
            need(m['micro_positive_reference_recovery'] == ratio, 'recovery ratio differs.')
            rows.append({'arm': arm, 'label': label, 'level': level,
                         'recovered': recovered, 'reference_positive': total,
                         'recovery': ratio, 'extra_truth_unknown': extra})
    clinical = deepcopy(value['clinical'])
    need(count(clinical['matched_expert_gold_source_records']) <= count(clinical['source_records'])
         and count(clinical['matched_expert_gold_assertions']) <= count(clinical['qualified_assertions'])
         and sum(count(x) for x in clinical['projection_labels'].values()) == clinical['source_records']
         and clinical['whole_assertion_scientific_labels_unknown'] == clinical['qualified_assertions'],
         'claim projection must not become a whole-assertion truth label.')
    ppi = value['same_release_ppi']
    need(set(ppi['panels']) == set(PANELS), 'all six fixed interaction panels are required.')
    panels = []
    for name in PANELS:
        p = ppi['panels'][name]
        need(p['graph_improvement_established'] is False
             and p['new_independent_experimental_confirmation'] is False
             and p['whole_graph_biological_accuracy'] is None,
             'conditional interaction reference agreement is not whole-graph truth.')
        pair = deepcopy(p['paired_both_native_weights'])
        count(pair['pairs'])
        need(set(pair['arms']) == {'functional', 'physical'}, 'paired source arms differ.')
        for m in pair['arms'].values():
            need(count(m['scored_pairs']) == pair['pairs']
                 and count(m['positive_pairs']) + count(m['negative_pairs']) == pair['pairs'],
                 'common-pair denominators differ.')
            score = m['AUROC']
            both = m['positive_pairs'] > 0 and m['negative_pairs'] > 0
            need((not both and score is None) or
                 (both and type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 1),
                 'AUROC requires both reference classes.')
        panels.append({'panel': name, **pair})
    mito = value['mitocarta']
    need(sum(count(mito[k]) for k in ('primary_gene_gold_positive',
        'primary_gene_gold_explicit_outside_inventory', 'primary_gene_gold_unknown'))
        == count(mito['primary_gene_units']), 'mitochondrial inventory units differ.')
    return {
        'title': 'Public curator references: measured recovery and source trade-offs',
        'scope': 'Separate reference tasks with explicit coverage. Positive-reference recovery is not precision; conditional assay labels are not universal noninteraction.',
        'localization': {'primary_proteins': n, 'matched_proteins': matched,
            'reference_unknown_proteins': unknown, 'rows': rows,
            'limitations': deepcopy(loc['limitations']),
            'interpretation': 'The added location records recover additional reference labels. HPA provider reuse affects the gained labels; this is not independent experimental confirmation.'},
        'clinical': clinical,
        'ppi': {'rows': panels, 'source_identity': deepcopy(ppi['source_identity']),
                'limits': deepcopy(ppi['limits']), 'source_overlap': ppi['source_overlap']},
        'mitocarta': {k: deepcopy(mito[k]) for k in ('primary_gene_units',
            'primary_gene_gold_positive', 'primary_gene_gold_explicit_outside_inventory',
            'primary_gene_gold_unknown', 'scope', 'limits', 'metrics')},
        'sources': [{'role': 'public_reference', 'file': FILE, 'file_sha256': pin}],
        'producer_report_pins': deepcopy(value['source_report_sha256']),
        'whole_graph_biological_accuracy': None,
    }


def render_html(result):
    e = lambda v: escape(str(v), quote=True)
    def table(head, rows):
        return '<div class="table-wrap"><table><tr>' + ''.join('<th>'+e(x)+'</th>' for x in head) + '</tr>' + ''.join(
            '<tr>' + ''.join('<td>'+e(x)+'</td>' for x in row) + '</tr>' for row in rows) + '</table></div>'
    loc = result['localization']
    detailed = [r for r in loc['rows'] if r['level'] == 'level1']
    text = '<section><h2>'+e(result['title'])+'</h2><p>'+e(result['scope'])+'</p>'
    text += '<h3>Location reference recovery</h3><p>'+e(loc['matched_proteins'])+'/'+e(loc['primary_proteins'])+' proteins matched; '+e(loc['reference_unknown_proteins'])+' have no matching reference label.</p>'
    text += table(['Fixed source view', 'Detailed positive labels recovered', 'Additional outputs: truth unknown'],
                  [[r['label'], str(r['recovered'])+'/'+str(r['reference_positive']), r['extra_truth_unknown']] for r in detailed])
    text += '<p>'+e(loc['interpretation'])+'</p><details><summary>All predefined levels and source limits</summary>'
    text += table(['Source view', 'Level', 'Recovered', 'Reference positives'],
                  [[r['label'], r['level'], r['recovered'], r['reference_positive']] for r in loc['rows']])
    text += '<ul>'+''.join('<li>'+e(x)+'</li>' for x in loc['limitations'])+'</ul></details>'
    cv = result['clinical']
    text += '<h3>Human-reviewed cancer claim projections</h3><p>'+e(cv['matched_expert_gold_source_records'])+'/'+e(cv['source_records'])+' evidence records match the released human-reviewed claim and passage. All '+e(cv['qualified_assertions'])+' full clinical assertions remain unassessed; added coverage is not a whole-graph accuracy gain.</p>'
    text += '<details><summary>Clinical human review, source lineage and benchmark exposure</summary>'
    text += ''.join('<p>'+e(cv[k])+'</p>' for k in ('human_label_provenance', 'source_lineage', 'version_and_exposure'))
    text += '<ul>'+''.join('<li>'+e(x)+'</li>' for x in cv['limitations'])+'</ul></details>'
    text += '<h3>Functional versus physical source networks</h3>'
    text += table(['Fixed panel', 'Common scored pairs', 'Positive / negative labels', 'Functional AUROC', 'Physical AUROC'],
        [[r['panel'], r['pairs'], str(r['arms']['functional']['positive_pairs'])+' / '+str(r['arms']['functional']['negative_pairs']),
          *['undefined' if r['arms'][a]['AUROC'] is None else format(r['arms'][a]['AUROC'], '.6f') for a in ('functional', 'physical')]] for r in result['ppi']['rows']])
    text += '<p>Physical filtering loses supported positive interactions as well as removing negative-reference conflicts. Neither network is a universal biological pruning rule. STRING physical associations include co-complex relationships.</p>'
    text += '<details><summary>Interaction identity and source dependence</summary><pre>'+e(json.dumps(result['ppi']['source_identity'], indent=2))+'</pre><p>'+e(result['ppi']['source_overlap'])+'</p></details>'
    mito = result['mitocarta']
    text += '<h3>Mitochondrial inventory control</h3><p>'+e(mito['primary_gene_gold_positive'])+' inventory-positive genes, '+e(mito['primary_gene_gold_explicit_outside_inventory'])+' explicitly outside the inventory and '+e(mito['primary_gene_gold_unknown'])+' unknown. All fixed source views give the same inventory result; no improvement was observed.</p></section>'
    return text


def opencell_summary(raw, pin):
    """Check the separately frozen author-category sensitivity, without pooling it."""
    from .scientific_assessment import _task_tree
    need(hashlib.sha256(raw).hexdigest() == pin, 'OpenCell FILE pin differs.')
    value = _task_tree(json.loads(raw))
    need(value['format'] == 'biograph-steward.OpenCell-localization-public-aggregate.v1'
         and all(value[k] is False for k in ('admission_or_mapping_changed_after_outcomes',
             'scientific_accuracy_percentage_estimated', 'fresh_blind_reference',
             'new_independent_experiment', 'whole_graph_accuracy_established', 'graph_or_model_changed'))
         and type(value['model_calls']) is int and value['model_calls'] == 0,
         'OpenCell source separation must not become an independent accuracy claim.')
    need([p['reference_grades'] for p in value['profiles']] == [[2, 3], [3]],
         'both predefined grade profiles are required.')
    matched = count(value['identity']['reciprocal_accession_and_HGNC_ENSG_matches'])
    expected = set(ARMS) - {'A_raw_Pharos_author_coarse_control'} | {'D_native_without_HPA_or_explicit_OpenCell'}
    for profile in value['profiles']:
        need(profile['matched_proteins'] == matched and set(profile['arms']) == expected,
             'OpenCell matched cohort or fixed arms differ.')
        totals = set()
        for m in profile['arms'].values():
            total = count(m['reference_positive_labels']); totals.add(total)
            recovered = count(m['recovered_reference_positive_labels'])
            count(m['extra_predicted_labels_truth_unknown'])
            need(recovered <= total and m['micro_positive_reference_recovery'] == (recovered / total if total else None)
                 and all(m[k] is None for k in ('precision', 'specificity', 'F1')),
                 'OpenCell positive recovery cannot supply biological precision.')
        need(len(totals) == 1, 'OpenCell common label denominator differs.')
        need({x['candidate'] for x in profile['paired']} == expected - {'A_raw_Pharos_scope_qualified'},
             'OpenCell paired outcomes are incomplete.')
        for comparison in profile['paired']:
            need(sum(count(comparison[k]) for k in ('improved_proteins', 'worse_proteins', 'unchanged_proteins')) == matched,
                 'OpenCell protein transition denominator differs.')
    return {**value, 'sources': [{'role': 'opencell_localization', 'file': OPENCELL_FILE, 'file_sha256': pin}],
            'reference_sources': value['sources']}


def opencell_html(value):
    e = lambda v: escape(str(v), quote=True)
    rows = []
    names = {**ARMS, 'D_native_without_HPA_or_explicit_OpenCell': 'Native excluding HPA and explicit OpenCell references'}
    for profile in value['profiles']:
        for arm, m in profile['arms'].items():
            rows.append('<tr><td>'+e(names[arm])+'</td><td>'+e(profile['reference_grades'])+'</td><td>'+e(m['recovered_reference_positive_labels'])+'/'+e(m['reference_positive_labels'])+'</td><td>'+e(m['extra_predicted_labels_truth_unknown'])+'</td></tr>')
    return ('<section><h2>OpenCell: source-separated localization sensitivity</h2><p>'+e(value['primary_result'])
        +'</p><p>'+e(value['scope'])+' '+e(sum(value['identity']['excluded_primary_proteins'].values()))+' proteins are reference-unavailable; they are not negatives.</p><p>'+e(value['reference_unit'])+'</p><details><summary>Every fixed source view and reference grade</summary>'
        +'<div class="table-wrap"><table><tr><th>Source view</th><th>Grades</th><th>Positive labels recovered</th><th>Additional outputs: truth unknown</th></tr>'
        +''.join(rows)+'</table></div><ul>'+''.join('<li>'+e(x)+'</li>' for x in value['limitations'])
        +'</ul></details><p>Previously exposed development reference; exact tested protein sequence and hidden citation independence remain unverified.</p></section>')
