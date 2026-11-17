# SPDX-License-Identifier: MIT
# Path-parameter adaptation of the successful source-only preparation; no label/scoring-policy changes.
"""Metadata-only source eligibility before any MitoCarta/cohort label join."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

import argparse

_parser = argparse.ArgumentParser(description=__doc__)
_parser.add_argument('--repo', type=Path, required=True)
_parser.add_argument('--work-dir', type=Path, required=True)
_parser.add_argument('--artifacts-dir', type=Path, required=True)
_args = _parser.parse_args()
REPO = _args.repo.resolve()
OUT_DIR = _args.work_dir.resolve()
OUT_DIR.mkdir(parents=True, exist_ok=True)
ART_DIR = _args.artifacts_dir.resolve()
sys.path.insert(0, str(REPO))
from biograph_steward.cohort_mapping import load_registry


def spec(path):
    path = Path(path).resolve()
    assert path.is_file() and not path.is_symlink()
    return {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size}


def main():
    out = OUT_DIR
    base = REPO / 'runs/source_faithful_workspace_20261113/source_retained_package/baseline_packet/source'
    graph_file = REPO / 'runs/source_faithful_workspace_20261113/graph.json'
    graph = json.loads(graph_file.read_text())
    snapshot_file = base / 'snapshot.json'
    snapshot = json.loads(snapshot_file.read_text())
    registry_path = REPO / 'runs/source_faithful_workspace_20261113/pathway_history/registry'
    _, registry = load_registry(registry_path)
    complete = {}
    for row in snapshot['retrieval']['context']['targets']:
        if row['family'] == 'go':
            assert row['uniprot'] not in complete
            complete[row['uniprot']] = (row['status'] == 'complete'
                and row['retrieved'] == row['available'] == row['retained']
                and not row['issues'] and not row['excluded_by_scope'])
    primary = {t['id'] for t in graph['targets']}
    proteins = {n['id'] for n in graph['nodes'] if n.get('category') == 'biolink:Protein'}
    assert len(primary) == 99 and primary <= proteins
    gaf_file = REPO / 'runs/crc_go_context_qualification_v3_20261112/source/annotations.gaf.gz'
    counts = Counter(); headers = []; total = 0
    with gzip.open(gaf_file, 'rt') as stream:
        for line in stream:
            if line.startswith('!'):
                headers.append(line.strip()); continue
            fields = line.rstrip('\n').split('\t')
            assert len(fields) == 17
            total += 1
            # Presence only: no GO term/relation/evidence or MitoCarta outcome is scored.
            if fields[0] == 'UniProtKB' and fields[12] == 'taxon:9606':
                counts[fields[1]] += 1
    rows = []
    for pid in sorted(proteins):
        acc = pid.removeprefix('UniProtKB:'); p = registry.proteins.get(acc)
        reasons = []; gene_id = None; hgnc_id = None
        if not pid.startswith('UniProtKB:') or '-' in acc:
            reasons.append('literal_canonical_accession_required')
        if p is None:
            reasons.append('not_in_frozen_reviewed_human_UniProt_registry')
        else:
            if len(p['hgnc_ids']) != 1 or len(p['ncbi_gene_ids']) != 1:
                reasons.append('unique_HGNC_and_GeneID_required')
            else:
                hgnc_id = p['hgnc_ids'][0]; gene_id = p['ncbi_gene_ids'][0]
                g = registry.genes.get(hgnc_id)
                products = registry.products(hgnc_id) if g is not None else []
                matches = [x for x in products if x['uniprot_id'] == pid]
                if (g is None or g['status'] != 'Approved' or g['entrez_id'] != gene_id
                    or len(matches) != 1 or matches[0]['status'] != 'reviewed_human_hgnc_match'
                    or not matches[0]['hgnc_declares_accession'] or matches[0]['shared_across_genes']):
                    reasons.append('reciprocal_approved_HGNC_GeneID_context_required')
        identity_eligible = not reasons
        is_primary = pid in primary
        go_complete = complete.get(acc, False)
        if is_primary and not go_complete:
            reasons.append('Pharos_GO_retrieval_not_documented_complete')
        rows.append({'protein_id': pid, 'primary_target': is_primary,
            'hgnc_id': hgnc_id, 'gene_id': gene_id,
            'reviewed_canonical_identity_eligible': identity_eligible,
            'primary_source_eligible': is_primary and not reasons,
            'Pharos_GO_documented_complete': go_complete,
            'native_human_GAF_row_presence': counts[acc], 'reasons': reasons})
    assert all(complete.values()) and len(complete) == 99 and total == 910476
    primary_eligible = [r for r in rows if r['primary_source_eligible']]
    gene_groups = {}
    for row in primary_eligible:
        gene_groups.setdefault(row['gene_id'], []).append(row['protein_id'])
    pins = {name: spec(path) for name, path in {
        'snapshot': snapshot_file, 'current_graph': graph_file,
        'original_graph': base / 'graph.json',
        'registry_manifest': registry_path / 'manifest.json',
        'reviewed_human_UniProt': registry_path / 'uniprot_reviewed_human_symbols.tsv',
        'HGNC': registry_path / 'hgnc_complete_set.txt',
        'ontology': REPO / 'runs/crc_go_ontology_qualification_20261112/ontology/source.json.gz',
        'native_GAF': gaf_file,
        'MitoCarta_author_workbook_bytes_only': ART_DIR / 'human.mitocarta3.0.xls',
        'producer': __file__}.items()}
    value = {'format': 'biograph-steward.mitocarta-source-eligibility-before-label-join.v1',
        'phase': 'source_metadata_only', 'MitoCarta_workbook_opened_by_this_producer': False,
        'cohort_reference_label_join_performed': False, 'predictions_or_metrics_computed': False,
        'primary_targets': len(primary), 'all_workspace_protein_nodes': len(proteins),
        'primary_source_eligible': len(primary_eligible),
        'primary_unique_gene_units': len(gene_groups),
        'multiple_primary_products_per_gene': {k: v for k, v in gene_groups.items() if len(v) > 1},
        'primary_source_excluded': len(primary) - len(primary_eligible),
        'all_protein_reviewed_canonical_mapping_eligible': sum(r['reviewed_canonical_identity_eligible'] for r in rows),
        'primary_complete_Pharos_GO_retrieval': sum(complete.values()),
        'native_GAF_source_rows': total, 'native_GAF_headers': headers,
        'input_pins': pins, 'rows': rows,
        'scope_note': 'Full protein-node extension is mapping/source coverage only. Only complete original primary-target GO inputs can enter paired classification.'}
    path = out / 'source_eligibility_before_label_join.json'
    with path.open('x') as stream: json.dump(value, stream, indent=2, sort_keys=True); stream.write('\n')
    print(json.dumps({'output': spec(path), **{k:v for k,v in value.items() if k.endswith('eligible') or k.endswith('excluded') or k in ('primary_targets','all_workspace_protein_nodes','primary_complete_Pharos_GO_retrieval')}}))


if __name__ == '__main__': main()
