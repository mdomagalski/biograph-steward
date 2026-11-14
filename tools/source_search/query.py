"""Inspect source papers for one supplied question, without an evaluation corpus.

This operator utility reuses the qualified PubMed tools and bounded Nano runner.
It produces a saved handoff report, not a biological answer or graph decision.
"""
import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.model_transport import JSONModelClient
from . import agent
from . import policy
from .policy import MODEL, MAX_CALLS, MAX_OUTPUT_TOKENS
from .prepare import need, read_sealed, seal
from .tools import SourceTools, PMID

FORMAT = 'biograph-steward.supplied-question-source-inspection.v1'
BOUNDARY = ('Pharos/evidence reuse unassessed; candidate source context, '
            'not independent new graph evidence.')
OWN_SEARCH_REASONS = {
    'Source search: unsupported empty/NUL/over2000character query.',
    'native non-JSON/timeout/process failure',
    'native JSON shape/provider plan not qualified',
}


def _ids(values):
    return (isinstance(values, list)
            and all(isinstance(value, str) and PMID.fullmatch(value) for value in values)
            and len(values) == len(set(values)))


def presentation(result, captures, mode):
    """Keep final model choices distinct from papers captured before it stopped."""
    papers = {}; searches = []; opened = []
    for capture, record_link in captures:
        if not isinstance(capture, dict):
            continue
        if capture.get('tool') == 'search_pubmed':
            reason = capture.get('reason')
            reason = (reason[:240] if isinstance(reason, str) and reason in OWN_SEARCH_REASONS
                      and capture.get('status') in {'unsupported_query', 'unavailable'} else None)
            searches.append({'query': capture.get('query', ''), 'status': capture.get('status', 'unavailable'),
                             'reason': reason, 'record_link': record_link})
            for row in capture.get('candidates', []):
                pmid = row.get('pmid')
                need(isinstance(pmid, str) and PMID.fullmatch(pmid), 'captured source has an invalid PMID.')
                if pmid not in papers:
                    papers[pmid] = {'pmid': pmid, 'title': row.get('title') if isinstance(row.get('title'), str) else '',
                                    'record_link': record_link, 'native_qualification_observations': []}
                if 'is_retracted' in row:
                    observation = {'is_retracted': row['is_retracted']}
                    if observation not in papers[pmid]['native_qualification_observations']:
                        papers[pmid]['native_qualification_observations'].append(observation)
        elif capture.get('tool') == 'get_abstract':
            pmid = capture.get('pmid')
            need(isinstance(pmid, str) and PMID.fullmatch(pmid), 'opened source has an invalid PMID.')
            record = capture.get('record')
            need(capture.get('identity_resolved') is not True
                 or isinstance(record, dict) and record.get('pmid') == pmid,
                 'opened article identity does not match the requested PMID.')
            opened.append({'pmid': pmid, 'status': capture.get('status', 'unavailable'),
                           'identity_resolved': capture.get('identity_resolved') is True,
                           'abstract_available': bool(isinstance(record, dict) and record.get('abstract')),
                           'publication_types': record.get('publication_types') if isinstance(record, dict) else None,
                           'correction_types': record.get('correction_types') if isinstance(record, dict) else None,
                           'record_link': record_link})
            if pmid in papers and isinstance(record, dict):
                observation = {key: record[key] for key in ('publication_types', 'correction_types') if key in record}
                if observation:
                    papers[pmid]['native_qualification_observations'].append(observation)
    final = result.get('ranked_pmids')
    # A corrupt/incompatible result is never converted to an agent success.
    valid = (mode == 'agent' and result.get('status') == 'completed'
             and _ids(final) and len(final) <= 10 and set(final) <= set(papers))
    state = ('valid_final_model_selection' if valid else 'no_valid_final_model_selection') if mode == 'agent' else 'native_search_results'
    return {'selection_state': state, 'final_model_pmids': list(final) if valid else [],
            'native_candidate_pmids': list(papers), 'papers': list(papers.values()),
            'searches': searches, 'abstract_inspections': opened,
            'operator_mode': mode, 'workflow_status': result.get('status', 'unavailable')}


def _captures(folder):
    rows = []
    for path in sorted(Path(folder).glob('tool_result*.json')):
        need(path.is_file() and not path.is_symlink() and re.fullmatch(r'tool_result(?:_[1-9][0-9]*)?\.json', path.name),
             'source capture must be an ordinary immediate file.')
        rows.append((json.loads(path.read_text()), 'workflow/' + path.name))
    return rows


