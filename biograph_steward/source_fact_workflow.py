"""Immutable source-fact artifacts and review-only claim checks; no model or graph writes."""
from copy import deepcopy
import hashlib
from html import escape
import json
from pathlib import Path

from .client import digest, utcnow, write_json
from .crc_pilot import new_output, sha
from .fact_comparison import compare_claim
from .literature import load_literature
from .source_facts import compile_source, validate_dossier

ARTIFACT = 'source-fact-artifact.v1'
CHECK = 'source-fact-check.v1'
FILES = {'facts': 'source_facts.json', 'comparison': 'comparison.json'}


def _page(title, content):
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + escape(title) + '</title><style>'
            'body{font:16px/1.6 system-ui;color:#172b3a;background:#f4f7f9;margin:0}'
            'main{max-width:1050px;margin:auto;padding:28px}h1{line-height:1.2}'
            'section,article{background:white;border:1px solid #d9e3e9;border-radius:10px;padding:20px;margin:18px 0}'
            'blockquote{border-left:4px solid #147c83;padding:8px 16px;margin:12px 0;background:#eaf6f5}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf3f7;padding:12px}'
            'small,.small{color:#52697b;font-size:13px}a{color:#086b85}'
            'table{border-collapse:collapse;width:100%}th,td{padding:8px;text-align:left;border-bottom:1px solid #d9e3e9;vertical-align:top}'
            '.scroll{overflow:auto}.notice{padding:12px;background:#fff4df;border-left:4px solid #9b650e}'
            'textarea{display:block;width:100%;box-sizing:border-box;font:inherit;padding:10px;margin:10px 0}'
            'button{padding:10px 16px;background:#147c83;color:white;border:0;border-radius:6px;font:inherit}'
            '</style><main><a href="/">BioGraph Steward</a>' + content + '</main></html>')


def _json(value):
    return escape(json.dumps(value, ensure_ascii=False, indent=2))


def _spans(provenance):
    parts = []
    for field, spans in provenance.items():
        for s in spans:
            parts.append('<p><strong>' + escape(field) + '</strong></p><blockquote>' + escape(s['text']) +
                         '</blockquote><p class="small">' + escape(s['locator']) + ' · passage ' +
                         str(s['passage_index']) + ' · Unicode offsets [' + str(s['start']) + ', ' +
                         str(s['end']) + ')</p>')
    return ''.join(parts)


