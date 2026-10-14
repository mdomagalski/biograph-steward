"""Scientific guardrails for preparing labels, not tests of model accuracy."""
from copy import deepcopy
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from biograph_steward.benchmark import save_audit
from biograph_steward.client import digest
from biograph_steward.demo import demo_snapshot
from biograph_steward.graph import build_graph, save_run
from biograph_steward.__main__ import main


def resign(snapshot):
    snapshot.pop('content_sha256', None)
    snapshot['content_sha256'] = digest(snapshot)
    return snapshot


def exact_record(snapshot):
    return next(r for t in snapshot['targets'] for r in t.get('diseaseAssociationDetails', [])
                if r.get('name') == snapshot['disease']['name'])


class BenchmarkTests(unittest.TestCase):
    def test_evidence_is_grouped_not_used_as_independent_labels(self):
        g = build_graph(demo_snapshot()); a = g['benchmark_readiness']
        self.assertEqual(a['counts']['unique_reported_pairs'], 5)
        self.assertGreater(a['counts']['association_records'], 5)
        self.assertEqual(a['counts']['other_disease_records'], 1)
        self.assertEqual(a['counts']['reviewed_positive_labels'], 0)
        self.assertEqual(a['counts']['reviewed_negative_labels'], 0)
        self.assertEqual(a['status'], 'not_ready')
        self.assertIn('synthetic_data', [x['code'] for x in a['required_actions']])

    def test_every_association_edge_is_accounted_for(self):
        g = build_graph(demo_snapshot()); a = g['benchmark_readiness']
        ids = {e['id'] for e in g['edges'] if e['predicate'] == 'biolink:associated_with'}
        listed = {eid for r in a['pairs'] for eid in r['evidence_edge_ids']}
        self.assertEqual(ids, listed | set(a['other_disease_edge_ids']))
        self.assertFalse(listed & set(a['other_disease_edge_ids']))
        for row in a['pairs']:
            candidates = set(row['review_candidate_edge_ids'])
            excluded = {e['edge_id'] for e in row['excluded_records']}
            self.assertFalse(candidates & excluded)
            self.assertEqual(candidates | excluded, set(row['evidence_edge_ids']))

    def test_duplicate_evidence_cannot_inflate_pair_count(self):
        s = demo_snapshot(); before = build_graph(s)['benchmark_readiness']['counts']
        s['targets'][0]['diseaseAssociationDetails'].append(deepcopy(exact_record(s)))
        after = build_graph(resign(s))['benchmark_readiness']['counts']
        self.assertEqual(before['unique_reported_pairs'], after['unique_reported_pairs'])
        self.assertEqual(before['association_records'], after['association_records'])

    def test_count_summary_is_not_a_citation(self):
        s = demo_snapshot()
        for t in s['targets']:
            for r in t.get('diseaseAssociationDetails', []):
                r['evidence'] = '2 PubMed IDs; 1 SNPs'; r['reference'] = None
        a = build_graph(resign(s))['benchmark_readiness']
        self.assertEqual(a['counts']['records_with_explicit_citation'], 0)
        self.assertIn('citation_recovery', [x['code'] for x in a['required_actions']])

    def test_explicit_citation_is_not_scientific_validation(self):
        s = demo_snapshot(); exact_record(s)['reference'] = 'PMID:123456'
        a = build_graph(resign(s))['benchmark_readiness']
        self.assertGreaterEqual(a['counts']['records_with_explicit_citation'], 1)
        self.assertEqual(a['counts']['reviewed_positive_labels'], 0)

    def test_missing_context_is_not_promoted(self):
        s = demo_snapshot(); exact_record(s)['name'] = None
        a = build_graph(resign(s))['benchmark_readiness']
        self.assertGreater(a['excluded_record_reason_counts']['explicit_disease_context_missing'], 0)

    def test_mismatched_context_and_membership_not_labels(self):
        a = build_graph(demo_snapshot())['benchmark_readiness']
        reasons = a['excluded_record_reason_counts']
        self.assertIn('evidence_disease_name_differs_from_selected_term', reasons)
        self.assertIn('membership_is_not_detailed_evidence', reasons)
        self.assertEqual(a['counts']['reviewed_negative_labels'], 0)

    def test_empty_extract_stays_not_ready(self):
        s = demo_snapshot(); s['targets'] = []
        a = build_graph(resign(s))['benchmark_readiness']
        self.assertEqual(a['counts']['unique_reported_pairs'], 0)
        self.assertIn('no_associations', [x['code'] for x in a['required_actions']])

    def test_truncation_remains_visible(self):
        s = demo_snapshot(); s['retrieval']['truncated'] = True
        a = build_graph(resign(s))['benchmark_readiness']
        self.assertIn('truncated_retrieval', [x['code'] for x in a['required_actions']])

    def test_audit_does_not_mutate_snapshot(self):
        s = demo_snapshot(); original = deepcopy(s)
        self.assertEqual(build_graph(s)['benchmark_readiness'], build_graph(s)['benchmark_readiness'])
        self.assertEqual(s, original)

    def test_integrity_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audit'; s = demo_snapshot()
            save_audit(s, path)
            with self.assertRaisesRegex(ValueError, 'not empty'): save_audit(s, path)
            s['targets'] = []
            with self.assertRaisesRegex(ValueError, 'integrity'): save_audit(s, Path(tmp) / 'bad')
            self.assertFalse((Path(tmp) / 'bad').exists())

    def test_cli_and_run_export_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); save_run(demo_snapshot(), root / 'run')
            with redirect_stdout(StringIO()):
                result = main(['audit', '--snapshot', str(root / 'run/snapshot.json'), '--out', str(root / 'audit')])
            self.assertEqual(result, 0)
            self.assertEqual((root / 'run/benchmark_readiness.json').read_text(),
                             (root / 'audit/benchmark_readiness.json').read_text())
            with (root / 'audit/review_candidates.tsv').open() as f:
                rows = list(csv.DictReader(f, delimiter='\t'))
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(r['review_status'] == 'pending' for r in rows))

    def test_cli_invalid_json_fails_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); (p / 'bad.json').write_text('{')
            with redirect_stderr(StringIO()):
                self.assertEqual(main(['audit', '--snapshot', str(p / 'bad.json'), '--out', str(p / 'out')]), 1)
            self.assertFalse((p / 'out').exists())


if __name__ == '__main__':
    unittest.main()
