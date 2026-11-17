"""Execute unchanged native helpers with sealed T1 outputs and metadata-only reporting."""
from pathlib import Path
import csv
import gzip
import hashlib
import importlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone

BASE = Path('/data/biograph_steward_research_20261114/contextual_gain_20261115/reference_apr_nov_2026_v1')
OLD_DEPS = Path('/data/biograph_steward_research_20261114/learned_combination_v1/reference_v1/native_deps_v3')
CAFA_DEPS = Path('/home/ubuntu/workspace/scientific-overnight-20261113/cafa-deps')
OLD_CODE = Path('/data/biograph_steward_research_20261114/learned_combination_v1/code_revisions/source_v4')
PYTHON = '/home/ubuntu/workspace/scientific-overnight-20261113/cafa-venv/bin/python'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def ids_file(path, values):
    with Path(path).open('x') as stream:
        stream.write('\n'.join(sorted(values)) + '\n')


def run_native(module, args, directory, role):
    """Keep every native log closed: some author warnings include GO terms."""
    log = directory / (role + '.closed.log')
    command = [PYTHON, '-m', module] + [str(v) for v in args]
    with log.open('x') as stream:
        result = subprocess.run(command, cwd=directory, env=os.environ.copy(),
                                stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        dump(directory / (role + '.failure.json'), {'exit_code': result.returncode,
            'command': command, 'log_sha256': sha(log), 'raw_log_not_opened': True})
        raise RuntimeError('Native helper failed; future log remains sealed: ' + role)
    return {'command': command, 'exit_code': result.returncode,
            'closed_log': str(log), 'closed_log_sha256': sha(log)}


def epoch_commands(folder, gaf, fasta, obo):
    commands = []
    filtered, terms = folder / 'filtered.gaf.gz', folder / 'train_terms.tsv'
    propagated, ia = folder / 'train_terms_propagated.tsv', folder / 'IA.tsv'
    commands.append(run_native('democafa.datacollection.filter_gaf',
        ['-a', gaf, '-q', fasta, '-o', filtered], folder, 'filter_gaf'))
    commands.append(run_native('democafa.datacollection.retrieve_terms',
        ['--annot', filtered, '-sgc', 'Experimental,IC,TAS', '-g', obo, '--tsv', terms], folder, 'retrieve_terms'))
    commands.append(run_native('democafa.datacollection.propagate_and_ia',
        ['--terms', terms, '--graph', obo, '--tsv_propagated', propagated, '--output_tsv', ia], folder, 'propagate_and_ia'))
    return commands


def fixture():
    """Invented annotations exercise admission, aliasing and NK/LK/PK semantics."""
    import pandas as pd
    root = BASE / 'synthetic_native_fixture_v1'
    root.mkdir()
    obo = root / 'fixture.obo'
    terms = [('GO:0003674','molecular_function',None,None),
        ('GO:0005488','molecular_function','GO:0003674',None),
        ('GO:0005515','molecular_function','GO:0005488',None),
        ('GO:1000001','molecular_function','GO:0003674','GO:1999999'),
        ('GO:1000002','molecular_function','GO:0005515',None),
        ('GO:0008150','biological_process',None,None),
        ('GO:1000003','biological_process','GO:0008150',None),
        ('GO:0005575','cellular_component',None,None),
        ('GO:1000004','cellular_component','GO:0005575',None),
        ('GO:1000005','cellular_component','GO:1000004',None)]
    text = 'format-version: 1.2\n\n'
    for term, ns, parent, alt in terms:
        text += f'[Term]\nid: {term}\nname: invented fixture\nnamespace: {ns}\ndef: "invented"\n'
        if parent:
            text += f'is_a: {parent} ! invented\n'
        if alt:
            text += f'alt_id: {alt}\n'
        text += '\n'
    obo.write_text(text)
    fasta = root / 'fixture.fasta'
    fasta.write_text(''.join(f'>sp|P0000{i}|INVENTED OX=9606\nMAAAA{i * "A"}\n' for i in range(1,8)))
    def gaf(path, rows):
        with gzip.open(path,'wt') as stream:
            stream.write('!gaf-version: 2.2\n')
            for protein, term, aspect, evidence, qualifier in rows:
                fields = ['UniProtKB',protein,protein,qualifier,term,'PMID:1',evidence,'',aspect,
                          'invented fixture','','protein','taxon:9606','20260410','UniProt','','']
                stream.write('\t'.join(fields)+'\n')
    old = [('P00001','GO:1000004','C','TAS','located_in'),('P00003','GO:1000004','C','IC','located_in')]
    new = old + [('P00001','GO:1000005','C','IDA','located_in'),
        ('P00002','GO:1000003','P','IMP','involved_in'),('P00003','GO:1999999','F','IDA','enables'),
        ('P00004','GO:0005515','F','IPI','enables'),('P00005','GO:1000002','F','IDA','enables'),
        ('P00006','GO:1000005','C','IDA','NOT|located_in'),('P00007','GO:1000005','C','IEA','located_in')]
    for epoch, rows in (('t0',old),('t1',new)):
        folder = root/epoch;folder.mkdir();source = folder/'input.gaf.gz';gaf(source,rows)
        epoch_commands(folder,source,fasta,obo)
    run_native('democafa.groundtruth.classify_ground_truth',
        ['--annot_known',root/'t0/train_terms_propagated.tsv','--annot2',root/'t1/train_terms_propagated.tsv',
         '--query_file',fasta,'--graph',obo,'--graph2',obo,'--out_prefix',root/'groundtruth.tsv'],root,'classify')
    frames = {setting: pd.read_csv(root/('groundtruth_'+setting+'.tsv'),sep='\t') for setting in ('NK','LK','PK','PK_known')}
    assert set(frames['NK'].EntryID)=={'P00002','P00005'}
    assert set(frames['LK'].EntryID)=={'P00003'} and set(frames['LK'].term)=={'GO:1000001','GO:0003674'}
    assert set(frames['PK'].EntryID)=={'P00001'} and set(frames['PK'].term)=={'GO:1000005'}
    assert set(frames['PK_known'].EntryID)=={'P00001'}
    assert 'P00004' not in set.union(*(set(v.EntryID) for v in frames.values()))
    assert 'P00006' not in set.union(*(set(v.EntryID) for v in frames.values()))
    assert 'P00007' not in set.union(*(set(v.EntryID) for v in frames.values()))
    receipt = {'passed':True,'synthetic_only':True,'checks':['exactID SwissProt filtering','Experimental,IC,TAS native admission',
        'NOT and IEA exclusion','native alt-ID resolution','native propagation','NK/LK/PK/PK_known classification',
        'generic protein-binding-only excluded; specific binding child retained'],
        'real_T1_annotation_rows_processed':False,'files':{str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}}
    dump(root/'receipt.json',receipt)
    return {'file':str(root/'receipt.json'),'sha256':sha(root/'receipt.json'),'passed':True}


def date_metadata_audit(path, cutoff):
    """Decode date/evidence/taxon metadata only, never the GO field bytes."""
    from collections import Counter
    native_codes = {x.encode() for x in ('EXP','IDA','IPI','IMP','IGI','IEP','HTP','HDA','HMP','HGI','HEP','IC','TAS')}
    counts,codes,taxa = Counter(),Counter(),Counter()
    latest = b'00000000'
    with gzip.open(path,'rb') as stream:
        for raw in stream:
            if raw.startswith(b'!'):
                continue
            fields = raw.rstrip(b'\r\n').split(b'\t')
            assert len(fields)==17,'GAF2.2 field count differs'
            date = fields[13]
            assert re.fullmatch(b'[0-9]{8}',date),'Invalid native GAF date'
            latest=max(latest,date);counts['rows']+=1
            counts['rows_dated_after_header_cutoff']+=date>cutoff.encode()
            if fields[0]!=b'UniProtKB' or b'NOT' in fields[3].split(b'|') or fields[6] not in native_codes:
                continue
            counts['native_admitted_rows_before_SwissProt_and_ontology_projection']+=1
            counts['native_admitted_rows_dated_after_header_cutoff']+=date>cutoff.encode()
            counts['native_admitted_rows_with_form_ID']+=bool(fields[16])
            counts['native_admitted_rows_with_extension']+=bool(fields[15])
            codes[fields[6].decode('ascii')]+=1;taxa[fields[12].decode('ascii')]+=1
    assert not counts['native_admitted_rows_dated_after_header_cutoff'],'Native admitted future-dated source rows require review'
    return {'counts':dict(counts),'latest_source_annotation_date':latest.decode('ascii'),
            'cutoff_date':cutoff,'native_evidence_codes':dict(codes),'native_taxa':dict(taxa),
            'GO_columns_decoded':False,'custom_admission_filter_applied':False}


def human_fasta(source, destination):
    from Bio import SeqIO
    records = {}
    with gzip.open(source,'rt') as stream, destination.open('x') as out:
        for record in SeqIO.parse(stream,'fasta'):
            if not re.search(r'(?:^|\s)OX=9606(?:\s|$)',record.description):
                continue
            accession=record.id.split('|')[1]
            assert accession not in records,'duplicate canonical SwissProt accession'
            seq=str(record.seq);records[accession]={'length':len(seq),'sequence_sha256':hashlib.sha256(seq.encode('ascii')).hexdigest()}
            SeqIO.write(record,out,'fasta')
    return records


def main():
    assert Path(sys.executable).resolve()==Path(PYTHON).resolve()
    sources = json.loads((BASE/'opaque_sources_v1.json').read_text())['sources']
    for row in sources.values():
        assert sha(row['file'])==row['sha256']
    capsule = json.loads((BASE/'source_capsule_receipt.json').read_text())
    for name,spec in capsule.items():
        assert sha(BASE/name)==spec['sha256']
    versions = {'python':platform.python_version()}
    for name in ('numpy','pandas','scipy','Bio','networkx','obonet','requests'):
        module=importlib.import_module(name);versions[name]=getattr(module,'__version__','unspecified')
    synthetic=fixture()
    # This receipt closes source/runtime qualification before real T1 processing.
    qualification={'format':'biograph-steward.native-temporal-reference-qualification.v1','created_at':now(),
        'plan_sha256':sha(BASE/'operator_source/new_window_plan_v1.json'),'source_capsule_sha256':sha(BASE/'source_capsule_receipt.json'),
        'opaque_sources_sha256':sha(BASE/'opaque_sources_v1.json'),'sources':sources,'runtime':versions,
        'synthetic_native_fixture':synthetic,'real_T1_terms_processed':False,'native_helper_code_unchanged':True,
        'scope':'Human SwissProt/reference-proteome GAF subset; LAFA-style reconstruction, not author-published release',
        'ontology_limit':'T1 latest official archived/current OBO buildAug5 has contentJuly26; GOA sourceGO-plusOct23 is not silently substituted.'}
    dump(BASE/'construction_qualification_v1.json',qualification)
    print(json.dumps({'phase':'qualified_before_real_T1_processing','receipt':str(BASE/'construction_qualification_v1.json'),
        'sha256':sha(BASE/'construction_qualification_v1.json'),'synthetic_passed':True}),flush=True)
    native_root=BASE/'native_reference_v1';native_root.mkdir()
    audits={};sequence_records={};commands={}
    for epoch,cutoff in (('t0','20260410'),('t1','20261104')):
        folder=native_root/epoch;folder.mkdir()
        fasta=folder/'human_swissprot.fasta'
        sequence_records[epoch]=human_fasta(sources['swissprot_'+epoch+'_fasta']['file'],fasta)
        audits[epoch]=date_metadata_audit(sources['gaf_'+epoch]['file'],cutoff)
        dump(folder/'date_metadata_audit.json',audits[epoch])
        print(json.dumps({'phase':'native_epoch_start','epoch':epoch,'human_SwissProt_sequences':len(sequence_records[epoch]),
            'GAF_GO_columns_decoded_by_agent':False}),flush=True)
        commands[epoch]=epoch_commands(folder,sources['gaf_'+epoch]['file'],fasta,sources['obo_'+epoch]['file'])
        print(json.dumps({'phase':'native_epoch_completed_closed','epoch':epoch}),flush=True)
    common=native_root/'common';common.mkdir()
    commands['compare_fasta']=run_native('democafa.datacollection.compare_fasta',
        [native_root/'t0/human_swissprot.fasta',native_root/'t1/human_swissprot.fasta',common/'differences.fasta'],common,'compare_fasta')
    final=native_root/'sealed_reference';final.mkdir()
    commands['classify']=run_native('democafa.groundtruth.classify_ground_truth',
        ['--annot_known',native_root/'t0/train_terms_propagated.tsv','--annot2',native_root/'t1/train_terms_propagated.tsv',
         '--query_file',common/'differences_common.fasta','--graph',sources['obo_t0']['file'],
         '--graph2',sources['obo_t1']['file'],'--out_prefix',final/'groundtruth.tsv'],final,'classify')
    # Reuse the previously invented-fixture-qualified opaque GO-column reader.
    from tools.learned_combination.reference import lafa_future_identities,read_target_ids
    metadata={};union=set()
    for setting in ('NK','LK','PK'):
        path=final/('groundtruth_'+setting+'.tsv')
        with path.open('rb') as stream:by_aspect,rows=lafa_future_identities(stream)
        metadata[setting]={'source_rows':rows,'by_aspect':{a:sorted(v) for a,v in by_aspect.items()}}
        union.update(set.union(*by_aspect.values()))
    declared=set(read_target_ids(final/'groundtruth_targets.tsv'))
    assert union==declared,'Native target file differs from opaque identity union'
    old_meta=Path('/data/biograph_steward_research_20261114/learned_combination_v1/sequence_compatibility_v1/sequence_compatibility.json')
    old=json.loads(old_meta.read_text())['old_forecast_sequence_records']
    compatible=set()
    for accession in declared & set(old):
        if sequence_records['t0'][accession]['sequence_sha256']==old[accession]['sequence_sha256']:
            compatible.add(accession)
    metadata_root=BASE/'identity_metadata_v1';metadata_root.mkdir()
    ids_file(metadata_root/'all_new_reference_targets.txt',declared)
    ids_file(metadata_root/'old_forecast_compatible_targets.txt',compatible)
    dump(metadata_root/'all_new_reference_target_sequences.json',{p:sequence_records['t0'][p] for p in sorted(declared)})
    dump(metadata_root/'identity_aspect_frames.json',metadata)
    dump(metadata_root/'all_human_swissprot_sequences.json',sequence_records)
    output_pins={str(p.relative_to(native_root)):{'bytes':p.stat().st_size,'sha256':sha(p)}
                 for p in native_root.rglob('*') if p.is_file()}
    receipt={'format':'biograph-steward.native-temporal-reference.sealed.v1','created_at':now(),
        'qualification_file_sha256':sha(BASE/'construction_qualification_v1.json'),'native_commands':commands,
        'native_code_unchanged':True,'future_GO_columns_decoded_by_agent':False,'future_TOI_opened_by_agent':False,
        'future_logs_opened_by_agent':False,'date_metadata_audits':audits,'all_human_reference_targets':len(declared),
        'overlap_old_forecast_accessions':len(declared&set(old)),'old_forecast_sequence_compatible_targets':len(compatible),
        'new_targets_without_old_forecasts':len(declared-set(old)),'sequence_changed_old_targets':len((declared&set(old))-compatible),
        'metadata':metadata,'output_pins':output_pins,'identity_metadata_files':{p.name:sha(p) for p in metadata_root.iterdir()},
        'old_forecast_sequence_receipt_sha256':sha(old_meta),'heldout_outcome_scores_computed':False,
        'limits':['PostMarch annotation window, but priorJuly/AugGOA sourceQC exposure disclosed.',
                  'Generic protein-binding-only native policy preserved; no custom descendant-wide exclusion.',
                  'Human-only native IA is a construction byproduct, not exact global author leaderboard IA.']}
    dump(BASE/'sealed_reference_receipt_v1.json',receipt)
    print(json.dumps({'phase':'native_reference_sealed','receipt':str(BASE/'sealed_reference_receipt_v1.json'),
        'sha256':sha(BASE/'sealed_reference_receipt_v1.json'),'all_human_reference_targets':len(declared),
        'old_forecast_compatible_targets':len(compatible),'new_targets_without_old_forecasts':len(declared-set(old)),
        'metadata_directory':str(metadata_root),'future_GO_columns_decoded_by_agent':False}),flush=True)


if __name__=='__main__':
    main()
