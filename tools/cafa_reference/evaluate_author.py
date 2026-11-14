"""Release a frozen CAFA5 reference and invoke its unchanged author evaluator.

This is an optional research command. It does not import the GPL author code
into the application, retrieve sources, alter predictions, or modify a graph.
Prediction and method-file pins are explicit, and verified before the first
future GO label is decoded. Download all artifacts separately under their terms.
"""
import argparse
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .intake import ASPECTS, HEADER, check_archive, need, node_frame, regular_members

POLICY = {'primary': 'partial knowledge biological_process',
    'primary_metric': 'unweighted micro Fmax (author f_micro)',
    'secondary_metrics': ['unweighted macro Fmax', 'IA-weighted micro and macro Fmax', 'Smin'],
    'secondary': ['partial knowledge molecular_function', 'partial knowledge cellular_component',
                  'annotations attributed to publications after t0'],
    'author_evaluator_revision': 'e386b085e204ccfbd75a4f52c1a8b25987d8b465',
    'propagation': 'fill', 'normalization': 'cafa', 'no_orphans': True,
    'threshold_step': 0.001, 'threshold_grid': 'np.arange(0.001, 1, 0.001)',
    'max_terms': None, 'future_known_file_feature_use': False,
    'fixed_operating_threshold': 0.5,
    'fixed_threshold_metrics': ['unweighted micro PPV', 'unweighted micro recall', 'unweighted micro F1'],
    'bootstrap': {'scope': 'paired primary biological_process proteins', 'draws': 2000,
                  'seed': 20261113, 'requires_author_point_curve_agreement': True}}


def pinned(path, expected):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and sha(path) == expected, 'pinned file differs: '+str(path))
    return path


def verify_plan(config):
    """The config binds the real producer protocol/manifests, not a metric result."""
    need(config['policy'] == POLICY, 'evaluation policy differs from the pre-outcome contract.')
    need(isinstance(config['methods'], dict) and config['methods'], 'sealed prediction methods are required.')
    need(isinstance(config['freeze_files_sha256'], dict) and config['freeze_files_sha256'],
         'a nonempty producer method/source freeze is required.')
    pins = dict(config['freeze_files_sha256'])
    remote_names=set(config.get('remote_method_names',[]))
    need(remote_names<=set(config['methods']), 'remote execution names must be declared methods.')
    remote={}
    if remote_names:
        binding=config['remote_method_verification']
        receipt=pinned(binding['file'],binding['sha256'])
        remote=json.loads(receipt.read_text())
        need(remote['format']=='biograph-steward.cafa5-remote-file-verification.v1'
             and remote['future_GO_labels_read'] is False and remote['remote_host']
             and remote['observed_at']
             and remote['observer_code_sha256']==sha(Path(__file__).with_name('remote_verify_predictions.py')),
             'a fresh pinned SSH observation of frozen remote file bytes is required.')
        pins[str(receipt)]=binding['sha256']
    for role in ('ontology', 'ia', 'toi'):
        pinned(config[role], config[role+'_sha256'])
        pins[config[role]] = config[role+'_sha256']
    if 'target_ids' in config:
        pinned(config['target_ids'],config['target_ids_sha256'])
        pins[config['target_ids']]=config['target_ids_sha256']
    need(config['author_files_sha256'], 'pinned unchanged author source is required.')
    for relative, expected in config['author_files_sha256'].items():
        file=Path(config['author_source'])/relative
        pinned(file,expected);pins[str(file)]=expected
    for name, spec in config['methods'].items():
        need(name and all(c.isalnum() or c in '_-' for c in name), 'unsafe method name.')
        need(set(spec) == {'file', 'sha256'}, 'prediction binding requires exact file and SHA256.')
        if name in remote_names:
            observed=remote['files'][spec['file']]
            need(observed['sha256']==observed['expected_sha256']==spec['sha256']
                 and observed['bytes']==observed['expected_bytes'] and observed['bytes']>0,
                 'remote prediction bytes disagree with the sealed producer manifest.')
        else:
            pinned(spec['file'], spec['sha256']); pins[spec['file']] = spec['sha256']
    need(pins, 'method/source freeze proof is required.')
    for path, expected in pins.items(): pinned(path, expected)
    return pins


def filter_known(source, output, ids):
    """Retain exact native rows only for the predefined protein frame.

    Author gt_exclude_parser itself discards every other protein after building
    dense matrices. Filtering before that parser is semantically identical and
    avoids allocating matrices for all137k source proteins.
    """
    n = 0
    with Path(source).open('rb') as src, Path(output).open('wb') as dst:
        header = next(src); need(header.rstrip(b'\r\n') == HEADER, 'known header differs.')
        dst.write(header)
        for raw in src:
            target = raw.partition(b'\t')[0].decode('ascii')
            if target in ids: dst.write(raw); n += 1
    return n