def _costs(result):
    events = result.get('tool_events', []); tokens = Counter()
    for usage in result.get('model_usage', []):
        if isinstance(usage, dict):
            for key, value in usage.items():
                if key in {'prompt_tokens', 'completion_tokens', 'total_tokens', 'input_tokens',
                           'output_tokens', 'cached_tokens', 'reasoning_tokens'} and type(value) is int:
                    tokens[key] += value
    return {'model_generation_calls': result.get('model_calls', 0),
            'model_tokenizer_requests': result.get('tokenizer_model_service_requests', 0),
            'observed_model_token_counts': dict(tokens),
            'controller_rejected_action_attempts': len(result.get('controller_rejections', [])),
            'source_tool_invocations': len(events),
            'native_search_process_executions': sum(event.get('native_process_executions', 0) for event in events),
            'direct_exact_PubMed_fetch_invocations': sum(event.get('direct_fetch_invocations', 0) for event in events),
            'source_cache_hits': sum(bool(event.get('cache_hit')) for event in events),
            'exact_upstream_HTTP_request_count': None, 'dollar_cost': None}


def _paper_list(rows):
    if not rows:
        return '<p>No papers in this list.</p>'
    def qualifications(row):
        values = row.get('native_qualification_observations') or []
        if not values:
            return '<br><small>Publication/retraction metadata not recorded or not checked in these captures.</small>'
        flags = []; publication_types = []; correction_types = []
        for observation in values:
            if type(observation.get('is_retracted')) is bool:
                flag = 'true' if observation['is_retracted'] else 'false'
                if flag not in flags:
                    flags.append(flag)
            for key, captured in (('publication_types', publication_types), ('correction_types', correction_types)):
                if key not in observation:
                    continue
                types = observation[key]
                text = (', '.join(types) if types else 'no values returned') if isinstance(types, list) and all(isinstance(item, str) for item in types) else 'not recorded'
                if text not in captured:
                    captured.append(text)
        return ('<br><small>Retraction source flag: ' + escape(', '.join(flags) or 'not recorded')
                + '; Publication types: ' + escape('; '.join(publication_types) or 'not recorded')
                + '; Correction types: ' + escape('; '.join(correction_types) or 'not recorded')
                + '. Source observations only, not independent clearance; missing or empty metadata does not establish a clean status.</small>')
    return '<ol>' + ''.join(
        '<li><a href="https://pubmed.ncbi.nlm.nih.gov/' + row['pmid'] + '/">PMID ' + row['pmid'] + '</a>'
        + (' — ' + escape(row['title']) if row['title'] else '')
        + ' · <a href="' + escape(row['record_link'], quote=True) + '">Saved source record</a>'
        + qualifications(row) + '</li>' for row in rows) + '</ol>'


