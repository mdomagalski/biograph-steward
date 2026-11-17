"""Bind the existing source-eligibility rules to an explicit protein cohort.

Only operator paths and cohort-size assumptions differ from the preserved
prepare_source_eligibility.py. No reference outcomes, predictions, new identity
mapping or eligibility relaxation are introduced here.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from biograph_steward.client import digest
from biograph_steward.cohort_mapping import load_registry
from biograph_steward.file_utils import new_output, sha
from biograph_steward.graph import UNIPROT


def need(value, message):
    if not value:
        raise ValueError('Cohort source eligibility: ' + message)


def spec(path):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink()
         and not any(p.is_symlink() for p in path.parents),
         'ordinary nonsymlink input files are required.')
    return {'file': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def cohort_scope(snapshot, graph, declared):
    """Validate the complete caller cohort and the original GO completeness rule."""
    need(isinstance(declared, list) and bool(declared)
         and all(isinstance(p, str) and p.startswith('UniProtKB:')
                 and UNIPROT.fullmatch(p.removeprefix('UniProtKB:')) for p in declared)
         and len(declared) == len(set(declared)),
         'declare unique exact UniProtKB protein IDs, not symbols.')
    primary = {t['id'] for t in graph['targets']}
    original = {'UniProtKB:' + t['uniprot'] for t in snapshot['targets']}
    need(primary == original == set(declared)
         and len(primary) == len(graph['targets']) == len(snapshot['targets']),
         'declared cohort must equal all original and current primary targets.')
    need(graph['snapshot_sha256'] == snapshot['content_sha256']
         and digest({k: v for k, v in snapshot.items() if k != 'content_sha256'})
             == snapshot['content_sha256'], 'snapshot/current graph binding differs.')
    complete = {}
    for row in snapshot['retrieval']['context']['targets']:
        if row['family'] != 'go':
            continue
        need(row['uniprot'] not in complete, 'duplicate original GO source scope.')
        complete[row['uniprot']] = (row['status'] == 'complete'
            and row['retrieved'] == row['available'] == row['retained']
            and not row['issues'] and not row['excluded_by_scope'])
    need(set(complete) == {p.removeprefix('UniProtKB:') for p in primary}
         and all(complete.values()),
         'each original primary GO query must satisfy the unchanged completeness criteria.')
    return primary, complete


def prepare(*, baseline_source, current_run, cohort, registry_path, gaf,
            gaf_sha256, gaf_source_rows, ontology, ontology_sha256,
            mitocarta_workbook, output):
    baseline_source, current_run, registry_path = map(
        lambda p: Path(p).absolute(), (baseline_source, current_run, registry_path))
    gaf, ontology = map(lambda p: Path(p).absolute(), (gaf, ontology))
    paths = {'snapshot': baseline_source / 'snapshot.json',
        'current_graph': current_run / 'graph.json',
        'original_graph': baseline_source / 'graph.json',
        'registry_manifest': registry_path / 'manifest.json',
        'reviewed_human_UniProt': registry_path / 'uniprot_reviewed_human_symbols.tsv',
        'HGNC': registry_path / 'hgnc_complete_set.txt', 'ontology': ontology,
        'native_GAF': gaf, 'MitoCarta_author_workbook_bytes_only': mitocarta_workbook,
        'producer': Path(__file__)}
    pins = {name: spec(path) for name, path in paths.items()}
    need(pins['native_GAF']['sha256'] == gaf_sha256
         and pins['ontology']['sha256'] == ontology_sha256
         and type(gaf_source_rows) is int and gaf_source_rows > 0,
         'explicit native source or ontology pin differs.')
    snapshot = json.loads(paths['snapshot'].read_text())
    baseline = json.loads(paths['original_graph'].read_text())
    cohort_scope(snapshot, baseline, cohort)
    del baseline
    graph = json.loads(paths['current_graph'].read_text())
    primary, complete = cohort_scope(snapshot, graph, cohort)
    proteins = {n['id'] for n in graph['nodes']
                if n.get('category') == 'biolink:Protein'}
    need(primary <= proteins, 'primary protein node is missing.')
    _, registry = load_registry(registry_path)
    counts = Counter(); headers = []; total = 0
    with gzip.open(gaf, 'rt') as stream:
        for line in stream:
            if line.startswith('!'):
                headers.append(line.strip()); continue
            fields = line.rstrip('\n').split('\t')
            need(len(fields) == 17, 'native source is not the expected GAF framing.')
            total += 1
            if fields[0] == 'UniProtKB' and fields[12] == 'taxon:9606':
                counts[fields[1]] += 1
    need(total == gaf_source_rows, 'complete pinned GAF row count differs.')
    rows = []
    for pid in sorted(proteins):
        acc = pid.removeprefix('UniProtKB:'); protein = registry.proteins.get(acc)
        reasons = []; gene_id = None; hgnc_id = None
        if not pid.startswith('UniProtKB:') or '-' in acc:
            reasons.append('literal_canonical_accession_required')
        if protein is None:
            reasons.append('not_in_frozen_reviewed_human_UniProt_registry')
        elif len(protein['hgnc_ids']) != 1 or len(protein['ncbi_gene_ids']) != 1:
            reasons.append('unique_HGNC_and_GeneID_required')
        else:
            hgnc_id = protein['hgnc_ids'][0]; gene_id = protein['ncbi_gene_ids'][0]
            gene = registry.genes.get(hgnc_id)
            products = registry.products(hgnc_id) if gene is not None else []
            matches = [p for p in products if p['uniprot_id'] == pid]
            if (gene is None or gene['status'] != 'Approved' or gene['entrez_id'] != gene_id
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
    eligible = [r for r in rows if r['primary_source_eligible']]
    groups = {}
    for row in eligible:
        groups.setdefault(row['gene_id'], []).append(row['protein_id'])
    value = {'format': 'biograph-steward.mitocarta-source-eligibility-before-label-join.v1',
        'phase': 'source_metadata_only', 'MitoCarta_workbook_opened_by_this_producer': False,
        'cohort_reference_label_join_performed': False, 'predictions_or_metrics_computed': False,
        'primary_targets': len(primary), 'all_workspace_protein_nodes': len(proteins),
        'primary_source_eligible': len(eligible), 'primary_unique_gene_units': len(groups),
        'multiple_primary_products_per_gene': {k: v for k, v in groups.items() if len(v) > 1},
        'primary_source_excluded': len(primary) - len(eligible),
        'all_protein_reviewed_canonical_mapping_eligible': sum(r['reviewed_canonical_identity_eligible'] for r in rows),
        'primary_complete_Pharos_GO_retrieval': sum(complete.values()),
        'native_GAF_source_rows': total, 'native_GAF_headers': headers,
        'input_pins': pins, 'rows': rows,
        'scope_note': 'Full protein-node extension is mapping/source coverage only. Only complete original primary-target GO inputs can enter paired classification.'}
    need(all(spec(path) == pins[name] for name, path in paths.items()),
         'source or producer changed during preparation.')
    folder = new_output(output, baseline_source, current_run, registry_path, gaf, ontology,
                        mitocarta_workbook)
    path = folder / 'source_eligibility_before_label_join.json'
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True); stream.write('\n')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-source', 'current-run', 'cohort', 'registry', 'gaf',
                 'ontology', 'mitocarta-workbook', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--gaf-sha256', required=True)
    parser.add_argument('--gaf-source-rows', type=int, required=True)
    parser.add_argument('--ontology-sha256', required=True)
    args = parser.parse_args(argv)
    declared = json.loads(args.cohort.read_text())
    value = prepare(baseline_source=args.baseline_source, current_run=args.current_run,
        cohort=declared, registry_path=args.registry, gaf=args.gaf,
        gaf_sha256=args.gaf_sha256, gaf_source_rows=args.gaf_source_rows,
        ontology=args.ontology,
        ontology_sha256=args.ontology_sha256, mitocarta_workbook=args.mitocarta_workbook,
        output=args.out)
    print(json.dumps({k: value[k] for k in ('primary_targets', 'primary_source_eligible',
        'primary_source_excluded', 'primary_complete_Pharos_GO_retrieval',
        'all_workspace_protein_nodes', 'native_GAF_source_rows')}))


if __name__ == '__main__':
    main()
