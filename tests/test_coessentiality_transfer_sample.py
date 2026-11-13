"""Invented metadata-only sample controls; no biomedical outcomes or sources."""
from copy import deepcopy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from test_cohort_mapping import gene, protein, registry
from tools.coessentiality_feasibility.identifiers import native_order
from tools.coessentiality_transfer import sample as sampler


def fixture(count=1):
    genes = []; proteins = []; names = []; fields = []
    for i in range(1, count + 1):
        gid, accession = 'HGNC:' + str(i), 'P' + str(i).zfill(5)
        g = gene(gid, 'CURRENT_' + str(i), products=accession); g['location'] = '1p36.13'; genes.append(g)
        proteins.append(protein(accession, gid, g['symbol']))
        names.append('NATIVE_' + str(i)); fields.append(names[-1] + ' (' + str(i) + ')')
    return registry(genes, proteins), native_order('\n'.join(names) + '\n', 'Broad_ID,' + ','.join(fields) + '\n')


EMPTY_OLD = {'gene_ids': [], 'hgnc_ids': [], 'products': []}


class ProspectiveMetadataTests(unittest.TestCase):
    def test_native_Entrez_not_symbol_guess_and_no_outcome_fields(self):
        r, order = fixture(); before = deepcopy(order)
        frame, ledger = sampler.eligible_frame(order, r, EMPTY_OLD)
        self.assertEqual(frame[0]['approved_symbol'], 'CURRENT_1')
        self.assertEqual(frame[0]['native_matrix_symbol'], 'NATIVE_1')
        self.assertEqual(frame[0]['subject'], 'UniProtKB:P00001')
        self.assertFalse(frame[0]['gene_product_mapping_claims_identity'])
        r.genes['HGNC:1']['Pharos_found'] = False; r.proteins['P00001']['fitness'] = 'invented'; r.genes['HGNC:1']['TDL'] = 'Tdark'
        self.assertEqual(sampler.eligible_frame(order, r, EMPTY_OLD), (frame, ledger))
        self.assertEqual(order, before)

    def test_old_gene_HGNC_or_product_identity_excluded_without_aliases(self):
        r, order = fixture()
        for key, value in [('gene_ids', '1'), ('hgnc_ids', 'HGNC:1'), ('products', 'UniProtKB:P00001')]:
            old = deepcopy(EMPTY_OLD); old[key] = [value]
            frame, ledger = sampler.eligible_frame(order, r, old)
            self.assertEqual(frame, []); self.assertEqual(ledger[0]['status'], 'excluded_original_gene_HGNC_or_product')

    def test_multiple_or_conflicting_reviewed_products_not_chosen(self):
        g = gene('HGNC:1', 'A', products='P00001|P00002'); g['location'] = '1p36.13'
        for ncbi in ['1', '999']:
            r = registry([g], [protein('P00001', 'HGNC:1', 'A'), protein('P00002', 'HGNC:1', 'A', ncbi=ncbi)])
            order = native_order('A\n', 'Broad_ID,A (1)\n'); frame, ledger = sampler.eligible_frame(order, r, EMPTY_OLD)
            self.assertEqual(frame, [])
            self.assertEqual(ledger[0]['reviewed_canonical_product_candidates'], ['P00001', 'P00002'])
            details = sampler.conflict_details(ledger, r)
            self.assertEqual(len(details), int(ncbi != '1'))
            if details:
                self.assertEqual(len(details[0]['all_candidate_products']), 2)

    def test_nonunique_native_ID_and_ambiguous_chromosome_are_UNKNOWN(self):
        r, order = fixture(); duplicate = deepcopy(order[0]); duplicate['matrix_index'] = 99
        self.assertEqual(sampler.eligible_frame(order + [duplicate], r, EMPTY_OLD)[0], [])
        r.genes['HGNC:1']['location'] = '1p36 or 2q21'
        self.assertEqual(sampler.eligible_frame(order, r, EMPTY_OLD)[0], [])
        r.genes['HGNC:1']['location'] = '1p36-p35'
        self.assertEqual(len(sampler.eligible_frame(order, r, EMPTY_OLD)[0]), 1)

    def test_single_draw_exact_fixed_seed_order_and_no_replacements(self):
        r, order = fixture(140); frame, ledger = sampler.eligible_frame(order, r, EMPTY_OLD)
        expected = sorted(random.Random(2026111302).sample(frame, 128), key=lambda x: int(x['ncbi_gene_id']))
        self.assertEqual(sampler.draw(frame), expected); self.assertEqual(sampler.draw(frame), expected)
        self.assertEqual(len({x['ncbi_gene_id'] for x in expected}), 128)
        with self.assertRaises(ValueError):
            sampler.draw(frame[:127])
        with self.assertRaises(ValueError):
            sampler.draw(list(reversed(frame)))

    def test_pair_frame_preserves_all_queries_and_canonical_pair_order(self):
        r, order = fixture(3); r.genes['HGNC:2']['location'] = '2q21'; frame, ledger = sampler.eligible_frame(order, r, EMPTY_OLD)
        pairs = sampler.pairs_for(frame)
        self.assertEqual(len(pairs), 3)
        self.assertEqual({tuple(x['gene_pair']): x['scope'] for x in pairs},
                         {('1', '2'): 'nonsyntenic', ('1', '3'): 'syntenic', ('2', '3'): 'nonsyntenic'})


