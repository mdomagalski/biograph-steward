# SPDX-License-Identifier: GPL-3.0-only
"""Dated, source-derived CAFA6 GOA context; no training or reference labels.

The pinned Apache-2.0 author grouping/traversal bodies and count-kernel C
operation execute unchanged. Explicit input/output plumbing fixes the released
formatter's namespace collisions and raw/propagated path duplication. Native
CAFA evaluator alias expansion precedes grouping, retaining evidence/relation
metadata. This is a disclosed 40-channel adaptation, not CAFA6 reproduction.
"""
import argparse
import ast
from collections import Counter
import ctypes
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

from tools.learned_combination.core import need
from tools.learned_combination.reference import file_sha256, gaf_header, read_target_ids
from .prepare import _check_path, write_json
from .native_stacker import sequence_edge_graph

AUTHOR_COMMIT='0ee85d2f07f724be1721ea39211f1b364535f976'
AUTHOR_PINS={
 'data_scripts/build_evidence_features.py':'35ab8018bd3846950e2eb54963834ff30ac412a5aaa5c147c0dcbea2c4c9e7f2',
 'protlib/scripts/prop_tsv_sum.py':'19533ce57f2e9e79e1b8de7052649b2ce6ccc6c38f6e197c98803ba1a0ab8646'}
EVIDENCE=('IEA','IBA','ISO','ISS','NAS','ND','ISM','other')
RELATIONS=('involved_in','enables','located_in','part_of','is_active_in','acts_upstream_of_or_within','other')
CHANNELS=(('global.raw','global.propagated')
 +tuple(f'evidence.{code}.{view}' for code in EVIDENCE for view in ('raw','propagated'))
 +tuple(f'relation.{relation}.{view}' for relation in RELATIONS for view in ('raw','propagated'))
 +tuple(f'support.{kind}.ge{cutoff}' for kind in ('branches','code_branches') for cutoff in range(2,6)))
NS='biological_process'


def native_term_map(ontologies):
    """Use pinned native primary/alternative dictionaries and alias priority.

    Mirrors load_native_scores' namespace assignment/alias-over-primary order;
    a native multi-primary alternative ID expands to every supplied primary.
    No synonym, sequence, disease or inferred biological mapping occurs here.
    """
    mapping={}
    for ns,graph in ontologies.items():
        for term in graph.terms_dict:mapping[term]=(ns,(term,))
        for term,primary in graph.terms_dict_alt.items():mapping[term]=(ns,tuple(primary))
    return mapping


def normalize(frame,ontologies,namespace=NS):
    """Preserve code/relation/date; collapse only exact normalized rows."""
    import pandas as pd
    mapping=native_term_map(ontologies);rows=[];counts=Counter()
    columns=['EntryID','type','term','source','date']
    need(list(frame.columns)==columns,'explicit native source columns required.')
    for protein,relation,term,code,date in frame.itertuples(index=False,name=None):
        counts['source_selected_rows']+=1
        value=mapping.get(term)
        if value is None or value[0]!=namespace:
            counts['rows_outside_fixed_model_namespace']+=1;continue
        actual,terms=value
        if term in ontologies[actual].terms_dict_alt:counts['native_alias_rows']+=1
        counts['native_canonical_assignments']+=len(terms)
        rows.extend((protein,relation,canonical,code,date) for canonical in terms)
    result=pd.DataFrame(rows,columns=columns).drop_duplicates(ignore_index=True)
    counts['exact_normalized_duplicate_rows_collapsed']=len(rows)-len(result)
    counts['distinct_normalized_metadata_rows']=len(result)
    return result,dict(counts)


