"""Preparation-only public scope/security checks. Actual NGINX replay is separate."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('gateway_public_test_render', HERE / 'render.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
public = renderer.public


def fixture_scope():
    return {'format': public.FORMAT, 'snapshot_id': 'public_demo_fixture',
        'snapshot_inventory_sha256': '1' * 64, 'read_only_snapshot': True,
        'run_ids': ['native_fixture', 'retained_fixture', 'question_fixture', 'source_agent_fixture', 'assessment_fixture'],
        'workspace_ids': ['native_fixture', 'retained_fixture'],
        'get_paths': sorted(public.CATALOGUES | {
            '/api/run/native_fixture', '/api/run/retained_fixture', '/api/question/question_fixture',
            '/api/source-agent/job/source_agent_fixture', '/api/source-agent/job/source_agent_fixture/download',
            '/api/scientific-assessment/assessment_fixture', '/api/scientific-assessment/assessment_fixture/report',
            '/api/scientific-assessment/assessment_fixture/files/sources/public_reference.json',
            '/api/assay-source-reuse/retained_fixture'})}


class PublicPreparationTests(unittest.TestCase):
    def write_scope(self, folder, data=None):
        path = Path(folder) / 'scope.json'
        path.write_text(json.dumps(fixture_scope() if data is None else data))
        return path

    def test_exact_get_and_query_scope_rejects_private_ids_duplicates_and_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            scope = public.load_scope(self.write_scope(folder))
            good = ['/', '/?run=native_fixture&question=question_fixture&agent_job=source_agent_fixture&view=data',
                    '/?agent_job=source_agent_fixture&view=ask&run=native_fixture&question=question_fixture',
                    '/api/source-agent/jobs?run_id=native_fixture', '/api/source-agent/status?run_id=retained_fixture',
                    '/api/source-agent/job/source_agent_fixture', '/api/run/native_fixture']
            bad = ['/?run=private_fixture', '/?run=native_fixture&run=native_fixture',
                   '/?view=data&run=native_fixture&view=ask',
                   '/?question=question_fixture&view=data&question=question_fixture',
                   '/?agent_job=source_agent_fixture&agent_job=source_agent_fixture',
                   '/?run=%6eative_fixture', '/?run=native_fixture&unknown=1',
                   '/api/source-agent/jobs', '/api/source-agent/jobs?run_id=private_fixture',
                   '/api/source-agent/jobs?run_id=native_fixture&run_id=native_fixture',
                   '/api/source-agent/jobs?run_id=native_fixture&extra=1',
                   '/api/source-agent/job/source_agent_private', '/api/source-agent/job/source_agent_fixture?extra=1',
                   '/api/run/NATIVE_fixture',
                   '/api/run/private_fixture', '/api/run/native_fixture?arbitrary=1',
                   '/api/download/native_fixture', '/api/planner', '/api/support-comparator/private/cases.json',
                   '/api/extension-source/native_fixture/extension_sources/string_physical/source/raw.gz',
                   '/%61pi/run/native_fixture', '/api/run/../run/native_fixture',
                   '/api/run/%2e%2e/run/native_fixture', '/api/run/native_fixture\n']
            for target in good:
                with self.subTest(target=target):
                    self.assertTrue(public.allows(scope, 'GET', target))
                    self.assertTrue(public.allows(scope, 'HEAD', target))
            for target in bad:
                with self.subTest(target=target):
                    self.assertFalse(public.allows(scope, 'GET', target))

    def test_only_four_readonly_post_paths_have_public_access(self):
        scope = fixture_scope()
        for path in public.POST_PATHS:
            self.assertTrue(public.allows(scope, 'POST', path))
            self.assertTrue(public.allows(scope, 'POST', path + '?'))
            self.assertFalse(public.allows(scope, 'POST', path + '?run_id=private_fixture'))
        for path in ['/api/question', '/api/native-go-question', '/api/plan', '/api/source-agent/run',
                     '/api/review', '/api/construct', '/api/civic', '/api/refresh-compare',
                     '/api/download-native-go-context', '/api/submission-export', '/api/neptune-inspect']:
            with self.subTest(path=path):
                self.assertFalse(public.allows(scope, 'POST', path))
        for method in ('PUT', 'DELETE', 'PATCH', 'OPTIONS'):
            self.assertFalse(public.allows(scope, method, '/'))

    def test_scope_requires_separate_pinned_snapshot_and_cannot_grant_raw_downloads(self):
        with tempfile.TemporaryDirectory() as folder:
            changes = [{'read_only_snapshot': False}, {'snapshot_inventory_sha256': '0' * 64},
                       {'workspace_ids': ['private_fixture']}, {'run_ids': ['native_fixture', 'native_fixture']},
                       {'get_paths': fixture_scope()['get_paths'] + ['/api/download/native_fixture']},
                       {'get_paths': fixture_scope()['get_paths'] + ['/api/run/private_fixture']},
                       {'get_paths': fixture_scope()['get_paths'] + ['/api/support-comparator/assessment_fixture/cases.json']}]
            for change in changes:
                with self.subTest(change=change), self.assertRaises(ValueError):
                    public.load_scope(self.write_scope(folder, {**fixture_scope(), **change}))

    def test_default_private_packet_is_unchanged_and_public_packet_never_contains_secret(self):
        with tempfile.TemporaryDirectory() as folder:
            private = Path(folder) / 'private'
            renderer.render('10.20.30.40', private)
            self.assertEqual((private / 'nginx.conf').read_text(), (HERE / 'nginx.conf.in').read_text().replace('__UPSTREAM_IPV4__', '10.20.30.40'))
            self.assertEqual((private / 'gateway.template.json').read_bytes(), (HERE / 'gateway.template.json').read_bytes())
            self.assertEqual((private / 'Dockerfile').read_text(), (HERE / 'Dockerfile.in').read_text().replace('__NGINX_IMAGE__', json.loads((HERE / 'image.lock.json').read_text())['image']))
            out = Path(folder) / 'public'
            receipt = renderer.render('10.20.30.40', out, public_demo=True, public_scope=self.write_scope(folder))
            text = (out / 'nginx.conf').read_text()
            self.assertIn('server 10.20.30.40:8768;', text)
            self.assertNotIn('~^(GET|HEAD):/ 1;', text)
            self.assertIn('~^/api/run/native_fixture\\\\?$', text)
            self.assertIn('proxy_set_header Authorization "Bearer ${BIOGRAPH_SERVER_TOKEN}";', text)
            self.assertNotIn('proxy_set_header Authorization $http_authorization;', text)
            self.assertIn('proxy_set_header Cookie "";', text)
            self.assertIn('proxy_hide_header Set-Cookie;', text)
            self.assertIn('proxy_set_header Accept-Encoding $public_upstream_accept_encoding;', text)
            self.assertIn('default $http_accept_encoding;', text)
            self.assertNotIn('proxy_set_header Accept-Encoding "";', text)
            self.assertIn('assessment_fixture/report$" "";', text)
            self.assertIn('location = /auth/login { return 303 /; }', text)
            self.assertIn('location = /auth/logout { return 303 /; }', text)
            self.assertIn('sub_filter \'' + public.LOGOUT_FORM + '\' \'\';', text)
            self.assertIn('return document.createDocumentFragment();', text)
            self.assertIn('#sourceAgentLive', text)
            self.assertNotIn('#sourceAgentOutput{', text)
            self.assertFalse(receipt['token_value_read_or_written'])
            self.assertFalse(receipt['public_snapshot_verified_by_renderer'])
            self.assertEqual(receipt['aws_calls'], 0)
            self.assertEqual((out / 'public-entrypoint.sh').stat().st_mode & 0o777, 0o600)

    def test_ssm_role_is_optional_exact_scoped_no_task_role_and_separate_backend_port(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'public'
            renderer.render('10.20.30.40', out, public_demo=True, public_scope=self.write_scope(folder),
                ssm_parameter_arn='arn:aws:ssm:us-east-2:123456789012:parameter/biograph/public-token',
                gateway_image='123456789012.dkr.ecr.us-east-2.amazonaws.com/gateway@sha256:' + 'a' * 64,
                vpc_id='vpc-12345678', subnet_a='subnet-12345678', subnet_b='subnet-87654321',
                app_security_group='sg-12345678')
            template = json.loads((out / 'gateway.template.json').read_text())
            task = template['Resources']['GatewayTask']['Properties']
            self.assertNotIn('TaskRoleArn', task)
            self.assertEqual(task['ContainerDefinitions'][0]['Secrets']['Fn::If'][1][0],
                {'Name': 'BIOGRAPH_SERVER_TOKEN', 'ValueFrom': {'Ref': 'SSMParameterARN'}})
            policy = template['Resources']['ExecutionRole']['Properties']['Policies']['Fn::If'][1][0]['PolicyDocument']['Statement']
            self.assertEqual(policy, [{'Effect': 'Allow', 'Action': 'ssm:GetParameters', 'Resource': {'Ref': 'SSMParameterARN'}}])
            self.assertEqual(template['Resources']['PublicAppIngress']['Condition'], 'PublicDemoEnabled')
            self.assertEqual(template['Resources']['PublicAppIngress']['Properties']['FromPort'], 8768)
            self.assertEqual(template['Resources']['PrivateAppIngress']['Properties']['FromPort'], 8766)
            parameters = {x['ParameterKey']: x['ParameterValue'] for x in json.loads((out / 'gateway.parameters.json').read_text())}
            self.assertEqual(parameters['PublicDemoEnabled'], 'true')
            self.assertEqual(parameters['SSMParameterARN'], 'arn:aws:ssm:us-east-2:123456789012:parameter/biograph/public-token')

    def test_invalid_secret_and_config_dump_fail_before_render_without_secret_output(self):
        script = HERE / 'public-entrypoint.sh'
        invalid = ['', 'short', 'x' * 257, 'A' * 24 + '\n', 'A' * 24 + '"', 'A' * 24 + '$variable']
        for token in invalid:
            with self.subTest(length=len(token)):
                result = subprocess.run(['sh', str(script), '-t'], env={'PATH': os.defpath, 'BIOGRAPH_SERVER_TOKEN': token}, text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertEqual(result.stderr.strip(), 'Public gateway token is missing or invalid.')
        canary = 'CANARY_NOT_A_REAL_TOKEN_123456789'
        for command in [['-T'], ['-c', '/tmp/other'], ['-g', 'error_log /dev/stdout debug;']]:
            result = subprocess.run(['sh', str(script), *command], env={'PATH': os.defpath, 'BIOGRAPH_SERVER_TOKEN': canary}, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(canary, result.stdout + result.stderr)
        source = script.read_text()
        self.assertIn("envsubst '${BIOGRAPH_SERVER_TOKEN}'", source)
        self.assertIn('unset BIOGRAPH_SERVER_TOKEN', source)
        self.assertIn('chmod 600 "$config"', source)
        self.assertNotIn('set -x', source)

    def test_missing_public_config_or_unbound_secret_account_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            scope = self.write_scope(folder)
            for kwargs in [{'public_demo': True}, {'public_scope': scope},
                           {'ssm_parameter_arn': 'arn:aws:ssm:us-east-2:123456789012:parameter/public'},
                           {'public_demo': True, 'public_scope': scope, 'ssm_parameter_arn': 'arn:aws:ssm:us-west-2:123456789012:parameter/public'}]:
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    renderer.render('10.20.30.40', Path(folder) / 'unused', **kwargs)
            original = (HERE.parents[2] / 'biograph_steward/navigation.js').read_text()
            self.assertEqual(original.count(public.GO_DOWNLOAD_HOOK), 1)


if __name__ == '__main__':
    unittest.main()
