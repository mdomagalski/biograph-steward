"""Publish readable, separately versioned historical LocalPlus query examples.

The optional producer uses the verified PyG query context and unchanged author
predictor. The saved JSON consumer below needs only the Python standard library.
No forecast recipe, current annotation intake, graph assertion or review changes.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import shutil

from biograph_steward.function_context import (FORMAT, QUERY, need, digest, sha, validate_query, load_publication)

VERSIONS={
    'pharos_archive':'Pharos319 SQL archive, dump completed 2024-04-17; TCRD6.13.4',
    'network_weights':'STRINGv11.0 human combined weights, native file dated 2018-12-20',
    'identifier_support':'Exact archived accession/locus correspondence supported by native STRING aliases dated 2019-01-17; globally ambiguous projections abstain',
    'annotations':'CAFA5 author known_t0 table from UniProt2023_03',
    't0_date':'2023-08-14',
    'ontology':'Gene Ontology2023-01-01 from the CAFA5 author release',
}
LIMITS=[
    'These are historical model hypotheses, not curator-approved annotations, direct molecular functions, binding claims or current discoveries.',
    'Scores rank weighted-neighbor annotation transfer; they are not calibrated probabilities or acceptance confidence.',
    'Only explicitly queried protein rows reproduce full-network LocalPlus scores. Other nodes provide context only.',
    'A missing neighbor or candidate in this qualified snapshot does not establish biological absence.',
    'The training table supplies protein/GO/aspect triples, not individual publication references, native GAF relations, product forms or experimental contexts.',
    'Source records and contributing neighbors are not independent experiment counts. Shared resources may reuse evidence.',
    'The original Pharos graph, source assertions and review decisions remain unchanged.',
]

DEFAULT_EQUIVALENCE_PROOF=Path('runs/prediction_next_20261113/query_context_equivalence_v1/report.json')
DEFAULT_EQUIVALENCE_PROOF_SHA256='7bbbdfc31c18e3d77c89dbca42ddfca237fdbb4fadb5d82bee3b4c2fc8b752fc'

def load_equivalence_proof(path,expected_sha256,source_protocol_sha256):
    """Rebind the existing execution proof from any explicit preserved folder."""
    path=Path(path).resolve()
    need(path.is_file() and path.stat().st_size<=1048576
         and isinstance(expected_sha256,str) and re.fullmatch(r'[a-f0-9]{64}',expected_sha256)
         and sha(path)==expected_sha256,'explicit equivalence-proof bytes differ.')
    report=json.loads(path.read_text())
    need(isinstance(report,dict) and report.get('format')=='biograph-steward.exact-onehop-LocalPlus-equivalence.v1.results'
         and report.get('content_sha256')==digest({k:v for k,v in report.items() if k!='content_sha256'})
         and report.get('all_query_scores_bitwise_equal') is True
         and all(report.get(k) is False for k in ('accuracy_measured','future_reference_labels_read','prediction_source_or_graph_changed')),
         'a sealed successful source-preserving query-equivalence proof is required.')
    protocol=path.parent/'protocol.json';record=report.get('files',{}).get('protocol.json',{})
    need(protocol.is_file() and not protocol.is_symlink() and protocol.stat().st_size<=1048576
         and protocol.stat().st_size==record.get('bytes') and sha(protocol)==record.get('sha256'),
         'equivalence source protocol bytes differ.')
    value=json.loads(protocol.read_text())
    need(isinstance(value,dict) and value.get('content_sha256')==digest({k:v for k,v in value.items() if k!='content_sha256'})
         and value.get('content_sha256')==report.get('protocol_content_sha256')
         and value.get('input_pins',{}).get('source_protocol',{}).get('sha256')==source_protocol_sha256,
         'equivalence proof belongs to another frozen source graph.')
    return path,protocol










def produce(frozen,expected,author_directory,author_receipt,proteins,output,*,
            equivalence_proof=DEFAULT_EQUIVALENCE_PROOF,equivalence_proof_sha256=DEFAULT_EQUIVALENCE_PROOF_SHA256):
    import numpy as np
    import torch
    import obonet
    from importlib import metadata
    from .core import adjacency,author_modules
    from .query_context import extract_context,ROOT_TERMS
    from .strict_alias_context import load_packet
    from .run import new_output,pin,read,timestamp,verify_pins,write
    torch.set_num_threads(1)
    need(metadata.version('torch')=='2.6.0' and metadata.version('torch-geometric')=='2.6.1'
         and metadata.version('obonet')=='1.3.0','use the inspected isolated runtime.')
    queries=[p if p.startswith('UniProtKB:') else 'UniProtKB:'+p for p in proteins]
    need(1<=len(queries)<=25 and len(set(queries))==len(queries),'choose1..25 unique exact source proteins.')
    frozen=Path(frozen).resolve();strict=load_packet(frozen,expected)
    proof,proof_protocol=load_equivalence_proof(equivalence_proof,equivalence_proof_sha256,expected)
    full_path=Path(strict['input_pins']['primary_protocol']['file']);need(sha(full_path)==strict['input_pins']['primary_protocol']['sha256'],'full source protocol changed.')
    full=read(full_path);primary_path=full_path.parent/'parent_protocol.json';need(sha(primary_path)==full['files']['parent_protocol.json'],'original source protocol changed.')
    original=read(primary_path);ontology_path=Path(original['input_pins']['ontology']['file']);need(sha(ontology_path)==original['input_pins']['ontology']['sha256'],'historical ontology changed.')
    qualification_path=Path(full['input_pins']['full_qualification']['file']);need(sha(qualification_path)==full['input_pins']['full_qualification']['sha256'],'full qualification changed.')
    qualification=read(qualification_path);protein_path=Path(qualification['input_pins']['proteins']['file']);pair_path=qualification_path.parent/'weighted_pairs.tsv'
    need(sha(protein_path)==qualification['input_pins']['proteins']['sha256'] and sha(pair_path)==qualification['files']['weighted_pairs.tsv']['sha256'],'source metadata changed.')
    metadata_rows={r['uniprot']:r for r in csv.DictReader(protein_path.open(),delimiter='\t')}
    tdl_path=qualification_path.parent.parent/'full_target_development_level.tsv'
    tdl={r['uniprot']:r['tdl'] for r in csv.DictReader(tdl_path.open(),delimiter='\t')} if tdl_path.is_file() else {}
    graph=read(frozen/'graph.json.gz');nodes=graph['nodes'];W=adjacency(nodes,graph['pairs']);del graph
    coo=W.tocoo();edge_index=torch.tensor(np.vstack((coo.row,coo.col)),dtype=torch.long)
    selected,qindices,local=extract_context(nodes,W,edge_index,queries);selected_nodes=[nodes[i] for i in selected]
    global_index={p:i for i,p in enumerate(nodes)};modules=author_modules(author_directory,author_receipt)
    P=modules['alg_utils'].normalizeGraphEdgeWeights(W);localP=modules['alg_utils'].normalizeGraphEdgeWeights(local)
    for q,l in zip(queries,qindices):
        a=P.getrow(global_index[q]);b=localP.getrow(l)
        need(np.array_equal(selected[b.indices],a.indices) and np.array_equal(b.data,a.data),'query normalization differs.')
    labels=read(frozen/'training.json.gz');local_index={p.split(':',1)[1]:i for i,p in enumerate(selected_nodes)};byterm=defaultdict(list)
    for protein,entries in labels.items():
        if protein in local_index:
            for aspect,term in entries:byterm[(aspect,term)].append(local_index[protein])
    scores={q:{} for q in queries}
    for key,positive in sorted(byterm.items()):
        values,_,_=modules['fss'].runLocal(localP,np.asarray(positive,dtype=int))
        for q,value in zip(queries,values[qindices]):
            if value>0:scores[q][key]=float(value)
    # Existing obonet reader supplies labels only; no new GO closure/reasoning.
    ontology=obonet.read_obo(ontology_path);names={term:row.get('name',term) for term,row in ontology.nodes(data=True)};del ontology
    wanted={tuple(sorted((q,nodes[j]))) for q in queries for j in W.getrow(global_index[q]).indices};source_pairs={}
    with pair_path.open() as stream:
        for line,row in enumerate(csv.DictReader(stream,delimiter='\t'),2):
            key=(row['subject'],row['object'])
            if key in wanted:source_pairs[key]={'derived_source_row':line,**row}
    need(set(source_pairs)==wanted,'complete source pair metadata is missing.')
    ambiguous=read(qualification_path.parent/'global_noninjective_mappings.json');by_sid={sid:values for sid,values in ambiguous.items()}
    absent=set(strict['unattested_mapping_nodes_retained_as_isolates'])
    pins={'strict_protocol':pin(frozen/'protocol.json'),'graph':pin(frozen/'graph.json.gz'),'training':pin(frozen/'training.json.gz'),
        'ontology':pin(ontology_path),'qualified_pairs':pin(pair_path),'protein_metadata':pin(protein_path),'producer':pin(__file__),
        'query_extractor':pin(Path(__file__).with_name('query_context.py')),'author_receipt':pin(author_receipt)}
    pins['equivalence_proof']=pin(proof);pins['equivalence_protocol']=pin(proof_protocol)
    from biograph_steward import function_context
    pins['stdlib_consumer']=pin(function_context.__file__)
    if tdl_path.is_file():pins['archived_TDL_metadata']=pin(tdl_path)
    identity={'source_protocol':expected,'query_ids':queries,'method':'published LocalPlus','display_top_per_aspect':3}
    publication_id='historical-localplus:'+digest(identity)[:24];folder=new_output(output);(folder/'queries').mkdir();(folder/'downloads').mkdir();query_files={}
    for q,l in zip(queries,qindices):
        accession=q.split(':',1)[1];meta=metadata_rows[accession];row=local.getrow(l);norm=localP.getrow(l);degree=float(row.sum());weights={int(i):float(w) for i,w in zip(row.indices,row.data)}
        known={term for aspect,term in labels.get(accession,[])};candidates=[]
        for aspect in ('BPO','MFO','CCO'):
            choices=sorted([(term,value) for (a,term),value in scores[q].items() if a==aspect and term not in known and term not in ROOT_TERMS],key=lambda pair:(-pair[1],pair[0]))[:3]
            for term,value in choices:
                contributors=[]
                for neighbor,coefficient in zip(norm.indices,norm.data):
                    seed=selected_nodes[neighbor].split(':',1)[1]
                    if [aspect,term] in labels.get(seed,[]):
                        pair=source_pairs[tuple(sorted((q,'UniProtKB:'+seed)))];need(float(pair['weight'])==weights[int(neighbor)],'contributor weight differs.')
                        contributors.append({'protein':'UniProtKB:'+seed,'symbol':metadata_rows[seed]['sym'],
                            'display_label':metadata_rows[seed]['sym']+' · '+seed,'raw_STRING_weight':weights[int(neighbor)],
                            'normalized_contribution':float(coefficient),'known_t0_term_row':[seed,term,aspect],
                            'source_pair':pair,'native_STRING_pair':['9606.'+metadata_rows[p]['stringid'] for p in (accession,seed)],
                            'individual_publication_references_available':False})
                candidates.append({'GO_ID':term,'label':names.get(term,term),'aspect':aspect,'score':value,
                    'known_in_training_snapshot':False,'complete_contributions':True,'contributors':contributors})
        reasons=[]
        if meta['stringid'] in by_sid:reasons.append({'code':'shared_archived_STRING_locus','accessions':by_sid[meta['stringid']],
            'message':'Distinct archived protein records share one STRING locus representative. This protein-level projection is unresolved; it is not evidence of absent biology.'})
        if accession in absent:reasons.append({'code':'historical_alias_not_exactly_attested','message':'The exact accession/locus pair was not found in the native2019 alias file; its incident model weights abstain.'})
        state='no_qualified_neighbor_context' if degree==0 else 'ranked_hypotheses' if candidates else 'no_unseen_training_terms'
        value={'format':QUERY,'publication_id':publication_id,'query':{'id':q,'symbol':meta['sym'],'name':None,
            'display_label':meta['sym']+' · '+accession,'archivedGeneID':meta['geneid'],'TDL':tdl.get(accession),
            'archived_STRING_ID':'9606.'+meta['stringid'] if re.fullmatch(r'ENSP[0-9]+',meta['stringid']) else None,
            'TDL_version':'Pharos319 April2024 metadata; not a predictor feature'},'source_versions':VERSIONS,
            'state':state,'weighted_degree':degree,'qualified_neighbor_count':row.nnz,'known_training_term_count':len(known),
            'query_context_nodes':len(selected),'query_context_undirected_edges':local.nnz//2,
            'source_qualification':reasons,'candidates':candidates,'uncalibrated_score':True,
            'knowledge_level':'prediction','curated_acceptance':False,'display_top_per_aspect':3,
            'scope':'Read-only historical usability example. Display selection uses scores and exact GO-ID tie breaks, never future labels or measured performance.',
            'limitations':LIMITS,'source_protocol_content_sha256':strict['content_sha256']}
        validate_query(value,publication_id);name='queries/'+accession+'.json';write(folder/name,value);query_files[q]=name
    for role,name in [('graph','graph.json.gz'),('training','training_snapshot.json.gz')]:shutil.copyfile(pins[role]['file'],folder/'downloads'/name)
    shutil.copyfile(protein_path,folder/'downloads/protein_metadata.tsv')
    shutil.copyfile(proof,folder/'downloads/execution_equivalence_report.json')
    shutil.copyfile(__file__,folder/'downloads/query_publication_producer.py')
    shutil.copyfile(function_context.__file__,folder/'downloads/function_context_consumer.py')
    write(folder/'downloads/model_source_qualification.json',{'source_versions':VERSIONS,
        'strict_source_protocol_sha256':expected,'source_nodes':len(nodes),'qualified_undirected_weights':W.nnz//2,
        'source_pins':{role:{'sha256':r['sha256'],'bytes':r['bytes']} for role,r in pins.items()},
        'reference_source':'https://zenodo.org/records/22381862','STRING_source':'https://stringdb-static.org/download/protein.links.v11.0/9606.protein.links.v11.0.txt.gz',
        'no_individual_study_references':'The benchmark feature table supplies no per-row publication identifiers; none is inferred.',
        'software':'Unchanged author LocalPlus functions plus PyG2.6.1 k_hop_subgraph; no model fitting or graph mutation.',
        'qualifications':LIMITS})
    (folder/'LICENSE.txt').write_text('Derived historical model inputs and explanations. Attribute STRINGv11, UniProt/Gene Ontology and the CAFA5 authors.\nNative STRING and GO/UniProt data retain upstream CC-BY-4.0 terms; the software license does not relicense the complete Pharos archive.\nhttps://creativecommons.org/licenses/by/4.0/\nhttps://geneontology.org/docs/go-citation-policy/\nhttps://string-db.org/cgi/access\n')
    verify_pins(pins)
    m={'format':FORMAT,'publication_id':publication_id,'created_at':timestamp(),'purpose':'Six-protein usability example, not a new validation cohort.' if len(queries)==6 else 'Declared historical query example; not an accuracy assessment.',
        'query_files':query_files,'source_versions':VERSIONS,'source_protocol_content_sha256':strict['content_sha256'],
        'input_source_pins':{role:{'sha256':r['sha256'],'bytes':r['bytes']} for role,r in pins.items()},
        'source_graph_modified':False,'future_reference_labels_included':False,'current2026_annotations_used':False,
        'model_or_parameter_fit':False,'scientific_accuracy_claimed':False,'uncalibrated_score':True,
        'executed_method':'Published LocalPlus on a query-complete one-hop context; exact full-row normalization verified.',
        'query_only_semantics':'Only declared queries have full-network scores. Context neighbors are not additional scored queries.',
        'method_references':[{'title':'FastSinkSource and its published LocalPlus baseline','url':'https://doi.org/10.1093/bioinformatics/btaa885'},
            {'title':'Unchanged author implementation','url':'https://github.com/Murali-group/multi-species-GOA-prediction/tree/c45c21b9c937c3372eae03248f49fb008d4cb0cf'},
            {'title':'PyG2.6.1 k_hop_subgraph','url':'https://pytorch-geometric.readthedocs.io/en/2.6.1/modules/utils.html#torch_geometric.utils.k_hop_subgraph'}],
        'downloads':{'full_qualified_graph':'downloads/graph.json.gz','historical_training_snapshot':'downloads/training_snapshot.json.gz',
            'source_qualification':'downloads/model_source_qualification.json','execution_equivalence_proof':'downloads/execution_equivalence_report.json',
            'producer_code':'downloads/query_publication_producer.py','consumer_code':'downloads/function_context_consumer.py'},
        'limitations':LIMITS,'files':{f.relative_to(folder).as_posix():{'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(folder.rglob('*')) if f.is_file()}}
    m['content_sha256']=digest(m);write(folder/'publication.json',m);load_publication(folder,sha(folder/'publication.json'));return m


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--frozen',required=True);p.add_argument('--protocol-sha256',required=True);p.add_argument('--author-directory',required=True);p.add_argument('--author-receipt',required=True);p.add_argument('--protein',action='append',required=True);p.add_argument('--output',required=True)
    p.add_argument('--equivalence-proof',default=str(DEFAULT_EQUIVALENCE_PROOF),help='Preserved query-equivalence report; its protocol.json sibling is verified.')
    p.add_argument('--equivalence-proof-sha256',default=DEFAULT_EQUIVALENCE_PROOF_SHA256,help='Exact report SHA256; set this when supplying a relocated/reproduced proof.')
    a=p.parse_args();m=produce(a.frozen,a.protocol_sha256,a.author_directory,a.author_receipt,a.protein,a.output,
        equivalence_proof=a.equivalence_proof,equivalence_proof_sha256=a.equivalence_proof_sha256);print(m['content_sha256'])