def load_author(root,output):
    """Execute pinned grouping/Python traversal and unchanged C operation."""
    import numpy as np
    import pandas as pd
    root,output=Path(root),Path(output);output.mkdir(parents=True,exist_ok=False)
    for name,pin in AUTHOR_PINS.items():need(file_sha256(root/name)==pin,'CAFA6 author source differs: '+name)
    group_tree=ast.parse((root/'data_scripts/build_evidence_features.py').read_text())
    group_nodes=[n for n in group_tree.body if (isinstance(n,ast.Assign) and any(
        isinstance(t,ast.Name) and t.id in ('TYPES','IEA_CODES','KAGGLE_CODES') for t in n.targets))
        or (isinstance(n,ast.FunctionDef) and n.name=='process_uniprot')]
    groups={'pd':pd};exec(compile(ast.Module(body=group_nodes,type_ignores=[]),str(root/'data_scripts/build_evidence_features.py'),'exec'),groups)
    need(tuple(groups['IEA_CODES'])==EVIDENCE[:-1] and tuple(groups['TYPES'])==RELATIONS[:-1],
         'native category order differs from fixed contract.')
    tree=ast.parse((root/'protlib/scripts/prop_tsv_sum.py').read_text())
    call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='ElementwiseKernel')
    operation=ast.literal_eval(call.args[2]);operation_sha=hashlib.sha256(operation.encode()).hexdigest()
    # CPU iteration/ABI encloses the literal, unchanged author CUDA C operation.
    source='#include <stdint.h>\nvoid native_count(const int64_t *indices,const int64_t *j_,int64_t col,int64_t l,int64_t lx,float *arr,int64_t n){for(int64_t pos=0;pos<n;pos++){int64_t i_=indices[pos];\n'+operation+'\n}}\n'
    cfile=output/'native_operation.c';cfile.write_text(source);library=output/'native_operation.so'
    subprocess.run(['cc','-O2','-fPIC','-shared',str(cfile),'-o',str(library)],check=True)
    dll=ctypes.CDLL(str(library));function=dll.native_count
    function.argtypes=[np.ctypeslib.ndpointer(np.int64,flags='C_CONTIGUOUS'),np.ctypeslib.ndpointer(np.int64,flags='C_CONTIGUOUS'),ctypes.c_int64,ctypes.c_int64,ctypes.c_int64,np.ctypeslib.ndpointer(np.float32,flags='C_CONTIGUOUS'),ctypes.c_int64];function.restype=None
    def kernel(rows,children,column,nchildren,width,values):
        function(rows,children,column,nchildren,width,values,len(rows))
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='propagate_max']
    counter={'cp':np,'propagate_col_kernel':kernel};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(root/'protlib/scripts/prop_tsv_sum.py'),'exec'),counter)
    receipt={'author_commit':AUTHOR_COMMIT,'author_files':AUTHOR_PINS,
        'native_C_operation_sha256':operation_sha,'C_bridge':'Unchanged source operation enclosed by CPU row loop and ABI; NumPy supplies cp.arange/asarray for unchanged Python traversal.',
        'grouping_AST_sha256':hashlib.sha256(ast.dump(ast.Module(body=group_nodes,type_ignores=[]),include_attributes=False).encode()).hexdigest(),
        'traversal_AST_sha256':hashlib.sha256(ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False).encode()).hexdigest(),
        'compiler_source_sha256':file_sha256(cfile),'library_sha256':file_sha256(library),
        'GPU_parity_measured':False,'count_math_changed':False}
    write_json(output/'receipt.json',receipt)
    return groups,counter['propagate_max'],receipt


