"""Display metadata binds to the existing decision report, outside graph basis."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest
from biograph_steward.workspaces import qualification_summary


class QualificationDisplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.package = self.folder / 'source_retained_package'
        self.package.mkdir()
        # Invented routing fixture, not real biological evidence.
        self.rows = [dict(decision='keep', edge_id='k', reason='retained'),
                     dict(decision='prune', edge_id='p', reason='recorded synthetic qualification'),
                     dict(decision='abstain', edge_id='a', reason='unresolved')]
        raw = ('\n'.join(json.dumps(row) for row in self.rows)+'\n').encode()
        (self.package/'edge_dispositions.jsonl').write_bytes(raw)
        self.report = {'counts': {'keep':1, 'prune':1, 'abstain':1},
                       'files': {'edge_dispositions.jsonl':hashlib.sha256(raw).hexdigest()}}
        self.seal()

    def seal(self):
        self.report['content_sha256'] = digest({k:v for k,v in self.report.items() if k!='content_sha256'})
        (self.package/'report.json').write_text(json.dumps(self.report))
        self.graph = {'qualified_view': {'disposition_report_content_sha256':self.report['content_sha256'],
                                        'baseline_evidence_edges':3, 'retained_evidence_edges':2}}

    def test_displays_exact_reasons_and_counts_without_mutating_graph(self):
        before = deepcopy(self.graph)
        result = qualification_summary(self.folder,self.graph)
        self.assertEqual(result['excluded_records'],1)
        self.assertEqual(result['abstained_records'],1)
        self.assertEqual(result['reason_groups'],[{'decision':'prune','reason':self.rows[1]['reason'],'records':1}])
        self.assertEqual(self.graph,before)
        self.assertNotIn('obsolete',json.dumps(result))

    def test_ordinary_graph_does_not_read_qualification_files(self):
        self.assertIsNone(qualification_summary(self.folder/'nonexistent',{}))

    def test_changed_ledger_is_rejected(self):
        with (self.package/'edge_dispositions.jsonl').open('ab') as stream:
            stream.write(b'\n')
        with self.assertRaisesRegex(ValueError,'ledger bytes changed'):
            qualification_summary(self.folder,self.graph)

    def test_resealed_different_report_does_not_match_loaded_graph(self):
        old = deepcopy(self.graph)
        self.report['note'] = 'changed'
        self.seal()
        with self.assertRaisesRegex(ValueError,'does not match'):
            qualification_summary(self.folder,old)

    def test_correctly_sealed_but_inconsistent_counts_are_rejected(self):
        self.report['counts']['keep'] = 2
        self.seal()
        with self.assertRaisesRegex(ValueError,'counts differ'):
            qualification_summary(self.folder,self.graph)

    def test_linked_ledger_is_rejected(self):
        ledger=self.package/'edge_dispositions.jsonl'
        ledger.rename(self.folder/'ledger.jsonl')
        ledger.symlink_to(self.folder/'ledger.jsonl')
        with self.assertRaisesRegex(ValueError,'linked source'):
            qualification_summary(self.folder,self.graph)


if __name__=='__main__':
    unittest.main()
