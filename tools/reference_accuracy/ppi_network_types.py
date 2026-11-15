"""Same-release STRING functional/physical proxies on fixed public PPI labels.

Only an exact reciprocal UniProt_AC/full-sequence crosswalk admits a native
source score. Existing PPI gold readers and published metric implementations
are reused. Missing weights never become numeric zero or negative gold.
"""
from collections import Counter, defaultdict
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from . import mitocarta as m
from . import ppi_gold as p

FORMAT = 'biograph-steward.same-release-STRING-network-types.v1'
TYPES = ('functional', 'physical')
ARMS = ('functional_presence_proxy', 'physical_presence_proxy',
        'functional_native_weight', 'physical_native_weight')
STRING_ID = re.compile(r'9606\.ENSP[0-9]+\Z')
ALIAS_HEADER = '#string_protein_id\talias\tsource'
LINK_HEADER = 'protein1 protein2 combined_score'


def sequence_records(records, *, canonical):
    """Validate literal records emitted by the existing BioPython FASTA parser."""
    found = {}
    for header, sequence in records:
        if canonical:
            parts = header.split()[0].split('|')
            m.need(len(parts) == 3 and parts[0] == 'sp' and p.ACCESSION.fullmatch(parts[1])
                   and re.search(r'(?:^| )OX=9606(?: |$)', header), 'reviewed canonical human FASTA identity differs.')
            key = parts[1]
        else:
            m.need(STRING_ID.fullmatch(header) is not None, 'literal STRING human FASTA identifier required.')
            key = header
        m.need(key not in found and isinstance(sequence, str) and re.fullmatch('[A-Z]+', sequence),
               'duplicate or nonliteral source sequence; no normalization permitted.')
        found[key] = sequence
    m.need(bool(found), 'empty FASTA source.')
    return found


def read_aliases(stream, canonical):
    """The v12.5 header/source vocabulary differs from the older v11 reader."""
    m.need(next(stream).rstrip('\r\n') == ALIAS_HEADER, 'v12.5 alias header differs.')
    found = defaultdict(set); seen = set(); rows = direct = 0
    for line in stream:
        rows += 1; fields = line.rstrip('\r\n').split('\t')
        m.need(len(fields) == 3 and STRING_ID.fullmatch(fields[0]), 'native alias row schema differs.')
        node, accession, tokens = fields[0], fields[1], fields[2].split()
        if accession not in canonical or 'UniProt_AC' not in tokens:
            continue
        key = (node, accession)
        m.need(key not in seen, 'duplicate direct canonical accession alias.')
        seen.add(key); direct += 1; found[accession].add(node)
    return dict(found), {'native_alias_rows': rows, 'direct_canonical_alias_rows': direct}


def crosswalk(canonical, source, aliases):
    """One direct alias in each direction, then full exact AA equality."""
    reverse = defaultdict(set)
    for accession, nodes in aliases.items():
        m.need(accession in canonical, 'alias is outside canonical source.')
        for node in nodes: reverse[node].add(accession)
    result = {}
    for accession, sequence in canonical.items():
        candidates = sorted(aliases.get(accession, set())); node = None
        reason = ('missing_direct_UniProt_AC_alias' if not candidates else
                  'ambiguous_direct_STRING_aliases' if len(candidates) != 1 else None)
        if reason is None:
            node = candidates[0]
            reason = ('ambiguous_reciprocal_canonical_accessions' if len(reverse[node]) != 1 else
                      'STRING_sequence_missing' if node not in source else
                      'full_sequence_mismatch' if sequence != source[node] else None)
        result[accession] = {'canonical_accession': accession, 'direct_STRING_alias_candidates': candidates,
            'selected_STRING_ID': node if reason is None else None,
            'admission': 'exact_reciprocal_alias_and_full_sequence' if reason is None else reason,
            'canonical_sequence_sha256': hashlib.sha256(sequence.encode('ascii')).hexdigest(),
            'source_sequence_sha256': hashlib.sha256(source[node].encode('ascii')).hexdigest() if node in source else None,
            'biological_truth_inferred': False}
    return result


