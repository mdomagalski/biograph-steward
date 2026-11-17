"""Target-only, disjoint-gene replication packet for the fixed full context model."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

from biograph_steward.client import digest as native_digest
from .core import need, sha
from .full_context import load_packet
from .run import digest, new_output, pin, read, timestamp, write


def target_frame(ids, original, full):
    need(ids and ids==sorted(set(ids)), 'reserved identities must be sorted, unique and nonempty.')
    need(not(set(ids)&set(original)), 'reserved target frame overlaps the original targets.')
    need(set(ids)<=set(full), 'reserved target is outside the unchanged full-source node frame.')
    return ids


def prepare(parent_folder, parent_sha, metadata_path, output):
    parent_folder=Path(parent_folder).resolve(); parent=load_packet(parent_folder,parent_sha)
    metadata_path=Path(metadata_path).resolve(); metadata=read(metadata_path)
    need(metadata['format']=='biograph-steward.cafa5-reserved-gene-transfer-metadata.v1'
         and metadata['future_GO_columns_decoded'] is False and metadata['labels_reserved'] is True
         and metadata['primary_frame_changed'] is False
         and metadata['content_sha256']==native_digest({k:v for k,v in metadata.items() if k!='content_sha256'}),'reserved identity-only source metadata differs.')
    ids_path=metadata_path.parent/'reserved_targets.txt'
    need(sha(ids_path)==metadata['files']['reserved_targets.txt'], 'reserved identity file changed.')
    fullgraph=read(parent_folder/'full_graph.json.gz'); oldgraph=read(parent_folder/'induced_graph.json.gz')
    oldtargets=(parent_folder/'targets.txt').read_text().splitlines()
    ids=target_frame(ids_path.read_text().splitlines(),oldtargets,[n.split(':',1)[1] for n in fullgraph['nodes']])
    oldnodes=set(oldgraph['nodes'])
    need(not any('UniProtKB:'+p in oldnodes for p in ids),'reserved target occurs anywhere in the original graph frame.')
    need(len(ids)==metadata['reserved_PK_target_IDs'],'reserved identity count differs.')
    need(metadata['source_full_protein_file_sha256']==read(parent_folder/'full_qualification.json')['input_pins']['proteins']['sha256'],'reserved metadata uses another full source.')
    folder=new_output(output)
    for name in parent['files']:
        if name not in {'targets.txt','induced_graph.json.gz'}: shutil.copyfile(parent_folder/name,folder/name)
    # Isolated padding changes neither the old control weights nor predictions
    # at its old nodes. It explicitly makes the out-of-frame absence visible.
    write(folder/'induced_graph.json.gz',{'nodes':fullgraph['nodes'],'pairs':oldgraph['pairs']})
    (folder/'targets.txt').write_text('\n'.join(ids)+'\n')
    shutil.copyfile(parent_folder/'protocol.json',folder/'source_context_protocol.json')
    shutil.copyfile(metadata_path,folder/'reserved_identity_metadata.json')
    p=deepcopy(parent); p.update({'created_at':timestamp(),'replication_scope':'disjoint_target_gene_temporal_PK_annotation_recovery',
        'derives_from_full_context_content_sha256':parent['content_sha256'],
        'target_frame_disjoint_from_original_graph':True,'reserved_future_GO_terms_opened':False,
        'primary_candidate_changed':False,'all_original_methods_parameters_seeds_weights_unchanged':True,
        'purpose':'Fixed out-of-original-graph target replication. Full all-seed FSS versus matched full LocalPlus and official sequence/resource controls; full old-seed FSS separates training-neighbor coverage. This is the same CAFA study, not an independent-study replication.',
        'inference_scope':'All4806 reserved exact canonical proteins outside every original3172graphnode. Known-at-t0 annotations remain valid partial-knowledge inputs; this is not label-free zero-shot gene prediction.',
        'induced_control':'Same20412nodes with identical87452old-induced edges. Every reserved target is isolated by construction; zero novel coverage is expected and is only a coverage diagnostic, never a strong scientific comparator.',
        'primary_reserved_metric':'Official author BPO partial-knowledge microFmax on all2826 metadata-eligible reservedBPOtargets before authorTOIfiltering; MF/CCsecondary. Do not choose candidate/threshold/weights using these futurelabels.'})
    p['counts'].update({'targets':len(ids),'induced_nodes':len(fullgraph['nodes']),'reserved_raw_targets_by_aspect':metadata['reserved_targets_by_aspect']})
    p['input_pins'].update({'reserved_preparer':pin(__file__),'reserved_identity_metadata':pin(metadata_path),'reserved_targets':pin(ids_path),'source_context_protocol':pin(parent_folder/'protocol.json')})
    p['files']={f.name:sha(f) for f in sorted(folder.iterdir())}
    p.pop('content_sha256',None); p['content_sha256']=digest(p); write(folder/'protocol.json',p); return p


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--parent',required=True); parser.add_argument('--parent-sha256',required=True); parser.add_argument('--metadata',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args(); print(prepare(args.parent,args.parent_sha256,args.metadata,args.output)['content_sha256'])
