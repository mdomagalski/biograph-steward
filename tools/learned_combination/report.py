"""Small, self-contained aggregate report; no reference rows are published."""
import argparse
import html
import json
from pathlib import Path


def number(value):
    return 'unavailable' if value is None else f'{value:.6f}'


def render(results, fitted, destination):
    result = json.loads(Path(results).read_text())
    fit = json.loads(Path(fitted).read_text())
    arms = result['protocol']['final']['arms']
    primary = result['strata']['PK/molecular_function']
    verdict = ('The learned mixture passed the declared primary comparison against all four controls.'
               if result['primary_success'] else
               'The learned mixture did not establish improvement over all four controls on the declared primary comparison.')
    lines = ['# Focused learned-combination comparison', '', verdict, '',
        'This measures agreement with later curator annotations for a bounded set of human proteins. '
        'It does not estimate whole-graph biological accuracy.', '',
        '## Design', '',
        'Adapted DeepGOPlus score mixing: `alpha × LocalPlus + (1−alpha) × DeepGO-SE`. '
        'A separate alpha was selected per GO aspect from 0.0–1.0 in steps of 0.1, '
        'using ordinary native development micro-Fmax. Fitting used the previously consumed CAFA5 PK reference '
        'after excluding all 7,401 LAFA target accessions and identical-sequence duplicates. '
        'The native propagation, ontology masks and known-term exclusions remain in use.', '',
        f"Development proteins: **{fit['development_target_count']:,}**. "
        f"Sequence-compatible later-reference forecast targets: **{result['exact_sequence_compatible_forecast_targets']:,}**. "
        'All five final forecasts were sealed before opening new LAFA reference terms or its evaluation-only term mask.', '',
        '| GO aspect | Selected LocalPlus weight | Development micro-Fmax |',
        '|---|---:|---:|']
    for ns, entry in fit['selections'].items():
        lines.append(f"| {ns} | {entry['alpha']:.1f} | {number(entry['development_micro_fmax'])} |")
    lines += ['', '## Later temporal measurement', '',
        '**Declared primary endpoint: PK molecular function.** All other settings/aspects are secondary. '
        'Values are ordinary micro-Fmax on the native .001–.999 threshold grid. '
        'The annotation control uses the author’s unchanged nonexperimental baseline and the September 4, 2025 human GOA snapshot.', '',
        '| Setting / GO aspect | Reference proteins | ' + ' | '.join(arms) + ' |',
        '|---|---:|' + '---:|' * len(arms)]
    for key, row in result['strata'].items():
        values = [number(row['methods'].get(a, {}).get('native_micro_fmax')) for a in arms]
        eligible = row['methods'].get('learned_mix', {}).get('eligible_proteins', 'unavailable')
        lines.append('| ' + key + ' | ' + str(eligible) + ' | ' + ' | '.join(values) + ' |')
    lines += ['', '## Primary paired comparisons', '',
              '| Learned mixture minus control | Point difference | Paired 95% interval |',
              '|---|---:|---:|']
    boot = primary.get('bootstrap', {})
    for item in boot.get('comparisons', []):
        method = item['comparator']
        delta = primary['methods']['learned_mix']['native_micro_fmax'] - primary['methods'][method]['native_micro_fmax']
        lo, hi = item['paired_95_percentile_interval']
        lines.append(f'| {method} | {delta:+.6f} | [{lo:+.6f}, {hi:+.6f}] |')
    secondary_rows = []
    for key in ('PK/biological_process', 'PK/cellular_component'):
        row = result['strata'].get(key, {})
        for item in row.get('bootstrap', {}).get('comparisons', []):
            method = item['comparator']
            delta = row['methods']['learned_mix']['native_micro_fmax'] - row['methods'][method]['native_micro_fmax']
            lo, hi = item['paired_95_percentile_interval']
            secondary_rows.append([key, method, f'{delta:+.6f}', f'[{lo:+.6f}, {hi:+.6f}]'])
    lines += ['', 'Intervals use 2,000 paired whole-protein resamples, seed 20261113. '
        'Per-protein contributions must reproduce every ordinary native curve column within 1e-12 before resampling. '
        'These are conditional, unadjusted descriptive intervals; proteins can share studies and graph neighborhoods.', '',
        '## Secondary PK results', '',
        'These contrasts were declared secondary and do not replace the primary endpoint. '
        'The cellular-component fitter selected the same 50/50 arithmetic as the equal-mixture control; '
        'any gain over a parent there is a mixing benefit, not evidence that learning the weight helped.', '',
        '| Setting / GO aspect | Learned mixture minus control | Point difference | Paired 95% interval |',
        '|---|---|---:|---:|']
    lines += ['| ' + ' | '.join(row) + ' |' for row in secondary_rows]
    lines += ['', 'All NK strata have no released reference rows inside this fixed human forecast intersection; '
        'they are unavailable, not scored zeros. LK populations contain only 9–19 eligible proteins, '
        'so their results provide limited support for broader transfer.', '',
        '## Interpretation and limits', '',
        'This is one global weight per aspect, not a conditional expert-routing or full stacking model. '
        'The 50/50 control separates a benefit from mixing from a benefit from fitting. '
        'A selected endpoint weight means fitting chose a parent; it is not a distinct ensemble gain. '
        'The contemporary annotation baseline is deliberately stronger than a 2023-only control.', '',
        'The later reference is external and temporally defined, but not fully developer-blind: '
        'newer GOA material was previously processed for source quality checks. '
        'Combiner-fit accessions and identical sequences are excluded from the final target set; '
        'near-homology separation and base-checkpoint training independence are not established. '
        'Incomplete annotation is scored by the fixed benchmark convention and is not negative biological truth. '
        'Information-accretion-weighted metrics are unavailable because the exact author IA file was not acquired. '
        'No graph or application default is automatically changed.', '',
        '## Sources', '',
        '- [DeepGOPlus primary method](https://doi.org/10.1093/bioinformatics/btz595) '
        'and [official source revision](https://github.com/bio-ontology-research-group/deepgoplus/tree/8e8dcb1be7f1bfd5beed11893dacc4132213ea19). '
        'Our component models, alpha grid and objective are declared adaptations.',
        '- [LAFA author release](https://github.com/FriedbergLab/CAFA_forever/tree/c3fd5b9a5226348d88b9efadddb3214c803b80c4/data/releases/Sep_2025_Mar_2026).',
        '- [Pinned native evaluator](https://github.com/claradepaolis/CAFA-evaluator-PK/tree/e386b085e204ccfbd75a4f52c1a8b25987d8b465).',
        '- [GO T0 ontology](https://release.geneontology.org/2025-07-22/ontology/go-basic.obo) '
        'and [GOA T0 source](https://ftp.ebi.ac.uk/pub/databases/GO/goa/old/HUMAN/goa_human.gaf.229.gz).', '']
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    markdown = '\n'.join(lines)
    (destination / 'report.md').write_text(markdown)
    def table(headers, rows):
        return ('<div class="table"><table><thead><tr>'
                + ''.join('<th>' + html.escape(str(v)) + '</th>' for v in headers)
                + '</tr></thead><tbody>'
                + ''.join('<tr>' + ''.join('<td>' + html.escape(str(v)) + '</td>' for v in row)
                          + '</tr>' for row in rows) + '</tbody></table></div>')
    body = '<h1>Focused learned-combination comparison</h1><p class="verdict">' + html.escape(verdict) + '</p>'
    body += '<p>Agreement with later curator annotations in a bounded human cohort. Whole-graph biological accuracy is outside this measurement.</p>'
    body += '<h2>Fitted weights</h2><p>LocalPlus weight α; DeepGO-SE weight 1−α. Development proteins: ' + str(fit['development_target_count']) + '.</p>'
    body += table(['GO aspect', 'α', 'Development micro-Fmax'],
                  [[ns, f"{entry['alpha']:.1f}", number(entry['development_micro_fmax'])]
                   for ns, entry in fit['selections'].items()])
    body += '<h2>Later temporal measurement</h2><p>Primary endpoint: <strong>PK molecular function</strong>. Other rows are secondary. All five forecasts were sealed before reference-term decoding.</p>'
    body += table(['Setting / aspect', 'Reference proteins'] + arms,
        [[key, row['methods'].get('learned_mix', {}).get('eligible_proteins', 'unavailable')]
         + [number(row['methods'].get(a, {}).get('native_micro_fmax')) for a in arms]
         for key, row in result['strata'].items()])
    body += '<h2>Primary paired comparisons</h2>'
    body += table(['Learned minus control', 'Point difference', 'Paired 95% interval'],
        [[item['comparator'],
          f"{primary['methods']['learned_mix']['native_micro_fmax'] - primary['methods'][item['comparator']]['native_micro_fmax']:+.6f}",
          '[' + ', '.join(f'{v:+.6f}' for v in item['paired_95_percentile_interval']) + ']']
         for item in boot.get('comparisons', [])])
    body += '<h2>Secondary PK contrasts</h2><p>Cellular component uses the same 50/50 weight as the equal-mixture control. Gains there support mixing, not a separate learned-weight advantage.</p>'
    body += table(['Setting / aspect', 'Learned minus control', 'Point difference', 'Paired 95% interval'], secondary_rows)
    body += '<p>NK reference rows are absent from this fixed intersection. LK groups have only 9–19 eligible proteins.</p>'
    body += ('<p>2,000 paired protein resamples; conditional, unadjusted descriptive intervals. '
             'A weight at 0 or 1 selects a parent and does not establish an ensemble gain.</p>'
             '<h2>Scope and provenance</h2><p>Retrospective external temporal reference, not fully developer-blind. '
             'Exact accession/full-sequence exclusions do not establish homology or base-model training independence. '
             'No IA-weighted metric, complete biological-negative reference or automatic application adoption.</p>'
             '<p><a href="report.md">Full methods, sources and limitations</a></p>')
    document = ('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Focused learned-combination comparison</title>'
        '<style>body{max-width:1250px;margin:36px auto;padding:0 24px;color:#19323c;'
        'font:15px/1.6 system-ui;background:#fafcfd}h1{line-height:1.2}h2{margin-top:32px}'
        '.verdict{background:#e7eff4;padding:18px;border-left:5px solid #28728d}'
        '.table{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}'
        'td,th{padding:9px 10px;border-bottom:1px solid #d4dfe4;text-align:right}'
        'td:first-child,th:first-child{text-align:left}th{background:#edf3f5}'
        'tr:hover{background:#f0f5f7} @media print{body{margin:0;max-width:none}}</style>' + body + '</html>')
    (destination / 'report.html').write_text(document)
    return markdown


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results', required=True)
    p.add_argument('--fitted', required=True)
    p.add_argument('--destination', required=True)
    a = p.parse_args()
    print(render(**vars(a)))


if __name__ == '__main__':
    main()
