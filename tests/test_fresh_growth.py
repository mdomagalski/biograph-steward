"""Invented reserved outcomes: protocol, 200-fit budget, isolation and sealed replay."""
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import PharosClient, digest, write_json
from biograph_steward.crc_pilot import sha
from biograph_steward.fresh_growth import (PRIMARY, ARMS, POLICY, check_access, freeze_fresh,
    permute_field, run_fresh, specification, verify_fresh_protocol, verify_fresh_result)
from biograph_steward.fresh_retrieval import retrieve_union
from biograph_steward.growth_comparison import read_effects, split_ids
from test_fresh_retrieval import union_fixture
from test_matched_panel import PanelAPI
from biograph_steward.retrieval import DEFAULT_LIMITS


def fresh_fixture(root):
    data = union_fixture(root, old_size=30, reserve_size=30, expanded=True)
    api = PanelAPI(); api.rows = []; api.context = {}
    for i, member in enumerate(data['members'], 1):
        uid = member['protein_candidates'][0]['uniprot_id'].removeprefix('UniProtKB:')
        api.rows.append({'uniprot': uid, 'sym': member['approved_symbol'], 'name': 'INVENTED'})
        context = {f: [] for f in DEFAULT_LIMITS}
        context['pathways'] = [{'pwid': i, 'type': 'Reactome', 'sourceID': 'R-HSA-' + str(i % 5 + 1), 'name': 'INVENTED'}]
        context['expressions'] = [{'expid': i, 'type': 'HPM Protein', 'tissue': 'Adult Colon', 'value': str(i)}]
        partner = data['members'][i % len(data['members'])]['protein_candidates'][0]['uniprot_id'].removeprefix('UniProtKB:')
        context['ppis'] = [{'nid': i, 'type': 'BioPlex', 'props': [{'name': 'p_int', 'value': '.9'}], 'target': {'uniprot': partner, 'sym': 'INVENTED'}}]
        api.context[uid] = context
    retrieve_union(root / 'union', root / 'retrieval', client=PharosClient(transport=api))
    mapping = root / 'mapping'; mapping.mkdir(); write_json(mapping / 'mappings.json', data['cptac_mapping_rows'])
    reference = root / 'reference'; reference.mkdir(); raw = b'// INVENTED preserved source, never executed.\n'
    (reference / 'pharos_TCRD.js').write_bytes(raw)
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    write_json(reference / 'pharos_repository_tree.json', {'sha': 'INVENTED-TREE', 'tree': [{'path': 'src/TCRD.js', 'sha': blob}]})
    with patch('biograph_steward.fresh_growth.verify_mapping', return_value={'result_sha256': 'MAP'}), \
         patch('biograph_steward.fresh_growth.verify_protocol', return_value={'depmap_source_sha256': 'DEPMAP', 'cohort_mapping_result_sha256': 'MAP'}):
        protocol = freeze_fresh(root / 'union', root / 'retrieval', mapping, reference, root / 'frozen')
    source = root / 'source'; source.mkdir()
    with (source / 'CRISPRGeneEffect.csv').open('w', newline='') as f:
        writer = csv.writer(f); writer.writerow(['', *[m['depmap_release_label'] for m in data['members']]])
        for i, model in enumerate(data['models']):
            writer.writerow([model['model_id'], *[-(int(m['hgnc_id'].split(':')[1]) % 5) - i * .001 for m in data['members']]])
    return protocol, source


