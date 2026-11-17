"""Release requires real immutable prediction/method artifacts; labels stay raw."""
import io
import json
import tempfile
from pathlib import Path
import unittest

from biograph_steward.file_utils import sha
from tools.cafa_reference.evaluate_author import POLICY, verify_plan, filter_known, filter_truth, execution_subset, release_frame


class AuthorAdapterTests(unittest.TestCase):
    def test_explicit_target_scope_cannot_expand_source_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            nodes=Path(folder)/'nodes.tsv';nodes.write_text('node_id\tresolution_status\tcanonical_graph_node_present\nUniProtKB:P04637\tresolved\ttrue\nUniProtKB:Q13315\tresolved\ttrue\n')
            targets=Path(folder)/'targets.txt';targets.write_text('P04637\n')
            config={'nodes':str(nodes),'nodes_sha256':sha(nodes),'target_ids':str(targets),'target_ids_sha256':sha(targets)}
            self.assertEqual(release_frame(config)[1],{'P04637'})
            targets.write_text('P04637\nQ9UNLISTED\n');config['target_ids_sha256']=sha(targets)
            with self.assertRaises(ValueError):release_frame(config)

    def test_execution_partitions_cannot_add_methods_or_redefine_settings(self):
        c={'methods':{'first':{},'second':{}}}
        self.assertEqual(execution_subset(c,['second'],['partial_publishedaftert0']),
                         (['second'],['partial_publishedaftert0']))
        for names,settings in ((['unfrozen'],['partial']),(['first','first'],['partial']),
                               (['first'],['unreviewed_setting'])):
            with self.assertRaises(ValueError):execution_subset(c,names,settings)

    def test_future_reference_cannot_open_before_nonempty_method_freeze(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/'pred.tsv';f.write_text('P04637\tGO:0000001\t0.5\n')
            c={'policy':POLICY,'freeze_files_sha256':{},'methods':{'fixed':{'file':str(f),'sha256':sha(f)}}}
            with self.assertRaises(ValueError): verify_plan(c)
            protocol=Path(folder)/'protocol.json';protocol.write_text('{"fixed_method":true}')
            c['freeze_files_sha256']={str(protocol):sha(protocol)}
            for role in ('ontology','ia','toi'):
                c[role]=str(protocol);c[role+'_sha256']=sha(protocol)
            c['author_source']=str(Path(folder));c['author_files_sha256']={'protocol.json':sha(protocol)}
            self.assertEqual(len(verify_plan(c)),2)
            remote=Path(folder)/'remote.json'
            remote.write_text(json.dumps({'format':'biograph-steward.cafa5-remote-file-verification.v1',
                'future_GO_labels_read':False,'remote_host':'test-host','observed_at':'fixed pre-outcome time',
                'observer_code_sha256':sha(Path(__file__).with_name('remote_verify_predictions.py')),'files':{'/remote/fixed.tsv':{
                    'sha256':sha(f),'expected_sha256':sha(f),'bytes':f.stat().st_size,'expected_bytes':f.stat().st_size}}}))
            remote_config={**c,'methods':{'fixed':{'file':'/remote/fixed.tsv','sha256':sha(f)}},
                'remote_method_names':['fixed'],'remote_method_verification':{'file':str(remote),'sha256':sha(remote)}}
            self.assertIn(str(remote),verify_plan(remote_config))
            remote_config['methods']['fixed']['sha256']='0'*64
            with self.assertRaises(ValueError):verify_plan(remote_config)
            f.write_text('changed prediction')
            with self.assertRaises(ValueError):verify_plan(c)

    def test_known_filter_only_removes_nonevaluated_proteins_without_rewriting_rows(self):
        raw=b'EntryID\tterm\taspect\r\nP04637\tGO:0000001\tBPO\r\nQ13315\tGO:0000002\tBPO\r\n'
        with tempfile.TemporaryDirectory() as folder:
            src,out=Path(folder)/'source',Path(folder)/'out';src.write_bytes(raw)
            self.assertEqual(filter_known(src,out,{'P04637'}),1)
            self.assertEqual(out.read_bytes(),b'EntryID\tterm\taspect\r\nP04637\tGO:0000001\tBPO\r\n')

    def test_released_truth_uses_exact_ID_scope_and_preserves_native_rows(self):
        raw=b'EntryID\tterm\taspect\nP04637\tGO:0000001\tBPO\nQ13315\tGO:0000002\tMFO\n'
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'truth'
            r=filter_truth(io.BytesIO(raw),out,{'P04637'})
            self.assertEqual(r['raw_proteins_by_aspect'],{'BPO':1,'MFO':0,'CCO':0})
            self.assertEqual(out.read_bytes(),b'EntryID\tterm\taspect\nP04637\tGO:0000001\tBPO\n')


if __name__=='__main__':unittest.main()
