"""Score saved, fixed grounding proposals against selected expert curations."""
from collections import Counter
import argparse
import gzip
import json
from pathlib import Path

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .prepare import need, ordinary
from .run import ARMS, load_frame, sealed
from .score import GOLD_LABELS, label_pairs, compare_methods

FORMAT = 'biograph-steward.expert-grounding-component-evaluation.v1'
BOUNDARY = ('Expert-curator-relative human-gene grounding-error triage in a published '
    'stratified mechanistic extraction corpus. Not whole-Pharos precision, protein-form '
    'validation, independent experimental biology or a biological prediction gain. '
    'The grounder merges gene/protein names; its training-paper overlap is unestablished. '
    'A candidate conflict is a review proposal, not a validated replacement or prune.')


def evaluate(frame, predictions, curations, plan_path, output):
    frame, predictions = Path(frame).absolute(), Path(predictions).absolute()
    curations = ordinary(curations)
    plan, pred = sealed(plan_path), sealed(predictions / 'report.json')
    need(plan['format'] == 'biograph-steward.grounding-claim-evaluation-freeze.v1'
         and sha(curations) == plan['raw_curations_sha256'], 'reference or evaluation freeze differs.')
    for path, pin in plan['implementation_pins'].items():
        need(sha(ordinary(path)) == pin, 'evaluation implementation differs from its pre-outcome pin.')
    need(pred['format'] == 'biograph-steward.grounding-claim-predictions.v1'
         and pred['evaluation_freeze_content_sha256'] == plan['content_sha256']
         and pred['curation_labels_opened'] is False and pred['arms'] == list(ARMS),
         'predictions were not produced by this outcome-free contract.')
    need(sha(frame / 'report.json') == plan['frame_report_sha256'], 'frame differs from the freeze.')
    frame_report, all_cases = load_frame(frame)
    cases = [r for r in all_cases if r['split'] == pred['split']]
    need(pred['cases'] == len(cases) and pred['case_ids'] == [r['case_id'] for r in cases],
         'saved prediction partition differs from the fixed frame.')
    for name, pin in pred['files'].items():
        need(Path(name).name == name and sha(ordinary(predictions / name)) == pin,
             'saved native prediction bytes differ.')
    captured = {}
    with gzip.open(predictions / 'predictions.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            need(row['case_id'] not in captured, 'duplicate prediction case.')
            captured[row['case_id']] = row
    need(set(captured) == {r['case_id'] for r in cases}, 'saved prediction case inventory differs.')
    for case in cases:
        row = captured[case['case_id']]
        need(all(row[k] == case[k] for k in ('pa_hash', 'source_hash', 'group_id', 'split'))
             and row['input_sha256'] == case['input']['input_sha256']
             and set(row['predictions']) == set(ARMS), 'native prediction identity/input differs.')
        for arm in ARMS:
            need(row['predictions'][arm]['input_sha256'] == case['input']['input_sha256'],
                 'an arm uses another source input.')
    # This is the first function in the pipeline that accesses selected tag
    # values. label_pairs checks the source identity before touching a tag.
    labels = label_pairs(json.loads(curations.read_text()),
                         [(r['pa_hash'], r['source_hash']) for r in cases])
    admitted = [r for r in cases if labels[(r['pa_hash'], r['source_hash'])]['label'] in GOLD_LABELS]
    by_arm = {arm: {r['case_id']: captured[r['case_id']]['predictions'][arm]
                   for r in admitted} for arm in ARMS}
    comparison = compare_methods(admitted, by_arm, labels)
    label_counts = Counter(value['label'] for value in labels.values())
    native_tags = Counter()
    for value in labels.values():
        for item in value['native_tag_counts']:
            native_tags[str(item['tag'])] += item['count']
    out = new_output(output, frame, predictions, curations, plan_path)
    write_json(out / 'comparison.json', comparison)
    with (out / 'label_admission.jsonl').open('w') as stream:
        for case in cases:
            row = {key: case[key] for key in ('case_id', 'pa_hash', 'source_hash', 'group_id', 'split')}
            row.update(labels[(case['pa_hash'], case['source_hash'])])
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    result = {'format': FORMAT, 'created_at': utcnow(), 'split': pred['split'],
        'scope': BOUNDARY, 'reference': {'DOI': '10.15252/msb.202211325', 'Zenodo': 7559353,
            'data_license': 'CC-BY-NC-SA-4.0', 'expert_labels_assigned_by_project_AI': False},
        'primary_frame_cases': len(cases), 'admitted_endpoint_cases': len(admitted),
        'outside_endpoint_cases': len(cases) - len(admitted), 'label_counts': dict(label_counts),
        'selected_native_curation_tag_counts': dict(native_tags),
        'curation_rows_in_selected_partition': sum(v['curation_row_count'] for v in labels.values()),
        'grounding_error_policy': "Only unanimous native 'grounding'; no other error type or qualification is relabeled.",
        'correct_policy': "Only unanimous native 'correct'; duplicate curations are not independent votes.",
        'comparison': comparison, 'prediction_runtime_status_counts': pred['status_counts'],
        'model_coverage_all_primary_cases': pred['model_coverage'],
        'source_sampling': 'Reader/mention-count-stratified original sample; results describe admitted released cases, not population accuracy.',
        'heldout_grouping': frame_report['split_policy'], 'known_exposure_audit_not_exhaustive': True,
        'native_grounder_training_paper_independence_established': False,
        'automatic_corrections_or_prunes_performed': False, 'new_gold_labels_created': False,
        'underlying_biological_truth_measured': False, 'whole_graph_accuracy_estimated': False,
        'source_graph_or_original_reference_changed': False,
        'input_files_sha256': {'frame_report': sha(frame / 'report.json'),
            'predictions_report': sha(predictions / 'report.json'), 'raw_curations': sha(curations),
            'evaluation_plan': sha(plan_path)},
        'evaluation_freeze_content_sha256': plan['content_sha256'],
        'implementation_sha256': sha(__file__), 'scoring_helper_sha256': sha(Path(__file__).with_name('score.py')),
        'files': {p.name: sha(p) for p in out.iterdir() if p.is_file()}}
    result['content_sha256'] = digest(result)
    need(sha(curations) == plan['raw_curations_sha256']
         and all(sha(ordinary(path)) == pin for path, pin in plan['implementation_pins'].items()),
         'reference or implementation changed during evaluation.')
    write_json(out / 'report.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('frame', 'predictions', 'curations', 'plan', 'out'):
        p.add_argument('--' + name, required=True, type=Path)
    a = p.parse_args()
    print(evaluate(a.frame, a.predictions, a.curations, a.plan, a.out)['content_sha256'])


if __name__ == '__main__':
    main()
