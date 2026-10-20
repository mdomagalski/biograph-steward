"""Invented Pharos envelopes and hash-selected union; no CRISPR values."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import PharosClient, digest, write_json
from biograph_steward.comparison_protocol import partitions
from biograph_steward.crc_pilot import sha
from biograph_steward.fresh_retrieval import (LIMITS, POLICY, TISSUE, load_union, prepare_union,
    retrieve_union, union_partitions, verify_union_retrieval)
from biograph_steward.matched_panel import POLICY as OLD_POLICY
from biograph_steward.growth_diagnostics import select_reserve
from test_comparison_protocol import invented_inputs
from test_matched_panel import PanelAPI, inputs


def union_fixture(root):
    data = invented_inputs(); population = deepcopy(data['members'])
    for row in population: row['selection_hash'] = digest({'policy': OLD_POLICY, 'hgnc_id': row['hgnc_id']})
    population.sort(key=lambda r: (r['selection_hash'], r['hgnc_id'])); old = population[:6]
    prior = partitions(old, data['models']); fit = [gid for g in prior['genes'] if g['split'] in {'train', 'validation'} for gid in g['hgnc_ids']]
    exposed_test = [gid for g in prior['genes'] if g['split'] == 'test' for gid in g['hgnc_ids']]
    exposure = {'fit_gene_ids': fit, 'exposed_test_gene_ids': exposed_test}
    reserved, _, _ = select_reserve(population, set(fit + exposed_test), size=2)
    for name in ['panel', 'reservation', 'diagnostics']: (root / name).mkdir()
    p = root / 'panel'; s = root / 'reservation'
    write_json(p / 'eligible_population.json', population); write_json(p / 'crc_models.json', data['models'])
    panel = {'selected_genes': 6, 'eligible_genes': 10, 'cohort_mapping_result_sha256': 'MAP', 'depmap_source_sha256': 'DEPMAP',
        'files': {n: sha(p / n) for n in ['eligible_population.json', 'crc_models.json']}}
    panel['panel_sha256'] = digest(panel)
    write_json(s / 'prior_exposure.json', exposure); write_json(s / 'reserved_members.json', reserved); write_json(s / 'model_partitions.json', prior['models'])
    reserve = {'previous_panel_sha256': panel['panel_sha256'], 'parent_result_sha256': 'PARENT', 'depmap_source_sha256': 'DEPMAP',
        'requested_reserve_genes': 2, 'files': {n: sha(s / n) for n in ['prior_exposure.json', 'model_partitions.json']}}
    reserve['result_sha256'] = digest(reserve)
    diagnostic = {'parent_result_sha256': 'PARENT', 'development_proposal': {'candidate': 'cptac_only'}}; diagnostic['result_sha256'] = digest(diagnostic)
    with patch('biograph_steward.fresh_retrieval.load_panel', return_value=(panel, old)), \
         patch('biograph_steward.fresh_retrieval.verify_reserve', return_value=reserve), \
         patch('biograph_steward.fresh_retrieval.verify_diagnostics', return_value=diagnostic):
        prepare_union(p, s, root / 'diagnostics', root / 'union')
    return data


class FreshRetrievalTests(unittest.TestCase):
    def test_union_reconstructs_members_and_reuses_whole_original_model_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); union_fixture(root); panel, members = load_union(root / 'union')
            self.assertEqual(len(members), 8); self.assertEqual(panel['development_genes'], 6); self.assertEqual(panel['reserved_genes'], 2)
            parts = json.loads((root / 'union/partitions.json').read_text())
            self.assertEqual(parts['models'], json.loads((root / 'reservation/model_partitions.json').read_text()))
            self.assertEqual(sum(len(g['hgnc_ids']) for g in parts['genes'] if g['split'] == 'test'), 2)
            (root / 'union/members.json').write_text('[]')
            with self.assertRaises(ValueError): load_union(root / 'union')

    def test_shared_product_cannot_cross_reserved_and_development_roles(self):
        data = invented_inputs(); old = partitions(data['members'][:6], data['models'])
        exposure = {'fit_gene_ids': [gid for g in old['genes'] if g['split'] in {'train', 'validation'} for gid in g['hgnc_ids']],
            'exposed_test_gene_ids': [gid for g in old['genes'] if g['split'] == 'test' for gid in g['hgnc_ids']]}
        data['members'][6]['protein_candidates'].append(data['members'][0]['protein_candidates'][0])
        with self.assertRaises(ValueError): union_partitions(data['members'], data['models'], exposure, old['models'])

    def panel(self, root):
        root.mkdir(exist_ok=True)
        _, members = inputs(); panel = {'policy': POLICY, 'eligible_genes': 2, 'retrieval_contract': {'limits': LIMITS, 'tissue_words': TISSUE}, 'files': {}}
        write_json(root / 'members.json', members); panel['files']['members.json'] = sha(root / 'members.json'); panel['panel_sha256'] = digest(panel)
        return panel, members

    def test_raw_envelopes_reproduce_full_union_cross_cohort_interaction_and_tissue_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); panel, members = self.panel(root / 'cohort'); api = PanelAPI()
            with patch('biograph_steward.fresh_retrieval.load_union', return_value=(panel, members)):
                result = retrieve_union(root / 'cohort', root / 'out', client=PharosClient(transport=api))
            out = root / 'out'
            self.assertEqual(verify_union_retrieval(out), result)
            source = json.loads((out / 'snapshot.json').read_text())
            by_id = {t['uniprot']: t for t in source['targets']}
            self.assertEqual(by_id['P04637']['pharos_context']['ppis'][0]['target']['uniprot'], 'P00533')
            self.assertEqual(result['retrieval']['ppis']['retained'], 1)

    def test_incomplete_family_is_rejected_without_replacing_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); panel, members = self.panel(root / 'cohort'); api = PanelAPI()
            api.context['P04637']['go'] = [{'goid': 'GO:' + str(i), 'assigned_by': 'TEST'} for i in range(LIMITS['go'] + 1)]
            with patch('biograph_steward.fresh_retrieval.load_union', return_value=(panel, members)):
                with self.assertRaises(ValueError): retrieve_union(root / 'cohort', root / 'out', client=PharosClient(transport=api))
            self.assertTrue((root / 'out/metrics.json').exists())


if __name__ == '__main__': unittest.main()
