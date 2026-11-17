# SPDX-License-Identifier: GPL-3.0-only
"""Extend the existing literal GO-content audit to an explicit used-term frame.

The historical OBO parser is the pinned author's unchanged function with its
unused dense Graph constructor replaced by a metadata collector. The native
OBOGraphs/lifecycle loader is reused unchanged. No reasoner, source annotation,
future reference, model score, alias resolution or graph decision is run here.
"""
import argparse
import ast
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha, new_output
from biograph_steward.go_ontology_qualification import load_ontology, classify_term
from biograph_steward.go_content_currency import FORMAT, FLAGS, LIMITATIONS, validate_term, literal_flags
from biograph_steward.function_context import digest as context_digest

GO = re.compile(r'GO:[0-9]{7}')
MENTION = re.compile(r'\bGO:[0-9]{7}\b')
IRI_MENTION = re.compile(r'http://purl\.obolibrary\.org/obo/GO_([0-9]{7})\b')
PREFIX = 'http://purl.obolibrary.org/obo/'
OIO = 'http://www.geneontology.org/formats/oboInOwl#'
OLD_SHA = '0c0062efbb1b199a6a54e62c0c48ff0038d39173aecc7edfab66a20090d5ec2d'
NEW_SHA = '86c2e58bd639053cabfafd831afc4049e3da8457cb900879262d164a13ba0273'


def need(value, message):
    if not value:
        raise ValueError('Used-term GO content audit: ' + message)


def read(path):
    p = Path(path)
    need(p.is_file() and not p.is_symlink(), 'ordinary input required.')
    raw = p.read_bytes()
    return json.loads(gzip.decompress(raw) if raw.startswith(b'\x1f\x8b') else raw)


def spec(path):
    p = Path(path)
    need(p.is_file() and not p.is_symlink(), 'ordinary input required.')
    return {'file': str(p.resolve()), 'sha256': sha(p), 'bytes': p.stat().st_size}