def mapped_pair(pair, mapping):
    if pair[0] == pair[1]: return None, 'self_pair_outside_proxy_domain'
    rows = [mapping.get(a) for a in pair]
    if any(r is None for r in rows): return None, 'accession_outside_reviewed_canonical_reference'
    if any(r['selected_STRING_ID'] is None for r in rows):
        return None, 'source_identity_unavailable:' + '|'.join(sorted({r['admission'] for r in rows if r['selected_STRING_ID'] is None}))
    key = tuple(sorted(r['selected_STRING_ID'] for r in rows))
    if key[0] == key[1]: return None, 'distinct_accessions_collapsed_to_same_STRING_ID'
    return key, None


def read_links(stream, wanted, source_nodes):
    """Stream a complete native file, keeping only frozen target-pair weights."""
    m.need(next(stream).rstrip('\r\n') == LINK_HEADER, 'v12.5 link header differs.')
    found = {}; directions = defaultdict(set); count = 0; minimum = 1001; maximum = -1
    for line in stream:
        count += 1; fields = line.split()
        m.need(len(fields) == 3 and all(STRING_ID.fullmatch(v) and v in source_nodes for v in fields[:2])
               and fields[2].isascii() and fields[2].isdecimal(), 'invalid native network row.')
        a, b = fields[:2]; score = int(fields[2])
        m.need(0 <= score <= 1000, 'native combined_score outside [0,1000].')
        minimum = min(minimum, score); maximum = max(maximum, score); key = tuple(sorted((a, b)))
        if key not in wanted: continue
        m.need((a, b) not in directions[key] and (key not in found or found[key] == score),
               'duplicate direction or conflicting AB/BA native score.')
        directions[key].add((a, b)); found[key] = score
    m.need(count > 0, 'empty native network file.')
    return {key: value / 1000 for key, value in found.items()}, {
        'source_rows': count, 'minimum_native_score': minimum, 'maximum_native_score': maximum,
        'queried_unique_source_pairs': len(wanted), 'returned_queried_pairs': len(found),
        'queried_pairs_seen_in_both_directions': sum(len(v) == 2 for v in directions.values())}


def annotate(reference, mapping, scores):
    result = []
    for row in reference:
        key, reason = mapped_pair(row['pair'], mapping); values = {}; missing = {}
        for network in TYPES:
            values[network+'_presence_proxy'] = int(key in scores[network]) if key is not None else None
            values[network+'_native_weight'] = scores[network].get(key) if key is not None else None
            missing[network+'_native_weight'] = reason or ('no_native_pair_weight_returned' if key not in scores[network] else None)
        result.append({**row, 'STRING_pair': key, 'source_identity_unavailable_reason': reason,
                       'scores': values, 'native_weight_unavailable_reasons': missing})
    return result


def summarize(rows):
    known = [r for r in rows if r['gold'] is not None]; arms = {}
    for arm in ARMS:
        available = [r for r in known if r['scores'][arm] is not None]
        arms[arm] = {'available_label_counts': dict(Counter(r['source_label'] for r in available)),
            'unavailable_label_counts': dict(Counter(r['source_label'] for r in known if r['scores'][arm] is None)),
            'ranking': p.ranking_metrics(known, arm)}
        if arm.endswith('presence_proxy'):
            arms[arm]['natural_boolean_decision'] = m.binary_metrics([(r['gold'], r['scores'][arm]) for r in known])
    joint = [r for r in known if all(r['scores'][n+'_native_weight'] is not None for n in TYPES)]
    paired = {n: p.ranking_metrics(joint, n+'_native_weight') for n in TYPES}
    delta = {metric: paired['physical'][metric] - paired['functional'][metric]
             if paired['physical'][metric] is not None else None for metric in ('AUROC', 'average_precision')}
    return {'reference_rows': len(rows), 'reference_label_counts': dict(Counter(r['source_label'] for r in rows)),
        'unknown_reference_rows_excluded_from_scoring': len(rows)-len(known), 'arms': arms,
        'source_identity_unavailable_reasons': dict(Counter(r['source_identity_unavailable_reason'] for r in known if r['source_identity_unavailable_reason'])),
        'paired_both_native_weights': {'pairs': len(joint), 'arms': paired, 'physical_minus_functional': delta},
        'confidence_interval': None, 'whole_graph_biological_accuracy': None,
        'new_independent_experimental_confirmation': False, 'graph_improvement_established': False}


