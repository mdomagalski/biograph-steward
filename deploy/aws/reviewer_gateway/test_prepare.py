"""Meaningful preparation boundaries; live proxy acceptance is separate."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('reviewer_gateway_render', HERE / 'render.py')
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)

class PreparationTests(unittest.TestCase):
    def test_private_upstream_and_immutable_template_packet(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'candidate'
            receipt = render.render('10.20.30.40', out)
            config = (out / 'nginx.conf').read_text()
            self.assertIn('server 10.20.30.40:8766;', config)
            self.assertNotIn('__UPSTREAM', config)
            self.assertIn('proxy_set_header Authorization $http_authorization;', config)
            self.assertIn('proxy_set_header Cookie $http_cookie;', config)
            self.assertIn('proxy_set_header Origin $http_origin;', config)
            self.assertIn('proxy_set_header Host $http_host;', config)
            self.assertIn('proxy_buffering off;', config)
            self.assertIn('proxy_cache off;', config)
            self.assertIn('proxy_read_timeout 600s;', config)
            self.assertIn('"POST:/api/question" 1;', config)
            self.assertIn('"POST:/api/download-native-go-context" 1;', config)
            self.assertIn('"GET:/api/planner" 0;', config)
            self.assertNotIn('"POST:/api/review" 1;', config)
            self.assertNotIn('"POST:/api/plan" 1;', config)
            self.assertIn('default_type application/json;', config)
            self.assertIn('@sha256:', (out / 'Dockerfile').read_text())
            self.assertEqual(receipt['aws_calls'], 0)
            self.assertFalse(receipt['public_endpoint_ready'])
            task = json.loads((out / 'gateway.template.json').read_text())['Resources']['GatewayTask']['Properties']
            self.assertNotIn('TaskRoleArn', task)
            self.assertNotIn('Environment', task['ContainerDefinitions'][0])
            with self.assertRaises(ValueError):
                render.render('10.20.30.40', out)

    def test_rejects_untrusted_upstream_and_incomplete_or_mutable_deployment_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            for ip in ('127.0.0.1', '169.254.169.254', '8.8.8.8', '10.0.0.1;return 200;', '::1'):
                with self.subTest(ip=ip), self.assertRaises(ValueError):
                    render.render(ip, Path(folder) / 'invalid')
            with self.assertRaises(ValueError):
                render.render('10.0.0.1', Path(folder) / 'missing', gateway_image='latest')
            with self.assertRaises(ValueError):
                render.render('10.0.0.1', Path(folder) / 'mutable',
                    gateway_image='123456789012.dkr.ecr.us-east-2.amazonaws.com/gateway:latest',
                    vpc_id='vpc-12345678', subnet_a='subnet-12345678', subnet_b='subnet-87654321', app_security_group='sg-12345678')

if __name__ == '__main__':
    unittest.main()
