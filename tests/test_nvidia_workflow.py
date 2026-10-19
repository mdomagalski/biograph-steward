"""Optional real Toolkit discovery and end-to-end execution using a local mock."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from biograph_steward.graph import save_run
from test_civic import fixture
from test_planning import civic_plan
from test_portability import chat, mock_model


@unittest.skipUnless(importlib.util.find_spec('nat'), 'Optional NeMo Agent Toolkit is not installed.')
class NvidiaWorkflowTests(unittest.TestCase):
    def test_installed_entry_point_is_discovered_and_cli_executes_one_bounded_query(self):
        from importlib.metadata import entry_points
        entries = [e for e in entry_points(group='nat.plugins') if e.name == 'nat_biograph']
        self.assertEqual(len(entries), 1); entries[0].load()
        cli = Path(sys.executable).with_name('nat')
        self.assertTrue(cli.is_file())
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(('BIOGRAPH_', 'OPENAI_', 'NVIDIA_'))}
        env.update(NO_PROXY='127.0.0.1,localhost,::1', no_proxy='127.0.0.1,localhost,::1')
        listed = subprocess.run([str(cli), 'info', 'components', '--query', 'biograph', '--types', 'function'],
                                capture_output=True, text=True, timeout=45, env=env)
        self.assertEqual(listed.returncode, 0, listed.stderr[-2500:])
        self.assertTrue('biograph' in listed.stdout.lower(), listed.stderr[-1500:])
        with tempfile.TemporaryDirectory() as root:
            source = Path(root)/'source'; p, c = fixture(); save_run(p, source, civic_snapshot=c)
            original = (source/'snapshot.json').read_bytes()
            # Exercise the actual committed YAML, including its environment expansion.
            config = Path(__file__).parents[1]/'deploy'/'nvidia'/'question.yml'
            with mock_model(lambda _: (200, {}, json.dumps(chat(civic_plan())).encode())) as (endpoint, calls):
                env.update(BIOGRAPH_NAT_SOURCE_RUN=str(source), BIOGRAPH_MODEL_PROVIDER='nim',
                           BIOGRAPH_MODEL_ID='invented-model', BIOGRAPH_MODEL_ENDPOINT=endpoint,
                           BIOGRAPH_MODEL_API_KEY='invented-test-key')
                result = subprocess.run([str(cli), 'run', '--config_file', str(config), '--input', 'Inspect candidate evidence.'],
                                        capture_output=True, text=True, timeout=60, env=env)
            self.assertEqual(result.returncode, 0, result.stderr[-3500:])
            self.assertEqual(len(calls), 1)
            output = result.stdout + result.stderr
            self.assertTrue('"tool_calls": 1' in output, output[-2000:])
            self.assertTrue('"status": "answered"' in output, output[-2000:])
            self.assertTrue('"trace":' in output, output[-2000:])
            self.assertEqual((source/'snapshot.json').read_bytes(), original)


if __name__ == '__main__': unittest.main()
