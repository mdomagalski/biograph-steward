"""Replay an existing Wiki inventory for a graph with unchanged Wiki evidence.

This is a source-binding migration, not a new history inference or a relaxed
reader. Complete equality of the provider's source edges is required, then the
existing inventory verifier and ordinary history producer can run unchanged.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import json

from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.wiki_history import load_history_packet
from .verify import verify_inventory


def wiki_edges(graph):
    return {r['id']: r for r in graph['edges'] if r.get('record_kind') == 'pathway_membership'
            and r.get('evidence_record', {}).get('type') == 'WikiPathways'}


def migrate_inventory(inventory, old_graph, new_graph, new_path, new_sha256):
    before, after = wiki_edges(old_graph), wiki_edges(new_graph)
    if not before or before != after:
        raise ValueError('History migration requires every Wiki source edge to remain identical, with no added or removed Wiki rows.')
    rows = [row for resource in inventory['versions'] for row in resource['evidence_edges']]
    if len(rows) != len(before) or {row['edge_id'] for row in rows} != set(before):
        raise ValueError('History inventory is not the complete unchanged Wiki frame.')
    result = deepcopy(inventory)
    result.pop('content_sha256', None)
    result.update(created_at=utcnow(), source_graph_path=str(Path(new_path).absolute()),
                  source_graph_file_sha256=new_sha256,
                  parent_inventory_content_sha256=inventory['content_sha256'],
                  source_binding_migration='all_Wiki_evidence_payloads_identical; full producer replay still required')
    result['content_sha256'] = digest(result)
    return result


def extend_inventory(history, baseline_packet, packet, output, *, history_content_sha256):
    history, baseline_packet, packet = map(Path, (history, baseline_packet, packet))
    old_history = load_history_packet(history, expected_content_sha256=history_content_sha256)
    old_manifest, old_graph = gold_packet.load_packet(baseline_packet)
    new_manifest, graph = gold_packet.load_packet(packet)
    old_path, new_path = baseline_packet / 'source/graph.json', packet / 'source/graph.json'
    parent = gold_packet._read(history / 'inventory.json')
    if (sha(old_path) != old_history['report']['source_graph_file_sha256']
            or sha(old_path) != parent['source_graph_file_sha256']
            or old_manifest['snapshot_sha256'] != new_manifest['snapshot_sha256']):
        raise ValueError('Old history/baseline or new snapshot binding differs.')
    # Permit an isolated portable copy of the SAME original graph bytes. This
    # changes no source value and writes nothing to the existing inventory.
    parent_replay = {**parent, 'source_graph_path': str(old_path.absolute())}
    verify_inventory(parent_replay)
    value = migrate_inventory(parent, old_graph, graph, new_path, sha(new_path))
    verify_inventory(value)
    folder = new_output(output, history, baseline_packet, packet)
    write_json(folder / 'inventory.json', value)
    receipt = {'format': 'biograph-steward.unchanged-wiki-inventory-extension.v1', 'created_at': utcnow(),
        'parent_history_content_sha256': history_content_sha256,
        'old_packet_id': old_manifest['packet_id'], 'new_packet_id': new_manifest['packet_id'],
        'old_source_graph_sha256': sha(old_path), 'new_source_graph_sha256': sha(new_path),
        'unchanged_Wiki_evidence_edges': len(wiki_edges(graph)),
        'new_inventory_file_sha256': sha(folder / 'inventory.json'),
        'new_inventory_content_sha256': value['content_sha256'],
        'full_existing_inventory_verifier_passed': True, 'native_history_producer_reexecuted': False,
        'next_step': 'Run the existing verify_history producer against this new inventory and the same preserved sources/registry.',
        'source_graph_changed': False, 'source_history_changed': False, 'model_calls': 0, 'source_fetches': 0}
    receipt['content_sha256'] = digest(receipt)
    write_json(folder / 'migration_receipt.json', receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('history', 'baseline-packet', 'packet', 'output', 'history-content-sha256'):
        p.add_argument('--' + flag, required=True)
    a = p.parse_args()
    print(json.dumps(extend_inventory(a.history, a.baseline_packet, a.packet, a.output,
        history_content_sha256=a.history_content_sha256), indent=2))


if __name__ == '__main__':
    main()
