"""Invented release fixtures; no live requests, prediction scores or biomedical gold."""
from copy import deepcopy
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest, write_json
from biograph_steward.cohort_mapping import collect_registry, map_cohort
from biograph_steward.cptac import prepare_cptac
from biograph_steward.depmap_audit import (FILES, freeze_depmap, gene_crosswalk, leakage_inventory,
                                         load_depmap, model_coverage, ncbi_id, run_audit, verify_audit)
from biograph_steward.graph import save_run
from test_civic import fixture
from test_cohort_mapping import gene, protein, tsv


def csv_bytes(rows):
    out = StringIO(); writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)
    return out.getvalue().encode()


def model(mid, name, *, lineage='Bowel', disease='Colorectal Adenocarcinoma', kind='Cell Line', patient='PT-TEST'):
    return {'ModelID': mid, 'PatientID': patient, 'CellLineName': name, 'OncotreeLineage': lineage,
            'OncotreePrimaryDisease': disease, 'OncotreeSubtype': 'INVENTED', 'ModelType': kind,
            'EngineeredModel': '', 'CulturedResistanceDrug': ''}


def files_fixture():
    models = [model('ACH-1', '<script>INVENTED</script>'), model('ACH-2', 'INVENTED related model'),
              model('ACH-3', 'INVENTED bowel exclusion', disease='Small Bowel Cancer', patient='PT-OTHER'),
              model('ACH-4', 'INVENTED organoid exclusion', kind='Organoid'),
              model('ACH-5', 'INVENTED other lineage', lineage='Lung', disease='INVENTED', patient='PT-LUNG')]
    genes = [gene('HGNC:1', 'TEST_0'), gene('HGNC:2', 'TEST_1')]
    for g in genes:g['entrez_id'] += '.0'
    screen_map = [{'ScreenID': 'SC-' + str(i), 'ModelID': mid} for i, mid in enumerate(['ACH-1', 'ACH-1', 'ACH-2', 'ACH-3', 'ACH-4', 'ACH-5'])]
    qc = [{'ScreenID': r['ScreenID'], 'ModelID': r['ModelID'], 'ModelConditionID': 'MC-' + r['ModelID'],
           'PassesQC': 'True', 'CanInclude': 'True', 'Library': 'INVENTED', 'ScreenType': '2DS'} for r in screen_map]
    conditions = [{'ModelConditionID': 'MC-' + r['ModelID'], 'ModelID': r['ModelID'], 'CellFormat': 'INVENTED', 'AnchorDrug': ''} for r in models]
    return {'README.txt': b'INVENTED SOFTWARE FIXTURE. No scientific claims.', 'Model.csv': csv_bytes(models),
            'Gene.csv': csv_bytes(genes), 'ModelCondition.csv': csv_bytes(conditions),
            'CRISPRScreenMap.csv': csv_bytes(screen_map), 'AchillesScreenQCReport.csv': csv_bytes(qc),
            'CRISPRInferredModelEfficacy.csv': b'ModelID,INVENTED\nACH-1,1\n',
            'ScreenSequenceMap.csv': b'ScreenID,SequenceID\nSC-1,INVENTED\n',
            'CRISPRGeneEffect.csv': b',OLD_TEST_0 (1),TEST_1 (2)\nACH-1,-9.87654321,\nACH-2,0,NA\nACH-3,1,2\nACH-4,1,2\nACH-5,1,2\n'}


def downloads_fixture(root):
    root.mkdir(); (root / 'downloads').mkdir(); files = []
    for number, (name, raw) in enumerate(sorted(files_fixture().items()), 1):
        (root / 'downloads' / name).write_bytes(raw)
        md5 = hashlib.md5(raw).hexdigest()
        files.append({'name': name, 'id': number, 'size': len(raw), 'computed_md5': md5, 'supplied_md5': md5,
                      'download_url': 'https://ndownloader.figshare.com/files/' + str(number), 'is_link_only': False})
    write_json(root / 'article_27993248_v1.json', {'id': 27993248, 'version': 1, 'title': 'DepMap 24Q4 Public',
        'doi': '10.25452/figshare.plus.27993248.v1', 'published_date': 'INVENTED SOFTWARE FIXTURE',
        'license': {'name': 'INVENTED TEST LICENSE'}, 'files': files})


