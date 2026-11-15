"""Separately declared fixed-T0 graph sensitivity; no forecast scores are read."""
from pathlib import Path
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

from native_window_build_v1 import BASE, sha, dump, ids_file, run_native


PLAN = {
    'format':'biograph-steward.native-fixed-ontology-sensitivity-plan.v1',
    'created_at':datetime.now(timezone.utc).isoformat(),
    'motivation':'Published LAFA classifier source notes gains can arise through new ancestral relationships with unchanged leaf annotation.',
    'reference_role':'Sensitivity alongside as-written native window, not a replacement or altered primary outcome.',
    'sources':'Exact same frozen April10/November4 humanGAF, native SwissProt sequence intersection, evidence codes Experimental,IC,TAS, NOT handling, forms/extensions/taxa policy.',
    'implementation':'Unchanged author retrieve_terms, propagate_and_ia and classify_ground_truth. T0 labels already use March25 ontology; re-extract/re-propagate T1 source on that same T0 ontology and classify with graph=graph2=T0.',
    'new_term_coverage_cost':'T1 direct GO terms absent from T0 graph are dropped by native extractor. Do not label the resulting missing reference support as experimentally false.',
    'masks':'Preserve both native intersection TOI and fixed-T0 TOI. Recommend common primary-native TOI for comparative scoring via native evaluator update_toi, declared before scoring. Identity exclusion uses union of gainers under both constructions.',
    'outputs':'Future term files and logs stay closed. Emit exact ID/aspect metadata, opaque triple-set counts/hashes, union IDs and sequence-only FASTA/hashes.',
    'no_custom_admission_filter':True,
    'no_outcome_scores_seen':True,
    'no_model_or_GPU_calls':True,
}


def opaque_triples(path):
    """Validate column framing; never decode or print GO bytes."""
    result=set()
    with Path(path).open('rb') as stream:
        assert next(stream).rstrip(b'\r\n')==b'EntryID\tterm\taspect'
        for raw in stream:
            fields=raw.rstrip(b'\r\n').split(b'\t')
            assert len(fields)==3 and fields[2] in (b'F',b'P',b'C')
            result.add(tuple(fields))
    return result


def token_sha(values):
    h=hashlib.sha256()
    for fields in sorted(values):
        h.update(b'\t'.join(fields)+b'\n')
    return h.hexdigest()


