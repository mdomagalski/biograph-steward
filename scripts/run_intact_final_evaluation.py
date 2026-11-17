#!/usr/bin/env python3
"""Prepare, then execute one source-bound IntAct fidelity flow; never retune it.

`prepare` reads only explicit metadata/code/control files and consumed inventory.
`execute` is the sole source-body access entrypoint, requires the externally
recorded freeze SHA, creates its exclusive exposure receipt before any read, and
preserves errors. Development replay is required before reserved preparation.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from http.client import HTTPException, IncompleteRead
from urllib.error import HTTPError
from urllib.request import Request, HTTPRedirectHandler, build_opener

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from biograph_steward.client import digest, utcnow, ENDPOINT, PharosClient, canonical
from scripts.intact_final_common import (DEVELOPMENT, RESERVED, PROTOCOL_SHA, AMENDMENT_SHA,
    sha, seal, load_json, save_new, ordinary, study_ids, provenance_audit,
    assess_alignment, summarize, participant_pair)
from scripts.inspect_intact_development import assess, source_lines, verify_controls_report
from scripts.validate_intact_reader_controls import runtime_bindings as mitab_runtime
from scripts.validate_intact_xml_provenance import runtime_bindings as xml_runtime, verify_controls as verify_xml_controls, parse_transport, assess_xml_summary
from scripts.inspect_intact_xml_development import compare_study, assess_development_xml
from scripts.evaluate_intact_evidence_fidelity import evaluate_rows, field_groups

FORMAT='biograph-steward.intact-final-execution-freeze.v1'
BASE='runs/intact_fidelity_preparation_20261026'
PROTOCOL='docs/evaluations/intact_fidelity_20261026_protocol.json'
AMENDMENT='docs/evaluations/intact_fidelity_20261026_semantic_amendment.json'
PREPARATION='docs/evaluations/intact_fidelity_20261026_preparation.json'
PREPARATION_SHA='e5c35e3f927e62d2c1094c4d19edaf33406940fba26eeadd397c6f156c2af5ea'
XML_DIRECTORY='https://ftp.ebi.ac.uk/pub/databases/intact/2026-10-17/psi25/pmid/2025/'
MAX_XML_BYTES=2*1024*1024
RESERVED_ACCESS_MARKER=ROOT/'runs/intact_final_reserved_access_20261027.json'


def _runtime(control, xml=False):
    runtime=control['runtime_bindings']
    fn=xml_runtime if xml else mitab_runtime
    current=fn(runtime['classes_directory'],runtime['classpath_file'],runtime['java']['executable'])
    if current!=runtime:raise ValueError('Actual official reader/runtime differs from passing controls.')
    return current


def implementation_paths():
    # Explicit code-only roots; never recurse through run/source directories.
    return [Path(__file__), ROOT/'scripts/intact_final_common.py',
        ROOT/'scripts/inspect_intact_development.py',ROOT/'scripts/inspect_intact_xml_development.py',
        ROOT/'scripts/validate_intact_reader_controls.py',ROOT/'scripts/validate_intact_xml_provenance.py',
        ROOT/'scripts/validate_intact_final_controls.py',
        ROOT/'tests/test_intact_final_execution.py',ROOT/'tests/test_intact_final_publication.py',
        ROOT/'scripts/evaluate_intact_evidence_fidelity.py',
        *[p for p in sorted((ROOT/'biograph_steward').glob('*')) if p.is_file() and p.suffix in {'.py','.js','.html'}]]


def prepare(*,split,controls_report,xml_controls_report,consumed_inventory,output,
            synthetic_report,development_report=None):
    ids=study_ids(split)
    output=Path(output).absolute()
    if output.exists() or output.is_symlink():raise ValueError('Choose a new immutable freeze directory.')
    paths=[ordinary(p) for p in (controls_report,xml_controls_report,consumed_inventory,synthetic_report)]
    controls,xml_controls,consumed,synthetic=map(load_json,paths)
    verify_controls_report(controls);verify_xml_controls(xml_controls)
    if consumed.get('format')!='biograph-steward.intact-consumed-inventory.v1' or not consumed.get('scope'):
        raise ValueError('A bounded explicit consumed inventory and incompleteness statement are required.')
    if (synthetic.get('format')!='biograph-steward.intact-final-synthetic-checks.v1'
            or synthetic.get('status')!='passed' or synthetic.get('reserved_bodies_accessed') is not False
            or synthetic.get('content_sha256')!=digest({k:v for k,v in synthetic.items() if k!='content_sha256'})
            or synthetic.get('implementation_sha256')!={str(p):sha(p) for p in implementation_paths() if p.is_file()}):
        raise ValueError('Passing invented final-flow controls are required before access.')
    if sha(ROOT/PROTOCOL)!=PROTOCOL_SHA or sha(ROOT/AMENDMENT)!=AMENDMENT_SHA:
        raise ValueError('Original protocol/amendment changed.')
    if split=='reserved_final':
        if development_report is None:raise ValueError('A passing complete consumed-development replay is required.')
        paths.append(ordinary(development_report));development=load_json(paths[-1])
        if (development.get('format')!='biograph-steward.intact-final-fidelity.v1'
                or development.get('content_sha256')!=digest({k:v for k,v in development.items() if k!='content_sha256'})
                or development.get('status')!='passed' or development.get('assessment_split')!='development_replay'):
            raise ValueError('Use the complete passing development replay, not the old limited result.')
        if development.get('implementation_sha256')!={str(p):sha(p) for p in implementation_paths() if p.is_file()}:
            raise ValueError('Implementation changed after consumed-development replay; recheck before final freeze.')
        devfreeze=ordinary(Path(development_report).parent.parent/'execution_freeze.json')
        declared_devfreeze=verify_freeze(devfreeze,development.get('execution_freeze_sha256'))
        if declared_devfreeze.get('assessment_split')!='development_replay':raise ValueError('Development report is linked to wrong-split freeze.')
        paths.append(devfreeze)
        roweval=development.get('row_evaluation') or {}
        checks=(roweval.get('global_checks') or [])+(development.get('source_preservation_checks') or [])
        metrics=development.get('metrics') or {};den=development.get('source_accounting',{}).get('final_assessment_eligible_rows')
        if (type(den)is not int or den<1 or len(roweval.get('rows') or [])!=den
                or not checks or any(check.get('passed') is not True for check in checks)
                or any(row.get('strict_fidelity') is not True or row.get('completed') is not True for row in roweval.get('rows',[]))
                or any(metrics.get(name,{}).get('numerator')!=den or metrics.get(name,{}).get('denominator')!=den for name in ('coverage','strict_fidelity'))
                or development.get('flow_failures')):
            raise ValueError('Complete passing development row/global/preservation results are required.')
    if sha(ROOT/PREPARATION)!=PREPARATION_SHA:raise ValueError('Original preparation receipt changed.')
    preparation=load_json(ROOT/PREPARATION)  # metadata only, never follow local paths here.
    selected=[]
    for pmid in ids:
        entry=next(item for item in preparation['sources'] if item['publication_id']=='pubmed:'+pmid)
        expected=f'{BASE}/opaque_sources/{pmid}.txt'
        if entry['local_path']!=expected or entry['split']!=('development' if split=='development_replay' else 'reserved_final'):
            # Historical preparation calls the reserved panel `reserved_final`.
            if entry['local_path']!=expected or not (split=='reserved_final' and entry['split'] in {'reserved','final','reserved_final'}):
                raise ValueError('Original fixed source catalog differs.')
        selected.append(deepcopy(entry))
    mr,xr=_runtime(controls),_runtime(xml_controls,True)
    code={str(p):sha(p) for p in implementation_paths() if p.is_file()}
    metadata={str(p):sha(p) for p in [*paths,ROOT/PROTOCOL,ROOT/AMENDMENT,ROOT/PREPARATION]}
    safe_consumed={f'runs/intact_development_inspection_20261026/{pmid}_reader.jsonl' for pmid in DEVELOPMENT}
    safe_consumed.add('runs/intact_provenance_metadata_20261026_attempt_02/report.json')
    declared=consumed.get('bindings',[])
    if any(not isinstance(item,dict) or set(item)!={'path','sha256'} or item['path'] not in safe_consumed for item in declared):
        raise ValueError('Consumed bindings require the exact declared safe development metadata paths.')
    for item in declared:
        path=ordinary(ROOT/item['path'])
        if sha(path)!=item['sha256']:raise ValueError('Consumed reference binding changed.')
        metadata[str(path)]=item['sha256']
    freeze={'python_runtime':{'executable':str(Path(sys.executable).resolve()),'sha256':sha(Path(sys.executable).resolve()),'version':sys.version},'format':FORMAT,'created_at':utcnow(),'pre_access':True,'assessment_split':split,
        'publication_ids':list(ids),'source_catalog':selected,'implementation_sha256':code,
        'metadata_sha256':metadata,'mitab_runtime':mr,'xml_runtime':xr,
        'controls_report':str(paths[0]),'xml_controls_report':str(paths[1]),'consumed_inventory':str(paths[2]),
        'synthetic_report':str(paths[3]),'development_report':str(Path(development_report).absolute()) if development_report else None,
        'protocol_sha256':PROTOCOL_SHA,'amendment_sha256':AMENDMENT_SHA,
        'xml_policy':{'directory':XML_DIRECTORY,'maximum_bytes':MAX_XML_BYTES,'redirects':False,
                      'timeout_seconds':90,'attempts':1,'format':'PSI-MI XML2.5.4'},
        'flow_policy':{'batching':'one exact unordered eligible primary-accession pair; lexical pair order',
            'question_template':'qualified_assay_evidence.v1','focus':None,'results':'all attached rows, all local states; no cap',
            'cohort_profile':'ppi','ppi_limit_per_target':5000,'other_context_limits':0,
            'identity_policy':'exact UniProt accession; no synonyms/isoform collapse or repairs',
            'pharos_endpoint':ENDPOINT,'pharos_timeout':30,'pharos_retries':0,'cache':None,
            'failures':'all source-eligible rows retained as misses; no failed-row reselection',
            'lineage':'known consumed identity/components excluded without replacement; ambiguous dataset statement stops scoring',
            'empty':'not_evaluable_not_success','new_model_arm':False},
        'development_saved_cohort':'runs/intact_cohort_source_20261026' if split=='development_replay' else None,
        'reserved_access_marker':str(RESERVED_ACCESS_MARKER),'reserved_bodies_accessed':False,'scientific_accuracy_measured':False}
    if split=='development_replay':
        # Exact consumed snapshot only; preserve its ordinary source trace.
        freeze['development_saved_cohort_sha256']={str(ROOT/'runs/intact_cohort_source_20261026'/name):sha(ROOT/'runs/intact_cohort_source_20261026'/name)
            for name in ('snapshot.json','graph.json','run_manifest.json')}
    if split=='development_replay':
        freeze['development_xml_sha256']={str(ROOT/f'runs/intact_xml_development_inspection_20261026_attempt_01/{pmid}.xml'):sha(ROOT/f'runs/intact_xml_development_inspection_20261026_attempt_01/{pmid}.xml') for pmid in ids}
    freeze=seal(freeze);output.mkdir(parents=True,exist_ok=False)
    save_new(output/'execution_freeze.json',freeze)
    return freeze


def verify_freeze(path,expected):
    path=ordinary(path)
    if sha(path)!=expected:raise ValueError('Explicit execution-freeze SHA differs.')
    freeze=load_json(path)
    if (freeze.get('format')!=FORMAT or freeze.get('pre_access') is not True
            or freeze.get('content_sha256')!=digest({k:v for k,v in freeze.items() if k!='content_sha256'})
            or freeze.get('publication_ids')!=list(study_ids(freeze.get('assessment_split')))):
        raise ValueError('Invalid exact-panel immutable execution freeze.')
    actual_python={'executable':str(Path(sys.executable).resolve()),'sha256':sha(Path(sys.executable).resolve()),'version':sys.version}
    if freeze.get('python_runtime')!=actual_python:raise ValueError('Python runtime changed after freeze.')
    for item,pin in {**freeze['metadata_sha256'],**freeze['implementation_sha256'],**freeze.get('development_saved_cohort_sha256',{}),**freeze.get('development_xml_sha256',{})}.items():
        if sha(ordinary(item))!=pin:raise ValueError('Frozen code/metadata changed: '+item)
    _runtime(load_json(freeze['controls_report']));_runtime(load_json(freeze['xml_controls_report']),True)
    return freeze


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Fixed XML source may not redirect.')


def fetch_xml(pmid,output):
    url=XML_DIRECTORY+pmid+'.xml'
    opener=None
    """One allowlisted bounded request; save opaque bytes and receipt before parse."""
    if pmid not in RESERVED:
        raise ValueError("Reserved/unknown source or alternate URL is forbidden.")
    output = Path(output)
    start = {"publication_id": pmid, "url": url, "started_at": utcnow(),
             "maximum_bytes": MAX_XML_BYTES, "attempt": 1, "redirects": False, "retries": False}
    save_new(output / (pmid + "_retrieval_started.json"), start)
    receipt = deepcopy(start)
    body = b""
    try:
        opener = opener or build_opener(NoRedirect())
        request = Request(url, headers={"User-Agent": "BioGraph-Steward/IntAct-final-provenance", "Accept-Encoding": "identity"})
        with opener.open(request, timeout=90) as response:
            receipt["status"] = response.status
            receipt["headers"] = dict(response.headers.items())
            receipt["final_url"] = response.geturl()
            if response.status != 200 or response.geturl() != url:
                raise ValueError("Exact source did not return HTTP200 without redirect.")
            if response.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
                raise ValueError("Compressed transport is outside the bounded opaque-byte contract.")
            declared = response.headers.get("Content-Length")
            if declared is not None and (not declared.isdigit() or int(declared) > MAX_XML_BYTES):
                raise ValueError("Declared XML size exceeds the fixed bound or is invalid.")
            try:
                body = response.read(MAX_XML_BYTES + 1)
            except IncompleteRead as error:
                body = error.partial[:MAX_XML_BYTES + 1]
                with (output / (pmid + ".partial.xml")).open("xb") as stream:
                    stream.write(body)
                receipt["partial_bytes"] = len(body)
                receipt["partial_sha256"] = hashlib.sha256(body).hexdigest()
                raise ValueError("Incomplete HTTP body; partial opaque bytes retained.") from error
            with (output / (pmid + ".xml")).open("xb") as stream:
                stream.write(body)
            receipt["bytes"] = len(body); receipt["sha256"] = hashlib.sha256(body).hexdigest()
            if len(body) > MAX_XML_BYTES:
                raise ValueError("XML body exceeds the fixed bound; truncated opaque evidence preserved.")
            if declared is not None and int(declared) != len(body):
                raise ValueError("XML byte count differs from HTTP Content-Length.")
            receipt["outcome"] = "opaque_bytes_saved_not_decoded"
    except (OSError, ValueError, HTTPError, HTTPException) as error:
        receipt["outcome"] = "failed"; receipt["error"] = str(error)
        if isinstance(error, HTTPError):
            receipt["status"] = error.code; receipt["headers"] = dict(error.headers.items())
        save_new(output / (pmid + "_http_receipt.json"), receipt)
        raise
    save_new(output / (pmid + "_http_receipt.json"), receipt)
    return output/(pmid+".xml")


def java_read(runtime,class_name,source,prefix):
    cp=os.pathsep.join([runtime['classes_directory'],*[x['path'] for x in runtime['dependency_jars']]])
    try:
        result=subprocess.run([runtime['java']['executable'],'-cp',cp,class_name,str(source)],capture_output=True,timeout=120,check=False)
    except subprocess.TimeoutExpired as exc:
        Path(str(prefix)+'.jsonl').write_bytes(exc.stdout or b'');Path(str(prefix)+'.stderr').write_bytes(exc.stderr or b'')
        raise ValueError('Official reader timed out; partial streams retained.') from exc
    Path(str(prefix)+'.jsonl').write_bytes(result.stdout);Path(str(prefix)+'.stderr').write_bytes(result.stderr)
    return result


def inspect_sources(freeze,freeze_path,expected_sha,output):
    records,ledger,xml_by_study,files,catalog,studies=[],[],{},{},[],[]
    for entry in freeze['source_catalog']:
        verify_freeze(freeze_path,expected_sha)
        pmid=entry['publication_id'].removeprefix('pubmed:')
        save_new(output/(pmid+'_exposure_started.json'),{'created_at':utcnow(),'publication_id':pmid,
            'execution_freeze_sha256':sha(freeze_path),'status':'consumed_before_any_body_read_or_hash',
            'assessment_split':freeze['assessment_split']})
        verify_freeze(freeze_path,expected_sha)
        source=ordinary(ROOT/entry['local_path']);raw=source.read_bytes()
        if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
            raise ValueError('Original source bytes differ; preserve exposure without replacement.')
        (output/(pmid+'.txt')).write_bytes(raw)
        verify_freeze(freeze_path,expected_sha)
        parsed=java_read(freeze['mitab_runtime'],'org.biograph.IntactReader',source,output/(pmid+'_reader'))
        verify_freeze(freeze_path,expected_sha)
        if parsed.returncode:raise ValueError('Official MITAB reader failed; preserve consumed status.')
        rows=[json.loads(line) for line in parsed.stdout.decode('utf-8').splitlines()]
        lines=source_lines(raw)
        if len(rows)!=len(lines):raise ValueError('Every physical row must be accounted for.')
        for number,(line,row) in enumerate(zip(lines,rows),1):
            if row['line_number']!=number or row['raw_line']!=line or row['raw_cells']!=line.split('\t'):
                raise ValueError('Official raw-cell/orientation/row locator mismatch.')
            assessment=assess(row,pmid)
            item={'publication_id':'pubmed:'+pmid,'artifact_sha256':entry['sha256'],'release':'2026-10-17',
                'source_line':number,'raw_row_sha256':hashlib.sha256(line.encode()).hexdigest(),**assessment}
            ledger.append(item);records.append({'publication_id':'pubmed:'+pmid,'artifact_sha256':entry['sha256'],
                'source_file':'source/'+pmid+'.txt','reader_file':'reader/'+pmid+'.jsonl','reader_record':row})
        verify_freeze(freeze_path,expected_sha)
        if freeze['assessment_split']=='development_replay':
            xml=ordinary(ROOT/f'runs/intact_xml_development_inspection_20261026_attempt_01/{pmid}.xml')
            (output/(pmid+'.xml')).write_bytes(xml.read_bytes())
        else:xml=fetch_xml(pmid,output)
        verify_freeze(freeze_path,expected_sha)
        result=java_read(freeze['xml_runtime'],'org.biograph.IntactXmlReader',xml,output/(pmid+'_xml_reader'))
        verify_freeze(freeze_path,expected_sha)
        xml_records,summary,_=parse_transport(result.stdout)
        gate=assess_development_xml(summary,xml_records,result.returncode)
        if gate['quarantined']:raise ValueError('Official XML reader diagnostics block reference projection.')
        expected_source=summary.get('input_sha256')
        if expected_source!=sha(xml) or summary.get('input_bytes')!=xml.stat().st_size:
            raise ValueError('XML reader mandatory source fingerprint/byte count mismatch.')
        files['provenance/'+pmid+'.xml']=xml.read_bytes()
        files['provenance/'+pmid+'_reader.jsonl']=result.stdout
        xml_by_study[pmid]=xml_records
        refs=[{'ledger':l,'reader_record':r['reader_record']} for l,r in zip(ledger,records) if l['publication_id']=='pubmed:'+pmid]
        alignment=compare_study(pmid,refs,xml_records)
        save_new(output/(pmid+'_alignment.json'),alignment)
        errors=assess_alignment(alignment,refs,xml_records)
        if errors:save_new(output/(pmid+'_projection_errors.json'),errors);raise ValueError('Unresolved cross-format reference projection; no repair or final score.')
        source_name,reader_name='source/'+pmid+'.txt','reader/'+pmid+'.jsonl'
        files[source_name]=raw;files[reader_name]=parsed.stdout
        catalog.append({'publication_id':'pubmed:'+pmid,'artifact_sha256':entry['sha256'],
            'source_file':source_name,'reader_file':reader_name,'reader_sha256':hashlib.sha256(parsed.stdout).hexdigest()})
        studies.append({'publication_id':'pubmed:'+pmid,'physical_rows':len(rows),
            'source_eligible_rows':sum(item['eligible'] for item in ledger if item['publication_id']=='pubmed:'+pmid),
            'xml_evidence_objects':len(xml_records)})
    return records,ledger,xml_by_study,files,catalog,studies


def claim_reserved_execution(freeze_path,expected_sha):
    # One marker across every output directory prevents a second held-out run
    # from being relabeled unseen after replacing the freeze or output name.
    save_new(RESERVED_ACCESS_MARKER,{'created_at':utcnow(),'execution_freeze':str(freeze_path),
        'execution_freeze_sha256':expected_sha,'status':'reserved_panel_consumed_if_any_subsequent_failure',
        'publication_ids':list(RESERVED)})


def execute(freeze_path,expected_sha):
    freeze_path=ordinary(freeze_path);freeze=verify_freeze(freeze_path,expected_sha)
    output=freeze_path.parent/'execution'
    if output.exists() or output.is_symlink():raise ValueError('This fixed execution already started; do not rerun.')
    if freeze['assessment_split']=='reserved_final':
        if freeze.get('reserved_access_marker')!=str(RESERVED_ACCESS_MARKER):raise ValueError('The fixed reserved access marker changed.')
        claim_reserved_execution(freeze_path,expected_sha)
    output.mkdir(exist_ok=False)
    save_new(output/'started.json',{'created_at':utcnow(),'freeze_sha256':expected_sha,
        'assessment_split':freeze['assessment_split'],'state':'one_fixed_execution_no_rerun_or_replacement'})
    try:
        result=_execute(freeze,freeze_path,expected_sha,output)
    except BaseException as exc:
        save_new(output/'failure.json',{'created_at':utcnow(),'status':'stopped_preserved_failure',
            'assessment_split':freeze['assessment_split'],'exception_type':type(exc).__name__,'error':str(exc),
            'reserved_panel_may_now_be_consumed':freeze['assessment_split']=='reserved_final','score_available':False})
        raise
    save_new(output/'report.json',seal(result));return result


def _execute(freeze,freeze_path,expected_sha,output, *, source_loader=None,
             lineage_auditor=None, freeze_verifier=None, pharos_factory=None,
             publication_extras=None, inspection_status=None, eligible_check=None,
             fatal_exception=None):
    # Explicit internal dependency hooks support a separately validated fresh
    # contract. Public prepare/execute retain their original exact-panel guards.
    load_sources=source_loader or inspect_sources
    audit_sources=lineage_auditor or provenance_audit
    verify_execution=freeze_verifier or verify_freeze
    from biograph_steward import intact_final_publication as final
    from biograph_steward.assay_attachment import attach_assay
    from biograph_steward.assay_questions import answer_assay_question
    from biograph_steward.questions import save_answer
    from biograph_steward.reviews import read_run
    from biograph_steward.gold_packet import export_packet,load_packet
    from biograph_steward.construction import run_construction,publish_construction
    records,ledger,xml,files,catalog,studies=load_sources(freeze,freeze_path,expected_sha,output)
    audit=audit_sources(xml,records,load_json(freeze['consumed_inventory']))
    excluded=set(audit['excluded_publication_ids'])
    if freeze['assessment_split']=='development_replay':
        # The four consumed studies are intentionally replayed for engineering
        # controls; their self-exposure is disclosed, never a fresh final score.
        audit['development_replay_retains_consumed_studies_for_engineering_check']=True
        audit['final_exclusion_policy_not_applied_to_consumed_rehearsal']=True
        excluded=set()
    save_new(output/'provenance_overlap.json',audit)
    if audit['ambiguous_dataset_statements']:raise ValueError('Qualified dataset lineage requires adjudication; stop before scoring.')
    source_count=sum(item['eligible'] for item in ledger)
    references=[{'ledger':l,'reader_record':r['reader_record']} for l,r in zip(ledger,records)]
    finalrefs=[r for r in references if r['ledger']['publication_id'].removeprefix('pubmed:') not in excluded]
    eligible=[r for r in finalrefs if r['ledger']['eligible']]
    if eligible_check is not None:eligible_check(references,eligible)
    ledgerraw=''.join(canonical(item)+'\n' for item in ledger).encode()
    inspection={'status':inspection_status or ('development_full_flow_replay_not_final_score' if freeze['assessment_split']=='development_replay' else 'final_inspected_not_fidelity_scored'),
        'publication_ids':freeze['publication_ids'],'studies':studies,'bindings':{
        'controls_report_sha256':sha(freeze['controls_report']),'runtime_bindings':freeze['mitab_runtime'],'execution_freeze_sha256':sha(freeze_path)}}
    files.update({'row_ledger.jsonl':ledgerraw,'protocol.json':(ROOT/PROTOCOL).read_bytes(),
        'semantic_amendment.json':(ROOT/AMENDMENT).read_bytes(),'inspection_report.json':(canonical(inspection)+'\n').encode(),
        'controls_report.json':Path(freeze['controls_report']).read_bytes(),
        'xml_controls_report.json':Path(freeze['xml_controls_report']).read_bytes(),
        'execution_freeze.json':freeze_path.read_bytes(),
        'LICENSE.md':(ROOT/f'{BASE}/sources/IntAct_license.md').read_bytes()})
    bindings={'protocol_sha256':PROTOCOL_SHA,'amendment_sha256':AMENDMENT_SHA,
        'result_sha256':hashlib.sha256(files['inspection_report.json']).hexdigest(),
        'ledger_sha256':hashlib.sha256(ledgerraw).hexdigest(),
        'source_sha256':{c['publication_id'].removeprefix('pubmed:'):c['artifact_sha256'] for c in catalog},
        'reader_sha256':{c['publication_id'].removeprefix('pubmed:'):c['reader_sha256'] for c in catalog},
        'reader_runtime':freeze['mitab_runtime'],'controls_report_sha256':sha(freeze['controls_report']),
        'xml_reader_runtime':freeze['xml_runtime'],'xml_controls_report_sha256':sha(freeze['xml_controls_report']),
        'publication_ids':freeze['publication_ids'],'assessment_split':freeze['assessment_split'],
        'execution_freeze_sha256':sha(freeze_path),'release':'2026-10-17'}
    if publication_extras is not None:
        extra_files,extra_bindings=publication_extras(freeze,output)
        if set(extra_files)&set(files) or set(extra_bindings)&set(bindings):
            raise ValueError('Additional publication bindings may not replace original source fields.')
        files.update(extra_files);bindings.update(extra_bindings)
    final.publish_material(files,catalog,bindings,inspection,output/'publication')
    grouped=defaultdict(list)
    for ref in eligible:grouped[participant_pair(ref['reader_record'])].append(ref)
    # The development replay uses the complete saved cohort, with original trace.
    batches=[('development',eligible)] if freeze['assessment_split']=='development_replay' and eligible else [(str(i).zfill(4),grouped[p]) for i,p in enumerate(sorted(grouped),1)]
    evaluated_rows=[];globals=[];failures=[];preservation=[]
    for name,refs in batches:
        verify_execution(freeze_path,expected_sha)
        folder=output/('batch_'+name);folder.mkdir()
        empty=None
        try:
            if freeze['assessment_split']=='development_replay':
                saved=load_json(ROOT/freeze['development_saved_cohort']/'snapshot.json')
                publish_construction(saved,folder/'cohort')
            else:
                ids=sorted({x['id'] for ref in refs for side in ('a','b') for x in ((ref['reader_record'].get('source_fields') or {}).get('primary_ids_'+side) or {}).get('values',[]) if ((x.get('database') or {}).get('name') or '').lower()=='uniprotkb'})
                run_construction(pharos_factory(folder) if pharos_factory else PharosClient(endpoint=ENDPOINT,cache_dir=None,timeout=30,retries=0),
                    {'accessions':ids,'focus_uniprot':ids[0],'profile':'ppi','relations':['interactions']},folder/'cohort')
            attach_assay(folder/'cohort',output/'publication',folder/'attached')
            _,_,graph=read_run(folder/'attached')
            answer=answer_assay_question(graph,source_run=str(folder/'attached'))
            save_answer(answer,folder/'answer');export_packet(folder/'attached',folder/'packet');load_packet(folder/'packet')
            wanted={tuple(r['ledger'][k] for k in ('publication_id','artifact_sha256','source_line')) for r in refs}
            chosen=lambda row:tuple(row.get('source',{}).get(k) for k in ('publication_id','artifact_sha256','source_line')) in wanted
            obs=[row for row in graph['assay_observations'] if chosen(row)]
            results=[row for row in answer['results'] if chosen(row['source_observation'])]
            packet=[json.loads(line) for line in (folder/'packet/assay_observations.jsonl').read_text().splitlines()]
            exported=[json.loads(line) for line in (folder/'answer/assay_evidence.jsonl').read_text().splitlines()]
            expected_cohort={target['id'] for target in graph['targets']}
            oracle_selected=[ref for ref in references if ref['ledger']['eligible'] and
                {'UniProtKB:'+x['id'] for side in ('a','b') for x in ((ref['reader_record'].get('source_fields') or {}).get('primary_ids_'+side) or {}).get('values',[])
                 if ((x.get('database') or {}).get('name') or '').lower()=='uniprotkb'}<=expected_cohort]
            from scripts.intact_final_common import output_inventory_checks
            globals+=output_inventory_checks(oracle_selected,graph['assay_observations'],answer['results'],packet,exported)
            edges=[edge for edge in graph['edges'] if edge.get('id') in {row['graph_edge_id'] for row in obs}]
            evaluation=evaluate_rows(refs,obs,results,[row for row in packet if chosen(row)],
                [row for row in exported if chosen(row['source_observation'])],(folder/'answer/report.html').read_text(),
                graph_edges=edges,columns=field_groups(),answer_bindings={k:answer[k] for k in ('answer_sha256','graph_basis_sha256','snapshot_sha256','assay_publication_sha256','assay_attachment_sha256','source_run')})
            for prefix in (folder/'attached/assay_source',folder/'packet/source/assay_source'):
                for filename,raw in files.items():
                    preservation.append({'batch':name,'file':str(prefix/filename),'passed':(prefix/filename).read_bytes()==raw})
            save_new(folder/'evaluation.json',evaluation)
            evaluated_rows+=evaluation['rows'];globals+=evaluation['global_checks']
        except Exception as exc:
            if fatal_exception is not None and isinstance(exc,fatal_exception):raise
            failure={'batch':name,'error_type':type(exc).__name__,'error':str(exc),'eligible_rows':len(refs)}
            failures.append(failure);save_new(folder/'failure.json',failure)
            empty=evaluate_rows(refs,[],[],[],[],'',graph_edges=[],columns=field_groups())
            evaluated_rows+=empty['rows'];globals+=empty['global_checks']
    evaluation={'rows':evaluated_rows,'global_checks':globals}
    metrics=summarize(evaluation,finalrefs,freeze['publication_ids'])
    verify_execution(freeze_path,expected_sha)
    passed=bool(eligible) and not failures and all(x['passed'] for x in globals+preservation) and metrics['strict_fidelity']['numerator']==len(eligible)
    return {'format':'biograph-steward.intact-final-fidelity.v1','created_at':utcnow(),
        'status':'passed' if passed else 'not_evaluable' if not eligible else 'failed',
        'assessment_split':freeze['assessment_split'],'execution_freeze_sha256':sha(freeze_path),
        'implementation_sha256':freeze['implementation_sha256'],
        'source_accounting':{'physical_rows':len(ledger),'evidence_rows':sum(r['kind']=='evidence' for r in ledger),
            'source_eligible_rows_before_study_exclusions':source_count,
            'study_excluded_source_eligible_rows':source_count-len(eligible),'final_assessment_eligible_rows':len(eligible),
            'excluded_publication_ids':sorted(excluded)},
        'metrics':metrics,'row_evaluation':evaluation,'source_preservation_checks':preservation,'flow_failures':failures,
        'model_calls':0,'gpu_runs':0,'biological_accuracy_measured':False,'study_independence':'unverified',
        'interpretation':'Bounded source preservation through official readers, ordinary Pharos attachment, readable answer and full source export. Not scientific accuracy or biological prediction gain.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--split',choices=['development_replay','reserved_final'],required=True)
    for flag in ('controls-report','xml-controls-report','consumed-inventory','synthetic-report','output'):
        p.add_argument('--'+flag,type=Path,required=True)
    p.add_argument('--development-report',type=Path)
    p=sub.add_parser('execute');p.add_argument('--freeze',type=Path,required=True);p.add_argument('--expected-sha256',required=True)
    args=parser.parse_args(argv)
    try:
        result=prepare(split=args.split,controls_report=args.controls_report,xml_controls_report=args.xml_controls_report,
            consumed_inventory=args.consumed_inventory,synthetic_report=args.synthetic_report,development_report=args.development_report,output=args.output) if args.command=='prepare' else execute(args.freeze,args.expected_sha256)
    except Exception as exc:
        print(json.dumps({'status':'stopped','error_type':type(exc).__name__,'error':str(exc)}));return 2
    print(json.dumps({'status':result.get('status','freeze_written'),'content_sha256':result.get('content_sha256')}));return 0 if result.get('status') in {None,'passed','not_evaluable'} else 1

if __name__=='__main__':raise SystemExit(main())