def mentions(value):
    if isinstance(value, str):
        return set(MENTION.findall(value)) | {'GO:' + x for x in IRI_MENTION.findall(value)}
    if isinstance(value, dict):
        return set().union(*(mentions(v) for v in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(mentions(v) for v in value)) if value else set()
    return set()


def prepare(graph, training, publication, historical, comparison, author_parser, output, *, native_publication=None):
    """Freeze identifiers/source scope BEFORE looking at content differences."""
    graph, training, publication, historical, comparison, author_parser = map(
        Path, (graph, training, publication, historical, comparison, author_parser))
    inputs = {k: spec(p) for k, p in (('graph', graph), ('training', training),
        ('historical', historical), ('comparison', comparison), ('author_parser', author_parser),
        ('saved_query_publication', publication / 'publication.json'))}
    need(inputs['historical']['sha256'] == OLD_SHA and inputs['comparison']['sha256'] == NEW_SHA,
         'use the existing qualified 2023 and July2026 snapshots.')
    g, t, m = read(graph), read(training), read(publication / 'publication.json')
    need(m['format'] == 'biograph-steward.exact-onehop-LocalPlus-publication.v1'
         and m['content_sha256'] == context_digest({k: v for k, v in m.items() if k != 'content_sha256'}),
         'retained query source publication differs.')
    need(m['files']['downloads/training_snapshot.json.gz']['sha256'] == inputs['training']['sha256']
         and m['input_source_pins']['ontology']['sha256'] == OLD_SHA,
         'retained predictor training/ontology binding differs.')
    scopes = defaultdict(set); labels = defaultdict(set)
    for row in g['nodes']:
        uid = row.get('id')
        if isinstance(uid, str) and GO.fullmatch(uid):
            scopes[uid].add('graph_GO_node')
            if isinstance(row.get('name'), str): labels[uid].add(row['name'])
    for edge in g['edges']:
        for field in ('subject', 'object'):
            uid = edge.get(field)
            if isinstance(uid, str) and GO.fullmatch(uid):
                scopes[uid].add('graph_primary_GO_endpoint')
                if edge.get('record_kind') == 'go_annotation': scopes[uid].add('graph_Pharos_GO_record_vintage_unknown')
                elif edge.get('record_kind') == 'native_go_annotation': scopes[uid].add('graph_separate_native_GOA_record')
    # A separate mention scope is explicit: context/extension mentions are not
    # converted into additional graph assertions or predictor output heads.
    for uid in mentions(g): scopes[uid].add('graph_embedded_GO_mention')
    need(isinstance(t, dict) and bool(t), 'complete retained training snapshot required.')
    for annotations in t.values():
        need(isinstance(annotations, list), 'training source shape differs.')
        for pair in annotations:
            need(isinstance(pair, list) and len(pair) == 2 and pair[0] in ('MFO', 'BPO', 'CCO')
                 and GO.fullmatch(pair[1]), 'retained training-head identity differs.')
            scopes[pair[1]].add('retained_2023_predictor_training_head_vocabulary')
    query_pins = {}
    for file in sorted(set(m['query_files'].values())):
        path = publication / file
        need(sha(path) == m['files'][file]['sha256'], 'saved query source bytes differ.')
        query_pins[file] = sha(path)
        q = read(path)
        for row in q['candidates']:
            need(GO.fullmatch(row['GO_ID']), 'saved candidate GO identity differs.')
            scopes[row['GO_ID']].add('retained_saved_query_candidate')
    native_source = None
    if native_publication is not None:
        native_publication = Path(native_publication)
        native_manifest = read(native_publication / 'publication.json')
        need(native_manifest['format'] == 'biograph-steward.native-goa-source-publication.v1'
             and native_manifest['content_sha256'] == digest({k: v for k, v in native_manifest.items()
                                                             if k != 'content_sha256'}),
             'native GO source publication seal differs.')
        inputs['native_GO_source_publication'] = spec(native_publication / 'publication.json')
        for key, filename in (('native_GO_records', 'source/context/native_records.jsonl'),
                              ('native_GO_source_qualification', 'source/context/go_context_qualification.json')):
            inputs[key] = spec(native_publication / filename)
            need(inputs[key]['sha256'] == native_manifest['files'][filename],
                 'native source record/qualification bytes differ.')
        qualification = read(inputs['native_GO_source_qualification']['file'])
        need(qualification['content_sha256'] == digest({k: v for k, v in qualification.items()
                                                       if k != 'content_sha256'}),
             'native annotation source qualification seal differs.')
        count = 0
        with Path(inputs['native_GO_records']['file']).open() as source:
            for line in source:
                row = json.loads(line); uid = row['go_id']
                need(isinstance(uid, str) and GO.fullmatch(uid), 'native source primary GO identity differs.')
                scopes[uid].add('separate_native_GOA_primary_record')
                for mentioned in mentions(row): scopes[mentioned].add('separate_native_GOA_literal_mention')
                count += 1
        need(count == qualification['counts']['native_rows'], 'complete native annotation frame differs.')
        native_source = {'native_rows': count, 'headers': qualification['source']['headers'],
                         'provided_source_url': qualification['source']['provided_source_url'],
                         'source_url_authentication_performed': qualification['source']['source_url_authentication_performed']}
    terms = [{'term_id': uid, 'scopes': sorted(scopes[uid]), 'graph_labels': sorted(labels[uid])}
             for uid in sorted(scopes)]
    need(terms and len(terms) <= 50_000, 'bounded nonempty used-term frame required.')
    out = new_output(output, *(v['file'] for v in inputs.values()))
    frame = {'format': FORMAT + '.frame', 'created_at': utcnow(), 'terms': terms,
        'term_frame_sha256': digest([r['term_id'] for r in terms]),
        'scope_meanings': {'graph_embedded_GO_mention': 'Literal ID mentioned anywhere in preserved graph/context values; not an additional assertion.',
            'separate_native_GOA_literal_mention': 'Literal ID in a preserved native GOA record, including extensions; not an additional graph assertion.',
            'separate_native_GOA_primary_record': 'Primary GO ID of a preserved native inspector annotation; source date remains separate from unknown-vintage Pharos.',
            'retained_2023_predictor_training_head_vocabulary': 'All term heads admitted by the retained training source, not a claim that every term receives a positive score for every query.'},
        'sources': inputs, 'saved_query_files_sha256': query_pins,
        'separate_native_annotation_source': native_source,
        'new_content_comparison_performed': False}
    frame['content_sha256'] = digest(frame); write_json(out / 'term_frame.json', frame)
    freeze = {'format': FORMAT + '.scope-freeze', 'created_at': utcnow(),
        'frame_file_sha256': sha(out / 'term_frame.json'), 'frame_content_sha256': frame['content_sha256'],
        'term_frame_sha256': frame['term_frame_sha256'], 'term_count': len(terms),
        'scope_term_counts': dict(Counter(scope for r in terms for scope in r['scopes'])),
        'ontology_file_pins': {'historical': OLD_SHA, 'comparison': NEW_SHA},
        'source_versions': {'historical_predictor': '2023-01-01', 'comparison_snapshot': '2026-07-26',
            'graph_Pharos_GO_vintage': 'UNKNOWN', 'latest_release_claimed': False},
        'comparison_fields': list(FLAGS), 'method': 'Existing literal OBO stanza versus OBOGraphs fields, no semantic inference.',
        'code_files_sha256': {'audit.py': sha(__file__), 'go_content_currency.py': sha(Path(__import__(
            'biograph_steward.go_content_currency', fromlist=['x']).__file__)),
            'go_ontology_qualification.py': sha(Path(__import__('biograph_steward.go_ontology_qualification', fromlist=['x']).__file__))},
        'author_parser_sha256': inputs['author_parser']['sha256'],
        'new_difference_aggregate_values_read': False, 'automatic_graph_or_prediction_changes': False,
        'semantic_equivalence_claimed': False, 'biological_accuracy_measured': False}
    freeze['content_sha256'] = digest(freeze); write_json(out / 'scope_freeze.json', freeze)
    return freeze


def author_records(path, historical):
    """Reuse exactly the existing metadata-only native OBO parser call."""
    tree = ast.parse(Path(path).read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'obo_parser']
    need(len(functions) == 1, 'unique qualified native OBO reader required.')
    scope = {'Graph': lambda namespace, records, ia, orphans: records}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), scope)
    records = scope['obo_parser'](str(historical), ('is_a', 'part_of'), None, False)
    return {uid: row for namespace in records.values() for uid, row in namespace.items()}


