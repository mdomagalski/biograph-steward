"""Reuse the qualified author predictor on the existing NK/LK identity frame.

The author accepts arbitrary FASTA inputs. The earlier validated entry point
deliberately fixes the PK frame, so this separate adapter preserves that freeze
and reuses its unchanged extractor, models, parameters and saved predictions.
No reference annotation reader or evaluator is imported here.
"""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys

from biograph_steward.client import utcnow, write_json
from biograph_steward.file_utils import new_output
from tools.deepgo_reference.archive import fingerprints, need, sealed
from tools.deepgo_reference.native import extract_features, pinned, predict_aspect
from tools.deepgo_reference.run import (
    AUTHOR_ASPECT_ORDER, PARAMETERS, aspect_specs, author_and_heads,
    load as load_parent, read_seal, verify_sources, write_lines,
)
from tools.deepgo_reference.scores import native_rows, raw_rows
from tools.deepgo_reference.sequences import collect, frame

FORMAT = 'biograph-steward.deepgo-nonpk-development.v1'
FRAME_FILES = ('targets.txt', 'no_knowledge_targets.txt', 'limited_targets.txt') + tuple(
    s+'_'+a+'.txt' for s in ('no_knowledge', 'limited') for a in ('BPO', 'MFO', 'CCO'))


def identities(config, upstream):
    need(set(config['frames']) == set(FRAME_FILES), 'all original NK/LK identity lists required.')
    result = {}
    for name, spec in config['frames'].items():
        need(spec['sha256'] == upstream['files'][name], 'original target-list pin differs.')
        result[name] = frame(spec['file'], spec['sha256'])
    nk, lk = map(set, (result['no_knowledge_targets.txt'], result['limited_targets.txt']))
    need(not nk & lk and nk | lk == set(result['targets.txt'])
         and (len(nk), len(lk), len(result['targets.txt'])) == (133, 414, 547),
         'existing disjoint population frame differs.')
    for setting, population in (('no_knowledge', nk), ('limited', lk)):
        for aspect in ('BPO', 'MFO', 'CCO'):
            values = set(result[setting+'_'+aspect+'.txt'])
            need(values <= population and len(values) == upstream['counts'][setting][aspect],
                 'native protein/aspect membership differs.')
    return result


def inputs(config):
    need(config['format'] == FORMAT+'.inputs' and config['references_already_exposed'] is True,
         'explicit consumed-reference development scope required.')
    parent = load_parent(config['parent_frozen'], config['parent_protocol_sha256'])
    model, old_sequences, _, covered, _ = verify_sources(parent['inputs'])
    upstream = read_seal(pinned(config['upstream_nonpk_protocol']))
    ids = identities(config, upstream)
    forecasts = read_seal(pinned(config['parent_predictions']))
    need(forecasts['format'] == 'biograph-steward.deepgo-development.v1.predictions'
         and forecasts['protocol_file_sha256'] == config['parent_protocol_sha256']
         and forecasts['runtime'] == parent['runtime']
         and forecasts['source_and_score_postprocessing'] == PARAMETERS
         and forecasts['all_evaluation_denominators_retained'] is True
         and len(forecasts['files']) == 6, 'complete unchanged parent forecasts required.')
    parity = read_seal(pinned(forecasts['native_parity_file']))
    need(parity['all_three_aspects_exact'] is True and parity['runtime'] == parent['runtime']
         and parity['protocol_file_sha256'] == config['parent_protocol_sha256'],
         'qualified native CLI parent differs.')
    directory = Path(config['parent_predictions']['file']).parent
    for name, spec in forecasts['files'].items():
        need(Path(name).name == name and fingerprints(directory/name) == spec,
             'saved parent forecast changed.')
    pinned(config['dated_fasta'])
    need(config['dated_fasta']['sha256'] == old_sequences['source_fasta_file_sha256'],
         'same dated canonical FASTA required; no current-sequence fallback.')
    cached = sorted(set(ids['targets.txt']) & set(covered))
    new = sorted(set(ids['targets.txt']) - set(covered))
    need((len(cached), len(new)) == (210, 337), 'fixed cached/new identity inventory differs.')
    return parent, model, old_sequences, ids, forecasts, cached, new


