#!/usr/bin/env python3
"""Prepare a portable local judge demonstration from a verified graph packet.

Reuses the source-release and gold packet/decision APIs. No data are fetched,
published or relabelled. The software ZIP contains no source data. The separate
local data ZIP preserves the full baseline and all-abstain retained graph;
its existence does not clear upstream redistribution rights.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.gold_packet import load_packet, save_decisions, load_decisions
from biograph_steward.questions import answer_question, save_answer
from biograph_steward.reviews import read_run
from deploy.aws.prepare_release import prepare as prepare_source_release

RUN_ID = 'crc_judge_demo'


def inventory(folder):
    folder = Path(folder)
    if any(p.is_symlink() for p in folder.rglob('*')):
        raise ValueError('Portable bundles require ordinary files, not links.')
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def archive(folder, destination):
    names = inventory(folder)
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as output:
        for name in names:
            output.write(Path(folder) / name, name)
    with tempfile.TemporaryDirectory(prefix='biograph-judge-download-') as temporary:
        # macOS can return /var/folders through its /private/var alias. Replay
        # requires canonical ordinary roots; resolve our own temporary root
        # before extraction, without relaxing source-file symlink checks.
        temporary = Path(temporary).resolve(strict=True)
        with zipfile.ZipFile(destination) as source:
            if set(source.namelist()) != set(names):
                raise ValueError('Judge archive inventory changed.')
            source.extractall(temporary)
        if inventory(temporary) != names:
            raise ValueError('Extracted judge archive bytes changed.')
        if (temporary / 'handoff').exists():
            _, retained = load_decisions(temporary / 'handoff')
            reopened = read_run(temporary / 'runs' / RUN_ID)[2]
            if any(retained[key] != reopened[key] for key in ('nodes', 'edges', 'assertions')):
                raise ValueError('Portable workspace differs from its retained handoff graph.')
    return {'file': Path(destination).name, 'sha256': sha(destination),
            'bytes': Path(destination).stat().st_size, 'file_count': len(names)}


def runtime(output, ref):
    receipt = prepare_source_release(output, ref=ref, root=ROOT)
    return output / receipt['bundle'], receipt['git_commit']


def unpack_runtime(bundle, output):
    output.mkdir()
    with tarfile.open(bundle, 'r:gz') as source:
        for member in source.getmembers():
            path = Path(member.name)
            if (path.is_absolute() or '..' in path.parts or member.issym() or member.islnk()
                    or not (member.isdir() or member.isfile())):
                raise ValueError('Unexpected runtime archive member.')
            target = output / path
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.extractfile(member).read())


def instructions(*, real, commit, counts=None):
    opening = ('This package contains the full saved source workspace and graph handoff. '
               'The original source records remain candidates; every graph disposition is abstain. '
               'Data redistribution clearance is not established by this local package.\n\n'
               if real else 'This package contains MIT software and no retrieved source data. '
               'Its offline synthetic example demonstrates the software, not biology.\n\n')
    commands = ('python3 app.py serve --runs-dir runs --host 127.0.0.1 --port 8765 --no-browser'
                if real else 'python3 app.py demo --out runs/synthetic_demo\n'
                'python3 app.py serve --runs-dir runs --host 127.0.0.1 --port 8765 --no-browser')
    url = ('http://127.0.0.1:8765/?run=' + RUN_ID + '&question=question_judge_focus' if real
           else 'http://127.0.0.1:8765/?run=synthetic_demo')
    body = '# BioGraph Steward reviewer demonstration\n\n' + opening
    body += 'Code revision: `' + commit + '`. Python 3.10+; no installation, model, GPU or cloud account is required.\n\n'
    body += 'Unzip, open a terminal in this directory and run:\n\n```sh\n' + commands + '\n```\n\nOpen ' + url + '. Keep the terminal running. Ctrl+C stops the server.\n\n'
    body += '1. **Ask & explore:** inspect the cited candidate answer and bounded paths.\n'
    body += '2. **Evidence & sources:** inspect the original support and recorded assay context. Where SIGNOR is present, select **Regulation and experimental context**, then **Sites & context**; the BRAF example distinguishes phosphate addition from the reported protein response.\n'
    body += '3. **Export:** inspect the complete workspace, its source baseline and explicit decisions. The current-answer diagram is a selection, not the entire workspace.\n\n'
    if real:
        body += ('This saved example has ' + str(counts['nodes']) + ' entities, ' + str(counts['edges']) + ' evidence records and '
                 + str(counts['assertions']) + ' assertions. `handoff/retained_graph.json` is the full retained graph, '
                 '`handoff/edge_dispositions.jsonl` accounts for every original edge, and `handoff/baseline_packet/source/graph.json` is the original graph. '
                 'Undecided edges remain retained. `runs/' + RUN_ID + '/` is a complete, reopenable source workspace.\n\n'
                 'Original provider terms travel with the data. Do not treat the software MIT license as a data license; '
                 'this package is prepared locally and has not been published or cleared for redistribution.\n\n')
    body += ('For new public data, use **Data & saved work → Pharos disease cohort**, search `colorectal`, '
             'choose the exact returned disease and retrieve a bounded cohort. Inspect retrieval coverage before asking questions. '
             'This makes a new source snapshot; it does not reproduce the frozen graph byte-for-byte or establish additional-source licenses.\n\n'
             'Local acceptance, source preservation and these delivery checks do not establish biological truth. '
             'The model planner remains experimental; the guided workflow is the supported demonstration.\n')
    return body


def prepare(packet, output, *, ref='HEAD', focus=None, site='', runtime_builder=runtime):
    packet, output = Path(packet).resolve(), Path(output).absolute()
    manifest, original = load_packet(packet)
    before = inventory(packet)
    output = new_output(output, packet)
    source_bundle, commit = runtime_builder(output / 'runtime_release', ref)
    software = output / 'software'
    unpack_runtime(source_bundle, software)
    (software / 'README_DEMO.md').write_text(instructions(real=False, commit=commit))
    software_archive = archive(software, output / 'biograph_steward_software.zip')
    private = output / 'crc_local'
    shutil.copytree(software, private)
    decisions = output / 'decisions.json'
    decisions.write_bytes((packet / 'decisions.template.json').read_bytes())
    report = save_decisions(packet, decisions, private / 'handoff')
    _, retained = load_decisions(private / 'handoff')
    if (any(retained[key] != original[key] for key in ('nodes', 'edges', 'assertions'))
            or report['counts'].get('prune') or report['counts'].get('keep')):
        raise ValueError('The demonstration must preserve the original graph with only abstentions.')
    workspace = private / 'runs' / RUN_ID
    shutil.copytree(private / 'handoff/baseline_packet/source', workspace)
    reopened = read_run(workspace)[2]
    if reopened != original:
        raise ValueError('Copied workspace does not replay its original graph.')
    focus = focus or original['targets'][0]['id']
    answer = answer_question(reopened, focus, relations=['interactions'], view='candidates',
                             source_run=RUN_ID)
    save_answer(answer, private / 'runs/question_judge_focus')
    saved_answers = {'focus_answer_sha256': answer['answer_sha256']}
    if reopened.get('evidence_extension', {}).get('sources', {}).get('signor'):
        from biograph_steward.regulatory_sites import answer_regulatory_sites
        sites = answer_regulatory_sites(reopened, focus, direction='both', site=site, source_run=RUN_ID)
        write_json(private / 'site_context_answer.json', sites)
        saved_answers['site_context_answer_sha256'] = sites['content_sha256']
    (private / 'README_DEMO.md').write_text(instructions(real=True, commit=commit, counts=manifest['counts']))
    private_archive = archive(private, output / 'biograph_steward_crc_local.zip')
    if inventory(packet) != before:
        raise ValueError('Original source packet changed during delivery preparation.')
    result = {'format': 'biograph-steward.judge-delivery.v1', 'created_at': utcnow(),
        'git_commit': commit, 'source_packet_id': manifest['packet_id'], 'source_packet_sha256': before,
        'data_kind': manifest['data_kind'], 'counts': manifest['counts'], 'decisions': report['counts'],
        'saved_answers': saved_answers, 'software_archive': software_archive,
        'local_data_archive': private_archive, 'source_data_in_software_archive': False,
        'local_data_redistribution_cleared': False, 'cloud_resources_created': False,
        'source_fetches': 0, 'model_calls': 0, 'source_packet_unchanged': True,
        'independent_biological_validation': False,
        'distribution_note': 'Prepared locally only; no publication or permission inferred for underlying data.'}
    result['content_sha256'] = digest(result)
    write_json(output / 'delivery.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ref', default='HEAD')
    parser.add_argument('--focus')
    parser.add_argument('--site', default='')
    args = parser.parse_args()
    print(json.dumps(prepare(args.packet, args.out, ref=args.ref, focus=args.focus, site=args.site), indent=2))
