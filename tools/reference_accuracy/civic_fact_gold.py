"""Apply a qualified public human CIViC-Fact review to its exact claim projection.

This optional adapter labels only the author's five-field claim/evidence task.
It does not adjudicate an entire qualified graph assertion, clinical efficacy,
or independent experimental truth. No model or upstream builder code executes.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import json
import re

from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .design import need, write_jsonl


AXIS = 'expert_gold_claim_evidence_benchmark_projection'
COMMIT = '1a767d889b015a836f0f4331afcac5cef165ec7f'
SOURCE_PINS = {
    'reviews': 'e470989ee94045780bf30a5596d044d98f6e9850c7f7b3fffcabf0b7ef7553c9',
    'raw_reviews': '7a3eb61acedea1643d5ac2e875f4d74282a89b62515d86eb96b207d4b7a62e80',
    'processor': '8bebf3918ac2a40a3f9e9a749aa664dce380037eea21d61ad53b07df95cf6985',
}
FIELDS = ('molecularProfile', 'evidenceType', 'significance', 'therapies', 'diseases')
WORDS = ('molecular profile', 'evidence type', 'significance', 'therapies', 'diseases')
LABELS = ('SUPPORTS', 'REFUTES', 'NEI')
ROUND = 'model error review 2024.05.21'
OUTSIDE_SCOPE = ['evidenceDirection', 'variantOrigin', 'therapyInteractionType',
                 'full_current_description_and_free_text_clinical_conditions']


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def checked(path, role):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink() and sha(path) == SOURCE_PINS[role],
         'CIViC-Fact author source bytes are not qualified: ' + role)
    return path


def reference_projection(row):
    """Read the released table; never expand aliases, variants or regimens."""
    claim = row.get('claim')
    need(isinstance(claim, list) and len(claim) == 1 and claim[0].get('type') == 'table',
         'one original structured claim table required')
    table = claim[0].get('content')
    need(isinstance(table, list) and all(isinstance(x, list) and len(x) == 2
         and all(isinstance(v, str) and v.strip() for v in x) for x in table), 'claim table fields differ')
    data = dict(table)
    need(len(data) == len(table) and set(data) == set(FIELDS), 'exact five-field benchmark projection required')
    # Author processing explicitly makes claim.flat authoritative where old
    # claim objects disagreed; accepting an inconsistent pair is unsafe.
    expected = '; '.join(word + ' is ' + data[key] for key, word in zip(FIELDS, WORDS))
    need(row.get('claim.flat') == expected, 'released flat claim and structured table disagree')
    therapies = [s for s in claim[0].get('meta', {}).get('synonyms', []) if s.get('type') == 'therapy']
    need(bool(therapies) and all(isinstance(t.get('name'), str) and isinstance(t.get('xrefs'), str)
         and re.fullmatch(r'NCI:C[0-9]+', t['xrefs']) for t in therapies),
         'complete native therapy names and NCIt cross-references required')
    names = [t['name'] for t in therapies]
    need(len(set(names)) == len(names) and len({t['xrefs'] for t in therapies}) == len(therapies),
         'therapy identity duplicates')
    need(data['therapies'] == ' and '.join(names), 'whole therapy table differs from native therapy entries')
    return {**{k: data[k] for k in FIELDS if k != 'therapies'},
        'therapies': sorted((t['name'], t['xrefs'][4:]) for t in therapies)}


def human_final_label(row, raw):
    """Bind typed human tags to the author's final correction, excluding model tags."""
    need(row.get('claim.generated') is False and row.get('evidence.generated') is False
         and row.get('claim.source') == 'civic' and raw.get('claim.generated') is False
         and raw.get('evidence.generated') is False and raw.get('claim.source') == 'civic',
         'augmented claims/evidence cannot be native graph gold')
    need(all(row.get(k) == raw.get(k) for k in ('id', 'display_id', 'civic.id', 'document.pmid',
              'claim.hash', 'evidence.hash')), 'manual input and processed source identity differ')
    reviews = row.get('reviews')
    need(isinstance(reviews, list) and bool(reviews), 'explicit human review required')
    need(all(r.get('username') == 'creisle' and r.get('round') == ROUND
         and r.get('label') in LABELS and isinstance(r.get('reason'), str) and r['reason'].strip()
         and r.get('original_label') == raw.get('gold_label_name') for r in reviews),
         'qualified single-expert review provenance differs')
    tags = raw.get('label')
    need(isinstance(tags, list) and all(isinstance(t, str) for t in tags), 'original manual tags required')
    human_tags = [t for t in tags if t and not t.startswith('[')]
    need(all(r['label'] + '. ' + r['reason'] in human_tags for r in reviews),
         'final label lacks its actual unbracketed human-entered tag')
    labels = {r['label'] for r in reviews}
    need(len(labels) == 1 and row.get('gold_label_name') in labels,
         'human reviews conflict or released final gold disagrees')
    return row['gold_label_name']


