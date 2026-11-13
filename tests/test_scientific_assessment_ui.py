"""Run the actual DOM renderer with the existing lightweight VM-test pattern."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from biograph_steward import scientific_assessment as module
from test_scientific_assessment import fixtures

NODE = shutil.which('node') or str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
JS = Path(__file__).resolve().parents[1] / 'biograph_steward/scientific_assessment.js'
HARNESS = r'''
const fs=require('node:fs'),vm=require('node:vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.textContent='';}
 append(...children){this.children.push(...children);}
 replaceChildren(...children){this.children=children;}
}
const container=new Element('section'),context=vm.createContext({window:{},URL,
 document:{createElement:tag=>new Element(tag),querySelector:()=>container}});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
let error=null;
try{context.window.ScientificAssessment.render(container,input.summary,input.options||{});}
catch(e){error=e.message;}
const nodes=[];function walk(n){nodes.push(n);for(const c of n.children)walk(c);}walk(container);
process.stdout.write(JSON.stringify({error,text:nodes.map(n=>n.textContent),tags:nodes.map(n=>n.tag),
 links:nodes.filter(n=>n.tag==='a').map(n=>({text:n.textContent,href:n.href,rel:n.rel}))}));
'''


@unittest.skipUnless(Path(NODE).is_file(), 'Node runtime unavailable for renderer execution')
class ScientificAssessmentUITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        paths, pins = fixtures(root / 'sources')
        files = {module.SOURCE_NAMES[k]: p.read_bytes() for k, p in paths.items()}
        self.summary = module._summary(files, pins)

    def render(self, **options):
        completed = subprocess.run([NODE, '-e', HARNESS, str(JS)], input=json.dumps({
            'summary': self.summary, 'options': options}), text=True, capture_output=True, check=True)
        return json.loads(completed.stdout)

    def test_actual_renderer_preserves_units_controls_scope_and_safe_text(self):
        self.summary['INMC']['interpretation'] = '<script>should remain literal text</script>'
        result = self.render(publicationId='scientific_test')
        self.assertIsNone(result['error'])
        self.assertNotIn('script', result['tags'])
        self.assertIn('<script>should remain literal text</script>', result['text'])
        self.assertTrue(any('UNKNOWN' in text for text in result['text']))
        self.assertIn('Degree-preserving control', result['text'])
        self.assertEqual(result['tags'].count('table'), 5)  # coverage +2mean +2seed tables
        self.assertTrue(any(x.get('href') == '/api/scientific-assessment/scientific_test/files/sources/history.json'
                            for x in result['links']))
        self.assertTrue(all(x.get('rel') == 'noopener noreferrer' for x in result['links']
                            if x.get('href', '').startswith('https://')))

    def test_renderer_rejects_external_or_protocol_relative_proof_base(self):
        for base in ['https://example.org/', '//example.org/', '/local/?query=unsafe/']:
            with self.subTest(base=base):
                self.assertIn('local absolute', self.render(baseUrl=base)['error'])


if __name__ == '__main__':
    unittest.main()
