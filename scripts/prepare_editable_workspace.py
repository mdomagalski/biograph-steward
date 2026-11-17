#!/usr/bin/env python3
"""Package an existing source workspace for offline review without changing it.

Reuse the committed source-release, question verifier and recorded-agent reader.
Write a standard ZIP directly from pinned inputs so large source folders do not
need a second staging copy. This performs no upload, retrieval or inference.
"""
import argparse
import ast
import gc
import hashlib
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.prepare_judge_demo import inventory, runtime, unpack_runtime
from biograph_steward.client import utcnow, write_json
from biograph_steward.file_utils import new_output, sha

IDENTIFIER = re.compile(r'[A-Za-z0-9_-]{1,80}')


def files(folder):
    folder = Path(folder).absolute()
    if (not folder.is_dir() or folder.is_symlink()
            or any(p.is_symlink() for p in folder.parents)):
        raise ValueError('Use an ordinary complete source directory.')
    result = {}
    for p in sorted(folder.rglob('*')):
        if p.is_symlink() or not (p.is_file() or p.is_dir()):
            raise ValueError('Linked or special source files cannot enter a local copy.')
        if p.is_file():
            if p.name in {'.env', 'runtime.env', 'credentials', 'cases.private.jsonl', 'labels.private.jsonl'}:
                raise ValueError('A private configuration or reference file entered the selected input.')
            result[p.relative_to(folder).as_posix()] = {'bytes': p.stat().st_size, 'sha256': sha(p)}
    return result


def launcher(run_id, question_id, job_id):
    params = 'run=' + run_id + '&question=' + question_id + '&agent_job=' + job_id + '&view=data'
    return '''"""Open your editable workspace on this computer only."""
import argparse
from pathlib import Path
import sys
import webbrowser

if __name__ == '__main__':
    from biograph_steward.client import ENDPOINT
    from biograph_steward.webapp import create_server
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0, help='Optional port; default chooses an available local port.')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    server = create_server(args.port, folder / 'runs', ENDPOINT, folder / '.pharos_cache',
                           host='127.0.0.1', access_token=None, saved_data_only=False)
    url = 'http://127.0.0.1:' + str(server.server_port) + '/?''' + params + ''''
    print('BioGraph Steward local review copy: ' + url, flush=True)
    print('Saving a review creates a new run and preserves the original. Stop with Ctrl+C.', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
'''


