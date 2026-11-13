"""Readable stored RA curves; no new weights, fitting or outcome selection."""
import argparse
from html import escape
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.coessentiality_feasibility.resource_allocation import checked_report, SCORED
from tools.coessentiality_feasibility.report import table, number
from tools.reference_accuracy.design import need


def render(scored, output):
    scored = Path(scored).absolute(); report = checked_report(scored)
    need(report['format'] == SCORED, 'RA result format differs')
    curves = gold_packet._read(scored / 'curves.json'); envelopes = gold_packet._read(scored / 'control_envelopes.json')
    source_pin = sha(scored / 'report.json')
    names = [('normalized', 'Normalized source'), ('current', 'Current-release contrast'), ('historical', 'Historical-xref contrast')]
    passing = [a for a, r in report['full_curve_descriptive_assessment'].items() if r['project_descriptive_full_curve_rule_met']]
    headline = ('A bounded exploratory functional-concordance signal was found.' if passing else
                'No consistent exploratory functional-concordance advantage was found.')
    body = '<h1>Degree-aware source context</h1><p class="lead">' + headline + '</p>'
    body += '<p><b>This is a consumed-reference extension.</b> The earlier binary-context comparison did not show consistent control superiority. This separate RA contract was then frozen before new weights/results. Its results are exploratory, not independent confirmation, calibrated scientific accuracy or evidence for automatic biological pruning.</p>'
    body += '<p>Native NetworkX ' + escape(report['native_NetworkX']['version']) + ' resource allocation weights each shared exact-version model by inverse observed model degree. Degree is fixed in each full 92-gene arm, not per query and not full biological pathway size. RA is an uncalibrated affinity that may exceed one; zero is not a biological negative.</p>'
    body += '<p><b>Fixed frame:</b> ' + str(report['query_genes']) + ' genes, ' + str(report['primary_pairs']) + ' nonsyntenic pairs, ' + str(report['source_arms']) + ' unchanged arms, all N=1…10. Original native GLS ranks and fractional boundary ties are reused; RA does not rerank the experimental reference. All queries, including zero-context queries, remain in the denominator.</p>'
    body += '<h2>Complete observed/expected weighted-context curve</h2>'
    body += table(['N'] + [name for a, name in names], [[n] + [number(curves[a][n - 1]['enrichment']) for a, name in names]
        for n in report['N']])
    body += '<p>The project-specific descriptive full-curve rule is met by: <b>' + escape(', '.join(passing) or 'neither contrast') + '</b>. It requires every N to exceed normalized and all forty own-treatment count/degree draws. It is not a significance test. The complete absolute scores below matter: greater enrichment can result from a larger reduction in expected background than observed score.</p>'
    for treatment, label in names[1:]:
        body += '<h2>' + escape(label) + ': all fixed controls</h2><p>Minimum / median / maximum over twenty draws per control type. These are descriptive ranges, not confidence intervals or a calibrated null distribution.</p>'
        body += table(['N', 'Count-matched draws', 'Degree-preserving draws'], [[n] + [' / '.join(
            number(envelopes[treatment][kind][n - 1][field]) for field in ['minimum', 'median', 'maximum'])
            for kind in ['count', 'degree']] for n in report['N']])
    for key, title in [('observed_mean_RA_per_slot', 'Observed mean RA per selected reference slot'),
                       ('expected_mean_RA_per_slot', 'Expected mean RA per eligible background slot')]:
        body += '<h2>' + title + '</h2>'
        body += table(['N'] + [name for a, name in names], [[n] + [number(curves[a][n - 1][key]) for a, name in names]
            for n in report['N']])
    body += '<details><summary>Every arm and every N</summary><p>Legacy global controls are preserved as diagnostics; measured-frame count/degree controls are the declared comparators.</p>'
    body += table(['Arm'] + report['N'], [[arm] + [number(p['enrichment']) for p in rows] for arm, rows in curves.items()]) + '</details>'
    body += '<h2>What this supports</h2><p>This can support further evaluation of a degree-aware contextual ranking or source-inspection feature. It does not mark source assertions true/false, change the production graph, establish physical binding or infer a CRC-specific mechanism. The experimental reference is historical pan-cancer fitness association. Fresh task-matched validation would be needed for a stronger biological-improvement claim.</p>'
    body += '<ul>' + ''.join('<li>' + escape(line) + '</li>' for line in report['limitations']) + '</ul>'
    body += '<p>Sources: <a href="https://networkx.org/documentation/3.7/reference/algorithms/generated/networkx.algorithms.link_prediction.resource_allocation_index.html">native RA implementation</a>; <a href="https://doi.org/10.1140/epjb/e2009-00335-8">RA paper</a>; <a href="https://doi.org/10.1038/s41588-021-00840-z">Wainberg experimental reference</a>.</p>'
    body += '<p class="pin">RA freeze: ' + escape(report['frozen_RA_content_sha256']) + '<br>Result: ' + escape(report['content_sha256']) + '<br>Previously consumed binary result: ' + escape(report['already_consumed_binary_result']) + '</p>'
    out = new_output(output, scored)
    (out / 'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Exploratory RA functional concordance</title><style>body{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:35px auto;padding:0 20px;color:#203040;background:#f9fafb}h1{font-size:30px}h2{font-size:21px;margin-top:30px}.lead{font-size:21px;font-weight:600;color:#285e4b}.scroll{overflow:auto}table{border-collapse:collapse;background:white;width:100%;font-variant-numeric:tabular-nums;margin:15px 0}th,td{border:1px solid #d8dfe5;padding:7px 10px;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{background:#eaf0f5}details{margin:18px 0;padding:12px;border:1px solid #d8dfe5;background:white}summary{cursor:pointer;font-weight:600}.pin{font-size:12px;overflow-wrap:anywhere}</style>' + body + '</html>', encoding='utf-8')
    checked_report(scored); need(sha(scored / 'report.json') == source_pin, 'RA source report changed during rendering')
    receipt = {'format': 'biograph-steward.exploratory-RA-readable-result.v1', 'created_at': utcnow(),
        'stored_result_content_sha256': report['content_sha256'], 'stored_result_report_file_sha256': source_pin,
        'all_arms_rendered': len(curves), 'all_N_rendered': report['N'], 'new_weights_or_outcome_selection': False,
        'implementation_sha256': sha(__file__), 'files': {'report.html': sha(out / 'report.html')}}
    receipt['content_sha256'] = digest(receipt); write_json(out / 'report.json', receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scored', required=True, type=Path); p.add_argument('--out', required=True, type=Path)
    a = p.parse_args(); print(render(a.scored, a.out)['content_sha256'])


if __name__ == '__main__':
    main()