def native_groups(groups,frame,proteins,terms):
    """Run original NOT/admission/coarsening before selecting channel groups."""
    import pandas as pd
    groups.update(train=pd.DataFrame({'EntryID':list(proteins)}),
                  old_train=pd.DataFrame({'EntryID':[]}),test=pd.DataFrame({'EntryID':[]}),
                  aspect={term:'BPO' for term in terms})
    processed=groups['process_uniprot'](frame.copy())
    eligible=processed.query('~is_kaggle & is_pos & valid_terms')
    # These are the unchanged native writer's per-category query/column/dedup
    # operations, with explicit in-memory inputs instead of filename globs.
    result={'global':eligible[['EntryID','term','is_train','is_old_train','is_test']].drop_duplicates(ignore_index=True)}
    for code in EVIDENCE:
        result['evidence.'+code]=processed.query(f'~is_kaggle & is_pos & valid_terms & (evidence == "{code}")')[['EntryID','term','is_train','is_old_train','is_test']].drop_duplicates(ignore_index=True)
    for code in RELATIONS:
        result['relation.'+code]=processed.query(f'~is_kaggle & is_pos & valid_terms & (type == "{code}")')[['EntryID','term','is_train','is_old_train','is_test']].drop_duplicates(ignore_index=True)
    return result,{'normalized_rows':len(frame),'eligible_metadata_rows':len(eligible),
        'NOT_rows_excluded':int((~processed.is_pos).sum()),'experimental_group_rows_excluded':int(processed.is_kaggle.sum())}


def build_context(proteins,graph,channel_groups,native_count,path):
    """Binary sidecar; count signals remain branch/code-branch thresholds."""
    import numpy as np
    proteins=tuple(proteins);graph=sequence_edge_graph(graph)
    pidx={p:i for i,p in enumerate(proteins)};terms=tuple(n['id'] for n in graph.terms_list);tidx={t:i for i,t in enumerate(terms)}
    need(not Path(path).exists(),'preserve existing context output.')
    out=np.lib.format.open_memmap(path,mode='w+',dtype=bool,shape=(len(proteins),len(CHANNELS),len(terms)));out[:]=False
    code_counts=np.zeros((len(proteins),len(terms)),dtype=np.float32)
    for group,table in channel_groups.items():
        print(datetime.now(timezone.utc).isoformat(),'NATIVE_CONTEXT_GROUP',group,len(table),flush=True)
        matrix=np.zeros(code_counts.shape,dtype=np.float32)
        rows=np.asarray([pidx[p] for p in table.EntryID],dtype=np.int64)
        columns=np.asarray([tidx[t] for t in table.term],dtype=np.int64)
        # Native direct initialization add+clip equals duplicate MAX membership.
        np.add.at(matrix,(rows,columns),1);np.clip(matrix,0,1,out=matrix)
        raw_index=0 if group=='global' else CHANNELS.index(group+'.raw')
        out[:,raw_index,:]=matrix>0
        native_count(matrix,graph)
        out[:,raw_index+1,:]=matrix>0
        if group=='global':
            for cutoff in range(2,6):out[:,CHANNELS.index('support.branches.ge'+str(cutoff)),:]=matrix>=cutoff
        elif group.startswith('evidence.'):
            code_counts+=matrix
    for cutoff in range(2,6):out[:,CHANNELS.index('support.code_branches.ge'+str(cutoff)),:]=code_counts>=cutoff
    out.flush();del out
    return terms


def read_t0_gaf(path,proteins,*,expected_date):
    """Use existing GAF header admission and exact17-field source selection.

    Five grouping fields match the published raw_uniprot.py projection. Forms,
    extensions and with/from are not interpreted as independent evidence.
    """
    import pandas as pd
    header=gaf_header(path)
    need('!gaf-version: 2.2' in header,'qualified GAF2.2 source required.')
    dates=[x.split(':',1)[1].strip().split()[0] for x in header if x.startswith('!date-generated:')]
    need(dates==[expected_date],'dated role source header changed.')
    cutoff=expected_date.replace('-','');selected=set(proteins);rows=[];counts=Counter();codes=Counter();qualifiers=Counter()
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:
            if line.startswith('!') or not line.strip():continue
            fields=line.rstrip('\r\n').split('\t');need(len(fields)==17,'native GAF requires exactly17 fields.')
            counts['source_rows']+=1
            if fields[1] not in selected:continue
            need(fields[0]=='UniProtKB','unexpected source DB for exact protein identity.')
            need(all(fields[i] for i in (1,3,4,6,13)),'required GAF grouping field is empty.')
            need(re.fullmatch('[0-9]{8}',fields[13]) is not None and fields[13]<=cutoff,'annotation assigned after declared source date.')
            rows.append((fields[1],fields[3],fields[4],fields[6],fields[13]));counts['exact_target_rows']+=1
            counts['with_product_form']+=bool(fields[16]);counts['with_annotation_extension']+=bool(fields[15]);counts['with_with_from']+=bool(fields[7]);counts['nonhuman_subject_taxon']+=fields[12].split('|')[0]!='taxon:9606'
            codes[fields[6]]+=1;qualifiers[fields[3]]+=1
    frame=pd.DataFrame(rows,columns=['EntryID','type','term','source','date']).drop_duplicates(ignore_index=True)
    return frame,{'native_header':header,'source_counts':dict(counts),'selected_evidence_counts':dict(codes),'selected_qualifier_counts':dict(qualifiers),'selected_native_rows_after_exact_duplicate_collapse':len(frame),
        'source_context_limit':'Forms/extensions/with-from/reference semantics are not inferred; original source remains pinned. Branch counts are not independent studies.'}


