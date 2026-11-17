"""Invented no-exclusion native fixtures, including the original BPO default."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


@unittest.skipUnless(importlib.util.find_spec('cafaeval'), 'optional pinned native evaluator required')
class NativeNamespace(unittest.TestCase):
    def test_all_native_namespaces_reproduce_full_point_curves(self):
        import numpy as np
        from cafaeval.evaluation import cafa_eval
        from tools.cafa_nonpk.counts import worker, sha
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);pred_dir=root/'pred';pred_dir.mkdir()
            obo=root/'go.obo';truth=root/'truth.tsv';ia=root/'ia.tsv';toi=root/'toi.tsv'
            namespaces=['biological_process','molecular_function','cellular_component']
            roots=['GO:0008150','GO:0003674','GO:0005575']
            blocks=['format-version: 1.2\n'];terms=[];labels=[];forecasts=[]
            for i,(ns,r) in enumerate(zip(namespaces,roots)):
                blocks.append('[Term]\nid: '+r+'\nname: invented root\nnamespace: '+ns+'\n')
                for j in (1,2):
                    t='GO:'+str(1000000+i*10+j);terms.append(t)
                    blocks.append('[Term]\nid: '+t+'\nname: invented child\nnamespace: '+ns+'\nis_a: '+r+' ! root\n')
                    labels.append('P0000'+str(j)+' '+t)
                    for p in (1,2):forecasts.append('P0000'+str(p)+' '+t+' '+('.8' if p==j else '.2'))
            obo.write_text('\n'.join(blocks));truth.write_text('\n'.join(labels)+'\n')
            ia.write_text('\n'.join(t+' 1' for t in terms)+'\n');toi.write_text('\n'.join(terms)+'\n')
            prediction=pred_dir/'invented.tsv';prediction.write_text('\n'.join(forecasts)+'\n')
            call=dict(obo_file=str(obo),pred_dir=str(pred_dir),gt_file=str(truth),ia=str(ia),
                      toi_file=str(toi),exclude=None,prop='fill',norm='cafa',th_step=.001,no_orphans=True,n_cpu=1)
            df,_=cafa_eval(**call);curve=root/'exact.tsv';df.to_csv(curve,sep='\t',float_format='%.17g')
            outcomes=root/'native_outcomes.json';outcomes.write_text(json.dumps({'namespaces':{
                ns:dict(author_recognized_target_IDs=2,eligible_proteins=2,IA_eligible_proteins=2) for ns in namespaces}}))
            for i,ns in enumerate(namespaces):
                job={'author_call':call,'prediction':str(prediction),'exact_point_curves':str(curve),
                     'native_outcomes':str(outcomes),'output_dir':str(root/ns),'input_files_sha256':{
                         str(p):sha(p) for p in (obo,truth,ia,toi,prediction,curve,outcomes)}}
                if i:job['namespace']=ns
                file=root/(ns+'.json');file.write_text(json.dumps(job));worker(file)
                agreement=json.loads((root/ns/'agreement.json').read_text())
                self.assertEqual(agreement['namespace'],ns)
                self.assertTrue(agreement['author_point_agreement_passed'])
                self.assertLessEqual(agreement['checks']['declared_ordinary_and_IA_micro_F_curves']['max_absolute_curve_difference'],1e-12)
                with np.load(root/ns/'counts.npz',allow_pickle=False) as data:
                    self.assertEqual(data['ordinary'].shape,(2,999,6))


if __name__=='__main__':unittest.main()
