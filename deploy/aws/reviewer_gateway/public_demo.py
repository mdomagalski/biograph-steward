"""Prepare an exact public replay scope. This module never reads credentials."""
from __future__ import annotations

import json
from pathlib import Path
import re

IDENTIFIER = re.compile(r'[A-Za-z0-9_-]{1,80}')
FORMAT = 'biograph-steward.public-demo-scope.v1'
POST_PATHS = ('/api/explore', '/api/inspect-source', '/api/protein-context', '/api/native-go-context')
CATALOGUES = {'/', '/healthz', '/api/workspaces', '/api/scientific-assessments', '/api/assay-publications'}
HIDE_IDS = ('sourceAgentLive', 'controls', 'openProteinConstruction', 'constructionForm',
            'constructionAgentPanel', 'plannerPanel', 'customQuestionOptions', 'questionExplore',
            'nativeGoaPanel', 'civicRetrievePanel', 'civicForm', 'civicExplore', 'regulatoryForm',
            'assayAttachForm', 'assayQuestionControls', 'refreshPanel', 'submissionExport',
            'submissionCreateNote', 'neptunePanel')
LOGOUT_FORM = '<form method="post" action="/auth/logout"><button type="submit">Sign out</button></form>'
GO_DOWNLOAD_HOOK = 'function nativeGoDownloadPanel(result){'
RAW_SAFE = r'^(?![^?]*/\.{1,2}(?:/|\?|$))[^%?\\\s]*(?:\?[^\s]*)?$'


def load_scope(path):
    data = json.loads(Path(path).read_text())
    required = {'format', 'snapshot_id', 'snapshot_inventory_sha256', 'read_only_snapshot',
                'run_ids', 'workspace_ids', 'get_paths'}
    if not isinstance(data, dict) or set(data) != required or data.get('format') != FORMAT:
        raise ValueError('Use the exact public-demo scope fields and format.')
    if data['read_only_snapshot'] is not True:
        raise ValueError('Public mode requires a separate read-only data snapshot.')
    if not isinstance(data['snapshot_id'], str) or not IDENTIFIER.fullmatch(data['snapshot_id']):
        raise ValueError('Supply a bounded public snapshot identifier.')
    pin = data['snapshot_inventory_sha256']
    if not isinstance(pin, str) or not re.fullmatch(r'[a-f0-9]{64}', pin) or pin == '0' * 64:
        raise ValueError('Pin the reviewed snapshot inventory, not a placeholder.')
    for key in ('run_ids', 'workspace_ids'):
        values = data[key]
        if (not isinstance(values, list) or not 1 <= len(values) <= 40
                or any(not isinstance(v, str) or not IDENTIFIER.fullmatch(v) for v in values)
                or len(set(values)) != len(values)):
            raise ValueError('Use unique exact public run/workspace identifiers, at most 40.')
    if not set(data['workspace_ids']) <= set(data['run_ids']):
        raise ValueError('Public workspace IDs must belong to the approved snapshot.')
    paths = data['get_paths']
    if (not isinstance(paths, list) or not 1 <= len(paths) <= 400
            or any(not isinstance(p, str) or len(p) > 200 for p in paths) or len(set(paths)) != len(paths)):
        raise ValueError('Supply unique exact public GET paths, at most 400.')
    if not CATALOGUES <= set(paths):
        raise ValueError('Include the exact saved-demo bootstrap catalogue paths.')
    for path in paths:
        if path in CATALOGUES:
            continue
        match = re.fullmatch(r'/api/(run|question)/([A-Za-z0-9_-]{1,80})', path)
        if match and match[2] in data['run_ids']:
            if match[1] == 'run' and match[2] not in data['workspace_ids']:
                raise ValueError('Graph GET requires a public workspace ID.')
            continue
        match = re.fullmatch(r'/api/source-agent/job/(source_agent_[A-Za-z0-9_-]{1,67})(/download)?', path)
        if match and match[1] in data['run_ids']:
            continue
        match = re.fullmatch(r'/api/scientific-assessment/([A-Za-z0-9_-]{1,80})'
                            r'(?:/(?:report|files/(?:sources/[a-z_]+\.json|README\.txt)))?', path)
        if match and match[1] in data['run_ids']:
            continue
        match = re.fullmatch(r'/api/assay-source-reuse/([A-Za-z0-9_-]{1,80})(?:/report\.html)?', path)
        if match and match[1] in data['workspace_ids']:
            continue
        raise ValueError('Unapproved route, raw source or bulk download in public GET scope: ' + path)
    data['run_ids'] = sorted(data['run_ids'])
    data['workspace_ids'] = sorted(data['workspace_ids'])
    data['get_paths'] = sorted(paths)
    return data


