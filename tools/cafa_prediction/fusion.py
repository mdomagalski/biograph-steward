"""Fixed pretest score fusion; not execution or reproduction of DeepGOPlus.

Convex score-level combination follows an established function-prediction
strategy. The component methods here differ, and the equal weights are a fixed
project choice, not the current DeepGOPlus namespace-specific fitted weights.
"""
import argparse
import gzip
import json
import math
from pathlib import Path
import re
import sqlite3
import tempfile

from .core import need, sha
from .run import digest, load_frozen, new_output, pin, read, timestamp, verify_pins, write
from biograph_steward.client import digest as native_digest

FORMAT = 'biograph-steward.cafa5-fixed-score-fusion.v1'
FUSIONS = {
    'blast_fss_half': ('blast', 'fastsinksourceplus'),
    'blast_local_half': ('blast', 'localplus'),
    'prott5_cosine1_fss_half': ('prott5_cosine1', 'fastsinksourceplus'),
    'prott5_cosine1_local_half': ('prott5_cosine1', 'localplus'),
}


def verify_baselines(config):
    qualification = read(config['baseline_qualification'])
    need(qualification.get('format') == 'biograph-steward.official-cafa5-baseline-intake.v1'
         and qualification.get('status') == 'completed'
         and qualification.get('future_GO_labels_opened') is False
         and qualification.get('score_rescaling') is False
         and qualification.get('target_file_sha256') == sha(config['targets'])
         and qualification.get('content_sha256') == native_digest({k:v for k,v in qualification.items() if k != 'content_sha256'}),
         'official baseline qualification or target frame differs.')
    for role, name in (('blast','official_blast.tsv.gz'), ('prott5_cosine1','official_prott5_cosine1.tsv.gz')):
        need(qualification['files'].get(name,{}).get('sha256') == sha(config[role]),
             'component bytes differ from the qualified official baseline: ' + role)
    return qualification


def load_scores(db, path, targets, column, canonical=None):
    """Keep max for literal duplicates, like the official evaluator's reader."""
    need(column in {'blast', 'prott5_cosine1', 'fastsinksourceplus', 'localplus'}, 'unreviewed score column.')
    rows, skipped, outside, aliases, roundoff, maximum, batch = 0, 0, 0, 0, 0, 0., []
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt') as stream:
        for line in stream:
            fields = line.strip().split()
            if not fields:
                continue
            need(len(fields) == 3, 'score rows require exactly accession, GO ID and score.')
            protein, term, text = fields
            need(protein in targets, 'score target is outside the fixed identity frame.')
            need(re.fullmatch(r'GO:[0-9]{7}', term), 'score term is not an exact GO identifier.')
            score = float(text)
            need(math.isfinite(score) and 0 <= score <= 1 + 1e-10,
                 'component score range must already be qualified to [0,1]; no implicit rescaling.')
            rows += 1; roundoff += score > 1; maximum = max(maximum, score)
            if score == 0:
                skipped += 1
                continue
            identities = [term] if canonical is None else canonical.get(term, [])
            if not identities:
                outside += 1
                continue
            aliases += identities != [term]
            batch.extend((protein, identity, score) for identity in identities)
            if len(batch) >= 20000:
                db.executemany('INSERT INTO scores(protein,term,' + column + ') VALUES (?,?,?) '
                    'ON CONFLICT(protein,term) DO UPDATE SET ' + column + '=MAX(' + column + ',excluded.' + column + ')', batch)
                db.commit(); batch = []
        db.executemany('INSERT INTO scores(protein,term,' + column + ') VALUES (?,?,?) '
            'ON CONFLICT(protein,term) DO UPDATE SET ' + column + '=MAX(' + column + ',excluded.' + column + ')', batch)
        db.commit()
    return {'source_rows': rows, 'exact_zero_rows_omitted': skipped,
            'outside_frozen_ontology_rows_ignored': outside, 'explicit_alternative_ID_rows_resolved': aliases,
            'scores_in_upper_float64_roundoff_band': roundoff, 'maximum_source_score': maximum,
            'literal_duplicate_policy': 'maximum component score, matching official CAFA reader',
            'score_normalization': 'none; source-qualified [0,1] scores with unchanged 1e-10 upper roundoff tolerance matching the primary numerical guard'}


