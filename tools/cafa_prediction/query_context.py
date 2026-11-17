"""Exact PyG one-hop execution context for the frozen published LocalPlus model.

This is a retrieval/execution equivalence check, not a prediction variant or an
accuracy measurement. Only explicitly queried rows have full-network semantics.
"""
import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
from importlib import metadata
from pathlib import Path
import time

from .core import adjacency, author_modules, need, sha
from .strict_alias_context import load_packet
from .run import digest, new_output, pin, read, timestamp, verify_pins, write

ROOT_TERMS={'GO:0003674','GO:0005575','GO:0008150'}


def extract_context(nodes, W, edge_index, queries):
    import numpy as np
    import torch
    from scipy.sparse import csr_matrix
    from torch_geometric.utils import k_hop_subgraph
    need(isinstance(queries,list) and 1<=len(queries)<=25 and len(set(queries))==len(queries),
         'request1..25 unique exact source protein IDs.')
    index={p:i for i,p in enumerate(nodes)}
    need(all(q in index for q in queries),'query protein is outside the exact frozen source; no alias rescue.')
    global_queries=np.asarray([index[q] for q in queries],dtype=int)
    subset,edges,mapping,mask=k_hop_subgraph(torch.tensor(global_queries,dtype=torch.long),1,edge_index,
        relabel_nodes=True,num_nodes=len(nodes),flow='target_to_source',directed=False)
    selected=subset.numpy(); local_queries=mapping.numpy()
    need(np.array_equal(selected[local_queries],global_queries),'PyG query relabeling changed identity/order.')
    coo=W.tocoo(); weights=coo.data[mask.numpy()]
    local=csr_matrix((weights,(edges[0].numpy(),edges[1].numpy())),shape=(len(selected),len(selected)))
    for global_q,local_q in zip(global_queries,local_queries):
        fullrow=W.getrow(global_q); row=local.getrow(local_q)
        need(np.array_equal(selected[row.indices],fullrow.indices) and np.array_equal(row.data,fullrow.data),
             'query incident source edges/weights were lost or duplicated.')
        need(float(row.sum())==float(fullrow.sum()),'query weighted-degree denominator differs.')
    return selected,local_queries,local


def metadata_queries(nodes,W,seed):
    """Prespecified graph-metadata sample; no labels or performance used."""
    degree=W.getnnz(axis=1)
    order=sorted(range(len(nodes)),key=lambda i:hashlib.sha256((seed+'|'+nodes[i]).encode()).hexdigest())
    connected=[i for i in order if degree[i]>0][:16]
    isolates=[i for i in order if degree[i]==0][:16]
    need(len(connected)==len(isolates)==16,'fixture requires16 metadata-connected and16 isolated source nodes.')
    keep=set(connected+isolates)
    return [nodes[i] for i in order if i in keep]