def target_patterns(scope):
    """Patterns apply to normalized URI plus raw query, not untrusted headers."""
    exact = [p + '?' for p in scope['get_paths']]
    workspaces = '(?:' + '|'.join(re.escape(v) for v in scope['workspace_ids']) + ')'
    questions = [p.rsplit('/', 1)[1] for p in scope['get_paths'] if p.startswith('/api/question/')]
    jobs = [p.rsplit('/', 1)[1] for p in scope['get_paths']
            if re.fullmatch(r'/api/source-agent/job/source_agent_[A-Za-z0-9_-]{1,67}', p)]
    # Raw query grammar rejects encoded identifiers, unknown keys and duplicates.
    options = {'run': workspaces, 'view': '(?:data|ask|evidence|compare|export)'}
    for key, identifiers in (('question', questions), ('agent_job', jobs)):
        if identifiers:
            options[key] = '(?:' + '|'.join(re.escape(v) for v in identifiers) + ')'
    duplicates = ''.join(r'(?!(?:[^&]*&)*' + key + r'=[^&]*(?:&[^&]*)*&' + key + '=)'
                         for key in options)
    atom = '(?:' + '|'.join(key + '=' + value for key, value in options.items()) + ')'
    # At most four known options; each can appear at most once in any order.
    root = r'^/\?' + duplicates + atom + '(?:&' + atom + '){0,3}$'
    scoped = r'^/api/source-agent/(?:status|jobs)\?run_id=' + workspaces + '$'
    return exact, [root, scoped]


def allows(scope, method, target):
    """Exercise the generated NGINX grammar in preparation tests (no server)."""
    if not isinstance(target, str) or not re.fullmatch(RAW_SAFE, target):
        return False
    path, separator, query = target.partition('?')
    if method == 'POST':
        return path in POST_PATHS and not query
    if method not in ('GET', 'HEAD'):
        return False
    exact, patterns = target_patterns(scope)
    value = path + '?' + query
    return value in exact or any(re.fullmatch(p, value) for p in patterns)