def render_html(question, view, costs, procedure):
    """Only allowlisted human fields are rendered, never traces or local pins."""
    by_id = {row['pmid']: row for row in view['papers']}
    if view['operator_mode'] == 'native':
        primary = '<h2>Native PubMed search results</h2><p>No language model was called. Search status is shown below.</p>'
    elif view['selection_state'] == 'valid_final_model_selection':
        if view['final_model_pmids']:
            primary = '<h2>Final model selection</h2><p>The bounded agent completed a source-paper handoff. This is not a biological conclusion.</p>'
            primary += _paper_list([by_id[pmid] for pmid in view['final_model_pmids']])
        else:
            primary = ('<h2>Agent finished without selecting papers</h2><p>It returned a valid empty selection. '
                       'Any captured search candidates remain below. This does not establish that relevant papers '
                       'or biological evidence are absent.</p>')
    else:
        primary = '<h2>No valid final model selection</h2><p>The agent stopped before a valid final handoff. Papers captured by its searches remain available below; they are not a completed agent answer.</p>'
    searches = ''.join('<tr><td>' + escape(str(row['query'])) + '</td><td>' + escape(str(row['status']))
                       + ('<br><small>' + escape(row['reason'][:240]) + '</small>' if row.get('reason') else '')
                       + '</td><td><a href="' + escape(row['record_link'], quote=True) + '">Saved record</a></td></tr>' for row in view['searches'])
    opened = ''.join('<li><a href="https://pubmed.ncbi.nlm.nih.gov/' + row['pmid'] + '/">PMID ' + row['pmid'] + '</a>: '
                     + escape(row['status']) + '; source identity ' + ('verified' if row['identity_resolved'] else 'not verified')
                     + '; abstract ' + ('available' if row['abstract_available'] else 'not available')
                     + ' · <a href="' + escape(row['record_link'], quote=True) + '">Saved inspection record</a></li>' for row in view['abstract_inspections'])
    model_rows = [('Generation calls', costs['model_generation_calls']), ('Tokenizer requests', costs['model_tokenizer_requests']),
                  ('Rejected action attempts (no source execution)', costs['controller_rejected_action_attempts']),
                  ('Observed token usage', json.dumps(costs['observed_model_token_counts'], sort_keys=True))]
    source_rows = [('Tool invocations', costs['source_tool_invocations']), ('Native search processes', costs['native_search_process_executions']),
                   ('Exact-PMID fetch invocations', costs['direct_exact_PubMed_fetch_invocations']), ('Cache hits', costs['source_cache_hits'])]
    def table(rows):
        return '<table>' + ''.join('<tr><th>' + escape(str(k)) + '</th><td>' + escape(str(v)) + '</td></tr>' for k, v in rows) + '</table>'
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>Supplied-question source inspection</title><style>body{font:16px system-ui;max-width:960px;margin:32px auto;padding:0 20px;line-height:1.5}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd7dd;padding:8px;text-align:left;overflow-wrap:anywhere}.notice{padding:14px;background:#fff4d7}a{color:#075c83}</style>'
            '<h1>Source papers for a supplied question</h1><p>' + escape(question) + '</p><p>Mode: ' + escape(view['operator_mode'])
            + ' · Procedure: ' + escape(procedure if view['operator_mode'] == 'agent' else 'not applied (native search)')
            + ' · Workflow status: ' + escape(str(view['workflow_status'])) + '</p><p class="notice">' + escape(BOUNDARY) + '</p>'
            + primary + '<h2>Search candidates already captured</h2><p>These are native search candidates. Membership, ranking and a valid PMID do not establish relevance, source entailment or scientific accuracy.</p>'
            + _paper_list(view['papers']) + '<h2>Source queries and statuses</h2><table><tr><th>Query</th><th>Status</th><th>Capture</th></tr>'
            + searches + '</table><h2>Exact article inspections</h2><ul>' + (opened or '<li>No exact abstract inspection was performed.</li>')
            + '</ul><p>Article identity and abstract availability are separate checks. Abstract bodies are not reproduced here. Captured publication/correction/retraction fields are source observations; missing or empty metadata is not a clean bill of health.</p>'
            + '<h2>Model cost observations</h2>' + table(model_rows) + '<h2>Source-tool cost observations</h2>' + table(source_rows)
            + '<p>Source processes and fetch invocations are not exact HTTP request counts. Token usage may be missing on failed calls; no price or dollar cost is assumed.</p>'
            + '<p>No graph was changed or annotation accepted. <a href="operator_receipt.json">Sealed operator receipt</a> · <a href="workflow/result.json">Saved workflow JSON</a></p></html>')


def _client(endpoint):
    parsed = urlsplit(endpoint)
    need(parsed.scheme in {'http', 'https'} and parsed.hostname in {'localhost', '127.0.0.1', '::1'}
         and parsed.username is None and parsed.password is None and not parsed.query and not parsed.fragment,
         'use the existing credential-free loopback Nano endpoint.')
    client = JSONModelClient(role='verifier', provider='api', model=MODEL, endpoint=endpoint, api='nim_chat')
    client.prompt_profile = 'nemotron_nano_v1'; client.max_output_tokens = MAX_OUTPUT_TOKENS; client.timeout = 120
    return client


