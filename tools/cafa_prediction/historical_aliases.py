"""Attest literal historical accession aliases without repairing any mapping.

The native STRING v11 human aliases file is the established upstream mechanism.
A source token describes provenance; neither membership nor uniqueness proves
sequence, isoform, construct equivalence, or biological correctness.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import json
from pathlib import Path
import re

from .core import need, sha
from .run import digest, timestamp, write

NATIVE_SHA='933f9be94487bbcea46d81dcb190edad7c43072541b79e96f4209967b43dcf02'
DIRECT_SOURCES=frozenset({'Ensembl_UniProt_AC','Ensembl_HGNC_UniProt_ID(supplied_by_UniProt)_AC'})
HEADER='## string_protein_id ## alias ## source ##'


def read_aliases(stream, accessions):
    need(next(stream).rstrip('\r\n')==HEADER,'unexpected native version-specific alias header.')
    aliases=defaultdict(dict); rows=0
    for line in stream:
        rows+=1;fields=line.rstrip('\r\n').split('\t')
        need(len(fields)==3 and re.fullmatch(r'9606\.ENSP[0-9]+',fields[0]),'invalid native human alias row.')
        if fields[1] not in accessions:continue
        sources=fields[2].split();need(sources and len(sources)==len(set(sources)),'invalid repeated/empty native source tokens.')
        need(fields[0] not in aliases[fields[1]],'duplicate exact accession/STRING alias; do not overwrite.')
        aliases[fields[1]][fields[0]]=sources
    return aliases,rows


def summarize_pair(accession, stringid, aliases):
    candidates=aliases.get(accession,{})
    expected='9606.'+stringid if re.fullmatch(r'ENSP[0-9]+',stringid or '') else None
    sources=candidates.get(expected,[])
    direct=sorted(s for s in candidates if set(candidates[s])&DIRECT_SOURCES)
    status=('exact_Ensembl_accession_source' if set(sources)&DIRECT_SOURCES else
            'exact_alias_other_provenance' if sources else
            'historical_aliases_point_elsewhere' if candidates else
            'no_exact_accession_alias')
    return {'accession':accession,'archived_pharos_STRING_ID':stringid,'native_alias_status':status,
            'literal_matching_source_tokens':sources,'all_native_alias_alternatives':candidates,
            'Ensembl_accession_source_alternatives':direct,
            'unique_Ensembl_source_matches_selected':len(direct)==1 and direct[0]==expected,
            'sequence_or_isoform_equivalence_inferred':False}


def run(aliases, proteins, headers, output):
    aliases,proteins,headers,output=map(Path,(aliases,proteins,headers,output))
    need(sha(aliases)==NATIVE_SHA,'official archived v11 alias bytes differ from the previously reviewed native artifact.')
    with proteins.open() as stream:
        reader=csv.DictReader(stream,delimiter='\t');need(reader.fieldnames==['id','uniprot','sym','geneid','stringid'],'native source protein export fields differ.')
        rows=list(reader)
    need(len({r['uniprot'] for r in rows})==len(rows),'duplicate source accession; do not collapse.')
    pins={str(p.resolve()):sha(p) for p in (aliases,proteins,headers,Path(__file__))}
    with gzip.open(aliases,'rt') as stream:
        mapping,alias_rows=read_aliases(stream,{r['uniprot'] for r in rows})
    records=[summarize_pair(r['uniprot'],r['stringid'],mapping) for r in rows]
    statuses=Counter(r['native_alias_status'] for r in records)
    need(not output.exists(),'choose a new historical alias attestation output.');output.mkdir(parents=True)
    write(output/'records.json.gz',records)
    report={'format':'biograph-steward.historical-STRING-alias-attestation.v1','created_at':timestamp(),
        'source_URL':'https://stringdb-downloads.org/download/protein.aliases.v11.0/9606.protein.aliases.v11.0.txt.gz',
        'archived_HTTP_Last_Modified':'2019-01-17T16:20:08GMT','native_file_sha256':NATIVE_SHA,
        'input_sha256':pins,'native_alias_rows':alias_rows,'Pharos_proteins':len(records),
        'statuses':dict(statuses),'unique_Ensembl_source_matches_selected':sum(r['unique_Ensembl_source_matches_selected'] for r in records),
        'source_tokens_classified_as_Ensembl_accession_provenance':sorted(DIRECT_SOURCES),
        'missing_or_alternative_alias_is_false_mapping':False,'mapping_changed':False,'scores_or_graph_changed':False,
        'future_GO_labels_read':False,'records_sha256':sha(output/'records.json.gz'),
        'meaning':'Literal historical identifier-source support, with every alternative retained. The later source selection is not backdated. No best-match reconstruction, sequence identity, exact isoform, or biological-truth judgment is inferred. BLAST-only support remains distinguishable from explicit Ensembl accession-source support.',
        'known_upstream_behavior':'TCRD loader v2.7.0 selected 100%-sequence-identity primary mappings from a separate 2018 file before considering aliases, without overriding conflicting primary mappings. That separate mapping file is unavailable; lack of the same alias does not refute its historical choice.',
        'official_documentation':'https://string-db.org/help/faq/#how-do-i-map-my-proteins-to-string-identifiers',
        'existing_upstream_review':'runs/biological_improvement_8h_20261111/reference_qualification/upstream_tcrd/upstream_mapping_findings.json'}
    for p,s in pins.items():need(sha(p)==s,'input changed during historical alias attestation.')
    report['content_sha256']=digest(report);write(output/'report.json',report);return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('aliases','proteins','headers','output'):p.add_argument('--'+n,required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
