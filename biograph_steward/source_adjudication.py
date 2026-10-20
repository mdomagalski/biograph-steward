"""AI-authored, source-bound follow-up overlays; never overwrite verdicts or gold."""
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from .client import digest, utcnow, write_json
from .cohort_mapping import verify_mapping
from .crc_pilot import new_output, sha, verify_pilot_result
from .literature import load_literature, text


def paper_passages(paper, raw):
    """Resolve cached paragraphs plus figure captions; no figure-image interpretation."""
    root = ET.fromstring(raw)
    article = root if root.tag == 'article' else root.find('.//article')
    if article is None or article.findtext('front/article-meta/article-id[@pub-id-type="pmid"]') != paper['pmid']:
        raise ValueError('Adjudication paper identity differs.')
    passages = deepcopy(paper['abstract'] + paper['full_text'])
    for fig in article.findall('.//fig'):
        if fig.get('id') and fig.find('caption') is not None:
            passages.append({'locator': '/article//fig[@id="' + fig.get('id') + '"]/caption',
                             'section': 'Figure ' + fig.get('id') + ' caption', 'text': text(fig.find('caption'))})
    if len({p['locator'] for p in passages}) != len(passages):
        raise ValueError('Duplicate paper locator.')
    return passages


def validate_decision(decision, item, passages):
    expected = {'format', 'author_kind', 'method', 'item_id', 'record_sha256', 'pmid', 'decision', 'summary',
                'proposed_scoped_summary', 'findings', 'reviewed_source_locators', 'limitations'}
    if set(decision) != expected or decision['format'] != 'biograph-steward.ai-context-decision.v1' or decision['author_kind'] != 'ai_assistant':
        raise ValueError('Expected an explicitly AI-authored decision, not a scientific gold label.')
    if decision['item_id'] != item['item_id'] or decision['record_sha256'] != item['record_sha256'] or digest(item['source_record']) != item['record_sha256'] or decision['pmid'] != item['pmid']:
        raise ValueError('Decision does not bind the original source item.')
    if decision['decision'] not in {'scope_warning_core_preclinical_finding_supported', 'unresolved_context', 'context_mismatch'}:
        raise ValueError('Unsupported advisory decision.')
    for key in ['method', 'summary', 'proposed_scoped_summary']:
        if not isinstance(decision[key], str) or not 1 <= len(decision[key]) <= 6000:
            raise ValueError('Missing or over-budget decision text.')
    source = {p['locator']: p for p in passages}
    reviewed = decision['reviewed_source_locators']
    if not isinstance(reviewed, list) or not reviewed or len(set(reviewed)) != len(reviewed) or not set(reviewed) <= set(source):
        raise ValueError('Invalid reviewed source scope.')
    findings = decision['findings']
    if not isinstance(findings, list) or not findings or len(findings) > 20 or len({f['id'] for f in findings}) != len(findings):
        raise ValueError('Invalid finding inventory.')
    for finding in findings:
        if set(finding) != {'id', 'status', 'explanation', 'sources'} or finding['status'] not in {'supported_in_scope', 'scope_warning', 'not_established'} or not finding['explanation'] or not finding['sources']:
            raise ValueError('Invalid scoped finding.')
        for reference in finding['sources']:
            if set(reference) != {'locator', 'text_sha256'} or reference['locator'] not in reviewed or reference['text_sha256'] != digest(source[reference['locator']]['text']):
                raise ValueError('Finding source reference does not match cached paper text.')
    if not isinstance(decision['limitations'], list) or not decision['limitations'] or any(not isinstance(v, str) or not v for v in decision['limitations']):
        raise ValueError('Adjudication limitations must remain explicit.')
    return decision