class FreshGrowthTests(unittest.TestCase):
    def test_full_invented_execution_seals_all_models_before_new_genes_and_replays(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); protocol, source = fresh_fixture(root); calls = []
            parts = json.loads((root / 'frozen/partitions.json').read_text()); reserved = set(split_ids(parts, 'genes', {'test'}))
            self.assertEqual(verify_fresh_protocol(root / 'frozen'), protocol)
            with patch('biograph_steward.fresh_growth.load_depmap', return_value={'source_sha256': 'WRONG'}), \
                 patch('biograph_steward.fresh_growth.read_effects') as reader:
                with self.assertRaises(ValueError): run_fresh(root / 'frozen', source, root / 'wrong')
                reader.assert_not_called(); self.assertFalse((root / 'wrong').exists())
            def observe(matrix, inputs, ids, models):
                calls.append(set(ids))
                if len(calls) == 1: self.assertTrue(set(ids).isdisjoint(reserved))
                else:
                    self.assertEqual(set(ids), reserved)
                    seal = json.loads((root / 'result/sealed_predictions.json').read_text())
                    self.assertEqual(len(seal['models']), 51); self.assertFalse(seal['fresh_dependency_values_loaded'])
                    self.assertEqual(seal['primary_candidate'], PRIMARY)
                    self.assertTrue((root / 'result/test_access_receipt.json').exists())
                    self.assertEqual(len(list(root.glob('.reserved_gene_test_access_*.json'))), 1)
                return read_effects(matrix, inputs, ids, models)
            with patch('biograph_steward.fresh_growth.load_depmap', return_value={'source_sha256': 'DEPMAP'}), \
                 patch('biograph_steward.fresh_growth.read_effects', side_effect=observe):
                result = run_fresh(root / 'frozen', source, root / 'result')
            self.assertEqual(len(calls), 2); self.assertEqual(result['ridge_fit_count'], 200)
            self.assertEqual(set(result['arms']), set(ARMS)); self.assertEqual(result['primary_candidate'], PRIMARY)
            self.assertGreater(result['arms'][PRIMARY]['spearman'], .8)
            (source / 'CRISPRGeneEffect.csv').unlink()
            self.assertEqual(verify_fresh_result(root / 'result'), result)
            with patch('biograph_steward.fresh_growth.load_depmap') as loader:
                with self.assertRaisesRegex(ValueError, 'already accessed'): run_fresh(root / 'frozen', source, root / 'again')
                loader.assert_not_called()
            # A new protocol identity cannot reset source-bound gene exposure.
            shutil.copytree(root / 'frozen', root / 'new-protocol')
            changed = deepcopy(protocol); changed['created_at'] = 'INVENTED-NEW-IDENTITY'
            changed['result_sha256'] = digest({k: v for k, v in changed.items() if k != 'result_sha256'}); write_json(root / 'new-protocol/metrics.json', changed)
            with patch('biograph_steward.fresh_growth.load_depmap') as loader:
                with self.assertRaisesRegex(ValueError, 'already accessed'): run_fresh(root / 'new-protocol', source, root / 'new-test')
                loader.assert_not_called()
            self.assertFalse(result['scientific_improvement_established']); self.assertFalse(result['fresh_laboratory_cohort'])
            # Hashes alone are not the score replay: rehashing a changed score still fails.
            scores = json.loads((root / 'result/scores.json').read_text()); scores['arms_and_permutations'][PRIMARY]['spearman'] = -1
            write_json(root / 'result/scores.json', scores); result['files']['scores.json'] = sha(root / 'result/scores.json')
            result['result_sha256'] = digest({k: v for k, v in result.items() if k != 'result_sha256'}); write_json(root / 'result/metrics.json', result)
            with self.assertRaises(ValueError): verify_fresh_result(root / 'result')

    def test_permutation_donors_stay_inside_roles_and_do_not_modify_other_sources(self):
        genes = {'HGNC:' + str(i): {'pathways': [i], 'cptac_median_reported_log2_ratio': -i, 'other': i} for i in range(1, 10)}
        parts = {'genes': [{'split': role, 'hgnc_ids': ['HGNC:' + str(i) for i in ids]} for role, ids in
            [('train', range(1, 4)), ('validation', range(4, 7)), ('test', range(7, 10))]]}
        for field in ['pathways', 'cptac_median_reported_log2_ratio']:
            changed, donors = permute_field(genes, parts, field, 3)
            self.assertEqual((changed, donors), permute_field(genes, parts, field, 3))
            for role in ['train', 'validation', 'test']:
                ids = split_ids(parts, 'genes', {role}); self.assertEqual({donors[g] for g in ids}, set(ids))
                for gid in ids:
                    self.assertEqual(changed[gid][field], genes[donors[gid]][field])
                    self.assertEqual(changed[gid]['other'], genes[gid]['other'])

    def test_rehashed_policy_edit_is_rejected_before_any_numeric_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, source = fresh_fixture(root)
            spec = specification(); spec['budgets']['alpha_grid'].append(100)
            write_json(root / 'frozen/specification.json', spec); r = json.loads((root / 'frozen/metrics.json').read_text())
            r['files']['specification.json'] = sha(root / 'frozen/specification.json')
            r['result_sha256'] = digest({k: v for k, v in r.items() if k != 'result_sha256'}); write_json(root / 'frozen/metrics.json', r)
            with patch('biograph_steward.fresh_growth.read_effects') as reader:
                with self.assertRaises(ValueError): run_fresh(root / 'frozen', source, root / 'out')
                reader.assert_not_called(); self.assertFalse((root / 'out').exists())

    def test_any_prior_overlapping_reserved_gene_blocks_new_selection_but_other_source_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source'; source.mkdir()
            write_json(root / '.reserved_gene_test_access_test.json', {'source_sha256': 'SAME', 'test_gene_ids': ['HGNC:2']})
            check_access(source, 'DIFFERENT', ['HGNC:2'])
            with self.assertRaises(ValueError): check_access(source, 'SAME', ['HGNC:1', 'HGNC:2'])


if __name__ == '__main__': unittest.main()
