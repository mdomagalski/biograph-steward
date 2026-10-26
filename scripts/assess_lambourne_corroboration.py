#!/usr/bin/env python3
"""Freeze, execute and replay one descriptive Pharos/assay corroboration report.

Freezing authenticates outcome files as opaque bytes. Only execution (or an
explicit replay of an already consumed result) invokes the assay adapter.
No training, inferred negatives, ranking, threshold sweep or significance test.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from html import escape
from pathlib import Path
import platform
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_lambourne_pharos_lookup as lookup_audit
from audit_lambourne_reference import COMMIT, PANEL, ORF_MAP, verified_author_files
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.gold_packet import _decode

FORMAT = 'biograph-steward.lambourne-corroboration-freeze.v1'
RESULT_FORMAT = 'biograph-steward.lambourne-corroboration-result.v1'
IDENTITY_SHA = 'f4bd5e51a28935e9cf5d673f7c0e17c5b0492760eba2e8d15f2d07c938148cbd'
LOOKUP_SHA = '5b7a3b46abdc719885a979559f2a38f043deb6b5c118bc571d06dcf812d22519'
RAW_SHA = '51433c18341467df559096eba1bad6a98e7fe4976166a498d2881270586d7db2'
AUTHOR_CODE_SHA = 'bc6fb2cb3e3ff635033a13692fe0d4a78cc8318fade3a3c881f6f0f5f7b3e616'
SOURCE_HASHES = {
    'source/panel.tsv': '477add8e6cfadc726a609b60cbc1089269741b0a00b75751cd37358fa40b28f2',
    'source/orf_map.tsv': 'b03bc31f4c0880697fd7a2d1bfe7a34889773e9317858986825910ffa77849d5',
    'source/raw_human.tsv': RAW_SHA, 'source/author_preprocessing.py': AUTHOR_CODE_SHA,
    'identity/report.json': IDENTITY_SHA, 'lookup/report.json': LOOKUP_SHA,
}
STATES = ('present_in_raw_ppi', 'no_match_both_endpoints_resolved', 'no_match_one_endpoint_resolved')
EXPECTED = dict(zip(STATES, (2325, 895, 2)))
ASSAY_STATES = ('detected', 'not_detected', 'test_failed', 'autoactivator',
                'failed_sequence_confirmation', 'ambiguous_sequence_confirmation',
                'inconsistent', 'unexpected_state')
FLAGS = ('huri_registry_projected_match', 'huri_author_crosswalk_match',
         'inmc_registry_projected_match', 'inmc_author_crosswalk_match')
CODE = ('scripts/assess_lambourne_corroboration.py', 'biograph_steward/lambourne_outcomes.py',
        'scripts/audit_lambourne_pharos_lookup.py', 'scripts/audit_lambourne_reference.py',
        'scripts/audit_pharos_inventory.py', 'scripts/retrieve_pharos_inventory.py',
        'biograph_steward/client.py', 'biograph_steward/retrieval.py',
        'biograph_steward/gold_packet.py', 'biograph_steward/file_utils.py')


def ordinary(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('Use ordinary files without symlink traversal: ' + str(path))
    return path.read_bytes()


def read(path):
    return _decode(ordinary(path))


def seal(value):
    value['content_sha256'] = digest({k: v for k, v in value.items() if k != 'content_sha256'})
    return value


def require_seal(value):
    if not isinstance(value, dict) or value.get('content_sha256') != digest({k: v for k, v in value.items() if k != 'content_sha256'}):
        raise ValueError('Content receipt does not match.')


def file_inventory(folder, exclude):
    folder = Path(folder)
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*'))
            if p.is_file() and p.relative_to(folder).as_posix() != exclude}


def capture_bundle(folder, receipt_name):
    folder = Path(folder)
    if any(p.is_symlink() for p in (folder, *folder.parents)) or not folder.is_dir():
        raise ValueError('Use an ordinary artifact directory.')
    if any(p.is_symlink() for p in folder.rglob('*')):
        raise ValueError('Artifact contains a symlink.')
    receipt = read(folder / receipt_name)
    require_seal(receipt)
    if receipt.get('files') != file_inventory(folder, receipt_name):
        raise ValueError('Artifact file inventory changed.')
    captured = {name: ordinary(folder / name) for name in receipt['files']}
    if any(hashlib.sha256(raw).hexdigest() != receipt['files'][name] for name, raw in captured.items()):
        raise ValueError('Artifact changed during capture.')
    return receipt, captured


def make_comparator(rows):
    result, seen = [], set()
    for row in rows:
        products = row['products']
        key = tuple(products)
        identity = row['identity']
        state = row['pharos_status']
        if (len(key) != 2 or key != tuple(sorted(key)) or key[0] == key[1] or key in seen
                or state not in STATES or sorted((identity['uniprot_a'], identity['uniprot_b'])) != products
                or row['source_row'] != identity['source_row']):
            raise ValueError('Invalid or duplicate comparator identity/state.')
        seen.add(key)
        present = bool(row['pharos_matches']['raw'])
        if present != (state == STATES[0]) or row['resolved_endpoint_count'] != (1 if state == STATES[2] else 2):
            raise ValueError('Comparator state disagrees with presence or identity coverage.')
        if any(type(row[f]) is not bool for f in FLAGS):
            raise ValueError('Exposure flags must be explicit booleans.')
        bundles = sorted({r['record']['type'] for r in row['pharos_matches']['raw']})
        if present and (not bundles or any(not isinstance(s, str) or not s for s in bundles)):
            raise ValueError('Represented pair lacks an explicit provider bundle.')
        result.append({'products': products, 'source_row': row['source_row'],
            'identity': identity, 'pharos_status': state,
            'resolved_endpoint_count': row['resolved_endpoint_count'],
            'comparator': None if state == STATES[2] else int(present),
            'provider_bundles': bundles, 'previous_pharos_status': row['previous_pharos_status'],
            **{f: row[f] for f in FLAGS},
            'huri_overlap': row[FLAGS[0]] or row[FLAGS[1]],
            'inmc_overlap': row[FLAGS[2]] or row[FLAGS[3]],
            'lookup_record_sha256': digest(row)})
    return sorted(result, key=lambda r: r['products'])


def specification():
    return {'assessment': 'retrospective_assay_corroboration', 'assay': 'human Y2H-v1',
        'population': 'All published Zhang_et_al nominations in the pinned author supplement; controls excluded.',
        'unit': 'unordered author UniProt pair with exact experimental AD/DB constructs',
        'assay_eligibility': 'Author Positive/Negative plus explicit true confirmation for the appropriate condition; unknown confirmation excluded, not relabeled.',
        'consistency_gate': 'Every nominated raw-derived author status and construct must reconcile to the published supplement or no metrics are emitted.',
        'comparator': '1=represented; 0=bounded no-match with both endpoints resolved; null=unresolved. Zero is not a biological negative.',
        'report': 'Full-panel lookup-by-assay cross-tab, detection/(detection+nondetection) with counts, and comparator-evaluable coverage.',
        'strata': ['exact provider bundle membership (may overlap)', 'HuRI/INMC union flag combinations', *FLAGS],
        'zero_denominator': None, 'uncertainty': 'Descriptive finite selected panel; no IID confidence intervals or significance tests.',
        'ranking_metrics': [], 'learned_model': None, 'study_independence_established': False,
        'steward_improvement_tested': False,
        'prior_exposure': 'Public paper methods and aggregate findings have been read; individual assay outcomes were not decoded before this freeze. This is not a prospectively hidden study.',
        'limitations': ['Selected nomination panel, not a random proteome sample.',
            'Unknown imported Pharos study lineage; provider bundles do not establish independent experiments.',
            'Y2H nondetection does not invalidate functional, co-complex or differently contextualized Pharos relations.',
            'Human figure caption differs from Methods/filenames; the endpoint is labeled Y2H-v1 per Methods and author files.',
            'No general Pharos accuracy, oncology validity, official gold score or causal Steward benefit is measured.']}


def check_author_proof(proof):
    if (proof.get('passed') is not True or proof.get('synthetic_only') is not True
            or proof.get('actual_outcomes_decoded') is not False
            or proof.get('pandas') != '1.4.3' or proof.get('numpy') != '1.23.0'
            or proof.get('failures') != 0 or proof.get('errors') != 0 or proof.get('skipped') != 0
            or proof.get('tests_run', 0) < 24 or proof.get('truth_table_cases') != 36
            or proof.get('implementation_sha256') != sha(ROOT / 'biograph_steward/lambourne_outcomes.py')
            or proof.get('author_full_source_sha256') != AUTHOR_CODE_SHA):
        raise ValueError('A passed synthetic replay against the pinned author runtime is required.')


def freeze(args):
    if Path(args.out).exists():
        raise ValueError('Choose a new freeze output.')
    prior, identities, _, _ = lookup_audit.prior_identity_audit(args.identity_audit, IDENTITY_SHA)
    saved = read(Path(args.lookup_audit) / 'report.json')
    if sha(Path(args.lookup_audit) / 'report.json') != LOOKUP_SHA:
        raise ValueError('Lookup report is not the reviewed frozen comparator.')
    lookup_bytes = ordinary(Path(args.lookup_audit) / 'pair_lookup.json')
    if hashlib.sha256(lookup_bytes).hexdigest() != saved['output_sha256']['pair_lookup.json']:
        raise ValueError('Lookup rows differ from their receipt.')
    # Reuse the full existing source/count/identity audit; no outcome decoder.
    reproduced, reproduced_rows = lookup_audit.audit(SimpleNamespace(pharos=args.pharos,
        identity_audit=args.identity_audit, identity_report_sha256=IDENTITY_SHA))
    strip = lambda r: {k: v for k, v in r.items() if k not in {'created_at', 'output_sha256'}}
    lookup_rows = _decode(lookup_bytes)
    if strip(reproduced) != strip(saved) or reproduced_rows != lookup_rows:
        raise ValueError('Pharos lookup does not reproduce from its original source receipts.')
    comparator = make_comparator(lookup_rows)
    if (dict(Counter(r['pharos_status'] for r in comparator)) != EXPECTED
            or sum(r['huri_overlap'] for r in comparator) != 442
            or sum(r['inmc_overlap'] for r in comparator) != 7):
        raise ValueError('Reviewed comparator population/exposure counts changed.')
    author, _ = verified_author_files(args.sources, args.source_receipts)
    raw = ordinary(Path(args.preparation) / 'raw_human.tsv')
    raw_receipt = read(Path(args.preparation) / 'raw_human.receipt.json')
    raw_url = f'https://raw.githubusercontent.com/CCSB-DFCI/ai-interactome-experimental-assessment/{COMMIT}/data/internal/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv'
    if (hashlib.sha256(raw).hexdigest() != RAW_SHA or raw_receipt.get('sha256') != RAW_SHA
            or raw_receipt.get('commit') != COMMIT or raw_receipt.get('url') != raw_url
            or raw_receipt.get('bytes') != len(raw)
            or raw_receipt.get('git_blob_sha1') != hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()):
        raise ValueError('Raw assay bytes differ from pinned author source.')
    author_code = ordinary(Path(args.preparation) / 'author_preprocessing.py')
    if hashlib.sha256(author_code).hexdigest() != AUTHOR_CODE_SHA:
        raise ValueError('Author preprocessing source differs from reviewed history.')
    code = {name: sha(ROOT / name) for name in CODE}
    proof_bytes = ordinary(Path(args.preparation).parent / 'synthetic_author_replay.json')
    proof = _decode(proof_bytes)
    check_author_proof(proof)
    if proof.get('test_sha256') != sha(ROOT / 'tests/test_lambourne_outcomes.py'):
        raise ValueError('Synthetic author proof does not bind the reviewed tests.')
    out = new_output(args.out, args.sources, args.pharos, args.identity_audit, args.lookup_audit, args.preparation)
    # Copy the exact bytes authenticated above; no path reopening for outcomes.
    files = {'source/panel.tsv': author[PANEL], 'source/orf_map.tsv': author[ORF_MAP],
             'verification/synthetic_author_replay.json': proof_bytes,
             'source/raw_human.tsv': raw, 'source/author_preprocessing.py': author_code,
             'source/raw_human.receipt.json': ordinary(Path(args.preparation) / 'raw_human.receipt.json'),
             'source/source_receipts.json': ordinary(args.source_receipts),
             'source/LICENSE': ordinary(Path(args.sources) / 'LICENSE'),
             'lookup/pair_lookup.json': lookup_bytes,
             'lookup/report.json': ordinary(Path(args.lookup_audit) / 'report.json'),
             'identity/report.json': ordinary(Path(args.identity_audit) / 'report.json'),
             'identity/identity_rows.json': ordinary(Path(args.identity_audit) / 'identity_rows.json'),
             'identity/pair_exposure.json': ordinary(Path(args.identity_audit) / 'pair_exposure.json')}
    for name in ('plan.json', 'source.json', 'summary.json', 'context_targets.json'):
        files['lookup/retrieval_' + name] = ordinary(Path(args.pharos) / name)
    for name, data in files.items():
        destination = out / name; destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(data)
    write_json(out / 'comparator.json', comparator)
    write_json(out / 'specification.json', specification())
    protocol = seal({'format': FORMAT, 'created_at': utcnow(), 'author_commit': COMMIT,
        'outcomes_decoded': False, 'population': len(comparator), 'lookup_counts': EXPECTED,
        'implementation_sha256': code, 'python': platform.python_version(),
        'source_replay_performed': True, 'source_chunks_copied': False,
        'source_replay_note': 'Full original Pharos chunks verified during freeze; their hashes are in the preserved retrieval summary. Exact pair evidence and source locators are included; full retrieval replay requires the original chunks.',
        'files': file_inventory(out, 'protocol.json')})
    write_json(out / 'protocol.json', protocol)
    validate_freeze(out)
    return protocol


def validate_freeze(folder):
    protocol, files = capture_bundle(folder, 'protocol.json')
    if (protocol.get('format') != FORMAT or protocol.get('outcomes_decoded') is not False
            or protocol.get('implementation_sha256') != {name: sha(ROOT / name) for name in CODE}
            or protocol.get('python') != platform.python_version()
            or _decode(files['specification.json']) != specification()):
        raise ValueError('Frozen implementation, runtime or specification differs.')
    if any(hashlib.sha256(files[name]).hexdigest() != expected for name, expected in SOURCE_HASHES.items()):
        raise ValueError('Frozen source differs from the reviewed study/audit bytes.')
    check_author_proof(_decode(files['verification/synthetic_author_replay.json']))
    for prefix, members in (('identity', ('identity_rows.json', 'pair_exposure.json')),
                            ('lookup', ('pair_lookup.json',))):
        source_report = _decode(files[prefix + '/report.json'])
        if any(hashlib.sha256(files[prefix + '/' + name]).hexdigest() != source_report['output_sha256'][name] for name in members):
            raise ValueError('Frozen audit outputs differ from the original source receipt.')
    lookup = _decode(files['lookup/report.json'])
    for filename, field in (('retrieval_plan.json', 'retrieval_plan_sha256'),
                            ('retrieval_summary.json', 'retrieval_summary_sha256')):
        value = _decode(files['lookup/' + filename]); require_seal(value)
        if value['content_sha256'] != lookup[field]:
            raise ValueError('Frozen retrieval metadata differs from the audited lineage.')
    if (hashlib.sha256(files['lookup/retrieval_source.json']).hexdigest() != lookup['retrieval_source_sha256']
            or hashlib.sha256(files['lookup/retrieval_context_targets.json']).hexdigest() != lookup['inventory_sha256']):
        raise ValueError('Frozen source/inventory metadata differs from the audited lineage.')
    comparator = _decode(files['comparator.json'])
    if comparator != make_comparator(_decode(files['lookup/pair_lookup.json'])):
        raise ValueError('Frozen comparator does not reproduce.')
    if (len(comparator) != protocol['population'] or dict(Counter(r['pharos_status'] for r in comparator)) != protocol['lookup_counts']
            or protocol['lookup_counts'] != EXPECTED
            or hashlib.sha256(files['source/raw_human.tsv']).hexdigest() != RAW_SHA):
        raise ValueError('Frozen population or outcome source changed.')
    return protocol, files, comparator


def join_assay(comparator, assay_rows):
    by_pair = {tuple(row['products']): row for row in assay_rows}
    if len(by_pair) != len(assay_rows) or set(by_pair) != {tuple(r['products']) for r in comparator}:
        raise ValueError('Assay output does not retain the exact nominated population.')
    rows = []
    for comp in comparator:
        assay = by_pair[tuple(comp['products'])]
        if (assay['source_row'] != comp['source_row'] or assay['assay_status'] not in ASSAY_STATES
                or type(assay['evaluable']) is not bool
                or assay['evaluable'] != (assay['assay_status'] in {'detected', 'not_detected'})
                or (assay['evaluable'] and type(assay['detected']) is not bool)
                or (assay['evaluable'] and assay['detected'] != (assay['assay_status'] == 'detected'))
                or (not assay['evaluable'] and assay['detected'] is not None)):
            raise ValueError('Assay status/identity contract differs.')
        rows.append({'comparator': comp, 'assay': assay,
                     'comparator_evaluable': assay['evaluable'] and comp['comparator'] is not None})
    return rows


def group_counts(rows):
    counts = {state: sum(r['assay']['assay_status'] == state for r in rows) for state in ASSAY_STATES}
    positive, negative = counts['detected'], counts['not_detected']
    return {'pairs': len(rows), 'assay_statuses': counts, 'assay_evaluable': positive + negative,
            'assay_excluded': len(rows) - positive - negative,
            'comparator_evaluable': sum(r['comparator_evaluable'] for r in rows),
            'detection_rate': positive / (positive + negative) if positive + negative else None}


def summarize(rows):
    statuses = {state: group_counts([r for r in rows if r['comparator']['pharos_status'] == state]) for state in STATES}
    bundles = sorted({bundle for row in rows for bundle in row['comparator']['provider_bundles']})
    exposure = {}
    for huri in (False, True):
        for inmc in (False, True):
            selected = [r for r in rows if r['comparator']['huri_overlap'] == huri and r['comparator']['inmc_overlap'] == inmc]
            exposure[f'huri={huri},inmc={inmc}'] = {state: group_counts([r for r in selected if r['comparator']['pharos_status'] == state]) for state in STATES}
    return {'overall': group_counts(rows), 'by_lookup_state': statuses,
            'by_provider_bundle': {bundle: group_counts([r for r in rows if bundle in r['comparator']['provider_bundles']]) for bundle in bundles},
            'by_exposure_combination_and_lookup': exposure,
            'by_mapping_flag': {flag: {str(value): group_counts([r for r in rows if r['comparator'][flag] == value]) for value in (False, True)} for flag in FLAGS}}


def write_html(out, report):
    def table(groups):
        headings = ('Group', 'All pairs', 'Detected', 'Not detected', 'Assay excluded', 'Detection rate')
        data = []
        for name, group in groups.items():
            rate = 'Not estimable' if group['detection_rate'] is None else f"{group['detection_rate']:.1%}"
            data.append((name, group['pairs'], group['assay_statuses']['detected'], group['assay_statuses']['not_detected'], group['assay_excluded'], rate))
        return '<table><thead><tr>' + ''.join('<th>'+escape(x)+'</th>' for x in headings) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+escape(str(x))+'</td>' for x in row)+'</tr>' for row in data) + '</tbody></table>'
    summary = report['summary']
    body = '<h1>Pharos and published human Y2H assay concordance</h1><p>Retrospective descriptive assessment of a selected panel. Study independence is unresolved; this is not a test of Steward improvement or general Pharos accuracy.</p>'
    body += '<h2>Complete nominated population</h2>' + table(summary['by_lookup_state'])
    body += '<p>Rates use detected + not-detected pairs only. Assay exclusions remain in the full population. Unresolved Pharos identities have no comparator score. Nondetection does not establish a false biological relationship.</p>'
    body += '<h2>Exact source bundles</h2>' + table(summary['by_provider_bundle']) + '<p>A pair can belong to multiple bundles; source labels do not count independent studies.</p>'
    body += '<h2>Prior exposure strata</h2>'
    for name, groups in summary['by_exposure_combination_and_lookup'].items():
        body += '<h3>' + escape(name) + '</h3>' + table(groups)
    body += '<h2>Assay status accounting</h2><pre>' + escape(str(summary['overall']['assay_statuses'])) + '</pre>'
    body += '<p>All eligibility rules and comparator outputs were frozen before individual outcome decoding. Public paper aggregates were already known. No significance test, learned predictor or post-outcome threshold selection was used.</p>'
    body += '<p><a href="report.json">Full report and limitations</a> · <a href="rows.json">All pair-level records</a> · <a href="exposure_started.json">First-access receipt</a></p>'
    (out / 'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Pharos assay corroboration</title><style>body{font:16px system-ui;max-width:1150px;margin:40px auto;padding:0 20px;line-height:1.5}table{border-collapse:collapse;width:100%;margin-bottom:24px}th,td{padding:10px;text-align:left;border-bottom:1px solid #ccc}th{background:#eef3f8}pre{white-space:pre-wrap}</style>' + body + '</html>', encoding='utf-8')


def run(folder, output):
    protocol, files, comparator = validate_freeze(folder)
    # Guarded reuse of the INMC first-exposure pattern: no semantic decoding
    # happens before the frozen bundle is checked and a durable receipt exists.
    marker = Path(folder).with_name(Path(folder).name + '_outcome_opening.json')
    if marker.exists() or marker.is_symlink():
        raise ValueError('This freeze has already opened outcomes. Use verify for replay; preserve failed attempts.')
    out = new_output(output, folder)
    opening = seal({'created_at': utcnow(), 'format': RESULT_FORMAT,
        'protocol_sha256': protocol['content_sha256'], 'status': 'exposure_started',
        'outcomes_consumed_for_future_development': True})
    # Outside the immutable freeze inventory; one exclusive first-access record
    # applies even if a caller supplies a different result directory later.
    import json
    with marker.open('x', encoding='utf-8') as stream:
        json.dump(opening, stream, indent=2, allow_nan=False)
        stream.write('\n')
    write_json(out / 'exposure_started.json', opening)
    try:
        from biograph_steward.lambourne_outcomes import adapt_outcomes
        identities = _decode(files['identity/identity_rows.json'])
        adapted = adapt_outcomes(files['source/panel.tsv'], files['source/raw_human.tsv'], identities, files['source/orf_map.tsv'])
        write_json(out / 'assay_audit.json', adapted)
        if adapted['scoring_allowed'] is not True:
            raise ValueError('Author/raw/identity reconciliation failed; no metrics emitted. Inspect assay_audit.json.')
        rows = join_assay(comparator, adapted['rows'])
        summary = summarize(rows)
        write_json(out / 'rows.json', rows)
        report = {'format': RESULT_FORMAT, 'created_at': utcnow(), 'status': 'completed',
            'protocol_sha256': protocol['content_sha256'], 'summary': summary,
            'study_independence_established': False, 'steward_improvement_tested': False,
            'outcomes_consumed_for_future_development': True, 'limitations': specification()['limitations']}
        write_html(out, report)
        report['files'] = file_inventory(out, 'report.json')
        write_json(out / 'report.json', seal(report))
        return report
    except BaseException as exc:
        failure = seal({'format': RESULT_FORMAT, 'status': 'blocked_after_outcome_access',
            'created_at': utcnow(), 'protocol_sha256': protocol['content_sha256'],
            'outcomes_consumed_for_future_development': True, 'metrics_emitted': False,
            'error': str(exc), 'files': file_inventory(out, 'failure.json')})
        write_json(out / 'failure.json', failure)
        raise


def verify(folder, output):
    protocol, files, comparator = validate_freeze(folder)
    report, captured = capture_bundle(output, 'report.json')
    opening = _decode(captured['exposure_started.json']); require_seal(opening)
    if (report.get('format') != RESULT_FORMAT or report.get('status') != 'completed'
            or report.get('protocol_sha256') != protocol['content_sha256']
            or opening.get('protocol_sha256') != protocol['content_sha256']
            or report.get('study_independence_established') is not False
            or report.get('steward_improvement_tested') is not False
            or report.get('outcomes_consumed_for_future_development') is not True):
        raise ValueError('Result is not bound to the declared frozen assessment.')
    from biograph_steward.lambourne_outcomes import adapt_outcomes
    adapted = adapt_outcomes(files['source/panel.tsv'], files['source/raw_human.tsv'],
                             _decode(files['identity/identity_rows.json']), files['source/orf_map.tsv'])
    if adapted != _decode(captured['assay_audit.json']) or adapted['scoring_allowed'] is not True:
        raise ValueError('Saved assay audit does not reproduce from frozen sources.')
    rows = join_assay(comparator, adapted['rows'])
    if rows != _decode(captured['rows.json']) or summarize(rows) != report['summary']:
        raise ValueError('Result rows or summary do not reproduce.')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('freeze')
    for name in ('pharos', 'identity-audit', 'lookup-audit', 'sources', 'source-receipts', 'preparation', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    for command in ('run', 'verify'):
        p = sub.add_parser(command); p.add_argument('--freeze', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = freeze(args) if args.command == 'freeze' else (run(args.freeze, args.out) if args.command == 'run' else verify(args.freeze, args.out))
        import json
        print(json.dumps({key: result[key] for key in ('format', 'status', 'population', 'lookup_counts', 'summary', 'content_sha256') if key in result}, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr); return 1


if __name__ == '__main__':
    raise SystemExit(main())
