"""Outcome-blind, entity-given BioRED case preparation from author artifacts.

The final relation columns are never decoded here. The released title/abstract
and gold entity annotations are allowed task inputs; relation/novelty/direction
annotations are outcomes and are replaced with literal None for inference.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import zipfile

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha

FORMAT = 'biograph-steward.biored-agent-frame.v1'
DATA_SHA = '29aa0b2060f9d3dc66d9452412e741158f69fb06021c7e326174cb3f1a1c4a85'
MODEL_ARCHIVE_SHA = 'f7c85ab60e9d61f3d06c682e432ac0a16ba56844a6389ec2941b23d567d9be00'
AUTHOR_COMMIT = 'fc090435fa8198187ab5145da26d8abf01000131'
SEED = 'biograph-biored-agent-20261113-v1'
PARTITIONS = {'development': ('dev', 32), 'test': ('bc8_test', 128)}
RELATIONS = ('None', 'Association', 'Bind', 'Comparison', 'Conversion',
             'Cotreatment', 'Drug_Interaction', 'Negative_Correlation', 'Positive_Correlation')
GENE_PAIRS = {('ChemicalEntity', 'GeneOrGeneProduct'),
              ('DiseaseOrPhenotypicFeature', 'GeneOrGeneProduct'),
              ('GeneOrGeneProduct', 'GeneOrGeneProduct')}


def need(condition, message):
    if not condition:
        raise ValueError('BioRED frame: ' + message)


def ranked(*parts):
    return hashlib.sha256((SEED + '\0' + '\0'.join(parts)).encode()).hexdigest()


def source_inputs(raw):
    """Read only permitted native text/entity lines; ignore all relation lines."""
    documents = {}
    for line in raw.splitlines():
        if b'|t|' in line or b'|a|' in line:
            pmid, kind, text = line.split(b'|', 2)
            need(pmid.isdigit() and kind in {b't', b'a'}, 'invalid native document identity.')
            doc = documents.setdefault(pmid.decode(), {'pmid': pmid.decode(), 'entities': []})
            key = 'title' if kind == b't' else 'abstract'
            need(key not in doc, 'duplicate native text.')
            doc[key] = text.decode()
        else:
            columns = line.split(b'\t', 6)
            # Native entity annotations have numeric character offsets. A
            # relation/subject line has no such numeric second/third fields.
            if len(columns) != 6 or not columns[1].isdigit() or not columns[2].isdigit():
                continue
            pmid, start, end, surface, kind, identifier = [x.decode() for x in columns]
            need(pmid in documents, 'entity precedes native title.')
            # Author convert_pubtator_2_tsv.py explicitly splits BioRED IDs on
            # comma/semicolon (not |, which belongs to variant identifiers).
            # Keep the unsplit original alongside that native membership.
            normalized = {'Chemical':'ChemicalEntity', 'Disease':'DiseaseOrPhenotypicFeature',
                          'Gene':'GeneOrGeneProduct'}.get(kind, kind)
            documents[pmid]['entities'].append({'start': int(start), 'end': int(end),
                'text': surface, 'type': normalized, 'native_type': kind, 'id': identifier,
                'native_ids': sorted({x.strip('*') for x in re.split(r'[,;]', identifier)})})
    for doc in documents.values():
        need('title' in doc and 'abstract' in doc, 'incomplete native document.')
        doc['text'] = doc['title'] + ' ' + doc['abstract']
        for entity in doc['entities']:
            need(doc['text'][entity['start']:entity['end']] == entity['text'],
                 'native mention offsets do not bind title/abstract.')
    return documents


def masked_candidates(raw):
    """Preserve native first six columns; opaque outcome bytes are discarded."""
    cases = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        columns = line.split(b'\t', 6)
        need(len(columns) == 7, 'expected native six input fields followed by outcomes.')
        inputs = [part.decode() for part in columns[:6]]
        pmid, type1, type2, id1, id2, text = inputs
        need(pmid.isdigit() and id1 and id2 and text, 'missing native input.')
        if (type1, type2) not in GENE_PAIRS:
            continue
        identity = {'pmid': pmid, 'type1': type1, 'type2': type2, 'id1': id1, 'id2': id2}
        cases.append({'id': 'biored-case:' + digest(identity)[:24], **identity,
            'author_tsv_line': line_number, 'model_text': text,
            'masked_tsv': b'\t'.join(columns[:6] + [b'None', b'None', b'None']).decode()})
    need(cases and len({r['id'] for r in cases}) == len(cases), 'empty or duplicate native candidate frame.')
    return cases


def prepare(data_zip, model, author_source, output, *, partition):
    data_zip, model, author_source, output = map(Path, (data_zip, model, author_source, output))
    need(partition in PARTITIONS, 'unknown partition.')
    need(sha(data_zip) == DATA_SHA, 'official dataset archive pin differs.')
    need(not output.exists(), 'choose a new output directory.')
    suffix, count = PARTITIONS[partition]
    tsv_member = 'bioredirect/processed/' + suffix + '.tsv'
    pubtator_member = 'bioredirect/bioredirect_' + suffix + '.pubtator'
    with zipfile.ZipFile(data_zip) as archive:
        tsv_raw, pubtator_raw = archive.read(tsv_member), archive.read(pubtator_member)
    documents = source_inputs(pubtator_raw)
    candidates = masked_candidates(tsv_raw)
    grouped = defaultdict(list)
    for row in candidates:
        need(row['pmid'] in documents, 'candidate has no native document.')
        doc = documents[row['pmid']]
        for key, entity_type in (('id1', row['type1']), ('id2', row['type2'])):
            need(any(row[key] in e['native_ids'] and e['type'] == entity_type for e in doc['entities']),
                 'native pair lacks exact ID/type in entity annotations.')
        grouped[row['pmid']].append(row)
    selected_pmids = sorted(grouped, key=lambda p: ranked(partition, 'document', p))[:count]
    need(len(selected_pmids) == count, 'too few eligible native documents.')
    selected = []
    unit_provenance = None
    for pmid in selected_pmids:
        row = min(grouped[pmid], key=lambda r: ranked(partition, 'pair', r['id']))
        row = {**row, 'document': documents[pmid], 'source_url': 'https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/'}
        from .passages import source_units
        units, provenance = source_units(row['document'], author_source)
        row['document']['source_units'] = units
        need(unit_provenance is None or unit_provenance == provenance, 'source-unit helper differs across cases.')
        unit_provenance = provenance
        selected.append(row)
    model_files = {p.name: sha(p) for p in sorted(model.iterdir()) if p.is_file()}
    code_files = {p.relative_to(author_source).as_posix(): sha(p) for p in sorted(author_source.rglob('*.py'))}
    need({'out_bioredirect_model.pth', 'config.json', 'model.safetensors', 'vocab.txt'} <= set(model_files),
         'incomplete official model artifact.')
    need({'models.py', 'data_processor.py', 'evaluation.py', 'run_exp.py'} <= set(code_files),
         'incomplete official source artifact.')
    output.mkdir(parents=True)
    write_json(output / 'cases.json', selected)
    (output / 'masked.tsv').write_text('\n'.join(r['masked_tsv'] for r in selected) + '\n')
    report = {'format': FORMAT, 'created_at': utcnow(), 'partition': partition,
        'data_archive_sha256': DATA_SHA, 'tsv_member': tsv_member,
        'tsv_member_sha256': hashlib.sha256(tsv_raw).hexdigest(),
        'native_pubtator_member': pubtator_member,
        'native_pubtator_sha256': hashlib.sha256(pubtator_raw).hexdigest(),
        'eligible_documents': len(grouped), 'eligible_native_candidate_pairs': len(candidates),
        'selected_documents': count, 'selected_pairs': len(selected),
        'selection_policy': 'fixed SHA256-ranked documents, then one SHA256-ranked eligible gene-involving native candidate per selected document',
        'selection_seed': SEED, 'outcome_columns_decoded': False, 'outcome_access': 'not opened',
        'gold_entity_inputs': True, 'all_model_outcomes_replaced_with_literal_None': True,
        'task': 'source-relative entity-given gene-involving relation classification',
        'native_species_not_inferred': True, 'model_files_sha256': model_files,
        'author_code_commit': AUTHOR_COMMIT, 'author_code_files_sha256': code_files,
        'source_unit_provenance': unit_provenance,
        'implementation_sha256': sha(__file__), 'cases_sha256': sha(output/'cases.json'),
        'masked_tsv_sha256': sha(output/'masked.tsv'), 'candidate_relations': list(RELATIONS),
        'limitation': 'Not a whole-Pharos accuracy sample or an independent experimental truth benchmark. Public model/pretraining exposure is not fully auditable.'}
    report['content_sha256'] = digest(report)
    write_json(output / 'frame.json', report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('data-zip', 'model', 'author-source', 'output'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--partition', choices=PARTITIONS, required=True)
    a = p.parse_args()
    report = prepare(a.data_zip,a.model,a.author_source,a.output,partition=a.partition)
    print(json.dumps({k: report[k] for k in ('partition','eligible_documents','eligible_native_candidate_pairs',
        'selected_pairs','outcome_columns_decoded','content_sha256')},indent=2))


if __name__ == '__main__': main()
