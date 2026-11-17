"""Render every stored prospective-transfer curve without new scientific selection."""
import argparse
from html import escape
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.reference_accuracy.design import need
from tools.coessentiality_transfer.prepare import inventory, sealed
from tools.coessentiality_transfer.evaluate import FORMAT
from tools.coessentiality_feasibility.report import table, number


def render(scored, output):
    scored = Path(scored).absolute(); code = sha(__file__); report_pin = sha(scored / 'report.json')
    report = sealed(scored / 'report.json')
    need(report['format'] == FORMAT and report['fixed_queries'] == 128 and report['source_arms'] == 42
         and report['N'] == list(range(1, 11)), 'stored prospective result profile differs')
    need(not any(p.is_symlink() for p in [scored, *scored.rglob('*')]), 'symlink in result')
    pins = inventory(scored); need(pins == report['files'], 'stored result inventory differs')
    curves = gold_packet._read(scored / 'curves.json')
    envelopes = gold_packet._read(scored / 'control_envelopes.json')
    need(len(curves) == 42 and all(len(v[m]) == 10 for v in curves.values()
         for m in ['RA', 'binary_diagnostic']), 'complete stored curve universe differs')
    met = report['full_curve_descriptive_assessment']['RA']['project_descriptive_full_curve_rule_met']
    lead = ('The historical-context view met the fixed descriptive full-curve rule in this new-gene sample.'
            if met else 'The historical-context view did not meet the fixed descriptive full-curve rule in this new-gene sample.')
    body = '<h1>Prospective transfer to 128 new genes</h1><p class="lead">' + lead + '</p>'
    body += '<p>This tests transfer of the previously selected interpretation method to newly sampled genes within the <b>same published experimental reference</b>. It is not an independent experiment, scientific-accuracy estimate, prediction benchmark or production-pruning decision. The complete fixed curves and absolute affinities remain visible below.</p>'
    coverage = report['source_only_coverage']
    zero_wiki = report['fixed_queries'] - coverage['normalized']['genes_with_memberships']
    body += '<h2>Fixed sample and source coverage</h2><p>One metadata-only sample of 128 genes was drawn without replacement from a reviewed, uniquely mapped subset of 17,231 native genes (seed 2026111302; inclusion probability 128/17231). Old evaluation genes and their current HGNC/product identities were excluded. No replacement or pathway/fitness/TDL selection was permitted. All required Pharos identities and pathway responses were complete, including ' + str(zero_wiki) + ' genes with valid zero Wiki rows. Other evidence families were explicitly unretrieved.</p>'
    body += table(['Source view', 'Gene/version links', 'Versioned models', 'Genes with links',
                   'Primary shared-context pairs', 'Queries with primary context', 'Zero-context queries retained'],
        [[arm] + [coverage[arm][key] for key in ['membership_links', 'model_nodes', 'genes_with_memberships',
          'co_context_pairs_primary', 'queries_with_primary_co_context_partner', 'zero_context_queries_retained']]
         for arm in ['normalized', 'historical']])
    body += '<p>The historical feature view omits unresolved source encoding from this research feature set; those records remain UNKNOWN evidence and are not false biological assertions. Its effective observed context is sparse: ' + str(coverage['historical']['queries_with_primary_co_context_partner']) + ' queries have a nonsyntenic shared-context partner and all ' + str(coverage['historical']['zero_context_queries_retained']) + ' zero-context queries remain in the fixed denominator.</p>'
    body += '<h2>Complete primary RA curve</h2><p>The reference ranks unsigned native two-sided GLS P within the fixed 128-gene sample, among different-chromosome partners. It does not identify genomewide top partners or significance-defined positive labels. Every N uses all 128 queries, fractional boundary ties and a query-matched expected affinity. Native P and affinity are not probabilities of edge truth.</p>'
    body += table(['N', 'Normalized O/E', 'Historical O/E', 'Historical exceeds baseline and all 40 controls'],
        [[i + 1, number(curves['normalized']['RA'][i]['enrichment']),
          number(curves['historical']['RA'][i]['enrichment']),
          report['full_curve_descriptive_assessment']['RA']['points'][i]['historical_exceeds_normalized_and_all_40_draws']]
         for i in range(10)])
    body += '<h2>Absolute affinity and expected background</h2><p>Relative enrichment can rise when expected affinity falls. These absolute means per selected query-partner slot must accompany the ratio; a higher ratio does not mean more observed evidence.</p>'
    body += table(['N', 'Normalized observed', 'Normalized expected', 'Historical observed', 'Historical expected'],
        [[i + 1] + [number(curves[arm]['RA'][i][key]) for arm in ['normalized', 'historical']
                    for key in ['observed_mean_RA_per_slot', 'expected_mean_RA_per_slot']]
         for i in range(10)])
    body += '<h2>All fixed control draws</h2><p>Twenty count-matched source subsets and twenty native-XSwap controls preserve the treatment link count or both full-frame degree vectors. All seeds were frozen before new reference capture. These minimum / median / maximum ranges are descriptive control distributions, not confidence intervals, independent biological replicates or significance tests. The project rule requires historical O/E to exceed baseline and every own control by more than 1e-12 at all ten N.</p>'
    body += table(['N', 'Count controls min / median / max', 'Degree controls min / median / max'],
        [[i + 1] + [' / '.join(number(envelopes['RA'][kind][i][key])
            for key in ['minimum', 'median', 'maximum']) for kind in ['count', 'degree']]
         for i in range(10)])
    for metric, label in [('RA', 'Primary RA'), ('binary_diagnostic', 'Binary shared context: diagnostic only')]:
        body += '<details><summary>' + label + ': every arm and every N</summary>'
        body += table(['Arm'] + list(range(1, 11)), [[arm] + [number(p['enrichment']) for p in data[metric]]
                                                   for arm, data in curves.items()])
        body += '<details><summary>Every absolute sum and availability denominator</summary>'
        keys = (['observed_weighted_sum', 'expected_weighted_sum', 'fixed_queries', 'available_queries']
                if metric == 'RA' else ['observed_hits', 'expected_hits', 'query_frame', 'reference_available_queries'])
        body += table(['Arm', 'N', 'Status'] + keys, [[arm, p['N'], p['status']] +
            [number(p[k]) if isinstance(p[k], float) or p[k] is None else p[k] for k in keys]
            for arm, data in curves.items() for p in data[metric]]) + '</details></details>'
    body += '<h2>Scope and reproducibility</h2><ul>'
    for item in report['limitations']:
        body += '<li>' + escape(item) + '</li>'
    body += '</ul><p>Pre-value metadata, source/history, control, code and statistical-contract seals were independently reviewed before the new block was captured. Earlier 92-column captures contained old–new raw bytes but not this new–new block. Source-only degree/affinity algebra was inspected during coverage review; reference outcomes remained closed. Complete HTTP ranges, server validators and per-payload hashes are preserved, without inventing a full-matrix hash.</p>'
    body += '<p>Native P status: ' + escape(str(report['native_P_status_counts'])) + '; native sign status: ' + escape(str(report['native_sign_status_counts'])) + '. Reverse-direction values are preserved diagnostically; the fixed author-style orientation was not selected after outcomes.</p>'
    body += '<p>Methods: <a href="https://doi.org/10.1038/s41588-021-00840-z">Wainberg et al.</a>; <a href="https://github.com/kundajelab/coessentiality">author code</a>; <a href="https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.link_prediction.resource_allocation_index.html">native resource allocation</a>; <a href="https://github.com/hetio/xswap">native XSwap</a>. No new fitness fit, FDR reconstruction or model inference was used.</p>'
    for label, key in [('Source/control freeze', 'frozen_source_control_content_sha256'),
                       ('Native capture', 'native_capture_content_sha256'), ('Stored result', 'content_sha256')]:
        body += '<p class="pin">' + label + ': ' + escape(report[key]) + '</p>'
    out = new_output(output, scored)
    style = 'body{font:16px/1.5 system-ui,sans-serif;max-width:1150px;margin:35px auto;padding:0 20px;color:#203040;background:#f9fafb}h1{font-size:30px}h2{font-size:21px;margin-top:30px}.lead{font-size:21px;font-weight:600;color:#734b18}.scroll{overflow:auto}table{border-collapse:collapse;background:white;width:100%;font-variant-numeric:tabular-nums;margin:15px 0}th,td{border:1px solid #d8dfe5;padding:7px 10px;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{background:#eaf0f5}details{margin:18px 0;padding:12px;border:1px solid #d8dfe5;background:white}summary{cursor:pointer;font-weight:600}.pin{font-size:12px;overflow-wrap:anywhere}'
    (out / 'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Prospective gene transfer</title><style>' + style + '</style>' + body + '</html>', encoding='utf-8')
    need(inventory(scored) == pins and sha(scored / 'report.json') == report_pin and sha(__file__) == code,
         'result/renderer changed during render')
    receipt = {'format': 'biograph-steward.prospective-gene-transfer-readable.v1', 'created_at': utcnow(),
        'stored_result_content_sha256': report['content_sha256'], 'stored_result_report_file_sha256': report_pin,
        'arm_count_rendered': len(curves), 'all_N_rendered': list(range(1, 11)), 'metrics': ['RA', 'binary_diagnostic'],
        'new_statistical_estimator_or_outcome_selection': False, 'implementation_sha256': code,
        'files': {'report.html': sha(out / 'report.html')}}
    receipt['content_sha256'] = digest(receipt); write_json(out / 'report.json', receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scored', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); print(render(a.scored, a.out)['content_sha256'])


if __name__ == '__main__':
    main()