def prepare(config, output):
    config = Path(config); cfg = json.loads(config.read_text())
    parent, _, old_sequences, ids, _, cached, new = inputs(cfg)
    from Bio import SeqIO
    with gzip.open(cfg['dated_fasta']['file'], 'rt') as stream:
        found = collect(SeqIO.parse(stream, 'fasta'), set(ids['targets.txt']))
    missing = sorted(set(ids['targets.txt'])-set(found))
    for accession in cached:
        need(accession in found and found[accession]['sequence_sha256'] ==
             old_sequences['source_records'][accession]['sequence_sha256'],
             'cached identity has a different dated sequence.')
    out = new_output(output, config)
    fasta = out/'new_targets.fasta'
    with fasta.open('w') as stream:
        for accession in new:
            if accession in found:
                stream.write('>'+accession+'\n'+found[accession]['sequence']+'\n')
    value = sealed({'format': FORMAT+'.freeze', 'created_at': utcnow(), 'inputs': cfg,
        'input_config_sha256': fingerprints(config)['sha256'],
        'adapter_file_sha256': fingerprints(__file__)['sha256'], 'parent_runtime': parent['runtime'],
        'parameters': PARAMETERS, 'target_count': 547, 'cached_target_ids': cached,
        'new_target_ids': new, 'missing_sequence_ids': missing,
        'sequence_records': {p:{k:v for k,v in row.items() if k!='sequence'} for p,row in found.items()},
        'new_fasta': {'file':str(fasta.resolve()), **fingerprints(fasta)},
        'population_counts': {'no_knowledge':133, 'limited':414},
        'reference_exposure': 'All NK/LK reference outcomes were previously evaluated; development extension, not a fresh test.',
        'evaluation_scope': 'Both existing settings/all three aspects; unchanged native exclude=None/fill/ontology/IA/TOI/grid. MFO designated focus before new scores.',
        'uncertainty_plan': 'Existing2000 paired protein draws/seed20261113, MFO ordinary+IA versus retained LocalPlus and official nonexperimental control in BOTH settings; preserve every aspect/control outcome.',
        'adoption_from_this_development_extension': False,
        'original_PK_protocol_or_forecasts_changed': False, 'model_or_threshold_fit': False,
        'reference_annotation_rows_read': False, 'current_sequence_fallback': False,
        'status': 'ready' if not missing else 'incomplete_keep_full_reference_denominators'})
    write_json(out/'protocol.json', value)
    return value


def load(frozen, expected):
    path = Path(frozen)/'protocol.json'
    need(fingerprints(path)['sha256'] == expected, 'nonPK freeze FILE differs.')
    value = read_seal(path, FORMAT+'.freeze')
    need(value['adapter_file_sha256'] == fingerprints(__file__)['sha256']
         and value['status'] == 'ready' and not value['missing_sequence_ids']
         and value['parameters'] == PARAMETERS
         and value['adoption_from_this_development_extension'] is False,
         'unchanged complete development freeze required.')
    parent, model, _, _, forecasts, cached, new = inputs(value['inputs'])
    need(value['parent_runtime'] == parent['runtime'] and value['cached_target_ids'] == cached
         and value['new_target_ids'] == new, 'frozen source/runtime/frame differs.')
    pinned(value['new_fasta'])
    return value, parent, model, forecasts


def copy_rows(source, wanted, terms, destination, counts):
    """Copy literal saved score rows; enforce exact heads/order and one vector/ID."""
    with gzip.open(source, 'rb') as stream:
        for line in stream:
            fields = line.decode('ascii').rstrip('\n').split('\t')
            need(len(fields) == 3, 'malformed raw score row.')
            accession, term, _ = fields
            if accession not in wanted:
                continue
            index = counts[accession]
            need(index < len(terms) and term == terms[index], 'duplicate/missing/reordered native head.')
            destination.write(line); counts[accession] += 1