def run(frozen,expected,author_directory,author_receipt,output):
    import numpy as np
    import torch
    import torch_geometric
    torch.set_num_threads(1)
    need(metadata.version('torch')=='2.6.0' and metadata.version('torch-geometric')=='2.6.1',
         'use inspected existing CPUtorch2.6.0 with isolatedPyG2.6.1.')
    frozen=Path(frozen).resolve(); parent=load_packet(frozen,expected)
    modules=author_modules(author_directory,author_receipt)
    graph=read(frozen/'graph.json.gz'); nodes=graph['nodes']; W=adjacency(nodes,graph['pairs']); del graph
    P=modules['alg_utils'].normalizeGraphEdgeWeights(W); coo=W.tocoo()
    edge_index=torch.tensor(np.vstack((coo.row,coo.col)),dtype=torch.long)
    labels=read(frozen/'training.json.gz'); index={p.split(':',1)[1]:i for i,p in enumerate(nodes)}
    byterm=defaultdict(list)
    for p,entries in labels.items():
        for aspect,term in entries:byterm[(aspect,term)].append(index[p])
    terms=sorted(byterm); sample=metadata_queries(nodes,W,expected)
    contexts=[[q] for q in sample]+[sample[:2],sample[:5],sample[:13],sample[:25],sample[25:]]
    pins={'source_protocol':pin(frozen/'protocol.json'),'graph':pin(frozen/'graph.json.gz'),
          'training':pin(frozen/'training.json.gz'),'adapter':pin(__file__),
          'author_receipt':pin(author_receipt),'core':pin(Path(__file__).with_name('core.py'))}
    context_protocol=read(parent['input_pins']['primary_protocol']['file'])
    qualification_path=Path(context_protocol['input_pins']['full_qualification']['file'])
    qualification=read(qualification_path)
    protein_path=Path(qualification['input_pins']['proteins']['file'])
    pair_path=qualification_path.parent/'weighted_pairs.tsv'
    need(sha(protein_path)==qualification['input_pins']['proteins']['sha256']
         and sha(pair_path)==qualification['files']['weighted_pairs.tsv']['sha256'],'source-pair metadata differs.')
    proteins={r['uniprot']:r for r in csv.DictReader(protein_path.open(),delimiter='\t')}
    wanted={tuple(sorted((q,nodes[j]))) for q in sample for j in W.getrow(nodes.index(q)).indices}
    pair_records={}
    with pair_path.open() as stream:
        for line,row in enumerate(csv.DictReader(stream,delimiter='\t'),2):
            key=(row['subject'],row['object'])
            if key in wanted:pair_records[key]={'derived_source_row':line,**row}
    need(set(pair_records)==wanted,'query incident source-pair provenance missing.')
    pins.update({'qualified_pair_metadata':pin(pair_path),'protein_metadata':pin(protein_path)})
    folder=new_output(output)
    recipe={'format':'biograph-steward.exact-onehop-LocalPlus-equivalence.v1','created_at':timestamp(),
        'input_pins':pins,'source_strict_protocol_content_sha256':parent['content_sha256'],
        'library':{'torch':torch.__version__,'torch_geometric':torch_geometric.__version__,
                   'function':'torch_geometric.utils.k_hop_subgraph','num_hops':1,'relabel_nodes':True,
                   'num_nodes':len(nodes),'flow':'target_to_source','directed':False,'device':'CPU'},
        'sample_rule':'SHA256(protocol_file_SHA+|+exactnodeID) ranks; first16connected+first16isolated source nodes, graphmetadataonly.',
        'sample_queries':sample,'query_sets':contexts,
        'checks':'Exact query incidentedge/weight identity, weighteddegree and normalizedrow identity; unchanged authorrunLocal fullversuscontext for every17670historicalGOhead.',
        'accuracy_evaluation':False,'future_reference_labels_read':False,'prediction_method_changed':False,
        'non_query_rows':'Contextonly; scores for nonqueriedneighbors doNOT inheritfullgraphsemantics.',
        'scope':'Historical2018STRING/2019alias-qualified network andauthor2023known_t0 annotations. No current2026seeddata.'}
    recipe['content_sha256']=digest(recipe);write(folder/'protocol.json',recipe)
    sample_index=np.asarray([nodes.index(q) for q in sample],dtype=int)
    full=np.zeros((len(sample),len(terms)),dtype=np.float64);started=time.time()
    for j,key in enumerate(terms):
        score,_,_=modules['fss'].runLocal(P,np.asarray(byterm[key],dtype=int));full[:,j]=score[sample_index]
        if (j+1)%3000==0:print({'full_heads':j+1,'seconds':time.time()-started},flush=True)
    diagnostics=[]; packet=None
    for count,queries in enumerate(contexts,1):
        selected,local_queries,local=extract_context(nodes,W,edge_index,queries)
        localP=modules['alg_utils'].normalizeGraphEdgeWeights(local)
        inverse={int(g):i for i,g in enumerate(selected)}
        for g,l in zip([nodes.index(q) for q in queries],local_queries):
            row=localP.getrow(l); fullrow=P.getrow(g)
            need(np.array_equal(selected[row.indices],fullrow.indices) and np.array_equal(row.data,fullrow.data),
                 'query normalized coefficients differ.')
        expected_scores=full[[sample.index(q) for q in queries],:]
        observed=np.zeros_like(expected_scores)
        for j,key in enumerate(terms):
            positive=np.asarray([inverse[g] for g in byterm[key] if g in inverse],dtype=int)
            # The unchanged authorfunction accepts an emptypositive vector,
            # which is the correct zero-contribution local context for thatterm.
            score,_,_=modules['fss'].runLocal(localP,positive); observed[:,j]=score[local_queries]
        need(np.array_equal(expected_scores,observed),'full/context LocalPlus float64 query scores differ.')
        diagnostic={'queries':queries,'context_nodes':len(selected),'undirected_context_edges':local.nnz//2,
                    'exact_query_score_values':observed.size,'bitwise_equal':True,'query_isolates':sum(local.getrow(i).nnz==0 for i in local_queries)}
        diagnostics.append(diagnostic);print({'context':count,**{k:v for k,v in diagnostic.items() if k!='queries'}},flush=True)
        if len(queries)==25:packet=(queries,selected,local,localP,observed)
    # One inspectable prototype packet. Top3/aspect is displayselection only;
    # equality above checked everyhead and did not select onfuture truth.
    queries,selected,local,localP,scores=packet; selected_nodes=[nodes[i] for i in selected]; localindex={p:i for i,p in enumerate(selected_nodes)}
    write(folder/'query_graph.json.gz',{'nodes':selected_nodes,'pairs':[(selected_nodes[a],selected_nodes[b],float(w)) for a,b,w in zip(*local.nonzero(),local.data) if a<b]})
    candidate_rows=[]
    for i,q in enumerate(queries):
        known={t for a,t in labels.get(q.split(':',1)[1],[])}; qlocal=localindex[q]; rawrow=local.getrow(qlocal); normrow=localP.getrow(qlocal); denominator=float(rawrow.sum())
        rawweights={int(j):float(w) for j,w in zip(rawrow.indices,rawrow.data)}
        for aspect in ('BPO','MFO','CCO'):
            choices=sorted([j for j,(a,t) in enumerate(terms) if a==aspect and t not in known and t not in ROOT_TERMS and scores[i,j]>0],key=lambda j:(-scores[i,j],terms[j][1]))[:3]
            for j in choices:
                term=terms[j][1]; contributors=[]
                for neighbor,coefficient in zip(normrow.indices,normrow.data):
                    seed=selected_nodes[neighbor].split(':',1)[1]
                    if [aspect,term] in labels.get(seed,[]):
                        source_pair=pair_records[tuple(sorted((q,'UniProtKB:'+seed)))]
                        need(float(source_pair['weight'])==rawweights[int(neighbor)],'witness raw weight differs from source pair.')
                        contributors.append({'protein':'UniProtKB:'+seed,'raw_STRING_weight':rawweights[int(neighbor)],
                            'normalized_contribution':float(coefficient),'known_t0_term_row':[seed,term,aspect],
                            'source_pair':source_pair,'native_STRING_pair':['9606.'+proteins[p.split(':',1)[1]]['stringid'] for p in (q,'UniProtKB:'+seed)],
                            'archived_geneid':proteins[seed]['geneid']})
                need(abs(sum(c['normalized_contribution'] for c in contributors)-float(scores[i,j]))<=1e-12,'witness contribution sum differs.')
                candidate_rows.append({'query':q,'GO_ID':term,'aspect':aspect,'score':float(scores[i,j]),'known_in_training_snapshot':False,
                    'full_query_weighted_degree':denominator,'contributors':contributors,
                    'interpretation':'PredictedGOassociationfromhistoricalweightedneighbors, notcuratedtruth, directfunction, physicalbinding, diseasecontext orcurrentnovelty.',
                    'source_note':'CAFAauthor known_t0 table has no per-rowPMIDs ornativeGAFrelation/context. These are historical trainingtriples, notinventedexperimentalpublications.'})
    write(folder/'candidate_explanations.json.gz',candidate_rows)
    verify_pins(pins)
    result={'format':recipe['format']+'.results','created_at':timestamp(),'protocol_content_sha256':recipe['content_sha256'],
        'full_nodes':len(nodes),'full_undirected_edges':W.nnz//2,'historical_GO_heads':len(terms),
        'contexts_checked':len(contexts),'query_values_checked':sum(r['exact_query_score_values'] for r in diagnostics),
        'all_query_scores_bitwise_equal':True,'diagnostics':diagnostics,'prototype_candidates':len(candidate_rows),
        'prediction_source_or_graph_changed':False,'accuracy_measured':False,'future_reference_labels_read':False,
        'files':{f.name:{'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(folder.iterdir())}}
    result['content_sha256']=digest(result);write(folder/'report.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--frozen',required=True);p.add_argument('--protocol-sha256',required=True);p.add_argument('--author-directory',required=True);p.add_argument('--author-receipt',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(run(a.frozen,a.protocol_sha256,a.author_directory,a.author_receipt,a.output)['content_sha256'])
