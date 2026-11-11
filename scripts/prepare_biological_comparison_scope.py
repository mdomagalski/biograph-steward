#!/usr/bin/env python3
"""Prepare a label-free candidate scope from the already consumed Y2H assessment.

This replays existing authenticated outcomes only to preserve prior eligibility.
It does not retrieve sources, calculate rankings, modify a graph or open a new
reference. Predictor mapping and score-censoring policies are a separate step.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import assess_lambourne_corroboration as assessment
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.gold_packet import _decode

FORMAT = 'biograph-steward.biological-comparison-scope.v1'
INVENTORY_FORMAT = 'biograph-steward.intact-consumed-inventory.v1'
# Literal fields only: provider labels and Pharos local nids cannot supply these.
PREREQUISITES = {
    'publication': {'publication', 'publications', 'pmid', 'pubmed', 'reference', 'references'},
    'curated_interaction_identifier': {'imex', 'intact', 'interaction_id', 'interaction_identifier'},
    'detection_method': {'detection_method', 'interaction_detection_method'},
    'interaction_type': {'interaction_type'},
    'experimental_host': {'experimental_host', 'host_organism'},
    'MIscore': {'miscore', 'intact_miscore'},
}


def exact_intact_pairs(inventory):
    """Only literal single-UniProt participants; do not collapse complexes/forms."""
    pairs = set()
    for row in inventory.get('pairs', []):
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError('Consumed inventory pair schema differs.')
        products = []
        for participant in row:
            if (isinstance(participant, list) and len(participant) == 1
                    and isinstance(participant[0], list) and len(participant[0]) == 2
                    and participant[0][0] == 'uniprotkb'
                    and isinstance(participant[0][1], str) and participant[0][1]):
                products.append(participant[0][1])
        if len(products) == 2:
            pairs.add(tuple(sorted(products)))
    return pairs


def project_candidates(lookup_rows, result_rows, inventory):
    """Authenticate exact pair/row/construct joins before dropping outcome labels."""
    comparator = assessment.make_comparator(lookup_rows)
    if any(not isinstance(row, dict) or set(row) != {'comparator', 'assay', 'comparator_evaluable'}
           for row in result_rows):
        raise ValueError('Saved assessment row schema differs.')
    assays = [row['assay'] for row in result_rows]
    joined = assessment.join_assay(comparator, assays)
    if joined != result_rows:
        raise ValueError('Assessment does not reproduce from exact source lookup identities.')
    consumed = exact_intact_pairs(inventory)
    result = []
    for row in joined:
        comp, assay = row['comparator'], row['assay']
        identity = comp['identity']
        if any(assay.get(key) != identity.get(key) or not isinstance(identity.get(key), str)
               or not identity[key] for key in ('ad_orf_id', 'db_orf_id')):
            raise ValueError('Assay constructs disagree with exact author identity.')
        result.append({'products': comp['products'], 'source_row': comp['source_row'],
            'constructs': {'ad_orf_id': identity['ad_orf_id'], 'db_orf_id': identity['db_orf_id'],
                           'protein_to_construct_orientation_inferred': False},
            'assay_eligible': assay['evaluable'],
            'assay_exclusion_reason': None if assay['evaluable'] else assay['assay_status'],
            'historical_pharos_comparator_eligible': row['comparator_evaluable'],
            'pharos_status': comp['pharos_status'], 'pharos_present': comp['comparator'],
            'resolved_endpoint_count': comp['resolved_endpoint_count'],
            'provider_bundles': comp['provider_bundles'],
            'previous_pharos_status': comp['previous_pharos_status'],
            'exposure': {**{flag: comp[flag] for flag in assessment.FLAGS},
                         'huri_overlap': comp['huri_overlap'], 'inmc_overlap': comp['inmc_overlap'],
                         'consumed_intact_exact_pair': tuple(comp['products']) in consumed},
            'lookup_record_sha256': comp['lookup_record_sha256']})
    return result


def field_availability(lookup_rows):
    properties, fields, prerequisites = Counter(), Counter(), Counter()
    records = [match['record'] for row in lookup_rows for match in row['pharos_matches']['raw']]
    for record in records:
        fields.update(record.keys())
        props = record.get('props', [])
        if not isinstance(props, list) or any(not isinstance(p, dict) or not isinstance(p.get('name'), str) for p in props):
            raise ValueError('Pharos property schema differs.')
        properties.update(p['name'] for p in props)
        names = {str(key).lower().replace(' ', '_').replace('-', '_')
                 for key, value in record.items() if value not in (None, '', [], {})}
        names.update(p['name'].lower().replace(' ', '_').replace('-', '_')
                     for p in props if p.get('value') not in (None, '', [], {}))
        prerequisites.update(name for name, aliases in PREREQUISITES.items() if names & aliases)
    return {'matching_source_views': len(records), 'source_record_field_counts': dict(sorted(fields.items())),
        'source_property_name_counts': dict(sorted(properties.items())),
        'MImerge_MIscore_prerequisite_literal_field_counts': {name: prerequisites[name] for name in PREREQUISITES},
        'interpretation': 'Literal field availability, not recovered study lineage; local nid and provider bundle are not curated evidence identities.'}


def prepare(assessment_dir, intact_inventory, output):
    assessment_dir, intact_inventory = Path(assessment_dir).absolute(), Path(intact_inventory).absolute()
    freeze, results = assessment_dir / 'freeze', assessment_dir / 'results'
    # Reuse the original verifier; do not create a new outcome adapter.
    verified = assessment.verify(freeze, results)
    protocol, frozen = assessment.capture_bundle(freeze, 'protocol.json')
    report, captured = assessment.capture_bundle(results, 'report.json')
    if verified != report or report.get('outcomes_consumed_for_future_development') is not True:
        raise ValueError('Use the completed, already consumed assessment.')
    inventory_raw = assessment.ordinary(intact_inventory)
    inventory = _decode(inventory_raw)
    assessment.require_seal(inventory)
    if inventory.get('format') != INVENTORY_FORMAT or inventory.get('inventory_revision') != 2:
        raise ValueError('Expected the complete consumed IntAct inventory revision 2.')
    lookup = _decode(frozen['lookup/pair_lookup.json'])
    candidates = project_candidates(lookup, _decode(captured['rows.json']), inventory)
    accessions = sorted({product for row in candidates for product in row['products']})
    counts = {'candidate_pairs': len(candidates), 'accessions': len(accessions),
        'assay_eligible': sum(row['assay_eligible'] for row in candidates),
        'assay_excluded': sum(not row['assay_eligible'] for row in candidates),
        'assay_exclusion_reasons': dict(sorted(Counter(row['assay_exclusion_reason'] for row in candidates if not row['assay_eligible']).items())),
        'historical_pharos_comparator_eligible': sum(row['historical_pharos_comparator_eligible'] for row in candidates),
        'assay_eligible_but_historical_pharos_unresolved': sum(row['assay_eligible'] and not row['historical_pharos_comparator_eligible'] for row in candidates),
        'pharos_states': dict(Counter(row['pharos_status'] for row in candidates)),
        'consumed_intact_exact_single_uniprot_pairs': len(exact_intact_pairs(inventory)),
        'consumed_intact_exact_pair_overlap': sum(row['exposure']['consumed_intact_exact_pair'] for row in candidates)}
    original = report['summary']['overall']
    if (counts['candidate_pairs'] != protocol['population'] or counts['candidate_pairs'] != original['pairs']
            or counts['assay_eligible'] != original['assay_evaluable']
            or counts['assay_excluded'] != original['assay_excluded']
            or counts['historical_pharos_comparator_eligible'] != original['comparator_evaluable']):
        raise ValueError('Scope denominators disagree with authenticated assessment.')
    source_hashes = {'assessment/freeze/protocol.json': sha(freeze / 'protocol.json'),
                    'assessment/results/report.json': sha(results / 'report.json'),
                    'intact_inventory.json': sha(intact_inventory),
                    **{'assessment/freeze/' + name: value for name, value in protocol['files'].items()},
                    **{'assessment/results/' + name: value for name, value in report['files'].items()}}
    out = new_output(output, assessment_dir, intact_inventory)
    write_json(out / 'candidates.json', candidates)
    write_json(out / 'accession_inventory.json', {'format': 'biograph-steward.biological-comparison-accessions.v1',
               'uniprot_accessions': accessions, 'candidate_selection_uses_detection_labels': False})
    result = {'format': FORMAT, 'created_at': utcnow(), 'status': 'scope_prepared_predictor_inputs_pending',
        'endpoint': 'Recorded detection in the reported human Y2H-v1 assessment; nondetection is assay-conditional.',
        'dataset_status': 'consumed_development', 'all_original_nominations_preserved': True,
        'existing_consumed_outcomes_replayed': True, 'per_pair_detection_labels_exported': False,
        'candidate_selection_uses_detection_labels': False, 'counts': counts,
        'pharos_field_availability': field_availability(lookup),
        'next_component': {'arms': ['STRING12.5 functional retrieval score',
                                  'STRING12.5 physical overlay of the same functional retrieval'],
            'assessment': 'fixed task-compatible ranking component comparison',
            'historical_pharos_lookup_role': 'descriptive anchor, not a third matched source-release arm',
            'predictor_inputs_prepared': False, 'mapping_and_score_censoring_policies_fixed': False,
            'three_arm_steward_comparison_ready': False,
            'remaining_gap': 'No adequate same-information addition versus qualified-evidence input contrast; current Pharos records lack MImerge/MIscore prerequisites.'},
        'source_input_sha256': source_hashes,
        'source_content_sha256': {'assessment_protocol': protocol['content_sha256'],
                                  'assessment_result': report['content_sha256'],
                                  'intact_inventory': inventory['content_sha256']},
        'implementation_sha256': {str(Path(__file__).relative_to(ROOT)): sha(Path(__file__)),
                                 **protocol['implementation_sha256']},
        'graph_modified': False, 'new_outcome_source_accesses': 0, 'new_source_calls': 0,
        'model_calls': 0, 'GPU_runs': 0, 'scores_generated': False,
        'study_independence_established': False, 'biological_improvement_measured': False,
        'limitations': ['A consumed selected panel cannot establish unseen generalization.',
            'Unknown historical Pharos/provider study reuse remains unresolved.',
            'No mapping, zero-score or missing-score equivalence is assumed.',
            'Matched source release and full candidate coverage need verification before comparison.'],
        'files': {name: sha(out / name) for name in ('candidates.json', 'accession_inventory.json')}}
    write_json(out / 'report.json', assessment.seal(result))
    if source_hashes['intact_inventory.json'] != sha(intact_inventory):
        raise ValueError('Inventory changed during preparation; preserve this failed output.')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assessment', type=Path, required=True)
    parser.add_argument('--intact-inventory', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.assessment, args.intact_inventory, args.out)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')
    print(f"{result['status']}: {result['counts']['candidate_pairs']} pairs; {args.out.resolve()}")


if __name__ == '__main__':
    main()
