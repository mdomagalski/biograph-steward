# SPDX-License-Identifier: GPL-3.0-only
"""Verify local inputs for the preserved optional reference recipe.

This portable input guard does not acquire data, execute the upstream pipeline,
or evaluate predictions. ``describe`` reads delivery metadata only. ``verify``
requires an explicit access acknowledgement because hashing reference sources
is itself reference access; it is not a cloud/user approval workflow.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
FORMAT = 'biograph-steward.optional-reference-source-recipe.v1'


def need(condition, message):
    if not condition:
        raise ValueError('Reference recipe: ' + message)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def member(root, name):
    # Canonicalize a caller-supplied directory so ordinary OS aliases such as
    # macOS /tmp remain usable; the selected file itself must be ordinary.
    root = Path(root).resolve()
    relative = Path(name)
    need(not relative.is_absolute() and relative.parts
         and not any(p in ('.', '..') for p in relative.parts), 'relative ordinary source path required.')
    path = root / relative
    need(root.is_dir() and not path.is_symlink(), 'symlinked input files are not admitted.')
    need(path.is_file() and root.resolve() in path.resolve().parents, 'ordinary in-root input is missing: ' + name)
    return path


def load_manifest(path=HERE / 'sources.json'):
    path = Path(path)
    value = json.loads(path.read_text())
    need(value['format'] == FORMAT, 'unrecognized delivery manifest.')
    for name, spec in value['executed_driver_snapshots'].items():
        source = member(path.parent, name)
        need(source.stat().st_size == spec['bytes'] and sha(source) == spec['sha256'],
             'preserved executed driver changed: ' + name)
    return value, sha(path)


def headers(path, *, gaf):
    if not gaf:
        with path.open('rt', encoding='utf8') as stream:
            return [stream.readline().rstrip('\r\n'), stream.readline().rstrip('\r\n')]
    result = []
    # Read comments only; no annotation row is decoded for a header check.
    with gzip.open(path, 'rb') as stream:
        while True:
            first = stream.read(1)
            if first != b'!':
                break
            result.append((first + stream.readline()).decode('utf8').rstrip('\r\n'))
    return result


def verify(manifest, sources_root, author_root, *, acknowledge_reference_access=False,
           include_acquisition_archive=False):
    need(acknowledge_reference_access,
         'verify hashes reference inputs; use --acknowledge-reference-access only when that access is intended.')
    checked = {}
    for role, spec in manifest['sources'].items():
        if not spec['required_for_reference'] and not include_acquisition_archive:
            continue
        need(type(spec['bytes']) is int and spec['bytes'] > 0
             and re.fullmatch('[a-f0-9]{64}', spec['sha256']), 'complete source size and SHA256 pin required.')
        path = member(sources_root, spec['local_name'])
        need(path.stat().st_size == spec['bytes'], 'source size changed: ' + role)
        need(sha(path) == spec['sha256'], 'source SHA256 changed; do not substitute a later release: ' + role)
        if spec.get('header_required'):
            actual = headers(path, gaf=role.startswith('gaf_'))
            need(all(line in actual for line in spec['header_required']), 'recorded source header changed: ' + role)
        checked[role] = {'file': str(path), 'bytes': spec['bytes'], 'sha256': spec['sha256'],
                         'header_checked': bool(spec.get('header_required'))}
    author = manifest['native_helpers']
    checked_helpers = {}
    for name, pin in author['files_sha256'].items():
        path = member(author_root, name)
        need(sha(path) == pin, 'upstream helper differs from the pinned native source: ' + name)
        checked_helpers[name] = pin
    return {'format': 'biograph-steward.optional-reference-input-verification.v1',
            'status': 'pinned_input_bytes_verified_pipeline_not_executed', 'sources': checked,
            'native_helper_commit': author['commit'], 'native_helpers_sha256': checked_helpers,
            'runtime_verified': False, 'network_calls': False, 'native_helper_execution': False,
            'prediction_or_reference_scoring': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('describe', 'verify'))
    parser.add_argument('--sources-root', type=Path)
    parser.add_argument('--author-root', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--acknowledge-reference-access', action='store_true')
    parser.add_argument('--include-acquisition-archive', action='store_true')
    args = parser.parse_args(argv)
    manifest, pin = load_manifest()
    if args.phase == 'describe':
        result = {'manifest_sha256': pin, 'sources': manifest['sources'],
                  'recorded_runtime': manifest['recorded_runtime'],
                  'native_helpers': manifest['native_helpers'],
                  'reference_inputs_opened': False, 'native_helper_execution': False}
    else:
        need(args.sources_root is not None and args.author_root is not None
             and args.output is not None, 'verify requires --sources-root, --author-root and --output.')
        result = verify(manifest, args.sources_root, args.author_root,
                        acknowledge_reference_access=args.acknowledge_reference_access,
                        include_acquisition_archive=args.include_acquisition_archive)
        result['manifest_sha256'] = pin
        with args.output.open('x') as stream:
            json.dump(result, stream, sort_keys=True, indent=2)
            stream.write('\n')
    print(json.dumps(result, sort_keys=True, indent=2))
    return result


if __name__ == '__main__':
    main()
