"""Scope extension of the existing archived STRING exact-weight attestation.

The native SQL importer and original published network are reused. No current
identifier rescue, weight imputation or future annotation labels are admitted.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

from .core import need, sha
from .run import digest, new_output, pin, read, timestamp, verify_pins, write


def rows(path):
    with Path(path).open(newline='') as stream:
        yield from csv.DictReader(stream, delimiter='\t')


def candidate(row, mapping, ambiguous):
    reasons = []
    a, b = row['subject_uniprot'], row['object_uniprot']
    sa, sb = row['subject_STRING_ID'], row['object_STRING_ID']
    if not (a in mapping and b in mapping and mapping[a] == sa and mapping[b] == sb):
        reasons.append('archived_mapping_inconsistent')
    if not (re.fullmatch(r'ENSP[0-9]+', sa) and re.fullmatch(r'ENSP[0-9]+', sb)):
        reasons.append('missing_or_unrecognized_archived_STRING_mapping')
    if sa in ambiguous or sb in ambiguous:
        reasons.append('globally_noninjective_archived_STRING_mapping')
    if row['source_rows'] != '2' or row['source_orientations'] != '2':
        reasons.append('source_reciprocal_rows_not_exactly_two')
    if row['min_score'] != row['max_score'] or row['min_provider'] != row['max_provider']:
        reasons.append('source_reciprocal_disagreement')
    score = int(row['min_score'])
    if not 0 < score <= 1000 or a == b or sa == sb:
        reasons.append('invalid_or_collapsed_pair')
    return tuple(sorted((sa, sb))), score, reasons


def qualify(config_path, output):
    config = read(config_path)
    need(set(config) == {'proteins', 'source_pairs', 'native_links', 'native_anchor', 'old_weights', 'source_extraction_receipt'},
         'exact full-source qualification configuration required.')
    pins = {k: pin(v) for k, v in config.items()}
    pins['adapter'] = pin(__file__); pins['configuration'] = pin(config_path)
    anchor = read(config['native_anchor'])
    need(anchor['gzip_crc_eof_verified'] is True and anchor['release'] == '11.0'
         and pins['native_links']['sha256'] == anchor['file_sha256'], 'native archived release bytes differ.')
    proteins = list(rows(config['proteins']))
    mapping = {r['uniprot']: r['stringid'] for r in proteins}
    need(len(mapping) == len(proteins) and all(re.fullmatch(r'[A-Z0-9]+', p) for p in mapping),
         'full protein frame must have distinct exact canonical accessions.')
    inverse = defaultdict(set)
    for p, s in mapping.items():
        if re.fullmatch(r'ENSP[0-9]+', s):
            inverse[s].add(p)
    ambiguous = {s for s, values in inverse.items() if len(values) != 1}
    wanted, source_counts = {}, Counter()
    for row in rows(config['source_pairs']):
        key, score, reasons = candidate(row, mapping, ambiguous)
        source_counts['source_pairs'] += 1
        source_counts.update(reasons)
        if not reasons:
            key = tuple(sys.intern(s) for s in key)
            need(key not in wanted, 'canonical source pair is duplicated after injective mapping.')
            wanted[key] = [score, 0, 0, 0]
    count = 0
    with gzip.open(config['native_links'], 'rt') as stream:
        need(stream.readline().strip().split() == ['protein1', 'protein2', 'combined_score'], 'official STRING header differs.')
        for line in stream:
            a, b, text = line.split(); count += 1
            need(a.startswith('9606.ENSP') and b.startswith('9606.ENSP'), 'nonhuman native row.')
            a, b = a[5:], b[5:]
            key = (a,b) if a < b else (b,a)
            record = wanted.get(key)
            if record is not None:
                record[1] += 1
                record[2] |= 1 if a < b else 2
                record[3] += int(text) != record[0]
    need(count == anchor['native_file_rows'], 'native source row count changed.')
    folder = new_output(output)
    with (folder/'network_nodes.tsv').open('x', newline='') as stream:
        writer = csv.writer(stream,delimiter='\t',lineterminator='\n'); writer.writerow(['node_id','canonical_graph_node_present'])
        writer.writerows(('UniProtKB:'+p,'true') for p in sorted(mapping))
    qualified, causes, degree = {}, {}, Counter()
    with (folder/'weighted_pairs.tsv').open('x', newline='') as stream, (folder/'qualification_ledger.jsonl').open('x') as ledger:
        writer = csv.writer(stream,delimiter='\t',lineterminator='\n')
        writer.writerow(['subject','object','weight','pair_id','source_bundle','first_source_id','last_source_id'])
        for row in rows(config['source_pairs']):
            key, score, reasons = candidate(row,mapping,ambiguous)
            if not reasons:
                record = wanted[key]
                if record[1] != 2 or record[2] != 3:
                    reasons.append('official_native_reciprocal_pair_not_exactly_attested')
                if record[3]:
                    reasons.append('official_native_combined_score_disagrees')
            pair = tuple(sorted((row['subject_uniprot'],row['object_uniprot'])))
            if reasons:
                causes[pair] = reasons
                ledger.write(json.dumps({'subject':pair[0],'object':pair[1],'reasons':reasons},sort_keys=True)+'\n')
            else:
                need(pair not in qualified,'duplicate qualified accession pair.')
                qualified[pair] = score
                writer.writerow(['UniProtKB:'+pair[0],'UniProtKB:'+pair[1],format(score/1000,'.17g'),
                    'pharos319ppi:'+row['left_id']+':'+row['right_id'],row['min_provider'],row['first_source_id'],row['last_source_id']])
                degree.update(pair)
    carried, lost, losses, old_pairs = 0, 0, Counter(), set()
    for row in rows(config['old_weights']):
        pair = tuple(sorted(row[k].removeprefix('UniProtKB:') for k in ('subject','object')))
        old_pairs.add(pair)
        if pair in qualified:
            need(abs(qualified[pair]/1000-float(row['weight'])) < 1e-12,'carried old source weight differs.')
            carried += 1
        else:
            lost += 1; losses.update(causes.get(pair,['pair_not_in_new_full_source_export']))
    write(folder/'global_noninjective_mappings.json',{s:sorted(inverse[s]) for s in sorted(ambiguous)})
    verify_pins(pins)
    report = {'format':'biograph-steward.qualified-full-pharos319-string11.v1','created_at':timestamp(),
        'input_pins':pins,'protein_nodes':len(mapping),'qualified_weighted_pairs':len(qualified),
        'protein_nodes_with_qualified_edges':len(degree),'native_file_rows':count,'gzip_crc_eof_verified':True,
        'global_noninjective_STRING_IDs':len(ambiguous),'source_pair_counts':dict(source_counts),
        'quarantined_pairs':len(causes),'quarantine_reason_counts':dict(Counter(r for rs in causes.values() for r in rs)),
        'old_qualified_weighted_pairs':len(old_pairs),'old_pairs_carried_with_identical_weights':carried,
        'old_pairs_newly_quarantined':lost,'old_pair_loss_reasons':dict(losses),
        'new_weighted_pairs_beyond_old_frame':len(qualified)-carried,
        'source_profile':'Existing app filter: exclude exact STRINGDB-only scores below400; preserve mixed source bundles; only exact archived ENSP serialization + globally injective accession mapping + both native December2018 score directions admit a weight.',
        'future_GO_labels_read':False,'current_identifier_rescue':False,'original_graph_modified':False,
        'unresolved_policy':'Quarantine from model adjacency only; no biological-false or prune assertion.',
        'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(folder.iterdir())}}
    report['content_sha256']=digest(report); write(folder/'qualification.json',report)
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--config',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args(); print(json.dumps(qualify(args.config,args.output),indent=2))