def main():
    from Bio import SeqIO
    from tools.learned_combination.reference import lafa_future_identities,read_target_ids
    source=json.loads((BASE/'opaque_sources_v1.json').read_text())['sources']
    native=BASE/'native_reference_v1'
    assert (BASE/'sealed_reference_receipt_v1.json').is_file()
    fixed=BASE/'fixed_t0_sensitivity_v1';fixed.mkdir()
    dump(fixed/'plan.json',PLAN)
    print(json.dumps({'phase':'fixed_T0_sensitivity_plan_frozen_before_processing',
        'sha256':sha(fixed/'plan.json'),'no_outcomes_scored':True}),flush=True)
    obo=source['obo_t0']['file']
    terms=fixed/'t1_terms_on_t0.tsv';prop=fixed/'t1_propagated_on_t0.tsv';ia=fixed/'human_IA_on_t0.tsv'
    commands=[]
    commands.append(run_native('democafa.datacollection.retrieve_terms',
        ['--annot',native/'t1/filtered.gaf.gz','-sgc','Experimental,IC,TAS','-g',obo,'--tsv',terms],fixed,'retrieve_terms'))
    commands.append(run_native('democafa.datacollection.propagate_and_ia',
        ['--terms',terms,'--graph',obo,'--tsv_propagated',prop,'--output_tsv',ia],fixed,'propagate_and_ia'))
    commands.append(run_native('democafa.groundtruth.classify_ground_truth',
        ['--annot_known',native/'t0/train_terms_propagated.tsv','--annot2',prop,
         '--query_file',native/'common/differences_common.fasta','--graph',obo,'--graph2',obo,
         '--out_prefix',fixed/'groundtruth.tsv'],fixed,'classify'))
    metadata={};diagnostics={};fixed_union=set()
    for setting in ('NK','LK','PK'):
        f=fixed/('groundtruth_'+setting+'.tsv')
        with f.open('rb') as stream:by_aspect,rows=lafa_future_identities(stream)
        metadata[setting]={'source_rows':rows,'by_aspect':{a:sorted(v) for a,v in by_aspect.items()}}
        fixed_union.update(set.union(*by_aspect.values()))
        first=opaque_triples(native/'sealed_reference'/('groundtruth_'+setting+'.tsv'))
        second=opaque_triples(f)
        diagnostics[setting]={'native_triples':len(first),'fixed_T0_triples':len(second),
            'shared_triples':len(first&second),'native_only_triples':len(first-second),'fixed_T0_only_triples':len(second-first),
            'native_triple_token_sha256':token_sha(first),'fixed_T0_triple_token_sha256':token_sha(second),
            'interpretation':'Different propagation and term admission scopes; native-only is not automatically ontology-only or biologically false.'}
    assert fixed_union==set(read_target_ids(fixed/'groundtruth_targets.tsv'))
    native_ids=set(read_target_ids(native/'sealed_reference/groundtruth_targets.tsv'))
    union=native_ids|fixed_union
    meta=BASE/'combined_reference_metadata_v1';meta.mkdir()
    ids_file(meta/'union_target_ids.txt',union)
    ids_file(meta/'native_only_target_ids.txt',native_ids-fixed_union)
    ids_file(meta/'fixed_T0_only_target_ids.txt',fixed_union-native_ids)
    dump(meta/'fixed_T0_identity_aspect_frames.json',metadata)
    allseq={};fasta=meta/'union_targets_T0_sequences.fasta'
    with (native/'t0/human_swissprot.fasta').open() as stream, fasta.open('x') as out:
        for record in SeqIO.parse(stream,'fasta'):
            accession=record.id.split('|')[1]
            sequence=str(record.seq)
            allseq[accession]={'residues':len(sequence),'sequence_sha256':hashlib.sha256(sequence.encode('ascii')).hexdigest(),
                'native_first1022_sha256':hashlib.sha256(sequence[:1022].encode('ascii')).hexdigest(),
                'native_residues_used':min(len(sequence),1022),'native_first1022_truncation':len(sequence)>1022,
                'taxon':'NCBITaxon:9606'}
            if accession in union:
                out.write('>'+accession+'\n'+sequence+'\n')
    assert union<=set(allseq)
    dump(meta/'all_human_T0_sequence_records.json',allseq)
    dump(meta/'union_target_sequence_records.json',{p:allseq[p] for p in sorted(union)})
    oldmeta=Path('/data/biograph_steward_research_20261114/learned_combination_v1/sequence_compatibility_v1/sequence_compatibility.json')
    old=json.loads(oldmeta.read_text())['old_forecast_sequence_records']
    compatible={p for p in union&set(old) if allseq[p]['sequence_sha256']==old[p]['sequence_sha256']}
    changed=(union&set(old))-compatible
    needed=union-compatible
    augmentation=needed-native_ids
    ids_file(meta/'cached_forecast_compatible_union_ids.txt',compatible)
    ids_file(meta/'new_or_sequence_changed_union_ids.txt',needed)
    ids_file(meta/'sequence_changed_old_ids.txt',changed)
    ids_file(meta/'additional_inference_beyond_native_ids.txt',augmentation)
    # Exact and model-input-prefix exclusions can now be checked without final labels.
    augmentation_records={}
    with (native/'t0/human_swissprot.fasta').open() as stream, (meta/'new_or_sequence_changed_T0_sequences.fasta').open('x') as out, (meta/'additional_inference_beyond_native.fasta').open('x') as extra:
        for record in SeqIO.parse(stream,'fasta'):
            p=record.id.split('|')[1]
            if p in needed:
                out.write('>'+p+'\n'+str(record.seq)+'\n')
            if p in augmentation:
                extra.write('>'+p+'\n'+str(record.seq)+'\n')
                augmentation_records[p]={**allseq[p],'sequence':str(record.seq),'original_header':record.description}
    dump(meta/'additional_inference_beyond_native_records.json',augmentation_records)
    receipt={'format':'biograph-steward.native-and-fixed-reference.metadata.v1','created_at':datetime.now(timezone.utc).isoformat(),
        'native_reference_receipt_sha256':sha(BASE/'sealed_reference_receipt_v1.json'),'fixed_T0_plan_sha256':sha(fixed/'plan.json'),
        'native_commands':commands,'native_code_unchanged':True,'native_targets':len(native_ids),'fixed_T0_targets':len(fixed_union),
        'target_intersection':len(native_ids&fixed_union),'native_only_targets':len(native_ids-fixed_union),
        'fixed_T0_only_targets':len(fixed_union-native_ids),'union_targets':len(union),
        'union_cached_forecast_sequence_compatible':len(compatible),'union_new_or_sequence_changed':len(needed),
        'union_new_no_old_forecast':len(union-set(old)),'union_sequence_changed_old':len(changed),
        'additional_inference_beyond_native_targets':len(augmentation),
        'diagnostics':diagnostics,'fixed_T0_identity_aspect_frames':metadata,
        'native_TOI_file':str(native/'sealed_reference/groundtruth_terms_of_interest.txt'),
        'native_TOI_sha256':sha(native/'sealed_reference/groundtruth_terms_of_interest.txt'),
        'fixed_T0_TOI_file':str(fixed/'groundtruth_terms_of_interest.txt'),
        'fixed_T0_TOI_sha256':sha(fixed/'groundtruth_terms_of_interest.txt'),
        'recommendation':'Use declared common native TOI for comparative scoring; both files remain closed to agent before final forecast seal.',
        'future_GO_columns_decoded_by_agent':False,'future_TOI_contents_opened_by_agent':False,'outcome_scores_computed':False,
        'metadata_files':{p.name:{'file':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in meta.iterdir()},
        'closed_fixed_reference_files':{p.name:{'file':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in fixed.iterdir() if p.is_file()},
        'interpretation':'Fixed-T0 sensitivity suppresses changing ontology edges but also drops T1 GO identities absent at T0. Native-only triples cannot be equated with error or ontology-only gains.'}
    dump(BASE/'combined_reference_metadata_receipt_v1.json',receipt)
    print(json.dumps({'phase':'native_and_fixed_T0_metadata_sealed','receipt':str(BASE/'combined_reference_metadata_receipt_v1.json'),
        'sha256':sha(BASE/'combined_reference_metadata_receipt_v1.json'),'native_targets':len(native_ids),'fixed_T0_targets':len(fixed_union),
        'union_targets':len(union),'cached_sequence_compatible':len(compatible),'new_or_changed_need_forecasts':len(needed),
        'new_no_old_forecast':len(union-set(old)),'sequence_changed_old':len(changed),'metadata_directory':str(meta)}),flush=True)


if __name__=='__main__':
    main()