def stanzas(path):
    output = {}; current = None; lines = []; is_term = False
    for line in Path(path).read_text().splitlines(keepends=True):
        if line.strip() in ('[Term]', '[Typedef]'):
            if current is not None: output[current] = ''.join(lines)
            current = None; lines = []; is_term = line.strip() == '[Term]'
        elif is_term and line.startswith('id: GO:'):
            uid = line.strip()[4:]
            need(GO.fullmatch(uid), 'invalid native stanza GO identity.')
            current = uid; lines.append(line)
        elif current is not None:
            lines.append(line)
    if current is not None: output[current] = ''.join(lines)
    return output


def quoted(value):
    # Identical to the earlier qualified literal audit. Unrecognized syntax
    # fails closed; it is never repaired with an invented escaping rule.
    text, end = json.JSONDecoder().raw_decode(value)
    need(isinstance(text, str), 'quoted OBO metadata is not a string.')
    return text, value[end:].strip()


def historical_record(uid, records, raw_stanzas):
    stanza = raw_stanzas.get(uid)
    if stanza is None:
        return {'present': False, 'state': 'not_found', 'name': None, 'definition': None,
                'namespace': None, 'synonyms': [], 'parents': []}
    fields = defaultdict(list)
    for line in stanza.splitlines():
        if ': ' in line:
            key, val = line.split(': ', 1); fields[key].append(val)
    def single(key):
        need(len(fields[key]) <= 1, 'single-valued native OBO field repeated.')
        return fields[key][0] if fields[key] else None
    name, namespace, definition_raw = single('name'), single('namespace'), single('def')
    active = uid in records
    if active:
        need(name == records[uid]['name'] and namespace == records[uid]['namespace']
             and definition_raw == records[uid]['def'], 'raw/native active-reader metadata differs.')
    definition = quoted(definition_raw)[0] if definition_raw is not None else None
    synonyms = []
    for value in fields['synonym']:
        text, rest = quoted(value); scope = rest.split()[0]
        need(scope in ('EXACT', 'RELATED', 'BROAD', 'NARROW'), 'unsupported declared synonym scope.')
        synonyms.append({'scope': scope, 'value': text})
    parents = [{'predicate': 'is_a', 'object': v.split()[0]} for v in fields['is_a']]
    parents += [{'predicate': 'part_of', 'object': v.split()[1]} for v in fields['relationship']
                if v.split()[0] == 'part_of']
    return {'present': True, 'state': 'obsolete' if fields['is_obsolete'] == ['true'] else 'active',
        'present_in_author_active_view': active, 'name': name, 'definition': definition,
        'definition_raw': definition_raw, 'namespace': namespace, 'synonyms': synonyms,
        'parents': parents, 'declared_alt_ids': fields['alt_id'], 'declared_replaced_by': fields['replaced_by'],
        'declared_consider': fields['consider'], 'stanza_utf8_sha256': hashlib.sha256(stanza.encode()).hexdigest(),
        'raw_stanza': stanza}


