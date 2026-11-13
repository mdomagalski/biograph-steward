#!/usr/bin/env python3
"""Prepare the predeclared historical-native xref-compatible feature view.

Native model and identifier matching are delegated to the existing history
reader. This optional feature ablation neither prunes the source graph nor
converts UNKNOWNs into biological negatives. Gene compatibility stays distinct
from literal protein encoding and unestablished historical isoform identity.
"""
from collections import Counter
from copy import deepcopy
import argparse
from pathlib import Path
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest,write_json,utcnow
from biograph_steward.file_utils import sha,new_output
from biograph_steward.cohort_mapping import load_registry
from biograph_steward.wiki_history import load_history_packet,inspect_model,assess_subject
from tools.wiki_utility.prepare import (verify,need,memberships,build_features,IMPLEMENTATION,FORMAT,
    ARMS,RELATION,CONTROL_SEED,XS_SEED,SEEDS,CONSUMED_OUTCOMES)

QUALIFIED={'explicitly_encoded_protein_xref','compatible_gene_level_xref'}


def select_history(path,content_pin,original,ordinary):
    """Replay all exact native resources once using the existing parser/rule.

    The complete portable packet is byte-verified first. Archive hashes are
    checked once rather than once for every subject; each selected member is
    still compared byte-for-byte. Schema receipts remain attached producer
    receipts, never represented as a consumer XSD execution.
    """
    path=Path(path);history=load_history_packet(path,expected_content_sha256=content_pin)
    need(history['report']['source_graph_file_sha256']==sha(path.parent/'original_graph.json'),
         'historical packet belongs to a different original source file')
    identities={(a,b.rsplit('/',1)[1]) for a,_,b in ordinary}
    need(identities==set(history['connections']),'historical source scope differs from original memberships')
    edges={e['id']:e for e in original['edges']}
    models,archives={},{}
    try:
        for full_id,resource in sorted(history['resources'].items()):
            if resource['status']!='exact_publisher_revision_content_available':continue
            candidate=resource['candidates'][0];file=candidate['portable_archive_file']
            need(file in history['report']['files'],'native archive is not in the pinned inventory')
            if file not in archives:archives[file]=zipfile.ZipFile(path/file)
            native=(path/resource['native_model_file']).read_bytes()
            matches=[i for i in archives[file].infolist() if i.filename==candidate['archive_member']]
            need(len(matches)==1 and matches[0].file_size<=20_000_000,'native archive member differs')
            need(archives[file].read(matches[0])==native and sha(path/resource['native_model_file'])==resource['gpml_sha256'],
                 'native archive member and model bytes differ')
            receipt=deepcopy(resource['official_schema_validation']);receipt['gpml_sha256']=resource['gpml_sha256']
            models[full_id]=inspect_model(native,full_source_id=full_id,archive_member=candidate['archive_member'],
                                          validation_receipt=receipt)
    finally:
        for z in archives.values():z.close()
    for file in archives:need(sha(path/file)==history['report']['files'][file],'archive changed during native replay')
    selected,set_rows=set(),[]
    for (subject,full_id),stored in sorted(history['connections'].items()):
        if full_id in models:
            replay=assess_subject(subject,models[full_id],history['registry'])
            need(all(replay[k]==stored[k] for k in ('status','gene_bridge','exact_protein_matches',
                 'compatible_gene_matches','other_entity_diagnostics')),'native xref assessment differs')
            need(stored['native_model_sha256']==models[full_id]['gpml_sha256'],'claim native model differs')
        else:need(stored['status']=='unresolved','positive claim has no exact native model')
        for eid in stored['original_edge_ids']:
            edge=edges.get(eid)
            need(edge is not None and edge['subject']==subject and edge['evidence_record']['sourceID']==full_id
                 and edge['assertion_id'] in stored['original_assertion_ids'],'historical claim source edge differs')
        include=stored['status'] in QUALIFIED
        if include:selected.add((subject,full_id))
        set_rows.append({'subject':subject,'full_source_id':full_id,'status':stored['status'],
            'selected_for_followup_features':include,'source_claim_seal':stored['content_sha256'],
            'original_edge_ids':stored['original_edge_ids'],'original_assertion_ids':stored['original_assertion_ids'],
            'native_model_sha256':stored['native_model_sha256'],
            'independent_scientific_correctness':'unreviewed','unknown_is_biological_negative':False})
    qualified=sorted(t for t in ordinary if (t[0],t[2].rsplit('/',1)[1]) in selected)
    counts={'kind':'historical_native_xref_compatible_context','connection_statuses':dict(Counter(r['status'] for r in set_rows)),
        'selected_unique_connections':len(qualified),'exact_native_models_replayed':len(models),
        'historical_gene_protein_or_isoform_identity_established':False,'biological_truth_assessed':False}
    return qualified,counts,set_rows