def runtime_binding():
    import Bio, numpy, scipy, sklearn
    from Bio.SeqIO import FastaIO
    from sklearn.metrics import _ranking
    m.need(Bio.__version__ == '1.86' and sklearn.__version__ == '1.7.2', 'qualified parser/metric version differs.')
    modules = {'adapter': Path(__file__), 'gold_reader_and_ranking_helper': Path(p.__file__),
        'binary_metrics_helper': Path(m.__file__), 'native_FASTA_parser': Path(FastaIO.__file__),
        'native_ranking_metrics': Path(_ranking.__file__)}
    return {'python': sys.version, 'versions': {x.__name__: x.__version__ for x in (Bio,numpy,scipy,sklearn)},
            'sources': {name: {'file': str(path.absolute()), 'sha256': sha(path)} for name,path in modules.items()}}


def seal_implementation(plan, expected, output):
    plan = m.pinned(plan, expected); cfg = json.loads(plan.read_text())
    m.need(cfg['format'] == FORMAT and cfg['status'] == 'frozen_before_new_score_gold_join', 'frozen plan required.')
    output = Path(output); m.need(not output.exists() and output.parent.is_dir(), 'exclusive implementation receipt required.')
    receipt = {'format': FORMAT+'.implementation', 'created_at': utcnow(), 'plan_sha256': expected,
               'runtime': runtime_binding(), 'new_score_gold_join_performed': False}
    with output.open('x') as stream: json.dump(receipt,stream,indent=2);stream.write('\n')
    return receipt


