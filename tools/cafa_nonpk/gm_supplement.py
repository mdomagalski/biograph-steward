"""Separately frozen, post-PK GeneMANIA+ transport supplement.

This only supplies the same qualified historical inputs to the existing
unchanged author implementation. No NK/LK future labels are read, and the
original five-arm transport contract is not modified.
"""
import argparse
from collections import defaultdict
import gzip
import hashlib
from pathlib import Path
import time

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.cafa_prediction import core
from tools.cafa_prediction.run import read
from tools.cafa_nonpk.run import load

FORMAT = 'biograph-steward.cafa5-nonpk-gm-supplement.v1'


def numerical_certificate(W, L):
    """Check the published regularized Laplacian, not an assumed probability.

    SciPy CG stops on a residual norm. Varah's1975 diagonal-dominance bound
    supplies a componentwise error certificate without altering its solution.
    """
    import numpy as np
    from scipy.sparse import eye
    M = eye(L.shape[0])+L
    off = M.copy(); off.setdiag(0); off.eliminate_zeros()
    delta = float((M.diagonal()-np.asarray(abs(off).sum(axis=1)).ravel()).min())
    symmetry = M-M.T
    symmetry_error = float(abs(symmetry).max()) if symmetry.nnz else 0.
    core.need(np.isfinite(M.data).all() and W.data.min()>0 and (off.data<=0).all()
        and delta>0 and symmetry_error<=1e-12,
        'the author matrix must remain a symmetric, strictly diagonally dominant M-matrix.')
    return M, {'minimum_row_diagonal_dominance_margin':delta,
        'symmetry_max_absolute_difference':symmetry_error,
        'bound_reference':'https://doi.org/10.1016/0024-3795(75)90112-3',
        'solver_documentation':'https://docs.scipy.org/doc/scipy-1.13.1/reference/generated/scipy.sparse.linalg.cg.html'}


def author_scores(modules, L, M, certificate, positives):
    import numpy as np
    core.need(positives and len(positives)==len(set(positives))
        and all(0<=i<M.shape[0] for i in positives),'native GM seeds must be nonempty, unique matrix indices.')
    y = np.zeros(M.shape[0]); y[sorted(positives)] = 1
    scores, process, wall, iterations = modules['gm'].runGeneMANIA(L, y, **core.PARAMETERS['genemaniaplus'])
    core.need(scores.shape==y.shape and np.isfinite(scores).all(), 'native GM output is nonfinite or incomplete.')
    residual = M.dot(scores)-y
    residual_2 = float(np.linalg.norm(residual))
    bound = float(abs(residual).max()/certificate['minimum_row_diagonal_dominance_margin'])
    core.need(residual_2<=core.PARAMETERS['genemaniaplus']['tol']*float(np.linalg.norm(y))*(1+1e-8),
        'native GM solution did not meet the unchanged author residual tolerance.')
    exact_upper = float(abs(y).max()/certificate['minimum_row_diagonal_dominance_margin'])
    core.need(float(scores.min())>=-bound-1e-12 and float(scores.max())<=exact_upper+bound+1e-12,
        'native GM component is outside its certified numerical error bound.')
    return scores, {'iterations':iterations,'equation_residual_norm':residual_2,
        'componentwise_error_bound':bound,'negative_graph_scores':int((scores<0).sum()),
        'minimum_graph_score':float(scores.min()),'process_seconds':process,'wall_seconds':wall}


def inputs(frozen, protocol_sha256, author, author_receipt):
    import numpy as np
    frozen = Path(frozen); plan = load(frozen, protocol_sha256)
    core.need(sha(author_receipt) == plan['input_pins']['author_receipt']['sha256'],
              'published implementation receipt changed.')
    modules = core.author_modules(author, author_receipt)
    graph = read(frozen/'graph.json.gz')
    index = {n.split(':', 1)[1]: i for i, n in enumerate(graph['nodes'])}
    W = core.adjacency(graph['nodes'], graph['pairs'])
    L = modules['gm'].setup_laplacian(W)
    terms = defaultdict(list)
    for protein, rows in read(frozen/'training.json.gz').items():
        for aspect, term in rows: terms[aspect, term].append(index[protein])
    targets = (frozen/'targets.txt').read_text().splitlines()
    return plan, modules, W, L, terms, targets, np.asarray([index[p] for p in targets], dtype=int)


def preflight(frozen, protocol_sha256, author, author_receipt, output):
    start = time.time()
    _, modules, W, L, terms, _, _ = inputs(frozen, protocol_sha256, author, author_receipt)
    selected = sorted(terms, key=lambda key: hashlib.sha256(
        ('gm-full-nonpk-preflight-v1|' + str(key)).encode()).hexdigest())[:20]
    rows = []; setup = time.time()-start; start = time.time()
    for aspect, term in selected:
        _, diagnostic = core.run_term(modules, W, L, terms[aspect, term], 'genemaniaplus')
        rows.append({'aspect': aspect, 'term': term, 'seeds': len(terms[aspect, term]), **diagnostic})
    report = {'format': FORMAT+'.training-only-preflight', 'created_at': utcnow(),
        'protocol_sha256': protocol_sha256, 'selection': '20 training-only heads in fixed salted-SHA256 order',
        'rows': rows, 'setup_seconds': setup, 'measured_seconds': time.time()-start,
        'all_heads': len(terms), 'parameters': core.PARAMETERS['genemaniaplus'],
        'PK_outcomes_previously_seen': True, 'new_future_GO_labels_read': False,
        'first_attempt_note': 'The same 20 numerical checks passed; its final JSON save used a string instead of Path and failed. No predictions or reference labels were changed.'}
    report['content_sha256'] = digest(report)
    output = Path(output); core.need(not output.exists(), 'choose a new preflight receipt.')
    write_json(output, report); return report