def mapping_rows():
    return [{'reported_symbol': 'TEST_' + str(i), 'approved_symbol': 'TEST_' + str(i), 'hgnc_id': 'HGNC:' + str(i + 1),
             'identifier_eligible': True, 'protein_context_eligible': True, 'ncbi_gene_id': str(i + 1), 'matrix_row': i + 2} for i in range(3)]


class DepMapContractsTests(unittest.TestCase):
    def test_release_float_ids_normalize_without_rounding_or_symbol_guessing(self):
        self.assertEqual(ncbi_id('3845.0'), '3845'); self.assertIsNone(ncbi_id('3845.5'))
        genes = [gene('HGNC:1', 'DIFFERENT_NAME'), gene('HGNC:2', 'TEST_1')]
        for g in genes:g['entrez_id'] += '.0'
        _, rows = gene_crosswalk(['', 'OLD_TEST_0 (1)', 'TEST_1 (2)'], mapping_rows(), genes)
        self.assertEqual(rows[0]['status'], 'unique_stable_id_match')
        self.assertTrue(rows[0]['release_symbol_differs'])
        self.assertEqual(rows[2]['status'], 'absent_from_gene_effect_matrix')
        with self.assertRaises(ValueError): gene_crosswalk(['', 'NO_ID'], mapping_rows(), genes)

    def test_ambiguous_and_disagreeing_gene_ids_stay_outside_unique_matches(self):
        genes = [gene('HGNC:1', 'ALPHA'), gene('HGNC:2', 'BETA')]; genes[1]['entrez_id'] = '1'
        _, rows = gene_crosswalk(['', 'ALPHA (1)'], mapping_rows(), genes)
        self.assertEqual(rows[0]['status'], 'ambiguous_release_gene_identity')
        changed = mapping_rows(); changed[0]['ncbi_gene_id'] = '999'
        _, rows = gene_crosswalk(['', 'ALPHA (1)'], changed, [genes[0]])
        self.assertEqual(rows[0]['status'], 'ncbi_gene_id_disagreement')
        with self.assertRaises(ValueError): gene_crosswalk(['', 'ALPHA (1)', 'ALPHA (1)'], mapping_rows(), genes)

    def test_crc_is_exact_screened_cell_line_scope_and_screens_are_not_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, raw in files_fixture().items():(root / name).write_bytes(raw)
            stats, rows, models, _ = model_coverage(root, mapping_rows())
            self.assertEqual(stats['metadata_models'], 5); self.assertEqual(stats['screened_crc_cell_lines'], 2)
            self.assertEqual(stats['crc_included_screens'], 3)
            self.assertEqual(stats['crc_patient_sample_groups'], 1)
            self.assertEqual(stats['related_crc_model_groups'], [['ACH-1', 'ACH-2']])
            self.assertEqual(stats['other_cell_line_models_with_documented_2d_context'], 1)
            self.assertEqual(rows[0]['crc_observed_models'], 2); self.assertEqual(rows[1]['crc_observed_models'], 0)
            self.assertEqual(rows[1]['crc_missing_models'], 2)
            self.assertFalse(any(k in rows[0] for k in ['mean_gene_effect', 'dependency_label', 'rank']))
            self.assertFalse(next(r for r in models if r['model_id'] == 'ACH-3')['selected_crc_model'])

    def test_treated_or_unresolved_conditions_are_visible_and_not_eligible_2d_contexts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); files = files_fixture()
            conditions = list(csv.DictReader(StringIO(files['ModelCondition.csv'].decode())))
            conditions[0]['AnchorDrug'] = 'INVENTED drug'
            files['ModelCondition.csv'] = csv_bytes(conditions)
            for name, raw in files.items():(root / name).write_bytes(raw)
            _, _, models, _ = model_coverage(root, mapping_rows())
            first = next(r for r in models if r['model_id'] == 'ACH-1')
            self.assertFalse(first['screen_provenance_eligible_2d'])
            self.assertEqual(first['included_screens'][0]['condition_treatments'], {'AnchorDrug': 'INVENTED drug'})

    def test_nonfinite_duplicate_and_unknown_matrix_models_fail(self):
        for matrix in [b',ALPHA (1)\nACH-1,inf\n', b',ALPHA (1)\nACH-1,1\nACH-1,2\n', b',ALPHA (1)\nUNKNOWN,1\n']:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for name, raw in files_fixture().items():(root / name).write_bytes(raw)
                (root / 'CRISPRGeneEffect.csv').write_bytes(matrix)
                with self.assertRaises(ValueError): model_coverage(root, mapping_rows())

    def test_leakage_inventory_distinguishes_current_inputs_from_historical_probe(self):
        snapshot = {'targets': [{'pharos_context': {'metadata': {'dataSources': ['Harmonizome', 'CCLE']},
            'publications': [{'title': 'INVENTED CRISPR study'}]}, 'gene_effect': -1}], 'requests': []}
        probe = {'response': {'target': {'harmonizome': {'name': 'Achilles shRNA knockdown'}}}}
        result = leakage_inventory(snapshot, probe=probe)
        self.assertEqual(result['summary']['targets_with_harmonizome_flag'], 1)
        self.assertTrue(any(r['category'] == 'source_or_dependency_field_name' and r['value'] == -1 for r in result['materialized_record_hits']))
        self.assertTrue(any('Achilles' in str(r['value']) for r in result['historical_probe_hits']))
        self.assertFalse(any('Achilles' in str(r['value']) for r in result['materialized_record_hits']))


