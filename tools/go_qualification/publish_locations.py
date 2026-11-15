"""Create a separate exact-snapshot Pharos plus native-location workspace.

Example: python -m tools.go_qualification.publish_locations --help
Only pinned local source inputs are accepted. No benchmark, model, retrieval,
default-workspace update, acceptance decision or whole-graph repair is run.
"""
import argparse
from pathlib import Path
import shutil

from biograph_steward import evidence_extension, goa_locations
from biograph_steward.assay_attachment import _decode, _ordinary
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha
from biograph_steward.graph import build_graph, save_run
from biograph_steward.reviews import read_run
from .publish_recoveries import _stage, need


def publish(snapshot, context, ontology, output, *, snapshot_sha256, context_sha256, ontology_sha256):
    snapshot, context, ontology = map(lambda p: Path(p).absolute(), (snapshot, context, ontology))
    inputs = {snapshot: snapshot_sha256, context / 'go_context_qualification.json': context_sha256,
              ontology: ontology_sha256}
    need(all(sha(path) == pin for path, pin in inputs.items()), 'input source pin differs.')
    implementation = {str(Path(__file__).absolute()): sha(__file__)}
    source = _decode(_ordinary(snapshot))
    original = build_graph(source)
    output, stage = _stage(output, (snapshot, context, ontology))
    try:
        sources = stage / 'sources'
        publication = sources / 'goa'
        manifest = goa_locations.publish_locations(snapshot, context, ontology, publication,
            snapshot_sha256=snapshot_sha256, context_sha256=context_sha256, ontology_sha256=ontology_sha256)
        extension = evidence_extension.prepare_extension(source, original, {'goa': publication})
        destination = stage / 'workspace'
        graph = save_run(source, destination, run_mode='biological_extension',
            evidence_extension=extension, extension_source=sources)
        (destination / 'snapshot.json').write_bytes(_ordinary(snapshot))
        need(read_run(destination)[2] == graph, 'new source-profile workspace does not replay.')
        new_edges = {e['id']: e for e in graph['edges']}
        new_assertions = {a['id']: a for a in graph['assertions']}
        need(all(new_edges.get(e['id']) == e for e in original['edges'])
             and all(new_assertions.get(a['id']) == a for a in original['assertions']),
             'historical Pharos evidence or assertion changed.')
        native = [a for a in graph['assertions'] if a['kind'] == 'native_go_annotation']
        need(native and all(a['lifecycle_state'] == 'candidate' for a in native),
             'native location evidence was automatically promoted.')
        need(all(sha(path) == pin for path, pin in inputs.items())
             and all(sha(path) == pin for path, pin in implementation.items()),
             'source or producer changed during publication.')
        receipt = {'format': 'biograph-steward.native-location-workspace.v1', 'created_at': utcnow(),
            'scope': 'Separate original-snapshot Pharos plus native-location source-profile demonstration; not the retained/enriched default.',
            'profile': goa_locations.PROFILE, 'summary': manifest['summary'],
            'snapshot_sha256': source['content_sha256'], 'snapshot_file_sha256': snapshot_sha256,
            'native_context_report_file_sha256': context_sha256, 'ontology_file_sha256': ontology_sha256,
            'source_publication_sha256': manifest['content_sha256'],
            'graph_file_sha256': sha(destination / 'graph.json'),
            'original_Pharos_evidence_records': len(original['edges']),
            'original_Pharos_assertions': len(original['assertions']),
            'native_location_assertions': len(native),
            'original_Pharos_payloads_preserved': True, 'automatic_acceptance': False,
            'default_or_existing_workspaces_changed': False, 'benchmark_inputs_used': False,
            'new_confirmatory_evaluation_performed': False, 'model_calls': 0, 'source_fetches': 0,
            'implementation_sha256': implementation,
            'counts_scope': 'Source rows and qualified protein-term assertions; no independent study count or truth estimate.'}
        receipt['content_sha256'] = digest(receipt)
        write_json(destination / 'location_profile_receipt.json', receipt)
        need(not output.exists(), 'output appeared during preparation.')
        destination.rename(output)
        return receipt
    finally:
        # Only our disposable duplicate staging copy is removed; inputs and
        # the successful self-contained workspace are never deleted.
        shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('snapshot', 'context', 'ontology', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    for name in ('snapshot', 'context', 'ontology'):
        parser.add_argument('--' + name + '-sha256', required=True)
    args = parser.parse_args()
    receipt = publish(args.snapshot, args.context, args.ontology, args.out,
        snapshot_sha256=args.snapshot_sha256, context_sha256=args.context_sha256,
        ontology_sha256=args.ontology_sha256)
    print(receipt['content_sha256'])


if __name__ == '__main__':
    main()
