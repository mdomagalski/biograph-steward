"""Bind a scientific-label comparison to existing source packets and samples.

This is an optional offline research reader. It changes no graph or review.
Reference adjudication is external: file hashes establish bytes, not truth.
"""
import argparse
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import random

from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .score import load_frozen, rows, verify_tree
from .scientific_statistics import assess, IDENTITY_FIELDS


FORMAT = 'biograph-steward.source-bound-scientific-comparison.v1'
SEMANTICS = {
    'disease_association': 'qualified_disease_association_as_stored',
    'drug_listing': 'historical_target_drug_listing_existence',
    'expression_observation': 'qualified_source_expression_observation_as_stored',
    'go_annotation': 'historical_source_GO_annotation_existence_with_unknown_relation_polarity_extensions',
    'pathway_membership': 'qualified_pathway_participation_as_stored',
    'protein_interaction': 'source_functional_interaction_annotation_not_direct_binding',
    'source_regulatory_observation': 'qualified_source_reported_regulatory_observation_as_stored',
    'tissue_proximity_observation': 'qualified_source_assay_proximity_observation_as_stored',
    'variant_therapy_response': 'qualified_source_reported_complete_profile_regimen_response_as_stored',
}
CLAIM_KEYS = ('id', 'subject', 'predicate', 'object', 'kind', 'qualifiers')
COMPATIBLE_INSPECTOR_SHA256 = '88a3b5e9826884b76359984c7be74020819ca31c8d7dd93681d8e50cb76d9965'


def need(value, message):
    if not value:
        raise ValueError('Source-bound scientific comparison: ' + message)


def pinned_json(path):
    path = Path(path).resolve()
    need(path.is_file(), 'input file is missing.')
    before = sha(path)
    value = json.loads(path.read_text(encoding='utf-8'))
    need(before == sha(path), 'input changed while reading.')
    return value, {'path': str(path), 'bytes': path.stat().st_size, 'sha256': before}