def prepare(source, question, job, output, runtime_ref, archive_name):
    source, question, job = (Path(p).absolute() for p in (source, question, job))
    if any(not IDENTIFIER.fullmatch(p.name) for p in (source, question, job)):
        raise ValueError('Use bounded saved-folder identifiers.')
    if len({source.parent, question.parent, job.parent}) != 1:
        raise ValueError('The workspace, saved question and agent record must share their runs root.')
    selected = {p.name: files(p) for p in (source, question, job)}
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}\.zip', archive_name):
        raise ValueError('Use an ordinary ZIP basename.')
    output = new_output(output, source, question, job)
    from biograph_steward.reviews import read_run
    from biograph_steward.questions import graph_basis, verify_answer, verify_ranking_files
    from biograph_steward.source_agent_jobs import read_source_agent_job
    snapshot, _, graph = read_run(source)
    if graph.get('qualified_view') or graph.get('data_kind') != 'live_pharos':
        raise ValueError('Use a real source workspace that permits recording reviews.')
    answer = json.loads((question / 'question.json').read_text())
    verify_answer(answer)
    verify_ranking_files(answer, question)
    if answer.get('source_run') != source.name or answer.get('graph_basis_sha256') != graph_basis(graph):
        raise ValueError('Saved question does not belong to this exact graph.')
    record = read_source_agent_job(job, source.parent)
    if not record['actual_model_run'] or record['status'] != 'completed' or record['source_run'] != source.name:
        raise ValueError('Use the completed actual agent record for this workspace.')
    counts = {'entities': len(graph['nodes']), 'evidence_records': len(graph['edges']),
              'assertions': len(graph['assertions'])}
    snapshot_pin = graph['snapshot_sha256']
    del graph, snapshot, answer, record
    gc.collect()
    bundle, commit = runtime(output / 'runtime_release', runtime_ref)
    stage = output / 'runtime_and_instructions'
    unpack_runtime(bundle, stage)
    text = launcher(source.name, question.name, job.name)
    ast.parse(text)
    (stage / 'START_EDITABLE_LOCAL.py').write_text(text)
    opening = f'''BIOGRAPH STEWARD — YOUR LOCAL REVIEW COPY

This is a complete copy of the source evidence workspace, its saved question
and recorded agent investigation. Its original graph and source
files are unchanged. The copy has {counts['entities']:,} entities and
{counts['evidence_records']:,} evidence records. All source terms and attribution
travel with the data; the software MIT license does not relicense those data.

OPEN THE COPY
1. Extract this ZIP into a new folder. Keep its runs folder names unchanged.
2. Install Python 3.10+ if it is not already available. No pip installation,
   GPU, running model, AWS account, access token or fresh retrieval is needed.
3. Open a terminal in the extracted folder and run:

   python3 START_EDITABLE_LOCAL.py

   On Windows, use: py START_EDITABLE_LOCAL.py

The launcher chooses an available port, prints its local address and opens your
browser. It listens only on 127.0.0.1, on your own computer. Keep the terminal
running. First opening checks the saved sources and can take some time.

EXPLORE THE SAVED GRAPH
Question & graph opens an overview of the returned results. Show in graph
focuses one result; Show all results restores the overview. Browse saved
workspace opens its bounded graph and record tables. The question diagram
is a selection from the workspace, rather than every saved entity at once.

Under Explore paths in this saved graph, choose a connected example or type a
name to filter starting entities. End suggestions follow saved relationships,
direction, evidence state and connection limits. Examples use saved records;
a path does not establish a biological mechanism. Results & evaluation explains
source qualification and the available assessments. Hosted assessment pages
and optional global inspectors are separate from this local source package.

RECORD YOUR EVIDENCE REVIEW
1. Read the question and graph. Under Inspect sources, select a saved claim and
   choose Guide me through this source.
2. Choose Record evidence review. Enter Reviewer, Decision and Reason and
   evidence reviewed.
3. Choose Save review in a new run. Your reviewed copy opens with a link to the
   earlier run. The earlier graph, source files and review history stay intact.

For a software demonstration, choose provisional and explain that the source
still needs scientific review. A local decision records your judgment; it is
not an independent biological benchmark label. Review edits change the local
reviewed evidence view. The source records remain preserved.

Your new runs are stored under runs/ in this extracted folder. Allow at least
2 GB of free disk space for extraction and a reviewed copy. Stop with Ctrl+C.
Optional: --no-browser prints the address without opening a browser; --port
sets a particular local port.

SCOPE AND REPRODUCIBILITY
This copy contains workspace {source.name}. Other hosted workspaces, cloud
assessments, optional global inspectors and the Neptune mirror stay separate.
Opening or reviewing this saved graph makes no model calls. New model
questions or source retrieval need explicit action and configuration.

The captured Pharos baseline and the separately attached native sources retain
their original versions, citations, qualifications and candidate states. Missing
evidence is not a negative biological finding. The software is not a general
node-and-edge drawing editor. Read runs/{source.name}/source_licenses.json for
provider terms. Preserved provenance can contain historical local file paths.

Code revision: {commit}
WORKSPACE_FILES.json records every original workspace/question/job file hash.
The recorded agent can be verified offline without new inference:
   python3 app.py source-agent-verify --job runs/{job.name} --runs-dir runs
'''
    (stage / 'OPEN_WORKSPACE.txt').write_text(opening)
    (stage / 'SOURCE_TERMS.txt').write_text('''SOURCE ATTRIBUTION AND TERMS

The application core is MIT licensed. Each source dataset retains its own terms;
this package does not grant a new blanket data license. The original per-source
notices, releases, record attributions and references are preserved inside the
workspace's source_licenses.json and extension_sources directory.

Gene Ontology and UniProt GOA data: CC BY4.0; preserve release, source/creator
attribution and references. https://geneontology.org/docs/go-citation-policy/
UniProt: CC BY4.0 for copyrightable database content.
https://www.uniprot.org/api-documentation/support-data
STRING12.5: CC BY4.0 with source/version attribution; incorporated source
material retains its original terms. https://string-db.org/cgi/access
Pharos/TCRD aggregates primary sources whose individual terms apply.
https://pharos.nih.gov/about
KEGG pathway-membership identifiers are present in the Pharos capture.
Consult applicable KEGG terms: https://www.kegg.jp/kegg/legal.html

No source has been silently removed or substituted. Exact byte preservation
establishes reproducibility of the saved copy, not biological truth or a new
license for all upstream material. Raw external evaluation/reference cases,
credentials, patient records and model weights are not part of this copy.
''')
    registration = {'format': 'biograph-steward.source-agent-reviewer-entry.v1',
                    'source_run': source.name, 'question_id': question.name,
                    'job_id': job.name, 'job_manifest_sha256': sha(job / 'manifest.json')}
    (stage / 'runs').mkdir()
    write_json(stage / 'runs/reviewer_agent_entry.json', registration)
    manifest = {'format': 'biograph-steward.portable-source-workspace.v1',
                'runtime_commit': commit, 'runtime_bundle_sha256': sha(bundle),
                'source_run': source.name, 'question_id': question.name,
                'agent_job': job.name, 'source_snapshot_sha256': snapshot_pin,
                'source_manifest_sha256': sha(source / 'run_manifest.json'),
                'source_graph_sha256': sha(source / 'graph.json'),
                'files': {f'runs/{name}/{rel}': pin for name, names in selected.items() for rel, pin in names.items()},
                'counts': counts, 'new_model_calls': 0, 'fresh_source_retrieval': 0,
                'public_shared_workspace_editing_enabled': False}
    write_json(stage / 'WORKSPACE_FILES.json', manifest)
    inputs = {name: stage / name for name in inventory(stage)}
    for folder in (source, question, job):
        inputs.update({f'runs/{folder.name}/{name}': folder / name for name in selected[folder.name]})
    archive = output / archive_name
    expected = {name: {'bytes': path.stat().st_size, 'sha256': sha(path)} for name, path in inputs.items()}
    with ZipFile(archive, 'x', compression=ZIP_DEFLATED) as z:
        for name, path in sorted(inputs.items()):
            z.write(path, name)
    with ZipFile(archive) as z:
        if len(z.namelist()) != len(expected) or set(z.namelist()) != set(expected) or z.testzip() is not None:
            raise ValueError('Portable archive inventory or CRC differs.')
        for name, pin in expected.items():
            h = hashlib.sha256()
            with z.open(name) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(block)
            if h.hexdigest() != pin['sha256'] or z.getinfo(name).file_size != pin['bytes']:
                raise ValueError('A portable archive member changed.')
    if any(files(p) != selected[p.name] for p in (source, question, job)):
        raise ValueError('Original workspace or recorded result changed during packaging.')
    receipt = {'format': 'biograph-steward.editable-workspace-package.v1', 'created_at': utcnow(),
               'runtime_commit': commit, 'file': archive.name, 'bytes': archive.stat().st_size,
               'sha256': sha(archive), 'members': len(expected),
               'expanded_bytes': sum(x['bytes'] for x in expected.values()),
               'source_files_preserved': len(manifest['files']), 'counts': counts,
               'source_run': source.name, 'question_id': question.name, 'agent_job': job.name,
               'source_manifest_sha256': manifest['source_manifest_sha256'],
               'source_graph_sha256': manifest['source_graph_sha256'], 'snapshot_sha256': snapshot_pin,
               'question_sha256': sha(question / 'question.json'),
               'all_original_files_unchanged': True, 'archive_member_hashes_and_CRC_verified': True,
               'new_model_calls': 0, 'fresh_source_retrieval': 0, 'upload_or_publication_performed': False}
    write_json(output / 'package_receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--question', type=Path, required=True)
    p.add_argument('--agent-job', type=Path, required=True)
    p.add_argument('--runtime-ref', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--archive-name', default='BioGraph_Steward_KRAS_Editable_Workspace.zip')
    a = p.parse_args()
    print(json.dumps(prepare(a.run, a.question, a.agent_job, a.out, a.runtime_ref, a.archive_name), indent=2))
