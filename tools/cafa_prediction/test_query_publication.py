import json
from pathlib import Path
import shutil
import tempfile
import unittest

from biograph_steward.function_context import digest,sha
from tools.cafa_prediction.query_publication import load_equivalence_proof


class RelocatedProofTests(unittest.TestCase):
    def fixture(self,folder):
        protocol={'input_pins':{'source_protocol':{'sha256':'a'*64}}}
        protocol['content_sha256']=digest(protocol)
        p=folder/'protocol.json';p.write_text(json.dumps(protocol))
        report={'format':'biograph-steward.exact-onehop-LocalPlus-equivalence.v1.results',
            'all_query_scores_bitwise_equal':True,'accuracy_measured':False,
            'future_reference_labels_read':False,'prediction_source_or_graph_changed':False,
            'protocol_content_sha256':protocol['content_sha256'],
            'files':{'protocol.json':{'bytes':p.stat().st_size,'sha256':sha(p)}}}
        report['content_sha256']=digest(report)
        r=folder/'report.json';r.write_text(json.dumps(report));return r

    def test_proof_relocates_without_a_hardcoded_run_directory(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            report=self.fixture(Path(a));expected=sha(report)
            shutil.copy2(report,Path(b)/'report.json');shutil.copy2(Path(a)/'protocol.json',Path(b)/'protocol.json')
            r,p=load_equivalence_proof(Path(b)/'report.json',expected,'a'*64)
            self.assertEqual(r.parent,Path(b).resolve());self.assertEqual(p.parent,Path(b).resolve())
            with self.assertRaises(ValueError):load_equivalence_proof(r,expected,'b'*64)

    def test_hash_tampering_or_success_flag_without_protocol_proof_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=self.fixture(Path(tmp));expected=sha(report)
            (Path(tmp)/'protocol.json').write_text('{}')
            with self.assertRaises(ValueError):load_equivalence_proof(report,expected,'a'*64)
            report.write_text(report.read_text()+' ')
            with self.assertRaises(ValueError):load_equivalence_proof(report,expected,'a'*64)


if __name__=='__main__':unittest.main()