def predict(frozen, protocol_sha256, author, author_receipt, preflight_report,
            preflight_sha256, output):
    preflight_report = Path(preflight_report)
    timing = read(preflight_report)
    core.need(sha(preflight_report) == preflight_sha256 and timing['protocol_sha256'] == protocol_sha256
        and timing['new_future_GO_labels_read'] is False
        and timing['content_sha256'] == digest({k:v for k,v in timing.items() if k!='content_sha256'}),
        'pre-outcome numerical preflight differs.')
    folder = new_output(output, frozen, preflight_report)
    pins = {str(Path(p).resolve()): sha(p) for p in (Path(frozen)/'protocol.json',
        Path(__file__), Path(core.__file__), Path(author_receipt), preflight_report)}
    commitment = {'format': FORMAT, 'created_at': utcnow(), 'input_files_sha256': pins,
        'protocol_sha256': protocol_sha256, 'parameters': core.PARAMETERS['genemaniaplus'],
        'method': 'strict_alias_genemaniaplus', 'target_frame': 'The unchanged547 NK/LK union, with exact aspect eligibility enforced by the separate reference release.',
        'choice_timing': 'Supplement chosen after old-graph PK GeneMANIA+ improved over LocalPlus, before any NK/LK GO reference labels were decoded.',
        'endpoint': 'All six setting/aspect native outcomes; exploratory supplementary comparison with all five frozen transport arms.',
        'new_fit_or_threshold_selection': False, 'new_future_GO_labels_read': False,
        'primary_five_arm_protocol_modified': False, 'PK_outcomes_previously_seen': True,
        'whole_graph_accuracy_or_independent_study_replication_claimed': False,
        'numerical_integration_version':2,
        'numerical_validation':'Unchanged native CG residual tolerance, M-matrix structure, and Varah1975 residual-infinity/diagonal-dominance bound; no assumed exact component positivity.',
        'native_scores_clipped_or_changed':False,
        'nonpositive_output_omission':'The original frozen writer still emits only raw positive scores; no positive cutoff or score rounding is introduced.',
        'prior_failure_preserved':'The v1 partial output and original adapter are retained separately; its overstrict probability-like guard failed before any NK/LK GO reference release.'}
    commitment['content_sha256'] = digest(commitment)
    # Durable selection commitment precedes all supplementary predictions.
    write_json(folder/'protocol.json', commitment)
    _, modules, W, L, terms, targets, target_indices = inputs(frozen, protocol_sha256, author, author_receipt)
    M, certificate = numerical_certificate(W,L)
    start = time.time(); count = 0; maximum_residual = 0.; maximum_iterations = 0
    negative_count = 0; minimum_score = 0.; maximum_bound = 0.
    with gzip.GzipFile(filename=str(folder/'strict_alias_genemaniaplus.tsv.gz'), mode='wb', mtime=0) as stream:
        for step, ((aspect, term), positives) in enumerate(sorted(terms.items()), 1):
            scores, diagnostic = author_scores(modules, L, M, certificate, positives)
            maximum_residual = max(maximum_residual, diagnostic['equation_residual_norm'])
            maximum_iterations = max(maximum_iterations, diagnostic['iterations'])
            maximum_bound = max(maximum_bound, diagnostic['componentwise_error_bound'])
            negative_count += diagnostic['negative_graph_scores']
            minimum_score = min(minimum_score, diagnostic['minimum_graph_score'])
            for protein, value in zip(targets, scores[target_indices]):
                if value > 0:
                    stream.write((protein+'\t'+term+'\t'+format(float(value), '.17g')+'\n').encode()); count += 1
            if step % 2000 == 0:
                print({'heads_completed': step, 'heads': len(terms), 'seconds': time.time()-start}, flush=True)
    load(frozen, protocol_sha256)
    for path, expected in pins.items(): core.need(sha(path) == expected, 'supplement input changed during scoring.')
    report = {'format': FORMAT+'.predictions', 'created_at': utcnow(),
        'protocol_file_sha256': sha(folder/'protocol.json'), 'protocol_content_sha256': commitment['content_sha256'],
        'target_count': len(targets), 'heads': len(terms), 'positive_rows': count,
        'wall_seconds': time.time()-start, 'new_future_GO_labels_read': False,
        'maximum_equation_residual_norm': maximum_residual, 'maximum_iterations': maximum_iterations,
        'numerical_integration_version':2,'matrix_certificate':certificate,
        'maximum_componentwise_error_bound':maximum_bound,'negative_graph_score_values':negative_count,
        'minimum_native_graph_score':minimum_score,'native_scores_clipped_or_changed':False,
        'every_head_passed_pinned_author_convergence_check': True,
        'files': {p.name: {'sha256':sha(p), 'bytes':p.stat().st_size} for p in folder.iterdir() if p.is_file()}}
    report['content_sha256'] = digest(report); write_json(folder/'predictions.json', report); return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['preflight', 'predict'])
    for name in ('frozen', 'protocol-sha256', 'author', 'author-receipt', 'output'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--preflight-report'); parser.add_argument('--preflight-sha256')
    values = vars(parser.parse_args()); command = values.pop('command')
    if command == 'preflight':
        values.pop('preflight_report'); values.pop('preflight_sha256')
    else:
        core.need(values['preflight_report'] and values['preflight_sha256'], 'preflight receipt and pin required.')
    import json
    print(json.dumps(globals()[command](**values), indent=2))
