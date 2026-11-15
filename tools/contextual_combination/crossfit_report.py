# SPDX-License-Identifier: GPL-3.0-only
"""Publish only saved aggregate readouts of the fixed cross-fit comparison.

Read one completed private assessment JSON, then project explicit scalar
allowlists. No reference cases, forecast arrays or contribution files are
opened. Draw vectors, identifiers, free text and private paths are discarded.
No scientific endpoint, interval, threshold or model choice is recomputed.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path

from .annotation_prior_report import (FLAGS, SETTINGS, VIEWS, numeric, pair,
    pin, public_method, number, table, require)
from .current_refit_report import LABELS as PREVIOUS_LABELS, expected_pairs as previous_pairs


NS = 'biological_process'
ARM = 'crossfit_graph_frequency_context'
PARENTS = ['localplus', 'fit_label_frequency']
LABELS = {**PREVIOUS_LABELS, ARM: 'Cross-fitted graph + annotation-frequency context GCN'}
FOCUS = ('validation_selected_context', 'localplus_T0_curated')
PLAN_SHA = '22a51e43cc9720bbd5d257c3dfc1fc8d23d1e73f2f39d5c9f854cb3b99621823'
ORIGINAL_SHA = '2dfebc4e855df8682335484cb39b5100f518363fa74b1b24b66ca3c4cdffdf98'
ANNOTATION_SHA = '76189617f4285a9b7f8ff253280642849ca1a117d80901b893c260e420601d9d'
PREVIOUS_SHA = 'b7792b0737835d374f2335735aa254e90a609d9a73bf0bfd9f99f9586065eac0'
REFERENCE_ROLES = ('obo', 'toi', 'PK', 'PK_known', 'NK', 'LK')


def expected_pairs():
    """Declared identities only; no comparison or success decision is made."""
    return previous_pairs() + [(ARM, comparator) for comparator in PREVIOUS_LABELS]


def bounded(value, lower, upper):
    result = numeric(value)
    require(lower <= result <= upper, 'saved aggregate value is outside its mathematical range.')
    return result


def bounded_pair(value, lower, upper):
    result = pair(value)
    require(lower <= result[0] <= result[1] <= upper, 'saved interval is outside its mathematical range.')
    return result


def public_bootstrap(boot):
    require(boot.get('status') != 'unavailable'
        and boot.get('draws') == 2000 and boot.get('seed') == 20261113
        and boot.get('original_native_gated_draws_reused_without_recomputation') is True
        and boot.get('earlier_contrasts_reused_without_recomputation') is True
        and boot.get('regenerated_anchor_peaks_equal_preserved_exactly') is True
        and boot.get('development_followup_on_consumed_reference') is True
        and boot.get('independent_confirmation') is False
        and boot.get('new_success_gate_or_model_selection') is False,
        'a completed comparison must retain the original paired consumed-reference design.')
    require(set(boot['scores']) == set(LABELS), 'all 23 saved method intervals are required.')
    comparisons = boot['comparisons']; keys = [(r.get('candidate'), r.get('comparator')) for r in comparisons]
    old = previous_pairs(); new = [(ARM, name) for name in PREVIOUS_LABELS]
    require(len(keys) == len(set(keys)) == 54 and set(keys[:32]) == set(old)
        and set(keys[32:]) == set(new), 'retain all 32 earlier contrasts followed by all 22 new contrasts.')
    rows = boot['raw_proteins']
    require(type(rows) is int and rows > 1, 'invalid complete paired protein frame.')
    out = {'draws': 2000, 'seed': 20261113, 'raw_proteins': rows,
        'original_native_gated_draws_reused_without_recomputation': True,
        'earlier_contrasts_reused_without_recomputation': True,
        'regenerated_anchor_peaks_equal_preserved_exactly': True,
        'scores': {}, 'comparisons': []}
    for arm in LABELS:
        row = boot['scores'][arm]
        out['scores'][arm] = {'bootstrap_mean': bounded(row['bootstrap_mean'], 0, 1),
            'bootstrap_95_percentile_interval': bounded_pair(row['bootstrap_95_percentile_interval'], 0, 1)}
    # Keep saved contrast order and values, including every unfavorable result.
    for row in comparisons:
        out['comparisons'].append({'candidate': row['candidate'], 'comparator': row['comparator'],
            'difference_mean': bounded(row['difference_mean'], -1, 1),
            'paired_95_percentile_interval': bounded_pair(row['paired_95_percentile_interval'], -1, 1),
            'fraction_draws_above_zero': bounded(row['fraction_draws_above_zero'], 0, 1)})
    return out


def aggregate(raw):
    require(raw.get('format') == 'biograph-steward.crossfit-development-assessment.v1'
        and all(raw.get(k) is v for k, v in FLAGS.items()),
        'only the completed consumed-reference cross-fit development assessment is accepted.')
    plan_path = Path(__file__).with_name('crossfit_protocol.json')
    require(hashlib.sha256(plan_path.read_bytes()).hexdigest() == raw.get('plan_sha256') == PLAN_SHA,
        'publication and assessment must use the same frozen plan.')
    plan = json.loads(plan_path.read_text())
    require(raw['original_report_sha256'] == ORIGINAL_SHA
        and raw['annotation_prior_report_sha256'] == ANNOTATION_SHA
        and raw['previous_development_report_sha256'] == PREVIOUS_SHA
        and raw['original_public_summary_sha256'] == plan['original_public_summary_sha256']
        and raw['original_forecast_seal_sha256'] == plan['original_forecast_seal_sha256'],
        'the immutable original and earlier development source fingerprints differ.')
    require(plan['evaluation']['reporting_focus'] == list(FOCUS)
        and plan['parent_axis'] == PARENTS and plan['arm'] == ARM,
        'fixed reporting focus or ordered input profile differs.')
    require(raw['target_count'] == 3300 and raw['new_arm_scopes'] == {ARM: [NS]}
        and raw.get('method_rows') == 138 and raw.get('contrast_rows') == 324,
        'completed fixed 138-point/324-contrast BP scope required.')
    require(set(raw['views']) == set(VIEWS), 'both original ontology views must remain visible.')
    out = {'format': 'biograph-steward.crossfit-development-public.v1', **FLAGS,
        'reference_previously_consumed': True, 'namespace': NS, 'target_count': 3300,
        'development_plan_sha256': PLAN_SHA, 'original_report_sha256': ORIGINAL_SHA,
        'annotation_prior_report_sha256': ANNOTATION_SHA, 'previous_development_report_sha256': PREVIOUS_SHA,
        'original_public_summary_sha256': pin({'sha256': raw['original_public_summary_sha256']}),
        'original_forecast_seal_sha256': pin({'sha256': raw['original_forecast_seal_sha256']}),
        'previous_method_count': 22, 'new_fixed_method_count': 1, 'total_declared_method_count': 23,
        'declared_methods': list(LABELS), 'reporting_focus': list(FOCUS), 'method_rows': 138,
        'contrast_rows': 324, 'earlier_contrast_rows': 192, 'new_contrast_rows': 132,
        'source_scope': {'parent_axis': list(PARENTS), 'fitting_proteins': 4040,
            'original_positive_annotation_memberships': 208835, 'root_positive_fitting_proteins': 3557,
            'model_output_terms': 27942, 'context_channels': 40, 'full_sequence_group_folds': 5,
            'context_dates': {'fit': '2023-05-18', 'validation': '2025-09-04', 'final': '2026-04-10'},
            'original_fitting_labels_and_dated_sources_retained': True,
            'DeepGO_parent_included': False, 'PU_loss_or_biological_class_prior_included': False,
            'full_ProtBoost_reproduction': False, 'isolated_OOF_effect_claimed': False},
        'publication_scope': 'All six BP cells, all 23 methods and all 324 saved contrasts; aggregate scalars only.',
        'interpretation': 'Consumed-reference development on later curator-annotation recovery; no independent confirmation or new success gate.',
        'views': {}}
    for view in VIEWS:
        source = raw['views'][view]
        require(set(source['cells']) == {s + '/' + NS for s in SETTINGS}, 'all six original BP cells are required.')
        require(set(source['reference_pins']) == set(REFERENCE_ROLES), 'complete original reference fingerprints are required.')
        dest = {'reference_sha256': {role: pin(source['reference_pins'][role]) for role in REFERENCE_ROLES}, 'cells': {}}
        out['views'][view] = dest
        for setting in SETTINGS:
            key = setting + '/' + NS; cell = source['cells'][key]
            require(cell.get('setting') == setting and cell.get('namespace') == NS
                and cell.get('status') == 'evaluated', 'completed original cell identity/status required.')
            require(set(cell['methods']) == set(LABELS), 'every earlier method and the new arm must remain visible.')
            public = {'setting': setting, 'namespace': NS, 'status': 'evaluated',
                'methods': {arm: public_method(cell['methods'][arm]) for arm in LABELS},
                'bootstrap': public_bootstrap(cell['bootstrap'])}
            dest['cells'][key] = public
            rows = public['bootstrap']['raw_proteins']
            for method in public['methods'].values():
                point = method['native_micro_fmax']
                if point is not None: bounded(point, 0, 1)
                require((method['status'] == 'evaluated') == (point is not None)
                    and method['raw_native_reference_proteins'] == rows
                    and method['eligible_proteins'] <= method['pre_exclusion_GT_proteins'] <= rows,
                    'saved method status or full native/bootstrap frame differs.')
            require(public['methods'][ARM]['native_full_curve_point_agreement_passed'] is True,
                'the new scored arm requires native full-curve/point agreement.')
    return out


def contrast_row(cell, contrast):
    a, b = contrast['candidate'], contrast['comparator']
    first, second = (cell['methods'][name]['native_micro_fmax'] for name in (a, b))
    delta = None if first is None or second is None else first - second  # Display only.
    lo, hi = contrast['paired_95_percentile_interval']
    return [LABELS[a], LABELS[b], number(delta, True),
        '[' + number(lo, True) + ', ' + number(hi, True) + ']']


def render(results, destination):
    source = Path(results); payload = source.read_bytes(); public = aggregate(json.loads(payload))
    public['source_aggregate_sha256'] = hashlib.sha256(payload).hexdigest()
    dest = Path(destination); dest.mkdir(parents=True, exist_ok=False)
    title = 'Cross-fitted graph and annotation-frequency comparison'
    banner = 'DEVELOPMENT — reference already consumed; no independent confirmation.'
    lead = ('One fixed context GCN combines cross-fitted LocalPlus with observed annotation frequency, '
        'using the original fitting labels and dated 40-channel context. '
        'Every earlier method and saved contrast remains visible, including unfavorable results.')
    md = ['# ' + title, '', '**' + banner + '**', '', lead, '', '## Fixed comparison focus', '']
    body = ['<h1>' + title + '</h1>', '<p class="banner"><strong>' + banner + '</strong></p>',
        '<p>' + html.escape(lead) + '</p>', '<nav><a href="#focus">Fixed comparisons</a> · '
        '<a href="#all-cells">All six BP cells</a> · <a href="#method">Method and limits</a> · '
        '<a href="summary.json">Aggregate JSON</a> · <a href="report.md">Markdown</a></nav>',
        '<h2 id="focus">Fixed comparison focus</h2>']
    focus_note = ('The two reporting comparators were fixed before this assessment: the original validation-selected context model '
        'and the current-T0 curated LocalPlus control. This focus does not select a winner or hide other controls.')
    md += [focus_note, '']; body.append('<p>' + html.escape(focus_note) + '</p>')
    rows = []
    for view in VIEWS:
        for setting in SETTINGS:
            cell = public['views'][view]['cells'][setting + '/' + NS]
            for comparator in FOCUS:
                contrast = next(r for r in cell['bootstrap']['comparisons'] if (r['candidate'], r['comparator']) == (ARM, comparator))
                row = contrast_row(cell, contrast)
                rows.append([view, setting, number(cell['methods'][ARM]['native_micro_fmax']), LABELS[comparator],
                    number(cell['methods'][comparator]['native_micro_fmax']), row[2], row[3]])
    lines, markup = table(['View', 'Setting', 'New arm Fmax', 'Fixed comparator', 'Comparator Fmax',
                          'Observed point difference', 'Copied paired 95% interval'], rows)
    md += lines + ['', '## All six BP cells', '']; body += [markup, '<h2 id="all-cells">All six BP cells</h2>']
    notes = ('PK is partial knowledge, with T0-known functions excluded by the unchanged evaluator; NK and LK retain the original no-knowledge '
        'and limited-knowledge definitions. Ordinary micro-Fmax uses the original .001–.999 threshold grid. '
        'Compare methods within one view: native and fixed-T0 references contain different populations. '
        'All intervals are copied from saved 2,000 whole-protein draws; they are conditional, unadjusted development descriptions.')
    md += [notes, '']; body.append('<p>' + html.escape(notes) + '</p>')
    for view in VIEWS:
        for setting in SETTINGS:
            cell = public['views'][view]['cells'][setting + '/' + NS]
            heading = view + ' · ' + setting + ' · Biological process'
            md += ['### ' + heading, '']; body.append('<details><summary>' + html.escape(heading) + '</summary>')
            method = cell['methods'][ARM]
            text = ('Full native/bootstrap protein frame: ' + str(method['raw_native_reference_proteins'])
                + '; proteins with residual positive labels: ' + str(method['eligible_proteins']) + '.')
            md += [text, '']; body.append('<p>' + html.escape(text) + '</p>')
            rows = []
            for arm, method in cell['methods'].items():
                lo, hi = cell['bootstrap']['scores'][arm]['bootstrap_95_percentile_interval']
                rows.append([LABELS[arm], method['status'], number(method['native_micro_fmax']),
                    '[' + number(lo) + ', ' + number(hi) + ']', method['raw_native_reference_proteins'], method['eligible_proteins']])
            lines, markup = table(['Method', 'Status', 'Ordinary micro-Fmax', 'Copied score 95% interval', 'Raw rows', 'Residual-positive proteins'], rows)
            md += lines + ['']; body.append(markup)
            lines, markup = table(['Candidate', 'Comparator', 'Observed point difference', 'Copied paired 95% interval'],
                [contrast_row(cell, r) for r in cell['bootstrap']['comparisons']])
            md += lines + ['']; body += [markup, '</details>']
    limits = [
        'This is one combined input-profile change: the ordered parents are historical LocalPlus and fitting-label annotation frequency; '
        'DeepGO-SE is absent from this new arm. The unchanged eight-layer native GCN receives the original 40 Boolean source-context channels. '
        'It is not a full ProtBoost reproduction or an isolated causal estimate of an OOF correction.',
        'The same 4,040 fitting proteins, 208,835 positive annotation memberships, 3,557 root-positive training rows and 27,942 model output terms are retained. '
        'Fitting, validation and final context snapshots remain May18,2023; September4,2025; and April10,2026, respectively. No source refresh or new target annotations enter this arm.',
        'Five exact full-sequence GroupKFold partitions exclude each fitting fold from its graph-parent seed table and prior/frequency calculations. '
        'Complement priors include every complementary fitting row before root filtering. Validation and final features use all original 4,040 fitting rows. '
        'The original literal source head vocabulary remains available even when a fold has zero positive seeds; alias scores are combined by native MAX after scoring.',
        'Observed annotation frequency is not verified biological prevalence or a PU class prior. Missing labels remain zero in the unchanged benchmark BCE. '
        'No positive-unlabeled loss or custom correction is included. Exact-sequence exclusion does not establish distant-family, study or GOA-source independence.',
        'Native model layers, loss, optimizer, twenty epochs and best-three SWA remain unchanged. Normal checkpoint selection uses the already-consumed September2025–March2026 validation. '
        'No final-reference label is a fitting or forecast input, and no final-reference result selects this fixed arm.',
        'All 22 earlier methods and all 192 earlier contrasts are retained alongside the 132 new contrasts. Saved scalar readouts and intervals are copied; '
        'observed point subtraction is display arithmetic only. No interval, threshold, winner or new success gate is selected by this renderer.',
        'Later curator annotations measure annotation recovery, not independent experiments, publication novelty or the percentage of biologically correct whole-graph Pharos assertions. '
        'Unmatched predictions are not established biological falsehoods. GOA-source reuse and incomplete annotations remain limitations.',
        'The reference was already consumed before this development comparison. Earlier failed and favorable approaches remain visible, and any gain needs independent confirmation. '
        'The original frozen comparison and its success gates remain unchanged. No automatic graph pruning, application-default change or model promotion follows this report.'
    ]
    md += ['## Method and limits', '']; body.append('<h2 id="method">Method and limits</h2>')
    for text in limits:
        md += ['- ' + text, '']; body.append('<p>' + html.escape(text) + '</p>')
    links = [('ProtBoost author code', 'https://github.com/btbpanda/CAFA5-protein-function-prediction-2nd-place'),
        ('Native LocalPlus author code', 'https://github.com/Murali-group/multi-species-GOA-prediction'),
        ('GroupKFold version1.3 documentation', 'https://scikit-learn.org/1.3/modules/generated/sklearn.model_selection.GroupKFold.html')]
    md += ['Published implementations: ' + '; '.join('[' + label + '](' + url + ')' for label, url in links) + '.', '']
    body.append('<p>Published implementations: ' + '; '.join('<a href="' + url + '">' + label + '</a>' for label, url in links) + '.</p>')
    (dest / 'summary.json').write_text(json.dumps(public, sort_keys=True, indent=2) + '\n')
    (dest / 'report.md').write_text('\n'.join(md))
    css = ('body{max-width:1280px;margin:32px auto;padding:0 24px;background:#f8fafb;color:#203544;font:15px/1.6 system-ui}'
        'h1{line-height:1.2}.banner{background:#fff1c9;border-left:5px solid #aa6e00;padding:16px}nav{margin:20px 0}.table{overflow:auto}'
        'table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:8px 10px;border-bottom:1px solid #d5e0e5;text-align:right}'
        'th{background:#e8f0f4}td:first-child,th:first-child{text-align:left}details{background:white;border:1px solid #d5e0e5;padding:12px 16px;margin:12px 0;border-radius:6px}'
        'summary{cursor:pointer;font-weight:650}a{color:#145e7a}h2{margin-top:32px}@media print{table{font-size:8px}body{margin:0;max-width:none}}')
    (dest / 'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + title + '</title><style>' + css + '</style>' + ''.join(body) + '</html>')
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    manifest = {'format': 'biograph-steward.crossfit-development-publication.v1',
        'source_aggregate_sha256': digest(source), 'renderer_source_sha256': digest(__file__),
        'development_plan_sha256': PLAN_SHA, 'evaluation_scores_intervals_or_model_choices_recomputed': False,
        'consumed_reference_development_only': True, 'raw_cases_draws_or_paths_published': False,
        'original_public_summary_sha256': public['original_public_summary_sha256'],
        'files': {name: {'sha256': digest(dest / name), 'bytes': (dest / name).stat().st_size}
                  for name in ('summary.json', 'report.md', 'report.html')}}
    (dest / 'publication_manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    return public


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--results', required=True); p.add_argument('--destination', required=True)
    args = p.parse_args(); render(args.results, args.destination)
