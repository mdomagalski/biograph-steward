"""Required invented native-API checks; run in the pinned CAFA runtime only."""
from pathlib import Path
import tempfile
import unittest


class NativeOverlap(unittest.TestCase):
    def test_native_no_fill_alias_max_and_both_scoring_branches(self):
        import numpy as np
        from cafaeval.parser import obo_parser, update_toi, gt_parser, gt_exclude_parser, pred_parser
        from cafaeval.evaluation import compute_confusion_matrix
        from .overlap import selections, score_lists, pk_reproduction
        from .shortlist import score_namespace
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); obo=root/'go.obo'; truth=root/'truth.tsv'; known=root/'known.tsv'
            forecast=root/'pred.tsv'; ia=root/'ia.tsv'; toi=root/'toi.tsv'
            obo.write_text('''format-version: 1.2

[Term]
id: GO:0003674
name: invented root
namespace: molecular_function

[Term]
id: GO:1000001
name: invented parent
namespace: molecular_function
is_a: GO:0003674 ! root

[Term]
id: GO:1000002
alt_id: GO:1999992
name: invented child
namespace: molecular_function
is_a: GO:1000001 ! parent

[Term]
id: GO:1000003
name: invented other
namespace: molecular_function
is_a: GO:0003674 ! root
''')
            truth.write_text('P00001 GO:1000002\nP00002 GO:1000003\n')
            known.write_text('P00001 GO:1000001\n')
            forecast.write_text('P00001 GO:1999992 .4\nP00001 GO:1000002 .8\nP00002 GO:1000003 .7\n')
            ia.write_text('GO:1000001 1\nGO:1000002 2\nGO:1000003 1\n')
            toi.write_text('GO:1000001\nGO:1000002\nGO:1000003\n')
            ns='molecular_function'; ont=update_toi(obo_parser(str(obo),('is_a','part_of'),str(ia),False),str(toi))
            gt=gt_parser(str(truth),ont); exclude=gt_exclude_parser(str(known),gt,ont)
            literal=pred_parser(str(forecast),ont,gt,None,None)
            filled=pred_parser(str(forecast),ont,gt,'fill',None)
            parent=ont[ns].terms_dict['GO:1000001']['index']; child=ont[ns].terms_dict['GO:1000002']['index']
            self.assertEqual(literal[ns].matrix[0,child],.8)
            self.assertEqual(literal[ns].matrix[0,parent],0.)
            self.assertEqual(filled[ns].matrix[0,parent],.8)
            for mask in (None,exclude[ns]):
                selected=selections(filled[ns],gt[ns],mask,ont[ns])
                summary,counts=score_lists(selected,gt[ns],mask,ont[ns])
                if mask is not None:
                    previous,_=score_namespace(filled[ns],gt[ns],mask,ont[ns]);pk_reproduction(summary,previous)
                else:
                    binary=np.zeros_like(gt[ns].matrix,dtype=bool)
                    for i,values in enumerate(selected):binary[i,values]=True
                    for label,t,weights in [('ordinary',ont[ns].toi,None),('IA_weighted',ont[ns].toi_ia,ont[ns].ia)]:
                        g=gt[ns].matrix[:,t];n=g.sum(1) if weights is None else (g*weights[t]).sum(1)
                        native=compute_confusion_matrix(np.asarray([.5]),g,binary[:,t],t,n,weights)[0]
                        np.testing.assert_allclose(counts[label].sum(0),native,rtol=1e-12,atol=1e-12)
                self.assertTrue(all(x['passed'] for x in summary['native_batch_point_agreement'].values()))


if __name__ == '__main__': unittest.main()
