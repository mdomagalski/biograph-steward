"""Invented native API checks; requires the pinned CAFA runtime, with no skip."""
from pathlib import Path
import tempfile
import unittest


class NativeBaselineAware(unittest.TestCase):
    def test_original_none_and_pk_scoring_keep_zero_residual_cases(self):
        import numpy as np
        from cafaeval.parser import obo_parser, update_toi, gt_parser, gt_exclude_parser, pred_parser
        from .baseline_aware import (after_top3, before_top3, matrix_sha, opportunity,
                                     selection_guards, utility)
        from .overlap import selections, score_lists
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            obo=root/'go.obo';truth=root/'truth.tsv';known=root/'known.tsv'
            forecast=root/'forecast.tsv';baseline_file=root/'baseline.tsv';ia=root/'ia.tsv';toi=root/'toi.tsv'
            obo.write_text('format-version: 1.2\n\n[Term]\nid: GO:0003674\n'
                'name: invented root\nnamespace: molecular_function\n\n'+''.join(
                '[Term]\nid: GO:100000'+str(i)+'\nname: invented '+str(i)+'\n'
                'namespace: molecular_function\nis_a: GO:0003674 ! root\n\n' for i in range(1,6)))
            truth.write_text('P00001 GO:1000003\nP00002 GO:1000001\nP00003 GO:1000005\n')
            known.write_text('P00001 GO:1000002\n')
            forecast.write_text(''.join(p+' GO:100000'+str(i)+' '+str(1.-i/10)+'\n'
                for p in ('P00001','P00002','P00003') for i in range(1,6)))
            # P2's future reference is already baseline-covered. It must still
            # contribute its ORIGINAL case and three-slot budget when scoring.
            baseline_file.write_text('P00001 GO:1000001 1\n'+''.join(
                p+' GO:100000'+str(i)+' 1\n' for p,stop in (('P00002',4),('P00003',5))
                for i in range(1,stop)))
            ia.write_text(''.join('GO:100000'+str(i)+' '+str(i)+'\n' for i in range(1,6)))
            toi.write_text(''.join('GO:100000'+str(i)+'\n' for i in range(1,6)))
            ns='molecular_function'
            ont=update_toi(obo_parser(str(obo),('is_a','part_of'),str(ia),False),str(toi))
            gt=gt_parser(str(truth),ont);exclude=gt_exclude_parser(str(known),gt,ont)
            prediction=pred_parser(str(forecast),ont,gt,'fill',None)
            baseline=pred_parser(str(baseline_file),ont,gt,'fill',None)
            before=matrix_sha(gt[ns].matrix)
            for original_exclude in (None,exclude[ns]):
                old=selections(prediction[ns],gt[ns],original_exclude,ont[ns])
                post=after_top3(old,baseline[ns])
                aware=before_top3(prediction[ns],gt[ns],original_exclude,ont[ns],baseline[ns])
                checks=selection_guards(old,post,aware,baseline[ns])
                old_summary,old_counts=score_lists(old,gt[ns],original_exclude,ont[ns])
                post_summary,post_counts=score_lists(post,gt[ns],original_exclude,ont[ns])
                aware_summary,aware_counts=score_lists(aware,gt[ns],original_exclude,ont[ns])
                self.assertTrue(checks['all_previous_baseline_absent_predictions_retained'])
                for value in (old_summary,post_summary,aware_summary):
                    self.assertEqual(value['ordinary']['eligible_proteins'],3)
                    self.assertEqual(value['IA_weighted']['eligible_proteins'],3)
                    self.assertTrue(all(x['passed'] for x in value['native_batch_point_agreement'].values()))
                np.testing.assert_array_equal(old_counts['eligible'],aware_counts['eligible'])
                np.testing.assert_array_equal(old_counts['eligible_IA_weighted'],aware_counts['eligible_IA_weighted'])
                p2=gt[ns].ids['P00002']
                self.assertTrue(aware_counts['eligible'][p2])
                self.assertEqual(aware_counts['ordinary'][p2,1],0.)
                self.assertGreater(aware_counts['ordinary'][p2,2],0.)
                residual=opportunity(gt[ns],original_exclude,ont[ns],baseline[ns],aware_counts['eligible'])
                self.assertEqual(residual['original_eligible_proteins'],3)
                self.assertEqual(residual['zero_residual_reference_proteins_retained'],1)
                value=utility(post,aware,post_counts,aware_counts)
                self.assertGreater(value['added_curator_supported_pairs'],0.)
                self.assertGreater(value['added_reference_unmatched_pairs'],0.)
                self.assertLess(value['marginal_added_curator_support_fraction'],1.)
                self.assertEqual(matrix_sha(gt[ns].matrix),before)


if __name__ == '__main__': unittest.main()
