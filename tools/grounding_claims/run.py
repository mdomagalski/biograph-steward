"""Run fixed native Gilda context arms without opening curator labels."""
from collections import Counter
import argparse
import gzip
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import time

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .context import load_context
from .native import check_grounding
from .prepare import FORMAT as FRAME_FORMAT, need, ordinary

FORMAT = 'biograph-steward.grounding-claim-predictions.v1'
ARMS = ('lexical', 'sentence', 'publication')
NATIVE_VERSIONS = {'gilda': '1.6.1', 'indra': '1.24.0', 'adeft': '0.13.0',
                   'scikit-learn': '1.9.1', 'numpy': '2.3.5'}


def sealed(path):
    path = ordinary(path)
    value = json.loads(path.read_text())
    need(value.get('content_sha256') == digest({k: v for k, v in value.items() if k != 'content_sha256'}),
         'content seal differs: ' + path.name)
    return value


def load_frame(folder):
    folder = Path(folder).absolute()
    report = sealed(folder / 'report.json')
    need(report.get('format') == FRAME_FORMAT and report['label_categories_inspected'] is False
         and report['predictions_run'] is False,
         'use the outcome-free prepared frame.')
    for name, pin in report['files'].items():
        need(Path(name).name == name and sha(ordinary(folder / name)) == pin, 'frame file changed.')
    with gzip.open(folder / 'cases.jsonl.gz', 'rt', encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream]
    need(len(rows) == report['primary_cases'] and len({r['case_id'] for r in rows}) == len(rows),
         'frame case inventory differs.')
    return report, rows


def unavailable_publication(case):
    return {'format': 'biograph-steward.native-grounding-check.v1',
        'input_sha256': case['input']['input_sha256'], 'use_context': True,
        'context_kind': 'unavailable_publication_context', 'context_sha256': None,
        'context_characters': 0, 'status': 'unresolved', 'candidate_conflict': None,
        'reasons': ['exact_publication_title_and_abstract_unavailable'], 'agents': [],
        'model_error_agents': 0, 'native_model_available_agents': 0,
        'native_model_availability_unknown_agents': 0, 'disambiguation_applied_agents': 0}


