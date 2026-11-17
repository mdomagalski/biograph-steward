# SPDX-License-Identifier: GPL-3.0-only
"""Phased, offline orchestration around the separately pinned native evaluator.

prepare -> fit -> seal -> evaluate. Only the last phase accepts the new release
labels. Source artifacts, failed runs and final forecast seals are never replaced.
"""
import argparse
from contextlib import redirect_stdout
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

from .core import ALPHA_GRID, ScoreMatrix, need, select_development_alpha
from .protocol import PROTOCOL
from .reference import file_sha256, read_target_ids

NS_ASPECT = {'molecular_function': 'mf', 'biological_process': 'bp', 'cellular_component': 'cc'}


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def now():
    return datetime.now(timezone.utc).isoformat()


def config(path):
    cfg = json.loads(Path(path).read_text())
    need(cfg['protocol'] == PROTOCOL, 'configuration differs from the predeclared protocol.')
    for name, expected in cfg['input_pins'].items():
        need(file_sha256(name) == expected, 'pinned input changed: ' + name)
    return cfg


def save_matrices(folder, matrices):
    import numpy as np
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for ns, matrix in matrices.items():
        path = folder / (ns + '.npy')
        np.save(path, matrix.values, allow_pickle=False)
        manifest[ns] = {'proteins': list(matrix.proteins), 'terms': list(matrix.terms),
                        'file': str(path), 'sha256': file_sha256(path),
                        'upper_roundoff_tolerance': matrix.upper_roundoff_tolerance}
    write_json(folder / 'manifest.json', manifest)
    return manifest


def load_matrices(folder):
    import numpy as np
    result = {}
    for ns, item in json.loads((folder / 'manifest.json').read_text()).items():
        need(file_sha256(item['file']) == item['sha256'], 'matrix cache changed.')
        result[ns] = ScoreMatrix(tuple(item['proteins']), tuple(item['terms']),
                                 np.load(item['file'], mmap_mode='r', allow_pickle=False),
                                 item['upper_roundoff_tolerance'])
    return result


def prepared_pins(folder):
    """Bind each later phase to the preserved label-free intake and cache axes."""
    paths = [folder / 'intake.json'] + sorted(folder.glob('*/*/manifest.json'))
    need(len(paths) >= 6 and all(p.is_file() for p in paths), 'complete prepared intake receipts required.')
    return {str(path): file_sha256(path) for path in paths}


def prepare(cfg, output):
    """Parse raw forecasts on fixed identity axes without any outcome labels."""
    import numpy as np
    from .native_adapter import native_ontologies, load_native_scores
    output.mkdir(parents=True, exist_ok=False)
    audit = {'created_at': now(), 'future_GO_labels_opened': False, 'epochs': {}}
    for epoch in ('development', 'final'):
        spec = cfg[epoch]
        ids = read_target_ids(spec['targets'])
        ont = native_ontologies(spec['obo'])
        audit['epochs'][epoch] = {}
        sources = dict(cfg['forecast_files'])
        if epoch == 'final':
            sources['native_t0_nonexperimental'] = {'PK': [spec['baseline']], 'nonPK': []}
        pk_ids = set(read_target_ids(cfg['pk_targets']))
        for method, source_frames in sources.items():
            print(now(), 'LOAD', epoch, method, flush=True)
            matrices, diag = load_native_scores(source_frames['PK'], ids, ont, localplus=(method == 'localplus'))
            other_ids = tuple(p for p in ids if p not in pk_ids)
            if other_ids and method != 'native_t0_nonexperimental':
                others, other_diag = load_native_scores(source_frames['nonPK'], other_ids, ont,
                                                        localplus=(method == 'localplus'))
                row_index = {p: i for i, p in enumerate(ids)}
                rows = np.asarray([row_index[p] for p in other_ids], dtype=np.int64)
                for ns in matrices:
                    matrices[ns].values[rows, :] = others[ns].values
                diag = {'PK_frame': diag, 'nonPK_only_frame': other_diag,
                        'nonPK_only_targets': len(other_ids), 'PK_precedence_for_overlap': True}
                del others
            save_matrices(output / epoch / method, matrices)
            audit['epochs'][epoch][method] = diag
            del matrices
            print(now(), 'SAVED', epoch, method, flush=True)
    write_json(output / 'intake.json', audit)
    return audit


def subset_reference(paths, ids, destination):
    """Restrict a source frame by literal accession, retaining native GO rows."""
    ids = set(ids)
    source_rows = retained = 0
    with destination.open('x') as out:
        out.write('EntryID\tterm\taspect\n')
        for path in paths:
            with Path(path).open() as stream:
                for line in stream:
                    fields = line.rstrip('\r\n').split('\t')
                    if fields[0] == 'EntryID':
                        continue
                    need(len(fields) >= 2, 'malformed reference record.')
                    source_rows += 1
                    if fields[0] in ids:
                        out.write(line if line.endswith('\n') else line + '\n')
                        retained += 1
    return {'source_rows': source_rows, 'retained_rows': retained,
            'file': str(destination), 'sha256': file_sha256(destination)}


