#!/usr/bin/env python3
"""Verify one portable, source-bound submission example without scientific labels.

Uses only an existing assay-attached workbench run. All decisions stay abstain.
This is engineering acceptance of complete exports, not biological evaluation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.gold_packet import _decode, export_packet, load_packet, load_decisions, save_decisions

FORMAT = 'biograph-steward.submission-demo-verification.v1'
CODE = ('scripts/verify_submission_demo.py', 'biograph_steward/gold_packet.py',
        'biograph_steward/assertions.py', 'biograph_steward/assay_attachment.py')


def files(folder):
    folder = Path(folder)
    if (folder.is_symlink() or not folder.is_dir()
            or any(path.is_symlink() for path in folder.rglob('*'))):
        raise ValueError('The demonstration requires ordinary directories without symlinks.')
    return {path.relative_to(folder).as_posix(): sha(path)
            for path in sorted(folder.rglob('*')) if path.is_file()}


def require(checks, name, condition):
    if not condition:
        raise ValueError('Submission demonstration failed: ' + name)
    checks[name] = True


def render(report, graph):
    def text(value):
        return escape(str(value))

    summary = report['summary']
    cards = ''.join('<article><strong>' + text(value) + '</strong><span>' + text(label) + '</span></article>'
                    for label, value in (
                        ('Nodes preserved', summary['retained_nodes']),
                        ('Evidence edges retained', summary['retained_edges']),
                        ('Explicit abstentions', summary['decisions']['abstain']),
                        ('Source files preserved', summary['source_files_preserved'])))
    checks = ''.join('<li><span aria-label="passed">PASS</span> ' + text(name.replace('_', ' ')) + '</li>'
                     for name in report['checks'])
    nodes = {row['id']: row for row in graph['nodes']}
    rows = []
    for edge in graph['edges']:
        subject = nodes[edge['subject']].get('name') or edge['subject']
        obj = nodes[edge['object']].get('name') or edge['object']
        rows.append('<tr><td>' + text(subject) + '<br><small>' + text(edge['subject']) + '</small></td>'
                    '<td>' + text(edge['predicate']) + '<br><small>' + text(edge['record_kind']) + '</small></td>'
                    '<td>' + text(obj) + '<br><small>' + text(edge['object']) + '</small></td>'
                    '<td>Abstain<br><small>' + text(edge['status']) + '</small></td>'
                    '<td><details><summary>Inspect qualification</summary><pre>' +
                    text(json.dumps({'edge_id': edge['id'], 'qualifiers': edge.get('qualifiers', {}),
                        'publications': edge.get('publications', []),
                        'record_locators': edge.get('record_locators', []),
                        'evidence_record': edge.get('evidence_record')}, ensure_ascii=False, indent=2)) +
                    '</pre></details></td></tr>')
    assay_link = ('<a href="handoff/retained_assay_observations.jsonl">Selected assay observations</a> · '
                  '<a href="handoff/baseline_packet/source/assay_source/index.html">Preserved assay publication</a>')
    return '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BioGraph Steward · Submission example</title><style>
:root{font:16px/1.5 system-ui,sans-serif;color:#18333c;background:#f3f6f7}*{box-sizing:border-box}
body{margin:0}main{max-width:1180px;margin:auto;padding:32px 24px}h1{font-size:32px;line-height:1.2}h2{font-size:22px}
a{color:#086682}header{max-width:960px}.eyebrow{font-size:13px;letter-spacing:.08em;font-weight:700;color:#46636e}
.note{background:#fff4d9;border-left:4px solid #b87a15;padding:14px 18px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}
article,section{background:white;border:1px solid #dbe5e8;border-radius:9px;padding:18px;margin:18px 0}
article{margin:0}article strong{display:block;font-size:30px}article span{display:block;color:#48616b;font-size:14px}
.links{display:flex;gap:12px;flex-wrap:wrap}.checks{columns:2;list-style:none;padding:0}.checks li{padding:6px 0;break-inside:avoid}
.checks span{font-size:12px;font-weight:700;color:#207350;margin-right:8px}table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;vertical-align:top;border-bottom:1px solid #dbe5e8;padding:12px 8px}small{color:#48616b;font-size:12px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-width:420px}summary{cursor:pointer;color:#086682}
.table{overflow-x:auto}.small{font-size:13px;color:#48616b}@media(max-width:750px){.cards{grid-template-columns:repeat(2,1fr)}.checks{columns:1}main{padding:20px 14px}}
</style><main><header><div class="eyebrow">BIOGRAPH STEWARD · REPRODUCIBLE HANDOFF</div>
<h1>A complete graph and its decision trail</h1>
<p>This saved example combines an exact Pharos protein cohort with qualified published assay observations.
The export contains the resulting graph, one decision per original evidence edge and the full source baseline.</p>
<p class="note"><strong>All decisions are abstentions.</strong> No biological pruning or acceptance has been invented for this demonstration.
The checks establish source preservation, consistent graph support and a portable download. They do not establish scientific improvement.</p>
</header><div class="cards">''' + cards + '''</div><section><h2>Download and inspect</h2>
<p class="links"><a href="submission_handoff.zip" download>Complete submission package (ZIP)</a>
<a href="handoff/retained_graph.json">Resulting graph (JSON)</a>
<a href="handoff/edge_dispositions.jsonl">Complete edge decisions</a>
<a href="handoff/baseline_packet/source/graph.json">Original graph</a></p><p>''' + assay_link + '''</p>
<p class="small">The ZIP was extracted into a separate temporary directory and verified there using its own preserved inputs.
Source context, failed assays, licenses and original review histories travel with it. This local format still needs the organizers' final submission contract.</p>
</section><section><h2>What is in this example?</h2><div class="table"><table><thead><tr>
<th>Subject</th><th>Relationship</th><th>Object</th><th>Decision / source check</th><th>Evidence</th>
</tr></thead><tbody>''' + ''.join(rows) + '''</tbody></table></div>
<p class="small">Structural status describes source processing, not a scientific truth label. Assay nondetection is not biological absence.
The original panel is already consumed for evaluation; this export is not a fresh experiment.</p>
</section><section><h2>Verification completed</h2><ul class="checks">''' + checks + '''</ul>
<p><a href="verification.json">Machine-readable verification and SHA-256 hashes</a> ·
<a href="handoff/report.json">Disposition report</a> ·
<a href="handoff/assertion_changes.jsonl">Assertion support and review changes</a></p>
</section><p class="small">Created ''' + text(report['created_at']) + '''. No new retrieval, model call, paid compute or biological scoring was performed.</p></main></html>'''


def verify(run, output):
    run = Path(run).resolve()
    before = files(run)
    implementation = {name: sha(ROOT / name) for name in CODE}
    graph = _decode((run / 'graph.json').read_bytes())
    if graph.get('data_kind') != 'live_pharos' or 'assay_observations' not in graph:
        raise ValueError('Select a saved real Pharos cohort with its qualified assay attachment.')
    output = new_output(output, run)
    packet = output / 'source_packet'
    manifest = export_packet(run, packet)
    verified_manifest, verified_graph = load_packet(packet)
    decision_path = output / 'decisions.json'
    decision_path.write_bytes((packet / 'decisions.template.json').read_bytes())
    handoff = output / 'handoff'
    report = save_decisions(packet, decision_path, handoff)
    checked_report, retained = load_decisions(handoff)
    decisions = _decode(decision_path.read_bytes())
    checks = {}
    require(checks, 'source_packet_verified', verified_manifest == manifest and verified_graph == graph)
    require(checks, 'complete_ledger_with_only_unassessed_abstentions',
            len(decisions['decisions']) == len(graph['edges'])
            and {row['edge_id'] for row in decisions['decisions']} == {row['id'] for row in graph['edges']}
            and all(row['decision'] == 'abstain' and row['confidence'] is None for row in decisions['decisions']))
    require(checks, 'retained_graph_and_dispositions_verified', checked_report == report)
    require(checks, 'all_original_nodes_and_isolates_preserved', retained['nodes'] == graph['nodes'])
    require(checks, 'qualified_evidence_and_source_statuses_unchanged', retained['edges'] == graph['edges'])
    require(checks, 'assertion_support_and_review_states_unchanged', retained['assertions'] == graph['assertions'])
    require(checks, 'all_context_and_quarantine_records_preserved',
            [{k: v for k, v in row.items() if k != 'retention'} for row in retained['context_records']]
                == graph['context_records'] and retained['quarantine'] == graph['quarantine'])
    require(checks, 'assay_outcomes_qualifications_and_exclusions_preserved',
            [{k: v for k, v in row.items() if k != 'retention'} for row in retained['assay_observations']]
                == graph['assay_observations'])
    require(checks, 'all_packet_source_bytes_preserved',
            all(sha(handoff / 'baseline_packet/source' / name) == value
                and before[name] == value for name, value in manifest['input_files'].items()))
    handoff_files = files(handoff)
    archive = output / 'submission_handoff.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        for name in handoff_files:
            zipped.write(handoff / name, name)
    with tempfile.TemporaryDirectory(prefix='biograph-submission-download-') as temporary:
        standalone = Path(temporary).resolve()
        with zipfile.ZipFile(archive) as zipped:
            if set(zipped.namelist()) != set(handoff_files):
                raise ValueError('Downloaded ZIP inventory differs from the complete handoff.')
            zipped.extractall(standalone)
        standalone_report, standalone_graph = load_decisions(standalone)
        require(checks, 'standalone_extracted_download_verified',
                files(standalone) == handoff_files and standalone_report == report and standalone_graph == retained)
    require(checks, 'original_run_file_inventory_and_bytes_unchanged', files(run) == before)
    require(checks, 'implementation_files_unchanged_during_verification',
            implementation == {name: sha(ROOT / name) for name in CODE})
    observations = graph['assay_observations']
    summary = {'baseline_nodes': len(graph['nodes']), 'retained_nodes': len(retained['nodes']),
               'baseline_edges': len(graph['edges']), 'retained_edges': len(retained['edges']),
               'baseline_assertions': len(graph['assertions']), 'retained_assertions': len(retained['assertions']),
               'original_source_run_files': len(before), 'source_files_preserved': len(manifest['input_files']),
               'handoff_files': len(handoff_files), 'decisions': report['counts'],
               'evidence_by_kind': dict(sorted(Counter(row['record_kind'] for row in graph['edges']).items())),
               'selected_assay_observations': len(observations),
               'non_evaluable_assay_observations': sum(not row['evaluable'] for row in observations),
               'assay_status_counts': dict(sorted(Counter(row['assay_status'] for row in observations).items()))}
    result = {'format': FORMAT, 'created_at': utcnow(), 'status': 'passed',
              'purpose': 'engineering_submission_handoff_verification',
              'source_run': str(run), 'source_input_sha256': before,
              'source_packet_id': manifest['packet_id'],
              'source_graph_sha256': manifest['graph_sha256'],
              'decision_report_sha256': report['content_sha256'],
              'retained_graph_sha256': report['retained_graph_sha256'],
              'download_sha256': sha(archive), 'summary': summary, 'checks': checks,
              'implementation_sha256': implementation,
              'scientific_accuracy_measured': False, 'independent_biological_improvement_demonstrated': False,
              'automatic_pruning_performed': False, 'fresh_evaluation_outcomes_opened': False,
              'limitations': ['All abstentions remain; no scientific pruning decision was manufactured.',
                  'The assay panel is previously consumed and this is not a new biological comparison.',
                  'Successful preservation and validation do not establish biological correctness.',
                  'This is a local submission interface, not an organizer-approved file format or full KGX mapping.',
                  'The example validates export usability mechanically; intended-user task assessment remains separate.']}
    (output / 'index.html').write_text(render(result, graph), encoding='utf-8')
    result['files'] = files(output)
    result['content_sha256'] = digest(result)
    write_json(output / 'verification.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True, help='Existing real assay-attached workbench run')
    parser.add_argument('--out', type=Path, required=True, help='New immutable demonstration directory')
    args = parser.parse_args()
    try:
        result = verify(args.run, args.out)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({'status': result['status'], 'summary': result['summary'],
                      'report': str(args.out.resolve() / 'index.html')}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