def run(question, qualification, qualification_sha256, mode, procedure, cache, output,
        *, endpoint='http://127.0.0.1:8011/v1/chat/completions', source_tools=None, client=None, token_counter=None):
    need(isinstance(question, str) and question.strip() and len(question) <= 5000 and '\x00' not in question,
         'supply one nonblank question of at most5000characters without NUL.')
    need(mode in {'native', 'agent'} and procedure in {'base', 'reviewed'}, 'unsupported operator mode/procedure.')
    injected_client = client is not None
    q = read_sealed(qualification, qualification_sha256)
    need(q['format'] == 'biograph-steward.biomcp-binary-qualification.v1', 'use an explicit pinned native binary qualification.')
    folder = new_output(output, qualification, cache)
    case = {'id': 'operator_' + digest(question)[:20], 'body': question, 'type': 'supplied_question'}
    write_json(folder / 'question.json', case)
    tools = source_tools or SourceTools(qualification, qualification_sha256, cache)
    work = folder / 'workflow'
    if mode == 'native':
        result = agent.direct_case(case, tools, work)
    else:
        client = client or _client(endpoint)
        result = agent.run_case(case, client, tools, work, skill=procedure == 'reviewed',
                                token_counter=token_counter, duplicate_feedback=True)
    view = presentation(result, _captures(work), mode); costs = _costs(result)
    need(type(costs['model_generation_calls']) is int and 0 <= costs['model_generation_calls'] <= (MAX_CALLS if mode == 'agent' else 0)
         and len(view['searches']) <= (2 if mode == 'agent' else 1)
         and len(view['abstract_inspections']) <= (1 if mode == 'agent' else 0), 'workflow exceeded its operator budget.')
    report = folder / 'report.html'; report.write_text(render_html(question, view, costs, procedure))
    source_pins = dict(tools.pins)
    receipt = seal({'format': FORMAT, 'created_at': utcnow(), 'mode': mode,
        'procedure_requested': procedure, 'procedure_applied': procedure if mode == 'agent' else None,
        'question_sha256': digest(question), 'question_characters': len(question),
        'selection_state': view['selection_state'], 'workflow_status': view['workflow_status'],
        'final_model_pmids': view['final_model_pmids'], 'native_candidate_pmids': view['native_candidate_pmids'],
        'abstract_inspections': view['abstract_inspections'], 'cost_observations': costs,
        'budgets': {'model_generation_calls': MAX_CALLS if mode == 'agent' else 0,
                    'output_tokens_per_call': MAX_OUTPUT_TOKENS if mode == 'agent' else 0,
                    'search_calls': 2 if mode == 'agent' else 1, 'exact_abstract_gets': 1 if mode == 'agent' else 0,
                    'context_cap': agent.CONTEXT_CAP if mode == 'agent' else None},
        'duplicate_search_feedback': mode == 'agent',
        'model_requested': MODEL if mode == 'agent' else None, 'model_revision_observed_by_this_utility': None,
        'model_revision_note': 'Existing service qualification is separate; no runtime/model revision is inferred from a model name.',
        'binary_qualification_sha256': qualification_sha256, 'binary_qualification_content_sha256': q['content_sha256'],
        'source_pins': source_pins, 'operator_source_sha256': sha(__file__),
        'agent_source_sha256': sha(agent.__file__),
        'policy_source_sha256': sha(policy.__file__), 'base_policy_sha256': digest(policy.BASE_POLICY),
        'reviewed_procedure_sha256': digest(policy.SKILL) if mode == 'agent' and procedure == 'reviewed' else None,
        'procedure_sources': policy.SKILL_SOURCES if mode == 'agent' and procedure == 'reviewed' else [],
        'workflow_result_content_sha256': result['content_sha256'],
        'injected_test_tools': source_tools is not None, 'injected_test_client': mode == 'agent' and injected_client,
        'uses_reference_corpus': False, 'biological_truth_or_entailment_measured': False,
        'Pharos_evidence_reuse_assessed': False, 'boundary': BOUNDARY, 'graph_changes': 0,
        'files': {str(p.relative_to(folder)): {'sha256': sha(p), 'bytes': p.stat().st_size}
                  for p in sorted(folder.rglob('*')) if p.is_file()}})
    write_json(folder / 'operator_receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('question', 'qualification', 'qualification-sha256', 'cache', 'output'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--mode', choices=('native', 'agent'), default='native')
    parser.add_argument('--procedure', choices=('base', 'reviewed'), default='base', help='Explicit agent instructions; native search uses no procedure.')
    parser.add_argument('--endpoint', default='http://127.0.0.1:8011/v1/chat/completions')
    receipt = run(**vars(parser.parse_args()))
    print(json.dumps({'format': receipt['format'], 'workflow_status': receipt['workflow_status'],
                      'selection_state': receipt['selection_state'], 'content_sha256': receipt['content_sha256']}))
