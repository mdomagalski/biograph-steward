"""Prepare unchanged native CAFA jobs after the fixed raw forecasts are sealed.

The forecast runtime is the published DeepGO profile; the evaluator deliberately
remains the single earlier NumPy1.26.4 CAFA runtime. No metric/label parser is
implemented here. Existing consumed labels and known masks are reused only.
"""
import argparse
import json
from pathlib import Path
import shutil

from biograph_steward.client import digest, write_json, utcnow
from biograph_steward.file_utils import new_output
from .archive import fingerprints, need, sealed
from .run import FORMAT, PARAMETERS, read_seal
from .scores import AUTHOR_ASPECT_ORDER


def merge_aspects(predictions, manifest, frame, output):
    """Concatenate exact gzip members, without decoding or changing any scores."""
    predictions, output = Path(predictions), Path(output)
    need(frame in ('primary', 'reserved') and not output.exists(), 'fixed frame/fresh combined forecast required.')
    specs = []
    for aspect in AUTHOR_ASPECT_ORDER:
        relative = f'{frame}_deepgose_{aspect}.tsv.gz'
        path = predictions / relative
        need(relative in manifest['files'] and fingerprints(path) == manifest['files'][relative],
             'sealed aspect forecast differs.')
        specs.append(path)
    with output.open('xb') as destination:
        for path in specs:
            with path.open('rb') as source:
                shutil.copyfileobj(source, destination, 8 * 1024 * 1024)
    return fingerprints(output)


def prepare(base, frozen, expected, predictions, predictions_sha256, output):
    base, frozen, predictions = map(Path, (base, frozen, predictions))
    protocol_file = frozen / 'protocol.json'
    need(fingerprints(protocol_file)['sha256'] == expected, 'prediction protocol differs.')
    protocol = read_seal(protocol_file, FORMAT + '.freeze')
    need(protocol['parameters'] == PARAMETERS and protocol['target_counts'] == {'primary':1294, 'reserved':4806}
         and protocol['all_six_cohort_aspect_outcomes_required'] is True, 'fixed comparison scope differs.')
    manifest_file = predictions / 'predictions.json'
    need(fingerprints(manifest_file)['sha256'] == predictions_sha256, 'prediction manifest FILE differs.')
    manifest = read_seal(manifest_file, FORMAT + '.predictions')
    need(manifest['protocol_file_sha256'] == expected
         and manifest['protocol_content_sha256'] == protocol['content_sha256']
         and manifest['all_evaluation_denominators_retained'] is True
         and manifest['development_exposed_reference_reuse'] is True
         and manifest['new_reference_labels_read'] is False,
         'complete fixed-development forecast seal required before evaluation.')
    driver = base / 'adapters/remote_author.py'
    driver_sha256 = fingerprints(driver)['sha256']
    out = new_output(output, base, frozen, predictions)
    jobs = {}
    for frame, parent_name in (('primary','primary_BPO_point_jobs_v2.json'),
                               ('reserved','reserved_BPO_point_jobs_v1.json')):
        parent = base / parent_name
        config = json.loads(parent.read_text())
        need(config['format'] == 'biograph-steward.cafa5-remote-author-jobs.v1',
             'unchanged author execution adapter required.')
        forecast = out / (frame + '_deepgose.tsv.gz')
        combined = merge_aspects(predictions, manifest, frame, forecast)
        # Despite the old BPO-only filenames, the existing runners are the
        # native all-namespace functions. Use the exact already released full
        # partial-reference and known mask, not any newly filtered endpoint.
        release = base / (frame + '-reference-v1')
        truth, known = release / 'partial.tsv', release / 'known_t0_frame.tsv'
        pins = dict(config['input_files_sha256'])
        paths = (parent, truth, known, release/'report.json', protocol_file, manifest_file,
                 forecast, driver, Path(__file__).resolve())
        pins.update({str(path):fingerprints(path)['sha256'] for path in paths})
        for aspect in AUTHOR_ASPECT_ORDER:
            relative = f'{frame}_deepgose_{aspect}.tsv.gz'
            pins[str(predictions/relative)] = manifest['files'][relative]['sha256']
        config.update(parent_evaluation_config_sha256=fingerprints(parent)['sha256'],
            producer_protocol_file_sha256=expected,
            references={'partial':{'truth':str(truth),'known':str(known)}},
            methods={'deepgose':{'file':str(forecast),'sha256':combined['sha256']}},
            threads=2, contributions=True, temporary_directory='/dev/shm', input_files_sha256=pins,
            additional_scope={'development_exposed_labels':True,'new_reference_release':False,
                'all_six_cohort_aspect_outcomes_required':True,'all_existing_controls_and_negatives_preserved':True,
                'prediction_runtime':'PublishedDeepGOversions with explicitCPU-DGL import adaptation',
                'evaluation_runtime':'EarlierunchangedCAFA NumPy1.26.4/SciPy1.13.1/Pandas2.2.3',
                'native_MLP_control':'Unavailableinsuppliedinferencearchives; no causalaxiom-onlyclaim',
                'raw_score_export':'Beforedefaultnative0.1cut/three-decimalpresentation'})
        config_file = out / (frame+'_native_jobs.json')
        write_json(config_file, config)
        jobs[frame] = {'config':str(config_file),'config_sha256':fingerprints(config_file)['sha256'],
            'output':str(out/(frame+'_native_v1')),'joined_forecast':combined}
    result = sealed({'format':FORMAT+'.native-jobs', 'created_at':utcnow(),
        'producer_protocol_file_sha256':expected,'prediction_manifest_file_sha256':predictions_sha256,
        'evaluation_plan_file_sha256':protocol['inputs']['evaluation_plan']['sha256'],
        'jobs':jobs, 'native_driver':str(driver), 'native_driver_sha256':driver_sha256,
        'new_scoring_formula':False, 'previous_released_truth_reused':True,
        'all_six_cohort_aspect_outcomes_required':True})
    write_json(out/'jobs.json',result)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('base','frozen','expected','predictions','predictions-sha256','output'):
        parser.add_argument('--'+key,required=True)
    value=prepare(**vars(parser.parse_args()))
    print(json.dumps({'format':value['format'],'content_sha256':value['content_sha256']}))
