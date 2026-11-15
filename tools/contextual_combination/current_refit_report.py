# SPDX-License-Identifier: GPL-3.0-only
"""Aggregate-only publication of the fixed, consumed-reference BP refit.

This adapter reads a completed JSON assessment, including its embedded private
fields, then projects an explicit scalar allowlist. It opens no reference-row,
forecast-matrix or per-protein contribution files. Embedded draw vectors remain
unpublished; no scientific endpoint, interval, success gate or model choice is
computed here.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path

from .annotation_prior_report import (LABELS as PREVIOUS_LABELS, FLAGS, SETTINGS,
    VIEWS, numeric, pair, pin, public_method, number, table, require)


NS = 'biological_process'
REFIT = 'current_T0_positive_union_context_refit'
UNION_LP = 'retained_and_current_curated_LocalPlus'
UNION_PRIOR = 'T0_nonexperimental_plus_retained_curated_prior'
NEW_ARMS = (REFIT, UNION_LP, UNION_PRIOR)
LABELS = {**PREVIOUS_LABELS,
    REFIT: 'Context GCN — current-T0 positive-union refit',
    UNION_LP: 'LocalPlus — retained and current curated seed union',
    UNION_PRIOR: 'Direct prior — current nonexperimental + retained curated annotations'}
SOURCE_COMPARATORS = ('localplus', 'localplus_updated_seeds', 'localplus_T0_curated',
                     'validation_selected_context', 'native_T0_nonexperimental')
OVERVIEW = ('localplus', 'validation_selected_context', 'localplus_T0_curated', UNION_LP,
            UNION_PRIOR, REFIT, 'native_T0_nonexperimental')
PLAN_SHA = '8128b0c3cbda794cb8cd75b711609cfed1f1a150ef81ba3e90339cd4815ecca9'
PREVIOUS_REPORT_SHA = '76189617f4285a9b7f8ff253280642849ca1a117d80901b893c260e420601d9d'


def expected_pairs():
    """Validate the fixed declared contrast table; compute no comparisons."""
    return ([(REFIT, arm) for arm in (*PREVIOUS_LABELS, UNION_LP, UNION_PRIOR)]
            + [(arm, comparator) for arm in (UNION_LP, UNION_PRIOR) for comparator in SOURCE_COMPARATORS]
            + [(UNION_LP, UNION_PRIOR)])


def public_bootstrap(boot):
    if boot.get('status') == 'unavailable':
        return {'status': 'unavailable', 'interval_claimed': False}
    require(boot.get('draws') == 2000 and boot.get('seed') == 20261113
            and boot.get('original_native_gated_draws_reused_without_recomputation') is True
            and boot.get('development_followup_on_consumed_reference') is True
            and boot.get('independent_confirmation') is False
            and boot.get('new_success_gate_or_model_selection') is False,
            'the original paired consumed-reference design must be preserved.')
    require(set(boot['scores']) == set(LABELS), 'every original and new method must retain its saved interval.')
    comparisons = boot['comparisons']; expected = expected_pairs()
    keys = [(row.get('candidate'), row.get('comparator')) for row in comparisons]
    require(len(keys) == len(expected) == len(set(keys)) and set(keys) == set(expected),
            'all fixed contrasts, including losses, must remain visible.')
    count = boot['raw_proteins']
    require(type(count) is int and count > 0, 'invalid full paired protein frame.')
    out = {'draws': 2000, 'seed': 20261113, 'raw_proteins': count,
           'original_native_gated_draws_reused_without_recomputation': True,
           'scores': {}, 'comparisons': []}
    for arm in LABELS:
        row = boot['scores'][arm]
        out['scores'][arm] = {'bootstrap_mean': numeric(row['bootstrap_mean']),
            'bootstrap_95_percentile_interval': pair(row['bootstrap_95_percentile_interval'])}
    by_pair = {(row['candidate'], row['comparator']): row for row in comparisons}
    for key in expected:
        row = by_pair[key]; fraction = numeric(row['fraction_draws_above_zero'])
        require(0 <= fraction <= 1, 'invalid saved bootstrap fraction.')
        out['comparisons'].append({'candidate': key[0], 'comparator': key[1],
            'difference_mean': numeric(row['difference_mean']),
            'paired_95_percentile_interval': pair(row['paired_95_percentile_interval']),
            'fraction_draws_above_zero': fraction})
    return out


def aggregate(raw):
    require(raw.get('format') == 'biograph-steward.current-refit-development-assessment.v1'
            and all(raw.get(k) is v for k, v in FLAGS.items()),
            'only the completed fixed consumed-reference development format is accepted.')
    plan_file = Path(__file__).with_name('current_refit_protocol.json')
    require(hashlib.sha256(plan_file.read_bytes()).hexdigest() == raw.get('plan_sha256') == PLAN_SHA,
            'publication and assessment must use the same frozen development plan.')
    plan = json.loads(plan_file.read_text())
    require(raw['original_report_sha256'] == plan['original_raw_report_sha256']
            and raw['previous_development_report_sha256'] == PREVIOUS_REPORT_SHA
            and raw['original_public_summary_sha256'] == plan['original_public_summary_sha256']
            and raw['original_forecast_seal_sha256'] == plan['original_forecast_seal_sha256'],
            'the original study or preceding fixed development source changed.')
    require(raw['target_count'] == 3300 and raw['new_arm_scopes'] == {a: [NS] for a in NEW_ARMS},
            'complete fixed BP-only scope required.')
    require(set(raw['views']) == set(VIEWS), 'both ontology views must remain visible.')
    source = plan['source_adaptation']
    out = {'format': 'biograph-steward.current-refit-development-public.v1', **FLAGS,
        'target_count': 3300, 'namespace': NS,
        'original_report_sha256': pin({'sha256': raw['original_report_sha256']}),
        'previous_development_report_sha256': PREVIOUS_REPORT_SHA,
        'original_public_summary_sha256': pin({'sha256': raw['original_public_summary_sha256']}),
        'original_forecast_seal_sha256': pin({'sha256': raw['original_forecast_seal_sha256']}),
        'development_plan_sha256': PLAN_SHA,
        'previous_method_count': len(PREVIOUS_LABELS), 'new_fixed_method_count': len(NEW_ARMS),
        'total_declared_method_count': len(LABELS), 'declared_methods': list(LABELS),
        'source_scope': {'fitting_proteins': 4040,
            'historical_positive_memberships_retained': source['expected_original_full_BP_positive_cells'],
            'positive_memberships_after_union': source['expected_augmented_BP_positive_cells'],
            'added_positive_memberships': source['expected_added_BP_positive_cells'],
            'fitting_proteins_with_additions': source['expected_fitting_proteins_with_additions'],
            'root_positive_fitting_proteins_after_union': source['expected_augmented_root_positive_rows'],
            'fixed_model_output_axis_unchanged': True,
            'current_source_generated_date': source['current_source_generated_date']},
        'publication_scope': 'All six BP cells, declared methods and saved contrasts; aggregate scalars only.',
        'interpretation': 'Post-opening development on a consumed curator-annotation reference; no independent confirmation or new success gate.',
        'views': {}}
    expected_cells = {setting + '/' + NS for setting in SETTINGS}
    for view in VIEWS:
        src = raw['views'][view]
        require(set(src['cells']) == expected_cells, 'all three BP knowledge settings per view are required.')
        dest = {'reference_sha256': {role: pin(spec) for role, spec in src['reference_pins'].items()
                if role in ('obo', 'toi', 'PK', 'PK_known', 'NK', 'LK')}, 'cells': {}}
        out['views'][view] = dest
        for setting in SETTINGS:
            key = setting + '/' + NS; cell = src['cells'][key]
            require(cell.get('setting') == setting and cell.get('namespace') == NS
                    and cell.get('status') in ('evaluated', 'reference_absent'), 'cell identity or status differs.')
            public = {'setting': setting, 'namespace': NS, 'status': cell['status'], 'methods': {}}
            dest['cells'][key] = public
            if cell['status'] == 'reference_absent':
                require(set(cell['methods']) <= set(LABELS)
                        and all(m.get('native_micro_fmax') is None for m in cell['methods'].values()),
                        'a reference-absent cell cannot contain a score.')
                public['bootstrap'] = {'status': 'unavailable', 'interval_claimed': False}
                continue
            require(set(cell['methods']) == set(LABELS), 'a declared original or new method is missing.')
            public['methods'] = {arm: public_method(cell['methods'][arm]) for arm in LABELS}
            public['bootstrap'] = public_bootstrap(cell['bootstrap'])
            if public['bootstrap'].get('status') != 'unavailable':
                require(all(m['raw_native_reference_proteins'] == public['bootstrap']['raw_proteins']
                            for m in public['methods'].values()), 'native and paired full row counts disagree.')
            for arm in NEW_ARMS:
                method = public['methods'][arm]
                require(method['native_full_curve_point_agreement_passed'] is True
                        or (method['status'] == 'no_native_coverage' and method['native_micro_fmax'] is None),
                        'a new scored arm lacks native full-curve agreement.')
    return out


def render(results, destination):
    source = Path(results); payload = source.read_bytes(); public = aggregate(json.loads(payload))
    public['source_aggregate_sha256'] = hashlib.sha256(payload).hexdigest()
    dest = Path(destination); dest.mkdir(parents=True, exist_ok=False)
    lead = ('One fixed biological-process refit adds legal pre-cutoff curated positives while retaining every historical fitting positive. '
            'Two information-union controls test whether a simpler source update explains the result. '
            'All six original BP cells and every declared control remain visible, including losses and unavailable intervals.')
    md = ['# Current-annotation refit and source controls', '',
          '**DEVELOPMENT — reference already consumed; no independent confirmation.**', '', lead, '']
    body = ['<h1>Current-annotation refit and source controls</h1>',
        '<p class="banner"><strong>DEVELOPMENT — reference already consumed; no independent confirmation.</strong></p>',
        '<p>' + html.escape(lead) + '</p>',
        '<nav><a href="#overview">PK overview</a> · <a href="#all-cells">All six BP cells</a> · '
        '<a href="#method">Method and limits</a> · <a href="summary.json">Aggregate JSON</a> · <a href="report.md">Markdown</a></nav>']
    text = ('The source-admitted update retains 208,835 positive fitting memberships and adds 1,941 across 161 of the same 4,040 proteins, '
            'giving 210,776 memberships and 3,567 root-positive fitting proteins. Memberships are annotations, not independent studies. '
            'The fixed output vocabulary, raw parent forecasts and final 3,300-target frame remain unchanged.')
    md += [text, '', '## PK overview', '']; body += ['<p>' + html.escape(text) + '</p>', '<h2 id="overview">PK overview</h2>']
    rows = []
    for arm in OVERVIEW:
        points = [public['views'][view]['cells']['PK/' + NS]['methods'].get(arm, {}).get('native_micro_fmax') for view in VIEWS]
        rows.append([LABELS[arm], *(number(p) for p in points)])
    lines, markup = table(['Method', 'Native-view micro-Fmax', 'Fixed-T0-view micro-Fmax'], rows)
    md += lines + ['']; body.append(markup)
    notes = ('PK means partial knowledge: T0-known functions are excluded by the unchanged evaluator. NK and LK retain the original no-knowledge and limited-knowledge definitions. '
             'Fmax uses the original .001–.999 threshold grid. Compare methods within one view; native and fixed-T0 views have different reference populations. '
             'Paired 95% intervals below are copied from the saved 2,000 whole-protein draws. They are conditional, unadjusted development descriptions.')
    md += [notes, '', '## All six BP cells', '']; body += ['<p>' + html.escape(notes) + '</p>', '<h2 id="all-cells">All six BP cells</h2>']
    for view in VIEWS:
        for setting in SETTINGS:
            cell = public['views'][view]['cells'][setting + '/' + NS]; title = view + ' · ' + setting + ' · Biological process'
            md += ['### ' + title, '']; body.append('<details><summary>' + html.escape(title) + '</summary>')
            if cell['status'] == 'reference_absent':
                text = 'No native reference; no score or interval claim.'
                md += [text, '']; body += ['<p>' + text + '</p></details>']; continue
            refit = cell['methods'][REFIT]; boot = cell['bootstrap']
            text = ('Full native protein frame: ' + str(refit['raw_native_reference_proteins'])
                    + '; proteins with residual positive labels: ' + str(refit['eligible_proteins']) + '.')
            md += [text, '']; body.append('<p>' + html.escape(text) + '</p>')
            rows = []
            for arm, method in cell['methods'].items():
                bounds = boot.get('scores', {}).get(arm, {}).get('bootstrap_95_percentile_interval')
                interval = 'unavailable' if bounds is None else '[' + number(bounds[0]) + ', ' + number(bounds[1]) + ']'
                rows.append([LABELS[arm], method['status'], number(method['native_micro_fmax']), interval,
                    method['raw_native_reference_proteins'], method['eligible_proteins']])
            lines, markup = table(['Method', 'Status', 'Ordinary micro-Fmax', 'Copied score 95% interval',
                                   'Raw rows', 'Residual-positive proteins'], rows)
            md += lines + ['']; body.append(markup)
            if boot.get('status') == 'unavailable':
                text = 'Paired intervals unavailable; no comparison interval is inferred.'
                md += [text, '']; body.append('<p>' + text + '</p>')
            else:
                rows = []
                for contrast in boot['comparisons']:
                    candidate, comparator = contrast['candidate'], contrast['comparator']
                    first, second = (cell['methods'][a]['native_micro_fmax'] for a in (candidate, comparator))
                    difference = None if first is None or second is None else first - second
                    lo, hi = contrast['paired_95_percentile_interval']
                    rows.append([LABELS[candidate], LABELS[comparator], number(difference, True),
                                 '[' + number(lo, True) + ', ' + number(hi, True) + ']'])
                lines, markup = table(['Candidate', 'Comparator', 'Observed Fmax difference', 'Copied paired 95% interval'], rows)
                md += lines + ['']; body.append(markup)
            body.append('</details>')
    limitations = [
        'The model is one eight-layer context GCN with the same 40 source-derived evidence/relation channels and fixed January2023 output ontology. '
        'The current source contains 867 heads receiving new fitting assignments; only 64 gain their first positive fitting label. These are not 867 new output classes.',
        'Targets retain the complete historical fitting repertoire and union only the source-admitted direct current-T0 curated positives. '
        'Missing current annotations are not used as negative evidence or as instructions to remove historical positives. '
        'The dated T0 source was generated April10,2026; native Experimental/IC/TAS admission and identifier/ontology handling are unchanged.',
        'The full 4,040-protein fitting frame supplies updated priors before root-positive filtering. Both fitting and final parent features use those same priors. '
        'Fitting GOA context is updated to T0; the already sealed final T0 context and both raw parent forecasts are reused.',
        'No current validation metric or outcome-based checkpoint selection is computed. Three SWA epoch positions are fixed from the original pre-opening run. '
        'Transferring that fixed schedule to this source update is a disclosed development adaptation, not a validated new training recipe.',
        'The LocalPlus control unions retained historical seeds, the matched fitting update, the candidate’s exact augmented4,040-protein positive target repertoire with its fixed-old-ontology ancestors, '
        'and complete current-T0 curated seeds on the unchanged graph and native scorer. '
        'It does not seed nonexperimental annotations. The GCN additionally uses the DeepGO-SE parent and 40 nonexperimental context channels. '
        'This is a stronger annotation control; the comparison does not isolate learning as the sole source of any difference. '
        'The direct source-union prior combines current nonexperimental and retained curated memberships at score1 on their complete literal vocabulary.',
        'Every earlier BP method remains visible, including the earlier fixed 0.99 annotation-prior follow-up. '
        'All stored contrasts are shown; observed point subtraction is display arithmetic, and no interval, threshold, winner or new success gate is selected by this renderer.',
        'Later-snapshot curator annotations assess annotation recovery, not independent experiments, publication novelty or the percentage of biologically correct Pharos edges. '
        'An unmatched prediction is not an established biological falsehood. Exact source NOT/positive overlaps and incomplete context remain documented source limitations.',
        'The reference had already been consumed when this refit was planned. Favorable or unfavorable results are development evidence and require independent confirmation. '
        'The original frozen comparison, its success gates and previous publication remain unchanged. No automatic graph pruning or application-default change is made.'
    ]
    md += ['## Method and limits', '']; body.append('<h2 id="method">Method and limits</h2>')
    for text in limitations:
        md += ['- ' + text, '']; body.append('<p>' + html.escape(text) + '</p>')
    md += ['Published implementation: [ProtBoost/CAFA6 author code](https://github.com/btbpanda/CAFA6-updates).', '']
    body.append('<p><a href="https://github.com/btbpanda/CAFA6-updates">ProtBoost/CAFA6 author code</a></p>')
    (dest / 'summary.json').write_text(json.dumps(public, sort_keys=True, indent=2) + '\n')
    (dest / 'report.md').write_text('\n'.join(md))
    css = ('body{max-width:1280px;margin:32px auto;padding:0 24px;background:#f8fafb;color:#203544;font:15px/1.6 system-ui}'
           'h1{line-height:1.2}.banner{background:#fff1c9;border-left:5px solid #aa6e00;padding:16px}nav{margin:20px 0}.table{overflow:auto}'
           'table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:8px 10px;border-bottom:1px solid #d5e0e5;text-align:right}'
           'th{background:#e8f0f4}td:first-child,th:first-child{text-align:left}details{background:white;border:1px solid #d5e0e5;padding:12px 16px;margin:12px 0;border-radius:6px}'
           'summary{cursor:pointer;font-weight:650}a{color:#145e7a}h2{margin-top:32px}@media print{table{font-size:8px}body{margin:0;max-width:none}}')
    (dest / 'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Current-annotation refit and source controls</title><style>' + css + '</style>' + ''.join(body) + '</html>')
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    manifest = {'format': 'biograph-steward.current-refit-publication.v1',
        'source_aggregate_sha256': digest(source), 'renderer_source_sha256': digest(__file__),
        'evaluation_scores_intervals_or_model_choices_recomputed': False,
        'consumed_reference_development_only': True, 'raw_cases_draws_or_paths_published': False,
        'original_public_summary_sha256': public['original_public_summary_sha256'],
        'files': {name: {'sha256': digest(dest / name), 'bytes': (dest / name).stat().st_size}
                  for name in ('summary.json', 'report.html', 'report.md')}}
    (dest / 'publication_manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    return public


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__);p.add_argument('--results', required=True);p.add_argument('--destination', required=True)
    args = p.parse_args();render(args.results, args.destination)