def render_facts(dossier):
    title = 'Source facts — ' + dossier['source_id']
    records = []
    for number, r in enumerate(dossier['records'], 1):
        fields = [('regimen', 'Treatment arm'), ('molecular', 'Molecular scope'), ('endpoint', 'Endpoint')]
        if r['kind'] == 'response_rate':
            fields += [('value', 'Response (%)'), ('evaluable_n', 'Evaluable patients')]
        else:
            fields += [('comparator', 'Comparator'), ('significance', 'Author-stated significance'),
                       ('p_value', 'Reported P value'), ('effect_direction', 'Reported direction')]
        rows = ''.join('<tr><th>' + label + '</th><td>' +
                       ('Unresolved' if r[key] is None else _json(r[key])) + '</td></tr>' for key, label in fields)
        records.append('<article><h2>Draft result ' + str(number) + ' · ' +
                       ('Response rate' if r['kind'] == 'response_rate' else 'Survival significance') +
                       '</h2><p class="small">' + escape(r['id']) + ' · ' + escape(r['association_status']) +
                       '</p><table>' + rows + '</table><details><summary>Exact source spans by field</summary>' +
                       _spans(r['provenance']) + '</details></article>')
    gaps = '<p>No additional flagged result sentences.</p>'
    if dossier['coverage_gaps']:
        gaps = '<pre>' + _json(dossier['coverage_gaps']) + '</pre>'
    source = ''.join('<h3>' + escape(p.get('section') or 'Abstract') + '</h3><p>' + escape(p['text']) +
                     '</p><p class="small">' + escape(p['locator']) + '</p>' for p in dossier['paper']['abstract'])
    # The form is useful only when served under a protected, saved artifact route.
    # User text is sent as JSON and never inserted into HTML.
    form = '''<section id="claim-check"><h2>Check a claim against these records</h2>
<p>Experimental scope: explicit response-rate sentences and survival-significance sentences.
Other wording is left unresolved. A compatible result still requires review.</p>
<details><summary>Supported sentence forms</summary><p>The [complete regimen] combination group had a reported response rate of [number]% in evaluable patients.</p>
<p>[Drug] monotherapy had a reported response rate of [number]% in evaluable patients.</p>
<p>In the [molecular] stratum, the increase in [overall survival / progression-free survival] with [complete regimen] compared with [comparator] was [nonsignificant / statistically significant].</p></details>
<form id="fact-form"><label for="claim">Claim</label><textarea id="claim" required maxlength="4000" rows="4"></textarea>
<button id="check-button" type="submit">Check and save for review</button><p id="check-status" role="status"></p></form></section>
<script>
const form=document.getElementById('fact-form'),statusBox=document.getElementById('check-status');
const match=location.pathname.match(/^\\/api\\/source-facts\\/([A-Za-z0-9_-]{1,80})\\/(?:report\\.html)?$/);
if(!match){document.getElementById('check-button').disabled=true;statusBox.textContent='Open this saved dossier in the workspace to check a claim.';}
form.addEventListener('submit',async event=>{event.preventDefault();if(!match)return;
 const button=document.getElementById('check-button');button.disabled=true;statusBox.textContent='Checking source records…';
 try{const response=await fetch('/api/fact-check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({facts_id:match[1],claim:document.getElementById('claim').value})});
 const data=await response.json();if(!response.ok)throw new Error(data.error||'Claim check failed.');
 const link=document.createElement('a');link.href=data.report_url;link.textContent='Inspect saved result: '+data.status;statusBox.replaceChildren(link);
 }catch(error){statusBox.textContent=error.message;}finally{button.disabled=false;}});
</script>'''
    return _page(title, '<h1>' + escape(title) + '</h1><p>' + escape(dossier['paper'].get('title', '')) +
                 '</p><p class="notice">Draft source-pattern extraction. Exact spans and reproducible bindings are software checks; '
                 'they do not establish scientific truth. No graph or review decisions are changed.</p>' +
                 '<p><a href="https://pubmed.ncbi.nlm.nih.gov/' + dossier['paper']['pmid'] +
                 '/" rel="noreferrer">Open PubMed source</a> · <a href="source_facts.json">Download source facts JSON</a></p>' +
                 '<p>' + str(len(records)) + ' draft records. Coverage gaps are flags within this narrow pattern scope, '
                 'not an inventory of everything the paper reports.</p>' + ''.join(records) +
                 '<section><h2>Coverage gaps</h2>' + gaps +
                 '<details><summary>Declared extraction scope</summary><pre>' + _json(dossier['compiler']) + '</pre></details></section>' + form +
                 '<section><details><summary>Complete supplied abstract</summary>' + source + '</details></section>')


def render_comparison(payload):
    result = payload['comparison']
    cards = []
    for candidate in result['candidates']:
        rows = ''.join('<tr><td>' + escape(f['field']) + '</td><td>' + escape(f['status']) +
                       '</td><td><pre>' + _json(f['claim_value']) + '</pre></td><td><pre>' +
                       _json(f['source_value']) + '</pre></td><td>' + escape(f.get('conflict_kind') or '') +
                       '</td></tr>' for f in candidate['facets'])
        record = next(r for r in payload['dossier']['records'] if r['id'] == candidate['record_id'])
        cards.append('<section><h2>' + escape(candidate['record_id']) + ' · ' + escape(candidate['status']) +
                     '</h2><div class="scroll"><table><thead><tr><th>Facet</th><th>Check</th><th>Claim</th><th>Source</th><th>Difference</th></tr></thead><tbody>' +
                     rows + '</tbody></table></div><details><summary>Exact source spans</summary>' +
                     _spans(record['provenance']) + '</details></section>')
    return _page('Source fact claim check', '<h1>Source fact claim check</h1><p><strong>' +
                 escape(result['status']) + '</strong> · ' + escape(result['source_id']) + '</p><blockquote>' +
                 escape(result['claim']) + '</blockquote><p class="notice">Limited facet comparison; entailment is not established. '
                 'Every outcome requests review. No automatic approval or graph changes.</p><p><a href="comparison.json">Download comparison JSON</a></p>' +
                 '<details><summary>Claim parsing and limits</summary><pre>' + _json(result['parsed_claim']) + '</pre></details>' +
                 ''.join(cards) + ('<p>No complete source record was compared.</p>' if not cards else ''))


def _save(payload, output, kind, *, sources=(), origin=None):
    folder = new_output(output, *sources)
    write_json(folder / FILES[kind], payload)
    report = render_facts(payload) if kind == 'facts' else render_comparison(payload)
    (folder / 'report.html').write_text(report, encoding='utf-8')
    manifest = {'format': ARTIFACT, 'kind': kind, 'created_at': utcnow(), 'origin': origin,
                'files': {name: sha(folder / name) for name in (FILES[kind], 'report.html')},
                'graph_mutations': 0, 'model_requests': 0, 'auto_approval': False}
    manifest['artifact_sha256'] = digest(manifest)
    write_json(folder / 'source_fact_manifest.json', manifest)
    return manifest


