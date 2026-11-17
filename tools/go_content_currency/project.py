"""Offline small content-note projection for an unchanged saved publication."""
import argparse
import json
from pathlib import Path

from biograph_steward.client import write_json
from biograph_steward.file_utils import new_output
from biograph_steward.function_context import (CONTENT_NOTES, digest, sha,
    load_publication, load_content_notes, need)
from biograph_steward.go_content_currency import load_index, project_terms, LIMITATIONS


def prepare(index, index_expected, publication, publication_expected, output):
    manifest, queries = load_publication(publication, publication_expected)
    currency, rows = load_index(index, index_expected)
    historical = currency['source_inputs']['historical']['file_sha256']
    need(historical == manifest.get('input_source_pins', {}).get('ontology', {}).get('sha256'),
         'source index and historical forecast use different ontology bytes.')
    ids = sorted({c['GO_ID'] for q in queries.values() for c in q['candidates']})
    terms = project_terms(currency, rows, ids) if ids else []
    report = {'format': CONTENT_NOTES, 'publication_manifest_sha256': publication_expected,
        'publication_content_sha256': manifest['content_sha256'],
        'source_currency_index': {'manifest_file_sha256': index_expected,
            'manifest_content_sha256': currency['content_sha256'], 'term_frame_sha256': currency['term_frame_sha256'],
            'term_count': currency['term_count'], 'index_file_sha256': currency['files']['terms.jsonl.gz']['sha256'],
            'historical_ontology_file_sha256': historical,
            'comparison_ontology_file_sha256': currency['source_inputs']['comparison']['file_sha256']},
        'source_versions': currency['source_versions'], 'terms': terms,
        'queries': {p: [{'GO_ID': c['GO_ID'], 'aspect': c['aspect'], 'published_score': c['score'],
                        'label': c.get('label')} for c in q['candidates']] for p, q in queries.items()},
        'scientific_accuracy_claimed': False, 'forecast_modified': False,
        'semantic_equivalence_claimed': False, 'automatic_mapping_or_pruning': False, 'graph_modified': False,
        'limitations': list(LIMITATIONS)}
    report['content_sha256'] = digest(report)
    out = new_output(output, index, publication)
    write_json(out/'notes.json', report)
    load_content_notes(out/'notes.json', sha(out/'notes.json'), manifest, queries,
                       manifest_file_sha256=publication_expected)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('index','index-expected','publication','publication-expected','output'):
        parser.add_argument('--'+name, required=True)
    result = prepare(**vars(parser.parse_args()))
    print(json.dumps({'format': result['format'], 'term_count': len(result['terms']),
                      'content_sha256': result['content_sha256']}))