def produce(config,output):
    import numpy as np
    from tools.learned_combination.native_adapter import native_ontologies
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    need(config['format']=='biograph-steward.rich-GOA-producer.v1' and config['fresh_final_reference_opened'] is False,'explicit pre-outcome producer contract required.')
    for path,pin in config['input_pins'].items():
        _check_path(path);need(file_sha256(path)==pin,'producer input changed: '+path)
    need(tuple(config['channels'])==CHANNELS,'fixed context channel order differs.')
    ont=native_ontologies(config['ontology']);graph=ont[NS];terms=tuple(n['id'] for n in graph.terms_list)
    groups,native_count,source=load_author(config['author_root'],output/'native_source')
    result={'format':'biograph-steward.rich-GOA-produced.v1','manifests':{},'source_input_pins':config['input_pins'],
        'author_source_receipt':source,'channels':list(CHANNELS),'fresh_final_reference_opened':False,
        'adaptations':['Explicit evidence/relation namespaces preserve both other groups','True raw and propagated category paths retained','Existing native primary/alternative-ID expansion and canonical duplicate MAX membership applied before native grouping'],
        'literal_CAFA6_reproduction':False,'count_signals_are_independent_studies':False}
    for role,spec in config['roles'].items():
        ids=read_target_ids(spec['targets']);base=json.loads(Path(spec['base_feature_manifest']).read_text())
        need(list(ids)==base['proteins'] and list(terms)==base['terms'],'sidecar must exactly match unchanged parent feature axes.')
        need(len(ids)==spec['expected_targets'],'role cohort differs.')
        frame,source_audit=read_t0_gaf(spec['gaf'],ids,expected_date=spec['date'])
        normalized,mapping_audit=normalize(frame,ont);channel_groups,admission=native_groups(groups,normalized,ids,terms)
        folder=output/role;folder.mkdir();context=folder/'context.npy'
        built_terms=build_context(ids,graph,channel_groups,native_count,context);need(built_terms==terms,'context term order changed.')
        manifest={'format':'biograph-steward.contextual-boolean-features.v1','proteins':list(ids),'terms':list(terms),'channels':list(CHANNELS),
            'context_file':str(context),'context_sha256':file_sha256(context),'fresh_final_reference_opened':False,
            'source_input_pins':config['input_pins'],'source_audit':source_audit,'normalization_audit':mapping_audit,'admission_audit':admission,
            'context_shape':[len(ids),len(CHANNELS),len(terms)],'context_dtype':'bool','base_feature_manifest':spec['base_feature_manifest'],
            'meaning':'Source-derived statistical context only; raw means canonical unpropagated membership, no scientific truth label or independent-study confidence.'}
        write_json(folder/'context.json',manifest);result['manifests'][role]={'file':str(folder/'context.json'),'sha256':file_sha256(folder/'context.json')}
        del frame,normalized,channel_groups
    write_json(output/'receipt.json',result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();produce(json.loads(Path(args.config).read_text()),args.output)


if __name__=='__main__':main()