class DepMapArtifactTests(unittest.TestCase):
    def test_archive_is_pinned_and_detects_publisher_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); downloads_fixture(root / 'input')
            freeze_depmap(root / 'input', root / 'source'); load_depmap(root / 'source')
            (root / 'source/CRISPRGeneEffect.csv').write_text('altered')
            with self.assertRaises(ValueError): load_depmap(root / 'source')
            (root / 'input/downloads/Model.csv').write_text('altered')
            with self.assertRaises(ValueError): freeze_depmap(root / 'input', root / 'bad')
            metadata = json.loads((root / 'input/article_27993248_v1.json').read_text()); metadata['version'] = 2
            write_json(root / 'input/article_27993248_v1.json', metadata)
            with self.assertRaises(ValueError): freeze_depmap(root / 'input', root / 'wrong_version')

    def test_real_artifact_pipeline_preserves_controls_and_exports_counts_without_effect_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); downloads_fixture(root / 'input'); freeze_depmap(root / 'input', root / 'source')
            p, _ = fixture(); save_run(p, root / 'pharos'); original = (root / 'pharos/snapshot.json').read_bytes()
            (root / 'matrix.cct').write_bytes(b'attrib_name\tA\tB\nTEST_0\t1\tNA\nTEST_1\t2\t3\n')
            prepare_cptac(root / 'pharos', root / 'cptac', matrix=root / 'matrix.cct')
            h = tsv([gene('HGNC:1', 'TEST_0', products='P04637'), gene('HGNC:2', 'TEST_1', products='P00533')])
            u = tsv([protein('P04637', 'HGNC:1', 'TEST_0'), protein('P00533', 'HGNC:2', 'TEST_1')])
            collect_registry(root / 'registry', transport=lambda url: (h if 'googleapis' in url else u, {}))
            map_cohort(root / 'cptac', root / 'pharos', root / 'registry', root / 'mapping')
            r = run_audit(root / 'source', root / 'mapping', root / 'pharos', root / 'audit')
            self.assertTrue(r['coverage_feasible']); self.assertFalse(r['ready_for_prediction_comparison'])
            self.assertFalse(r['scientific_improvement_established']); self.assertEqual(r['model_requests'], 0)
            self.assertEqual((root / 'pharos/snapshot.json').read_bytes(), original)
            verify_audit(root / 'audit')
            all_outputs = ''.join(p.read_text() for p in (root / 'audit').rglob('*') if p.is_file())
            self.assertNotIn('-9.87654321', all_outputs)
            self.assertIn('&lt;script&gt;', (root / 'audit/report.html').read_text())
            self.assertNotIn('<script>', (root / 'audit/report.html').read_text())
            (root / 'audit/gene_coverage.json').write_text('[]')
            with self.assertRaises(ValueError): verify_audit(root / 'audit')


if __name__ == '__main__':
    unittest.main()