def prepare_history(parent,history,history_pin,declaration,declaration_pin,xswap_path,output):
    pins={p:sha(ROOT/p) for p in IMPLEMENTATION}
    old,base_packet=verify(parent,code=False)
    declaration=Path(declaration);decl=gold_packet._read(declaration/'report.json')
    need(gold_packet._sealed(decl) and decl['content_sha256']==declaration_pin
         and decl['source_history_content_sha256']==history_pin
         and decl['original_v3_protocol_report_file_sha256']==sha(Path(parent)/'report.json')
         and decl['v3_metrics_or_outcomes_viewed_before_followup_selection'] is False,'pre-exposure declaration differs')
    need(decl['files']=={p.name:sha(p) for p in declaration.iterdir() if p.is_file() and p.name!='report.json'},
         'declaration source files differ')
    sources=Path(parent)/'sources';original=gold_packet._read(sources/'original_graph.json')
    ordinary,ordinary_counts=memberships(original)
    # The native reader expects the original source file beside the history
    # package. Verify that explicit byte binding before copying or selection.
    hist=load_history_packet(history,expected_content_sha256=history_pin)
    need(hist['report']['source_graph_file_sha256']==sha(sources/'original_graph.json'),'historical original file differs')
    base=__import__('run_inmc_comparison').validate_packet(sources/'inmc',resource_smoke=True)
    _,registry=load_registry(sources/'registry')
    out=new_output(output,parent,history,declaration)
    shutil.copytree(sources,out/'sources');shutil.copytree(history,out/'sources/history')
    qualified,qualified_counts,selection=select_history(out/'sources/history',history_pin,original,ordinary)
    need(selection==gold_packet._read(declaration/'connection_selection.json'),'predeclared connection selection changed')
    sys.path.insert(0,str(Path(xswap_path).resolve()))
    import xswap
    from xswap.permute import permute_edge_list
    packet,coverage=build_features(base,ordinary,qualified,registry,permute_edge_list,
        ordinary_counts=ordinary_counts,qualified_counts=qualified_counts)
    need(digest(packet)==digest(gold_packet._read(declaration/'packet.json')),'predeclared model packet changed')
    for name in ('entities','relations','supervision','candidates','development','masked_gene_pairs'):
        need(digest(packet[name])==digest(base_packet[name]),'shared parent input changed: '+name)
    write_json(out/'packet.json',packet);write_json(out/'coverage.json',coverage)
    write_json(out/'historical_selection.json',selection)
    shutil.copytree(declaration,out/'predeclaration')
    write_json(out/'parent_protocol_report.json',old)
    report=deepcopy(old)
    report.update(created_at=utcnow(),qualification_kind='historical_native_xref_compatible_context',
        historical_source_content_sha256=history_pin,historical_source_report_file_sha256=sha(out/'sources/history/historical_verification.json'),
        predeclaration_content_sha256=declaration_pin,parent_protocol_report_file_sha256=sha(Path(parent)/'report.json'),
        implementation_sha256=pins,controls={**old['controls'],
            'xswap_module_sha256':sha(Path(xswap.__file__).parent/'permute.py'),
            'xswap_backend_sha256':sha(next(Path(xswap.__file__).parent.glob('_xswap_backend*.so')))},
        files={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()})
    report.pop('content_sha256',None)
    need({p:sha(ROOT/p) for p in IMPLEMENTATION}==pins,'implementation changed during historical freeze')
    report['content_sha256']=digest(report);write_json(out/'report.json',report)
    verify(out)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('parent','history','declaration','xswap','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--history-content-sha256',required=True);p.add_argument('--declaration-content-sha256',required=True)
    a=p.parse_args();r=prepare_history(a.parent,a.history,a.history_content_sha256,a.declaration,
        a.declaration_content_sha256,a.xswap,a.out);print(r['content_sha256'])
if __name__=='__main__':main()
