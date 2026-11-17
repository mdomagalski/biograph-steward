"""Native STRING 12.5 bulk readers shared by source intake and evaluation.

Moved unchanged (apart from the local validator) from the qualified public-PPI
reference adapter. Direct reciprocal UniProt_AC aliases and exact complete
sequences are required; native score absence remains unavailable.
"""
from collections import defaultdict
import hashlib
import re

ACCESSION = re.compile(r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})')
STRING_ID = re.compile(r'9606\.ENSP[0-9]+\Z')
ALIAS_HEADER = '#string_protein_id\talias\tsource'
LINK_HEADER = 'protein1 protein2 combined_score'


def need(value, message):
    if not value:
        raise ValueError('Native STRING source: ' + message)


def sequence_records(records, *, canonical):
    """Validate literal records emitted by the existing BioPython FASTA parser."""
    found = {}
    for header, sequence in records:
        if canonical:
            parts = header.split()[0].split('|')
            need(len(parts) == 3 and parts[0] == 'sp' and ACCESSION.fullmatch(parts[1])
                   and re.search(r'(?:^| )OX=9606(?: |$)', header), 'reviewed canonical human FASTA identity differs.')
            key = parts[1]
        else:
            need(STRING_ID.fullmatch(header) is not None, 'literal STRING human FASTA identifier required.')
            key = header
        need(key not in found and isinstance(sequence, str) and re.fullmatch('[A-Z]+', sequence),
               'duplicate or nonliteral source sequence; no normalization permitted.')
        found[key] = sequence
    need(bool(found), 'empty FASTA source.')
    return found


def read_aliases(stream, canonical):
    """The v12.5 header/source vocabulary differs from the older v11 reader."""
    need(next(stream).rstrip('\r\n') == ALIAS_HEADER, 'v12.5 alias header differs.')
    found = defaultdict(set); seen = set(); rows = direct = 0
    for line in stream:
        rows += 1; fields = line.rstrip('\r\n').split('\t')
        need(len(fields) == 3 and STRING_ID.fullmatch(fields[0]), 'native alias row schema differs.')
        node, accession, tokens = fields[0], fields[1], fields[2].split()
        if accession not in canonical or 'UniProt_AC' not in tokens:
            continue
        key = (node, accession)
        need(key not in seen, 'duplicate direct canonical accession alias.')
        seen.add(key); direct += 1; found[accession].add(node)
    return dict(found), {'native_alias_rows': rows, 'direct_canonical_alias_rows': direct}


def crosswalk(canonical, source, aliases):
    """One direct alias in each direction, then full exact AA equality."""
    reverse = defaultdict(set)
    for accession, nodes in aliases.items():
        need(accession in canonical, 'alias is outside canonical source.')
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
    need(next(stream).rstrip('\r\n') == LINK_HEADER, 'v12.5 link header differs.')
    found = {}; directions = defaultdict(set); count = 0; minimum = 1001; maximum = -1
    for line in stream:
        count += 1; fields = line.split()
        need(len(fields) == 3 and all(STRING_ID.fullmatch(v) and v in source_nodes for v in fields[:2])
               and fields[2].isascii() and fields[2].isdecimal(), 'invalid native network row.')
        a, b = fields[:2]; score = int(fields[2])
        need(0 <= score <= 1000, 'native combined_score outside [0,1000].')
        minimum = min(minimum, score); maximum = max(maximum, score); key = tuple(sorted((a, b)))
        if key not in wanted: continue
        need((a, b) not in directions[key] and (key not in found or found[key] == score),
               'duplicate direction or conflicting AB/BA native score.')
        directions[key].add((a, b)); found[key] = score
    need(count > 0, 'empty native network file.')
    return {key: value / 1000 for key, value in found.items()}, {
        'source_rows': count, 'minimum_native_score': minimum, 'maximum_native_score': maximum,
        'queried_unique_source_pairs': len(wanted), 'returned_queried_pairs': len(found),
        'queried_pairs_seen_in_both_directions': sum(len(v) == 2 for v in directions.values())}