def predict(frozen, expected, output):
    import torch
    policy, parent, model, old_forecasts = load(frozen, expected)
    cfg = policy['inputs']; cached = set(policy['cached_target_ids']); new = policy['new_target_ids']
    author, heads = author_and_heads(parent['inputs'], model)
    out = new_output(output, frozen)
    need(shutil.disk_usage(out).free >= 8*1024**3, '8GiB task disk required.')
    fasta = out/'new_targets.fasta'; shutil.copyfile(policy['new_fasta']['file'], fasta)
    feature = out/'new_targets_esm.pkl'
    _, data = extract_features(author, {'file':str(fasta), 'sha256':policy['new_fasta']['sha256']},
        parent['inputs']['esm_model'], parent['inputs']['esm_regression'], feature,
        device='cuda:0', expected_ids=new)
    del data
    torch.cuda.empty_cache()
    feature_pin = {'file':str(feature), 'sha256':fingerprints(feature)['sha256']}
    command = [sys.executable, str(Path(parent['inputs']['author_root'])/'predict.py'),
        '--in-file', str(fasta), '--data-root', str(Path(parent['inputs']['modelview']['file']).parent),
        '--device', 'cuda:0']
    with (out/'native_cli.log').open('xb') as log:
        subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True)
    pinned(feature_pin)
    files, rows, checks = {}, {}, {}
    for aspect in AUTHOR_ASPECT_ORDER:
        terms, forms, checkpoints = aspect_specs(parent['inputs'], model, aspect)
        proteins, terms, scores = predict_aspect(author, feature_pin, terms, forms, checkpoints,
            aspect, device='cuda:0', expected_ids=new)
        presented = native_rows(proteins, terms, scores); count = 0
        with gzip.open(out/('new_targets_preds_'+aspect+'.tsv.gz'), 'rt') as stream:
            for line in stream:
                need(line == next(presented, None), 'new-cohort unchanged CLI presentation differs.')
                count += 1
        need(next(presented, None) is None, 'new-cohort CLI omits adapter rows.')
        checks[aspect] = {'all_337_new_protein_presentations_exact':True, 'rows':count}
        new_raw = out/('new_deepgose_'+aspect+'.tsv.gz')
        write_lines(new_raw, raw_rows(proteins, terms, scores))
        name = 'nonpk_deepgose_'+aspect+'.tsv.gz'; target = out/name; totals = Counter()
        with gzip.GzipFile(filename=str(target), mode='wb', mtime=0) as destination:
            copy_rows(new_raw, set(new), terms, destination, totals)
            for old_name, spec in old_forecasts['files'].items():
                if old_name.endswith('_'+aspect+'.tsv.gz'):
                    source = Path(cfg['parent_predictions']['file']).parent/old_name
                    need(fingerprints(source) == spec, 'old forecast differs before literal reuse.')
                    copy_rows(source, cached, terms, destination, totals)
                    need(fingerprints(source) == spec, 'old forecast changed during literal reuse.')
        need(set(totals) == cached|set(new) and all(n == len(terms) for n in totals.values()),
             'full547 target/head frame must be preserved.')
        files[name] = fingerprints(target); rows[name] = sum(totals.values())
        write_json(out/'progress.json', {'aspect_completed':aspect, 'rows':rows,
            'native_CLI_checks':checks, 'reference_annotation_rows_read':False})
    load(frozen, expected); pinned(feature_pin)
    result = sealed({'format':FORMAT+'.predictions', 'created_at':utcnow(),
        'protocol_file_sha256':expected, 'protocol_content_sha256':policy['content_sha256'],
        'parent_protocol_sha256':cfg['parent_protocol_sha256'],
        'parent_predictions_sha256':cfg['parent_predictions']['sha256'],
        'target_count':547, 'new_native_inference_targets':337, 'literal_cached_forecast_targets':210,
        'all_three_new_CLI_presentations_exact':True, 'native_CLI_checks':checks,
        'heads':heads, 'feature_cache':feature_pin, 'files':files, 'raw_rows':rows,
        'all_reference_denominators_retained':True, 'reference_annotation_rows_read':False,
        'references_previously_exposed':True, 'model_or_threshold_fit':False,
        'original_PK_protocol_or_forecasts_changed':False, 'runtime':parent['runtime']})
    write_json(out/'predictions.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    q = sub.add_parser('prepare')
    for key in ('config', 'output'): q.add_argument('--'+key, required=True)
    q = sub.add_parser('predict')
    for key in ('frozen', 'expected', 'output'): q.add_argument('--'+key, required=True)
    args = vars(p.parse_args()); result = globals()[args.pop('command')](**args)
    print(json.dumps({'format':result['format'], 'status':result.get('status','complete'),
                      'content_sha256':result['content_sha256']}))