def combine(config_path, output):
    config_path = Path(config_path).resolve(); config = read(config_path)
    need(set(config) == {'prediction_manifest', 'prediction_freeze', 'targets', 'blast', 'prott5_cosine1', 'baseline_qualification', 'canonical_alias_map'},
         'exact fixed-fusion configuration required.')
    manifest = read(config['prediction_manifest'])
    need(manifest.get('format') == 'biograph-steward.cafa5-historical-predictions.v1'
         and manifest.get('future_GO_labels_read') is False
         and manifest['content_sha256'] == digest({k: v for k, v in manifest.items() if k != 'content_sha256'}),
         'sealed historical predictions required.')
    base = Path(config['prediction_manifest']).resolve().parent
    parent_protocol = load_frozen(config['prediction_freeze'], manifest['protocol_file_sha256'])
    need(parent_protocol['content_sha256'] == manifest['protocol_content_sha256'],
         'prediction source protocol differs.')
    for name, data in manifest['files'].items():
        need(sha(base / name) == data['sha256'], 'frozen prediction component changed.')
    targets = Path(config['targets']).read_text().splitlines()
    need(targets and targets == sorted(set(targets)) and len(targets) == manifest['target_IDs'],
         'fixed target identities differ.')
    need(sha(config['targets']) == parent_protocol['files']['targets.txt'],
         'fusion target frame differs from prediction frame.')
    verify_baselines(config)
    mapping = read(config['canonical_alias_map'])
    need(set(mapping) == {'primary', 'alternative', 'namespace'}, 'official canonical map fields differ.')
    canonical = {**mapping['primary'], **mapping['alternative']}
    need(all(isinstance(v, list) and v and all(p in mapping['primary'] for p in v) for v in canonical.values()),
         'canonical mapping does not use explicit frozen primary GO identities.')
    sources = {'blast': Path(config['blast']), 'prott5_cosine1': Path(config['prott5_cosine1']),
               'fastsinksourceplus': base / 'fastsinksourceplus.tsv.gz', 'localplus': base / 'localplus.tsv.gz'}
    pins = {k: pin(p) for k, p in sources.items()}
    pins.update({k: pin(config[k]) for k in ('prediction_manifest', 'targets', 'baseline_qualification', 'canonical_alias_map')})
    pins['fusion_adapter'] = pin(__file__); pins['configuration'] = pin(config_path)
    folder = new_output(output)
    protocol = {'format': FORMAT, 'created_at': timestamp(), 'input_pins': pins,
        'parent_prediction_content_sha256': manifest['content_sha256'],
        'arms': {name: {'components': [a, b], 'weights': [.5, .5]} for name, (a, b) in FUSIONS.items()},
        'missing_score': 'zero prediction score for arithmetic only; never a biological-negative label',
        'score_postprocessing': 'none; no clipping, fitted calibration, alpha sweep or performance-selected term filter',
        'upper_roundoff_tolerance': '1e-10, same as native run_term; raw scores retained. Native LocalPlus row sums can exceed 1 by about 1e-15. The author threshold grid ends at .999.',
        'GO_identity': 'Explicit primary/alternative identities from unchanged official CAFA OBO parser before arithmetic; max component score for resolved duplicates. Ontology propagation remains in the official evaluator.',
        'primary_candidate_changed': False, 'status': 'fixed_secondary_pretest_extension',
        'future_GO_labels_read': False,
        'established_form': 'https://github.com/bio-ontology-research-group/deepgoplus/blob/master/predict.py',
        'interpretation': 'Fixed score-level fusion adaptation using graph propagation and official sequence-transfer scores. Not a DeepGOPlus reproduction; its current code uses namespace-specific weights rather than its unused CLI alpha default.'}
    protocol['content_sha256'] = digest(protocol)
    write(folder / 'fusion_protocol.json', protocol)
    with tempfile.TemporaryDirectory(prefix='biograph-cafa-fusion-') as temporary:
        db = sqlite3.connect(str(Path(temporary) / 'scores.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA cache_size=-131072')
            db.execute('CREATE TABLE scores(protein TEXT,term TEXT,blast REAL DEFAULT 0,prott5_cosine1 REAL DEFAULT 0,fastsinksourceplus REAL DEFAULT 0,localplus REAL DEFAULT 0,PRIMARY KEY(protein,term)) WITHOUT ROWID')
            diagnostics = {}
            for column, path in sources.items():
                diagnostics[column] = load_scores(db, path, set(targets), column, canonical)
                print(json.dumps({'component': column, **diagnostics[column]}), flush=True)
            emitted = {}
            for name, (a, b) in FUSIONS.items():
                count = 0
                with gzip.GzipFile(filename=str(folder / (name + '.tsv.gz')), mode='wb', mtime=0) as stream:
                    for protein, term, value in db.execute('SELECT protein,term,.5*' + a + '+.5*' + b + ' FROM scores WHERE ' + a + '>0 OR ' + b + '>0 ORDER BY protein,term'):
                        need(math.isfinite(value) and 0 < value <= 1 + 1e-10, 'fixed convex mixture produced an invalid score.')
                        stream.write((protein + '\t' + term + '\t' + format(value, '.17g') + '\n').encode()); count += 1
                emitted[name] = count
        finally:
            db.close()
    verify_pins(pins)
    result = {'format': FORMAT + '.results', 'created_at': timestamp(),
        'protocol_content_sha256': protocol['content_sha256'],
        'protocol_file_sha256': sha(folder / 'fusion_protocol.json'),
        'parent_prediction_content_sha256': manifest['content_sha256'],
        'files': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(folder.iterdir())},
        'component_intake': diagnostics, 'emitted_rows': emitted,
        'future_GO_labels_read': False, 'primary_candidate_changed': False}
    result['content_sha256'] = digest(result); write(folder / 'fusion_predictions.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); result = combine(args.config, args.output)
    print(json.dumps({k: result[k] for k in ('format', 'content_sha256')}, indent=2))


if __name__ == '__main__': main()