def fit(cfg, prepared, output):
    import numpy as np
    from cafaeval.parser import gt_parser, gt_exclude_parser, update_toi
    from .native_adapter import native_ontologies, native_predictions, evaluate_native, align_predictions
    output.mkdir(parents=True, exist_ok=False)
    spec = cfg['development']
    ids = read_target_ids(spec['targets'])
    truth_path, known_path = output / 'development_truth.tsv', output / 'development_known.tsv'
    truth_audit = subset_reference(spec['truth'], ids, truth_path)
    known_audit = subset_reference(spec['known'], ids, known_path)
    ont = update_toi(native_ontologies(spec['obo']), spec['toi'])
    gt = gt_parser(str(truth_path), ont)
    ex = gt_exclude_parser(str(known_path), gt, ont)
    local = load_matrices(prepared / 'development' / 'localplus')
    deep = load_matrices(prepared / 'development' / 'deepgose')
    selections = {}
    for ns, aspect in NS_ASPECT.items():
        need(ns in gt, 'development namespace absent: ' + ns)
        objectives = {}
        for alpha in ALPHA_GRID:
            print(now(), 'FIT', ns, alpha, flush=True)
            pred = native_predictions({ns: local[ns]}, {ns: deep[ns]}, {ns: alpha}, ont)
            pred = align_predictions(pred, {ns: gt[ns]})
            curve, values = evaluate_native(pred, {ns: gt[ns]}, ont,
                                            gt_exclude={ns: ex[ns]},
                                            tau=np.arange(.01, 1, .01), n_cpu=cfg['n_cpu'])
            curve.to_csv(output / (aspect + '_alpha_' + str(alpha) + '.tsv'), sep='\t', index=False)
            need(values.get(ns) is not None, 'no native development coverage: ' + ns)
            objectives[alpha] = float(values[ns])
            del pred
        selections[ns] = select_development_alpha(aspect, objectives,
                                                  development_id=file_sha256(truth_path)).to_dict()
        print(now(), 'SELECTED', ns, selections[ns]['alpha'], flush=True)
    report = {'created_at': now(), 'protocol': PROTOCOL, 'selections': selections,
              'truth': truth_audit, 'known': known_audit, 'final_GO_labels_opened': False,
              'prepared_receipt_pins': prepared_pins(prepared),
              'development_target_count': len(ids), 'files': {p.name: file_sha256(p) for p in output.iterdir() if p.is_file()}}
    write_json(output / 'fit.json', report)
    return report


def seal(cfg, prepared, fitted, output):
    """Close every final forecast before new reference/TOI decoding."""
    import numpy as np
    from .native_adapter import native_ontologies, native_predictions
    output.mkdir(parents=True, exist_ok=False)
    fit_path = fitted / 'fit.json'
    fit_report = json.loads(fit_path.read_text())
    need(fit_report['final_GO_labels_opened'] is False and fit_report['protocol'] == PROTOCOL,
         'fit must use the unchanged protocol and precede final reference access.')
    need(fit_report['prepared_receipt_pins'] == prepared_pins(prepared),
         'label-free prepared receipts changed after fitting.')
    ont = native_ontologies(cfg['final']['obo'])
    local = load_matrices(prepared / 'final' / 'localplus')
    deep = load_matrices(prepared / 'final' / 'deepgose')
    baseline = load_matrices(prepared / 'final' / 'native_t0_nonexperimental')
    alphas = {ns: entry['alpha'] for ns, entry in fit_report['selections'].items()}
    methods = {
        'deepgose': (local, deep, {ns: 0.0 for ns in ont}),
        'localplus': (local, deep, {ns: 1.0 for ns in ont}),
        'equal_mix': (local, deep, {ns: .5 for ns in ont}),
        'learned_mix': (local, deep, alphas),
        'native_t0_nonexperimental': (baseline, baseline, {ns: 1.0 for ns in ont}),
    }
    files = {}
    for method, (left, right, weights) in methods.items():
        for ns in NS_ASPECT:
            pred = native_predictions({ns: left[ns]}, {ns: right[ns]}, {ns: weights[ns]}, ont)
            need(ns in pred, 'no final source coverage: ' + method + '/' + ns)
            path = output / (method + '_' + NS_ASPECT[ns] + '.npz')
            np.savez_compressed(path, values=pred[ns].matrix,
                                proteins=np.asarray(left[ns].proteins), terms=np.asarray(left[ns].terms))
            files[path.name] = file_sha256(path)
            print(now(), 'SEALED', path.name, flush=True)
    report = {'created_at': now(), 'protocol': PROTOCOL, 'fit_sha256': file_sha256(fit_path),
              'selected_alphas': alphas, 'future_GO_labels_opened': False,
              'prepared_receipt_pins': prepared_pins(prepared),
              'ontology_sha256': file_sha256(cfg['final']['obo']), 'files': files}
    write_json(output / 'forecast_seal.json', report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=('prepare', 'fit', 'seal', 'evaluate'))
    p.add_argument('--config', required=True)
    p.add_argument('--prepared', type=Path)
    p.add_argument('--fitted', type=Path)
    p.add_argument('--sealed', type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    cfg = config(a.config)
    if a.phase == 'prepare':
        prepare(cfg, a.output)
    elif a.phase == 'fit':
        fit(cfg, a.prepared, a.output)
    elif a.phase == 'seal':
        seal(cfg, a.prepared, a.fitted, a.output)
    else:
        from .assessment import evaluate
        evaluate(cfg, a.sealed, a.output)


if __name__ == '__main__':
    main()
