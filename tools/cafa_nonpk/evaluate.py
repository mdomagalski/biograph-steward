"""Gate separately frozen NK/LK labels and run the unchanged CAFA evaluator.

This transport assessment follows the already observed PK comparison. It is
not a new model fit, an independent-study test, or a change to the PK protocol.
The --job-json mode is a process-isolated adapter, usable without installing
the application beside the separately licensed author evaluator.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tarfile


NS = {'BPO': 'biological_process', 'MFO': 'molecular_function', 'CCO': 'cellular_component'}


def point(job_path):
    """Only author APIs compute reference propagation, curves and denominators."""
    import numpy as np
    import pandas as pd
    from cafaeval.evaluation import cafa_eval, write_results
    from cafaeval.parser import obo_parser, update_toi, gt_parser
    job = json.loads(Path(job_path).read_text()); call = job['author_call']
    if not (call['exclude'] is None and call['prop'] == 'fill' and call['norm'] == 'cafa'
            and call['no_orphans'] is True and call['th_step'] == .001):
        raise ValueError('Native NK/LK execution requires the frozen non-exclusion policy.')
    if (np.__version__, pd.__version__) != ('1.26.4', '2.2.3'):
        raise ValueError('Use the already standardized NumPy1.26.4/Pandas2.2.3 runtime.')
    out = Path(job['output_dir']); out.mkdir(parents=True, exist_ok=False)
    # Native parser/TOI definitions are the same ones called by cafa_eval.
    ontologies = update_toi(obo_parser(call['obo_file'], ('is_a', 'part_of'), call['ia'], False), call['toi_file'])
    ground = gt_parser(call['gt_file'], ontologies)
    denominators = {}
    for aspect, ns in NS.items():
        if ns not in ground:
            denominators[ns] = {'author_recognized_target_IDs': 0, 'eligible_proteins': 0,
                'IA_eligible_proteins': 0, 'TOI_reference_pairs': 0}
            continue
        matrix = ground[ns].matrix; ontology = ontologies[ns]
        denominators[ns] = {'author_recognized_target_IDs': len(ground[ns].ids),
            'eligible_proteins': int(np.count_nonzero(matrix[:, ontology.toi].sum(1) > 0)),
            'IA_eligible_proteins': int(np.count_nonzero((matrix[:, ontology.toi_ia] * ontology.ia[ontology.toi_ia]).sum(1) > 0)),
            'TOI_reference_pairs': int(matrix[:, ontology.toi].sum())}
    df, best = cafa_eval(**call)
    outcomes = {}; fixed = []
    if df is not None:
        write_results(df, best, out_dir=str(out), th_step=call['th_step'])
        df.to_csv(out/'evaluation_all_exact.tsv', sep='\t', float_format='%.17g')
        plain = df.reset_index()
        for (filename, ns), group in plain.groupby(['filename', 'ns']):
            chosen = group[(group['tau'] - .5).abs() < 1e-12]
            if len(chosen) > 1: raise ValueError('The author fixed-threshold row is not unique.')
            row = {'filename': filename, 'namespace': ns, 'threshold': .5}
            if chosen.empty:
                row.update(status='author omits thresholds with zero prediction coverage', PPV=None, recall=None, F1=None)
            else:
                item = chosen.iloc[0]
                row.update(status='unchanged author curve at predeclared threshold', PPV=float(item['pr_micro']),
                    recall=float(item['rc_micro']), F1=float(item['f_micro']), coverage=float(item['cov']))
            fixed.append(row)
            outcomes[ns] = {'status': 'scored', 'native_curve_rows': len(group)}
    for ns in NS.values():
        outcomes.setdefault(ns, {'status': 'no_native_curve', 'reason':
            'The unchanged author evaluator returned no curve for this namespace; no zero metric is imputed.'})
        outcomes[ns].update(denominators[ns])
    (out/'fixed_threshold_0_5.json').write_text(json.dumps({'threshold_selected_using_test_labels': False,
        'rows': fixed, 'interpretation': 'Reference operating point, not calibrated acceptance probability.'}, indent=2)+'\n')
    (out/'native_outcomes.json').write_text(json.dumps({'known_exclusion': None,
        'numpy': np.__version__, 'pandas': pd.__version__, 'namespaces': outcomes}, indent=2)+'\n')


# The existing isolated remote_author driver invokes --job-json directly.
# Avoid requiring any MIT application imports in that author-only process.
if __name__ == '__main__' and '--job-json' in sys.argv:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--job-json', required=True)
    point(parser.parse_args().job_json)
    raise SystemExit(0)

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.cafa_reference.intake import HEADER, ACCESSION, check_archive, regular_members, need
from tools.cafa_reference.evaluate_author import pinned
from tools.cafa_nonpk.run import load, SETTINGS, ASPECTS, FORMAT as PRODUCER_FORMAT

FORMAT = 'biograph-steward.cafa5-nonpk-evaluation-freeze.v1'
POLICY = {'settings': list(SETTINGS), 'aspects': list(ASPECTS), 'known_exclusion': None,
    'prop': 'fill', 'norm': 'cafa', 'no_orphans': True, 'threshold_step': .001,
    'fixed_operating_threshold': .5, 'author_evaluator_revision': 'e386b085e204ccfbd75a4f52c1a8b25987d8b465',
    'expected_versions': {'numpy': '1.26.4', 'pandas': '2.2.3'},
    'scope': 'All six native NK/LK setting/aspect outcomes; post-PK transport, not independent-study replication.',
    'no_missing_outcome_imputation': True, 'new_fit_or_threshold_selection': False}


def sealed(path, expected):
    value = json.loads(pinned(path, expected).read_text())
    need(isinstance(value, dict) and value.get('content_sha256') == digest({k:v for k,v in value.items() if k!='content_sha256'}),
         'input content seal differs.')
    return value


def producer(folder, expected, kind, protocol_sha256, count):
    folder = Path(folder); name = 'predictions.json' if kind == 'predictions' else 'qualification.json'
    result = sealed(folder/name, expected)
    need(result.get('format') == PRODUCER_FORMAT+'.'+kind and result.get('protocol_sha256') == protocol_sha256
         and result.get('target_count') == count and result.get('new_future_GO_labels_read') is False,
         'the complete pre-outcome producer boundary differs.')
    files = result.get('files'); need(isinstance(files, dict) and files, 'producer has no complete file inventory.')
    for file, spec in files.items():
        need(Path(file).name == file and set(spec)=={'bytes','sha256'}, 'unsafe/incomplete producer file entry.')
        path = pinned(folder/file, spec['sha256'])
        need(path.stat().st_size == spec['bytes'], 'producer byte size differs.')
    return result


def freeze(frozen, protocol_sha256, predictions, predictions_sha256, controls, controls_sha256,
           parent_pk_config, parent_pk_config_sha256, output):
    frozen, predictions, controls = map(Path, (frozen, predictions, controls))
    plan = load(frozen, protocol_sha256)
    need(set(plan['historical_eligibility'])=={s+'_'+a for s in SETTINGS for a in ASPECTS}
         and all(row['targets_with_training_rows_in_aspect']==0 for row in plan['historical_eligibility'].values()),
         'native NK/LK matching-aspect historical eligibility must be explicit and unchanged.')
    model = producer(predictions, predictions_sha256, 'predictions', protocol_sha256, plan['targets'])
    native = producer(controls, controls_sha256, 'controls', protocol_sha256, plan['targets'])
    parent = json.loads(pinned(parent_pk_config, parent_pk_config_sha256).read_text())
    need(parent['policy']['author_evaluator_revision'] == POLICY['author_evaluator_revision'], 'unchanged author evaluator required.')
    methods = {name: {'file': str((predictions if name=='strict_alias_localplus' else controls)/(name+'.tsv.gz')),
        'sha256': (model if name=='strict_alias_localplus' else native)['files'][name+'.tsv.gz']['sha256']}
        for name in plan['methods']}
    pins = {str(Path(__file__).resolve()): sha(__file__), str(Path(frozen/'protocol.json').resolve()): protocol_sha256,
        str(Path(predictions/'predictions.json').resolve()): predictions_sha256,
        str(Path(controls/'qualification.json').resolve()): controls_sha256,
        str(Path(parent_pk_config).resolve()): parent_pk_config_sha256}
    inputs = {}
    for name in ('metadata', 'archive', 'ontology', 'ia', 'toi'):
        path = Path(parent[name]); inputs[name] = str(path.resolve()); pins[str(path.resolve())] = sha(path)
    for name, expected in parent['author_files_sha256'].items():
        path = pinned(Path(parent['author_source'])/name, expected); pins[str(path.resolve())] = expected
    ids = {}
    for setting in SETTINGS:
        ids[setting] = {}
        for aspect in ASPECTS:
            path = frozen/(setting+'_'+aspect+'.txt'); rows = path.read_text().splitlines()
            need(rows and len(rows)==len(set(rows)) and all(ACCESSION.fullmatch(p) for p in rows), 'fixed identity/aspect frame differs.')
            ids[setting][aspect] = {'file':str(path.resolve()), 'sha256':sha(path), 'count':len(rows)}
            pins[str(path.resolve())] = sha(path)
    source = check_archive(inputs['archive'], json.loads(Path(inputs['metadata']).read_text()), 'full_evaluation.tar.gz')
    value = {'format': FORMAT, 'created_at': utcnow(), 'policy': POLICY, 'protocol_sha256': protocol_sha256,
        'protocol_content_sha256': plan['content_sha256'], 'target_count': plan['targets'], 'methods': methods,
        'author_source': parent['author_source'], 'author_files_sha256': parent['author_files_sha256'],
        'identities': ids, 'inputs': inputs, 'input_files_sha256': pins, 'archive_source': source,
        'new_future_GO_labels_read': {s:False for s in SETTINGS}, 'PK_outcomes_previously_seen': True,
        'scientific_interpretation': plan['setting_semantics'], 'new_fit_or_threshold_selection': False}
    value['content_sha256'] = digest(value)
    output = Path(output); need(not output.exists(), 'choose a new evaluation freeze file.')
    write_json(output, value); verify(output, sha(output)); return value


def verify(config, expected):
    value = sealed(config, expected)
    need(value.get('format') == FORMAT and value.get('policy') == POLICY
         and value.get('new_future_GO_labels_read') == {s:False for s in SETTINGS}
         and value.get('PK_outcomes_previously_seen') is True and value.get('new_fit_or_threshold_selection') is False,
         'the frozen nonPK evaluation policy/exposure differs.')
    need(set(value['methods']) == {'strict_alias_localplus','official_blast','official_prott5_cosine3','official_nonexperimental','official_naive'},
         'preserve all five fixed nonPK arms.')
    for path, expected in value['input_files_sha256'].items(): pinned(path, expected)
    for spec in value['methods'].values(): pinned(spec['file'], spec['sha256'])
    for setting in SETTINGS:
        need(set(value['identities'][setting]) == set(ASPECTS), 'all native aspect frames are required.')
        for spec in value['identities'][setting].values():
            rows = pinned(spec['file'],spec['sha256']).read_text().splitlines()
            need(len(rows)==spec['count'] and len(rows)==len(set(rows)) and all(ACCESSION.fullmatch(p) for p in rows),
                 'identity frame count/uniqueness differs.')
    return value


def filter_truth(stream, output, by_aspect):
    """Release only exact predeclared (protein, native aspect) pairs, byte intact."""
    need(set(by_aspect) == set(ASPECTS), 'all fixed aspect frames are required.')
    ids = {a:set(rows) for a,rows in by_aspect.items()}; proteins = {a:set() for a in ASPECTS}; counts = Counter()
    with Path(output).open('wb') as dst:
        header = next(stream); need(header.rstrip(b'\r\n') == HEADER, 'native future header differs.'); dst.write(header)
        for raw in stream:
            parts = raw.rstrip(b'\r\n').split(b'\t'); need(len(parts)==3, 'native future row shape differs.')
            protein, aspect = parts[0].decode('ascii'), parts[2].decode('ascii')
            need(ACCESSION.fullmatch(protein) and aspect in ASPECTS, 'native target/aspect metadata differs.')
            if protein not in ids[aspect]: continue
            term = parts[1].decode('ascii'); need(term.startswith('GO:') and len(term)==10 and term[3:].isdigit(), 'native GO term differs.')
            dst.write(raw); proteins[aspect].add(protein); counts[aspect] += 1
    return {'raw_rows_by_aspect':{a:counts[a] for a in ASPECTS},
        'raw_proteins_by_aspect':{a:len(proteins[a]) for a in ASPECTS},
        'raw_protein_union':len(set().union(*proteins.values()))}


def verify_supplement(folder, protocol_sha256, predictions_sha256, parent_protocol_sha256, target_count):
    """The GM supplement is separately selected/pinned; the five-arm plan stays intact."""
    folder=Path(folder); protocol=sealed(folder/'protocol.json',protocol_sha256)
    prediction=sealed(folder/'predictions.json',predictions_sha256)
    fmt='biograph-steward.cafa5-nonpk-gm-supplement.v1'
    need(protocol.get('format')==fmt and protocol.get('protocol_sha256')==parent_protocol_sha256
         and protocol.get('method')=='strict_alias_genemaniaplus' and protocol.get('parameters')=={'alpha':1,'tol':1e-5}
         and protocol.get('new_future_GO_labels_read') is False and protocol.get('new_fit_or_threshold_selection') is False
         and protocol.get('primary_five_arm_protocol_modified') is False and protocol.get('PK_outcomes_previously_seen') is True,
         'the separately frozen GM supplement boundary differs.')
    need(prediction.get('format')==fmt+'.predictions' and prediction.get('protocol_file_sha256')==protocol_sha256
         and prediction.get('protocol_content_sha256')==protocol['content_sha256']
         and prediction.get('target_count')==target_count and prediction.get('new_future_GO_labels_read') is False
         and prediction.get('every_head_passed_pinned_author_convergence_check') is True,
         'the completed supplementary prediction boundary differs.')
    for path,expected in protocol['input_files_sha256'].items():pinned(path,expected)
    for name,spec in prediction['files'].items():
        need(Path(name).name==name and set(spec)=={'sha256','bytes'},'invalid supplementary file inventory.')
        path=pinned(folder/name,spec['sha256']);need(path.stat().st_size==spec['bytes'],'supplement file size differs.')
    file=folder/'strict_alias_genemaniaplus.tsv.gz'
    need(file.name in prediction['files'],'missing supplementary method scores.')
    return {'protocol_file':str((folder/'protocol.json').resolve()),'protocol_file_sha256':protocol_sha256,
        'protocol_content_sha256':protocol['content_sha256'],
        'predictions_file':str((folder/'predictions.json').resolve()),'predictions_file_sha256':predictions_sha256,
        'predictions_content_sha256':prediction['content_sha256'],
        'method':'strict_alias_genemaniaplus','file':str(file.resolve()),'sha256':sha(file),
        'choice_timing':protocol['choice_timing'],'analysis_role':'Separate post-PK supplementary method; five-arm protocol unchanged.'}


def release(config, config_sha256, output, *, supplement=None, supplement_protocol_sha256=None,
            supplement_predictions_sha256=None):
    config = Path(config); value = verify(config, config_sha256)
    extra=None
    if any(p is not None for p in (supplement,supplement_protocol_sha256,supplement_predictions_sha256)):
        need(all(p is not None for p in (supplement,supplement_protocol_sha256,supplement_predictions_sha256)),
             'supply both explicit supplement FILE pins and its folder together.')
        extra=verify_supplement(supplement,supplement_protocol_sha256,supplement_predictions_sha256,
                                value['protocol_sha256'],value['target_count'])
    archive = value['inputs']['archive']
    source = check_archive(archive, json.loads(Path(value['inputs']['metadata']).read_text()), 'full_evaluation.tar.gz')
    need(source == value['archive_source'], 'the official reference archive changed.')
    folder = new_output(output, config)
    event = {'format':FORMAT+'.release-event', 'created_at':utcnow(), 'config_file_sha256':config_sha256,
        'config_content_sha256':value['content_sha256'], 'verified_freeze_files_sha256':value['input_files_sha256'],
        'prediction_files_sha256':{n:s['sha256'] for n,s in value['methods'].items()},
        'separately_frozen_supplement':extra,
        'new_future_GO_labels_decoded_before_this_event':False, 'policy':POLICY, 'archive_source':source}
    event['content_sha256']=digest(event); write_json(folder/'truth_access_started.json', event)
    # First permitted GO-column interpretation occurs after the durable event.
    counts = {}
    with tarfile.open(archive, 'r:gz') as tar:
        members = regular_members(tar)
        for setting in SETTINGS:
            member = 'full_evaluation/eval_terms_'+setting+'_2025_03.tsv'
            need(member in members, 'native setting file is missing.')
            by = {a:Path(spec['file']).read_text().splitlines() for a,spec in value['identities'][setting].items()}
            counts[setting] = filter_truth(tar.extractfile(members[member]), folder/(setting+'.tsv'), by)
    verify(config, config_sha256)
    if extra is not None:
        need(verify_supplement(supplement,supplement_protocol_sha256,supplement_predictions_sha256,
             value['protocol_sha256'],value['target_count'])==extra,'supplement changed during reference release.')
    report = {'format':FORMAT+'.released', 'created_at':utcnow(), 'config_file_sha256':config_sha256,
        'config_content_sha256':value['content_sha256'], 'release_event_content_sha256':event['content_sha256'],
        'future_GO_columns_decoded':True, 'scope':'Only the exact frozen NK/LK protein/aspect pairs; no PK or publication-reference expansion.',
        'counts':counts, 'known_exclusion':None, 'native_rows_rewritten':False, 'source_graph_changed':False,
        'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
    report['content_sha256']=digest(report); write_json(folder/'report.json',report); return report


def execution_jobs(config, config_sha256, reference, reference_sha256, paths, output,
                   *, author_source, dependency_pythonpath, python, temporary_directory, threads=1,
                   supplementary_only=False):
    """Rebase explicit files for the existing remote_author driver, without scoring."""
    value = verify(config,config_sha256); reference = Path(reference)
    ref = sealed(reference/'report.json',reference_sha256)
    need(ref.get('format')==FORMAT+'.released' and ref['config_file_sha256']==config_sha256
         and ref['future_GO_columns_decoded'] is True and ref['known_exclusion'] is None,
         'released reference belongs to another frozen nonPK evaluation.')
    need(isinstance(paths,dict) and type(threads) is int and threads>0, 'explicit execution file locations and CPU count required.')
    methods=value['methods']
    if supplementary_only:
        event=sealed(reference/'truth_access_started.json',ref['files']['truth_access_started.json'])
        extra=event.get('separately_frozen_supplement')
        need(isinstance(extra,dict),'supplement must have been pinned before the future-label release event.')
        checked=verify_supplement(Path(extra['protocol_file']).parent,extra['protocol_file_sha256'],
             extra['predictions_file_sha256'],value['protocol_sha256'],value['target_count'])
        need(checked==extra,'supplement differs from the pre-decode release event.')
        methods={extra['method']:{'file':extra['file'],'sha256':extra['sha256']}}
    required = {spec['file']:spec['sha256'] for spec in methods.values()}
    for name in ('ontology','ia','toi'):
        src=value['inputs'][name];required[src]=value['input_files_sha256'][src]
    for name,expected in value['author_files_sha256'].items(): required[str(Path(value['author_source'])/name)]=expected
    for name,expected in ref['files'].items():
        source=str((reference/name).resolve()); pinned(source,expected); required[source]=expected
    runner=str(Path(__file__).resolve());required[runner]=sha(runner)
    need(set(paths)==set(required) and all(isinstance(p,str) and p.startswith('/') for p in paths.values()),
         'execution map must cover exactly the already pinned files with absolute target paths.')
    pins={paths[src]:expected for src,expected in required.items()}
    need(len(pins)==len(required),'execution file paths collide.')
    for name in value['author_files_sha256']:
        need(paths[str(Path(value['author_source'])/name)]==str(Path(author_source)/name), 'author execution source path mapping differs.')
    jobs={'format':'biograph-steward.cafa5-remote-author-jobs.v1',
        'parent_evaluation_config_sha256':config_sha256, 'reference_content_sha256':ref['content_sha256'],
        'input_files_sha256':pins, 'methods':{name:{'file':paths[spec['file']],'sha256':spec['sha256']} for name,spec in methods.items()},
        'references':{setting:{'truth':paths[str((reference/(setting+'.tsv')).resolve())],'known':None} for setting in SETTINGS},
        **{name:paths[value['inputs'][name]] for name in ('ontology','ia','toi')},
        'author_source':author_source, 'dependency_pythonpath':dependency_pythonpath, 'python':python,
        'temporary_directory':temporary_directory, 'threads':threads, 'point_runner':paths[runner],
        'contributions':False, 'expected_versions':POLICY['expected_versions'],
        'nonPK_native_policy':POLICY, 'PK_protocol_or_predictions_changed':False,
        'execution_role':'separately frozen post-PK GM supplement' if supplementary_only else 'unchanged five-arm transport'}
    need(not Path(output).exists(),'choose a new execution-job file.'); write_json(output,jobs); return jobs


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('freeze')
    for name in ('frozen','protocol-sha256','predictions','predictions-sha256','controls','controls-sha256',
                 'parent-pk-config','parent-pk-config-sha256','output'):p.add_argument('--'+name,required=True)
    p=sub.add_parser('release')
    for name in ('config','config-sha256','output'):p.add_argument('--'+name,required=True)
    for name in ('supplement','supplement-protocol-sha256','supplement-predictions-sha256'):p.add_argument('--'+name)
    args=vars(parser.parse_args());command=args.pop('command');result=globals()[command](**args)
    print(json.dumps({k:v for k,v in result.items() if k in ('format','content_sha256','target_count','counts')},indent=2))


if __name__=='__main__':main()
