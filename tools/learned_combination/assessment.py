# SPDX-License-Identifier: GPL-3.0-only
"""Open the new temporal labels only after the immutable final-forecast seal."""
import hashlib
import json
from pathlib import Path
import urllib.request

from .core import need
from .reference import file_sha256
from .runner import NS_ASPECT, now, subset_reference, write_json


def acquire(spec, directory):
    """Verify immutable author Git blob identity, with a preserved raw receipt."""
    path = directory / spec['name']
    need('c3fd5b9a5226348d88b9efadddb3214c803b80c4' in spec['url'],
         'final-reference source must use the qualified immutable release commit.')
    request = urllib.request.Request(spec['url'], headers={'User-Agent': 'BioGraph-Steward-scientific-comparison/1'})
    with urllib.request.urlopen(request, timeout=120) as response:
        with path.open('xb') as stream:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                stream.write(chunk)
    size = path.stat().st_size
    git_hash = hashlib.sha1()
    git_hash.update(('blob ' + str(size) + '\0').encode('ascii'))
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            git_hash.update(chunk)
    need(git_hash.hexdigest() == spec['git_blob'], 'download differs from immutable release Git blob.')
    return path, {'file': str(path), 'url': spec['url'], 'bytes': size,
                  'git_blob': git_hash.hexdigest(), 'sha256': file_sha256(path)}


def evaluate(cfg, sealed, output):
    import numpy as np
    from cafaeval.graph import Prediction
    from cafaeval.parser import gt_parser, gt_exclude_parser, update_toi
    from .native_adapter import native_ontologies, align_predictions, evaluate_native
    from .ordinary_counts import contributions, verify_curve, paired_bootstrap

    seal_path = sealed / 'forecast_seal.json'
    seal = json.loads(seal_path.read_text())
    need(seal['future_GO_labels_opened'] is False and seal['protocol'] == cfg['protocol'],
         'an unchanged pre-label forecast seal is required.')
    need(seal['ontology_sha256'] == file_sha256(cfg['final']['obo']), 'final ontology changed after sealing.')
    for name, pin in seal['files'].items():
        need(file_sha256(sealed / name) == pin, 'sealed forecast changed: ' + name)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'reference_opening_gate.json', {
        'created_at': now(), 'forecast_seal_sha256': file_sha256(seal_path),
        'all_forecast_pins_verified': True, 'reference_opened_after_forecast_sealing': True})
    reference = output / 'reference'
    reference.mkdir()
    paths, receipts = {}, {}
    for role, spec in cfg['final_reference'].items():
        paths[role], receipts[role] = acquire(spec, reference)
    write_json(reference / 'sources.json', receipts)
    targets = tuple(Path(cfg['final']['targets']).read_text().splitlines())
    ont = update_toi(native_ontologies(cfg['final']['obo']), str(paths['toi']))
    tau = np.arange(.001, 1, .001)
    methods = cfg['protocol']['final']['arms']
    report = {'created_at': now(), 'protocol': cfg['protocol'],
              'forecast_seal_sha256': file_sha256(seal_path), 'selected_alphas': seal['selected_alphas'],
              'reference_sources': receipts, 'exact_sequence_compatible_forecast_targets': len(targets),
              'strata': {}, 'primary_success': False, 'automatic_adoption': False}
    for setting in ('PK', 'NK', 'LK'):
        frame = output / setting
        frame.mkdir()
        truth = frame / 'truth.tsv'
        truth_audit = subset_reference([paths[setting]], targets, truth)
        gt = gt_parser(str(truth), ont)
        known_audit = None
        ex = None
        if setting == 'PK' and gt:
            known = frame / 'known.tsv'
            known_audit = subset_reference([paths['PK_known']], targets, known)
            ex = gt_exclude_parser(str(known), gt, ont)
        for ns, aspect in NS_ASPECT.items():
            key = setting + '/' + ns
            result = {'setting': setting, 'namespace': ns, 'reference': truth_audit,
                      'known': known_audit, 'methods': {}, 'status': 'reference_absent'}
            report['strata'][key] = result
            if ns not in gt:
                continue
            result['raw_native_recognized_proteins'] = len(gt[ns].ids)
            arrays = {}
            for method in methods:
                print(now(), 'EVALUATE', key, method, flush=True)
                path = sealed / (method + '_' + aspect + '.npz')
                with np.load(path, allow_pickle=False) as f:
                    terms = tuple(f['terms'].tolist())
                    need(all(ont[ns].terms_dict[t]['index'] == j for j, t in enumerate(terms))
                         and len(terms) == ont[ns].idxs, 'sealed ontology term axis differs.')
                    pred = {ns: Prediction({p: i for i, p in enumerate(f['proteins'].tolist())},
                                           f['values'], ns)}
                    pred[ns]._learned_combination_terms = terms
                pred = align_predictions(pred, {ns: gt[ns]})
                curves, points = evaluate_native(pred, {ns: gt[ns]}, ont,
                    gt_exclude=None if ex is None else {ns: ex[ns]}, tau=tau, n_cpu=cfg['n_cpu'])
                curves.to_csv(frame / (aspect + '_' + method + '_curves.tsv'), sep='\t', index=False)
                counts, eligible = contributions(pred[ns], gt[ns], ont[ns], tau,
                                                   exclude=None if ex is None else ex[ns])
                residual = int(np.count_nonzero((counts[:, 0, 1] + counts[:, 0, 3]) > 0))
                parity = (verify_curve(counts, curves, namespace=ns) if residual else
                          {'author_point_agreement_passed': False,
                           'status': 'unscorable_no_residual_reference_proteins'})
                ids = np.asarray([p for p, i in sorted(gt[ns].ids.items(), key=lambda item: item[1])])
                array = {'ids': ids, 'tau': tau, 'ordinary': counts}
                arrays[method] = array
                np.savez_compressed(frame / (aspect + '_' + method + '_counts.npz'), **array, eligible=eligible)
                point = points.get(ns)
                result['methods'][method] = {'native_micro_fmax': point,
                    'pre_exclusion_GT_proteins': int(eligible.sum()),
                    'eligible_proteins': residual, 'native_curve_agreement': parity,
                    'status': 'evaluated' if point is not None else 'no_native_coverage',
                    'native_positive_forecast_cells': int(np.count_nonzero(pred[ns].matrix))}
                print(now(), 'POINT', key, method, point, flush=True)
            result['status'] = 'evaluated'
            if len(gt[ns].ids) > 1 and all(m['status'] == 'evaluated' for m in result['methods'].values()):
                result['bootstrap'] = paired_bootstrap(arrays)
            else:
                result['bootstrap'] = {'status': 'unavailable', 'reason': 'fewer than two native proteins or an unscorable arm'}
            write_json(frame / (aspect + '_summary.json'), result)
    primary = report['strata']['PK/molecular_function']
    if 'bootstrap' in primary and primary['bootstrap'].get('status') != 'unavailable':
        comparisons = {item['comparator']: item for item in primary['bootstrap']['comparisons']}
        report['primary_success'] = all(
            primary['methods']['learned_mix']['native_micro_fmax'] > primary['methods'][m]['native_micro_fmax']
            and comparisons[m]['paired_95_percentile_interval'][0] > 0
            for m in methods if m != 'learned_mix')
    report['files'] = {str(p.relative_to(output)): file_sha256(p) for p in output.rglob('*') if p.is_file()}
    write_json(output / 'report.json', report)
    return report
