"""Author-metric consistency diagnostic across the complete native BC8 table.

This does not establish the released weights' training membership. Native
decoded outputs are joined in author row order and scored with author helpers
only after the complete primary prediction seal exists.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import zipfile

from biograph_steward.client import digest,write_json,utcnow
from biograph_steward.file_utils import sha
from .prepare import need,DATA_SHA
from .predict import load_frame
from .evaluate import sealed,code_pins
from .secondary import primary_boundary

LEVELS=('pair','pair+novelty','relation','relation+novelty','relation+direction','all')
PAPER_MEAN_F1={'pair':.7534,'pair+novelty':.5726,'relation':.5606,
               'relation+novelty':.4266,'relation+direction':.4862,'all':.3702}


def projection(row,level):
    """Same tuple levels as the authors' run_gen_summary.load_pred_labels.

    Labels are the already saved native convert_to_biored_label outputs; no
    synthetic probabilities, alternate decoding threshold or model fitting.
    """
    rel,nov,direction=row['relation'],row['novelty'],row['direction']
    pair='Association' if rel!='None' else 'None'
    return {'pair':(pair,'_'),'pair+novelty':(pair,nov),'relation':(rel,'_'),
            'relation+novelty':(rel,nov),'relation+direction':(rel,direction),
            'all':(rel,nov,direction)}[level]


def read_slice(frame_path,prediction_path):
    frame,cases=load_frame(frame_path);root=Path(prediction_path);report=sealed(root/'execution.json')
    need(report['status']=='completed' and report['completed_cases']==len(cases)
         and report['frame_content_sha256']==frame['content_sha256'], 'complete every diagnostic prediction before outcomes open.')
    need(sha(root/'predictions.jsonl')==report['predictions_sha256'],'diagnostic predictions changed.')
    rows=[json.loads(line) for line in (root/'predictions.jsonl').read_text().splitlines()]
    need([r['case_id'] for r in rows]==[c['id'] for c in cases],'diagnostic candidate order differs.')
    return frame,cases,report,rows


def score(gene_frame,gene_predictions,remaining_frame,remaining_predictions,predeclaration,
          analysis_freeze,primary_prediction_freeze,author_source,data_zip,output):
    output=Path(output);need(not output.exists(),'choose a new artifact diagnostic output.')
    pre=sealed(predeclaration);analysis=sealed(analysis_freeze)
    need(analysis['analysis_code_sha256']==sha(__file__) and analysis['shared_code_sha256']==code_pins()
         and analysis['predeclaration_content_sha256']==pre['content_sha256'],'diagnostic method changed.')
    primary=primary_boundary({'primary_cases':128,'primary_frame_content_sha256':analysis['primary_frame_content_sha256']},
                             primary_prediction_freeze)
    gf,gc,gr,gp=read_slice(gene_frame,gene_predictions)
    rf,rc,rr,rp=read_slice(remaining_frame,remaining_predictions)
    need(len(gc)==pre['gene_rows_already_frozen'] and len(rc)==pre['new_rows']
         and rf['content_sha256']==pre['remaining_frame_content_sha256'], 'diagnostic split inventory differs.')
    need(gf['model_files_sha256']==rf['model_files_sha256']==gr['model_files_sha256']==rr['model_files_sha256']
         and gr['implementation_sha256']==rr['implementation_sha256']==code_pins()['tools/biored_agent/predict.py'],
         'diagnostic used a different released model or decoder implementation.')
    merged={}
    for cases,rows in [(gc,gp),(rc,rp)]:
        for case,row in zip(cases,rows):
            line=case['author_tsv_line'];need(line not in merged,'duplicate native author row in diagnostic union.')
            merged[line]=(case,row)
    need(set(merged)==set(range(1,pre['all_native_rows']+1)),'diagnostic must cover every native row exactly once.')
    source=Path(author_source)/'run_gen_summary.py'
    need(sha(source)==gf['author_code_files_sha256']['run_gen_summary.py'],'author metric helper changed.')
    need(sha(data_zip)==DATA_SHA,'native reference archive changed.')
    # First reference opening occurs only after all primary/slice/method checks.
    opened=utcnow()
    with zipfile.ZipFile(data_zip) as archive:raw=archive.read(gf['tsv_member'])
    need(sha_bytes(raw)==gf['tsv_member_sha256'] and len(raw.splitlines())==len(merged),'native metric reference table differs.')
    ordered=[merged[i] for i in range(1,len(merged)+1)]
    for (case,_),line in zip(ordered,raw.splitlines()):
        need(line.split(b'\t',6)[:6]==[p.encode() for p in case['masked_tsv'].split('\t')[:6]],'native reference input join differs.')
    spec=importlib.util.spec_from_file_location('biograph_pinned_author_summary',source)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    predictions=[row for _,row in ordered];result={}
    with tempfile.TemporaryDirectory(prefix='biograph_author_metrics_') as temp:
        reference=Path(temp)/'native_bc8.tsv';reference.write_bytes(raw)
        for level in LEVELS:
            gold=helper.load_gold_labels(str(reference),level=level)
            result[level]=helper.eval([projection(row,level) for row in predictions],gold)
    report={'format':'biograph-steward.biored-released-artifact-consistency.v1','created_at':utcnow(),
        'labels_first_opened_at':opened,'primary_prediction_freeze_content_sha256':primary['content_sha256'],
        'predeclaration_content_sha256':pre['content_sha256'],'analysis_freeze_content_sha256':analysis['content_sha256'],
        'gene_execution_content_sha256':gr['content_sha256'],'remaining_execution_content_sha256':rr['content_sha256'],
        'native_candidate_rows':len(merged),'native_candidate_publications':len({c['pmid'] for c,_ in ordered}),
        'released_corpus_abstracts':400,'source_metric_helper_sha256':sha(source),
        'author_metric_reference_agreement':result,'paper_reported_10_seed_mean_F1':PAPER_MEAN_F1,
        'single_checkpoint_minus_paper_mean_F1':{key:result[key]['f1']-PAPER_MEAN_F1[key] for key in LEVELS},
        'checkpoint_training_membership_independently_audited':False,
        'interpretation':'Author-intended BC8 reference-agreement reproduction diagnostic. One released checkpoint versus paper seed means is not an exact numerical reproduction or a test of fine-tuning independence.',
        'scope':'All author processed candidate rows; one of the400 source abstracts has no processed candidate row. Gold entities supplied; no end-to-end NER or canonical human-protein mapping evaluation.',
        'decoding':'Unchanged native convert_to_biored_label saved outputs; author load_gold_labels and eval helpers used for all six metric levels. No alternate threshold or synthetic score vector.',
        'source_graph_changes':0,'additional_LLM_requests':0}
    report['content_sha256']=digest(report);output.mkdir(parents=True);write_json(output/'report.json',report);return report


def sha_bytes(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('gene-frame','gene-predictions','remaining-frame','remaining-predictions','predeclaration',
                 'analysis-freeze','primary-prediction-freeze','author-source','data-zip','output'):
        parser.add_argument('--'+name,required=True)
    a=parser.parse_args();r=score(a.gene_frame,a.gene_predictions,a.remaining_frame,a.remaining_predictions,
        a.predeclaration,a.analysis_freeze,a.primary_prediction_freeze,a.author_source,a.data_zip,a.output)
    print(json.dumps({k:r[k] for k in ('native_candidate_rows','content_sha256')},indent=2))


if __name__=='__main__':main()
