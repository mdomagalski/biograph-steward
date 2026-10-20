"""Invented source-pattern fixtures; extraction is not biological adjudication."""
from copy import deepcopy
import hashlib
import unittest

from biograph_steward.client import digest
from biograph_steward.source_facts import compile_source, validate_dossier


def paper(*paragraphs):
    return {'pmid': '90000123', 'title': 'INVENTED SOFTWARE FIXTURE',
            'abstract': [{'text': text, 'section': section, 'locator': '/invented/abstract/' + str(index)}
                         for index, (section, text) in enumerate(paragraphs)]}


def response_paper():
    return paper(('METHODS', 'Adults with mutant KRAS G13D received sotorasib monotherapy (100 mg daily) '
        'or sotorasib (at the same dose) in combination with intravenous panitumumab.'),
        ('RESULTS', 'Évaluation — 22 patients received sotorasib and 17 received combination therapy. '
         'In the monotherapy group (18 evaluable patients), a response was reported in 31.5% of patients. '
         'In the combination-therapy group (12 evaluable patients), the response was 67% of patients.'))


class SourceFactTests(unittest.TestCase):
    def test_response_arms_bind_evaluable_counts_not_treated_counts(self):
        source = response_paper()
        before = deepcopy(source)
        dossier = compile_source(source)
        self.assertEqual(source, before)
        self.assertEqual(dossier['source_id'], 'PubMed:90000123')
        self.assertEqual(dossier['source_sha256'], digest(source))
        self.assertEqual(dossier['paper'], source)
        self.assertIsNot(dossier['paper'], source)
        self.assertEqual([(r['regimen'], r['value'], r['evaluable_n']) for r in dossier['records']],
                         [(['sotorasib'], '31.5', 18), (['panitumumab', 'sotorasib'], '67', 12)])
        for record in dossier['records']:
            self.assertEqual(record['molecular'], {'gene': 'KRAS', 'state': 'variant', 'variant': 'G13D'})
            self.assertEqual(record['endpoint'], 'response_rate')
            self.assertIsNone(record['comparator'])
            self.assertEqual(record['association_status'], 'pattern_extracted_unreviewed')
            self.assertIsNone(record['effect_direction'])
        self.assertIs(validate_dossier(dossier, source), dossier)

    def test_endpoint_significance_and_nearest_stratum_remain_associated(self):
        source = paper(('RESULTS',
            'In the wild-type (WT) KRAS stratum, panitumumab-FOLFOX4 significantly improved PFS compared with FOLFOX4 (P = .03). '
            'A nonsignificant increase in OS was observed for panitumumab-FOLFOX4 versus FOLFOX4 (P = .12). '
            'In the mutant KRAS stratum, panitumumab-FOLFOX4 significantly reduced PFS compared with FOLFOX4 (P = .04).'),
            ('RESULTS', 'Panitumumab-FOLFOX4 significantly improved PFS compared with FOLFOX4 (P = .01).'))
        dossier = compile_source(source)
        records = dossier['records']
        self.assertEqual([(r['endpoint'], r['significance'], r['p_value'], r['molecular']['state'] if r['molecular'] else None)
                          for r in records], [('PFS', 'significant', '0.03', 'wild_type'),
                          ('OS', 'not_significant', '0.12', 'wild_type'),
                          ('PFS', 'significant', '0.04', 'mutant_unspecified'),
                          ('PFS', 'significant', '0.01', None)])
        self.assertTrue(all(r['regimen'] == ['folfox4', 'panitumumab'] and r['comparator'] == ['folfox4'] for r in records))
        self.assertEqual([r['effect_direction'] for r in records], ['increase', 'increase', 'decrease', 'increase'])
        self.assertEqual(records[2]['provenance']['effect_direction'][0]['text'], 'reduced')
        self.assertIn('molecular_scope_unresolved', [g['code'] for g in dossier['coverage_gaps']])

    def test_multiendpoint_mutant_unit_is_a_gap_and_does_not_reuse_wild_type_scope(self):
        source = paper(('RESULTS', 'In the wild-type (WT) KRAS stratum, panitumumab-FOLFOX4 significantly improved PFS '
            'compared with FOLFOX4 (P = .03). In the mutant KRAS stratum, PFS was significantly reduced for '
            'panitumumab-FOLFOX4 versus FOLFOX4 (P = .04), and OS increased (P = .08).'))
        dossier = compile_source(source)
        self.assertEqual(len(dossier['records']), 1)
        self.assertEqual(dossier['records'][0]['molecular']['state'], 'wild_type')
        skipped = [g for g in dossier['coverage_gaps'] if g['code'] == 'ambiguous_multiple_endpoints']
        self.assertEqual(len(skipped), 1)
        self.assertIn('mutant KRAS', skipped[0]['provenance'][0]['text'])

    def test_author_qualifiers_are_not_inferred_from_p_value(self):
        source = paper(('RESULTS', 'In the wild-type KRAS stratum, panitumumab-FOLFOX4 improved PFS '
            'compared with FOLFOX4 (P = .001). A nonsignificant increase in OS was observed for '
            'panitumumab-FOLFOX4 versus FOLFOX4 (P = .001).'))
        dossier = compile_source(source)
        self.assertEqual([(r['endpoint'], r['significance']) for r in dossier['records']], [('OS', 'not_significant')])
        self.assertIn('unsupported_survival_language', [g['code'] for g in dossier['coverage_gaps']])

    def test_absent_or_negated_effect_direction_is_not_fabricated(self):
        source = paper(('RESULTS', 'In the wild-type KRAS stratum, a statistically significant difference in PFS '
            'was observed for panitumumab-FOLFOX4 versus FOLFOX4 (P = .03). '
            'No significant increase in OS was observed for panitumumab-FOLFOX4 versus FOLFOX4 (P = .12).'))
        dossier = compile_source(source)
        self.assertEqual(len(dossier['records']), 2)
        self.assertTrue(all(r['effect_direction'] is None and 'effect_direction' not in r['provenance']
                            for r in dossier['records']))
        self.assertEqual(sum(g['code'] == 'effect_direction_unresolved' for g in dossier['coverage_gaps']), 2)

    def test_denied_or_hypothetical_findings_are_not_positive_survival_records(self):
        sentences = [
            'There was no evidence that panitumumab-FOLFOX4 significantly increased PFS compared with FOLFOX4 (P = .03).',
            'Panitumumab-FOLFOX4 did not significantly increase PFS compared with FOLFOX4 (P = .03).',
            'A significant increase in PFS was not observed for panitumumab-FOLFOX4 versus FOLFOX4 (P = .03).',
            'Panitumumab-FOLFOX4 might significantly increase PFS compared with FOLFOX4 (P = .03).']
        for sentence in sentences:
            with self.subTest(sentence=sentence):
                dossier = compile_source(paper(('RESULTS', 'In the wild-type KRAS stratum, ' + sentence)))
                self.assertEqual(dossier['records'], [])
                self.assertIn('unsupported_negated_or_uncertain_report', [g['code'] for g in dossier['coverage_gaps']])

    def test_ambiguous_or_unknown_arms_are_not_completed_from_cooccurrence(self):
        result = ('RESULTS', 'In the monotherapy group (18 evaluable patients), a response was reported in 31%. '
                  'In the combination-therapy group (12 evaluable patients), the response was 67%.')
        definitions = [
            'Patients received sotorasib monotherapy or adagrasib monotherapy. They also received sotorasib plus panitumumab or adagrasib plus cetuximab.',
            'Patients received sotorasib or adagrasib plus cetuximab.',
            'Patients received sotorasib plus panitumumab and irinotecan.',
            'Patients received unknownximab monotherapy or unknownximab plus anotherximab.']
        for methods in definitions:
            with self.subTest(methods=methods):
                dossier = compile_source(paper(('METHODS', methods), result))
                self.assertEqual(dossier['records'], [])
                self.assertIn('ambiguous_or_missing_regimen_definition', [g['code'] for g in dossier['coverage_gaps']])

    def test_molecular_fallback_requires_a_single_methods_variant(self):
        source = response_paper()
        source['abstract'][0]['text'] += ' Another cohort had KRAS G12C.'
        dossier = compile_source(source)
        self.assertEqual(len(dossier['records']), 2)
        self.assertTrue(all(r['molecular'] is None for r in dossier['records']))
        self.assertIn('molecular_scope_unresolved', [g['code'] for g in dossier['coverage_gaps']])

    def test_denied_regimen_or_excluded_variant_is_not_a_positive_definition(self):
        source = paper(('METHODS', 'Patients did not receive sotorasib monotherapy.'),
                       ('RESULTS', 'In the monotherapy group (18 evaluable patients), a response was reported in 31%.'))
        dossier = compile_source(source)
        self.assertEqual(dossier['records'], [])
        self.assertIn('ambiguous_or_missing_regimen_definition', [g['code'] for g in dossier['coverage_gaps']])
        source = response_paper()
        source['abstract'][0]['text'] = ('Patients without KRAS G13D received sotorasib monotherapy '
                                        'or sotorasib in combination with panitumumab.')
        dossier = compile_source(source)
        self.assertEqual(len(dossier['records']), 2)
        self.assertTrue(all(r['molecular'] is None for r in dossier['records']))
        source = response_paper()
        source['abstract'][1]['text'] = ('We hypothesized: In the monotherapy group (18 evaluable patients), '
                                         'a response was reported in 31%.')
        dossier = compile_source(source)
        self.assertEqual(dossier['records'], [])
        self.assertIn('unsupported_negated_or_uncertain_report', [g['code'] for g in dossier['coverage_gaps']])

    def test_unknown_extra_therapy_is_not_silently_removed_from_an_arm(self):
        source = response_paper()
        source['abstract'][0]['text'] = ('Patients with KRAS G13D received sotorasib monotherapy or '
            'sotorasib in combination with panitumumab plus bevacizumab.')
        dossier = compile_source(source)
        self.assertEqual([r['regimen'] for r in dossier['records']], [['sotorasib']])
        self.assertIn('ambiguous_or_missing_regimen_definition', [g['code'] for g in dossier['coverage_gaps']])
        for arm in ('panitumumab-FOLFOX4 plus bevacizumab', 'bevacizumab plus panitumumab-FOLFOX4'):
            with self.subTest(arm=arm):
                dossier = compile_source(paper(('RESULTS', 'In the wild-type KRAS stratum, ' + arm +
                    ' significantly improved PFS compared with FOLFOX4 (P = .03).')))
                self.assertEqual(dossier['records'], [])

    def test_significance_and_direction_cannot_be_borrowed_from_another_outcome(self):
        source = paper(('RESULTS', 'In the wild-type KRAS stratum, panitumumab-FOLFOX4 improved PFS '
            'compared with FOLFOX4; toxicity was statistically significant (P = .02).'))
        dossier = compile_source(source)
        self.assertEqual(dossier['records'], [])
        self.assertIn('unsupported_multiple_result_clauses', [g['code'] for g in dossier['coverage_gaps']])
        source = paper(('RESULTS', 'In the wild-type KRAS stratum, a statistically significant difference in OS '
            'was observed for panitumumab-FOLFOX4 versus FOLFOX4 (P = .02), with improved nausea.'))
        dossier = compile_source(source)
        self.assertEqual(len(dossier['records']), 1)
        self.assertIsNone(dossier['records'][0]['effect_direction'])
        self.assertIn('effect_direction_unresolved', [g['code'] for g in dossier['coverage_gaps']])

    def test_excluded_nearest_stratum_does_not_inherit_an_earlier_context(self):
        source = paper(('RESULTS', 'The mutant KRAS stratum was described. The wild-type KRAS stratum was excluded from analysis. '
            'A nonsignificant increase in OS was observed for panitumumab-FOLFOX4 versus FOLFOX4 (P = .12).'))
        dossier = compile_source(source)
        self.assertEqual(len(dossier['records']), 1)
        self.assertIsNone(dossier['records'][0]['molecular'])
        self.assertNotIn('molecular', dossier['records'][0]['provenance'])

    def test_duplicate_occurrences_and_non_ascii_use_exact_parent_codepoint_offsets(self):
        source = response_paper()
        duplicate = deepcopy(source['abstract'][1])
        duplicate['locator'] = '/invented/duplicate'
        source['abstract'].append(duplicate)
        dossier = compile_source(source)
        self.assertEqual(len(dossier['records']), 4)
        self.assertEqual(len({r['id'] for r in dossier['records']}), 4)
        for record in dossier['records']:
            for spans in record['provenance'].values():
                for span in spans:
                    parent = source['abstract'][span['passage_index']]
                    self.assertEqual(parent['text'][span['start']:span['end']], span['text'])
                    self.assertEqual(span['locator'], parent['locator'])
                    self.assertEqual(span['offset_unit'], 'unicode_codepoints')
                    self.assertEqual(span['text_sha256'], hashlib.sha256(span['text'].encode('utf-8')).hexdigest())
        rate = dossier['records'][0]['provenance']['value'][0]
        paragraph = source['abstract'][rate['passage_index']]['text']
        self.assertEqual(rate['start'], paragraph.index('31.5'))
        self.assertNotEqual(rate['start'], len(paragraph[:rate['start']].encode('utf-8')))

    def test_multiple_response_matches_in_one_sentence_are_all_compiled(self):
        source = response_paper()
        source['abstract'][1]['text'] = ('In the monotherapy group (18 evaluable patients), a response was reported in 31%; '
            'In the combination-therapy group (12 evaluable patients), the response was 67%.')
        self.assertEqual([r['value'] for r in compile_source(source)['records']], ['31', '67'])

    def test_semantic_field_swaps_and_exact_span_swaps_fail_replay(self):
        source = response_paper()
        dossier = compile_source(source)
        for mutate in (lambda d: d['records'][0].update(value='67'),
                       lambda d: d['records'][0].update(regimen=['panitumumab', 'sotorasib']),
                       lambda d: d['records'][0].update(evaluable_n=22),
                       lambda d: d['records'][0]['provenance'].update(value=deepcopy(d['records'][1]['provenance']['value'])),
                       lambda d: d['coverage_gaps'].append({'code': 'invented'}),
                       lambda d: d['paper'].update(title='ALTERED SOURCE')):
            changed = deepcopy(dossier)
            mutate(changed)
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    validate_dossier(changed)
        changed_source = deepcopy(source)
        changed_source['title'] = 'DIFFERENT EXTERNAL SOURCE'
        with self.assertRaises(ValueError):
            validate_dossier(dossier, changed_source)

    def test_unsupported_source_and_invalid_input_remain_explicit(self):
        source = paper(('RESULTS', 'Response rates were promising in several unnamed groups.'))
        dossier = compile_source(source)
        self.assertEqual(dossier['records'], [])
        self.assertIn('no_supported_facts', [g['code'] for g in dossier['coverage_gaps']])
        self.assertIn('scientific truth', ' '.join(dossier['compiler']['limitations']))
        self.assertTrue(all(g['action'] == 'review' for g in dossier['coverage_gaps']))
        with self.assertRaises(ValueError):
            compile_source({'pmid': 'invalid', 'title': 'fixture', 'abstract': []})
        with self.assertRaises(ValueError):
            compile_source(paper(('RESULTS', 'fixture')) | {'abstract': [{'text': 'missing locator'}]})


if __name__ == '__main__':
    unittest.main()
