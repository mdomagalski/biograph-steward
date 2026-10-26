"""Inventory a Pharos extract before defining a link-prediction benchmark.

This module prepares human review, not labels, splits, or model performance.
An evidence summary (for example '2 PubMed IDs') is not a resolvable citation.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from .client import digest, write_json


def audit_graph(graph: dict) -> dict:
    """Accept a graph built from a verified snapshot; preserve all evidence IDs."""
    from .graph import safe_url, text

    if graph.get('scope', {}).get('kind') == 'protein_cohort':
        return {
            'audit_format': 'biograph-steward.benchmark-readiness.v2',
            'status': 'not_applicable',
            'scope': 'Disease-label readiness does not apply to an explicitly selected protein cohort.',
            'data_kind': graph['data_kind'], 'disease': None, 'disease_id': None,
            'snapshot_sha256': graph['snapshot_sha256'],
            'counts': {
                'proteins': len(graph['targets']), 'association_records': 0,
                'other_disease_records': 0, 'proteins_without_selected_disease_evidence': None,
                'unique_reported_pairs': 0, 'pairs_for_review': 0,
                'pairs_without_review_candidate': 0, 'records_with_explicit_citation': 0,
                'records_without_explicit_citation': 0,
                'reviewed_positive_labels': 0, 'reviewed_negative_labels': 0,
            },
            'association_data_types': {}, 'reported_source_counts': {},
            'excluded_record_reason_counts': {}, 'pairs': [], 'other_disease_edge_ids': [],
            'required_actions': [{'code': 'evaluation_task_not_defined',
                'message': 'Declare a reference task, source-overlap controls and a fixed comparison before using this graph for scientific evaluation.'}],
            'interpretation': 'Cohort membership is a retrieval selection, not a disease association or benchmark label. '
                              'Source annotations and unresolved identifiers remain inspectable; no predictive improvement has been measured.',
        }

    did = graph['disease_node_id']
    nodes = {n['id']: n for n in graph['nodes']}
    proteins = {n['id'] for n in graph['nodes'] if n['category'] == 'biolink:Protein'}
    associations = [e for e in graph['edges']
                    if e['predicate'] == 'biolink:associated_with'
                    and e['subject'] in proteins and e['object'] == did]
    pairs: dict[tuple[str, str], dict] = {}
    reason_counts: Counter = Counter()
    explicit_citations = 0
    out_of_scope = [e for e in graph['edges'] if e['predicate'] == 'biolink:associated_with'
                    and e['subject'] in proteins and e['object'] != did]
    for edge in out_of_scope:
        reason_counts.update(edge.get('review_reasons', []))
    for record in graph['quarantine']:
        if record['reason'] == 'explicit_disease_context_missing':
            reason_counts.update([record['reason']])
    for edge in associations:
        key = (edge['subject'], edge['object'])
        row = pairs.setdefault(key, {
            'pair_id': 'pair:' + digest(list(key))[:20],
            'subject': key[0], 'object': key[1],
            'symbol': nodes[key[0]].get('sym'),
            'development_level': nodes[key[0]].get('tdl'),
            'evidence_edge_ids': [], 'review_candidate_edge_ids': [],
            'excluded_records': [], 'explicit_citation_edge_ids': [],
            'reported_sources': [], 'review_status': 'pending',
            'reviewer': '', 'review_notes': '',
            'snapshot_sha256': graph['snapshot_sha256'],
            'data_kind': graph['data_kind'],
        })
        row['evidence_edge_ids'].append(edge['id'])
        if text(edge.get('primary_source_raw')):
            row['reported_sources'].append(text(edge['primary_source_raw']))
        # Only count explicit PMID identifiers or a supplied HTTP(S) reference.
        # This checks presence, not whether the citation supports the claim.
        if edge.get('publications') or safe_url(edge.get('reference_raw')):
            row['explicit_citation_edge_ids'].append(edge['id'])
            explicit_citations += 1
        reasons = set(edge.get('review_reasons', []))
        if edge['record_kind'] != 'disease_association':
            reasons.add('membership_is_not_detailed_evidence')
        name = text(edge['evidence_record'].get('name'))
        if not name:
            reasons.add('explicit_disease_context_missing')
        elif name.casefold() != text(graph['disease']['name']).casefold():
            reasons.add('evidence_disease_name_differs_from_selected_term')
        if not text(edge.get('primary_source_raw')):
            reasons.add('primary_source_missing')
        if not text(edge.get('evidence_raw')) and not text(edge.get('reference_raw')):
            reasons.add('reference_and_evidence_missing')
        if edge.get('status') != 'passed_structural_checks':
            reasons.add('structural_review_required')
        if reasons:
            row['excluded_records'].append({'edge_id': edge['id'], 'reasons': sorted(reasons)})
            reason_counts.update(reasons)
        else:
            row['review_candidate_edge_ids'].append(edge['id'])

    rows = []
    for key in sorted(pairs):
        row = pairs[key]
        for field in ['evidence_edge_ids', 'review_candidate_edge_ids',
                      'explicit_citation_edge_ids', 'reported_sources']:
            row[field] = sorted(set(row[field]))
        row['excluded_records'].sort(key=lambda x: x['edge_id'])
        row['candidate_for_review'] = bool(row['review_candidate_edge_ids'])
        rows.append(row)

    checks = []

    def check(code: str, message: str):
        checks.append({'code': code, 'message': message})

    if graph['data_kind'] == 'synthetic_demo':
        check('synthetic_data', 'Use a real snapshot for scientific evaluation; this is synthetic software test data.')
    if graph['retrieval'].get('truncated'):
        check('truncated_retrieval', 'This target list is capped. Define and freeze the candidate population before splitting.')
    if not associations:
        check('no_associations', 'No usable protein–disease association records were found in this extract.')
    if not any(r['candidate_for_review'] for r in rows):
        check('no_review_candidates', 'No pair has an exact-context record passing the current structural checks.')
    if explicit_citations < len(associations):
        check('citation_recovery', 'Recover source records or citations for evidence review. Publication counts and SNP counts are not citations.')
    check('labels_unreviewed', 'Review association type and evidence before assigning benchmark labels. Structural checks do not establish experimental support.')
    check('comparison_population_missing', 'Add a declared comparison population. Proteins absent from this disease extract are unlabeled, not proven negatives.')
    check('split_not_defined', 'Freeze a pair-level train/validation/test split; keep duplicate, reverse and disease-equivalent links out of held-out model inputs.')
    if graph.get('civic'):
        check('enrichment_independence_unresolved', 'Scoped CIViC enrichment is present. Review source overlap and underlying-study independence before claiming new evidence.')
    else:
        check('external_enrichment_missing', 'Add independently retrieved context to a copy of the baseline. Pathways returned by Pharos remain part of the Pharos baseline.')
    check('model_comparison_not_run', 'Evaluate the same model, candidate population, splits and training budget on both graph versions.')

    return {
        'audit_format': 'biograph-steward.benchmark-readiness.v2',
        'status': 'not_ready',
        'scope': 'Pharos disease-label readiness audit; scoped CIViC enrichment present, with independence unresolved.' if graph.get('civic') else 'Single Pharos disease snapshot; no label review, comparison population or training is implemented.',
        'data_kind': graph['data_kind'], 'disease': graph['disease']['name'],
        'disease_id': did, 'snapshot_sha256': graph['snapshot_sha256'],
        'counts': {
            'proteins': len(proteins), 'association_records': len(associations),
            'other_disease_records': len(out_of_scope),
            'proteins_without_selected_disease_evidence': len(proteins - {e['subject'] for e in associations}),
            'unique_reported_pairs': len(rows),
            'pairs_for_review': sum(r['candidate_for_review'] for r in rows),
            'pairs_without_review_candidate': sum(not r['candidate_for_review'] for r in rows),
            'records_with_explicit_citation': explicit_citations,
            'records_without_explicit_citation': len(associations) - explicit_citations,
            'reviewed_positive_labels': 0, 'reviewed_negative_labels': 0,
        },
        'association_data_types': dict(sorted(Counter(
            text(e['evidence_record'].get('dataType')) or 'not supplied' for e in associations).items())),
        'reported_source_counts': dict(sorted(Counter(
            text(e.get('primary_source_raw')) or 'not supplied' for e in associations).items())),
        'excluded_record_reason_counts': dict(sorted(reason_counts.items())),
        'required_actions': checks, 'pairs': rows,
        'other_disease_edge_ids': sorted(e['id'] for e in out_of_scope),
        'interpretation': 'Review candidates are database-reported associations, not verified positives. '
                          'Excluded records remain in the graph and snapshot; they are not negative labels. '
                          'Citation presence is not citation validity. Source names are not independent evidence votes.',
    }


def write_audit(audit: dict, directory: Path) -> None:
    """Write into a new or empty output directory prepared by the caller."""
    from .graph import _write_tsv

    write_json(directory / 'benchmark_readiness.json', audit)
    _write_tsv(directory / 'review_candidates.tsv', audit['pairs'], [
        'pair_id', 'subject', 'object', 'symbol', 'development_level',
        'candidate_for_review', 'reported_sources', 'evidence_edge_ids',
        'review_candidate_edge_ids', 'explicit_citation_edge_ids', 'excluded_records',
        'review_status', 'reviewer', 'review_notes', 'snapshot_sha256', 'data_kind',
    ])


def save_audit(snapshot: dict, directory: Path) -> dict:
    from .graph import build_graph

    audit = build_graph(snapshot)['benchmark_readiness']
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Output directory is not empty. Choose a new directory to preserve previous runs.')
    directory.mkdir(parents=True, exist_ok=True)
    write_audit(audit, directory)
    return audit