def filter_truth(stream, output, ids):
    """This function may run only after the caller has recorded release proof."""
    by = {a: set() for a in ASPECTS}; rows = Counter()
    with Path(output).open('wb') as dst:
        header = next(stream); need(header.rstrip(b'\r\n') == HEADER, 'future header differs.')
        dst.write(header)
        for raw in stream:
            fields = raw.rstrip(b'\r\n').split(b'\t')
            need(len(fields) == 3, 'native future row shape differs.')
            target = fields[0].decode('ascii')
            if target not in ids: continue
            term, aspect = fields[1].decode('ascii'), fields[2].decode('ascii')
            need(term.startswith('GO:') and aspect in ASPECTS, 'native future term/aspect differs.')
            dst.write(raw); by[aspect].add(target); rows[aspect] += 1
    return {'raw_rows_by_aspect': dict(rows), 'raw_proteins_by_aspect': {a:len(v) for a,v in by.items()},
            'raw_protein_union': len(set.union(*by.values()))}


def release_frame(config):
    """An optional exact target list narrows, and can never expand, source nodes."""
    nodes=pinned(config['nodes'],config['nodes_sha256']); ids=node_frame(nodes)
    if 'target_ids' in config:
        path=pinned(config['target_ids'],config['target_ids_sha256'])
        targets=path.read_text().splitlines()
        need(targets and len(targets)==len(set(targets)) and all(t and t in ids for t in targets),
             'explicit reference target IDs must be unique exact members of the pinned source frame.')
        ids=set(targets)
    return nodes,ids


