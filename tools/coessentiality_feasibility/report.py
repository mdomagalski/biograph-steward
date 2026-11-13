"""Render stored complete concordance curves without fitting or new selection."""
import argparse
from html import escape
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha, new_output
from tools.coessentiality_feasibility.prepare import sealed
from tools.reference_accuracy.design import need


def number(value):
    return 'UNKNOWN / undefined' if value is None else f'{value:.4f}'


def table(headings, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join('<th>' + escape(str(x)) + '</th>' for x in headings) + \
        '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + escape(str(v)) + '</td>' for v in row) +
        '</tr>' for row in rows) + '</tbody></table></div>'


def render(scored, output):
    scored = Path(scored).absolute(); report = sealed(scored / 'report.json')
    need(report['format'] == 'biograph-steward.coessentiality-functional-concordance.v1', 'result format differs')
    need(not any(p.is_symlink() for p in [scored, *scored.rglob('*')]), 'symlink in stored result')
    pins = {p.relative_to(scored).as_posix(): sha(p) for p in scored.rglob('*') if p.is_file() and p != scored / 'report.json'}
    need(pins == report['files'], 'stored result inventory differs')
    curves = gold_packet._read(scored / 'curves.json')
    controls = gold_packet._read(scored / 'descriptive_control_envelopes.json')
    names = [('normalized', 'Normalized source context'), ('current', 'Current-release eligibility contrast'),
             ('historical', 'Exact-historical-xref contrast')]
    primary = [[n] + [number(curves[a]['nonsyntenic'][n - 1]['enrichment']) for a, label in names]
               for n in range(1, 11)]
    meets_rule = any(v['pointwise_above_baseline_and_all_controls_at_every_N']
                     for v in report['full_curve_descriptive_assessment'].values())
    headline = ('A source contrast meets the predeclared descriptive full-curve comparison rule.' if meets_rule else
                'Source qualification did not show a consistent advantage over the fixed count and degree controls.')
    body = '<h1>Experimental functional concordance</h1><p class="lead">' + headline + '</p>'
    body += '<p>Read every curve together with its control envelopes and absolute context coverage. The project-specific descriptive rule requires pointwise superiority to normalized context and all forty own-treatment control draws at every declared N. This frozen exploratory readout does not establish scientific accuracy, physical binding, causal mechanism or prediction benefit.</p>'
    body += '<p><b>Fixed primary frame:</b> ' + str(report['query_genes']) + ' genes, ' + str(report['pair_scope_counts']['nonsyntenic']) + ' different-chromosome pairs, all N=1…10. Native P availability: ' + escape(str(report['native_p_status_counts'])) + '. Every query remains in the denominator, including queries without shared source context. Native P is a two-sided association-test output, not an edge truth probability or a credible negative label.</p>'
    body += '<h2>Complete primary curve</h2><p>Observed shared-context hits divided by query-matched expected hits. Higher enrichment alone is insufficient when controls show comparable enrichment.</p>'
    body += table(['N'] + [label for a, label in names], primary)
    for treatment, label in names[1:]:
        body += '<h2>' + escape(label) + ': all frozen controls</h2><p>Twenty count-matched and twenty measured-frame degree-preserving draws. Each cell is minimum / median / maximum. These ranges are not confidence intervals; no uniform-null, mixing or significance claim is made.</p>'
        rows = []
        for i in range(10):
            rows.append([i + 1] + [' / '.join(number(controls[treatment][kind]['nonsyntenic'][i][v])
                for v in ['minimum', 'median', 'maximum']) for kind in ['count', 'degree']])
        body += table(['N', 'Count-matched draws', 'Degree-preserving draws'], rows)
    body += '<details><summary>Absolute hit fractions and denominators</summary><p>Enrichment must be read together with absolute context coverage. Each complete primary N has fixed-query-count×N selected query-partner slots; opposite directions are query slots, not independent experiments. Reference-incomplete points remain unscorable.</p>'
    body += table(['N'] + [label for a, label in names], [[n] + [number(curves[a]['nonsyntenic'][n - 1]['observed_hit_fraction'])
        for a, label in names] for n in range(1, 11)]) + '</details>'
    body += '<h2>All arms and declared diagnostic scopes</h2><p>Every one of the ' + str(len(curves)) + ' arms is preserved. Prior/global controls are diagnostic because degree/count matching did not survive the fixed measured-gene projection. Sign-restricted and same-chromosome summaries condition on reference-available queries and cannot establish primary success. Undefined points remain visible.</p>'
    for scope in next(iter(curves.values())):
        body += '<details><summary>' + escape(scope) + ': complete curves</summary>'
        body += table(['Arm'] + list(range(1, 11)), [[arm] + [number(p['enrichment']) for p in scopes[scope]]
            for arm, scopes in curves.items()]) + '</details>'
    body += '<h2>Scope and reproducibility</h2><ul><li>Published pan-cancer DepMap18Q3 fitness associations; not a colorectal-cancer-specific reference.</li><li>Author two-sided P ranks, lexical native-symbol orientation, fractional boundary ties and common measurement availability were frozen before numeric decoding.</li><li>Source-context links are exact versioned memberships projected through reviewed gene-product relationships, not gene/protein identity.</li><li>Indirect source reuse and GO-assisted preprocessing remain disclosed; missing annotations are never biological negatives.</li><li>Pre-value scientific and later transport seals are preserved separately. Any technical repairs and raw-byte exposure are documented in the bound frozen/capture receipts; they never select new source arms or outcomes.</li><li>ETags validate server representations; per-range SHA256 hashes do not constitute complete matrix hashes.</li></ul>'
    body += '<p>Methods: <a href="https://doi.org/10.1038/s41588-021-00840-z">Wainberg et al.</a>; <a href="https://github.com/kundajelab/coessentiality">author code</a>; <a href="https://github.com/hetio/xswap">native XSwap controls</a>. No FDR threshold was reconstructed.</p>'
    body += '<p class="pin">Stored result seal: ' + escape(report['content_sha256']) + '</p>'
    out = new_output(output, scored)
    (out / 'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Frozen co-functionality comparison</title><style>body{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:35px auto;padding:0 20px;color:#203040;background:#f9fafb}h1{font-size:30px}h2{font-size:21px;margin-top:30px}.lead{font-size:21px;font-weight:600;color:#734b18}.scroll{overflow:auto}table{border-collapse:collapse;background:white;width:100%;font-variant-numeric:tabular-nums;margin:15px 0}th,td{border:1px solid #d8dfe5;padding:7px 10px;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{background:#eaf0f5}details{margin:18px 0;padding:12px;border:1px solid #d8dfe5;background:white}summary{cursor:pointer;font-weight:600}.pin{font-size:12px;overflow-wrap:anywhere}</style>' + body + '</html>', encoding='utf-8')
    need(pins == {p.relative_to(scored).as_posix(): sha(p) for p in scored.rglob('*') if p.is_file() and p != scored / 'report.json'},
         'result files changed during rendering')
    receipt = {'format': 'biograph-steward.coessentiality-readable-result.v1', 'created_at': utcnow(),
        'stored_result_content_sha256': report['content_sha256'], 'stored_result_report_file_sha256': sha(scored / 'report.json'),
        'arm_count_rendered': len(curves), 'scope_count_rendered': len(next(iter(curves.values()))),
        'all_N_rendered': list(range(1, 11)), 'new_statistical_estimator_or_outcome_selection': False,
        'implementation_sha256': sha(__file__), 'files': {'report.html': sha(out / 'report.html')}}
    receipt['content_sha256'] = digest(receipt); write_json(out / 'report.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scored', type=Path, required=True); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); print(render(args.scored, args.out)['content_sha256'])


if __name__ == '__main__':
    main()
