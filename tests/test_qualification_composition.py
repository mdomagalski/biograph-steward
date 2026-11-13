"""Compatible decision composition never votes over or overwrites a conflict."""
from pathlib import Path
import tempfile
import unittest

from biograph_steward import gold_packet
from biograph_steward.client import write_json
from biograph_steward.demo import demo_snapshot
from biograph_steward.graph import save_run
from tools.sampled_audit.compose_qualifications import compose


class CompositionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        save_run(demo_snapshot(), self.root/'source')
        gold_packet.export_packet(self.root/'source', self.root/'packet')
        self.template = gold_packet._read(self.root/'packet/decisions.template.json')

    def package(self, name, explicit):
        value = gold_packet._read(self.root/'packet/decisions.template.json')
        value['method'] = 'Invented policy ' + name
        value['actor'] = 'Software fixture only'
        for index, decision in enumerate(value['decisions']):
            decision['decision'] = explicit.get(index, 'abstain')
            decision['reason'] = 'Invented context qualification'
        write_json(self.root/(name+'.json'), value)
        gold_packet.save_decisions(self.root/'packet', self.root/(name+'.json'), self.root/name)
        return self.root/name

    def test_disjoint_decisions_apply_together_without_adding_confidence(self):
        first, second = self.package('a', {0: 'keep'}), self.package('b', {1: 'prune'})
        before = [gold_packet._read(p/'decisions.json') for p in (first, second)]
        report = compose([first, second], self.root/'combined')
        self.assertEqual(report['counts']['keep'], 1)
        self.assertEqual(report['counts']['prune'], 1)
        output = gold_packet._read(self.root/'combined/decisions.json')
        self.assertTrue(all(d['confidence'] is None for d in output['decisions']))
        self.assertEqual(before, [gold_packet._read(p/'decisions.json') for p in (first, second)])

    def test_conflicting_keep_prune_fails_before_output_without_precedence(self):
        first, second = self.package('a', {0: 'keep'}), self.package('b', {0: 'prune'})
        with self.assertRaisesRegex(ValueError, 'Conflicting keep/prune'):
            compose([first, second], self.root/'combined')
        self.assertFalse((self.root/'combined').exists())

    def test_repeated_input_is_rejected(self):
        first = self.package('a', {0: 'keep'})
        with self.assertRaisesRegex(ValueError, 'repeat'):
            compose([first, first], self.root/'combined')


if __name__ == '__main__':
    unittest.main()