def match_projection(record, projection, pmid, reference_evidence):
    """Match only the old benchmark projection; omitted context stays unassessed."""
    significance = {'RESISTANCE': 'resistance', 'SENSITIVITYRESPONSE': 'sensitivity/response'}
    current = {'molecularProfile': record['molecularProfile']['name'],
        'evidenceType': record['evidenceType'], 'significance': significance.get(record['significance']),
        'diseases': record['disease']['name'],
        'therapies': sorted((t['name'], t['ncitId']) for t in record['therapies'])}
    mismatch = [k for k in FIELDS if current[k] != projection[k]]
    if record['source'].get('sourceType') != 'PUBMED' or str(record['source'].get('citationId')) != str(pmid):
        mismatch.append('publication')
    # Gold adjudicates a claim/evidence pair. The same five-field claim with a
    # different source passage does not inherit that pair's human judgment.
    if not isinstance(reference_evidence, str) or record.get('description') != reference_evidence:
        mismatch.append('current_evidence_passage')
    # A directionless historical positive claim cannot stand in for a source
    # record explicitly reporting DOES_NOT_SUPPORT that same significance.
    if record.get('evidenceDirection') != 'SUPPORTS':
        mismatch.append('legacy_positive_claim_direction_scope')
    return mismatch


def apply_to_graph(graph, reference_rows, raw_rows, *, retained_edge_ids=None):
    raw_by_id = {r['id']: r for r in raw_rows}
    need(len(raw_by_id) == len(raw_rows), 'raw reference IDs duplicate')
    references, rejected = defaultdict(list), []
    for row in reference_rows:
        try:
            need(row['id'] in raw_by_id, 'original manual input missing')
            label = human_final_label(row, raw_by_id[row['id']])
            projection = reference_projection(row)
            references[str(row['civic.id'])].append((row, projection, label))
        except (ValueError, KeyError, TypeError) as error:
            rejected.append({'reference_row_id': row.get('id'), 'reason': str(error)})
    clinical = [e for e in graph['edges'] if e.get('record_kind') == 'variant_therapy_response']
    assertions = {a['id']: a for a in graph.get('assertions', [])}
    results = []
    for edge in clinical:
        record = edge['evidence_record']; matches, candidates = [], []
        for row, projection, label in references.get(str(record['id']), []):
            mismatch = match_projection(record, projection, row['document.pmid'], row.get('evidence.flat'))
            candidates.append({'reference_row_id': row['id'], 'mismatching_fields': mismatch})
            if not mismatch:
                matches.append({'reference_row_id': row['id'], 'gold_label': label,
                    'reference_row_sha256': digest(row), 'claim_projection_sha256': digest(projection),
                    'reference_evidence_sha256': digest(row['evidence.flat']),
                    'current_description_equals_reference_evidence': record.get('description') == row['evidence.flat'],
                    'single_human_reviewer': 'creisle', 'review_round': ROUND,
                    'non_model_typed_review_tag_verified': True})
        labels = {m['gold_label'] for m in matches}
        verdict = next(iter(labels)) if len(labels) == 1 else 'unknown'
        results.append({'edge_id': edge['id'], 'assertion_id': edge['assertion_id'],
            'evidence_item_id': record['id'], 'axis': AXIS, 'benchmark_projection_label': verdict,
            'source_record_sha256': digest(record), 'source_direction': record.get('evidenceDirection'),
            'source_variant_origin': record.get('variantOrigin'),
            'source_therapy_interaction': record.get('therapyInteractionType'),
            'source_edge_structural_status': edge.get('status'),
            'source_assertion_lifecycle_state': assertions.get(edge['assertion_id'], {}).get('lifecycle_state'),
            'matched_gold_rows': matches,
            'candidate_context_checks': candidates, 'outside_benchmark_context_unassessed': OUTSIDE_SCOPE,
            'whole_assertion_scientific_correctness': 'unknown',
            'retained_source_edge': edge['id'] in retained_edge_ids if retained_edge_ids is not None else None})
    return results, {'qualified_human_reference_rows': sum(map(len, references.values())),
                     'rejected_reference_rows': rejected}


