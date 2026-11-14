"""Invented gzip members verify byte-preserving common-evaluator intake."""
import gzip
from pathlib import Path
import tempfile
import unittest
from .archive import fingerprints
from .native_jobs import merge_aspects
from .scores import AUTHOR_ASPECT_ORDER


class NativeJobTests(unittest.TestCase):
    def test_gzip_members_preserve_all_aspects_and_zero_scores(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);files={};expected=[]
            for i,aspect in enumerate(AUTHOR_ASPECT_ORDER):
                name=f'primary_deepgose_{aspect}.tsv.gz';row=f'Q00001\tGO:000000{i+1}\t0\n'
                with gzip.open(folder/name,'wt') as stream:stream.write(row)
                files[name]=fingerprints(folder/name);expected.append(row)
            output=folder/'joined.tsv.gz'
            merge_aspects(folder,{'files':files},'primary',output)
            with gzip.open(output,'rt') as stream:self.assertEqual(stream.read(),''.join(expected))
            self.assertEqual(output.stat().st_size,sum((folder/n).stat().st_size for n in files))

    def test_modified_aspect_cannot_enter_native_evaluator(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);files={}
            for aspect in AUTHOR_ASPECT_ORDER:
                name=f'reserved_deepgose_{aspect}.tsv.gz'
                with gzip.open(folder/name,'wt') as stream:stream.write('invented')
                files[name]=fingerprints(folder/name)
            (folder/next(iter(files))).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'differs'):
                merge_aspects(folder,{'files':files},'reserved',folder/'rejected.tsv.gz')


class ExistingParentLayoutTests(unittest.TestCase):
    def test_prepared_jobs_use_actual_unchanged_adapters_driver(self):
        import json
        from biograph_steward.client import write_json
        from .archive import sealed
        from .native_jobs import prepare
        from .run import FORMAT, PARAMETERS
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);base=root/'author-evaluation-v1';base.mkdir()
            (base/'adapters').mkdir();driver=base/'adapters/remote_author.py'
            driver.write_text('# invented existing native execution adapter\n')
            self.assertFalse((base/'remote_author.py').exists())
            for frame,parent in (('primary','primary_BPO_point_jobs_v2.json'),('reserved','reserved_BPO_point_jobs_v1.json')):
                write_json(base/parent,{'format':'biograph-steward.cafa5-remote-author-jobs.v1','input_files_sha256':{}})
                release=base/(frame+'-reference-v1');release.mkdir()
                for name in ('partial.tsv','known_t0_frame.tsv','report.json'):
                    (release/name).write_text('invented existing reference placeholder, never parsed\n')
            frozen=root/'frozen';frozen.mkdir();protocol=sealed({'format':FORMAT+'.freeze','parameters':PARAMETERS,
                'target_counts':{'primary':1294,'reserved':4806},'all_six_cohort_aspect_outcomes_required':True,
                'inputs':{'evaluation_plan':{'sha256':'invented exact frozen plan SHA'}}})
            write_json(frozen/'protocol.json',protocol);expected=fingerprints(frozen/'protocol.json')['sha256']
            predictions=root/'predictions';predictions.mkdir();files={}
            for frame in ('primary','reserved'):
                for i,aspect in enumerate(AUTHOR_ASPECT_ORDER):
                    name=f'{frame}_deepgose_{aspect}.tsv.gz'
                    with gzip.open(predictions/name,'wt') as stream:stream.write(f'Q00001\tGO:000000{i+1}\t0\n')
                    files[name]=fingerprints(predictions/name)
            manifest=sealed({'format':FORMAT+'.predictions','protocol_file_sha256':expected,
                'protocol_content_sha256':protocol['content_sha256'],'all_evaluation_denominators_retained':True,
                'development_exposed_reference_reuse':True,'new_reference_labels_read':False,'files':files})
            write_json(predictions/'predictions.json',manifest)
            value=prepare(base,frozen,expected,predictions,fingerprints(predictions/'predictions.json')['sha256'],root/'jobs')
            self.assertEqual(value['native_driver'],str(driver))
            self.assertEqual(value['native_driver_sha256'],fingerprints(driver)['sha256'])
            for spec in value['jobs'].values():
                job=json.loads(Path(spec['config']).read_text())
                self.assertEqual(job['input_files_sha256'][str(driver)],value['native_driver_sha256'])


if __name__=='__main__':unittest.main()