class ProspectiveFreezeTests(unittest.TestCase):
    def inputs(self, root):
        r, order = fixture(140); source = root / 'input'; source.mkdir()
        paths = {k: source / k for k in ['genes', 'header', 'registry', 'old_gold', 'old_capture']}
        for p in paths.values():
            p.write_text('invented metadata')
        pins = {str(p): sha(p) for p in paths.values()}
        return paths, (paths, order, {'registry_sha256': 'invented_registry'}, r, EMPTY_OLD, [], pins)

    def test_protocol_is_sealed_before_draw_and_resealed_scope_mutation_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); paths, inputs = self.inputs(root); out = root / 'sample'; original_draw = sampler.draw
            def checked_draw(frame):
                self.assertTrue((out / 'protocol.json').is_file())
                self.assertIn('content_sha256', json.loads((out / 'protocol.json').read_text()))
                return original_draw(frame)
            with patch.object(sampler, 'source_inputs', return_value=inputs), patch.object(sampler, 'draw', side_effect=checked_draw):
                sampler.prepare(*paths.values(), out)
            with patch.object(sampler, 'source_inputs', return_value=inputs):
                sampler.verify(out)
                protocol = json.loads((out / 'protocol.json').read_text()); protocol['no_replacements_or_outcome_driven_reframing'] = False
                protocol.pop('content_sha256'); protocol['content_sha256'] = digest(protocol); write_json(out / 'protocol.json', protocol)
                report = json.loads((out / 'report.json').read_text()); report['protocol_content_sha256'] = protocol['content_sha256']
                report['files']['protocol.json'] = sha(out / 'protocol.json'); report.pop('content_sha256'); report['content_sha256'] = digest(report)
                write_json(out / 'report.json', report)
                with self.assertRaisesRegex(ValueError, 'scientific exposure protocol differs'):
                    sampler.verify(out)

    def test_code_mutation_during_metadata_stage_cannot_seal_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); paths, inputs = self.inputs(root); code = root / 'producer.txt'; code.write_text('before')
            def changed(*args, **kwargs):
                code.write_text('after'); return inputs
            with patch.object(sampler, 'ROOT', root), patch.object(sampler, 'IMPLEMENTATIONS', ['producer.txt']), \
                 patch.object(sampler, 'source_inputs', side_effect=changed):
                with self.assertRaisesRegex(ValueError, 'code changed'):
                    sampler.prepare(*paths.values(), root / 'sample')
            self.assertFalse((root / 'sample/report.json').exists())


if __name__ == '__main__':
    unittest.main()