def compatible_inspector(path):
    """Load only the verified compatible historical source-guide renderer."""
    if path is None:
        return None, {'profile': 'current_default_reader'}
    path = Path(path).resolve()
    need(path.suffix == '.py' and path.is_file(), 'historical inspector must be the qualified Python source.')
    need(sha(path) == COMPATIBLE_INSPECTOR_SHA256, 'historical inspector source hash is not qualified.')
    spec = importlib.util.spec_from_file_location('biograph_steward._sampled_frozen_inspector', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    need(sha(path) == COMPATIBLE_INSPECTOR_SHA256, 'historical inspector changed during loading.')
    return module.inspect_selection, {'profile': 'verified_compatible_git_3b2318e',
        'path': str(path), 'sha256': COMPATIBLE_INSPECTOR_SHA256,
        'original_inspector_source_pin_recorded_by_old_manifest': False,
        'qualification': 'Exact complete source_inspection parity for all 180 frozen dossiers; no dossier checks disabled.'}


def population_and_memberships(union_graph, pharos_graph, retained_graph):
    """Preserve one biological unit for every shared assertion identity."""
    graphs = {'enriched_baseline': union_graph, 'pharos_only': pharos_graph,
              'retained': retained_graph}
    indices = {}
    for name, graph in graphs.items():
        aa = graph.get('assertions')
        need(isinstance(aa, list) and aa, 'nonempty assertion arrays required.')
        index = {a['id']: a for a in aa}
        need(len(index) == len(aa), 'duplicate assertion IDs in ' + name)
        indices[name] = index
    union = indices['enriched_baseline']
    targets = {t['id'] for t in union_graph['targets']}
    snapshot = union_graph['snapshot_sha256']
    for name, graph in graphs.items():
        if 'targets' in graph:
            need({t['id'] for t in graph['targets']} == targets,
                 'primary target cohort changed in ' + name)
        else:
            # Gold's native retained profile preserves nodes and source
            # binding, but intentionally omits full-run target metadata.
            need(name == 'retained'
                 and graph.get('graph_format') == 'biograph-steward.retained-evidence-graph.v1'
                 and graph.get('retention_policy') == 'remove_explicit_prune_keep_abstain_preserve_all_nodes.v1'
                 and targets <= {node['id'] for node in graph['nodes']},
                 'native retained profile no longer preserves the original primary targets.')
        need(graph['snapshot_sha256'] == snapshot, 'Pharos snapshot changed in ' + name)
        need(set(indices[name]) <= set(union), 'assertions outside original source union.')
        for uid, assertion in indices[name].items():
            need({k: assertion.get(k) for k in CLAIM_KEYS}
                 == {k: union[uid].get(k) for k in CLAIM_KEYS},
                 'shared assertion changed its stored identity or qualifiers: ' + uid)
    need(not any(pharos_graph.get(k) for k in ('civic', 'evidence_extension',
         'civic_snapshot_sha256', 'evidence_extension_sha256',
         'assay_attachment_sha256', 'assay_publication_sha256')),
         'the declared Pharos-only graph includes an extension marker.')
    source_edges = {e['id']: e for e in union_graph['edges']}
    pharos_ids = {uid for uid, a in union.items() if a['evidence_edge_ids'] and all(
        source_edges[e].get('aggregator') == 'Pharos'
        and source_edges[e].get('data_kind') == 'live_pharos' for e in a['evidence_edge_ids'])}
    need(set(indices['pharos_only']) == pharos_ids,
         'Pharos-only graph does not contain exactly the captured Pharos-origin assertion frame.')
    for edge in pharos_graph['edges']:
        need(edge.get('aggregator') == 'Pharos' and edge.get('data_kind') == 'live_pharos'
             and edge['id'] in source_edges and edge == source_edges[edge['id']],
             'Pharos-only source payload or provenance differs from preserved union.')
    population = []
    for uid, a in sorted(union.items()):
        need(a['kind'] in SEMANTICS, 'claim family needs an explicit semantics qualification.')
        population.append({'assertion_id': uid, 'assertion_content_sha256': digest(a),
                           'stored_predicate': a['predicate'], 'claim_semantics': SEMANTICS[a['kind']],
                           'stratum': a['kind']})
    return population, {name: sorted(index) for name, index in indices.items()}


def load_removed_sample(folder, union_graph, removed_ids, packet, main_sample_id, policy_package):
    """Replay the pre-existing removed-domain supplement without pooling it."""
    folder = Path(folder)
    manifest, pin = pinned_json(folder / 'sample_manifest.json')
    protocol, _ = pinned_json(folder / 'protocol.json')
    need(gold_packet._sealed(manifest) and gold_packet._sealed(protocol), 'removed-sample seal differs.')
    need(manifest.get('format') == 'biograph-steward.removed-domain-supplement.v1'
         and protocol.get('format') == manifest['format'], 'removed-sample format differs.')
    need(manifest.get('protocol_content_sha256') == protocol['content_sha256']
         and manifest.get('do_not_pool_into_original_sample') is True
         and protocol.get('pool_with_original_sample') is False, 'removed-domain contract differs.')
    need(set(protocol['domain_assertion_ids']) == set(removed_ids)
         and protocol['population_size'] == manifest['population_size'] == len(removed_ids),
         'removed sample belongs to a different intervention.')
    need(protocol['packet_id'] == packet['packet_id']
         and protocol['baseline_graph_sha256'] == packet['graph_sha256']
         and protocol['prior_sample_id'] == main_sample_id,
         'removed sample belongs to another source packet.')
    policy, old_retained = gold_packet.load_decisions(policy_package)
    original_ids = {a['id'] for a in union_graph['assertions']}
    need(policy['content_sha256'] == protocol['retained_report_content_sha256']
         and policy['packet_id'] == packet['packet_id']
         and original_ids - {a['id'] for a in old_retained['assertions']} == set(removed_ids),
         'original sampled intervention report or removed domain differs.')
    n, total = protocol['sample_size'], len(removed_ids)
    need(manifest['conditional_inclusion_probability'] == {'numerator': n, 'denominator': total}
         and manifest['conditional_inverse_inclusion_weight'] == total / n,
         'removed-sample conditional probabilities differ.')
    verify_tree(folder, manifest['files'], 'sample_manifest.json')
    sample = rows(folder / 'sample.jsonl')
    expected = sorted(random.Random(protocol['seed']).sample(sorted(removed_ids), protocol['sample_size']))
    need([r['assertion_id'] for r in sample] == expected
         and len(sample) == manifest['sample_size'], 'removed-domain random selection differs.')
    by_id = {a['id']: a for a in union_graph['assertions']}
    edges = {e['id']: e for e in union_graph['edges']}
    for index, row in enumerate(sample, 1):
        case_id = 'removed_go_%03d' % index
        need(row['case_id'] == case_id and row['dossier_path'] == 'cases/' + case_id + '.json'
             and row['stratum'] == by_id[row['assertion_id']]['kind']
             and row['inclusion_probability'] == {'numerator': n, 'denominator': total}
             and row['inverse_inclusion_weight'] == total / n,
             'removed case identity, locator or inclusion probability differs.')
        dossier = json.loads((folder / row['dossier_path']).read_text(encoding='utf-8'))
        source_edges = [edges[uid] for uid in by_id[row['assertion_id']]['evidence_edge_ids']]
        need(gold_packet._sealed(dossier) and dossier['sample_id'] == manifest['sample_id']
             and all(dossier[k] == row[k] for k in ('case_id', 'assertion_id', 'stratum',
                         'inclusion_probability', 'inverse_inclusion_weight'))
             and dossier['protocol_content_sha256'] == protocol['content_sha256']
             and dossier['content_sha256'] == row['dossier_content_sha256']
             and dossier['assertion'] == by_id[row['assertion_id']]
             and dossier['assertion_content_sha256'] == digest(by_id[row['assertion_id']])
             and dossier['source_edges'] == source_edges
             and dossier['source_edge_content_sha256'] == {e['id']: digest(e) for e in source_edges},
             'removed dossier is not the original stored assertion.')
    need(sha(folder / 'sample_manifest.json') == pin['sha256'], 'removed sample changed during replay.')
    return manifest, sample, pin


def admit_judgments(paths, population, frozen_cases, root):
    """Verify case/reference bindings; never upgrade source audit statuses."""
    population = {r['assertion_id']: r for r in population}
    expected = defaultdict(list)
    for row in frozen_cases:
        expected[row['assertion_id']].append(row)
    result, pins, reference_pins, seen = [], [], {}, set()
    root = Path(root).resolve()
    for path in paths:
        pin = sha(path)
        rr = rows(path)
        for row in rr:
            uid = row.get('assertion_id')
            need(uid in expected and uid not in seen, 'judgment is duplicated or outside frozen cases.')
            need(any(all(row.get(k) == case[k] for k in ('case_id', 'sample_id', 'dossier_content_sha256'))
                     for case in expected[uid]),
                 'judgment does not bind the exact frozen case/dossier.')
            need(all(row.get(k) == population[uid][k] for k in IDENTITY_FIELDS),
                 'judgment changed the exact stored claim.')
            if row.get('scientific_label') != 'unknown':
                need(row.get('reference_independence') == 'independent',
                     'this independent-label assessment cannot admit shared/unresolved reference lineage.')
            refs = row.get('reference_files')
            need(isinstance(refs, list), 'reference files must be explicit, including an empty unknown list.')
            for ref in refs:
                need(isinstance(ref, dict) and set(ref) == {'file', 'sha256'}
                     and isinstance(ref['file'], str) and isinstance(ref['sha256'], str),
                     'reference must have a path and SHA256.')
                pp = Path(ref['file'])
                pp = (root / pp).resolve() if not pp.is_absolute() else pp.resolve()
                need(pp.is_relative_to(root) and pp.suffix.lower() != '.docx',
                     'reference must be an explicitly provided local research artifact.')
                key = str(pp)
                if key not in reference_pins:
                    need(pp.is_file(), 'reference artifact is missing.')
                    reference_pins[key] = sha(pp)
                need(reference_pins[key] == ref['sha256'], 'reference artifact hash differs.')
            seen.add(uid)
            result.append(row)
        need(sha(path) == pin, 'judgment file changed during admission.')
        pins.append({'path': str(Path(path).resolve()), 'sha256': pin, 'rows': len(rr)})
    need(seen == set(expected), 'explicit judgments must cover every frozen case, including unknowns.')
    return result, pins, reference_pins


def run(pharos_graph, retained_package, audit, removed_sample, judgments, output, *, root,
        removed_policy_package, frozen_inspector=None):
    package, audit = Path(retained_package).resolve(), Path(audit).resolve()
    disposition, retained = gold_packet.load_decisions(package)
    reader, reader_pin = compatible_inspector(frozen_inspector)
    report, protocol, packet, union, sample = load_frozen(
        audit, package / 'baseline_packet', inspection_reader=reader)
    pharos, pharos_pin = pinned_json(pharos_graph)
    population, memberships = population_and_memberships(union, pharos, retained)
    removed = sorted(set(memberships['enriched_baseline']) - set(memberships['retained']))
    supplement, removed_rows, supplement_pin = load_removed_sample(
        removed_sample, union, removed, packet, report['sample_id'], removed_policy_package)
    need(supplement['population_size'] == len(removed), 'removed denominator differs.')
    main_cases = [{**r, 'sample_id': report['sample_id']} for r in sample]
    extra_cases = [{**r, 'sample_id': supplement['sample_id']} for r in removed_rows]
    admitted, judgment_pins, ref_pins = admit_judgments(judgments, population, main_cases + extra_cases, root)
    domains = {
        'original_union_sample': {'population_ids': memberships['enriched_baseline'],
            'purpose': 'original_union_probability_sample', 'strata': report['strata'], 'sample_rows': sample},
        'removed_GO_supplement': {'population_ids': removed, 'purpose': 'separate_removed_domain',
            'strata': supplement['strata'], 'sample_rows': removed_rows},
    }
    comparisons = [{'baseline': name, 'candidate': 'retained'}
                   for name in ('pharos_only', 'enriched_baseline')]
    summary = assess(population, memberships, admitted, comparisons=comparisons, sampling_domains=domains)
    source_pins = {'pharos_graph': pharos_pin, 'union_graph_sha256': packet['graph_sha256'],
        'retained_report_file_sha256': sha(package / 'report.json'),
        'retained_report_content_sha256': disposition['content_sha256'],
        'main_sample_manifest_sha256': sha(audit / 'sample_manifest.json'),
        'removed_sample_manifest': supplement_pin, 'judgments': judgment_pins,
        'removed_original_policy_report_sha256': sha(Path(removed_policy_package) / 'report.json'),
        'reference_files': ref_pins,
        'producer_code_sha256': sha(__file__),
        'statistics_code_sha256': sha(Path(__file__).with_name('scientific_statistics.py'))}
    source_pins['source_inspection_replay'] = reader_pin
    source_pins['frozen_sample_validator_code_sha256'] = sha(Path(__file__).with_name('score.py'))
    need(sha(pharos_graph) == pharos_pin['sha256'], 'Pharos input changed during assessment.')
    for pp, pin in ref_pins.items():
        need(sha(pp) == pin, 'reference changed during assessment.')
    folder = new_output(output, package, audit, removed_sample, removed_policy_package,
                        Path(pharos_graph).parent, *judgments)
    inputs = {'population_rows': population, 'graph_memberships': memberships,
              'judgment_rows': admitted, 'comparisons': comparisons, 'sampling_domains': domains}
    write_json(folder / 'inputs.private.json', inputs)
    write_json(folder / 'summary.json', summary)
    member_sets = {name: set(ids) for name, ids in memberships.items()}
    provenance = {'format': FORMAT, 'created_at': utcnow(), 'source_pins': source_pins,
        'primary_targets': len(union['targets']),
        'graph_family_counts': {name: dict(sorted(Counter(r['stratum'] for r in population
                                    if r['assertion_id'] in ids).items()))
                                for name, ids in member_sets.items()},
        'complete_source_packet_and_decisions_replayed': True,
        'main_sample_dossiers_replayed': True, 'removed_sample_replayed_separately': True,
        'all_reference_file_hashes_checked': True,
        'independent_reference_lineage_is_a_supplied_adjudication_not_software_certification': True,
        'graph_changed': False, 'source_retrievals_by_runner': 0, 'model_calls': 0,
        'files': {name: {'sha256': sha(folder / name), 'bytes': (folder / name).stat().st_size}
                  for name in ('inputs.private.json', 'summary.json')}}
    provenance['content_sha256'] = digest(provenance)
    write_json(folder / 'provenance.private.json', provenance)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pharos-graph', 'retained-package', 'audit', 'removed-sample',
                 'removed-policy-package', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--judgments', type=Path, nargs='+', required=True)
    parser.add_argument('--reference-root', type=Path, default=Path.cwd())
    parser.add_argument('--frozen-inspector', type=Path)
    args = parser.parse_args()
    summary = run(args.pharos_graph, args.retained_package, args.audit, args.removed_sample,
                  args.judgments, args.out, root=args.reference_root,
                  removed_policy_package=args.removed_policy_package,
                  frozen_inspector=args.frozen_inspector)
    print(json.dumps({'format': summary['format'], 'graphs': summary['graphs'],
                      'comparisons': summary['comparisons']}))


if __name__ == '__main__':
    main()
