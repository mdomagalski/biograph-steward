"""Execute the already-declared K3/network 50:50 controls without a large SQL DB.

Exact native sequence scores are canonically resolved using the pinned author
ontology map. Graph scores already use the same primary term identities. This
is the same fixed convex arithmetic as the earlier score-fusion adaptation;
it is not fitting, a negative-label construction or a DeepGOPlus replication.
"""
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re

ARMS={'prott5_cosine3_full_fss_half':'global_full_allseeds_fss',
      'prott5_cosine3_full_local_half':'global_full_allseeds_local'}


def need(ok,message):
    if not ok:raise ValueError('Reserved fixed fusion: '+message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def sealed(path):
    d=json.loads(Path(path).read_text());need(d.get('content_sha256')==digest({k:v for k,v in d.items() if k!='content_sha256'}),'content seal differs: '+str(path));return d


def load_sequence(path,targets,canonical):
    scores={};rows=outside=resolved=0
    with gzip.open(path,'rt') as f:
        for raw in f:
            p,t,s=raw.rstrip('\n').split('\t');v=float(s);rows+=1
            need(p in targets and re.fullmatch(r'GO:[0-9]{7}',t) and math.isfinite(v) and 0<=v<=1+1e-10,'invalid qualified sequence score.')
            terms=canonical.get(t,[]);outside+=not bool(terms);resolved+=bool(terms) and terms!=[t]
            for term in terms:
                key=(p,term);scores[key]=max(v,scores.get(key,0.))
    return scores,{'native_rows':rows,'canonical_positive_pairs':sum(v>0 for v in scores.values()),'outside_ontology_rows':outside,'alternative_ID_rows':resolved}


def mix(model,sequence,targets,canonical,output):
    remaining=dict(sequence);seen_terms=set();seen_proteins=set();current=None;count=0;modelrows=0
    with gzip.open(model,'rt') as source,gzip.GzipFile(filename=str(output),mode='wb',mtime=0) as sink:
        for raw in source:
            p,t,s=raw.rstrip('\n').split('\t');v=float(s);modelrows+=1
            need(p in targets and canonical.get(t)==[t] and math.isfinite(v) and 0<v<=1+1e-10,'model row is not an exact canonical qualified prediction.')
            if t!=current:
                need(t not in seen_terms,'model term repeats noncontiguously; no implicit duplicate averaging.')
                seen_terms.add(t);seen_proteins=set();current=t
            need(p not in seen_proteins,'duplicate model protein/term; no implicit score repair.');seen_proteins.add(p)
            value=.5*v+.5*remaining.pop((p,t),0.)
            need(0<value<=1+1e-10,'invalid convex output.')
            sink.write((p+'\t'+t+'\t'+format(value,'.17g')+'\n').encode());count+=1
        for (p,t),v in sorted(remaining.items()):
            if v>0:sink.write((p+'\t'+t+'\t'+format(.5*v,'.17g')+'\n').encode());count+=v>0
    return {'model_rows':modelrows,'union_output_rows':count,'sequence_only_pairs':sum(v>0 for v in remaining.values()),
            'zero_missing_is_arithmetic_only':True,'score_normalization':'none'}


def run(config_path,output):
    config_path=Path(config_path);c=json.loads(config_path.read_text())
    need(set(c)=={'targets','sequence','baseline_qualification','model_manifest','model_directory','canonical_map','predeclared_recipe','model_freeze'},'exact execution configuration required.')
    pins={role:dict(c[role]) for role in c if role!='model_directory'}
    pins['configuration']={'file':str(config_path),'sha256':sha(config_path)}
    pins['adapter']={'file':str(Path(__file__).resolve()),'sha256':sha(__file__)}
    for item in pins.values():need(sha(item['file'])==item['sha256'],'input file differs from execution pin.')
    q=sealed(c['baseline_qualification']['file']);recipe=sealed(c['predeclared_recipe']['file']);m=sealed(c['model_manifest']['file']);frozen=sealed(c['model_freeze']['file'])
    need(q['format']=='biograph-steward.reserved-cafa5-native-controls.v1.results' and q['future_GO_terms_read'] is False,'native controls do not precede outcome access.')
    need(recipe['content_sha256']==q['protocol_content_sha256'] and recipe['fixed_fusion_if_executed']['weights']==[.5,.5],'predeclared arithmetic recipe differs.')
    need(m['format']=='biograph-steward.cafa5-full-context-predictions.v1' and m['future_GO_labels_read'] is False,'historical model prediction seal required.')
    need(m['protocol_file_sha256']==c['model_freeze']['sha256'] and m['protocol_content_sha256']==frozen['content_sha256']
         and frozen['files']['targets.txt']==c['targets']['sha256'],'network model/frozen reserved target binding differs.')
    need(q['target_file_sha256']==c['targets']['sha256'] and q['files']['official_prott5_cosine3.tsv.gz']['sha256']==c['sequence']['sha256'],'native score or target identity binding differs.')
    targets=Path(c['targets']['file']).read_text().splitlines();need(targets==sorted(set(targets)) and len(targets)==q['target_count'],'reserved target inventory differs.')
    cmap=json.loads(Path(c['canonical_map']['file']).read_text());need(set(cmap)=={'primary','alternative','namespace'},'official ontology canonical-map fields differ.')
    canonical={**cmap['primary'],**cmap['alternative']}
    modelbase=Path(c['model_directory'])
    for name in ARMS.values():
        fn=name+'.tsv.gz';need(sha(modelbase/fn)==m['files'][fn]['sha256'],'frozen network model bytes differ.')
        pins[name]={'file':str(modelbase/fn),'sha256':m['files'][fn]['sha256']}
    output=Path(output);need(not output.exists(),'choose a new output folder.');output.mkdir(parents=True)
    protocol={'format':'biograph-steward.reserved-fixed-fusion.v1','at':datetime.now(timezone.utc).isoformat(),'input_pins':pins,'arms':ARMS,'weights':[.5,.5],
        'predeclared_recipe_content_sha256':recipe['content_sha256'],'model_prediction_content_sha256':m['content_sha256'],
        'future_GO_labels_read':False,'target_count':len(targets),'missing_model_score_is_biological_negative':False,
        'mechanism':'Established convex score sum; equal weights fixed before all future labels, no calibration or alpha search. Sequence max-duplicate resolution matches the author evaluator. Same exact K3 control combined with full FSS and full Local.'}
    protocol['content_sha256']=digest(protocol);(output/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    sequence,diagnostic=load_sequence(c['sequence']['file'],set(targets),canonical);results={}
    for arm,source in ARMS.items():
        results[arm]=mix(modelbase/(source+'.tsv.gz'),sequence,set(targets),canonical,output/(arm+'.tsv.gz'));print(json.dumps({'arm':arm,**results[arm]}),flush=True)
    for item in pins.values():need(sha(item['file'])==item['sha256'],'frozen source changed during arithmetic.')
    report={'format':protocol['format']+'.results','at':datetime.now(timezone.utc).isoformat(),'protocol_content_sha256':protocol['content_sha256'],
        'protocol_file_sha256':sha(output/'protocol.json'),'sequence_intake':diagnostic,'outputs':results,'future_GO_labels_read':False,
        'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir())}}
    report['content_sha256']=digest(report);(output/'predictions.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();r=run(args.config,args.output);print(r['content_sha256'])