def comparison_record(uid, nodes, parent_index):
    node = nodes.get(uid)
    if node is None:
        return {'present': False, 'state': 'not_found', 'name': None, 'definition': None,
                'namespace': None, 'synonyms': [], 'parents': []}
    meta = node.get('meta', {}); properties = meta.get('basicPropertyValues', [])
    namespaces = [x['val'] for x in properties if x['pred'] == OIO + 'hasOBONamespace']
    need(len(namespaces) <= 1, 'native namespace repeated.')
    synonyms = []
    for item in meta.get('synonyms', []):
        pred = item['pred'].removeprefix(OIO)
        mapping = {'hasExactSynonym': 'EXACT', 'hasRelatedSynonym': 'RELATED',
                   'hasBroadSynonym': 'BROAD', 'hasNarrowSynonym': 'NARROW'}
        need(pred in mapping, 'unsupported native OBOGraphs synonym predicate.')
        synonyms.append({'scope': mapping[pred], 'value': item['val']})
    life = classify_term(uid, nodes)
    return {'present': True, 'state': 'obsolete' if meta.get('deprecated', False) else 'active',
        'name': node.get('lbl'), 'definition': meta.get('definition', {}).get('val'),
        'namespace': namespaces[0] if namespaces else None, 'synonyms': synonyms,
        'parents': parent_index.get(uid, []), 'declared_lifecycle': {k: v for k, v in life.items()
            if k not in ('decision', 'reason_code', 'replacement_proposal')},
        'replacement_applied': False, 'node_canonical_json_sha256': digest(node), 'native_node': node}


def flags(old, new):
    return literal_flags(old, new)