def run(plan, expected, implementation_receipt, receipt_sha256, output):
    plan = m.pinned(plan, expected); cfg = json.loads(plan.read_text())
    receipt_path = m.pinned(implementation_receipt, receipt_sha256); receipt = json.loads(receipt_path.read_text())
    m.need(cfg['format'] == FORMAT and cfg['status'] == 'frozen_before_new_score_gold_join'
           and cfg['arms'] == list(ARMS) and cfg['no_fit_or_threshold_selection'] is True
           and cfg['identity_admission']['alias_source_tokens'] == ['UniProt_AC'], 'frozen network-type policy differs.')
    m.need(receipt['format'] == FORMAT+'.implementation' and receipt['plan_sha256'] == expected
           and receipt['new_score_gold_join_performed'] is False and receipt['runtime'] == runtime_binding(),
           'implementation/runtime changed after the exclusive pre-join receipt.')
    paths = {name: m.pinned(s['file'], s['sha256']) for name,s in cfg['bulk_files'].items()}
    fasta = m.pinned(cfg['canonical_FASTA']['file'], cfg['canonical_FASTA']['sha256'])
    source_pins = {str(path): sha(path) for path in [plan,receipt_path,fasta,*paths.values()]}
    for key in ('source_capture','prior_score_contract'):
        spec=cfg[key];path=m.pinned(spec['file'],spec['sha256']);source_pins[str(path)]=spec['sha256']
    expected_panels={'canonical_'+frame for frame in cfg['same_fixed_frames']} | {'manual_assay_'+frame for frame in cfg['same_fixed_frames']}
    m.need(len(cfg['reference_panels'])==6 and {s['name'] for s in cfg['reference_panels']}==expected_panels,
           'all six fixed scope/reference panels required.')
    for s in cfg['reference_panels']:
        path=m.pinned(s['file'],s['sha256']);source_pins[str(path)]=s['sha256']
    folder = new_output(output, plan.parent, *(x.parent for x in paths.values()))
    from Bio.SeqIO.FastaIO import SimpleFastaParser
    with fasta.open() as stream: canonical = sequence_records(SimpleFastaParser(stream), canonical=True)
    with gzip.open(paths['9606.protein.sequences.v12.5.fa.gz'],'rt') as stream:
        source = sequence_records(SimpleFastaParser(stream), canonical=False)
    with gzip.open(paths['9606.protein.aliases.v12.5.txt.gz'],'rt') as stream:
        aliases, alias_meta = read_aliases(stream,canonical)
    mapping = crosswalk(canonical, source, aliases)
    with (folder/'source_mapping.private.jsonl').open('x') as stream:
        for accession in sorted(mapping):stream.write(json.dumps(mapping[accession],sort_keys=True)+'\n')
    mapping_sha=sha(folder/'source_mapping.private.jsonl')
    # The source identity policy is fixed and the all-canonical crosswalk is
    # persisted before the new score join. Earlier reference outcomes are known.
    references=[];wanted=set()
    for spec in cfg['reference_panels']:
        raw=[json.loads(line) for line in Path(spec['file']).read_text().splitlines() if line.strip()]
        m.need(len(raw)==spec['expected_reference_rows'] and dict(Counter(r['reference_label'] for r in raw))==spec['expected_label_counts'], 'frozen gold denominator or class counts differ.')
        rows=p.gold_rows(raw,spec['profile']);references.append((spec,rows))
        wanted.update(key for row in rows for key,reason in [mapped_pair(row['pair'],mapping)] if key is not None)
    scores={};native={}
    for network,filename in [('functional','9606.protein.links.v12.5.txt.gz'),('physical','9606.protein.physical.links.v12.5.txt.gz')]:
        with gzip.open(paths[filename],'rt') as stream:scores[network],native[network]=read_links(stream,wanted,set(source))
    predictions={name: annotate(rows,mapping,scores) for spec,rows in references for name in [spec['name']]}
    seal={'format':FORMAT+'.predictions','created_at':utcnow(),'plan_sha256':expected,
        'implementation_receipt_sha256':receipt_sha256,'mapping_sha256':mapping_sha,'native_source_counts':native,
        'previous_reference_labels_consumed':True,'new_metrics_computed':False,
        'predictions_sha256':{name:digest([{k:v for k,v in row.items() if k!='reference'} for row in rows]) for name,rows in predictions.items()}}
    write_json(folder/'predictions_before_metrics.json',seal)
    reports={}
    for spec,_ in references:
        rows=predictions[spec['name']];report=summarize(rows)
        if spec.get('negative_paper_leave_one_out'):
            papers=sorted({v for row in rows if row['gold']==0 for v in row['publications']})
            report['negative_paper_leave_one_out']=[{'excluded_paper':paper,'excluded_rows_all_labels':sum(paper in r['publications'] for r in rows),'result':summarize([r for r in rows if paper not in r['publications']])} for paper in papers]
        if spec['profile']=='manual_gene_pair':
            for name,field in [('unfiltered_manual_negatives','negative_unfiltered_manual_available'),('IntAct_filtered_only_negatives','negative_only_IntAct_filtered_manual')]:
                report[name]=summarize([r for r in rows if r['gold']!=0 or r['reference'][field]])
        reports[spec['name']]=report
        with (folder/(spec['name']+'.scored.private.jsonl')).open('x') as stream:
            for row in rows:stream.write(json.dumps({**{k:v for k,v in row.items() if k!='reference'},'reference_row_content_sha256':digest(row['reference'])},sort_keys=True)+'\n')
    m.need(all(sha(path)==pin for path,pin in source_pins.items()) and runtime_binding()==receipt['runtime'], 'source/runtime changed during comparison.')
    result={'format':FORMAT,'created_at':utcnow(),'plan_sha256':expected,'implementation_receipt_sha256':receipt_sha256,
        'source_identity':{**alias_meta,'canonical_reference_proteins':len(canonical),'STRING_sequence_proteins':len(source),'admission_counts':dict(Counter(r['admission'] for r in mapping.values()))},
        'native_source_counts':native,'results':reports,'runtime':receipt['runtime'],
        'source_pins':source_pins,'graph_or_gold_changed':False,'model_calls':0,
        'no_score_imputation':True,'independent_experiment_claimed':False,
        'source_overlap':cfg['source_overlap'],'interpretation_limits':cfg['interpretation_limits'],
        'files':{f.name:{'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(folder.iterdir()) if f.is_file()}}
    write_json(folder/'report.private.json',result);return result


def main():
    a=argparse.ArgumentParser(description=__doc__)
    for key in ('plan','plan-sha256','out'):a.add_argument('--'+key,required=True)
    a.add_argument('--seal-implementation',action='store_true')
    a.add_argument('--implementation-receipt');a.add_argument('--receipt-sha256')
    args=a.parse_args()
    if args.seal_implementation: result=seal_implementation(args.plan,args.plan_sha256,args.out)
    else:result=run(args.plan,args.plan_sha256,args.implementation_receipt,args.receipt_sha256,args.out)
    print(json.dumps({'format':result['format'],'status':'complete'}))


if __name__=='__main__':main()
