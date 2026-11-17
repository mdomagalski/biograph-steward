"""Run the released BioREDirect tool on sealed, relation-masked native inputs.

Model, tokenizer, input chunks and label decoding come from the official author
artifact. This thin runner adds provenance and incremental outputs, and selects
one explicit device. No labels, source acquisition or parameter fitting occur.
"""
from __future__ import annotations
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
import time

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha
from .prepare import FORMAT, RELATIONS, need


def load_frame(folder):
    folder = Path(folder)
    frame = json.loads((folder/'frame.json').read_text())
    need(frame.get('format') == FORMAT and digest({k:v for k,v in frame.items() if k!='content_sha256'}) == frame.get('content_sha256'),
         'frame seal differs.')
    need(sha(folder/'cases.json') == frame['cases_sha256'] and sha(folder/'masked.tsv') == frame['masked_tsv_sha256'],
         'frame input files differ.')
    cases = json.loads((folder/'cases.json').read_text())
    need(len(cases) == frame['selected_pairs'] and len({r['id'] for r in cases}) == len(cases), 'case inventory differs.')
    rows = (folder/'masked.tsv').read_text().splitlines()
    need(rows == [r['masked_tsv'] for r in cases] and all(row.split('\t')[-3:] == ['None']*3 for row in rows),
         'native inference labels must all be masked.')
    return frame, cases


def predict(frame_dir, model_dir, author_source, output, *, device='cpu', batch_size=2, threads=4):
    frame_dir, model_dir, author_source, output = map(Path,(frame_dir,model_dir,author_source,output))
    frame,cases = load_frame(frame_dir)
    need(device in {'cpu','cuda','mps'} and type(batch_size) is int and 1<=batch_size<=16, 'invalid explicit device/batch.')
    need(not output.exists(), 'choose a new prediction output.')
    need({p.name:sha(p) for p in model_dir.iterdir() if p.is_file()} == frame['model_files_sha256'], 'model files changed.')
    need({p.relative_to(author_source).as_posix():sha(p) for p in author_source.rglob('*.py')} == frame['author_code_files_sha256'], 'author source changed.')
    sys.path.insert(0,str(author_source.resolve()))
    import torch
    from torch.utils.data import DataLoader
    from transformers import BertTokenizer
    from models import BioREDirect
    from data_processor import BioREDDataset
    from run_exp import custom_collate_fn
    from evaluation import convert_to_biored_label
    torch.set_num_threads(threads)
    torch.manual_seed(1111)
    if device=='cuda': need(torch.cuda.is_available(), 'CUDA unavailable; no fallback.')
    if device=='mps': need(torch.backends.mps.is_available(), 'MPS unavailable; no fallback.')
    runtime={k:importlib.metadata.version(k) for k in ('torch','transformers','numpy','pandas')}
    need(runtime['transformers']=='4.55.0' and runtime['torch'].split('+')[0]=='2.6.0', 'unqualified tool runtime.')
    output.mkdir(parents=True)
    header={'format':'biograph-steward.biored-specialist-execution.v1','created_at':utcnow(),
        'frame_content_sha256':frame['content_sha256'],'runtime':runtime,'device':device,
        'batch_size':batch_size,'threads':threads,'implementation_sha256':sha(__file__),
        'source_fetches':0,'training_performed':False,'outcome_access':'masked only',
        'author_implementation_sha256':frame['author_code_files_sha256'],
        'model_files_sha256':frame['model_files_sha256'],'status':'running'}
    write_json(output/'execution.json',header)
    started=time.perf_counter()
    tokenizer=BertTokenizer.from_pretrained(str(model_dir),local_files_only=True)
    model=BioREDirect.load_model(str(model_dir))
    # Author load_model sets CPU after an initial MPS selection, whereas its
    # inference function may put batches on MPS. Bind both explicitly here.
    model.to(torch.device(device));model.device=torch.device(device);model.eval()
    dataset=BioREDDataset(str(frame_dir/'masked.tsv'),tokenizer,max_seq_len=512,
        soft_prompt_len=model.soft_prompt_len,use_single_chunk=model.use_single_chunk)
    need(dataset.get_labels('relation')==list(RELATIONS), 'native relation enum changed.')
    loader=DataLoader(dataset,batch_size=batch_size,shuffle=False,collate_fn=custom_collate_fn,
                      num_workers=0,pin_memory=device=='cuda')
    cursor=0
    with (output/'predictions.jsonl').open('w') as stream,torch.inference_mode():
        for batch in loader:
            before=time.perf_counter()
            kwargs={k:v.to(device) for k,v in batch.items() if k in ('input_ids','attention_mask',
                'pair_prompt_ids','relation_token_index','direction_token_index','novelty_token_index')}
            rel,nov,dire=model(**kwargs)
            vectors=[torch.sigmoid(x).cpu().numpy() for x in (rel,nov,dire)]
            decoded=convert_to_biored_label(*vectors,dataset.get_labels('relation'),
                         dataset.get_labels('novelty'),dataset.get_labels('direction'))
            for j,indices in enumerate(decoded):
                case=cases[cursor];need(str(batch['pmid'][j])==case['pmid'],'native row order changed.')
                row={'case_id':case['id'],'pmid':case['pmid'],'relation':RELATIONS[indices[0]],
                    'novelty':dataset.get_labels('novelty')[indices[1]],
                    'direction':dataset.get_labels('direction')[indices[2]],
                    'relation_sigmoid_scores':dict(zip(RELATIONS,map(float,vectors[0][j]))),
                    'probabilities_calibrated':False,'source_relative':True,'biologically_validated':False}
                stream.write(json.dumps(row,allow_nan=False)+'\n');stream.flush();cursor+=1
            print(json.dumps({'completed':cursor,'total':len(cases),'batch_seconds':round(time.perf_counter()-before,3)}),flush=True)
    need(cursor==len(cases),'incomplete specialist predictions.')
    report={**header,'status':'completed','completed_cases':cursor,'elapsed_seconds':time.perf_counter()-started,
        'predictions_sha256':sha(output/'predictions.jsonl')}
    report['content_sha256']=digest(report);write_json(output/'execution.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('frame','model','author-source','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--device',choices=('cpu','cuda','mps'),default='cpu')
    p.add_argument('--batch-size',type=int,default=2);p.add_argument('--threads',type=int,default=4)
    a=p.parse_args();r=predict(a.frame,a.model,a.author_source,a.output,device=a.device,batch_size=a.batch_size,threads=a.threads)
    print(json.dumps({k:r[k] for k in ('status','completed_cases','elapsed_seconds','content_sha256')},indent=2))


if __name__=='__main__':main()