def audit(frame, freeze, expected, historical, comparison, author_parser, output):
    frame, freeze, historical, comparison, author_parser = map(Path, (frame, freeze, historical, comparison, author_parser))
    f, p = read(frame), read(freeze)
    need(sha(freeze) == expected and p['content_sha256'] == digest({k: v for k, v in p.items() if k != 'content_sha256'}), 'scope freeze differs.')
    need(sha(frame) == p['frame_file_sha256'] and f['content_sha256'] == p['frame_content_sha256']
         and f['content_sha256'] == digest({k: v for k, v in f.items() if k != 'content_sha256'}), 'term frame differs.')
    need(sha(historical) == p['ontology_file_pins']['historical'] == OLD_SHA
         and sha(comparison) == p['ontology_file_pins']['comparison'] == NEW_SHA
         and sha(author_parser) == p['author_parser_sha256'], 'qualified ontology/parser bytes differ.')
    actual_codes = {'audit.py': sha(__file__), 'go_content_currency.py': sha(Path(__import__(
        'biograph_steward.go_content_currency', fromlist=['x']).__file__)),
        'go_ontology_qualification.py': sha(Path(__import__('biograph_steward.go_ontology_qualification', fromlist=['x']).__file__))}
    need(actual_codes == p['code_files_sha256'], 'frozen audit/consumer/loader source differs.')
    terms = f['terms']; need(digest([r['term_id'] for r in terms]) == p['term_frame_sha256'], 'full term frame differs.')
    records, raw_stanzas = author_records(author_parser, historical), stanzas(historical)
    nodes, binding, raw = load_ontology(comparison, NEW_SHA)
    graph = json.loads(gzip.decompress(raw) if raw.startswith(b'\x1f\x8b') else raw)['graphs'][0]
    parent_index = defaultdict(list)
    for edge in graph['edges']:
        if edge['sub'].startswith(PREFIX + 'GO_') and edge['pred'] in ('is_a', PREFIX + 'BFO_0000050'):
            uid = 'GO:' + edge['sub'].removeprefix(PREFIX + 'GO_')
            target = edge['obj'].removeprefix(PREFIX).replace('_', ':')
            parent_index[uid].append({'predicate': 'is_a' if edge['pred'] == 'is_a' else 'part_of', 'object': target})
    out = new_output(output, frame, freeze, historical, comparison, author_parser)
    index = out / 'terms.jsonl.gz'; counts = Counter(); per_scope = defaultdict(Counter)
    with index.open('xb') as raw_output, gzip.GzipFile(fileobj=raw_output, mode='wb', mtime=0, filename='') as stream:
        for item in terms:
            uid = item['term_id']; old = historical_record(uid, records, raw_stanzas)
            new = comparison_record(uid, nodes, parent_index)
            row = {**item, 'historical': old, 'comparison': new, 'flags': flags(old, new),
                'semantic_equivalence_inferred': False, 'biological_falsehood_inferred': False, 'automatic_action': 'none'}
            validate_term(row)
            states = ['historical_' + old['state'], 'comparison_' + new['state']]
            marked = [k for k, v in row['flags'].items() if v is True]
            counts.update(states + marked)
            for scope in item['scopes']: per_scope[scope].update(states + marked)
            stream.write((json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode())
    manifest = {'format': FORMAT, 'created_at': utcnow(), 'source_versions': p['source_versions'],
        'source_freeze_file_sha256': expected, 'source_frame_file_sha256': sha(frame),
        'term_frame_sha256': p['term_frame_sha256'], 'term_count': len(terms),
        'scope_term_counts': p['scope_term_counts'], 'summary': dict(counts),
        'scope_summaries': {k: dict(v) for k, v in per_scope.items()},
        'source_inputs': {'historical': {'file_sha256': OLD_SHA, 'version': '2023-01-01'},
                          'comparison': binding, 'author_parser_file_sha256': sha(author_parser)},
        'files': {'terms.jsonl.gz': {'bytes': index.stat().st_size, 'sha256': sha(index)}},
        'limitations': list(LIMITATIONS), 'semantic_equivalence_claimed': False,
        'biological_accuracy_measured': False, 'automatic_graph_or_prediction_changes': False,
        'source_content_only': True, 'new_model_or_scoring_calls': 0}
    manifest['content_sha256'] = digest(manifest); write_json(out / 'publication.json', manifest)
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    prepare_cmd = sub.add_parser('prepare')
    for key in ('graph', 'training', 'publication', 'historical', 'comparison', 'author-parser', 'output'):
        prepare_cmd.add_argument('--' + key, required=True)
    prepare_cmd.add_argument('--native-publication', required=True)
    run_cmd = sub.add_parser('audit')
    for key in ('frame', 'freeze', 'expected', 'historical', 'comparison', 'author-parser', 'output'):
        run_cmd.add_argument('--' + key, required=True)
    args = vars(p.parse_args()); command = args.pop('command')
    value = prepare(**args) if command == 'prepare' else audit(**args)
    print(json.dumps({'format': value['format'], 'term_count': value['term_count'], 'content_sha256': value['content_sha256']}))