def build_source_facts(literature, pmid, output):
    _, papers = load_literature(literature)
    if not isinstance(pmid, str) or pmid not in papers:
        raise ValueError('Choose a PMID in the verified literature collection.')
    dossier = compile_source(papers[pmid])
    validate_dossier(dossier)
    return _save(dossier, output, 'facts', sources=(literature,),
                 origin={'literature_manifest_sha256': sha(Path(literature) / 'manifest.json')})


def save_fact_check(facts, claim, output):
    if not isinstance(claim, str) or not claim.strip() or len(claim) > 4000:
        raise ValueError('Provide one claim of 1–4000 characters.')
    manifest, dossier = load_fact_artifact(facts)
    if manifest['kind'] != 'facts':
        raise ValueError('Choose a source-fact dossier, not a comparison.')
    result = compare_claim(claim, dossier)
    payload = {'format': CHECK, 'source_fact_artifact_sha256': manifest['artifact_sha256'],
               'source_fact_manifest': deepcopy(manifest),
               'dossier': deepcopy(dossier), 'comparison': result}
    return _save(payload, output, 'comparison', sources=(facts,),
                 origin={'source_fact_artifact_sha256': manifest['artifact_sha256']})


def _validate_manifest(manifest):
    if (set(manifest) != {'format', 'kind', 'created_at', 'origin', 'files', 'graph_mutations',
                         'model_requests', 'auto_approval', 'artifact_sha256'} or
            manifest.get('format') != ARTIFACT or manifest.get('kind') not in FILES or
            manifest.get('graph_mutations') != 0 or manifest.get('model_requests') != 0 or
            manifest.get('auto_approval') is not False or
            manifest.get('artifact_sha256') != digest({k: v for k, v in manifest.items() if k != 'artifact_sha256'})):
        raise ValueError('Source-fact artifact manifest failed integrity checks.')
    kind = manifest['kind']
    if set(manifest['files']) != {FILES[kind], 'report.html'}:
        raise ValueError('Source-fact artifact inventory changed.')
    return kind


def load_fact_artifact(path):
    """Verify bytes, source span/association replay, comparison replay and HTML replay."""
    folder = Path(path)
    if folder.is_symlink() or (folder / 'source_fact_manifest.json').is_symlink():
        raise ValueError('Source-fact artifact symlinks are not allowed.')
    manifest = json.loads((folder / 'source_fact_manifest.json').read_text())
    kind = _validate_manifest(manifest)
    for name, expected in manifest['files'].items():
        if (folder / name).is_symlink() or sha(folder / name) != expected:
            raise ValueError('Source-fact artifact bytes changed.')
    payload = json.loads((folder / FILES[kind]).read_text())
    if kind == 'facts':
        validate_dossier(payload)
        report = render_facts(payload)
    else:
        if (set(payload) != {'format', 'source_fact_artifact_sha256', 'source_fact_manifest', 'dossier', 'comparison'} or
                payload['format'] != CHECK or manifest['origin'] != {
                    'source_fact_artifact_sha256': payload['source_fact_artifact_sha256']}):
            raise ValueError('Source-fact comparison binding changed.')
        validate_dossier(payload['dossier'])
        parent = payload['source_fact_manifest']
        parent_kind = _validate_manifest(parent)
        # Check the embedded dossier against the original artifact's exact JSON
        # and report bytes, so an old parent fingerprint cannot name new facts.
        parent_json = json.dumps(payload['dossier'], indent=2, ensure_ascii=True, allow_nan=False) + '\n'
        if (parent_kind != 'facts' or parent['artifact_sha256'] != payload['source_fact_artifact_sha256'] or
                parent['files']['source_facts.json'] != hashlib.sha256(parent_json.encode()).hexdigest() or
                parent['files']['report.html'] != hashlib.sha256(render_facts(payload['dossier']).encode()).hexdigest()):
            raise ValueError('Embedded source-fact artifact binding changed.')
        if compare_claim(payload['comparison']['claim'], payload['dossier']) != payload['comparison']:
            raise ValueError('Source-fact comparison replay changed.')
        report = render_comparison(payload)
    if (folder / 'report.html').read_text() != report:
        raise ValueError('Source-fact report replay changed.')
    return manifest, payload