def release(config_path, output):
    config_path = Path(config_path)
    config = json.loads(config_path.read_text()); pins = verify_plan(config)
    meta = json.loads(Path(config['metadata']).read_text())
    archive = Path(config['archive']); source = check_archive(archive, meta, 'full_evaluation.tar.gz')
    nodes, ids = release_frame(config)
    known = pinned(config['known_t0'], config['known_t0_sha256'])
    secondary = Path(config['secondary_archive'])
    second_source = check_archive(secondary, meta, 'other_evaluations.tar.gz')
    folder = new_output(output, config_path, archive, secondary, nodes, known)
    event = {'format': 'biograph-steward.cafa5-future-label-release.v1', 'created_at': utcnow(),
        'prediction_and_method_freeze_verified_before_future_GO_decode': True,
        'config_sha256': sha(config_path), 'verified_freeze_files_sha256': pins,
        'primary_archive': source, 'secondary_archive': second_source, 'policy': POLICY,
        'scope': 'Public retrospective temporal benchmark; prior GOA corpus exposure is disclosed.',
        'released_target_IDs':len(ids),
        'target_ids_sha256':config.get('target_ids_sha256')}
    event['content_sha256'] = digest(event); write_json(folder/'truth_access_started.json', event)
    # No future GO term is interpreted above this line.
    counts = {}
    with tarfile.open(archive, 'r:gz') as tar:
        members = regular_members(tar)
        name = 'full_evaluation/eval_terms_partial_2025_03.tsv'
        counts['partial'] = filter_truth(tar.extractfile(members[name]), folder/'partial.tsv', ids)
    counts['known_t0_rows'] = filter_known(known, folder/'known_t0_frame.tsv', ids)
    with tarfile.open(secondary, 'r:gz') as tar:
        members = regular_members(tar)
        prefix = 'other_evaluations/new_publications/'
        counts['partial_publishedaftert0'] = filter_truth(tar.extractfile(members[prefix+
            'eval_terms_partial_2025_03_publishedaftert0.tsv']), folder/'partial_publishedaftert0.tsv', ids)
        # This source includes later curation of older papers; evaluation-only.
        temp = folder/'known_publications_source.tsv'
        with temp.open('wb') as f: shutil.copyfileobj(tar.extractfile(members[prefix+'known_publishedaftert0.tsv']), f)
        counts['known_publishedaftert0_rows'] = filter_known(temp, folder/'known_publishedaftert0_frame.tsv', ids)
        temp.unlink()
    need(verify_plan(config) == pins, 'prediction/method inputs changed during reference release.')
    report = {'format':'biograph-steward.cafa5-released-frame.v1','created_at':utcnow(),
        'release_content_sha256':event['content_sha256'],'config_sha256':sha(config_path),'counts':counts,
        'future_GO_columns_decoded':True,'source_rows_rewritten':False,'source_graph_changed':False,
        'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
    report['content_sha256']=digest(report);write_json(folder/'report.json',report)
    return report


def execution_subset(config, methods=None, settings=None, secondary=False):
    names=list(config['methods']) if methods is None else methods
    need(names and len(names)==len(set(names)) and set(names)<=set(config['methods']),
         'execution method subset is outside the sealed comparison.')
    need(not (settings is not None and secondary), 'choose an explicit setting list or the secondary flag.')
    settings=(['partial']+(['partial_publishedaftert0'] if secondary else [])) if settings is None else settings
    need(settings and len(settings)==len(set(settings)) and set(settings)<= {'partial','partial_publishedaftert0'},
         'unreviewed or repeated execution setting.')
    return names,settings


def evaluate(config_path, reference, output, *, python, author_source, threads=1, secondary=False,
             methods=None, settings=None):
    config_path, reference, author_source = map(Path, (config_path, reference, author_source))
    config = json.loads(config_path.read_text()); pins = verify_plan(config)
    ref = json.loads((reference/'report.json').read_text())
    need(ref.get('config_sha256') == sha(config_path) and ref.get('future_GO_columns_decoded') is True,
         'released reference belongs to a different frozen model/config.')
    for name, expected in ref['files'].items(): pinned(reference/name, expected)
    for path, expected in config['author_files_sha256'].items(): pinned(author_source/path, expected)
    need(type(threads) is int and threads > 0, 'positive CPU worker count required.')
    folder = new_output(output, reference, config_path, author_source)
    env = dict(os.environ); env['PYTHONPATH'] = str((author_source/'src').resolve())
    env['MPLBACKEND'] = 'Agg'
    env['OPENBLAS_NUM_THREADS'] = '1';env['OMP_NUM_THREADS'] = '1';env['MKL_NUM_THREADS'] = '1'
    outputs = {}
    names,settings=execution_subset(config,methods,settings,secondary)
    need(not set(names)&set(config.get('remote_method_names',[])),
         'use the byte-pinned remote author driver for the declared remote execution partition.')
    for setting in settings:
        truth = reference/(setting+'.tsv')
        known = reference/('known_publishedaftert0_frame.tsv' if setting != 'partial' else 'known_t0_frame.tsv')
        for method in names:
            spec=config['methods'][method]
            work = folder/setting/method; work.mkdir(parents=True)
            pred = work/'predictions'; pred.mkdir(); plain = pred/(method+'.tsv')
            src = Path(spec['file'])
            if src.suffix == '.gz':
                with gzip.open(src,'rb') as f, plain.open('wb') as dst: shutil.copyfileobj(f,dst)
            else: shutil.copyfile(src,plain)
            job={'author_call':{'obo_file':str(Path(config['ontology']).resolve()),'pred_dir':str(pred.resolve()),
                'gt_file':str(truth.resolve()),'ia':str(Path(config['ia']).resolve()),
                'toi_file':str(Path(config['toi']).resolve()),'exclude':str(known.resolve()),
                'prop':'fill','norm':'cafa','th_step':0.001,'no_orphans':True,'n_cpu':threads},
                'output_dir':str((work/'scores').resolve())}
            write_json(work/'job.json',job)
            runner=Path(__file__).with_name('author_point_runner.py').resolve()
            cmd = [str(python),str(runner),'--job-json',str((work/'job.json').resolve())]
            write_json(work/'command.json', {'command':cmd,'source_prediction_sha256':spec['sha256'],
                'decompressed_prediction_sha256':sha(plain),'author_source':str(author_source),'policy':POLICY,
                'adapter_sha256':sha(runner)})
            with (work/'author.log').open('w') as log:
                completed = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, cwd=folder.resolve())
            need(completed.returncode == 0, 'author evaluator failed; preserve log at '+str(work/'author.log'))
            outputs[setting+'/'+method] = {p.relative_to(work).as_posix():sha(p) for p in work.rglob('*')
                                          if p.is_file() and pred not in p.parents}
            plain.unlink();pred.rmdir()
            write_json(folder/'progress.json', {'completed':list(outputs),'updated_at':utcnow()})
    need(verify_plan(config) == pins, 'prediction/method inputs changed during scoring.')
    report = {'format':'biograph-steward.cafa5-author-evaluation.v1','created_at':utcnow(),
        'reference_content_sha256':ref['content_sha256'],'config_sha256':sha(config_path),'policy':POLICY,
        'author_source_sha256':config['author_files_sha256'],'outputs':outputs,'method_files_changed':False,
        'execution_methods':names,'execution_settings':settings,
        'all_declared_methods_scored_in_this_partition':set(names)==set(config['methods']),
        'execution_partition_changes_no_frozen_predictions_or_method_choices':True,
        'source_graph_changed':False,'author_code_modified':False}
    report['content_sha256']=digest(report);write_json(folder/'report.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('release');r.add_argument('--config',required=True);r.add_argument('--output',required=True)
    e=sub.add_parser('evaluate');
    for name in ('config','reference','output','python','author-source'):e.add_argument('--'+name,required=True)
    e.add_argument('--threads',type=int,default=1);e.add_argument('--secondary',action='store_true')
    e.add_argument('--method',action='append',dest='methods',help='Execute one declared method; repeat for independent execution partitions.')
    e.add_argument('--only-setting',action='append',dest='settings',choices=['partial','partial_publishedaftert0'])
    a=vars(p.parse_args());command=a.pop('command');a['config_path']=a.pop('config')
    result = release(**a) if command=='release' else evaluate(**a)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
