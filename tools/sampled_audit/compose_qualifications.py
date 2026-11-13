#!/usr/bin/env python3
"""Combine compatible existing Gold decisions against one exact baseline.

This closes a consumer gap: separately verified GO and Wiki qualifications must
not overwrite each other. It reuses the existing Gold decision contract and
loader. Conflicting keep/prune choices fail rather than acquiring precedence.
No confidence combination or new biological adjudication is performed.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha


def compose(inputs, output):
    if len(inputs) < 2:
        raise ValueError('Provide at least two independently verified decision packages.')
    paths = [Path(p).resolve() for p in inputs]
    if len(set(paths)) != len(paths):
        raise ValueError('Do not repeat the same decision package.')
    source = []
    for path in paths:
        report, _ = gold_packet.load_decisions(path)
        decisions = gold_packet._read(path/'decisions.json')
        source.append((path, report, decisions))
    if len({(r['packet_id'], r['graph_sha256']) for _, r, _ in source}) != 1:
        raise ValueError('Qualifications must use the same exact source packet and graph.')
    keys = set(d['edge_id'] for d in source[0][2]['decisions'])
    if any(set(d['edge_id'] for d in value['decisions']) != keys for _, _, value in source):
        raise ValueError('Every input must account for the same complete edge inventory.')
    by_source = [{d['edge_id']: d for d in value['decisions']} for _, _, value in source]
    merged = []
    for eid in sorted(keys):
        rows = [(source[i][2]['method'], mapping[eid]) for i, mapping in enumerate(by_source)]
        explicit = [(method, d) for method, d in rows if d['decision'] != 'abstain']
        choices = {d['decision'] for _, d in explicit}
        if len(choices) > 1:
            raise ValueError('Conflicting keep/prune qualifications for edge ' + eid)
        chosen = next(iter(choices)) if choices else 'abstain'
        reasons = explicit or rows
        merged.append({'edge_id': eid, 'decision': chosen, 'confidence': None,
            'reason': ' | '.join(method + ': ' + d['reason'] for method, d in reasons)})
    folder = new_output(output, *paths)
    value = {'format': gold_packet.DECISION_FORMAT, 'packet_id': source[0][1]['packet_id'],
        'method': 'compatible-explicit-source-qualifications.v1',
        'actor': 'Deterministic composition of preserved policy decisions', 'decisions': merged}
    write_json(folder/'decisions.json', value)
    retained = gold_packet.save_decisions(paths[0]/'baseline_packet', folder/'decisions.json', folder/'retained')
    # Revalidate every original package after producing the composite.
    for path, report, original in source:
        if gold_packet.load_decisions(path)[0] != report or gold_packet._read(path/'decisions.json') != original:
            raise ValueError('A source decision package changed during composition.')
    report = {'format': 'biograph-steward.source-qualification-composition.v1', 'created_at': utcnow(),
        'packet_id': value['packet_id'], 'graph_sha256': source[0][1]['graph_sha256'],
        'inputs': [{'path': str(path), 'method': original['method'],
            'report_file_sha256': sha(path/'report.json'), 'report_content_sha256': r['content_sha256'],
            'decisions_file_sha256': sha(path/'decisions.json')} for path, r, original in source],
        'output_decisions_sha256': sha(folder/'decisions.json'),
        'output_retained_report_sha256': sha(folder/'retained/report.json'),
        'output_retained_report_content_sha256': retained['content_sha256'],
        'counts': retained['counts'], 'confidence_combined': False, 'conflict_precedence_applied': False,
        'biological_truth_adjudicated': False, 'source_graph_mutated': False,
        'model_calls': 0, 'source_fetches': 0, 'implementation_sha256': sha(__file__)}
    report['content_sha256'] = digest(report)
    write_json(folder/'composition_report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', action='append', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    print(json.dumps(compose(args.input, args.out), indent=2))


if __name__ == '__main__':
    main()
