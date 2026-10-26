"""Pinned upstream export checks; schema validity is not scientific validity.

The upstream KGX/BMT constructors fetch mutable/default remote resources even
when validating local records. Only their resource loading is redirected here:
the model, imports, predicate map and prefix context are unchanged release bytes.
No validator rule or schema constraint is weakened to make a graph pass.
Run this optional audit in its dedicated process/environment, not an HTTP thread.
"""
from collections import Counter
from contextlib import ExitStack
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import urlopen

from .client import digest, write_json


MODEL_VERSION = '4.4.6'
PACKAGE_VERSIONS = {'kgx': '2.7.0', 'bmt': '1.4.8', 'linkml': '1.10.0',
                    'linkml-runtime': '1.10.0', 'jsonschema': '4.26.0'}
BASE = 'https://raw.githubusercontent.com/biolink/biolink-model/v4.4.6/'
RESOURCE_PATHS = {
    'biolink-model.yaml': 'biolink-model.yaml', 'attributes.yaml': 'attributes.yaml',
    'predicate_mapping.yaml': 'predicate_mapping.yaml',
    'biolink_model.context.jsonld': 'project/jsonld/biolink_model.context.jsonld',
    'biolink_model.schema.json': 'project/jsonschema/biolink_model.schema.json',
    'LICENSE': 'LICENSE',
}
RESOURCE_HASHES = {
    'biolink-model.yaml': '5837907e1eb579812856579feea5a099665252f2454bd6f950d63fbb00f4c9f0',
    'attributes.yaml': 'a8be9078ee33492141b1043989dc6ee05d51b9eaeb7e35d3dda1fef7fd42e07d',
    'predicate_mapping.yaml': 'b532220b1d33f0e51794566fa33a736905b5a41ed1fe38839f9e949cb58c796c',
    'biolink_model.context.jsonld': 'ca6b4cae21d6cb993824bfba85f148bade56d99749e3a930d048f149bb0f57b7',
    'biolink_model.schema.json': '968a2dd3fcdbac03fdfddf36b8acf337f201597387f4f3c07dbd87e13ce0076a',
    'LICENSE': '8cf88c8c0e912fee74bea0fb2bac7065beb251be971e896cc974fdb91ca7b6d9',
}


def resource_manifest():
    return {'biolink_model_version': MODEL_VERSION,
            'files': {name: {'url': BASE + RESOURCE_PATHS[name], 'sha256': sha}
                      for name, sha in RESOURCE_HASHES.items()}}


def verify_resources(directory):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Standards resources must be an ordinary directory.')
    allowed = set(RESOURCE_HASHES) | {'resources.json'}
    for path in directory.iterdir():
        if path.name not in allowed or path.is_symlink() or not path.is_file():
            raise ValueError('Unexpected or nonordinary standards resource: ' + path.name)
    for name, expected in RESOURCE_HASHES.items():
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing ordinary standards resource: ' + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Pinned standards resource hash mismatch: ' + name)
    manifest_path = directory / 'resources.json'
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except (UnicodeError, ValueError) as exc:
            raise ValueError('Invalid standards resource manifest.') from exc
        if manifest != resource_manifest():
            raise ValueError('Standards resource manifest differs from the pinned source bindings.')
    return resource_manifest()