def prepare(packet, dispositions, reviews, raw_reviews, processor, plan, output, *, plan_sha256,
            disposition_report_sha256):
    packet, dispositions, plan = map(Path, (packet, dispositions, plan))
    need(plan.is_file() and sha(plan) == plan_sha256, 'frozen eligibility plan changed')
    selected = json.loads(plan.read_text())
    paths = {role: checked(path, role) for role, path in
             (('reviews', reviews), ('raw_reviews', raw_reviews), ('processor', processor))}
    need(sha(dispositions/'report.json') == disposition_report_sha256,
         'exact retained package report pin required')
    manifest, graph = gold_packet.load_packet(packet)
    report, retained = gold_packet.load_decisions(dispositions)
    need(report['packet_id'] == manifest['packet_id']
         and report['graph_sha256'] == manifest['graph_sha256']
         and sha(packet/'source/graph.json') == selected['source_graph']['sha256'], 'source packet differs from frozen full cohort')
    pins = {str(packet/'packet_manifest.json'): sha(packet/'packet_manifest.json'),
        **{str(packet/name): pin for name, pin in manifest['files'].items()},
        str(dispositions/'report.json'): disposition_report_sha256,
        **{str(dispositions/name): pin for name, pin in report['files'].items()}}
    clinical = [e for e in graph['edges'] if e.get('record_kind') == 'variant_therapy_response']
    need({(r['edge_id'], r['assertion_id'], r['evidence_item_id']) for r in selected['panel']}
         == {(e['id'], e['assertion_id'], e['evidence_record']['id']) for e in clinical}
         and len(clinical) == selected['source_record_panel_size']
         and len({e['assertion_id'] for e in clinical}) == selected['qualified_assertions'],
         'complete frozen clinical EvidenceItem/assertion panel differs')
    labels, audit = apply_to_graph(graph, read_rows(paths['reviews']), read_rows(paths['raw_reviews']),
        retained_edge_ids={e['id'] for e in retained['edges']})
    matched = [r for r in labels if r['benchmark_projection_label'] != 'unknown']
    supported = [r for r in matched if r['benchmark_projection_label'] == 'SUPPORTS']
    edges = {e['id']: e for e in graph['edges']}
    pharos_supported = [r for r in supported if edges[r['edge_id']].get('aggregator') == 'Pharos'
        and edges[r['edge_id']].get('data_kind') == 'live_pharos']
    pin = sha(__file__)
    out = new_output(output, packet, dispositions, *paths.values(), plan)
    write_jsonl(out/'labels.private.jsonl', labels)
    write_json(out/'reference_admission.private.json', audit)
    result = {'format': 'biograph-steward.civic-fact-human-gold-projection.v1', 'created_at': utcnow(),
        'axis': AXIS, 'source_packet_id': manifest['packet_id'], 'source_graph_sha256': manifest['graph_sha256'],
        'upstream_commit': COMMIT, 'source_records': len(labels),
        'qualified_assertions': len({r['assertion_id'] for r in labels}),
        'reference_rows': audit['qualified_human_reference_rows'],
        'matched_expert_gold_source_records': len(matched),
        'matched_expert_gold_assertions': len({r['assertion_id'] for r in matched}),
        'projection_labels': dict(Counter(r['benchmark_projection_label'] for r in labels)),
        'supported_source_records': len(supported), 'supported_assertions': len({r['assertion_id'] for r in supported}),
        'captured_Pharos_only_gold_supported_assertions': len({r['assertion_id'] for r in pharos_supported}),
        'retained_gold_supported_assertions': len({r['assertion_id'] for r in supported if r['retained_source_edge']}),
        'whole_assertion_scientific_labels_unknown': len({r['assertion_id'] for r in labels}),
        'accuracy_percentage': None, 'whole_graph_biological_accuracy_established': False,
        'source_lineage': 'Shared CIViC knowledgebase and cited studies; separate published human claim-evidence review, not independent experiment.',
        'human_label_provenance': 'Author raw typed non-model review tags; one named human reviewer; corrected label equals processed/released final gold.',
        'version_and_exposure': '2024.05.21 manual review uses the older five-field claim format. March2025 model/references previously consumed; June2026 schema adds direction/origin/interaction. No new blind model evaluation.',
        'outside_benchmark_context_unassessed': OUTSIDE_SCOPE, 'graph_changed': False,
        'source_review_states_promoted': False, 'model_calls': 0, 'upstream_code_executed': False,
        'licenses': {'author_processing_code': 'GPL-3.0, external inspected artifact, not imported or vendored',
            'CIViC_data': 'CC0-1.0', 'evidence_excerpts': 'Inherited article-specific licenses; raw research sidecar remains private'},
        'input_files_sha256': {**pins,
            **{str(path.absolute()): sha(path) for path in [*paths.values(), plan]}},
        'retained_report_content_sha256': report['content_sha256'], 'implementation_sha256': pin,
        'limitations': ['Labels apply only to the unchanged five-field structured claim against the released evidence passage.',
            'The current full paragraph, extra clinical qualifiers and entire graph assertion remain unassessed.',
            'Unmatched records and parallel source records remain in the denominator; no absent record is labelled false.',
            'Added gold-labelled coverage is not a graph-wide accuracy gain or model-prediction improvement.'],
        'files': {p.name: sha(p) for p in out.iterdir() if p.is_file()}}
    need(sha(plan) == plan_sha256 and all(sha(path) == SOURCE_PINS[role] for role, path in paths.items())
         and all(sha(path) == expected for path, expected in pins.items())
         and sha(__file__) == pin, 'source, reference or implementation changed during application')
    result['content_sha256'] = digest(result); write_json(out/'report.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('packet', 'dispositions', 'reviews', 'raw-reviews', 'processor', 'plan', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--plan-sha256', required=True)
    p.add_argument('--disposition-report-sha256', required=True)
    a = p.parse_args()
    result = prepare(a.packet, a.dispositions, a.reviews, a.raw_reviews, a.processor,
                     a.plan, a.out, plan_sha256=a.plan_sha256,
                     disposition_report_sha256=a.disposition_report_sha256)
    print(json.dumps({k: result[k] for k in ('source_records', 'qualified_assertions',
        'matched_expert_gold_source_records', 'projection_labels', 'supported_assertions',
        'captured_Pharos_only_gold_supported_assertions', 'retained_gold_supported_assertions')}))


if __name__ == '__main__':
    main()
