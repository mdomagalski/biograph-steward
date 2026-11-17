import copy
import unittest

from biograph_steward.client import digest
from tools.reference_accuracy.reproduction.prepare_cohort_source_eligibility import cohort_scope


def inputs():
    ids = ['P05067', 'P49768', 'P49810']
    snapshot = {'targets': [{'uniprot': p} for p in ids],
        'retrieval': {'context': {'targets': [
            {'uniprot': p, 'family': 'go', 'status': 'complete',
             'retrieved': 3, 'available': 3, 'retained': 3,
             'issues': [], 'excluded_by_scope': 0} for p in ids]}}}
    snapshot['content_sha256'] = digest(snapshot)
    graph = {'targets': [{'id': 'UniProtKB:' + p} for p in ids],
             'snapshot_sha256': snapshot['content_sha256']}
    return snapshot, graph, ['UniProtKB:' + p for p in ids]


class CohortEligibilityBindings(unittest.TestCase):
    def test_new_complete_three_protein_cohort_requires_no_99_replacement(self):
        snapshot, graph, declared = inputs()
        primary, complete = cohort_scope(snapshot, graph, declared)
        self.assertEqual(primary, set(declared))
        self.assertEqual(len(complete), 3)
        self.assertTrue(all(complete.values()))

    def test_declared_subset_cannot_silently_drop_a_primary_protein(self):
        snapshot, graph, declared = inputs()
        with self.assertRaisesRegex(ValueError, 'equal all original and current'):
            cohort_scope(snapshot, graph, declared[:-1])

    def test_resealed_incomplete_or_excluded_GO_scope_still_fails(self):
        for change in ({'retrieved': 2}, {'excluded_by_scope': 1},
                       {'issues': ['unresolved_source_count']}, {'status': 'capped'}):
            with self.subTest(change=change):
                snapshot, graph, declared = inputs()
                snapshot['retrieval']['context']['targets'][0].update(change)
                snapshot['content_sha256'] = digest({k: v for k, v in snapshot.items()
                                                     if k != 'content_sha256'})
                graph['snapshot_sha256'] = snapshot['content_sha256']
                with self.assertRaisesRegex(ValueError, 'unchanged completeness'):
                    cohort_scope(snapshot, graph, declared)

    def test_missing_or_duplicate_GO_scope_fails(self):
        for duplicate in (False, True):
            snapshot, graph, declared = inputs()
            rows = snapshot['retrieval']['context']['targets']
            rows.append(copy.deepcopy(rows[0])) if duplicate else rows.pop()
            snapshot['content_sha256'] = digest({k: v for k, v in snapshot.items()
                                                 if k != 'content_sha256'})
            graph['snapshot_sha256'] = snapshot['content_sha256']
            with self.assertRaises(ValueError):
                cohort_scope(snapshot, graph, declared)

    def test_other_current_snapshot_or_duplicate_primary_fails(self):
        for duplicate in (False, True):
            snapshot, graph, declared = inputs()
            if duplicate:
                graph['targets'].append(copy.deepcopy(graph['targets'][0]))
            else:
                graph['snapshot_sha256'] = '0' * 64
            with self.assertRaises(ValueError):
                cohort_scope(snapshot, graph, declared)


if __name__ == '__main__':
    unittest.main()
