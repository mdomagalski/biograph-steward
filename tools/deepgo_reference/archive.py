"""Index verified author archives and copy an explicit inference-only allowlist.

Uses tarfile's streaming reader and the repository's existing seal/output
conventions. Unlike the small CAFA intake, multi-GB archives are hashed without
read_bytes/getmembers, and unselected link inventory is never followed.
No pickle, checkpoint, annotation, sequence or reference content is interpreted.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output


def need(value, message):
    if not value:
        raise ValueError('DeepGO archive: ' + message)


def sealed(value):
    return {**value, 'content_sha256': digest(value)}


def fingerprints(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink(), 'archive must be ordinary.')
    sha, md5, size = hashlib.sha256(), hashlib.md5(), 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            sha.update(block); md5.update(block); size += len(block)
    return {'bytes': size, 'sha256': sha.hexdigest(), 'md5': md5.hexdigest()}


def canonical(name):
    need(isinstance(name, str) and name and '\\' not in name and '\x00' not in name,
         'invalid member path.')
    value = PurePosixPath(name)
    need(not value.is_absolute() and '..' not in value.parts, 'unsafe member path.')
    result = str(value)
    need(result not in {'.', ''}, 'empty member path.')
    return result


def member_record(member):
    return {'name': member.name, 'canonical_name': canonical(member.name),
            'bytes': member.size, 'ordinary_file': member.isfile(),
            'directory': member.isdir(), 'sparse': member.issparse(),
            'symbolic_link': member.issym(), 'hard_link': member.islnk(),
            'type_hex': member.type.hex(),
            'link_target_not_followed': member.linkname if member.issym() or member.islnk() else None}


def index(archive, expected_bytes, expected_md5, output):
    archive, output = Path(archive), Path(output)
    need(not output.exists(), 'choose a new immutable index.')
    fp = fingerprints(archive)
    need(fp['bytes'] == expected_bytes and fp['md5'] == expected_md5,
         'publisher size/checksum differs before archive parsing.')
    rows, names, total = [], set(), 0
    with tarfile.open(archive, 'r|gz') as stream:
        for member in stream:
            row = member_record(member)
            need(row['canonical_name'] not in names, 'canonical member names repeat.')
            need(member.size >= 0, 'negative member size.')
            names.add(row['canonical_name']); rows.append(row); total += member.size
            need(len(rows) <= 20000 and total <= 200 * 1024**3,
                 'archive exceeds reviewed metadata/expansion bounds.')
    result = sealed({'format': 'biograph-steward.deepgo-archive-index.v1',
        'created_at': utcnow(), 'archive': fp, 'members': rows,
        'expanded_file_bytes': total, 'member_count': len(rows),
        'member_contents_interpreted': False, 'links_followed': False,
        'extracted_files': 0})
    write_json(output, result)
    return result


def inference_member(name):
    """Only model/ontology metadata or the separately dated sequence FASTA."""
    name = canonical(name)
    base = PurePosixPath(name).name
    if base in {'go.obo', 'go.norm', 'go-plus.norm', 'uniprot_sprot.fasta.gz',
                'esm2_t36_3B_UR50D.pt', 'esm2_t36_3B_UR50D-contact-regression.pt'}:
        return True
    return bool(re.search(
        r'(?:^|/)(?:mf|bp|cc)/(?:terms\.pkl|'
        r'(?:deepgozero_esm_plus_[0-9]+|mlp_esm(?:_[0-9]+)?|'
        r'deepgogat(?:_esm|_mf|_mfpreds)?(?:_plus)?(?:_[0-9]+)?)\.th)$', name))


def extract(archive, index_file, index_sha256, selection, output):
    archive, index_file, selection = map(Path, (archive, index_file, selection))
    need(fingerprints(index_file)['sha256'] == index_sha256, 'index FILE pin differs.')
    saved = json.loads(index_file.read_text())
    need(saved['format'] == 'biograph-steward.deepgo-archive-index.v1'
         and saved['content_sha256'] == digest({k: v for k, v in saved.items() if k != 'content_sha256'}),
         'index content seal differs.')
    need(fingerprints(archive) == saved['archive'], 'archive changed since indexing.')
    requested = json.loads(selection.read_text())
    need(isinstance(requested, dict) and requested, 'selection must map exact members to new relative paths.')
    members = {r['canonical_name']: r for r in saved['members']}
    need(len(members) == len(saved['members']), 'index repeats canonical members.')
    chosen, destinations = {}, set()
    for source, destination in requested.items():
        source, destination = canonical(source), canonical(destination)
        need(source not in chosen and destination not in destinations, 'selection repeats a source/destination.')
        need(destination != 'extraction.json'
             and not any(PurePosixPath(destination) in PurePosixPath(x).parents
                         or PurePosixPath(x) in PurePosixPath(destination).parents for x in destinations),
             'selection collides with a file/directory or output receipt.')
        need(source in members and inference_member(source), 'member is not admitted inference metadata/weights/FASTA.')
        row = members[source]
        need(row['ordinary_file'] and not any(row[k] for k in ('sparse', 'symbolic_link', 'hard_link')),
             'selected member is nonordinary; no link resolution is permitted.')
        chosen[source] = destination; destinations.add(destination)
    need(sum(members[x]['bytes'] for x in chosen) <= 100 * 1024**3,
         'selected expansion exceeds reviewed bound.')
    out = new_output(output, archive, index_file, selection)
    copied, seen = {}, set()
    with tarfile.open(archive, 'r|gz') as stream:
        for member in stream:
            name = canonical(member.name)
            if name not in chosen:
                continue
            need(name not in seen and member_record(member) == members[name], 'selected member metadata differs.')
            seen.add(name); target = out / chosen[name]; target.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(member) as source, target.open('xb') as destination:
                shutil.copyfileobj(source, destination, 8 * 1024 * 1024)
            fp = fingerprints(target)
            need(fp['bytes'] == member.size, 'selected member truncated.')
            copied[chosen[name]] = {'source_member': name, **fp}
    need(seen == set(chosen), 'selected member absent while streaming.')
    result = sealed({'format': 'biograph-steward.deepgo-selected-extraction.v1',
        'created_at': utcnow(), 'archive': saved['archive'], 'index_file_sha256': index_sha256,
        'selection_file_sha256': fingerprints(selection)['sha256'], 'files': copied,
        'unselected_member_contents_interpreted': False, 'links_followed': False,
        'pickle_or_checkpoint_deserialized': False, 'source_or_model_executed': False})
    write_json(out / 'extraction.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('index')
    for key in ('archive', 'expected-md5', 'output'): p.add_argument('--' + key, required=True)
    p.add_argument('--expected-bytes', required=True, type=int)
    p = sub.add_parser('extract')
    for key in ('archive', 'index-file', 'index-sha256', 'selection', 'output'): p.add_argument('--' + key, required=True)
    args = vars(parser.parse_args()); command = args.pop('command')
    value = globals()[command](**args)
    print(json.dumps({'format': value['format'], 'content_sha256': value['content_sha256']}))