def nginx_quote(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def maps(scope):
    exact, patterns = target_patterns(scope)
    lines = ['    map "$uri?$args" $public_get_target {', '        default 0;']
    # NGINX map string keys ignore case. Use anchored case-sensitive regexes
    # even for exact targets so recorded folder IDs retain their exact spelling.
    lines += ['        ' + nginx_quote('~^' + re.escape(p) + '$') + ' 1;' for p in exact]
    lines += ['        ' + nginx_quote('~' + p) + ' 1;' for p in patterns]
    lines += ['    }', '    map "$request_method:$uri:$args" $public_post_target {', '        default 0;']
    lines += ['        ' + nginx_quote('~^' + re.escape('POST:' + p + ':') + '$') + ' 1;' for p in POST_PATHS]
    lines += ['    }', '    map $request_uri $public_raw_path_safe {', '        default 0;',
              '        ' + nginx_quote('~' + RAW_SAFE) + ' 1;', '    }']
    # Only HTML is filtered. Preserve the application's existing compressed
    # JSON negotiation, including its quality-value checks and Vary response.
    html_paths = [p for p in scope['get_paths'] if p == '/' or p.endswith('/report') or p.endswith('/report.html')]
    lines += ['    map $uri $public_upstream_accept_encoding {', '        default $http_accept_encoding;']
    lines += ['        ' + nginx_quote('~^' + re.escape(p) + '$') + ' "";' for p in html_paths]
    lines += ['    }']
    return '\n'.join(lines)


def ui_subfilters():
    selectors = ','.join('#' + identifier for identifier in HIDE_IDS)
    selectors += ',a[href^="/api/download/"],a[href^="/api/extension-source/"],a[href^="/api/assay-source/"]'
    style = '<style id="publicDemoScope">' + selectors + '{display:none!important}</style>'
    banner = ('<div class="notice" role="note">Explore recorded agent investigations and inspect their '
              'cited evidence. Use the downloadable app to build new graphs.</div>')
    return '\n'.join([
        "            sub_filter_once off;",
        "            sub_filter '</head>' '" + style + "</head>';",
        "            sub_filter '<main>' '<main>" + banner + "';",
        "            sub_filter '" + LOGOUT_FORM + "' '';",
        "            sub_filter '" + GO_DOWNLOAD_HOOK + "' '" + GO_DOWNLOAD_HOOK + "return document.createDocumentFragment();';",
    ])


def validate_ui_contract(repo_root):
    """Fail preparation when the narrow public presentation hooks no longer fit."""
    ui = (repo_root / 'biograph_steward/ui.html').read_text()
    source = (repo_root / 'biograph_steward/webapp.py').read_text()
    navigation = (repo_root / 'biograph_steward/navigation.js').read_text()
    if source.count(LOGOUT_FORM) != 1 or navigation.count(GO_DOWNLOAD_HOOK) != 1:
        raise ValueError('Public presentation hook changed; review the current application before rendering.')
    for identifier in HIDE_IDS:
        if ui.count('id="' + identifier + '"') != 1:
            raise ValueError('Public hidden-control ID changed: ' + identifier)


def cloud_template(original):
    """Opt-in ECS secret delivery, never a task role or plaintext token parameter."""
    template = json.loads(original)
    template['Parameters'].update({
        'PublicDemoEnabled': {'Type': 'String', 'Default': 'false', 'AllowedValues': ['false', 'true']},
        'SSMParameterARN': {'Type': 'String', 'Default': '',
                            'AllowedPattern': r'|arn:aws:ssm:us-east-2:[0-9]{12}:parameter/[A-Za-z0-9_./-]+',
                            'Description': 'Existing SecureString holding only the separate public-backend token. No secret value.'},
    })
    enabled = {'Fn::Equals': [{'Ref': 'PublicDemoEnabled'}, 'true']}
    template['Conditions'] = {'PublicDemoEnabled': enabled}
    template['Rules']['PublicDemoSecretRequired'] = {'Assertions': [{
        'Assert': {'Fn::Or': [{'Fn::Not': [enabled]}, {'Fn::Not': [{'Fn::Equals': [{'Ref': 'SSMParameterARN'}, '']}]}]},
        'AssertDescription': 'Public mode requires the existing public-backend SSM SecureString ARN.'}]}
    properties = template['Resources']['ExecutionRole']['Properties']
    properties['Policies'] = {'Fn::If': ['PublicDemoEnabled', [{
        'PolicyName': 'ReadOnlyPublicBackendToken',
        'PolicyDocument': {'Version': '2012-10-17', 'Statement': [{
            'Effect': 'Allow', 'Action': 'ssm:GetParameters', 'Resource': {'Ref': 'SSMParameterARN'}}]}}],
        {'Ref': 'AWS::NoValue'}]}
    container = template['Resources']['GatewayTask']['Properties']['ContainerDefinitions'][0]
    container['Secrets'] = {'Fn::If': ['PublicDemoEnabled', [{
        'Name': 'BIOGRAPH_SERVER_TOKEN', 'ValueFrom': {'Ref': 'SSMParameterARN'}}], {'Ref': 'AWS::NoValue'}]}
    egress = template['Resources']['GatewayTaskIdentity']['Properties']['SecurityGroupEgress']
    egress.append({'Fn::If': ['PublicDemoEnabled', {'IpProtocol': 'tcp', 'FromPort': 8768, 'ToPort': 8768,
                   'DestinationSecurityGroupId': {'Ref': 'ExistingAppSecurityGroupId'}}, {'Ref': 'AWS::NoValue'}]})
    template['Resources']['PublicAppIngress'] = {'Type': 'AWS::EC2::SecurityGroupIngress',
        'Condition': 'PublicDemoEnabled', 'Properties': {'GroupId': {'Ref': 'ExistingAppSecurityGroupId'},
        'IpProtocol': 'tcp', 'FromPort': 8768, 'ToPort': 8768,
        'SourceSecurityGroupId': {'Ref': 'GatewayTaskIdentity'},
        'Description': 'Public saved-replay backend only. Separate token and read-only curated snapshot.'}}
    return template