def run(frame, contexts, resources, plan_path, output, *, split):
    """Predict a fixed source partition. No label path is accepted by this API."""
    need(split in {'development', 'test'}, 'choose development or test explicitly.')
    plan = sealed(plan_path)
    need(plan['format'] == 'biograph-steward.grounding-claim-evaluation-freeze.v1'
         and plan['curation_categories_or_predictions_inspected_before_freeze'] is False
         and plan['arms'] == list(ARMS), 'use the declared pre-outcome evaluation freeze.')
    frame, contexts, resources = Path(frame).absolute(), Path(contexts).absolute(), ordinary(resources)
    need(sha(frame / 'report.json') == plan['frame_report_sha256']
         and sha(contexts / 'manifest.json') == plan['contexts_manifest_sha256']
         and sha(resources) == plan['resource_receipt_sha256'], 'frozen input pin differs.')
    for path, pin in plan['implementation_pins'].items():
        need(sha(ordinary(path)) == pin, 'frozen implementation differs: ' + path)
    frame_report, all_cases = load_frame(frame)
    cases = [row for row in all_cases if row['split'] == split]
    context_by_pmid = load_context(contexts)
    receipt = json.loads(resources.read_text())
    native_resources = {}
    for row in receipt['resources']:
        path = ordinary(row['local_file'])
        need(path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], 'native model resource differs.')
        native_resources[path.name] = path
    need(set(native_resources) == {'grounding_terms.tsv.gz', 'gilda_models.json.gz'}, 'use both pinned native resources.')
    terms = native_resources['grounding_terms.tsv.gz']
    need(terms.parent == native_resources['gilda_models.json.gz'].parent and terms.parent.name == '1.6.1',
         'resource version/path differs.')
    adeft = receipt.get('adeft')
    need(isinstance(adeft, dict) and adeft['version'] == '0.13.0'
         and receipt.get('Adeft_models_included') is True, 'use the complete frozen native disambiguation setup.')
    adeft_home = Path(adeft['cache_home']).absolute()
    expected_adeft = set()
    for row in adeft['files']:
        path = ordinary(row['local_file'])
        need(adeft_home in path.parents and path.stat().st_size == row['bytes']
             and sha(path) == row['sha256'], 'Adeft resource differs.')
        expected_adeft.add(path)
    model_root = adeft_home / '0.13.0' / 'models'
    need({p.absolute() for p in model_root.rglob('*') if p.is_file()} == expected_adeft
         and not any(p.is_symlink() for p in model_root.rglob('*')), 'unexpected Adeft model resource.')
    # Set documented cache controls before importing the optional libraries.
    cache_root = terms.parent.parent
    os.environ['GILDA_HOME'] = str(cache_root)
    os.environ['PYSTOW_HOME'] = str(cache_root.parent)
    os.environ['ADEFT_HOME'] = str(adeft_home)
    need(all(importlib.metadata.version(name) == version
             for name, version in NATIVE_VERSIONS.items()), 'native package versions differ.')
    from gilda.grounder import Grounder, load_gilda_models
    logging.getLogger('gilda').setLevel(logging.WARNING)
    grounder = Grounder(terms=terms)
    need(set(adeft['selected_shortforms']) <= set(grounder.adeft_disambiguators),
         'the fresh process did not discover all declared Adeft shortforms.')
    # This is the library's own lazy loader with its published default cutoff.
    # Preload it once so model availability is known in every arm, including
    # lexical requests; no benchmark prediction has yet occurred.
    grounder.gilda_disambiguators = load_gilda_models()
    out = new_output(output, frame, contexts, resources, plan_path)
    # Non-benchmark probes check both native classifier stacks. Terms are
    # selected from deployed models with native lexical entries, never by
    # benchmark correctness. No expected biological entity is asserted.
    need(grounder.gilda_disambiguators, 'the pinned context-model collection is empty.')
    probes = []
    for engine, keys in (
            ('adeft', set(grounder.adeft_disambiguators)),
            ('gilda', set(grounder.gilda_disambiguators) - set(grounder.adeft_disambiguators))):
        candidates = [key for key in sorted(keys) if grounder.lookup(key)]
        need(candidates, 'no lexically available classifier for native compatibility probe.')
        probe_term = 'PDK1' if 'PDK1' in candidates else candidates[0]
        probe_context = 'This publication discusses the entity ' + probe_term + '.'
        probe = grounder.ground(probe_term, context=probe_context)
        probe_json = [match.to_json() for match in probe]
        applied = any(row.get('disambiguation', {}).get('type') == engine for row in probe_json)
        probes.append({'engine': engine, 'mention': probe_term, 'context': probe_context,
            'native_model_available': True, 'disambiguation_applied': applied,
            'ranked_native_matches': probe_json, 'expected_grounding_or_gold_label': None})
        write_json(out / 'runtime_preflight.json', {'purpose':
            'Non-evaluation native classifier compatibility; not biological accuracy.', 'probes': probes})
        need(probe and applied, 'native classifier compatibility probe failed; no benchmark labels opened.')
    pins = {str(frame / 'report.json'): sha(frame / 'report.json'),
            str(contexts / 'manifest.json'): sha(contexts / 'manifest.json'),
            str(resources): sha(resources), str(Path(plan_path).absolute()): sha(plan_path)}
    status_counts = {arm: Counter() for arm in ARMS}
    error_types, model_coverage = Counter(), {arm: Counter() for arm in ARMS}
    start = time.monotonic()
    with gzip.open(out / 'predictions.jsonl.gz', 'wt', encoding='utf-8') as stream:
        for index, case in enumerate(cases):
            predictions = {}
            for arm in ARMS:
                if arm == 'publication':
                    context = context_by_pmid.get(case['pmid'])
                    if context is None or context['status'] != 'available':
                        result = unavailable_publication(case)
                    else:
                        result = check_grounding(case['input'], grounder, use_context=True,
                                                 context_text=context['context_text'])
                else:
                    result = check_grounding(case['input'], grounder, use_context=arm == 'sentence')
                predictions[arm] = result
                status_counts[arm][result['status']] += 1
                for key in ('native_model_available_agents', 'disambiguation_applied_agents', 'model_error_agents'):
                    model_coverage[arm][key] += result[key]
                for agent in result.get('agents', []):
                    if agent.get('error_type'):
                        error_types[agent['error_type']] += 1
            row = {'case_id': case['case_id'], 'pa_hash': case['pa_hash'], 'source_hash': case['source_hash'],
                   'group_id': case['group_id'], 'split': split, 'input_sha256': case['input']['input_sha256'],
                   'predictions': predictions}
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n')
            if (index + 1) % 100 == 0:
                print(json.dumps({'processed': index + 1, 'total': len(cases), 'split': split}), flush=True)
    need(all(sha(path) == pin for path, pin in pins.items()), 'input changed during prediction.')
    for path, pin in plan['implementation_pins'].items():
        need(sha(path) == pin, 'implementation changed during prediction.')
    result = {'format': FORMAT, 'created_at': utcnow(), 'split': split, 'cases': len(cases),
        'case_ids': [r['case_id'] for r in cases], 'group_ids': sorted({r['group_id'] for r in cases}),
        'arms': list(ARMS), 'status_counts': {a: dict(c) for a, c in status_counts.items()},
        'model_coverage': {a: dict(c) for a, c in model_coverage.items()}, 'error_types': dict(error_types),
        'elapsed_seconds': time.monotonic() - start, 'curation_labels_opened': False,
        'new_gold_labels_created': False, 'source_graph_or_review_changed': False,
        'automatic_identifier_replacements_or_prunes': 0,
        'context_mode': 'Native default human-prior Gilda; fixed lexical, source sentence, exact current PubMed title+abstract; no fulltext fallback.',
        'gene_level_not_protein_form_validation': True,
        'grounder_training_publication_independence_established': False,
        'native_Gilda_disambiguation_models_loaded': len(grounder.gilda_disambiguators),
        'native_Adeft_models_loaded': len(grounder.adeft_disambiguators),
        'native_package_versions': dict(NATIVE_VERSIONS),
        'input_files_sha256': pins, 'frame_content_sha256': frame_report['content_sha256'],
        'evaluation_freeze_content_sha256': plan['content_sha256'],
        'files': {name: sha(out / name) for name in ('predictions.jsonl.gz', 'runtime_preflight.json')}}
    result['content_sha256'] = digest(result)
    write_json(out / 'report.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('frame', 'contexts', 'resources', 'plan', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--split', required=True, choices=('development', 'test'))
    args = parser.parse_args()
    print(run(args.frame, args.contexts, args.resources, args.plan, args.out, split=args.split)['content_sha256'])


if __name__ == '__main__':
    main()