def adjudicate_source(pilot, literature, decision_file, output, *, mapping=None):
    original = verify_pilot_result(pilot); manifest, papers = load_literature(literature)
    if original['literature_manifest_sha256'] != manifest['manifest_sha256']:
        raise ValueError('Adjudication literature differs from original pilot.')
    decision = json.loads(Path(decision_file).read_text())
    panel = json.loads((Path(pilot) / 'panel.json').read_text())
    matches = [row for row in panel if row['item_id'] == decision['item_id']]
    if len(matches) != 1:
        raise ValueError('Source item is not uniquely present in original panel.')
    item = matches[0]; paper = papers[item['pmid']]
    if paper['full_text_status'] != 'available' or not re.fullmatch(r'PMC[1-9][0-9]*', paper['pmcid'] or ''):
        raise ValueError('Adjudication requires the original cached full-text source.')
    raw_file = paper['pmcid'] + '.xml'
    if raw_file not in manifest['files']:
        raise ValueError('Paper XML is outside the frozen source inventory.')
    raw = (Path(literature) / raw_file).read_bytes(); passages = paper_passages(paper, raw)
    validate_decision(decision, item, passages)
    mapping_result = verify_mapping(mapping) if mapping else None
    if mapping_result and mapping_result['cptac_sidecar_sha256'] != original['cptac']['sidecar_sha256']:
        raise ValueError('Mapping does not use the original CPTAC sidecar.')
    out = new_output(output, pilot, literature, *([mapping] if mapping else []))
    assessments = [r for r in json.loads((Path(pilot) / 'assessments.json').read_text()) if r['item_id'] == item['item_id']]
    write_json(out / 'original_item.json', item); write_json(out / 'original_assessments.json', assessments)
    write_json(out / 'decision.json', decision); write_json(out / 'source_passages.json', passages)
    provenance = {k: deepcopy(paper.get(k)) for k in ['pmid', 'pmcid', 'doi', 'title', 'license', 'copyright', 'publication_types', 'correction_types']}
    provenance.update(source_url='https://pubmed.ncbi.nlm.nih.gov/' + item['pmid'] + '/',
                      source_xml_sha256=manifest['files'][raw_file], literature_manifest_sha256=manifest['manifest_sha256'],
                      rights_note='Original paper-specific terms apply; no new redistribution license is assigned.')
    write_json(out / 'source_provenance.json', provenance)
    # Preserve original verifier traces byte for byte; the assistant's overlay is a separate artifact.
    files = ['original_item.json', 'original_assessments.json', 'decision.json', 'source_passages.json', 'source_provenance.json']
    for row in assessments:
        if row['status'] != 'not_run':
            name = 'traces/' + row['task_id'] + '.json'; (out / 'traces').mkdir(exist_ok=True)
            (out / name).write_bytes((Path(pilot) / name).read_bytes()); files.append(name)
    result = {'format': 'biograph-steward.ai-source-adjudication.v1', 'created_at': utcnow(),
              'original_pilot_result_sha256': original['result_sha256'], 'literature_manifest_sha256': manifest['manifest_sha256'],
              'source_xml_sha256': manifest['files'][raw_file], 'decision_sha256': digest(decision),
              'item_id': item['item_id'], 'pmid': item['pmid'], 'decision': decision['decision'],
              'summary': decision['summary'], 'author_kind': 'ai_assistant', 'new_verifier_model_requests': 0,
              'original_verdicts': {r['view']: (r['assessment'] or {}).get('verdict') for r in assessments},
              'source_scope': {'cached_body_blocks': len(paper['full_text']), 'available_passages_including_abstract_and_captions': len(passages),
                               'reviewed_text_blocks': len(decision['reviewed_source_locators']), 'figure_images_reviewed': False,
                               'supplements_reviewed': False, 'independent_raw_data_reanalysis': False},
              'human_scientific_labels': 0, 'scientific_accuracy': None, 'scientific_improvement_established': False,
              'graph_assertions_changed': 0, 'source_records_changed': 0, 'original_verdicts_changed': 0,
              'mapping': {'result_sha256': mapping_result['result_sha256'], 'summary': mapping_result['summary']} if mapping_result else None,
              'files': {name: sha(out / name) for name in files}}
    result['result_sha256'] = digest(result); write_json(out / 'metrics.json', result)
    (out / 'report.html').write_text(render_adjudication(result, decision, item, assessments, passages, provenance), encoding='utf-8')
    return result


