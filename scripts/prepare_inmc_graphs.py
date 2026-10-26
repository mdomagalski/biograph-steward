#!/usr/bin/env python3
"""Prepare a restricted, outcome-blind Pharos/GO comparison using saved inputs.

This is a learner projection, not a disease graph, official challenge gold set,
temporal validation or biological correction. No assay outcome adapter exists
in this script. Original genes and candidate identities are never collapsed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_inmc_inputs import ARCHIVE_SHA256, TRAIN_MEMBER, identifier_pairs
from audit_pharos_inventory import (BLOCKED_PMID, pair_inventory, retained_rows,
    source_rows, verified_chunk, verified_header)
from audit_go_qualification import exposure_diagnostics, projection_key
from biograph_steward.client import canonical, digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.gold_packet import _read
from retrieve_pharos_inventory import verify_sealed

ONTOLOGY_SHA = '86c2e58bd639053cabfafd831afc4049e3da8457cb900879262d164a13ba0273'
TRAIN_SHA = 'c312a9ae5f24479944775287624604db6e449a435011874d201224263f3fdc4c'
FORMAT = 'biograph-steward.inmc-paired-projection.v1'
RELATIONS = ['interacts', 'reviewed_product_context', 'pharos_cc_annotation', 'go_is_a']
POLICY = {
    'format': 'biograph-steward.inmc-hierarchy-comparison.v1', 'fully_frozen': False,
    'task': 'Retrospective recorded Y2H detection recovery on the fixed complete-scored nominated off-diagonal panel.',
    'intervention': 'Add only official child-to-parent GO is_a edges to unchanged qualified-source annotation listings.',
    'development': {'source': 'HuRI off-diagonal unordered pairs', 'fraction': 0.05, 'seed': 20261023,
                    'selection': 'SHA256 threshold of shared-product-connected gene-pair groups; no coverage repair'},
    'model': {'embedding_dim': 32, 'num_layers': 3, 'num_bases': 4, 'activation': 'relu',
              'edge_dropout': 0.0, 'self_loop_dropout': 0.0},
    'training': {'num_epochs': 20, 'batch_size': 4096, 'num_negs_per_pos': 16,
                 'optimizer': 'Adam', 'learning_rate': 0.001, 'seeds': [17, 43, 101]},
    'training_implementation': {
        'library': 'PyKEEN 1.11.1 with torch 2.6.0', 'loss': 'SoftplusLoss',
        'batching': 'Native BatchedSLCWAInstances (sampler=None), shuffled supervision, drop_last=False',
        'negative_sampler': 'Native PseudoTypedNegativeSampler with PythonSetFilterer',
        'effective_rgcn_edge_dropout': None,
        'dropout_reason': 'Use the native disabled branch: pinned PyKEEN draws unused size-dependent random masks even at probability zero.',
        'sampler_reason': 'The pinned graph sampler can select zero-degree nodes; preserve isolated genes using the supported ordinary batch sampler.',
        'paired_checks': ['Equal R-GCN initial parameters', 'Equal R-GCN positive batch schedules',
                          'Identical supervision and reserved-identity filtering', 'Equal optimizer update counts'],
    },
    'selection': 'No HPO or early stopping; development is a diagnostic, not measured assay negatives.',
    'metrics': {'primary': 'sklearn.metrics.average_precision_score', 'secondary': 'roc_auc_score',
                'pair_score': 'arithmetic mean of both directions',
                'uncertainty': 'All paired seed deltas and leave-one-original-gene-out influence; descriptive only, no significance claim',
                'missing_score': 'Any missing/nonfinite eligible score blocks headline results; no arm-specific denominator changes'},
    'qualification': {'aspect': 'C', 'evidence_codes': ['IDA', 'HDA'], 'exclude_complex_root': 'GO:0032991',
                      'exclude_obsolete': True, 'polarity_in_pharos': 'unknown',
                      'current_goa_use': 'Conservative shared exclusion diagnostics only; never imported as recovered source identity'},
    'source_scope': 'HuRI scaffold plus reviewed product context and restricted Pharos GO listings; all Pharos PPI and other context families excluded.',
    'negative_sampling': 'Native typed proposals; filter all known scaffold positives and both orientations of every candidate/development identity.',
    'holdout_policy': 'All nominated identities including self-pairs reserved; self-pairs reported separately; no assay outcomes read until full freeze.',
    'limitations': ['Current sources postdate the assay panel; this is not temporal or study-independent validation.',
                   'Unknown Pharos GO source references and polarity remain unknown; no complete derivative-evidence exclusion is claimed.',
                   'IDA/HDA and the complex exclusion are a risk-reduction adaptation, not a certified quality ranking.',
                   'A shared reviewed UniProt entry supplies context, not assayed construct/isoform identity.',
                   'The nominated single-study panel and complete-scored subset are selected populations.'],
}


def _jsonl(path, rows):
    with Path(path).open('w', encoding='utf-8') as stream:
        for row in rows:
            stream.write(canonical(row) + '\n')


def product_mapping(inventory):
    result = {g: set() for g in inventory['panel_gene_ids']}
    for row in inventory['targets']:
        for gene in row['panel_gene_ids']:
            if gene not in result:
                raise ValueError('Product mapping refers to an undeclared original gene.')
            result[gene].add(row['uniprot_id'].removeprefix('UniProtKB:'))
    return result


def split_scaffold(training_pairs, reserved_candidates, inventory, seed=20261023, fraction=0.05):
    """Group related identities for masks only; never merge actual graph nodes."""
    if not 0 < fraction < 1:
        raise ValueError('Development fraction must be between zero and one.')
    pairs = sorted({tuple(sorted(p)) for p in training_pairs})
    if len(pairs) != len(training_pairs) or any(len(p) != 2 for p in training_pairs):
        raise ValueError('Scaffold has duplicate/reversed or malformed pairs.')
    genes = {g for p in pairs for g in p}
    if not set(inventory['panel_gene_ids']) <= genes:
        raise ValueError('Every original panel gene must remain in the scaffold vocabulary.')
    products = product_mapping(inventory)
    parent = {g: g for g in genes}

    def find(g):
        while parent[g] != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g

    by_product = defaultdict(list)
    for g, values in products.items():
        for product in values:
            by_product[product].append(g)
    for values in by_product.values():
        for gene in values[1:]:
            a, b = sorted((find(values[0]), find(gene)))
            parent[b] = a
    groups = defaultdict(list)
    for pair in pairs:
        groups[tuple(sorted(find(g) for g in pair))].append(pair)
    reserved_pairs = {tuple(sorted(row['original_genes'])) for row in reserved_candidates}
    reserved_groups = {tuple(sorted(find(g) for g in pair)) for pair in reserved_pairs}
    train, development, blocked = [], [], []
    for key, values in sorted(groups.items()):
        if key in reserved_groups:
            blocked.extend(values)
        elif all(a != b for a, b in values) and int(digest({'seed': seed, 'pair_group': key}), 16) / 2**256 < fraction:
            development.extend(values)
        else:
            train.extend(values)
    # Group closure also masks non-nominated original pairs that share products.
    masked_groups = reserved_groups | {tuple(sorted(find(g) for g in p)) for p in development}
    component_genes, component_products = defaultdict(set), defaultdict(set)
    for gene in genes:
        component_genes[find(gene)].add(gene)
        component_products[find(gene)].update(products.get(gene, set()))
    equivalents = {tuple(sorted((a, b))) for x, y in masked_groups
                   for a in component_products[x] for b in component_products[y]}
    masked_genes = {tuple(sorted((a, b))) for x, y in masked_groups
                    for a in component_genes[x] for b in component_genes[y]}
    if any(tuple(sorted(find(g) for g in p)) in masked_groups for p in train):
        raise ValueError('A masked pair-equivalence group leaked into supervision.')
    degree = Counter(g for a, b in train for g in ({a, b} if a == b else (a, b)))
    return {'train_pairs': [list(p) for p in sorted(train)],
            'development_pairs': [list(p) for p in sorted(development)],
            'excluded_reserved_pairs': [list(p) for p in sorted(blocked)],
            'product_masks': [list(p) for p in sorted(equivalents)],
            'masked_gene_pairs': [list(p) for p in sorted(masked_genes)],
            'gene_components_for_masking_only': {g: find(g) for g in sorted(genes)},
            'all_gene_ids': sorted(genes), 'training_degree': {g: degree[g] for g in sorted(genes)},
            'isolated_after_development': sorted(genes - degree.keys()),
            'panel_isolated_after_development': sorted(set(products) - degree.keys()),
            'development_seed': seed, 'development_fraction': fraction}


def ontology_graph(ontology):
    import networkx as nx
    def identifier(value):
        result = value.rsplit('/', 1)[-1].replace('GO_', 'GO:')
        if not re.fullmatch(r'GO:[0-9]{7}', result):
            raise ValueError('Expected a GO ontology identifier.')
        return result
    nodes = {}
    for row in ontology['nodes']:
        # OBO Graphs serializes relation declarations as PROPERTY nodes too.
        # They are not GO terms and must not enter the learner vocabulary.
        if row.get('type') == 'PROPERTY':
            continue
        if row.get('type') not in (None, 'CLASS'):
            raise ValueError('Unsupported OBO Graphs node type.')
        uid = identifier(row['id'])
        if uid in nodes:
            raise ValueError('Duplicate ontology node.')
        nodes[uid] = row
    graph = nx.DiGraph(); graph.add_nodes_from(nodes)
    for row in ontology['edges']:
        if row['pred'] != 'is_a':
            continue
        a, b = identifier(row['sub']), identifier(row['obj'])
        if a not in nodes or b not in nodes:
            raise ValueError('Ontology edge endpoint is absent.')
        graph.add_edge(a, b)
    if not nx.is_directed_acyclic_graph(graph) or not {'GO:0032991', 'GO:0005575'} <= nodes.keys():
        raise ValueError('Expected an acyclic is_a graph with cellular-component and complex roots.')
    return nodes, graph


def qualify_go(records, goa_rows, ontology, product_masks):
    """Keep source rows opaque; current GOA supplies conservative diagnostics."""
    import networkx as nx
    nodes, graph = ontology_graph(ontology)
    complexes = nx.ancestors(graph, 'GO:0032991') | {'GO:0032991'}
    cellular = nx.ancestors(graph, 'GO:0005575') | {'GO:0005575'}
    obsolete = {k for k, row in nodes.items() if row.get('meta', {}).get('deprecated')}
    masks = {tuple(sorted(p)) for p in product_masks}
    mask_index = {p: ['identity_only_mask'] for p in masks}
    goa = defaultdict(list)
    for row in goa_rows:
        goa[tuple(row['projection_key'])].append(row)
    ledger, annotations, prequalified = [], {}, []
    for uid, raw, locator in records:
        key = projection_key(uid, raw['goid'], raw.get('evidence'), raw.get('assigned_by'))
        term = raw['goid']; reasons = []
        if raw.get('type') != 'C': reasons.append('outside_cellular_component_scope')
        if raw.get('evidence') not in {'IDA', 'HDA'}: reasons.append('outside_IDA_HDA_scope')
        if term in complexes: reasons.append('protein_complex_subtree')
        if term in obsolete: reasons.append('obsolete_GO_term')
        if term not in nodes: reasons.append('unknown_GO_term')
        if term in nodes and term not in obsolete and term not in cellular:
            reasons.append('not_in_cellular_component_is_a_branch')
        in_selected_scope = not reasons
        if in_selected_scope: prequalified.append((uid, term))
        flags, diagnostics = set(), []
        for row in goa.get(key, []):
            row_flags = []
            if row['negated']: row_flags.append('current_goa_possible_negation')
            if row['blocked_reference_present']: row_flags.append('current_goa_blocked_reference')
            if row['annotation_extension_present']: row_flags.append('current_goa_context_extension_unresolved')
            fields = row['raw_fields']
            if fields[16] and fields[16].removeprefix('UniProtKB:') != uid:
                row_flags.append('current_goa_distinct_product_form')
            if raw.get('evidence') == 'IDA' and fields[7]:
                row_flags.append('current_goa_IDA_with_from_incompatible')
            hits = exposure_diagnostics(row, mask_index)
            if hits['with_from']: row_flags.append('current_goa_masked_pair_with_from')
            if hits['extension']: row_flags.append('current_goa_masked_pair_extension')
            flags.update(row_flags)
            if row_flags:
                diagnostics.append({'source_line': row['source_line'], 'source_record_sha256': digest(row),
                                    'flags': row_flags, 'exposure': hits})
        if BLOCKED_PMID.search(canonical(raw)): reasons.append('blocked_reference_in_pharos_row')
        reasons.extend(sorted(flags))
        entry = {'subject': 'UniProtKB:' + uid, 'object': term, 'projection_key': list(key),
                 'source_locator': locator, 'source_row': raw, 'source_row_sha256': digest(raw),
                 'in_selected_scope_before_diagnostics': in_selected_scope,
                 'disposition': 'exclude' if reasons else 'retain_source_annotation_listing',
                 'reasons': reasons, 'current_goa_compatible_rows': len(goa.get(key, [])),
                 'current_goa_diagnostics': diagnostics, 'historical_row_identity_established': False,
                 'polarity': 'unknown', 'original_reference': 'not_exposed_by_saved_Pharos_API',
                 'biological_validation': False}
        ledger.append(entry)
        if not reasons:
            pair = ('UniProtKB:' + uid, term)
            annotations.setdefault(pair, []).append(entry)
    direct_before = {term for _, term in prequalified}
    before_closure = direct_before | set().union(*(nx.descendants(graph, t) for t in direct_before))
    direct = {term for _, term in annotations}
    closure = direct | set().union(*(nx.descendants(graph, t) for t in direct))
    if closure & obsolete:
        raise ValueError('An obsolete ancestor would enter the comparison.')
    hierarchy = sorted((a, 'go_is_a', b) for a, b in graph.subgraph(closure).edges)
    immediate_parents = {b for a, _, b in hierarchy if a in direct}
    return {'records': ledger, 'annotations': [(a, 'pharos_cc_annotation', b) for a, b in sorted(annotations)],
            'hierarchy': hierarchy, 'nodes': [{'id': t, 'type': 'go_term', 'label': nodes[t].get('lbl')} for t in sorted(closure)],
            'summary': {'source_go_rows': len(records), 'prequalification_pairs': len(set(prequalified)),
                'prequalification_products': len({p for p, _ in prequalified}), 'prequalification_terms': len(direct_before),
                'prequalification_closure_nodes': len(before_closure), 'prequalification_hierarchy_edges': graph.subgraph(before_closure).number_of_edges(),
                'retained_annotation_pairs': len(annotations), 'retained_products': len({a for a, _ in annotations}),
                'retained_direct_terms': len(direct), 'closure_nodes': len(closure), 'hierarchy_edges': len(hierarchy),
                'hierarchy_edges_with_directly_annotated_child': sum(a in direct for a, _, _ in hierarchy),
                'ancestor_nodes_beyond_direct_terms_and_immediate_parents': len(closure - direct - immediate_parents),
                'additional_excluded_selected_rows': sum(r['in_selected_scope_before_diagnostics'] and bool(r['reasons']) for r in ledger),
                'selected_scope_diagnostic_exclusion_reasons': dict(Counter(reason for r in ledger if r['in_selected_scope_before_diagnostics'] for reason in r['reasons'])),
                'exclusion_reasons': dict(Counter(reason for row in ledger for reason in row['reasons'])),
                'retained_without_current_goa_match': sum(not r['reasons'] and not r['current_goa_compatible_rows'] for r in ledger),
                'retained_multiple_current_goa_matches': sum(not r['reasons'] and r['current_goa_compatible_rows'] > 1 for r in ledger)}}


def paired_arms(split, inventory, qualified):
    genes = split['all_gene_ids']
    products = product_mapping(inventory)
    links = sorted((g, 'reviewed_product_context', 'UniProtKB:' + p) for g, values in products.items() for p in values)
    supervision = sorted({(x, 'interacts', y) for a, b in split['train_pairs'] for x, y in ((a, b), (b, a))})
    baseline = sorted(set(supervision + links + qualified['annotations']))
    enriched = sorted(set(baseline + qualified['hierarchy']))
    entities = ([{'id': g, 'type': 'original_gene'} for g in genes] +
                [{'id': row['uniprot_id'], 'type': 'reviewed_product_context',
                  'assay_construct_identity_established': False} for row in inventory['targets']] + qualified['nodes'])
    ids = [r['id'] for r in entities]
    known = set(ids)
    if len(known) != len(ids) or any(a not in known or b not in known for a, _, b in enriched):
        raise ValueError('Graph vocabulary is duplicated or incomplete.')
    if set(enriched) - set(baseline) != set(qualified['hierarchy']):
        raise ValueError('The paired arm difference is not exactly the ontology intervention.')
    return {'entities': sorted(entities, key=lambda r: r['id']), 'relations': [{'id': r} for r in RELATIONS],
            'supervision': supervision, 'arms': {'scaffold': supervision, 'baseline': baseline, 'enriched': enriched},
            'product_links': links}


def _table(path, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream, delimiter='\t'); writer.writerow(['subject', 'predicate', 'object']); writer.writerows(rows)


def prepare(retrieval, audit_folder, goa_folder, ontology_path, archive, output):
    retrieval, audit_folder, goa_folder = map(Path, (retrieval, audit_folder, goa_folder))
    ontology_path, archive = Path(ontology_path), Path(archive)
    receipt = _read(ROOT / 'docs/evaluations/inmc_pharos_uniform_20261022_summary.json')
    plan, source, summary, inventory, ids, names = verified_header(retrieval)
    audit = verify_sealed(_read(audit_folder / 'report.json'))
    overlaps = _read(audit_folder / 'overlaps.json')
    expected_inputs = {name: sha(retrieval / name) for name in ('plan.json', 'source.json', 'summary.json', 'context_targets.json', 'gene_coverage.json')}
    if (audit['overlaps_sha256'] != digest(overlaps) or audit['input_files'] != expected_inputs
            or audit['chunk_files'] != summary['files'] or audit['retrieval_plan_sha256'] != plan['content_sha256']
            or plan['content_sha256'] != receipt['retrieval_plan_sha256']
            or summary['content_sha256'] != receipt['retrieval_summary_sha256']):
        raise ValueError('Inputs do not match the audited Pharos retrieval and pair inventory.')
    # Bind previously inspected artifacts; do not silently consume a replacement source.
    input_paths = {'ontology': ontology_path, 'archive': archive,
                   'goa_summary': goa_folder / 'summary.json', 'goa_staged': goa_folder / 'staged_annotations.jsonl',
                   'audit_report': audit_folder / 'report.json', 'audit_overlaps': audit_folder / 'overlaps.json',
                   'assay_contract': ROOT / 'docs/evaluations/inmc_assay_contract_20261022.json'}
    hashes = {k: sha(p) for k, p in input_paths.items()}
    fixed_artifacts = {'audit_report': 'runs/inmc_pharos_uniform_20261022/audit/report.json',
                       'audit_overlaps': 'runs/inmc_pharos_uniform_20261022/audit/overlaps.json',
                       'goa_summary': 'runs/inmc_go_feasibility_20261022/pharos_join/summary.json'}
    if any(hashes[key] != receipt['local_artifacts'][name] for key, name in fixed_artifacts.items()):
        raise ValueError('Audited candidate population or GOA receipt differs from the pre-outcome source freeze.')
    assay_binding = _read(ROOT / 'docs/evaluations/inmc_readiness_followup_20261022_summary.json')
    if hashes['assay_contract'] != assay_binding['assay_contract_sha256']:
        raise ValueError('The prespecified assay contract changed before graph preparation.')
    if hashes['ontology'] != ONTOLOGY_SHA or hashes['archive'] != ARCHIVE_SHA256:
        raise ValueError('Ontology or INMC archive differs from the selected release.')
    go_summary = _read(input_paths['goa_summary'])
    if (hashes['goa_staged'] != receipt['go_source']['staged_annotations_sha256']
            or hashes['goa_staged'] != go_summary['staged_annotations_sha256']
            or go_summary['inputs']['pharos_retrieval']['input_files'] != expected_inputs
            or go_summary['inputs']['inventory_sha256'] != plan['inventory_sha256']):
        raise ValueError('GOA diagnostics do not match the frozen same-retrieval source audit.')
    with zipfile.ZipFile(BytesIO(archive.read_bytes())) as bundle:
        training_bytes = bundle.read(TRAIN_MEMBER)  # The outcome member is deliberately never read.
    if hashlib.sha256(training_bytes).hexdigest() != TRAIN_SHA:
        raise ValueError('Training scaffold differs from the inspected source.')
    training = identifier_pairs(training_bytes, panel=False)
    candidates = overlaps['candidate_pairs']
    _, rebuilt_candidates, _ = pair_inventory([tuple(r['original_genes']) for r in candidates], inventory)
    if [(r['id'], r['original_genes'], r['equivalent_product_pairs']) for r in rebuilt_candidates] != [
            (r['id'], r['original_genes'], r['equivalent_product_pairs']) for r in candidates]:
        raise ValueError('Reserved identities or their product projections do not reproduce.')
    split = split_scaffold(training, candidates, inventory)
    records, ppi_exclusions, resolved = [], [], set()
    for number, name in enumerate(names):
        chunk = verified_chunk(retrieval, name, plan, source, summary, ids[number * plan['chunk_size']:(number + 1) * plan['chunk_size']])
        resolved.update(t['uniprot'] for t in chunk['targets'])
        raw_go = Counter((uid, digest(row)) for uid, row, _ in source_rows(chunk, name, 'go'))
        for uid, row, locator in retained_rows(chunk, name, 'go'):
            key = uid, digest(row)
            if raw_go[key] < 1: raise ValueError('Retained GO row is missing from raw source responses.')
            raw_go[key] -= 1; records.append((uid, row, locator))
        mask = {tuple(p) for p in split['product_masks']}
        for uid, row, locator in retained_rows(chunk, name, 'ppis'):
            partner = row['target']['uniprot']
            ppi_exclusions.append({'source_locator': locator, 'subject': uid, 'object': partner,
                'source_row_sha256': digest(row), 'reason': 'all_current_Pharos_PPI_outside_selected_projection',
                'reserved_or_development_product_pair': tuple(sorted((uid, partner))) in mask})
    if len(records) != summary['families']['go']['retained'] or len(ppi_exclusions) != summary['families']['ppis']['retained']:
        raise ValueError('Source inventory counts do not reconcile.')
    with gzip.open(ontology_path, 'rt') as stream: ontology = json.load(stream)['graphs'][0]
    with input_paths['goa_staged'].open() as stream: goa_rows = [json.loads(line) for line in stream]
    qualified = qualify_go(records, goa_rows, ontology, split['product_masks'])
    prior = receipt['hierarchy_scope_feasibility']
    for actual, expected in [('prequalification_pairs', 'retained_distinct_product_go_pairs'),
                             ('prequalification_products', 'retained_products'), ('prequalification_terms', 'direct_go_terms'),
                             ('prequalification_closure_nodes', 'ancestor_closure_nodes'), ('prequalification_hierarchy_edges', 'ancestor_closure_edges')]:
        if qualified['summary'][actual] != prior[expected]:
            raise ValueError('Selected scope does not reproduce the prespecified outcome-blind feasibility counts: ' + actual)
    paired = paired_arms(split, inventory, qualified)
    protocol = json.loads(json.dumps(POLICY))
    protocol['assay_contract_sha256'] = hashes['assay_contract']
    protocol['graph_source_hashes'] = hashes
    protocol['hierarchy_smoke'] = None; protocol['runner_sha256'] = None
    out = new_output(output, retrieval, audit_folder, goa_folder, ontology_path, archive)
    (out / 'arms').mkdir()
    for name, rows in paired['arms'].items(): _table(out / 'arms' / (name + '.tsv'), rows)
    _table(out / 'supervision.tsv', paired['supervision'])
    for name, value in [('entities.json', paired['entities']), ('relations.json', paired['relations']),
                        ('protocol.json', protocol), ('candidates.json', candidates), ('split.json', split),
                        ('development_pairs.json', split['development_pairs']), ('source_inventory.json', inventory),
                        ('assay_contract.json', _read(input_paths['assay_contract']))]: write_json(out / name, value)
    _jsonl(out / 'annotation_dispositions.jsonl', qualified['records'])
    _jsonl(out / 'excluded_pharos_ppi.jsonl', ppi_exclusions)
    write_json(out / 'excluded_source_families.json', {family: {**v, 'learner_use': 'none'}
        for family, v in summary['families'].items() if family != 'go'})
    report = {'format': FORMAT, 'created_at': utcnow(), 'status': 'graphs_prepared_resource_check_pending',
        'fully_frozen': False, 'outcome_values_loaded': False, 'author_positive_pairs_opened': False,
        'scientific_predictions_generated': False, 'model_requests': 0,
        'pharos_version': source['db_version'], 'source_files': {k: {'path': str(p.resolve()), 'sha256': hashes[k]} for k, p in input_paths.items()},
        'retrieval_files': expected_inputs, 'chunk_files': summary['files'],
        'code_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__), ROOT / 'scripts/audit_pharos_inventory.py',
            ROOT / 'scripts/audit_inmc_inputs.py', ROOT / 'scripts/audit_go_qualification.py', ROOT / 'scripts/retrieve_pharos_inventory.py']},
        'counts': {'entities': len(paired['entities']), 'entity_types': dict(Counter(r['type'] for r in paired['entities'])),
            'original_scaffold_pairs': len(training), 'supervised_unordered_pairs': len(split['train_pairs']),
            'supervised_directed_triples': len(paired['supervision']), 'development_pairs': len(split['development_pairs']),
            'scaffold_reserved_equivalent_exclusions': len(split['excluded_reserved_pairs']), 'candidate_pairs': len(candidates),
            'candidate_self_pairs': sum(r['self_pair'] for r in candidates), 'gene_product_context_links': len(paired['product_links']),
            'masked_product_pairs': len(split['product_masks']), 'masked_gene_pairs': len(split['masked_gene_pairs']),
            'panel_isolated_after_development': len(split['panel_isolated_after_development']),
            'arms': {k: len(v) for k, v in paired['arms'].items()}, 'GO': qualified['summary'],
            'excluded_pharos_ppi_retained_rows': len(ppi_exclusions),
            'excluded_pharos_ppi_reserved_or_development_rows': sum(r['reserved_or_development_product_pair'] for r in ppi_exclusions)},
        'known_reserved_overlap': audit['ppi_overlap'], 'invariants': {'same_supervision': True, 'same_union_vocabulary': True,
            'only_hierarchy_added': True, 'candidate_nodes_preserved': True, 'no_Pharos_PPI_in_any_arm': True,
            'no_GOA_protein_annotations_added': True, 'no_disease_membership_invented': True},
        'remaining_before_full_freeze': ['Pass native three-hop synthetic smoke.', 'Pass intended-device resource smoke.',
            'Freeze implementation/runtime hashes and scoring adapter before decoding any reserved assay outcomes.'],
        'limitations': protocol['limitations']}
    if (any(sha(p) != hashes[k] for k, p in input_paths.items())
            or any(sha(retrieval / name) != value for name, value in expected_inputs.items())
            or any(sha(retrieval / name) != value for name, value in summary['files'].items())):
        raise ValueError('Inputs changed during preparation; no sealed report was written.')
    report['files'] = {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    report['content_sha256'] = digest(report); write_json(out / 'report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retrieval', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--goa-audit', type=Path, required=True)
    parser.add_argument('--ontology', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.retrieval, args.audit, args.goa_audit, args.ontology, args.archive, args.out)
    print(json.dumps({'status': report['status'], 'counts': report['counts'], 'output': str(args.out.resolve())}, indent=2))