def prepare_resources(directory):
    """Download only pinned public upstream resources into a new directory."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    for name, expected in RESOURCE_HASHES.items():
        with urlopen(BASE + RESOURCE_PATHS[name], timeout=60) as response:
            data = response.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Upstream standards resource differs from pinned bytes: ' + name)
        (directory / name).write_bytes(data)
    manifest = verify_resources(directory)
    write_json(directory / 'resources.json', manifest)
    return manifest


def _packages():
    found = {}
    for name, expected in PACKAGE_VERSIONS.items():
        try:
            found[name] = version(name)
        except PackageNotFoundError as exc:
            raise ValueError('Install requirements-export-validation.txt in the optional audit environment.') from exc
        if found[name] != expected:
            raise ValueError(f'Standards audit requires {name}=={expected}; found {found[name]}.')
    return found


def _schema_report(nodes, edges, schema):
    from jsonschema import validators
    validator_class = validators.validator_for(schema)
    validator_class.check_schema(schema)
    counts, examples = Counter(), []
    invalid = 0
    for kind, rows in (('node', nodes), ('edge', edges)):
        for row in rows:
            # Use the actual upstream class definition, not the schema's
            # permissive root object. KGX node category remains a JSON list.
            target = row['category'][0].split(':', 1)[-1] if kind == 'node' else 'Association'
            selected = dict(schema, **{'$ref': '#/$defs/' + target})
            errors = list(validator_class(selected).iter_errors(row))
            invalid += bool(errors)
            for error in errors:
                counts[kind + ':' + error.validator] += 1
                if len(examples) < 12:
                    examples.append({'kind': kind, 'id': row.get('id'),
                                     'path': list(error.path), 'message': error.message})
    return {'status': 'passed' if not invalid else 'failed',
            'invalid_records': invalid, 'error_counts': dict(sorted(counts.items())),
            'examples': examples, 'examples_truncated': sum(counts.values()) > len(examples),
            'schema_modified': False}


def _kgx_roundtrip(nodes, edges):
    """Exercise upstream JSONL Source/Sink without replacing published bytes."""
    from kgx.error_detection import ErrorDetecting
    from kgx.source.jsonl_source import JsonlSource
    from kgx.sink.jsonl_sink import JsonlSink
    owner = ErrorDetecting()
    differences = []
    with tempfile.TemporaryDirectory(prefix='biograph-kgx-roundtrip-') as temp:
        directory = Path(temp)
        for kind, rows in (('nodes', nodes), ('edges', edges)):
            (directory / (kind + '.jsonl')).write_text(
                ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
        sink = JsonlSink(owner, str(directory / 'roundtrip'))
        try:
            for kind, rows in (('nodes', nodes), ('edges', edges)):
                source = JsonlSource(owner)
                for record in source.parse(str(directory / (kind + '.jsonl')),
                                           default_provenance=''):
                    if record is not None:
                        (sink.write_node if kind == 'nodes' else sink.write_edge)(record[-1])
        finally:
            sink.finalize()
        counts = {}
        for kind, rows in (('nodes', nodes), ('edges', edges)):
            output = [json.loads(line) for line in
                      (directory / ('roundtrip_' + kind + '.jsonl')).read_text().splitlines()]
            counts[kind] = len(output)
            by_id = {row['id']: row for row in output}
            for row in rows:
                returned = by_id.get(row['id'])
                if returned != row:
                    changed = sorted(k for k in set(row) | set(returned or {})
                                     if row.get(k) != (returned or {}).get(k))
                    differences.append({'kind': kind, 'id': row['id'], 'changed_fields': changed})
    return {'status': 'passed' if not differences and counts == {'nodes': len(nodes), 'edges': len(edges)}
            else 'not_lossless', 'output_counts': counts, 'changed_records': len(differences),
            'examples': differences[:12], 'examples_truncated': len(differences) > 12,
            'default_provenance': '', 'messages': owner.get_errors(),
            'published_export_replaced_with_transformed_output': False}


def validate_projection(nodes, edges, resources_dir):
    """Audit an already constructed projection using frozen upstream artifacts.

    Returns independent KGX, JSON Schema and model-semantics results. In
    particular, a KGX pass must never erase an upstream schema/domain failure.
    All input values are inspected without KGX Transformer default insertion.
    """
    resources = verify_resources(resources_dir)
    resources_dir = Path(resources_dir).resolve()
    packages = _packages()
    if not edges:
        result = {
            'format': 'biograph-steward.standards-validation.v1',
            'status': 'no_supported_records', 'packages': packages, 'resources': resources,
            'input_sha256': digest({'nodes': nodes, 'edges': edges}),
            'counts': {'nodes': len(nodes), 'edges': 0},
            'kgx': {'status': 'not_evaluated', 'messages': {}},
            'published_json_schema': {'status': 'not_evaluated'},
            'declared_domain_range_and_predicate_audit': {'status': 'not_evaluated', 'issues': []},
            'kgx_jsonl_roundtrip': {'status': 'not_evaluated'},
            'full_conformance': False, 'biological_validation_performed': False,
            'notes': ['No supported edges were projected; an empty projection is not a validation success.'],
        }
        result['content_sha256'] = digest(result)
        return result
    from bmt import Toolkit

    predicate_url = BASE + 'predicate_mapping.yaml'
    predicate_text = (resources_dir / 'predicate_mapping.yaml').read_text()

    def recorded_get(url, *args, **kwargs):
        if url != predicate_url or args or kwargs:
            raise ValueError('Unexpected network request in frozen BMT resource loader.')
        return SimpleNamespace(text=predicate_text)

    # BMT's published constructor unconditionally requests its predicate map.
    # Replay that exact source response; all model operations remain upstream.
    with patch('bmt.toolkit.requests.get', side_effect=recorded_get):
        toolkit = Toolkit(schema=str(resources_dir / 'biolink-model.yaml'),
                          predicate_map=predicate_url)
    if toolkit.get_model_version() != MODEL_VERSION:
        raise ValueError('Loaded model version differs from the pinned model.')

    # kgx.utils.kgx_utils initializes Toolkit() during import. Supply the same
    # frozen official toolkit at that load boundary, before importing KGX.
    with patch('bmt.Toolkit', return_value=toolkit):
        from kgx.validator import Validator
        import kgx.config as kgx_config

    context = json.loads((resources_dir / 'biolink_model.context.jsonld').read_text())['@context']
    with ExitStack() as stack:
        stack.enter_context(patch.object(Validator, 'get_toolkit', return_value=toolkit))
        stack.enter_context(patch.dict(kgx_config.jsonld_context_map, {'biolink': context}))
        validator = Validator()
        for node in nodes:
            validator.analyse_node(node['id'], node)
        for edge in edges:
            validator.analyse_edge(edge['subject'], edge['object'], edge['id'], edge)
        kgx_errors = validator.get_errors()
        probe = Validator()
        probe.validate_edge_predicate('UniProtKB:P00533', 'UniProtKB:P01116',
                                      {'predicate': 'biolink:interacts_with'}, toolkit)
        mixin_probe = {'predicate': 'biolink:interacts_with',
                       'model_mixin': bool(toolkit.is_mixin('biolink:interacts_with')),
                       'kgx_reports_error': bool(probe.get_errors())}
        roundtrip = _kgx_roundtrip(nodes, edges)

    by_id = {n['id']: n for n in nodes}
    semantic_issues = []
    for edge in edges:
        element = toolkit.get_element(edge['predicate'])
        if element is None:
            semantic_issues.append({'edge_id': edge['id'], 'reason': 'unknown_predicate'})
            continue
        if element.mixin or element.abstract or element.deprecated:
            semantic_issues.append({'edge_id': edge['id'], 'reason': 'mixin_abstract_or_deprecated_predicate'})
        for role, expected in (('subject', element.domain), ('object', element.range)):
            if not expected or expected not in toolkit.view.all_classes():
                continue
            categories = by_id.get(edge[role], {}).get('category', [])
            ancestors = {ancestor for category in categories
                         for ancestor in toolkit.get_ancestors(category, mixin=True)}
            if expected not in ancestors:
                semantic_issues.append({'edge_id': edge['id'], 'reason': role + '_outside_declared_domain_or_range',
                                        'categories': categories, 'declared_class': expected})

    schema = json.loads((resources_dir / 'biolink_model.schema.json').read_text())
    result = {
        'format': 'biograph-steward.standards-validation.v1',
        'status': 'audited_with_limitations',
        'packages': packages, 'resources': resources,
        'input_sha256': digest({'nodes': nodes, 'edges': edges}),
        'counts': {'nodes': len(nodes), 'edges': len(edges)},
        'kgx': {'status': 'passed' if not kgx_errors.get('ERROR') else 'failed',
                'messages': kgx_errors, 'predicate_mixin_probe': mixin_probe,
                'scope': 'KGX field, prefix, category and predicate checks; no biological validation.'},
        'published_json_schema': _schema_report(nodes, edges, schema),
        'kgx_jsonl_roundtrip': roundtrip,
        'declared_domain_range_and_predicate_audit': {
            'status': 'passed' if not semantic_issues else 'review_required',
            'issues': semantic_issues,
            'method': 'Inspect pinned BMT elements and category ancestors; preserve model constraints unchanged.',
            'known_upstream_issue': 'https://github.com/biolink/biolink-model/issues/1606'},
        'resource_loading': 'Offline replay of pinned official resources; validator algorithms and schemas unchanged.',
        'full_conformance': False,
        'biological_validation_performed': False,
        'notes': [
            'KGX permits non-Biolink extension fields; the published closed JSON Schema rejects them.',
            'Biolink 4.4.6 Protein/Pathway category arrays fail the published category enum constraint.',
            'The supported LinkML 1.10.0 regeneration path reproduces the category-array failure.',
            'Protein participates_in Pathway conflicts with the declared occurrent domain; upstream issue 1606 documents it.',
            'Do not strengthen annotation-existence, drug-listing or mixed-source PPI records into unsupported relationships.',
        ],
    }
    result['content_sha256'] = digest(result)
    return result