def verify_adjudication(path):
    path = Path(path); result = json.loads((path / 'metrics.json').read_text())
    if result['result_sha256'] != digest({k: v for k, v in result.items() if k != 'result_sha256'}):
        raise ValueError('Adjudication manifest changed.')
    required = {'original_item.json', 'original_assessments.json', 'decision.json', 'source_passages.json', 'source_provenance.json'}
    assessments = json.loads((path / 'original_assessments.json').read_text())
    traces = {'traces/' + r['task_id'] + '.json' for r in assessments if r['status'] != 'not_run'}
    if required | traces != set(result['files']):
        raise ValueError('Adjudication source inventory changed.')
    for name, value in result['files'].items():
        if not (name in required or re.fullmatch(r'traces/crc-[0-9]+-(abstract|augmented)\.json', name)) or (path / name).is_symlink() or sha(path / name) != value:
            raise ValueError('Adjudication artifact changed.')
    decision = json.loads((path / 'decision.json').read_text())
    validate_decision(decision, json.loads((path / 'original_item.json').read_text()), json.loads((path / 'source_passages.json').read_text()))
    if digest(decision) != result['decision_sha256'] or result['human_scientific_labels'] != 0 or result['scientific_accuracy'] is not None:
        raise ValueError('Adjudication provenance changed.')
    provenance = json.loads((path / 'source_provenance.json').read_text())
    if (provenance['source_xml_sha256'] != result['source_xml_sha256'] or provenance['literature_manifest_sha256'] != result['literature_manifest_sha256'] or
            provenance['pmid'] != result['pmid'] or result['original_verdicts'] != {r['view']: (r['assessment'] or {}).get('verdict') for r in assessments}):
        raise ValueError('Adjudication source or original verdict identity changed.')
    for row in assessments:
        if row['status'] != 'not_run' and sha(path / 'traces' / (row['task_id'] + '.json')) != row['trace_sha256']:
            raise ValueError('Original verifier trace changed.')
    return result


def render_adjudication(result, decision, item, assessments, passages, provenance):
    esc = lambda x: escape(str(x), quote=True)
    source = {p['locator']: p for p in passages}
    findings = []
    for finding in decision['findings']:
        references = ''.join('<details><summary>' + esc(ref['locator']) + '</summary><p>' + esc(source[ref['locator']]['text']) + '</p></details>' for ref in finding['sources'])
        findings.append('<section><h3>' + esc(finding['id']) + ' — ' + esc(finding['status']) + '</h3><p>' + esc(finding['explanation']) + '</p>' + references + '</section>')
    mapping = '<h2>Cohort mapping</h2><pre>' + esc(json.dumps(result['mapping'], indent=2)) + '</pre>' if result['mapping'] else ''
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>CRC context adjudication</title><style>body{max-width:1050px;margin:30px auto;padding:20px;font:16px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}section,details{border:1px solid #ccd;padding:12px;margin:12px 0}</style>'
            '<h1>CRC context adjudication</h1><p><strong>AI-assisted source inspection. Human scientific labels: zero. Original source records, verifier verdicts and graph states are unchanged.</strong></p>'
            '<h2>Decision</h2><p>' + esc(decision['summary']) + '</p><p><a href="https://pubmed.ncbi.nlm.nih.gov/' + esc(item['pmid']) + '/">Underlying primary study</a></p>'
            '<h2>Proposed scoped wording</h2><p>' + esc(decision['proposed_scoped_summary']) + '</p><p>This is a local proposal, not an edit to CIViC or a new accepted graph assertion.</p>'
            '<h2>Findings and source references</h2>' + ''.join(findings) + '<h2>Limits</h2><ul>' + ''.join('<li>' + esc(v) + '</li>' for v in decision['limitations']) + '</ul>'
            '<details><summary>Original source item and machine assessments</summary><pre>' + esc(json.dumps({'item': item, 'assessments': assessments}, indent=2)) + '</pre></details>'
            + mapping + '<details><summary>Paper provenance and original rights</summary><pre>' + esc(json.dumps(provenance, indent=2)) + '</pre></details>'
            '<details><summary>Provenance and unchanged controls</summary><pre>' + esc(json.dumps(result, indent=2)) + '</pre></details></html>')
