"""Census explicit GO replacements against pinned native rows and graph concepts.

Reuse the ontology lifecycle classifier, five-field compatibility projection,
experimental-reference context gates and complete Gold/GOA source verifiers.
No graph edit, alias expansion, historical qualifier recovery or truth label.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import (client, file_utils, gold_packet, go_context_inspection,
                             go_ontology_qualification, go_qualification)
from biograph_steward.client import canonical, digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.go_context_inspection import load_go_context, REPORT as CONTEXT_REPORT
from tools.reference_accuracy.go_reference import exclusion_reasons, POLICY as REFERENCE_POLICY
from tools.reference_accuracy import go_reference

from biograph_steward.go_replacement_selection import (
    FORMAT, REPORT, METHOD, need, projection, candidate_gaf, classify,
)
from biograph_steward import go_native_support, go_replacement_selection


def audit(qualification, retained_package, context, output, *, qualification_sha256,
          retained_sha256, context_sha256):
    # Bind the reused eligibility/verification helpers before processing rows,
    # rather than accidentally pinning code changed after Python imported it.
    code_paths = [Path(__file__).absolute()] + [Path(m.__file__).absolute() for m in
        (client, file_utils, gold_packet, go_context_inspection,
         go_ontology_qualification, go_qualification, go_reference,
         go_native_support, go_replacement_selection)]
    code_pins = {str(p): sha(p) for p in code_paths}
    qualification, retained_package, context = map(lambda p: Path(p).absolute(),
                                                  (qualification, retained_package, context))
    need(sha(qualification / REPORT) == qualification_sha256
         and sha(retained_package / 'report.json') == retained_sha256
         and sha(context / CONTEXT_REPORT) == context_sha256, 'explicit report pins differ.')
    old = gold_packet._read(qualification / REPORT)
    need(gold_packet._sealed(old) and old.get('format') == go_ontology_qualification.FORMAT,
         'invalid original GO qualification seal or format.')
    need(all(sha(qualification / name) == pin for name, pin in old['files'].items()),
         'original GO qualification files changed.')
    report, retained = gold_packet.load_decisions(retained_package)
    manifest, baseline = gold_packet.load_packet(retained_package / 'baseline_packet')
    native_report, native, compatibilities = load_go_context(context)
    for source in (old, report, native_report):
        need(source['packet_id'] == manifest['packet_id'] and source['graph_sha256'] == manifest['graph_sha256'],
             'source packages belong to different baselines.')
    need(native_report['snapshot_sha256'] == manifest['snapshot_sha256']
         and native_report['source_graph_file_sha256'] == manifest['files']['source/graph.json'],
         'native context baseline source differs.')
    need(go_qualification.project_compatibilities(baseline, native) == compatibilities,
         'native compatibility does not replay against the actual baseline.')
    nodes, ontology, _ = go_ontology_qualification.load_ontology(
        qualification / old['ontology']['source_file'], old['ontology']['file_sha256'])
    need(ontology == old['ontology'], 'ontology binding differs.')
    proposal_file = gold_packet._read(qualification / 'replacement_proposals.json')
    need(proposal_file.get('applied') is False and proposal_file.get('profile') == old['profile']
         and proposal_file.get('ontology_sha256') == ontology['file_sha256'], 'proposal metadata differs.')
    rows, concepts, additions, counts = classify(baseline, retained, proposal_file['proposals'], native, nodes)
    need(counts['proposals'] == old['counts']['explicit_active_replacement_proposals'], 'incomplete proposal census.')
    pins = {str(qualification / REPORT): qualification_sha256,
            **{str(qualification / name): pin for name, pin in old['files'].items()},
            str(retained_package / 'report.json'): retained_sha256,
            **{str(retained_package / name): pin for name, pin in report['files'].items()},
            str(context / CONTEXT_REPORT): context_sha256,
            **{str(context / name): pin for name, pin in native_report['files'].items()},
            **code_pins}
    folder = new_output(output, qualification, retained_package, context)
    for name, values in (('proposal_audit.jsonl', rows), ('concept_audit.jsonl', concepts),
                         ('qualified_nonduplicate_native_records.jsonl', additions)):
        (folder / name).write_text(''.join(canonical(v) + '\n' for v in values), encoding='utf-8')
    (folder / 'qualified_recoveries.gaf').write_text(candidate_gaf(
        native_report['source']['headers'], additions, native_report['source']['gaf_sha256']), encoding='utf-8')
    result = {'format': FORMAT, 'created_at': utcnow(), 'method': METHOD,
        'packet_id': manifest['packet_id'], 'baseline_graph_sha256': manifest['graph_sha256'],
        'retained_graph_sha256': report['retained_graph_sha256'], 'ontology': ontology,
        'native_source': native_report['source'], 'counts': counts,
        'census_complete': True, 'census_is_independent_truth_evaluation': False,
        'native_subset_export': {'file': 'qualified_recoveries.gaf', 'records': len(additions),
                                'native_annotation_bodies_unchanged': True, 'applied_to_graph': False,
                                'license': 'CC-BY-4.0', 'attribution': 'Gene Ontology Consortium / UniProt and native Assigned_By providers'},
        'source_graph_changed': False, 'retained_graph_changed': False,
        'proposals_applied': False, 'review_states_inherited': False,
        'new_source_fetches': 0, 'model_calls': 0,
        'next_action': ('qualified_nonduplicate_native_records_require_separate_native_assertion_materialization'
                        if additions else 'no_experimental_context_qualified_nonduplicate_additions'),
        'limits': ['Native curation may reuse Pharos evidence; no independent experiment or truth score.',
                   'Concept overlap does not establish identity of relations, qualifiers, publications or evidence.',
                   'Nonexperimental curation is outside the existing experimental-reference scope, not false.',
                   'No native match is unknown; current GAF does not identify the historical Pharos record.',
                   'Pinned July2026 ontology/GAF are not asserted to be the latest release today.',
                   'Main-term lifecycle audit is not full GORULE20 or GO pipeline conformance.'],
        'input_files_sha256': pins,
        'files': {name: sha(folder / name) for name in ('proposal_audit.jsonl', 'concept_audit.jsonl',
                                                       'qualified_nonduplicate_native_records.jsonl', 'qualified_recoveries.gaf')}}
    need(all(sha(path) == pin for path, pin in pins.items()), 'source or implementation changed during audit.')
    result['content_sha256'] = digest(result)
    write_json(folder / 'report.json', result)
    return result


def main():
    import json
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('qualification', 'retained-package', 'context', 'output',
                 'qualification-sha256', 'retained-sha256', 'context-sha256'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    r = audit(a.qualification, a.retained_package, a.context, a.output,
              qualification_sha256=a.qualification_sha256,
              retained_sha256=a.retained_sha256, context_sha256=a.context_sha256)
    print(json.dumps({'output': a.output, 'counts': r['counts'], 'content_sha256': r['content_sha256']}, indent=2))


if __name__ == '__main__':
    main()
